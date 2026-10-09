import hashlib
import hmac
import json
import re
import secrets
import time


SESSION_SECONDS = 30 * 86400


def password_hash(password, salt=None):
    from .service import GameError
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise GameError('invalid_password', 'Le mot de passe doit contenir 12 à 128 caractères.')
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=131072, r=8, p=1, maxmem=192 * 1024 * 1024).hex()
    return 'scrypt$' + salt + '$' + value


class AccountMixin:
    def account_identity(self, token):
        from .service import GameError, digest
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise GameError('unauthorized', 'Connectez-vous à votre compte.', 401)
        row = self.db.execute('SELECT a.id,a.username,a.suspended,s.player_id FROM accounts a JOIN account_sessions s ON s.account_id=a.id WHERE s.token_hash=? AND s.expires>?', (digest(token), time.time())).fetchone()
        if row is None:
            raise GameError('unauthorized', 'Connectez-vous à votre compte.', 401)
        if row['suspended']:
            raise GameError('account_suspended', 'Compte suspendu.', 403)
        return row

    def account_view(self, token):
        with self._transaction():
            account = self.account_identity(token)
            characters = [dict(row) for row in self.db.execute('SELECT p.id,p.name,p.class_name FROM account_characters c JOIN players p ON p.id=c.player_id WHERE c.account_id=? ORDER BY p.class_name', (account['id'],))]
            return {'account': {'id': account['id'], 'username': account['username']}, 'characters': characters, 'selected': account['player_id']}

    def prepare_account_login(self, username, password, signup=False):
        from .service import GameError
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,24}', username):
            raise GameError('invalid_username', 'Nom de compte : 3 à 24 lettres, chiffres ou underscores.')
        with self._lock:
            row = self.db.execute('SELECT password_hash FROM accounts WHERE username_key=?', (username.casefold(),)).fetchone()
        expected = row[0] if row else None
        calculated = password_hash(password, expected.split('$')[1] if expected and not signup else None)
        return expected, calculated

    def account_login(self, username, password, signup=False, _prepared=None):
        from .service import GameError, digest
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,24}', username):
            raise GameError('invalid_username', 'Nom de compte : 3 à 24 lettres, chiffres ou underscores.')
        with self._lock:
            expected = self.db.execute('SELECT password_hash FROM accounts WHERE username_key=?', (username.casefold(),)).fetchone()
        if _prepared is not None and _prepared[0] == (expected[0] if expected else None):
            calculated = _prepared[1]
        else:
            calculated = password_hash(password, expected[0].split('$')[1] if expected and not signup else None)
        with self._transaction():
            account = self.db.execute('SELECT * FROM accounts WHERE username_key=?', (username.casefold(),)).fetchone()
            if signup:
                if account:
                    raise GameError('account_exists', 'Ce nom de compte est déjà utilisé.', 409)
                identifier = secrets.token_hex(16)
                self.db.execute('INSERT INTO accounts VALUES(?,?,?,?,?,?)', (identifier, username, username.casefold(), calculated, 0, time.time()))
                account = self.db.execute('SELECT * FROM accounts WHERE id=?', (identifier,)).fetchone()
            else:
                if account is None or not hmac.compare_digest(calculated, account['password_hash']):
                    raise GameError('unauthorized', 'Nom de compte ou mot de passe incorrect.', 401)
                if account['suspended']:
                    raise GameError('account_suspended', 'Compte suspendu.', 403)
            self.db.execute('DELETE FROM account_sessions WHERE expires<=?', (time.time(),))
            token = secrets.token_urlsafe(32)
            self.db.execute('INSERT INTO account_sessions VALUES(?,?,NULL,?)', (digest(token), account['id'], time.time() + SESSION_SECONDS))
            self.db.execute('DELETE FROM account_sessions WHERE account_id=? AND token_hash NOT IN (SELECT token_hash FROM account_sessions WHERE account_id=? ORDER BY expires DESC LIMIT 5)', (account['id'], account['id']))
            self.persistent_social_changed = True
            return {'token': token, **self.account_view(token)}

    def account_sessions(self, token):
        from .service import digest
        with self._transaction():
            account = self.account_identity(token)
            current = digest(token)
            rows = self.db.execute(
                "SELECT token_hash,player_id,expires FROM account_sessions WHERE account_id=? AND expires>? ORDER BY expires DESC",
                (account["id"], time.time()),
            ).fetchall()
            return {
                "sessions": [
                    {
                        "current": row["token_hash"] == current,
                        "player_id": row["player_id"],
                        "expires": row["expires"],
                    }
                    for row in rows
                ]
            }

    def account_change_password(self, token, current_password, new_password):
        from .service import GameError, digest
        if not isinstance(current_password, str) or not isinstance(new_password, str):
            raise GameError("invalid_password", "Mot de passe invalide.")
        with self._transaction():
            account = self.account_identity(token)
            row = self.db.execute(
                "SELECT password_hash FROM accounts WHERE id=?", (account["id"],)
            ).fetchone()
            expected = row["password_hash"]
            calculated = password_hash(current_password, expected.split("$")[1])
            if not hmac.compare_digest(calculated, expected):
                raise GameError("unauthorized", "Mot de passe actuel incorrect.", 401)
            replacement = password_hash(new_password)
            new_token = secrets.token_urlsafe(32)
            expires = time.time() + SESSION_SECONDS
            self.db.execute(
                "UPDATE accounts SET password_hash=? WHERE id=?",
                (replacement, account["id"]),
            )
            self.db.execute(
                "UPDATE account_sessions SET expires=0 WHERE account_id=?",
                (account["id"],),
            )
            self.db.execute(
                "INSERT INTO account_sessions(token_hash,account_id,player_id,expires) VALUES(?,?,?,?)",
                (digest(new_token), account["id"], account["player_id"], expires),
            )
            self.persistent_social_changed = True
            return {"token": new_token, **self.account_view(new_token)}

    def account_logout_all(self, token):
        with self._transaction():
            account = self.account_identity(token)
            self.db.execute(
                "UPDATE account_sessions SET expires=0 WHERE account_id=?",
                (account["id"],),
            )
            for row in self.db.execute(
                "SELECT player_id FROM account_characters WHERE account_id=?",
                (account["id"],),
            ):
                self.runtime_presence.pop(row["player_id"], None)
                self.db.execute(
                    "DELETE FROM presence WHERE player_id=?", (row["player_id"],)
                )
            self.persistent_social_changed = True
            return {"ok": True}

    def account_character(self, token, action, **params):
        from .service import GameError, digest
        with self._transaction():
            account = self.account_identity(token)
            if action == 'create':
                if set(params) != {'name', 'class_name'}:
                    raise GameError('invalid_command', 'Paramètres de personnage invalides.')
                if self.db.execute('SELECT 1 FROM account_characters WHERE account_id=? AND class_name=?', (account['id'], params['class_name'])).fetchone():
                    raise GameError('class_exists', 'Vous possédez déjà un personnage de cette classe.', 409)
                player = self._register(params['name'], params['class_name'], 'local')['player']
                self.db.execute('INSERT INTO account_characters VALUES(?,?,?)', (account['id'], player['class_name'], player['id']))
                identifier = player['id']
            elif action == 'select' and set(params) == {'player_id'}:
                identifier = params['player_id']
                if not self.db.execute('SELECT 1 FROM account_characters WHERE account_id=? AND player_id=?', (account['id'], identifier)).fetchone():
                    raise GameError('not_found', 'Personnage introuvable.', 404)
            else:
                raise GameError('invalid_command', 'Action de personnage invalide.')
            previous = [row[0] for row in self.db.execute('SELECT player_id FROM account_sessions WHERE account_id=? AND player_id IS NOT NULL', (account['id'],))]
            for old in previous:
                if old != identifier:
                    self.runtime_presence.pop(old, None)
                    self.db.execute('DELETE FROM presence WHERE player_id=?', (old,))
            self.db.execute('UPDATE account_sessions SET player_id=? WHERE account_id=? AND expires>?', (identifier, account['id'], time.time()))
            self.persistent_social_changed = True
            return self.account_view(token)

    def account_logout(self, token):
        from .service import digest
        with self._transaction():
            account = self.account_identity(token)
            self.db.execute('UPDATE account_sessions SET expires=0 WHERE token_hash=?', (digest(token),))
            if not self.db.execute('SELECT 1 FROM account_sessions WHERE account_id=? AND expires>?', (account['id'], time.time())).fetchone():
                self.runtime_presence.pop(account['player_id'], None)
                self.db.execute('DELETE FROM presence WHERE player_id=?', (account['player_id'],))
            self.persistent_social_changed = True
            return {'ok': True}

    def _team(self, account_id):
        return self.db.execute('SELECT t.* FROM teams t JOIN team_members m ON m.team_id=t.id WHERE m.account_id=? AND m.active=1', (account_id,)).fetchone()

    def _character_location(self, player_id):
        from .world import zone_of, point_name
        cached = self.location_cache.get(player_id)
        if cached and time.monotonic() - cached[0] < 2:
            return dict(cached[1])
        row = self.db.execute('SELECT t.session_id,t.data FROM tutorials t JOIN members m ON m.session_id=t.session_id JOIN sessions s ON s.id=t.session_id WHERE m.player_id=? ORDER BY s.created DESC LIMIT 1', (player_id,)).fetchone()
        if not row:
            return {'zone': None, 'map': None, 'position': None, 'mode': 'lobby', 'location': 'Choix du tutoriel'}
        party = json.loads(row['data'])
        self.record_party_locations(party)
        return dict(self.location_cache[player_id][1])

    def record_party_locations(self, party):
        from .world import zone_of, point_name
        for player_id in party['characters']:
            self.location_cache[player_id] = (time.monotonic(), self._party_location(party, player_id, zone_of, point_name))

    @staticmethod
    def _party_location(party, player_id, zone_of, point_name):
        battle = party.get('battle')
        transit = party.get('transit')
        moving = bool(transit and transit.get('paused_at') is None)
        return {'zone': zone_of(party.get('position')), 'map': party.get('field_map') or (battle or {}).get('preset'),
                'position': (battle or {}).get('players', {}).get(player_id, {}).get('position'),
                'mode': 'travel' if moving else 'combat' if battle and not party.get('field_map') else 'exploration' if battle else 'outing',
                'location': point_name(party.get('position')), 'point': party.get('position'), 'waiting': bool(transit and transit.get('paused_at') is not None)}

    def _admit(self, player_id, realm=None):
        from .service import GameError
        if realm is not None and (type(realm) is not int or not 1 <= realm <= self.realm_count):
            raise GameError('invalid_server', 'Serveur invalide.')
        now = time.time()
        self.runtime_presence.prune(now - 60)
        existing = self.runtime_presence.get(player_id)
        counts = [sum(value['realm'] == index for value in self.runtime_presence.values()) for index in range(1, self.realm_count + 1)]
        selected = realm or (existing or {}).get('realm')
        if selected is None:
            selected = next((index for index, count in enumerate(counts, 1) if count < 40), None)
        if type(selected) is not int or not 1 <= selected <= self.realm_count or counts[selected - 1] >= 40 and (not existing or existing['realm'] != selected):
            raise GameError('server_full', 'Ce serveur est complet (40 joueurs). Réessayez ou choisissez un autre serveur.', 429)
        self.runtime_presence[player_id] = {'realm': selected, 'seen': now}
        return selected

    def world_presence(self, player):
        realm = self._admit(player['id'])
        location = self._character_location(player['id'])
        nearby = []
        team_accounts = set()
        owner = self.db.execute('SELECT account_id FROM account_characters WHERE player_id=?', (player['id'],)).fetchone()
        team = self._team(owner[0]) if owner else None
        if team:
            team_accounts = {row[0] for row in self.db.execute('SELECT account_id FROM team_members WHERE team_id=? AND active=1', (team['id'],))}
        for identifier, presence in self.runtime_presence.items():
            if identifier == player['id'] or presence['realm'] != realm:
                continue
            other = self._character_location(identifier)
            if other['zone'] != location['zone'] or other['zone'] is None:
                continue
            row = self.db.execute('SELECT p.id,p.name,p.class_name,c.account_id FROM players p LEFT JOIN account_characters c ON c.player_id=p.id LEFT JOIN account_status a ON a.player_id=p.id WHERE p.id=? AND COALESCE(a.suspended,0)=0', (identifier,)).fetchone()
            if row:
                nearby.append({**dict(row), **other, 'ally': row['account_id'] in team_accounts})
        return {'realm': realm, 'realms': self.realm_count, 'capacity': 40, 'online': sum(p['realm'] == realm for p in self.runtime_presence.values()), 'nearby': nearby, 'pvp': False}

    def social_view(self, token):
        with self._transaction():
            account = self.account_identity(token)
            team = self._team(account['id'])
            result = {'friends': [], 'requests': [], 'invitations': [], 'team': None, 'rallies': []}
            for row in self.db.execute("SELECT * FROM friendships WHERE (first_id=? OR second_id=?) AND status IN ('pending','accepted')", (account['id'], account['id'])):
                identifier = row['second_id'] if row['first_id'] == account['id'] else row['first_id']
                other = self.db.execute('SELECT id,username FROM accounts WHERE id=? AND suspended=0', (identifier,)).fetchone()
                if other:
                    item = {**dict(other), 'incoming': row['requester'] != account['id']}
                    result['friends' if row['status'] == 'accepted' else 'requests'].append(item)
            result['invitations'] = [dict(row) for row in self.db.execute("SELECT i.id,i.team_id,a.username FROM team_invites i JOIN accounts a ON a.id=i.sender WHERE i.recipient=? AND i.status='pending' AND i.expires>?", (account['id'], time.time()))]
            if team:
                members = []
                for row in self.db.execute('SELECT a.id,a.username FROM team_members m JOIN accounts a ON a.id=m.account_id WHERE m.team_id=? AND m.active=1 ORDER BY m.joined', (team['id'],)):
                    player = next((item for item in self.db.execute('SELECT p.id,p.name FROM players p JOIN account_characters c ON c.player_id=p.id WHERE c.account_id=?', (row['id'],)) if item['id'] in self.runtime_presence and time.time() - self.runtime_presence[item['id']]['seen'] < 60), None)
                    members.append({**dict(row), 'online': player is not None, 'player_id': player['id'] if player else None, 'name': player['name'] if player else row['username'], 'realm': self.runtime_presence[player['id']]['realm'] if player else None, **(self._character_location(player['id']) if player else {})})
                result['team'] = {'id': team['id'], 'owner': team['owner'], 'members': members, 'capacity': 4}
                result['rallies'] = [item for item in self.rallies.values() if item['team_id'] == team['id'] and item['expires'] > time.time() and item['sender'] != account['id']]
            return result

    def social_action(self, token, action, params):
        from .service import GameError
        allowed = {'friend_add': {'username'}, 'friend_accept': {'account_id'}, 'friend_remove': {'account_id'},
                   'team_invite': {'username'}, 'team_accept': {'invite_id'}, 'team_decline': {'invite_id'}, 'team_leave': set(),
                   'realm': {'realm'}, 'rally': {'destination'}, 'rally_accept': {'rally_id'}, 'join_ally': {'player_id'},
                   'wait': set(), 'resume': set()}
        if action not in allowed or not isinstance(params, dict) or set(params) != allowed[action]:
            raise GameError('invalid_command', 'Action sociale invalide.')
        with self._transaction():
            account = self.account_identity(token)
            team = self._team(account['id'])
            now = time.time()
            if action in ('friend_add', 'team_invite'):
                if not isinstance(params['username'], str):
                    raise GameError('invalid_username', 'Nom de compte invalide.')
                other = self.db.execute('SELECT id FROM accounts WHERE username_key=? AND suspended=0', (params['username'].casefold(),)).fetchone()
                if not other or other[0] == account['id']:
                    raise GameError('not_found', 'Ce joueur est introuvable.', 404)
                target = other[0]
            else:
                target = params.get('account_id')
            if action.startswith('friend_'):
                if not isinstance(target, str) or not re.fullmatch('[a-f0-9]{32}', target) or target == account['id']:
                    raise GameError('invalid_player', 'Joueur invalide.')
                first, second = sorted((account['id'], target))
                relation = self.db.execute('SELECT * FROM friendships WHERE first_id=? AND second_id=?', (first, second)).fetchone()
                if action == 'friend_add':
                    count = self.db.execute("SELECT COUNT(*) FROM friendships WHERE (first_id=? OR second_id=?) AND status IN ('pending','accepted')", (account['id'], account['id'])).fetchone()[0]
                    if count >= 200:
                        raise GameError('capacity', 'La liste d’amis est complète.', 429)
                    if not relation or relation['status'] == 'removed':
                        self.db.execute("INSERT INTO friendships VALUES(?,?,?,'pending') ON CONFLICT(first_id,second_id) DO UPDATE SET requester=excluded.requester,status='pending'", (first, second, account['id']))
                elif action == 'friend_accept':
                    if not relation or relation['status'] != 'pending' or relation['requester'] == account['id']:
                        raise GameError('not_found', 'Demande d’ami introuvable.', 404)
                    self.db.execute("UPDATE friendships SET status='accepted' WHERE first_id=? AND second_id=?", (first, second))
                else:
                    self.db.execute("UPDATE friendships SET status='removed' WHERE first_id=? AND second_id=?", (first, second))
            elif action == 'team_invite':
                if self._team(target):
                    raise GameError('already_in_team', 'Ce joueur est déjà dans une équipe.', 409)
                if not team:
                    identifier = secrets.token_hex(16)
                    self.db.execute('INSERT INTO teams VALUES(?,?)', (identifier, account['id']))
                    self.db.execute('INSERT INTO team_members VALUES(?,?,1,?) ON CONFLICT(account_id) DO UPDATE SET team_id=excluded.team_id,active=1,joined=excluded.joined', (account['id'], identifier, now))
                    team = self._team(account['id'])
                if self.db.execute('SELECT COUNT(*) FROM team_members WHERE team_id=? AND active=1', (team['id'],)).fetchone()[0] >= 4:
                    raise GameError('team_full', 'L’équipe est complète (4 joueurs).', 409)
                self.db.execute("UPDATE team_invites SET status='replaced' WHERE sender=? AND recipient=? AND status='pending'", (account['id'], target))
                self.db.execute("INSERT INTO team_invites VALUES(?,?,?,?,'pending',?)", (secrets.token_hex(16), team['id'], account['id'], target, now + 300))
            elif action in ('team_accept', 'team_decline'):
                invite = self.db.execute("SELECT * FROM team_invites WHERE id=? AND recipient=? AND status='pending' AND expires>?", (params['invite_id'], account['id'], now)).fetchone()
                if not invite:
                    raise GameError('not_found', 'Invitation expirée.', 404)
                if action == 'team_accept':
                    if team:
                        raise GameError('already_in_team', 'Quittez votre équipe avant de rejoindre une autre.', 409)
                    if not self.db.execute('SELECT 1 FROM team_members WHERE account_id=? AND team_id=? AND active=1', (invite['sender'], invite['team_id'])).fetchone():
                        raise GameError('not_found', 'Cette équipe n’existe plus.', 404)
                    if self.db.execute('SELECT COUNT(*) FROM team_members WHERE team_id=? AND active=1', (invite['team_id'],)).fetchone()[0] >= 4:
                        raise GameError('team_full', 'L’équipe est complète (4 joueurs).', 409)
                    self.db.execute('INSERT INTO team_members VALUES(?,?,1,?) ON CONFLICT(account_id) DO UPDATE SET team_id=excluded.team_id,active=1,joined=excluded.joined', (account['id'], invite['team_id'], now))
                self.db.execute('UPDATE team_invites SET status=? WHERE id=?', ('accepted' if action == 'team_accept' else 'declined', invite['id']))
            elif action == 'team_leave':
                if team:
                    self.db.execute('UPDATE team_members SET active=0 WHERE account_id=?', (account['id'],))
                    replacement = self.db.execute('SELECT account_id FROM team_members WHERE team_id=? AND active=1 ORDER BY joined LIMIT 1', (team['id'],)).fetchone()
                    if team['owner'] == account['id'] and replacement:
                        self.db.execute('UPDATE teams SET owner=? WHERE id=?', (replacement[0], team['id']))
            elif action == 'realm':
                if type(params['realm']) is not int:
                    raise GameError('invalid_server', 'Serveur invalide.')
                player = self._authenticate(token)
                self._admit(player['id'], params['realm'])
            else:
                self._social_travel(account, team, action, params)
            if action.startswith(('friend_', 'team_')):
                self.persistent_social_changed = True
            return self.social_view(token)

    def _social_travel(self, account, team, action, params):
        from .service import GameError
        from . import tutorial, world
        player_id = account['player_id']
        if not player_id:
            raise GameError('character_required', 'Choisissez un personnage.', 409)
        row = self.db.execute('SELECT t.session_id,t.data FROM tutorials t JOIN members m ON m.session_id=t.session_id JOIN sessions s ON s.id=t.session_id WHERE m.player_id=? ORDER BY s.created DESC LIMIT 1', (player_id,)).fetchone()
        if not row:
            raise GameError('not_running', 'Commencez votre aventure.', 409)
        party = json.loads(row['data'])
        now = self._now()
        if action in ('wait', 'resume'):
            transit = party.get('transit')
            if not transit or party.get('battle'):
                raise GameError('not_travelling', 'Cette action nécessite un trajet hors combat.', 409)
            if action == 'wait' and transit.get('paused_at') is None:
                transit['paused_at'] = now
                transit['waiting'] = True
                transit['next_encounter'] = now + 150
            elif action == 'resume' and transit.get('waiting'):
                delay = now - transit.pop('paused_at')
                transit['started_at'] += delay
                transit['ready_at'] += delay
                transit.pop('waiting', None)
                party['field_mode'] = transit.pop('resume_field_mode', party.get('field_mode', False))
            else:
                raise GameError('invalid_travel', 'Le trajet a déjà changé.', 409)
        else:
            if not team:
                raise GameError('not_in_team', 'Rejoignez une équipe.', 409)
            if party.get('battle') or party.get('mobs'):
                raise GameError('in_combat', 'Quittez le combat ou l’exploration avant de vous rallier.', 409)
            if action == 'rally':
                if party.get('transit') and not party['transit'].get('waiting'):
                    raise GameError('moving', 'Arrêtez-vous avant d’appeler les alliés.', 409)
                destination = params['destination']
                available = {p['id'] for p in world.view(party, player_id)['places']}
                if not isinstance(destination, str) or destination not in available:
                    raise GameError('invalid_destination', 'Destination inaccessible.')
                location = self._character_location(player_id)
                others = [m for m in self.social_view_for_team(team) if m['player_id'] != player_id and m['mode'] == 'outing' and m['zone'] == location['zone'] and m['realm'] == self.runtime_presence.get(player_id, {}).get('realm')]
                if not others:
                    raise GameError('no_allies', 'Aucun allié dans cette zone en vue sortie.', 409)
                self.rallies = {key: value for key, value in self.rallies.items() if value['expires'] > time.time() and value['sender'] != account['id']}
                identifier = secrets.token_hex(16)
                self.rallies[identifier] = {'id': identifier, 'team_id': team['id'], 'sender': account['id'], 'username': account['username'], 'zone': location['zone'], 'realm': self.runtime_presence.get(player_id, {}).get('realm'), 'destination': destination, 'expires': time.time() + 60}
                return
            if action == 'rally_accept':
                rally = self.rallies.get(params['rally_id'])
                location = self._character_location(player_id)
                if not rally or rally['team_id'] != team['id'] or rally['expires'] <= time.time() or location['zone'] != rally['zone'] or location['mode'] != 'outing' or self.runtime_presence.get(player_id, {}).get('realm') != rally['realm']:
                    raise GameError('not_found', 'Appel de ralliement expiré ou inaccessible.', 404)
                destination = rally['destination']
            else:
                target = next((m for m in self.social_view_for_team(team) if m['player_id'] == params['player_id']), None)
                if not target or target['mode'] != 'outing' or not target['online']:
                    raise GameError('ally_moving', 'L’allié doit être arrêté hors exploration.', 409)
                if target['realm'] != self.runtime_presence.get(player_id, {}).get('realm'):
                    raise GameError('different_server', 'Rejoignez d’abord le serveur de votre allié.', 409)
                destination = target['point']
                target_row = self.db.execute('SELECT t.data FROM tutorials t JOIN members m ON m.session_id=t.session_id JOIN sessions s ON s.id=t.session_id WHERE m.player_id=? ORDER BY s.created DESC LIMIT 1', (target['player_id'],)).fetchone()
                target_party = json.loads(target_row[0])
                transit = target_party.get('transit')
                if transit and transit.get('waiting'):
                    elapsed = min(transit.get('total', transit['remaining']), max(0, transit.get('total', transit['remaining']) - transit['remaining'] + transit['paused_at'] - transit['started_at']))
                    destination = transit['source']
                    transit['resume_field_mode'] = target_party.get('field_mode', False)
                    party['rendezvous'] = {'source': destination, 'point': target_party['position'], 'destination': transit['destination'], 'duration': elapsed, 'transit': transit, 'target': target['player_id']}
                    party['field_mode'] = False
            messages, _ = tutorial.execute(party, player_id, 'move', {'destination': destination}, now, GameError, self.random)
            for message in messages:
                self._event(row['session_id'], now, message)
        self.record_party_locations(party)
        self.dirty_sessions.add(row['session_id'])
        self.db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(party), row['session_id']))
        self.db.execute('UPDATE sessions SET revision=revision+1 WHERE id=?', (row['session_id'],))

    def social_view_for_team(self, team):
        result = []
        for row in self.db.execute('SELECT c.player_id FROM account_characters c JOIN team_members m ON m.account_id=c.account_id WHERE m.team_id=? AND m.active=1', (team['id'],)):
            presence = self.runtime_presence.get(row[0])
            if presence and time.monotonic() - presence['seen'] < 60:
                result.append({'player_id': row[0], 'online': True, 'realm': presence['realm'], **self._character_location(row[0])})
        return result
