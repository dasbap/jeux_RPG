import json
import random
import subprocess
import sys

import pytest

from jeuxRPG.adventure import Adventure
from jeuxRPG.adventure.catalog import Catalog, default_catalog, load_catalog
from jeuxRPG.adventure.equipment import Gear


def at(session, zone, level=None):
    session.location.zone = zone
    session.location.world = session.catalog.zones[zone].world
    if level is not None and session.player.level < level:
        total = 50 * level * (level - 1)
        current = 50 * session.player.level * (session.player.level - 1) + session.player.exp
        session.player.gain_exp(total - current)
    session._remove_overlevel_equipment()
    return session


def test_default_worlds_and_map_have_settlements_frontiers_and_pools(tmp_path):
    session = Adventure(tmp_path / "save.json")
    assert len(session.catalog.worlds) == 3
    assert session.current_zone.kind == "capital"
    for world in session.catalog.worlds:
        zones = [zone for zone in session.catalog.zones.values() if zone.world == world]
        assert {zone.kind for zone in zones} == {"capital", "village", "city", "wilderness", "fortress"}
        village = next(zone for zone in zones if zone.kind == "village")
        city = next(zone for zone in zones if zone.kind == "city")
        assert village.max_level < city.min_level
        for zone in zones:
            assert zone.max_level <= session.catalog.worlds[world].max_level
            if zone.kind == "fortress":
                assert not zone.inn and not zone.craft
                assert any(session.catalog.creatures[key].variant == "boss" for key in zone.creatures)
    assert "aube-capitale-village" in session.available_paths()
    assert "aube-montagnes-fort-est" not in session.available_paths()
    assert session.world_map()["hour"] == 8


def test_subspecies_and_boss_stats_loot_and_parent(tmp_path, monkeypatch):
    session = Adventure(tmp_path / "save.json")
    base = session.create_enemy("Goblin", 1)
    sub = session.create_enemy("GoblinForestier", 1)
    boss = session.create_enemy("RoiGobelin", 1)
    assert base.hp.value < sub.hp.value < boss.hp.value
    assert session.catalog.creatures["RoiGobelin"].parent == "Goblin"
    at(session, "aube-fort-ouest", 16)
    monkeypatch.setattr(session.rng, "choice", lambda pool: "RoiGobelin")
    monkeypatch.setattr(session.rng, "randint", lambda low, high: low)
    session.player.force.upgrade_base_value(100000)
    report = session.encounter()
    assert report["variant"] == "boss"
    assert report["outcome"] == "victory"
    assert report["loot"]["materials"]["Goblin:4:hide"] == 6


def test_combat_pool_and_levels_follow_zone(tmp_path, monkeypatch):
    session = at(Adventure(tmp_path / "save.json"), "aube-ville", 6)
    pools = []
    monkeypatch.setattr(session.rng, "choice", lambda pool: pools.append(list(pool)) or pool[0])
    report = session.encounter(max_rounds=1)
    assert pools[0] == session.current_zone.creatures
    assert report["enemy_level"] == 6


