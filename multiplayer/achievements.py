from . import progression, world


def record(party):
    stats = party.setdefault("achievements", {"kills": 0, "max_level": 1, "zones": [], "best_seconds": None, "titles": []})
    stats["max_level"] = max(stats["max_level"], *(c["level"] for c in party["characters"].values()))
    stats["zones"] = sorted(set(stats["zones"]) | set(party.get("visited", [])))
    return stats


def victory(party, now):
    battle = party["battle"]
    if battle.get("arrivals") or party.get("training") or battle.get("awarded") or party["mobs"] or "initial_mobs" not in battle:
        return
    battle["awarded"] = True
    stats = record(party)
    seconds = max(0, now - battle["started_at"]) / progression.RATIO
    stats["best_seconds"] = seconds if stats["best_seconds"] is None else min(stats["best_seconds"], seconds)
    titles = set(stats["titles"])
    if not battle.get("enemy_alerted"):
        titles.add("Ombre silencieuse")
    if not battle.get("damage_received"):
        titles.add("Intouchable")
    if seconds <= 30:
        titles.add("Éclair de la lisière")
    count = battle.get("initial_mobs", 1)
    players = battle.get("initial_players", 1)
    if players == count == 1 and battle.get("higher_level"):
        titles.add("Briseur de limites")
        stats["level_difference"] = max(stats.get("level_difference", 0), battle.get("level_difference", 0))
    if players > count:
        titles.add("Force du nombre")
    if players < count:
        titles.add("Contre toute attente")
    stats["titles"] = sorted(titles)


def view(party):
    stats = record(party)
    rows = []
    for zone, definition in world.PLACES.items():
        rows.append({"name": "Découvrir " + definition["name"], "progress": "Découvert" if zone in stats["zones"] else "À découvrir", "title": "Éclaireur de " + definition["name"], "unlocked": zone in stats["zones"]})
    for level in (5, 10, 20):
        rows.append({"name": f"Atteindre le niveau {level}", "progress": f"{stats['max_level']}/{level}", "title": {5: "Aventurier confirmé", 10: "Vétéran", 20: "Légende vivante"}[level], "unlocked": stats["max_level"] >= level})
    for count, title in ((1, "Première victoire"), (10, "Chasseur"), (50, "Fléau des gobelins"), (100, "Gardien des chemins")):
        rows.append({"name": f"Vaincre {count} créatures", "progress": f"{stats['kills']}/{count}", "title": title, "unlocked": stats["kills"] >= count})
    for name, title in (("Victoire sans alerter d’ennemi", "Ombre silencieuse"), ("Victoire sans dégâts au groupe ni aux invocations", "Intouchable"), ("Victoire en 30 secondes réelles maximum", "Éclair de la lisière"), ("Seul contre un ennemi de niveau supérieur", "Briseur de limites"), ("Victoire en supériorité numérique", "Force du nombre"), ("Victoire en infériorité numérique", "Contre toute attente")):
        unlocked = title in stats["titles"]
        if title == "Briseur de limites":
            difference = stats.get("level_difference", 0)
            title += f" (+{difference} niveaux)" if difference else " (différence de niveau)"
        rows.append({"name": name, "progress": "Accompli" if unlocked else "À accomplir", "title": title, "unlocked": unlocked})
    return {**stats, "rows": rows, "unlocked_titles": [r["title"] for r in rows if r["unlocked"]]}
