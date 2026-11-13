"""Spawner discovery and neutral creatures behave as configured by the Builder."""

from copy import deepcopy

import pytest
from test_controller import project
from test_fields import party as field_party
from test_fields import stable_field_scenarios  # noqa: F401
from test_tactics import act, near, party

from jeuxRPG.multiplayer import content, map_assets, map_building, mob_rules, tactics
from jeuxRPG.multiplayer.mob_picker import MobPicker, filter_profiles, profiles, race_of


def catalogue(tmp_path):
    selected = project(tmp_path)
    selected.mobs["goblin"].update(race="Gobelin", hostile=True)
    selected.mobs["scout"] = {
        "parent": "goblin",
        "name": "Éclaireur des bois",
        "hostile": False,
        "abilities": [
            {
                "name": "Flèche",
                "type": "damage",
                "level": 1,
                "power": 3,
                "growth": 0.5,
                "cooldown": 5,
                "cast": 0.5,
                "range": 6,
                "duration": 2,
            }
        ],
    }
    selected.mobs["shaman"] = {
        "parent": "scout",
        "name": "Chamane des bois",
        "abilities": [
            *selected.mobs["scout"]["abilities"],
            {"skill_id": "native:Priest:Blessing", "level": 1},
        ],
    }
    return selected


def test_filters_combine_actual_abilities_race_name_and_hostility(tmp_path):
    selected = catalogue(tmp_path)
    before = selected.state()
    rows = profiles(selected.mobs, selected.content)
    assert race_of(selected.mobs, "shaman") == "Gobelin"
    assert [
        row["id"]
        for row in filter_profiles(
            rows, "ECLAIREUR", "Gobelin", "ranged", hostility="neutral"
        )
    ] == ["scout"]
    assert [
        row["id"]
        for row in filter_profiles(
            rows, race="Gobelin", combat="ranged", roles=["buff"], hostility="neutral"
        )
    ] == ["shaman"]
    assert filter_profiles(rows, query="absent") == []
    assert filter_profiles(rows, roles=["summon"]) == []
    assert "buff" not in next(row for row in rows if row["id"] == "scout")["roles"]
    assert selected.state() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("hostile", "false"),
        ("hostile", 0),
        ("race", ""),
        ("race", []),
        ("race", "x" * 65),
    ],
)
def test_invalid_species_metadata_is_rejected(field, value):
    mobs = deepcopy(map_building.MOBS)
    mobs["goblin"][field] = value
    with pytest.raises(ValueError):
        mob_rules.validate_mobs(mobs)


def test_species_defaults_and_spawner_overrides_persist(tmp_path, monkeypatch):
    selected = catalogue(tmp_path)
    monkeypatch.setattr(map_building, "MOBS", selected.mobs)
    map_id = "clearing"
    position = selected.maps[map_id]["spawns"][0]
    selected.maps[map_id]["spawners"] = [
        {"position": position, "mob_id": "scout", "hostile": True, "count": 2}
    ]
    selected.save()
    loaded = type(selected)(selected.directory)
    assert loaded.mobs["scout"]["hostile"] is False
    config = map_building.spawners(loaded.maps[map_id])[0]
    overridden = map_building.create_mob(loaded.maps, map_id, config, 0)
    assert overridden["hostile"] is True and overridden["race"] == "Gobelin"
    config.pop("hostile")
    assert map_building.create_mob(loaded.maps, map_id, config, 0)["hostile"] is False
    loaded.maps[map_id]["spawners"][0]["hostile"] = "Non"
    with pytest.raises(ValueError, match="hostilité"):
        map_assets.validate(loaded.maps)


@pytest.mark.usefixtures("gui_display")
def test_real_picker_combines_filters_handles_empty_results_and_keeps_selected_id(
    tmp_path,
):
    import tkinter as tk

    selected = catalogue(tmp_path)
    root = tk.Tk()
    root.withdraw()
    try:
        picker = MobPicker(root, selected.mobs, selected.content, "scout")
        picker.frame.pack(fill="both", expand=True)
        root.update()
        assert picker.get() == "scout"
        picker.race.set("Gobelin")
        picker.combat.set("À distance")
        picker.hostility.set("Neutres")
        picker.query.set("eclaireur")
        root.update()
        assert picker.table.get_children() == ("scout",)
        assert picker.get() == "scout"
        picker.roles["buff"].set(True)
        assert not picker.get()
        assert "Aucun résultat" in picker.details.get()
        picker.query.set("")
        assert picker.get() == "shaman"
        picker.reset()
        assert len(picker.table.get_children()) == len(selected.mobs)
    finally:
        root.destroy()


def test_neutral_patrols_without_aggro_then_defends_when_attacked():
    data = party()
    near(data)
    mob = data["mobs"][0]
    mob["hostile"] = False
    data["battle"]["players"]["p0"]["hidden"] = False
    hp = data["characters"]["p0"]["stats"]["hp"]["current"]
    for now in range(8):
        tactics.advance(data, now, lambda: 0.5)
    assert not mob.get("alerted") and mob["target"] is None
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == hp
    assert tactics.view(data, 8, "p0")["hostiles_alive"] == 0
    near(data)
    act(data, "strike", now=8, target=mob["combat_id"])
    assert mob["provoked"] and mob["target"] == "p0"
    assert tactics.view(data, 8, "p0")["hostiles_alive"] == 1
    for now in range(9, 18):
        tactics.advance(data, now, lambda: 0.5)
    assert data["characters"]["p0"]["stats"]["hp"]["current"] < hp


def test_hostile_still_aggroes_without_being_attacked():
    data = party()
    near(data)
    data["mobs"][0]["hostile"] = True
    data["battle"]["players"]["p0"]["hidden"] = False
    tactics.advance(data, 1, lambda: 0.5)
    assert data["mobs"][0]["target"] == "p0"