def test_craft_only_in_settlements_and_no_mutation_outside(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.inventory.add_loot("Goblin", 1, 7, 3)
    at(session, "aube-foret")
    before = session.inventory.model_dump()
    with pytest.raises(ValueError, match="ateliers"):
        session.craft("Goblin:1:helmet")
    assert session.auto_craft() == []
    assert session.inventory.model_dump() == before
    at(session, "aube-village")
    assert not session.can_craft
    for key in ["aube-ville", "aube-capitale"]:
        at(session, key)
        assert session.can_craft
    identifier = session.craft("Goblin:1:helmet")
    assert identifier in session.inventory.items


def test_invalid_travel_is_atomic_and_level_gated(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.save()
    before = session.snapshot().model_dump()
    file_before = session.path.read_bytes()
    for path in ["missing", "aube-village-foret", "aube-capitale-ville"]:
        with pytest.raises(ValueError):
            session.travel(path)
        assert session.snapshot().model_dump() == before
        assert session.path.read_bytes() == file_before


def test_bidirectional_travel_persists_clock_and_rest(tmp_path, monkeypatch):
    session = Adventure(tmp_path / "save.json")
    monkeypatch.setattr(session.rng, "random", lambda: .99)
    result = session.travel("aube-capitale-village")
    assert result["arrived"] and not result["encounters"]
    assert session.location.zone == "aube-village"
    assert session.location.elapsed_hours == 10
    assert session.rest_at_inn("night") == {"rested_hours": 8, "hour": 18, "night": True}
    assert session.rest_at_inn("day") == {"rested_hours": 12, "hour": 6, "night": False}
    assert session.rest_at_inn("day")["rested_hours"] == 24
    restored = Adventure(session.path)
    assert restored.status() == session.status()
    assert restored.travel("aube-capitale-village")["arrived"]
    assert restored.location.zone == "aube-capitale"


def test_rest_requires_inn_and_valid_phase(tmp_path):
    session = Adventure(tmp_path / "save.json")
    with pytest.raises(ValueError):
        session.rest_at_inn("tomorrow")
    at(session, "aube-foret")
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match="auberge"):
        session.rest_at_inn()
    assert session.snapshot().model_dump() == before


def test_night_has_more_ambushes_and_failed_fight_prevents_arrival(tmp_path, monkeypatch):
    day = Adventure(tmp_path / "day.json")
    night = Adventure(tmp_path / "night.json")
    night.location.elapsed_hours = 18
    for session in [day, night]:
        monkeypatch.setattr(session.rng, "random", lambda: .2)
    assert day.travel("aube-capitale-village")["encounters"] == []
    monkeypatch.setattr(night, "encounter", lambda: {"outcome": "defeat"})
    result = night.travel("aube-capitale-village")
    assert len(result["encounters"]) == 1
    assert not result["arrived"]
    assert night.location.zone == "aube-capitale"
    assert Adventure(night.path).location.elapsed_hours == 19


def test_risk_changes_during_a_path_crossing_sunset(tmp_path, monkeypatch):
    session = Adventure(tmp_path / "save.json")
    session.location.elapsed_hours = 17
    monkeypatch.setattr(session.rng, "random", lambda: .2)
    monkeypatch.setattr(session, "encounter", lambda: {"outcome": "victory"})
    result = session.travel("aube-capitale-village")
    assert result["arrived"]
    assert len(result["encounters"]) == 1


def test_world_cap_preserves_real_character_and_removes_overlevel_gear(tmp_path, monkeypatch):
    session = at(Adventure(tmp_path / "save.json"), "cendres-capitale", 30)
    session.inventory.add_loot("Goblin", 5, 7, 3)
    identifier = session.craft("Goblin:5:helmet")
    assert session.inventory.items[identifier].required_level == 21
    session.equip(identifier)
    monkeypatch.setattr(session.rng, "random", lambda: .99)
    result = session.travel("portail-aube-cendres")
    assert result["arrived"]
    assert result["removed_equipment"] == [identifier]
    assert identifier in session.inventory.items
    assert not session.inventory.equipped
    assert session.player.level == 30 and session.effective_level == 20
    original_stats = session.snapshot().player.stats
    with pytest.raises(ValueError, match="maximal"):
        session.equip(identifier)
    combatant = session.combat_player()
    assert combatant.level == 20
    assert combatant.force.value < session.player.force.value
    global_rng = random.getstate()
    report = session.encounter(max_rounds=1)
    assert report["effective_level"] == 20
    assert session.player.level == 30
    assert session.snapshot().player.stats == original_stats
    assert random.getstate() == global_rng
    restored = Adventure(session.path)
    assert restored.status() == session.status()
    restored.rng.random = lambda: .99
    assert restored.travel("portail-aube-cendres")["arrived"]
    assert restored.effective_level == 30
    restored.equip(identifier)


def test_cap_does_not_leak_high_level_skills_or_modify_permanent_stats(tmp_path):
    session = at(Adventure(tmp_path / "save.json"), "aube-capitale", 40)
    canonical = Adventure(tmp_path / "reference.json")
    at(canonical, "aube-capitale", 20)
    combatant = session.combat_player()
    assert set(combatant.skills) == set(canonical.player.skills)
    for stat in ["HP", "Force", "Endurance", "Intelligence", "Sagesse"]:
        assert combatant.get_stat(stat).value == canonical.player.get_stat(stat).value
    before = session.snapshot().player
    session.encounter(max_rounds=1)
    assert session.snapshot().player == before


def test_capped_victory_keeps_effective_level_and_awards_real_xp(tmp_path):
    session = at(Adventure(tmp_path / "save.json"), "aube-capitale", 30)
    exp = session.player.exp
    report = session.encounter()
    assert report["outcome"] == "victory"
    assert report["effective_level"] == 20
    assert session.player.exp > exp
    assert session.player.level == 30


def test_auto_craft_does_not_equip_above_world_cap(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.inventory.add_loot("Goblin", 5, 7, 3)
    assert session.auto_craft() == []
    assert session.inventory.items == {}


@pytest.mark.parametrize("mutation", [
    lambda d: d["creatures"]["RoiGobelin"].update(parent="unknown"),
    lambda d: d["creatures"]["Goblin"].update(parent="RoiGobelin"),
    lambda d: d["creatures"]["RoiGobelin"].update(parent=None),
    lambda d: d["worlds"]["aube"].update(max_level=0),
    lambda d: d["worlds"]["aube"].update(entry_zone="confins-capitale"),
    lambda d: d["zones"]["aube-foret"].update(max_level=21),
    lambda d: d["zones"]["aube-foret"].update(min_level=9),
    lambda d: d["zones"]["aube-foret"].update(creatures=["unknown"]),
    lambda d: d["zones"]["aube-foret"].update(craft=True),
    lambda d: d["zones"]["aube-fort-est"].update(inn=True),
    lambda d: d["paths"]["aube-capitale-village"].update(night_risk=.1),
    lambda d: d["paths"]["aube-capitale-village"].update(destination="missing"),
    lambda d: d.update(paths={key: path for key, path in d["paths"].items() if "aube-foret" not in {path["source"], path["destination"]}}),
    lambda d: d["geography"].update(day_start=20),
    lambda d: d["geography"].update(start_world="missing"),
    lambda d: d["paths"].update(duplicate=dict(d["paths"]["aube-capitale-village"])),
])
def test_invalid_geography_and_species_fail_before_save(tmp_path, mutation):
    data = default_catalog().model_dump()
    mutation(data)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(path)
    assert not (tmp_path / "save.json").exists()


def test_missing_saved_zone_does_not_rewrite_save(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.save()
    data = json.loads(session.path.read_text(encoding="utf-8"))
    data["location"]["zone"] = "missing"
    session.path.write_text(json.dumps(data), encoding="utf-8")
    before = session.path.read_bytes()
    with pytest.raises(ValueError, match="Position"):
        Adventure(session.path)
    assert session.path.read_bytes() == before


def test_old_save_migrates_to_capital_without_losing_progression(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.save()
    data = json.loads(session.path.read_text(encoding="utf-8"))
    del data["location"]
    session.path.write_text(json.dumps(data), encoding="utf-8")
    restored = Adventure(session.path)
    assert restored.current_zone.kind == "capital"
    assert restored.snapshot().player == session.snapshot().player


def test_cli_map_travel_and_inn_are_playable(tmp_path):
    result = subprocess.run([sys.executable, "main.py", "--interactive", "--save", str(tmp_path / "save.json")],
                            input="carte\nchemins\nvoyager aube-capitale-village\nauberge nuit\npersonnage\nquitter\n",
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert '"worlds"' in result.stdout
    assert '"arrived": true' in result.stdout
    assert '"night": true' in result.stdout
    assert Adventure(tmp_path / "save.json").location.zone == "aube-village"


def test_new_world_zone_and_path_are_declared_without_engine_edits(tmp_path):
    data = default_catalog().model_dump()
    data["worlds"]["ocean"] = {"name": "Océan", "max_level": 5, "entry_zone": "ocean-port"}
    data["zones"]["ocean-port"] = {"name": "Port", "world": "ocean", "min_level": 1, "max_level": 5, "creatures": ["GoblinForestier"], "kind": "village", "craft": False, "inn": True}
    data["paths"]["ocean-portail"] = {"source": "aube-capitale", "destination": "ocean-port", "hours": 1, "day_risk": 0, "night_risk": .1}
    resources = tmp_path / "catalog.json"
    resources.write_text(json.dumps(data), encoding="utf-8")
    session = Adventure(tmp_path / "save.json", resources=resources)
    session.rng.random = lambda: .99
    assert session.travel("ocean-portail")["arrived"]
    assert session.level_cap == 5
    assert session.encounter()["enemy"] == "GoblinForestier"
    assert Adventure(session.path, resources=resources).location.world == "ocean"


def test_extra_resource_file_assigns_new_subspecies_to_existing_zone(tmp_path, monkeypatch):
    directory = tmp_path / "resources"
    directory.mkdir()
    (directory / "base.json").write_text(default_catalog().model_dump_json(), encoding="utf-8")
    extra = {"creatures": {"GoblinDesMarais": {"name": "Gobelin des marais", "character_class": "Goblin", "parent": "Goblin", "variant": "subspecies", "zones": ["aube-foret"], "drops": []}}}
    (directory / "marais.json").write_text(json.dumps(extra), encoding="utf-8")
    session = at(Adventure(tmp_path / "save.json", resources=directory), "aube-foret")
    pool = session.catalog.zone_creatures("aube-foret")
    assert "GoblinDesMarais" in pool
    assert "GoblinDesMarais" not in session.catalog.zone_creatures("aube-capitale")
    monkeypatch.setattr(session.rng, "choice", lambda choices: choices[-1])
    assert session.encounter()["enemy"] == "GoblinDesMarais"
    assert session.world_map()["zones"]["aube-foret"]["creatures"] == pool


def test_capped_auto_craft_does_not_corrupt_original_base_stats(tmp_path):
    session = at(Adventure(tmp_path / "save.json"), "aube-capitale", 30)
    session.inventory.add_loot("Goblin", 1, 7, 3)
    session.auto_craft()
    old_stats = session.snapshot().player.stats
    session.inventory.add_loot("Goblin", 2, 7, 3)
    report = session.encounter(auto_craft=True)
    assert report["outcome"] == "victory"
    assert report["crafted"]
    assert session.snapshot().player.stats == old_stats
    restored = Adventure(session.path)
    assert restored.status() == session.status()


def test_invalid_parent_chain_raises_value_error_not_key_error():
    data = default_catalog().model_dump()
    data["creatures"]["Goblin"].update(parent="GoblinForestier")
    data["creatures"]["GoblinForestier"].update(parent="missing")
    with pytest.raises(ValueError, match="parente"):
        Catalog.model_validate(data)


def test_capped_combat_exception_restores_original_character(tmp_path, monkeypatch):
    session = at(Adventure(tmp_path / "save.json"), "aube-capitale", 30)
    original = session.player
    before = session.snapshot().model_dump()
    def fail(*args):
        raise RuntimeError("combat interrompu")
    monkeypatch.setattr(session, "_encounter", fail)
    with pytest.raises(RuntimeError):
        session.encounter()
    assert session.player is original
    assert session.snapshot().model_dump() == before


def test_uncapped_auto_craft_applies_each_bonus_once(tmp_path):
    session = Adventure(tmp_path / "save.json")
    before = session.snapshot().player.stats
    session.inventory.add_loot("Goblin", 1, 7, 3)
    session.encounter(max_rounds=1, auto_craft=True)
    assert session.snapshot().player.stats == before
    bonuses = session.inventory.bonuses()
    for stat, amount in bonuses.items():
        assert session.player.get_stat(stat).value == before[stat] + amount
    session.encounter(max_rounds=1, auto_craft=True)
    assert session.snapshot().player.stats == before


@pytest.mark.performance
def test_capped_combat_performance_and_stable_permanent_stats(tmp_path):
    from time import perf_counter

    session = at(Adventure(tmp_path / "save.json"), "confins-capitale", 90)
    before = session.snapshot().player
    start = perf_counter()
    for _ in range(30):
        report = session.encounter(max_rounds=1)
        assert report["effective_level"] == 80
    assert perf_counter() - start < 10
    assert session.snapshot().player == before


@pytest.mark.parametrize("world", ["aube", "cendres", "confins"])
def test_world_core_is_a_mesh_with_alternative_routes(world):
    catalog = default_catalog()
    core = {key for key, zone in catalog.zones.items() if zone.world == world and zone.kind != "fortress"}
    adjacency = {key: set() for key in core}
    for path in catalog.paths.values():
        if path.source in core and path.destination in core:
            assert path.bidirectional
            adjacency[path.source].add(path.destination)
            adjacency[path.destination].add(path.source)
    assert all(len(neighbours) >= 2 for neighbours in adjacency.values())
    for blocked in core:
        remaining = core - {blocked}
        visited = {next(iter(remaining))}
        while True:
            expanded = visited | {destination for source in visited for destination in adjacency[source] if destination in remaining}
            if expanded == visited:
                break
            visited = expanded
        assert visited == remaining
    for key, zone in catalog.zones.items():
        if zone.world == world and zone.kind == "fortress":
            assert sum(key in {path.source, path.destination} for path in catalog.paths.values()) == 1


def test_mesh_loop_is_playable_and_saved_without_teleportation(tmp_path, monkeypatch):
    session = Adventure(tmp_path / "save.json")
    monkeypatch.setattr(session.rng, "random", lambda: .99)
    for path, destination in [("aube-capitale-foret", "aube-foret"), ("aube-village-foret", "aube-village"), ("aube-capitale-village", "aube-capitale")]:
        assert path in session.available_paths()
        assert session.travel(path)["arrived"]
        assert session.location.zone == destination
        assert Adventure(session.path).location.zone == destination
    assert session.location.elapsed_hours == 15


def test_new_mesh_shortcut_keeps_zone_level_requirement(tmp_path):
    session = Adventure(tmp_path / "save.json")
    session.location.zone = "aube-village"
    before = session.snapshot().model_dump()
    assert "aube-village-montagnes" in session.available_paths()
    with pytest.raises(ValueError, match="Niveau insuffisant"):
        session.travel("aube-village-montagnes")
    assert session.snapshot().model_dump() == before
