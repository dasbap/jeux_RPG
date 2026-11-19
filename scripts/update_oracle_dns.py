"""External-controller hook: update DuckDNS with Oracle's explicit new public IP."""

import argparse
import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def update(environment, ipv4):
    subdomain = environment.get("RPG_DUCKDNS_SUBDOMAIN", "jeux-rpg")
    token = environment.get("RPG_DUCKDNS_TOKEN") or environment.get("DUCKDNS_TOKEN", "")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain):
        raise ValueError("Sous-domaine DuckDNS invalide")
    if not re.fullmatch(r"[A-Za-z0-9-]{20,128}", token) or "REPLACE" in token:
        raise ValueError("Jeton DuckDNS absent ou invalide")
    address = ipaddress.IPv4Address(ipv4)
    if not address.is_global:
        raise ValueError("Une IPv4 publique Oracle explicite est requise")
    query = urllib.parse.urlencode(
        {"domains": subdomain, "token": token, "ip": str(address), "verbose": "true"}
    )
    request = urllib.request.Request(
        "https://www.duckdns.org/update?" + query,
        headers={"User-Agent": "jeux-rpg-controller/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = response.read(1024).decode("ascii").splitlines()
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
        # Never leak the provider URL: the DuckDNS protocol carries its token there.
        raise RuntimeError(
            "Mise à jour DuckDNS indisponible ; réessayer depuis le contrôleur"
        ) from None
    if len(result) < 2 or result[0] != "OK" or result[1] != str(address):
        raise RuntimeError("Mise à jour DuckDNS non confirmée")
    return {
        "hostname": subdomain + ".duckdns.org",
        "ipv4": str(address),
        "provider_confirmed": True,
        "dns_propagation_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ipv4",
        required=True,
        help="Adresse obtenue auprès d'Oracle, jamais l'IP du contrôleur",
    )
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    environment = dict(os.environ)
    if args.env_file:
        from dotenv import dotenv_values

        environment = dict(dotenv_values(args.env_file, interpolate=False))
    print(json.dumps(update(environment, args.ipv4)))


if __name__ == "__main__":
    main()