def test_allies_cannot_recruit_neutral_creatures():
    data = party(mobs=2)
    caller, neutral = data["mobs"]
    neutral["hostile"] = False
    assert neutral["combat_id"] in caller["allies"]
    assert neutral not in tactics.unalerted_allies(data, caller)


def test_legacy_save_gets_builder_behavior_and_preserves_spawner_override(
    tmp_path, monkeypatch
):
    selected = catalogue(tmp_path)
    monkeypatch.setattr(map_building, "MOBS", selected.mobs)
    maps = {
        "map": {
            "spawns": [[1, 1]],
            "spawners": [{"position": [1, 1], "mob_id": "scout", "hostile": True}],
        }
    }
    old = {"mob_id": "scout", "combat_id": "map-mob-0"}
    neutral = {"mob_id": "scout", "combat_id": "other", "alerted": True, "target": "p0"}
    data = {"field_map": "map", "mobs": [old, neutral]}
    map_building.migrate_behavior(data, maps)
    assert old["hostile"] is True
    assert neutral["hostile"] is False and neutral["target"] is None
    assert not neutral["alerted"]


def test_old_catalogue_profiles_keep_compatible_defaults():
    rows = profiles(map_building.MOBS, content.DATA)
    assert rows and all("melee" in row["roles"] for row in rows)


@pytest.mark.usefixtures("gui_display")
def test_real_spawner_form_selects_by_name_and_saves_override(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk
    from types import SimpleNamespace

    from jeuxRPG.multiplayer import map_editor, mob_picker

    selected = catalogue(tmp_path)
    root = tk.Tk()
    root.withdraw()
    captured, errors, failures = [], [], []
    actual_picker = mob_picker.MobPicker

    def capture(*args, **kwargs):
        picker = actual_picker(*args, **kwargs)
        captured.append(picker)
        return picker

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    monkeypatch.setattr(mob_picker, "MobPicker", capture)
    monkeypatch.setattr(map_editor, "tk", tk, raising=False)
    monkeypatch.setattr(map_editor, "ttk", ttk, raising=False)
    monkeypatch.setattr(map_editor, "MOBS", selected.mobs)
    editor = map_editor.MapEditor.__new__(map_editor.MapEditor)
    editor.root, editor.catalog_content = root, selected.content
    editor._messages = SimpleNamespace(
        showerror=lambda *args, **kwargs: errors.append(args)
    )
    definition = deepcopy(selected.maps["clearing"])
    position = definition["spawns"][0]
    definition["spawners"] = [
        {"position": position, "mob_id": "goblin", "patrol": [position]}
    ]

    def choose():
        try:
            picker = captured[0]
            accept = next(
                widget
                for widget in descendants(root)
                if isinstance(widget, ttk.Button) and widget.cget("text") == "Valider"
            )
            picker.query.set("aucun résultat")
            accept.invoke()
            assert errors and picker.frame.winfo_exists()
            picker.query.set("eclaireur")
            assert picker.get() == "scout"
            behavior = next(
                widget
                for widget in descendants(root)
                if isinstance(widget, ttk.Combobox)
                and "Espèce (par défaut)" in widget.cget("values")
            )
            behavior.set("Hostile")
            accept.invoke()
        except BaseException as error:
            failures.append(error)
            root.destroy()

    try:
        root.after(100, choose)
        editor._paint_cell(position, definition, "Spawn")
        assert not failures, failures
        saved = definition["spawners"][-1]
        assert saved["mob_id"] == "scout" and saved["hostile"] is True
        assert saved["patrol"] == [position]
    finally:
        if not failures:
            root.destroy()


def test_neutral_is_not_attacked_by_an_automatic_summon():
    data = party(class_name="Necromancien")
    near(data)
    mob = data["mobs"][0]
    mob["hostile"] = False
    act(data, "skill", skill_name="Low Skull", target="p0")
    tactics.complete_casts(data, 6, lambda: 0.5)
    summon = next(iter(data["battle"]["summons"].values()))
    summon["position"] = [9, 5]
    mob["position"] = [9, 4]
    hp = mob["stats"]["hp"]["current"]
    tactics.advance(data, 6, lambda: 0.5)
    assert mob["stats"]["hp"]["current"] == hp
    assert not mob.get("provoked")


def test_neutral_does_not_block_dialogue_but_hostile_does(monkeypatch):
    from jeuxRPG.multiplayer import fields, narrative

    data = party()
    data["field_map"] = "clearing"
    monkeypatch.setattr(fields, "interactions", lambda *args: [{"id": "mira"}])
    monkeypatch.setattr(tactics, "sees", lambda *args: True)
    data["mobs"][0]["hostile"] = False
    assert narrative.accessible(data, "p0", "mira")
    data["mobs"][0]["hostile"] = True
    assert not narrative.accessible(data, "p0", "mira")


@pytest.mark.usefixtures("stable_field_scenarios")
def test_neutral_does_not_lock_the_next_dungeon_room():
    from jeuxRPG.multiplayer import fields

    data = field_party()
    fields.MAPS["cave_1"]["dungeon"] = {
        "id": "test",
        "room": 1,
        "final": False,
        "lock_until_clear": True,
    }
    fields.MAPS["cave_2"]["dungeon"] = {
        "id": "test",
        "room": 2,
        "final": False,
        "lock_until_clear": True,
    }
    fields.enter(data, "cave_1", [20, 7], 0)
    for mob in data["mobs"]:
        mob["hostile"] = False
    gate = next(
        gate
        for gate in fields.MAPS["cave_1"]["exits"]
        if gate["destination"] == "cave_2"
    )
    fields.transition(data, gate, "p", 1)
    assert data["field_map"] == "cave_2"
