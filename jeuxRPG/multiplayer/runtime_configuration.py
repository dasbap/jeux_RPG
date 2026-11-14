"""Explicit runtime selection; keep the deployed distributed mode by default."""


def runtime_mode(environment):
    mode = environment.get("RPG_RUNTIME_MODE", "distributed")
    if mode not in ("distributed", "single"):
        raise ValueError("RPG_RUNTIME_MODE doit valoir distributed ou single")
    return mode


def account_auth_required(environment):
    return bool(environment.get("VERCEL")) or runtime_mode(environment) == "single"
