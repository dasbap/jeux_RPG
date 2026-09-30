import json
import os
import random
import subprocess
import sys

import pytest
from pydantic import ValidationError

from jeuxRPG.adventure import Adventure
from jeuxRPG.adventure.equipment import Family, Gear, Inventory, Slot, material_id, parse_recipe


@pytest.mark.parametrize("family", list(Family))
def test_generated_creature_set_and_recipe_consumption(family):
    inventory = Inventory()
    inventory.add_loot(family, 2, 7, 3)
    recipes = inventory.recipes()
    assert len(recipes) == 3
    for slot in Slot:
        recipe = f"{family.value}:2:{slot.value}"
        identifier = inventory.craft(recipe)
        inventory.equip(identifier)
        assert inventory.items[identifier].family == family
        assert inventory.items[identifier].tier == 2
    assert all(count == 0 for count in inventory.materials.values())
    expected_hp = sum(gear.bonuses["HP"] for gear in inventory.items.values()) + 40
    assert inventory.bonuses()["HP"] == expected_hp
    inventory.unequip(Slot.BOOTS)
    assert inventory.bonuses()["HP"] == expected_hp - 40 - 10


def test_craft_is_atomic_without_materials_and_equipping_keeps_items():
    inventory = Inventory()
    inventory.add_loot(Family.ORC, 1, 3, 0)
    before = inventory.model_dump_json()
    with pytest.raises(ValueError, match="insuffisants"):
        inventory.craft("Orc:1:chest")
    assert inventory.model_dump_json() == before
    inventory.add_loot(Family.ORC, 1, 0, 2)
    first = inventory.craft("Orc:1:helmet")
    inventory.add_loot(Family.GOBLIN, 1, 2, 1)
    second = inventory.craft("Goblin:1:helmet")
    inventory.equip(first)
    inventory.equip(second)
    assert len(inventory.items) == 2
    assert inventory.equipped[Slot.HELMET] == second
    with pytest.raises(ValueError):
        inventory.equip("missing")


@pytest.mark.parametrize("recipe", ["Unknown:1:boots", "Goblin:0:helmet", "Goblin:-1:chest", "Goblin:01:boots", "Goblin:1:weapon", "bad"])
def test_invalid_recipes_are_rejected(recipe):
    with pytest.raises(ValueError):
        parse_recipe(recipe)


def test_invalid_saved_inventory_rejected():
    with pytest.raises(ValidationError):
        Inventory(materials={"Goblin:1:hide": -1})
    with pytest.raises(ValidationError):
        Inventory(materials={"Unknown:1:hide": 3})
    with pytest.raises(ValidationError):
        Inventory(equipped={Slot.HELMET: "missing"})
    with pytest.raises(ValidationError):
        Inventory(items={"item-000001": Gear(family=Family.ORC, tier=1, slot=Slot.CHEST)}, equipped={Slot.HELMET: "item-000001"}, next_id=2)


