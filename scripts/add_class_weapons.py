"""Add class-compatible weapons to the editable catalogue; keep existing recipes."""

from jeuxRPG.multiplayer.controller_project import Project


def add_weapons(project):
    gameplay = project.content["gameplay"]
    gameplay["slots"]["weapon"] = "Arme"
    recipes = {
        "epee_lisiere": {
            "name": "Épée de la Lisière",
            "weapon_type": "sword",
            "classes": ["Knight"],
            "cost": {"peau": 2, "croc": 5},
            "force": 3,
            "endurance": 1,
        },
        "arc_ronces": {
            "name": "Arc des Ronces",
            "weapon_type": "bow",
            "classes": ["Archer"],
            "cost": {"cuir_roncier": 2, "epine_ronciere": 2},
            "force": 4,
            "endurance": 1,
        },
        "baton_lucioles": {
            "name": "Bâton des Lucioles",
            "weapon_type": "staff",
            "classes": ["Mage", "Priest", "Necromancien"],
            "cost": {"carapace_luciole": 2, "poudre_lumineuse": 2},
            "intelligence": 3,
            "sagesse": 3,
        },
        "sceptre_veille": {
            "name": "Sceptre de la Veille",
            "weapon_type": "staff",
            "classes": ["Mage", "Priest", "Necromancien"],
            "cost": {"etoffe_veille": 2, "essence_veille": 2},
            "intelligence": 5,
            "sagesse": 5,
        },
    }
    for key, value in recipes.items():
        gameplay["recipes"][key] = {
            "slot": "weapon",
            "adjective": "éveillée" if key == "epee_lisiere" else "éveillé",
            **value,
        }
    project.validate()


if __name__ == "__main__":
    project = Project("projects/authored")
    add_weapons(project)
    project.save()
    print(
        "Four weapon recipes added; five classes supported, two shared magical weapons."
    )
