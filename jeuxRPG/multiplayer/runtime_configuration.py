"""Runtime selection for local, persistent and serverless hosting."""


def runtime_mode(environment):
    default = (
        "d1"
        if environment.get("VERCEL") and environment.get("RPG_DATABASE_BACKEND") == "d1"
        else "local"
    )
    mode = environment.get("RPG_RUNTIME_MODE", default)
    if mode == "distributed" and not environment.get("VERCEL"):
        return "local"
    if mode not in ("local", "single", "d1"):
        raise ValueError("RPG_RUNTIME_MODE doit valoir local, single ou d1")
    return mode


def account_auth_required(environment):
    return bool(environment.get("VERCEL")) or runtime_mode(environment) in (
        "single",
        "d1",
    )


def runtime_environment(environment):
    return {
        key: value
        for key, value in environment.items()
        if not any(part in key for part in ("REDIS", "UPSTASH", "KV_"))
    }
