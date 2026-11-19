"""Explicit runtime selection; keep the deployed distributed mode by default."""


def runtime_mode(environment):
    default = (
        "d1"
        if environment.get("VERCEL") and environment.get("RPG_DATABASE_BACKEND") == "d1"
        else "distributed"
    )
    mode = environment.get("RPG_RUNTIME_MODE", default)
    if mode not in ("distributed", "single", "d1"):
        raise ValueError("RPG_RUNTIME_MODE doit valoir distributed, single ou d1")
    return mode


def account_auth_required(environment):
    return bool(environment.get("VERCEL")) or runtime_mode(environment) in (
        "single",
        "d1",
    )


def runtime_environment(environment):
    if runtime_mode(environment) != "d1":
        return dict(environment)
    return {
        key: value
        for key, value in environment.items()
        if not any(part in key for part in ("REDIS", "UPSTASH", "KV_"))
    }
