"""Run the living-world prototype on loopback with a separate local SQLite DB."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8085)
    parser.add_argument(
        "--world-speed",
        type=float,
        default=1,
        help="Accélère uniquement le monde ; 60 pour observer les événements rapidement",
    )
    parser.add_argument(
        "--profile", default="default", help="Nom d'une base locale isolée"
    )
    args = parser.parse_args()
    if (
        not args.profile
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-_"
            for character in args.profile
        )
        or len(args.profile) > 40
    ):
        parser.error(
            "Le profil doit contenir 1 à 40 lettres minuscules, chiffres, - ou _"
        )
    if not 1 <= args.port <= 65535 or not 0 < args.world_speed <= 600:
        parser.error("Port ou vitesse invalide")
    # No .env is loaded. Strip inherited cloud coordination before importing it.
    for key in list(os.environ):
        if any(
            part in key.upper()
            for part in ("REDIS", "UPSTASH", "TURSO", "VERCEL", "RPG_D1", "KV_REST")
        ):
            os.environ.pop(key)
    from jeuxRPG.multiplayer.distributed import PresenceRegistry
    from jeuxRPG.multiplayer.server import RPGServer
    from jeuxRPG.multiplayer.service import GameService

    root = Path(__file__).resolve().parents[1] / ".data/living-world" / args.profile
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    service = GameService(
        root / "world.sqlite3",
        log_directory=str(root / "logs"),
        presence_registry=PresenceRegistry(),
        living_world=True,
        world_speed=args.world_speed,
    )
    server = RPGServer(
        ("127.0.0.1", args.port), service, log_directory=str(root / "logs")
    )
    print(
        f"Monde vivant local : http://127.0.0.1:{args.port} — profil {args.profile}",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
