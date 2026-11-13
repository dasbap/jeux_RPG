"""Verify the delivered catalogues, independently of the reference-world fixtures."""
import os
import sys
import argparse
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["RPG_MAPS_FILE"] = str(ROOT / "jeuxRPG/maps")
os.environ.pop("RPG_CONTENT_FILE", None)
os.environ.pop("RPG_CLASSES_FILE", None)

from jeuxRPG.multiplayer import content, fields, forge, narrative, tactics, tutorial, world
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.map_building import MOBS
from jeuxRPG.multiplayer.service import GameError

NEW_CONTENT = [
    ("luciole_cuirassee", "rosee_prairies", "bottes_lucioles", 1),
    ("sanglier_roncier", "rosee_verger", "gants_ronciers", 1),
    ("gardien_de_schiste", "rosee_carriere", "casque_schiste", 2),
    ("veilleur_des_brumes", "brume_ruines", "manteau_veille", 2),
]


def party():
    return tutorial.new_party([{"id": "p", "name": "Audit", "class_name": "Knight"}])


def states(p):
    return narrative.state(p,"p")["quests"] if narrative.enabled() else content.quest_states(p)


def dialogue(p,npc):
    if not narrative.enabled():
        return content.quest_dialogue(p,npc)
    p.update(position=npc,battle=None,mobs=[],mob=None)
    p.pop("field_map",None)
    narrative.interact(p,"p",npc,"open",GameError)
    messages=[]
    for quest in content.DATA["quests"]:
        if quest["npc"]!=npc or narrative.requirements(p,"p",quest):
            continue
        saved=states(p).get(quest["id"])
        if saved is None:
            messages.extend(narrative.interact(p,"p",npc,"accept:"+quest["id"],GameError))
        elif saved["status"]=="active" and narrative.progress(p,"p",quest,saved)>=quest["count"]:
            messages.extend(narrative.interact(p,"p",npc,"claim:"+quest["id"],GameError))
    narrative.interact(p,"p",npc,"close",GameError)
    return messages


def unlock(p):
    p.update(position="mira", step="village", battle=None, mobs=[], mob=None)
    dialogue(p, "mira")
    quest = forge.rosee_unlock_quest()
    for _ in range(quest["count"]):
        content.quest_event(p, "kill", quest["target"], quest["zone"])
    assert not forge.rosee_unlocked(p,"p"), "Le compteur rempli ne remplace pas la remise de quête."
    dialogue(p, "mira")
    assert forge.rosee_unlocked(p,"p")
    p["position"] = "forge"


