import json
from copy import deepcopy
from pathlib import Path

import pytest

from jeuxRPG.multiplayer import (
    content,
    fields,
    forge,
    map_building,
    narrative,
    tactics,
    tutorial,
    world,
)
from jeuxRPG.multiplayer.controller_project import Project
from jeuxRPG.multiplayer.service import GameError
from jeuxRPG.multiplayer.world_topology import compile_world


@pytest.fixture
def story(monkeypatch):
    project = Project(Path(__file__).resolve().parents[1] / "projects/authored")
    monkeypatch.setattr(content, "DATA", deepcopy(project.content))
    monkeypatch.setattr(fields, "MAPS", deepcopy(project.maps))
    monkeypatch.setattr(map_building, "MOBS", project.mobs)
    monkeypatch.setattr(forge, "GAMEPLAY", content.DATA["gameplay"])
    monkeypatch.setattr(forge, "RECIPES", content.DATA["gameplay"]["recipes"])
    monkeypatch.setattr(forge, "RULES", content.DATA["gameplay"]["rules"]["forge"])
    monkeypatch.setattr(world, "WORLD_MAP_DATA", fields.MAPS)
    for definition in fields.MAPS.values():
        monkeypatch.setitem(tactics.PRESETS, definition["id"], definition)
    for name, value in zip(
        (
            "PLACES",
            "VILLAGE_STREETS",
            "ROUTES",
            "LEVELS",
            "POINT_MAPS",
            "ZONE_ENTRIES",
            "EDGES",
        ),
        compile_world(fields.MAPS),
        strict=True,
    ):
        monkeypatch.setattr(world, name, value)
    return project


def party(players=("p",)):
    result = tutorial.new_party(
        [{"id": key, "name": key, "class_name": "Knight"} for key in players]
    )
    fields.start(result, 0)
    return result


def visit(party, npc, player="p"):
    map_id, site = next(
        (key, site)
        for key, definition in fields.MAPS.items()
        for site in definition["sites"]
        if site["id"] == npc
    )
    fields.enter(party, map_id, site["position"], 0)
    # Keep other players from occupying the interaction cell in group tests.
    party["battle"]["players"][player]["position"] = site["position"][:]
    tutorial.execute(party, player, "talk", {"npc": npc}, 0, GameError, lambda: 1)


def choose(party, npc, key, player="p"):
    return tutorial.execute(
        party, player, "story", {"npc": npc, "choice": key}, 0, GameError, lambda: 1
    )


def accept(p, npc, quest, player="p"):
    visit(p, npc, player)
    choose(p, npc, "accept:" + quest, player)


def claim(p, npc, quest, player="p"):
    visit(p, npc, player)
    choose(p, npc, "claim:" + quest, player)


def read(p, npc, topic="lire", player="p"):
    visit(p, npc, player)
    choose(p, npc, "topic:" + topic, player)


def test_talking_never_accepts_quests_and_choices_are_personal(story):
    p = party(("p", "q"))
    visit(p, "mira")
    assert narrative.journal(p, "p") == []
    choose(p, "mira", "accept:mira_hunt_1")
    assert len(narrative.journal(p, "p")) == 1
    assert narrative.journal(p, "q") == []
    with pytest.raises(GameError, match="Ouvrez"):
        choose(p, "mira", "accept:mira_hunt_1", "q")
    fields.enter(p, "hunt", [2, 20], 0)
    for _ in range(4):
        content.quest_event(p, "kill", "goblin", "zone_lisiere")
    assert narrative.journal(p, "p")[0]["status"] == "ready"
    assert narrative.journal(p, "q") == []
    before_q = deepcopy(p["characters"]["q"])
    claim(p, "mira", "mira_hunt_1")
    assert forge.rosee_unlocked(p, "p") and not forge.rosee_unlocked(p, "q")
    assert p["characters"]["q"] == before_q
    before_p = deepcopy(p["characters"]["p"])
    with pytest.raises(GameError):
        choose(p, "mira", "claim:mira_hunt_1")
    assert p["characters"]["p"] == before_p


