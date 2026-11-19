"""Validate VM preview configuration without claiming a D1 generation."""

import argparse
from pathlib import Path

from dotenv import dotenv_values

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.host_configuration import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("env_file", type=Path)
    args = parser.parse_args()
    environment = dict(dotenv_values(args.env_file, interpolate=False))
    validate(environment)
    D1Client(environment).health()
    print("Configuration Oracle preview et schéma D1 valides ; génération inchangée")


if __name__ == "__main__":
    main()