def main():
    for directory in ("jeuxRPG/maps", "projects/authored"):
        Project(ROOT / directory).validate()
    assert len(content.DATA["quests"]) >= 14
    assert {"hunt", "boss", "crafting", "upgrade"} <= {q.get("category") for q in content.DATA["quests"]}
    for _,_,recipe,_ in NEW_CONTENT:
        followup = next(q for q in content.DATA["quests"] if q["id"] == "upgrade_"+recipe)
        assert followup["requirements"]["quests"] == ["craft_"+recipe]
    assert any(point["id"] == "elyne" for place in world.PLACES.values() for point in place["points"])

    free = party()
    free.update(position="rosee", step="village", visited=["clearing", "rosee"])
    assert not forge.rosee_unlocked(free,"p")
    messages, _ = tutorial.execute(free, "p", "travel", {"destination":"brume"}, 0, GameError, lambda:1)
    assert messages or free.get("journey") or free.get("transit")
    tutorial.arrive(free, "brume", [])
    assert free["step"] == "complete" and not forge.rosee_unlocked(free,"p")
    assert not any(s["status"]=="completed" for s in states(free).values())
    walking = party()
    fields.enter(walking,"brume",fields.MAPS["brume"]["exits"][0]["position"],0)
    assert walking["step"]=="complete" and not forge.rosee_unlocked(walking,"p")

    locked = party()
    locked.update(position="forge", battle=None)
    locked["inventory"]["p"] = {"peau":100,"croc":100}
    before = deepcopy(locked["inventory"])
    try:
        forge.execute(locked,"p","craft","veste",GameError)
    except GameError as error:
        assert error.code == "forge_locked"
    else:
        raise AssertionError("Le serveur doit verrouiller la forge de Rosée.")
    assert locked["inventory"] == before and not locked["equipment"]

    for species, area, recipe, goal in NEW_CONTENT:
        hunt = next(q for q in content.DATA["quests"] if q["id"] == "hunt_"+species)
        p = party()
        dialogue(p, hunt["npc"])
        fields.enter(p, area, fields.MAPS[area]["exits"][0]["position"], 0)
        mob = next(m for m in p["mobs"] if m["mob_id"] == species)
        assert mob["level"] == MOBS[species]["level"]
        mob["stats"]["hp"]["current"] = 0
        p["mobs"].remove(mob)
        tutorial.sync_mobs(p)
        tactics.defeated(p,mob,0,lambda:.5,[])
        assert states(p)[hunt["id"]]["progress"] == 1
        corpse = p["battle"]["corpses"][-1]
        ingredients = forge.RECIPES[recipe]["cost"]
        assert set(ingredients) <= corpse["loot"].keys()
        assert all(corpse["loot"][key] > 0 for key in ingredients)

        p = party()
        unlock(p)
        p["inventory"]["p"] = {key:1000 for key in content.gameplay()["materials"]}
        dialogue(p,"forge")
        objective = "upgrade_"+recipe
        assert objective not in states(p)
        forge.execute(p,"p","craft",recipe,GameError)
        assert objective not in states(p), "La fabrication seule ne remplace pas la remise de quête."
        dialogue(p,"forge")
        assert states(p)["craft_"+recipe]["status"] == "completed"
        assert states(p)[objective]["progress"] == 0
        for level in range(1,goal+1):
            forge.execute(p,"p","upgrade",recipe,GameError)
            assert states(p)[objective]["progress"] == int(level >= goal)
        assert all(states(p).get("upgrade_"+other,{}).get("progress",0)==0 for _,_,other,_ in NEW_CONTENT if other != recipe)
        dialogue(p,"forge")
        assert states(p)[objective]["status"] == "completed"
        assert not any("Quête terminée" in line for line in dialogue(p,"forge"))

        old = party()
        unlock(old)
        old["inventory"]["p"] = {key:1000 for key in content.gameplay()["materials"]}
        forge.execute(old,"p","craft",recipe,GameError)
        for _ in range(goal): forge.execute(old,"p","upgrade",recipe,GameError)
        dialogue(old,"forge")
        assert states(old)["craft_"+recipe]["progress"] == 1
        assert objective not in states(old)
        dialogue(old,"forge")
        assert states(old)[objective]["progress"] == 1

    print(f"Catalogues validés : {len(content.DATA['quests'])} quêtes facultatives, 4 espèces liées à leurs recettes et améliorations.")
    print("Exploration libre, forge de Rosée verrouillée jusqu’à la remise de Mira, butins et récompenses vérifiés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-fixtures", type=Path)
    args = parser.parse_args()
    main()
    if args.ui_fixtures:
        p = party()
        fields.start(p,0)
        fields.enter(p,"rosee",[43,12],0)
        p["inventory"]["p"] = {key:1000 for key in content.gameplay()["materials"]}
        dialogue(p,"mira")
        dialogue(p,"forge")
        locked = tutorial.view(p,"p",0)
        quest = forge.rosee_unlock_quest()
        states(p)[quest["id"]]["progress"] = quest["count"]
        dialogue(p,"mira")
        p.pop("field_map",None)
        p.update(battle=None,mobs=[],mob=None,position="forge")
        for _,_,recipe,_ in NEW_CONTENT: forge.execute(p,"p","craft",recipe,GameError)
        dialogue(p,"forge")
        dialogue(p,"forge")
        args.ui_fixtures.parent.mkdir(parents=True, exist_ok=True)
        scenes={"locked":locked,"unlocked":tutorial.view(p,"p",0)}
        panoplie=party()
        unlock(panoplie)
        panoplie["inventory"]["p"]={key:1000 for key in content.gameplay()["materials"]}
        for recipe in ("casque","veste","gants","jambieres","bottes"):
            forge.execute(panoplie,"p","craft",recipe,GameError)
        scenes["panoplie"]=tutorial.view(panoplie,"p",0)
        forge.execute(panoplie,"p","craft","bottes_lucioles",GameError)
        scenes["panoplie_mixed"]=tutorial.view(panoplie,"p",0)
        args.ui_fixtures.write_text(json.dumps(scenes,ensure_ascii=False),encoding="utf-8")
