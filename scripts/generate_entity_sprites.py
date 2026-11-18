"""Create the original editable body/weapon art pack for the local Builder project."""

import argparse

from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.entity_sprite_art import populate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="projects/authored")
    parser.add_argument(
        "--art-only",
        action="store_true",
        help="Actualiser les dessins gérés en conservant les associations, armes et teintes.",
    )
    args = parser.parse_args()
    project = Project(args.directory)
    data = populate(project, preserve_bindings=args.art_only)
    project.save()
    print(
        f"{len(data['assets'])} sprites, {len(data['bindings'])} entités, {len(data['equipment'])} armes associées. Projet local enregistré."
    )


if __name__ == "__main__":
    main()
