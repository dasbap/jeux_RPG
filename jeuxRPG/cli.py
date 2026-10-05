import argparse
import json
import shlex
import signal
import time


def show(value):
    print(json.dumps(value, ensure_ascii=True, indent=2))


def interactive(session):
    from jeuxRPG.adventure.equipment import material_name, parse_recipe

    print("Commandes : combat, personnage, inventaire, recettes, craft <recette>, equiper <objet>, retirer <slot>, carte, chemins, voyager <chemin>, auberge <jour|nuit>, observer, explorer <repere>, recolter, dormir <jour|nuit>, recruter <pnj>, camp <nom>, fonder, relier <zone>, relais <chemin>, halte <chemin>, attendre <heures>, quitter")
    while True:
        try:
            command = shlex.split(input("rpg> "))
        except EOFError:
            return
        except ValueError:
            print("Commande mal formée.")
            continue
        if not command:
            continue
        action, *arguments = command
        try:
            if action == "quitter":
                return
            if action == "combat" and not arguments:
                show(session.encounter())
            elif action == "carte" and not arguments:
                show(session.world_map())
            elif action == "chemins" and not arguments:
                show(session.available_paths())
            elif action == "voyager" and len(arguments) == 1:
                show(session.travel(arguments[0]))
            elif action == "auberge" and len(arguments) == 1:
                if arguments[0] not in {"jour", "nuit"}:
                    raise ValueError("Choisissez jour ou nuit")
                show(session.rest_at_inn({"jour": "day", "nuit": "night"}[arguments[0]]))
            elif action == "observer" and not arguments:
                show(session.observe())
                session.save()
            elif action == "explorer" and len(arguments) == 1:
                show(session.explore(arguments[0]))
            elif action == "dormir" and len(arguments) == 1:
                if arguments[0] not in {"jour", "nuit"}:
                    raise ValueError("Choisissez jour ou nuit")
                show(session.rest_at_camp({"jour": "day", "nuit": "night"}[arguments[0]]))
            elif action == "recolter" and not arguments:
                show(session.gather())
            elif action == "recruter" and len(arguments) == 1:
                show({"workers": session.hire(arguments[0])})
            elif action == "camp" and arguments:
                show(session.establish_camp(" ".join(arguments)))
            elif action == "fonder" and not arguments:
                show(session.upgrade_village())
            elif action == "relier" and len(arguments) == 1:
                show(session.connect_village(arguments[0]))
            elif action == "relais" and len(arguments) == 1:
                show(session.build_relay(arguments[0]))
            elif action == "halte" and len(arguments) == 1:
                show(session.travel(arguments[0], stop_at_relay=True))
            elif action == "attendre" and len(arguments) == 1:
                show(session.advance_world(int(arguments[0])))
            elif action == "personnage" and not arguments:
                show(session.status())
            elif action == "inventaire" and not arguments:
                show({"materiaux": {material_name(key, session.catalog): count for key, count in session.inventory.materials.items()},
                      "objets": {key: gear.name for key, gear in session.inventory.items.items()},
                      "equipes": session.status()["equipped"]})
            elif action == "recettes" and not arguments:
                show({key: {"nom": parse_recipe(key, session.catalog).name,
                            "ingredients": {material_name(material, session.catalog): {"requis": amount, "disponible": session.inventory.materials.get(material, 0)}
                                            for material, amount in parse_recipe(key, session.catalog).ingredients.items()}}
                      for key in session.inventory.recipes()})
            elif action == "craft" and len(arguments) == 1:
                print(f"Objet fabriqué : {session.craft(arguments[0])}")
            elif action == "equiper" and len(arguments) == 1:
                session.equip(arguments[0])
                print("Objet équipé.")
            elif action == "retirer" and len(arguments) == 1:
                session.unequip(arguments[0])
                print("Objet retiré.")
            else:
                print("Commande inconnue ou arguments incorrects.")
        except ValueError as error:
            print(str(error))


