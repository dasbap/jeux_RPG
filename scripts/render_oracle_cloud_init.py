"""Render secret-free cloud-init for an already selected Ubuntu ARM64 VM."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deploy/oracle"
FILES = {
    "bootstrap.sh": ("/usr/local/sbin/jeux-rpg-bootstrap", "0700"),
    "deploy.sh": ("/usr/local/sbin/jeux-rpg-deploy", "0700"),
    "maintenance.sh": ("/usr/local/sbin/jeux-rpg-maintenance", "0700"),
    "jeux-rpg.service": ("/etc/systemd/system/jeux-rpg.service", "0644"),
    "jeux-rpg-maintenance.service": (
        "/etc/systemd/system/jeux-rpg-maintenance.service",
        "0644",
    ),
    "jeux-rpg-maintenance.timer": (
        "/etc/systemd/system/jeux-rpg-maintenance.timer",
        "0644",
    ),
    "Caddyfile": ("/etc/caddy/Caddyfile", "0644"),
    "caddy-override.conf": (
        "/etc/systemd/system/caddy.service.d/jeux-rpg.conf",
        "0644",
    ),
}


def render(revision, domain=None):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Un commit Git complet de 40 caractères est requis")
    if domain and (
        len(domain) > 253
        or "." not in domain
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in domain.split(".")
        )
    ):
        raise ValueError("Un nom DNS sans protocole ni chemin est requis")
    configuration = {
        "package_update": True,
        "package_upgrade": False,
        "packages": [
            "git",
            "python3-venv",
            "python3-pip",
            "curl",
            "ca-certificates",
            "caddy",
            "iptables-persistent",
        ],
        "apt": {
            "debconf_selections": {
                "iptables": "iptables-persistent iptables-persistent/autosave_v4 boolean false\niptables-persistent iptables-persistent/autosave_v6 boolean false\n",
            },
        },
        "ssh_pwauth": False,
        "disable_root": True,
        "write_files": [
            {
                "path": destination,
                "owner": "root:root",
                "permissions": mode,
                "defer": True,
                "content": (ASSETS / name).read_text(encoding="utf-8"),
            }
            for name, (destination, mode) in FILES.items()
        ],
        "runcmd": [["/usr/local/sbin/jeux-rpg-bootstrap", revision, domain or ""]],
        "final_message": "Jeux RPG : installation terminée, activation après configuration privée.",
    }
    return (
        "#cloud-config\n"
        + json.dumps(configuration, ensure_ascii=False, indent=2)
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--domain", default="jeux-rpg.duckdns.org")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = render(args.revision, args.domain)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(content)
    print("Cloud-init généré sans secrets ; aucune ressource Oracle créée")


if __name__ == "__main__":
    main()
