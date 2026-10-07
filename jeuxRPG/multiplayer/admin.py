import re
import json
import secrets
import time

from .service import GameError, digest


def accounts(service, search="", offset=0):
    if len(search) > 64 or offset < 0 or offset > 100000:
        raise GameError("invalid_search", "Recherche invalide.")
    with service._transaction():
        rows = service.db.execute("""SELECT p.id,p.name,p.class_name,p.scope,
            MAX(COALESCE(a.suspended,0),COALESCE(ac.suspended,0)) AS suspended,ac.id AS account_id,ac.username FROM players p
            LEFT JOIN account_status a ON a.player_id=p.id
            LEFT JOIN account_characters c ON c.player_id=p.id LEFT JOIN accounts ac ON ac.id=c.account_id
            WHERE instr(lower(p.name),lower(?))>0 OR p.id=? OR instr(lower(COALESCE(ac.username,'')),lower(?))>0
            ORDER BY p.name,p.id LIMIT 51 OFFSET ?""", (search, search, search, offset)).fetchall()
        return {"accounts": [dict(row) for row in rows[:50]], "has_more": len(rows) > 50}


def update_account(service, body):
    if set(body) not in ({"player_id", "action"}, {"player_id", "action", "name"}):
        raise GameError("invalid_command", "Paramètres invalides.")
    identifier, action = body.get("player_id"), body.get("action")
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise GameError("invalid_player", "Compte invalide.")
    if action not in ("rename", "suspend", "restore", "revoke") or ("name" in body) != (action == "rename"):
        raise GameError("invalid_command", "Action invalide.")
    with service._transaction():
        if not service.db.execute("SELECT id FROM players WHERE id=?", (identifier,)).fetchone():
            raise GameError("not_found", "Compte introuvable.", 404)
        if action == "rename":
            name = service._name(body["name"])
            service.db.execute("UPDATE players SET name=? WHERE id=?", (name, identifier))
            rows = service.db.execute("SELECT t.session_id,t.data FROM tutorials t JOIN members m ON m.session_id=t.session_id WHERE m.player_id=?", (identifier,)).fetchall()
            for row in rows:
                party = json.loads(row["data"])
                if identifier in party.get("characters", {}):
                    party["characters"][identifier]["name"] = name
                    service.dirty_sessions.add(row['session_id'])
                    service.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), row["session_id"]))
                    service.db.execute("UPDATE sessions SET revision=revision+1 WHERE id=?", (row["session_id"],))
        elif action == "revoke":
            service.db.execute("UPDATE account_sessions SET expires=0 WHERE account_id IN (SELECT account_id FROM account_characters WHERE player_id=?)", (identifier,))
            service.persistent_social_changed = True
            service.db.execute("UPDATE players SET token_hash=? WHERE id=?", (digest(secrets.token_urlsafe(32)), identifier))
        else:
            service.db.execute("UPDATE accounts SET suspended=? WHERE id IN (SELECT account_id FROM account_characters WHERE player_id=?)", (int(action == "suspend"), identifier))
            service.persistent_social_changed = True
            service.db.execute("INSERT INTO account_status VALUES(?,?) ON CONFLICT(player_id) DO UPDATE SET suspended=excluded.suspended", (identifier, int(action == "suspend")))
            service.db.execute("DELETE FROM presence WHERE player_id=?", (identifier,))
        service.db.execute("INSERT INTO admin_audit(player_id,action,created) VALUES(?,?,?)", (identifier, action, time.time()))
    return {"ok": True}