def test_equipment_does_not_stack_and_save_roundtrip(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.inventory.add_loot(Family.ORC, 2, 7, 3)
    base = session.player.hp.value
    identifiers = [session.craft(f"Orc:2:{slot.value}") for slot in Slot]
    for identifier in identifiers:
        session.equip(identifier)
    maximum = session.player.hp.value
    hp = session.player.hp.current_value
    assert maximum == base + session.inventory.bonuses()["HP"]
    session.equip(identifiers[0])
    session.refresh_equipment()
    assert session.player.hp.value == maximum
    assert session.player.hp.current_value == hp
    session.save()
    loaded = Adventure(session.path, class_name="Mage", seed=0)
    assert loaded.status() == session.status()
    assert loaded.inventory == session.inventory
    assert loaded.rng.getstate() == session.rng.getstate()
    loaded.unequip("chest")
    assert loaded.player.hp.value < maximum
    assert len(loaded.inventory.items) == 3


def test_automatic_full_set_and_no_duplicate_crafting(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.inventory.add_loot(Family.GOBLIN, 1, 7, 3)
    assert len(session.auto_craft()) == 3
    assert len(session.inventory.equipped) == 3
    before = session.inventory.model_dump_json()
    assert session.auto_craft() == []
    assert session.inventory.model_dump_json() == before


def test_encounter_resume_is_deterministic_and_does_not_leak_rng(tmp_path):
    session = Adventure(tmp_path / "first.json", seed=42)
    initial = random.getstate()
    session.encounter(auto_craft=True)
    assert random.getstate() == initial
    restored = Adventure(session.path)
    restored.path = tmp_path / "second.json"
    assert session.encounter(auto_craft=True) == restored.encounter(auto_craft=True)
    assert session.snapshot().model_dump() == restored.snapshot().model_dump()
    assert session.battles == session.wins + session.losses + session.draws == 2


def test_draw_has_no_loot_and_is_saved(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.player.attack = lambda target: (False, "")
    result = session.encounter(max_rounds=1)
    assert result["outcome"] == "draw"
    assert not result["loot"]
    assert not session.inventory.materials
    assert Adventure(session.path).draws == 1


def test_defeat_recovers_without_progress_or_inventory_loss(tmp_path):
    session = Adventure(tmp_path / "player.json")
    session.player.hp.value = 1
    session.player.hp.current_value = 1
    session.player.attack = lambda target: (False, "")
    session.player.gain_exp(250)
    session.player.hp.value = 1
    session.player.hp.current_value = 1
    progression = (session.player.level, session.player.exp)
    result = session.encounter(max_rounds=20)
    assert result["outcome"] == "defeat"
    assert (session.player.level, session.player.exp) == progression
    assert session.player.is_alive()
    assert not result["loot"]


def test_failed_atomic_save_preserves_previous_file(tmp_path, monkeypatch):
    session = Adventure(tmp_path / "player.json")
    session.save()
    before = session.path.read_bytes()
    def fail(*args):
        raise OSError("write failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        session.save()
    assert session.path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("change", [lambda data: data.update(version=99), lambda data: data["player"].update(level=-1), lambda data: data.update(wins=2), lambda data: data["player"].update(hp=999999), lambda data: data.update(rng_state=[])])
def test_invalid_save_never_overwritten(tmp_path, change):
    session = Adventure(tmp_path / "player.json")
    session.save()
    data = json.loads(session.path.read_text())
    change(data)
    session.path.write_text(json.dumps(data))
    before = session.path.read_bytes()
    with pytest.raises((ValueError, IndexError)):
        Adventure(session.path)
    assert session.path.read_bytes() == before


def test_cli_finite_run_and_resume(tmp_path):
    path = tmp_path / "player.json"
    for battles, expected in [(3, 3), (2, 5)]:
        result = subprocess.run([sys.executable, "main.py", "--battles", str(battles), "--interval", "0", "--save", str(path)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert Adventure(path).battles == expected


def test_interactive_craft_and_equip(tmp_path, monkeypatch, capsys):
    from jeuxRPG.cli import interactive
    session = Adventure(tmp_path / "player.json")
    session.inventory.add_loot(Family.GOBLIN, 1, 2, 1)
    commands = iter(["inventaire", "recettes", "craft Goblin:1:helmet", "equiper item-000001", "personnage", "retirer helmet", "craft invalid", "???", "quitter"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    interactive(session)
    assert len(session.inventory.items) == 1
    assert not session.inventory.equipped
    assert "Objet fabriqué" in capsys.readouterr().out


@pytest.mark.parametrize("class_name", ["Knight", "Mage", "Archer", "Priest", "Necromancien"])
def test_all_playable_classes_resume_and_can_progress(tmp_path, class_name):
    from jeuxRPG._class.sub_character.invocations.invocation import Invocation
    session = Adventure(tmp_path / f"{class_name}.json", class_name=class_name)
    for _ in range(10):
        session.encounter(auto_craft=True)
    assert session.wins > 0
    assert session.player.level > 1
    assert not any(invocation.master is session.player for invocation in Invocation.all_invocation)
    restored = Adventure(session.path)
    assert session.encounter() == restored.encounter()


@pytest.mark.parametrize("family", list(Family))
@pytest.mark.parametrize("level", [1, 2, 5, 10])
def test_enemy_scaling_matches_existing_progression(tmp_path, family, level):
    from jeuxRPG._class.character import Character
    session = Adventure(tmp_path / "player.json")
    scaled = session.create_enemy(family, level)
    reference = Character.create(family.value, "reference", "Reference")
    if level > 1:
        reference.gain_exp(50 * (level - 1) * level)
    for name in ("HP", "Force", "Endurance", "Intelligence", "Sagesse"):
        assert scaled.get_stat(name).value == reference.get_stat(name).value
    assert [(energy.value, type(energy)) for energy in scaled.energie] == [(energy.value, type(energy)) for energy in reference.energie]
    assert scaled.level == reference.level
    assert scaled.skills.keys() == reference.skills.keys()


def test_high_level_enemy_creation_does_not_recurse(tmp_path):
    session = Adventure(tmp_path / "player.json")
    enemy = session.create_enemy(Family.ORC, 10000)
    assert enemy.level == 10000
    assert enemy.hp.value > 10000


def test_character_snapshot_existing_save_model(tmp_path):
    from jeuxRPG._core.save.entity_save import PlayerSaveData
    session = Adventure(tmp_path / "player.json")
    data = PlayerSaveData.from_character(session.player)
    assert data.stats["force"] == session.player.force.current_value
    assert data.level == session.player.level


def test_small_damage_to_necromancer_with_summons(tmp_path):
    from jeuxRPG._class.sub_character.invocations.squelette import Squelette
    session = Adventure(tmp_path / "player.json", class_name="Necromancien")
    summon = Squelette(session.player)
    session.player.invocations.add_invocation(summon)
    session.player.lose_hp(session.player, 1)
    session.player.invocations.kill_all()


def test_interrupt_saves_completed_combat(tmp_path, monkeypatch, capsys):
    import signal
    from jeuxRPG.cli import main
    path = tmp_path / "player.json"
    monkeypatch.setattr(sys, "argv", ["rpg", "--save", str(path)])
    def interrupt(seconds):
        signal.raise_signal(signal.SIGINT)
    monkeypatch.setattr("jeuxRPG.cli.time.sleep", interrupt)
    main()
    assert Adventure(path).battles == 1
    assert "interrompue" in capsys.readouterr().out


@pytest.mark.parametrize("options", [["--battles", "0"], ["--interval", "nan"], ["--interval", "-1"], ["--name", " "], ["--class", "Goblin"]])
def test_invalid_cli_options_do_not_create_save(tmp_path, monkeypatch, options):
    from jeuxRPG.cli import main
    path = tmp_path / "player.json"
    monkeypatch.setattr(sys, "argv", ["rpg", "--save", str(path), *options])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not path.exists()


def test_corrupt_save_cli_does_not_reset_player(tmp_path, monkeypatch):
    from jeuxRPG.cli import main
    path = tmp_path / "player.json"
    path.write_text("{")
    monkeypatch.setattr(sys, "argv", ["rpg", "--save", str(path), "--battles", "1"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert path.read_text() == "{"
