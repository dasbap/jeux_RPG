import json
from urllib.parse import urlsplit


class RedisConfigurationError(RuntimeError):
    pass


def redis_url(environment):
    configured = environment.get("REDIS_URLS")
    if not configured:
        return environment.get("REDIS_URL") or environment.get("KV_URL")
    try:
        urls = json.loads(configured)
        if not isinstance(urls, list) or not urls:
            raise ValueError
        for url in urls:
            if not isinstance(url, str):
                raise ValueError
            parsed = urlsplit(url)
            if parsed.scheme not in ("redis", "rediss") or not parsed.hostname:
                raise ValueError
            _ = parsed.port
    except (ValueError, TypeError):
        raise RedisConfigurationError(
            "REDIS_URLS doit contenir une liste JSON d'URL Redis valides."
        ) from None
    try:
        index = int(environment.get("RPG_REDIS_ACTIVE_INDEX", "0"))
        if not 0 <= index < len(urls):
            raise ValueError
    except (ValueError, TypeError):
        raise RedisConfigurationError(
            "RPG_REDIS_ACTIVE_INDEX doit désigner une URL de REDIS_URLS, à partir de 0."
        ) from None
    return urls[index]
