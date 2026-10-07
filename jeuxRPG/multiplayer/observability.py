import time


def health():
    return {"status": "ok"}


def ready(service):
    service.db.execute("SELECT 1").fetchone()
    return {"status": "ready"}


def metrics(service, tick_seconds=None):
    active_sessions = service.db.execute(
        "SELECT COUNT(*) FROM sessions WHERE state IN ('lobby','running')"
    ).fetchone()[0]
    players = service.db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    accounts = service.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    now = time.monotonic()
    online = sum(
        1
        for item in service.runtime_presence.values()
        if now - item.get("seen", 0) < 60
    )
    values = {
        "rpg_players_total": players,
        "rpg_accounts_total": accounts,
        "rpg_sessions_active": active_sessions,
        "rpg_runtime_presence": online,
    }
    if tick_seconds is not None:
        values["rpg_tick_seconds_last"] = float(tick_seconds)
    lines = [
        "# TYPE rpg_players_total gauge",
        f"rpg_players_total {values['rpg_players_total']}",
        "# TYPE rpg_accounts_total gauge",
        f"rpg_accounts_total {values['rpg_accounts_total']}",
        "# TYPE rpg_sessions_active gauge",
        f"rpg_sessions_active {values['rpg_sessions_active']}",
        "# TYPE rpg_runtime_presence gauge",
        f"rpg_runtime_presence {values['rpg_runtime_presence']}",
    ]
    if "rpg_tick_seconds_last" in values:
        lines.extend(
            [
                "# TYPE rpg_tick_seconds_last gauge",
                f"rpg_tick_seconds_last {values['rpg_tick_seconds_last']:.6f}",
            ]
        )
    return "\n".join(lines) + "\n"