def test_inspecting_before_acceptance_is_remembered_and_local(story):
    p = party()
    with pytest.raises(GameError, match="Approchez"):
        tutorial.execute(
            p, "p", "talk", {"npc": "borne_veille"}, 0, GameError, lambda: 1
        )
    read(p, "borne_veille")
    assert narrative.journal(p, "p") == []
    accept(p, "clearing:0", "derniere_borne")
    assert narrative.journal(p, "p")[0]["status"] == "ready"
    claim(p, "clearing:0", "derniere_borne")
    assert narrative.completed(p, "p", "derniere_borne")
    # No automatic travel or regional prerequisite was added.
    assert not p["transit"] and p["journey"] == []
    assert world.path("clearing", "rosee", set(world.PLACES))


def test_forge_recognizes_existing_equipment_only_for_its_owner(story):
    p = party(("p", "q"))
    narrative.state(p, "p")["quests"]["mira_hunt_1"] = {
        "status": "completed",
        "progress": 4,
    }
    p["inventory"]["p"] = dict.fromkeys(content.DATA["gameplay"]["materials"], 1000)
    visit(p, "forge")
    assert (
        "Mira m’a parlé" in tutorial.view(p, "p", 0)["narrative"]["greetings"]["forge"]
    )
    tutorial.execute(
        p, "p", "craft", {"recipe": "bottes_lucioles"}, 0, GameError, lambda: 1
    )
    accept(p, "forge", "craft_bottes_lucioles")
    assert (
        next(
            q for q in narrative.journal(p, "p") if q["id"] == "craft_bottes_lucioles"
        )["status"]
        == "ready"
    )
    with pytest.raises(GameError, match="rendre"):
        choose(p, "forge", "accept:upgrade_bottes_lucioles")
    claim(p, "forge", "craft_bottes_lucioles")
    tutorial.execute(
        p, "p", "upgrade", {"recipe": "bottes_lucioles"}, 0, GameError, lambda: 1
    )
    accept(p, "forge", "upgrade_bottes_lucioles")
    assert (
        next(
            q for q in narrative.journal(p, "p") if q["id"] == "upgrade_bottes_lucioles"
        )["status"]
        == "ready"
    )
    narrative.state(p, "q")["quests"]["mira_hunt_1"] = {
        "status": "completed",
        "progress": 4,
    }
    accept(p, "forge", "craft_bottes_lucioles", "q")
    assert narrative.journal(p, "q")[-1]["progress"] == 0


def test_old_quests_aliases_and_retired_deserter_migrate_once(story):
    p = party()
    p["custom_quests"] = {
        "mira_hunt": {"status": "completed", "progress": 10},
        "craft_bottes_lucioles": {"status": "completed", "progress": 1},
    }
    p["quest"] = "completed"
    before = deepcopy(p["characters"])
    assert forge.rosee_unlocked(p, "p")
    assert narrative.completed(p, "p", "craft_bottes_lucioles")
    assert narrative.state(p, "p")["quests"]["mira_hunt_1"]["status"] == "completed"
    p["mobs"].append(
        {**deepcopy(p["mobs"][0]), "name": "gobelin deserteur", "combat_id": "old-rusk"}
    )
    p["fields"]["clearing"] = {
        "mobs": deepcopy(p["mobs"]),
        "battle": deepcopy(p["battle"]),
    }
    fields.migrate_terrain(p)
    assert not any(m["name"] == "gobelin deserteur" for m in p["mobs"])
    assert not any(
        m["name"] == "gobelin deserteur" for m in p["fields"]["clearing"]["mobs"]
    )
    narrative.state(p, "p")
    assert p["characters"] == before
    view = tutorial.view(p, "p", 0)
    assert "narrative_state" not in view


def test_replaced_equipment_remains_recognized_before_accepting_its_quests(story):
    p = party()
    narrative.state(p, "p")["quests"]["mira_hunt_1"] = {
        "status": "completed",
        "progress": 4,
    }
    p["inventory"]["p"] = dict.fromkeys(content.DATA["gameplay"]["materials"], 1000)
    visit(p, "forge")
    for action, recipe in [
        ("craft", "bottes_lucioles"),
        ("upgrade", "bottes_lucioles"),
        ("craft", "bottes"),
    ]:
        tutorial.execute(p, "p", action, {"recipe": recipe}, 0, GameError, lambda: 1)
    assert p["equipment"]["p"]["feet"]["recipe"] == "bottes"
    accept(p, "forge", "craft_bottes_lucioles")
    claim(p, "forge", "craft_bottes_lucioles")
    accept(p, "forge", "upgrade_bottes_lucioles")
    assert (
        next(
            q for q in narrative.journal(p, "p") if q["id"] == "upgrade_bottes_lucioles"
        )["status"]
        == "ready"
    )


