import sys

from jeuxRPG.multiplayer.server import main


if __name__ == "__main__":
    if set(sys.argv[1:]) & {"--battles", "--floors", "--interactive", "--mode", "--world-save", "--ticks", "--save"}:
        from jeuxRPG.cli import main as legacy_main
        legacy_main()
    else:
        main()