def main():
    parser = argparse.ArgumentParser(description="Arène RPG persistante et craft")
    parser.add_argument("--class", dest="class_name", default="Knight")
    parser.add_argument("--name", default="Héros")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["adventure", "simulation", "world"])
    parser.add_argument("--floors", type=int)
    parser.add_argument("--world-save", help="État partagé de la simulation du monde")
    parser.add_argument("--ticks", type=int, help="Nombre d’heures à simuler sans joueur")
    parser.add_argument("--resources", help="Fichier ou dossier de ressources JSON")
    parser.add_argument("--save", default=".data/adventure/player.json")
    parser.add_argument("--battles", type=int)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--no-auto-craft", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.ticks is not None and args.ticks < 1:
        parser.error("--ticks doit être positif")
    if args.floors is not None and args.floors < 1:
        parser.error("--floors doit être positif")
    if args.battles is not None and args.battles < 1:
        parser.error("--battles doit être positif")
    if not 0 <= args.interval <= 60:
        parser.error("--interval doit être compris entre 0 et 60")
    if not args.name.strip():
        parser.error("--name ne peut pas être vide")
    mode = args.mode or ("simulation" if args.floors is not None else "adventure")
    if mode == "world":
        from jeuxRPG.adventure.catalog import load_catalog
        from jeuxRPG.adventure.frontier import WorldSimulation

        world_path = args.world_save or ".data/world/world.json"
        try:
            simulation = WorldSimulation.load(world_path, load_catalog(args.resources))
            count = 0
            while args.ticks is None or count < args.ticks:
                show(WorldSimulation.tick_file(world_path, simulation.catalog, 1))
                count += 1
                if args.ticks is None or count < args.ticks:
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            print("Simulation interrompue ; état du monde sauvegardé.")
        except (ValueError, OSError) as error:
            parser.error(f"Simulation impossible : {error}")
        return
    if mode == "simulation":
        from jeuxRPG._balance.simulator import simulate_tower

        show(simulate_tower(class_name=args.class_name, difficulty="easy", floors=args.floors or 2,
                            start_floor=1, enemies_per_floor=1, seed=args.seed, resolution="reward_curve"))
        return
    from jeuxRPG.adventure import Adventure

    try:
        session = Adventure(args.save, args.class_name, args.name, args.seed, resources=args.resources, world_save=args.world_save)
    except (ValueError, OSError) as error:
        parser.error(f"Chargement impossible : {error}")
    session.save()
    stopped = False
    previous_handler = None
    if not args.interactive:
        def stop(signum, frame):
            nonlocal stopped
            stopped = True
        previous_handler = signal.signal(signal.SIGINT, stop)
    try:
        if args.interactive:
            interactive(session)
            return
        count = 0
        while not stopped and (args.battles is None or count < args.battles):
            result = session.encounter(auto_craft=not args.no_auto_craft)
            if args.json:
                show(result)
            else:
                outcome = {"victory": "victoire", "defeat": "défaite", "draw": "match nul"}[result["outcome"]]
                print(f"Combat {result['battle']} — {result['enemy']} niveau {result['enemy_level']} : {outcome}, {result['rounds']} rounds. Niveau {result['level']}.", flush=True)
                if result["loot"]:
                    from jeuxRPG.adventure.equipment import material_name
                    for material, amount in result["loot"]["materials"].items():
                        print(f"Butin : {amount} {material_name(material, session.catalog)}.", flush=True)
                for identifier in result["crafted"]:
                    print(f"Fabriqué et équipé : {session.inventory.items[identifier].name} ({identifier}).", flush=True)
            count += 1
            if not stopped and (args.battles is None or count < args.battles):
                time.sleep(args.interval)
        if stopped:
            print("Aventure interrompue ; progression sauvegardée.")
    except KeyboardInterrupt:
        print("\nAventure interrompue ; progression sauvegardée.")
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)
        session.save()