@pytest.mark.parametrize("ending", ["restaurer", "partager"])
def test_complete_brume_arc_in_any_region_order_and_restore_ending(story, ending):
    p = party(("p", "q"))
    # Legacy historical victory, before accepting the boss quest.
    p["achievements"]["counters"].setdefault("kills", {}).setdefault(
        "seigneur_gobelin", {}
    ).setdefault("zone_brume", {})["brume_sanctuaire"] = 1
    accept(p, "oriel", "noms_mousse")
    for site in ("stele_isel", "stele_aline", "stele_tovan"):
        read(p, site)
    claim(p, "oriel", "noms_mousse")
    accept(p, "elyne", "garde_sans_releve")
    read(p, "poste_veille")
    claim(p, "elyne", "garde_sans_releve")
    accept(p, "elyne", "voix_commande")
    assert (
        next(q for q in narrative.journal(p, "p") if q["id"] == "voix_commande")[
            "status"
        ]
        == "ready"
    )
    claim(p, "elyne", "voix_commande")
    accept(p, "oriel", "accord_vivants")
    read(p, "elyne", "accord")
    read(p, "forge", "accord")
    read(p, "mira", "accord")
    read(p, "oriel", "accord")
    choose(p, "oriel", "answer:" + ending)
    claim(p, "oriel", "accord_vivants")
    saved = json.loads(json.dumps(p))
    assert narrative.view(saved, "p")["ending"]["id"] == ending
    assert narrative.view(saved, "q")["ending"] is None
    assert (
        "Témoin de la Veille"
        in tutorial.view(saved, "p", 0)["achievements"]["unlocked_titles"]
    )
    before = deepcopy(saved["characters"])
    read(saved, "oriel", "accord")
    with pytest.raises(GameError, match="déjà"):
        choose(
            saved,
            "oriel",
            "answer:" + ("partager" if ending == "restaurer" else "restaurer"),
        )
    assert saved["characters"] == before


def test_repeatable_patrol_requires_new_acceptance_and_new_kills(story):
    p = party()
    accept(p, "mira", "patrouille_veteran")
    fields.enter(p, "hunt", [2, 20], 0)
    for _ in range(5):
        content.quest_event(p, "kill", "goblin", "zone_lisiere")
    claim(p, "mira", "patrouille_veteran")
    choose(p, "mira", "accept:patrouille_veteran")
    assert narrative.state(p, "p")["quests"]["patrouille_veteran"]["progress"] == 0
    with pytest.raises(GameError):
        choose(p, "mira", "claim:patrouille_veteran")


def test_rusk_and_carrier_branches_have_real_local_objectives(story):
    p = party()
    accept(p, "rusk", "rusk_rencontre")
    read(p, "rusk", "partir")
    read(p, "mira", "rusk")
    claim(p, "rusk", "rusk_rencontre")
    accept(p, "rusk", "rusk_temoin")
    read(p, "ancien_chargement")
    read(p, "oriel", "rusk")
    claim(p, "rusk", "rusk_temoin")
    accept(p, "neran", "trois_silences")
    read(p, "inscription_veille")
    read(p, "forge", "inscription")
    claim(p, "neran", "trois_silences")
    accept(p, "forge", "prix_outil")
    read(p, "forge", "aveu")
    choose(p, "forge", "answer:reparer")
    claim(p, "forge", "prix_outil")
    assert not forge.rosee_unlocked(p, "p"), (
        "L’histoire de Garrik se découvre même sans déblocage de la forge"
    )
    assert all(
        narrative.completed(p, "p", q)
        for q in ("rusk_rencontre", "rusk_temoin", "trois_silences", "prix_outil")
    )


def test_veilleur_memorial_does_not_require_another_hunt(story):
    p = party()
    personal = narrative.state(p, "p")
    personal["quests"].update(
        {
            key: {"status": "completed", "progress": 3}
            for key in ("noms_mousse", "garde_sans_releve", "hunt_veilleur_des_brumes")
        }
    )
    accept(p, "elyne", "ceux_qu_on_garde")
    read(p, "oriel", "noms")
    claim(p, "elyne", "ceux_qu_on_garde")
    assert "Porte-mémoire" in narrative.view(p, "p")["titles"]


def test_catalogue_rejects_missing_facts_and_unplaced_npcs(story):
    bad = deepcopy(story.content)
    bad["narrative"]["npcs"]["oriel"]["topics"][0]["facts"] = ["missing"]
    with pytest.raises(ValueError):
        content.validate_content(bad)
    bad = deepcopy(story.content)
    bad["narrative"]["facts"]["borne_lue"]["npc"] = "not_placed"
    with pytest.raises(ValueError):
        content.validate_references(bad, story.mobs, story.maps)
    bad = deepcopy(story.content)
    next(
        topic
        for topic in bad["narrative"]["npcs"]["borne_veille"]["topics"]
        if topic["id"] == "lire"
    )["requires"] = ["derniere_borne"]
    with pytest.raises(ValueError, match="boucle"):
        content.validate_content(bad)


def test_enemy_speech_is_authored_and_does_not_interrupt_combat(story):
    p = party()
    fields.enter(p, "brume_sanctuaire", [2, 12], 0)
    boss = next(m for m in p["mobs"] if m["mob_id"] == "seigneur_gobelin")
    assert narrative.combat_messages(p) == []
    boss["alerted"] = True
    messages = narrative.combat_messages(p)
    assert len(messages) == 1 and "La mienne" in messages[0]
    assert narrative.combat_messages(p) == []
    assert p["battle"] is not None and not narrative.view(p, "p")["conversation"]


@pytest.mark.usefixtures("gui_display")
def test_builder_widgets_edit_narrative_and_multiline_fields(story, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    from jeuxRPG.multiplayer.controller import Controller

    root = tk.Tk()
    root.withdraw()
    try:
        controller = Controller(root, story)
        table = controller.tables["narrative"]
        assert table.exists("topic|oriel|veille")
        table.selection_set("topic|oriel|veille")
        original_form = controller.form
        monkeypatch.setattr(
            controller,
            "form",
            lambda title, values, choices=None: {
                **values,
                "text": "Dialogue édité par le Builder.",
            },
        )
        controller.edit("narrative")
        assert (
            story.content["narrative"]["npcs"]["oriel"]["topics"][0]["text"]
            == "Dialogue édité par le Builder."
        )
        monkeypatch.setattr(controller, "form", original_form)

        def widgets(widget):
            return [
                child
                for direct in widget.winfo_children()
                for child in [direct, *widgets(direct)]
            ]

        def apply_form():
            dialog = next(
                child
                for child in root.winfo_children()
                if isinstance(child, tk.Toplevel)
            )
            dialog.withdraw()
            texts = [
                widget for widget in widgets(dialog) if isinstance(widget, tk.Text)
            ]
            for widget, value in zip(
                texts, ["Réplique modifiée.", '["borne_lue"]'], strict=True
            ):
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            next(
                widget
                for widget in widgets(dialog)
                if isinstance(widget, ttk.Button) and widget.cget("text") == "Appliquer"
            ).invoke()

        root.after(30, apply_form)
        root.after(
            5000,
            lambda: [
                child.destroy()
                for child in root.winfo_children()
                if isinstance(child, tk.Toplevel)
            ],
        )
        result = controller.form(
            "Texte et indices", {"text": "Texte initial.", "facts": ["borne_lue"]}
        )
        assert result == {"text": "Réplique modifiée.", "facts": ["borne_lue"]}
    finally:
        root.destroy()


def test_builder_can_edit_dialogue_and_preserve_quest_references(story, tmp_path):
    from jeuxRPG.multiplayer.controller_narrative import locate, rows

    assert any(row[0] == "topic|oriel|accord" for row in rows(story))
    container, key = locate(story.content["narrative"], "topic|oriel|veille")
    container[key]["text"] = "Texte de vérification du Builder."
    story.rename("quests", "voix_commande", "cloche_retrouvee")
    assert (
        "cloche_retrouvee"
        in next(
            t
            for t in story.content["narrative"]["npcs"]["oriel"]["topics"]
            if t["id"] == "accord"
        )["requires"]
    )
    exported = Project(tmp_path / "story")
    exported.restore(story.state())
    exported.save()
    reopened = Project(exported.directory)
    assert (
        locate(reopened.content["narrative"], "topic|oriel|veille")[0][0]["text"]
        == "Texte de vérification du Builder."
    )
