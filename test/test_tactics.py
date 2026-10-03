from copy import deepcopy

import pytest

from jeuxRPG.multiplayer import forge, progression, tactics, tutorial
from jeuxRPG.multiplayer.service import GameError


def party(count=1, mobs=1, class_name="Knight"):
    data = tutorial.new_party([{"id": f"p{i}", "name": f"Joueur {i}", "class_name": class_name} for i in range(count)])
    tutorial.migrate(data, 0)
    draws = iter([0] * mobs + [1] + [.5] * mobs)
    tutorial.spawn(data, 0, lambda: next(draws), [], origin="explore")
    return data


def act(data, action, now=0, player="p0", **params):
    return tutorial.execute(data, player, action, params, now, GameError, lambda: .5)


def near(data):
    data["battle"]["players"]["p0"]["position"] = [9, 5]
    data["mobs"][0]["position"] = [9, 4]


def test_slash_consumes_ten_aura_and_simple_attack_after_global_delay():
    data = party()
    near(data)
    before = data["characters"]["p0"]["energies"][0]["current"]
    act(data, "skill", skill_name="Sword Slash", target="mob")
    assert data["characters"]["p0"]["energies"][0]["current"] == before - 10
    assert data["skill_ready"]["p0"]["Sword Slash"] == pytest.approx(1.2)
    with pytest.raises(GameError) as failure:
        act(data, "strike", now=3.59, target="mob")
    assert failure.value.code == "cooldown"
    tactics.complete_casts(data, 1.21, lambda: .5)
    act(data, "strike", now=3.6, target="mob")
    assert data["characters"]["p0"]["energies"][0]["current"] < before
    assert data["skill_ready"]["p0"]["Sword Slash"] == 1.21


def test_fractional_regeneration_accumulates_and_is_not_action_based():
    data = party()
    energy = data["characters"]["p0"]["energies"][0]
    energy["current"] = 0
    for instant in range(3, 31, 3):
        progression.resources(data, instant)
    assert 1 <= data["characters"]["p0"]["energies"][0]["current"] < energy["max"]
    progression.resources(data, 3000)
    assert data["characters"]["p0"]["energies"][0]["current"] == energy["max"]


def test_attack_and_skill_scale_without_excessive_knight_damage():
    character = tutorial.create_character({"id": "p", "name": "Knight", "class_name": "Knight"})
    low = progression.simple_damage(character)
    skill = deepcopy(character.skills["Sword Slash"])
    progression.scale_skill(character, skill)
    low_skill = skill.effects["damage"].value
    character.force.current_value = 100
    high_skill = deepcopy(character.skills["Sword Slash"])
    progression.scale_skill(character, high_skill)
    assert low < progression.simple_damage(character) <= 33
    assert low_skill < high_skill.effects["damage"].value
    assert progression.required(1) == 500
    assert progression.required(10) > progression.required(5) > progression.required(2)


def test_client_cannot_teleport_cross_cover_or_increase_range():
    data = party()
    data["battle"]["players"]["p0"]["hidden"] = False
    for route, target in [([[9, 5]], [9, 5]), ([[2, 6]], [2, 6]), ([[True, 5]], [1, 5]), ([[1, 5], [1, 4]], [1, 3])]:
        before = deepcopy(data)
        with pytest.raises(GameError) as failure:
            act(data, "battle_move", x=target[0], y=target[1], path=route)
        assert failure.value.code == "invalid_path"
        assert data == before
    with pytest.raises(GameError) as failure:
        act(data, "strike", target="mob")
    assert failure.value.code == "out_of_range"
    act(data, "battle_move", x=1, y=4, path=[[1, 5], [1, 4]])
    tactics.advance(data, 1.2, lambda: .5)
    assert data["battle"]["players"]["p0"]["position"] == [1, 5]
    tactics.advance(data, 2.4, lambda: .5)
    assert data["battle"]["players"]["p0"]["position"] == [1, 4]


def test_cover_hides_and_prevents_line_of_sight():
    data = party()
    act(data, "hide")
    unit = data["battle"]["players"]["p0"]
    enemy = data["mobs"][0]
    enemy["position"] = [3, 6]
    assert unit["hidden"]
    assert not tactics.sees(tactics.PRESETS[data["battle"]["preset"]], enemy, unit)
    assert not tactics.allowed(data, "p0", "mob", 6)
    unit["position"] = [0, 0]
    with pytest.raises(GameError) as failure:
        act(data, "hide", now=4)
    assert failure.value.code == "no_cover"


def test_hidden_coop_ally_not_focused_and_calls_interrupted_by_damage():
    data = party(count=2, mobs=2)
    near(data)
    data["battle"]["players"]["p0"]["hidden"] = False
    data["battle"]["players"]["p1"].update(position=[1, 6], hidden=True)
    data["mobs"][1]["position"] = [1, 4]
    tactics.advance(data, 0, lambda: .5)
    enemy = data["mobs"][0]
    assert enemy["target"] == "p0"
    assert enemy["calling_until"] == tactics.CALL_TIME
    act(data, "strike", target="mob")
    assert enemy["calling_until"] is None
    assert enemy["next_call"] == tactics.CALL_TIME
    tactics.advance(data, 1.2, lambda: .5)
    assert enemy["target"] != "p1"
    assert enemy["calling_until"] is None


def test_search_lasts_ten_real_seconds_then_returns_to_patrol():
    data = party()
    near(data)
    unit = data["battle"]["players"]["p0"]
    unit["hidden"] = False
    tactics.advance(data, 0, lambda: .5)
    enemy = data["mobs"][0]
    unit.update(position=[1, 6], hidden=True)
    tactics.advance(data, 1.2, lambda: .5)
    assert enemy["state"] == "search"
    assert enemy["last_known"] == [9, 5]
    assert enemy["search_until"] == pytest.approx(31.2)
    tactics.advance(data, 30, lambda: .5)
    assert enemy["state"] == "search"
    tactics.advance(data, 31.2, lambda: .5)
    assert enemy["state"] == "patrol"


def test_stunned_enemy_cannot_move_attack_or_call_and_resumes_patrol():
    data = party(mobs=2)
    enemy = data["mobs"][0]
    enemy.update(stunned_until=6, calling_until=2, windup_until=2, state="chase", target="p0")
    before = enemy["position"][:]
    hp = data["characters"]["p0"]["stats"]["hp"]["current"]
    tactics.advance(data, 3, lambda: .5)
    assert enemy["position"] == before
    assert enemy["calling_until"] is None and enemy["windup_until"] is None
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == hp
    tactics.advance(data, 6, lambda: .5)
    assert enemy["state"] == "patrol" and enemy["target"] is None


def test_skinning_requires_approach_and_only_rewards_party_once():
    data = party(count=2)
    near(data)
    for i in range(30):
        act(data, "strike", now=i * 4, target="mob")
        if not data["mobs"]:
            break
    assert not data["mobs"] and data["battle"]
    assert data["inventory"]["p0"] == {}
    with pytest.raises(GameError) as failure:
        act(data, "move", now=150, destination="rosee")
    assert failure.value.code == "in_combat"
    with pytest.raises(GameError) as failure:
        act(data, "harvest", now=150, player="p1", target="mob")
    assert failure.value.code == "too_far"
    act(data, "harvest", now=150, target="mob")
    assert data["inventory"]["p0"] == data["inventory"]["p1"] == {"peau": 1, "croc": 1}
    with pytest.raises(GameError) as failure:
        act(data, "harvest", now=154, target="mob")
    assert failure.value.code == "already_harvested"
    data["battle"]["players"]["p0"]["position"] = tactics.exit_cell(data)
    act(data, "leave_battle", now=154)
    assert data["battle"] is None


def test_rare_drops_are_rolled_once_at_death_and_zero_loot_in_training():
    for training, expected in [(False, {"peau": 1, "croc": 1, "cristal_gobelin": 1, "noyau_gobelin": 1}), (True, {})]:
        data = party()
        enemy = data["mobs"].pop()
        data["training"] = training
        tactics.defeated(data, enemy, 0, lambda: 0, [])
        assert data["battle"]["corpses"][0]["loot"] == expected


@pytest.mark.parametrize("recipe", forge.RECIPES)
def test_forge_independent_pieces_upgrade_to_ten_and_max_adjective(recipe):
    data = tutorial.new_party([{"id": "p0", "name": "Forgeron", "class_name": "Knight"}])
    tutorial.migrate(data, 0)
    data.update(quest="completed", position="forge", step="craft")
    data["inventory"]["p0"] = {key: 10000 for key in ("peau", "croc", "cristal_gobelin", "noyau_gobelin")}
    act(data, "craft", recipe=recipe)
    for level in range(1, 11):
        before = deepcopy(data["inventory"]["p0"])
        act(data, "upgrade", recipe=recipe)
        cost = forge.upgrade_cost(recipe, level)
        assert all(data["inventory"]["p0"][key] == before[key] - value for key, value in cost.items())
        assert len(data["equipment"]["p0"]) == 1
    piece = data["equipment"]["p0"][forge.RECIPES[recipe]["slot"]]
    assert piece["level"] == 10
    assert piece["name"].endswith(forge.RECIPES[recipe]["adjective"])
    before = deepcopy(data)
    with pytest.raises(GameError) as failure:
        act(data, "upgrade", recipe=recipe)
    assert failure.value.code == "max_upgrade" and data == before
    assert "cristal_gobelin" not in forge.upgrade_cost(recipe, 3)
    assert "cristal_gobelin" in forge.upgrade_cost(recipe, 4)
    assert forge.upgrade_cost(recipe, 10)["noyau_gobelin"] > forge.upgrade_cost(recipe, 8)["noyau_gobelin"]


def test_missing_rare_material_cannot_upgrade_or_change_stats():
    data = tutorial.new_party([{"id": "p0", "name": "Forgeron", "class_name": "Knight"}])
    tutorial.migrate(data, 0)
    data.update(quest="completed", position="forge")
    data["inventory"]["p0"] = {"peau": 10000, "croc": 10000}
    act(data, "craft", recipe="casque")
    for _ in range(3):
        act(data, "upgrade", recipe="casque")
    before = deepcopy(data)
    with pytest.raises(GameError) as failure:
        act(data, "upgrade", recipe="casque")
    assert failure.value.code == "missing_materials"
    assert data == before


def test_fifteen_presets_have_valid_cover_and_traversable_spawn_positions():
    assert len(tactics.PRESETS) == 15
    for preset in tactics.PRESETS.values():
        assert tactics.walkable(preset, [1, 6])
        assert tactics.path(preset, [1, 6], [9, 5])
        assert all(not tactics.walkable(preset, cover) for cover in preset["cover"])


def test_support_skill_cooldown_expires_with_time_independently_of_attack():
    data = party(class_name="Priest")
    character = tutorial.unpack(data["characters"]["p0"])
    character.gain_exp(sum(progression.required(level) for level in range(1, 5)))
    data["characters"]["p0"] = tutorial.pack(character)
    near(data)
    act(data, "skill", skill_name="Blessing", target="p0")
    assert data["skill_ready"]["p0"]["Blessing"] == 10.5
    tactics.complete_casts(data, 4.5, lambda: .5)
    act(data, "strike", now=4.5, target="mob")
    assert data["skill_ready"]["p0"]["Blessing"] == 10.5
    tutorial.advance(data, 12, lambda: .5)
    view = tutorial.view(data, "p0", 12)
    blessing = next(s for s in view["players"][0]["skills"] if s["name"] == "Blessing")
    assert blessing["cooldown"] == 0 and blessing["available"]
    assert "p0" in blessing["targets"]


def test_rescue_before_first_village_returns_to_known_safe_point():
    data = party()
    data.update(step="road", position="clearing_rosee")
    data["characters"]["p0"]["stats"]["hp"]["current"] = 0
    tutorial.advance(data, 0, lambda: .5)
    assert data["position"] == "clearing"
    assert data["step"] == "road"
    assert not data["battle"] and not data["transit"]
    world = tutorial.view(data, "p0", 0)["world"]
    assert any(route["destination"] == "rosee" for route in world["routes"])


def test_dead_ally_does_not_trigger_a_call():
    data = party(mobs=2)
    near(data)
    unit = data["battle"]["players"]["p0"]
    unit["hidden"] = False
    dead = data["mobs"].pop()
    dead["position"] = [13, 9]
    tactics.defeated(data, dead, 0, lambda: .5, [])
    enemy = data["mobs"][0]
    tactics.advance(data, 0, lambda: .5)
    assert dead["combat_id"] not in enemy["known_dead"]
    assert enemy["calling_until"] is None
    data["battle"]["corpses"][0]["position"] = [9, 3]
    enemy["calling_until"] = None
    enemy["needs_call"] = True
    tactics.advance(data, 6, lambda: .5)
    assert dead["combat_id"] in enemy["known_dead"]
    assert enemy["calling_until"] is None


def test_goblin_combat_movement_is_three_kilometres_per_hour():
    data = party()
    data["battle"]["players"]["p0"].update(position=[9, 5], hidden=False)
    enemy = data["mobs"][0]
    enemy["position"] = [5, 5]
    positions = []
    for instant in (0, 1.2, 2.4, 3.6, 4.8):
        tactics.advance(data, instant, lambda: .5)
        positions.append(enemy["position"][:])
    assert positions == [[5, 5], [5, 5], [5, 4], [5, 4], [6, 4]]
    assert tactics.GOBLIN_MOVE_TIME == 2 * tactics.MOVE_TIME
    preset = tactics.PRESETS[data["battle"]["preset"]]
    assert preset["cell_metres"] / tactics.GOBLIN_MOVE_TIME * 3.6 == 3


def test_call_only_reaches_unalerted_allies_strictly_within_ten_tiles():
    data = party(mobs=3)
    caller, close, distant = data["mobs"]
    caller["position"] = [1, 0]
    close["position"] = [10, 0]
    distant["position"] = [11, 0]
    assert tactics.unalerted_allies(data, caller) == [close]
    close["alerted"] = True
    assert tactics.unalerted_allies(data, caller) == []
    caller["calling_until"] = 6
    tactics.advance(data, 0, lambda: .5)
    assert caller["calling_until"] is None


def test_snapshot_hides_distant_and_occluded_enemies_without_ending_combat():
    data = party()
    state = tutorial.view(data, "p0", 0)
    assert state["mobs"] == [] and state["mob"] is None
    assert state["battle"]["hostiles_alive"] == 1
    assert state["battle"]["intents"] == []
    near(data)
    assert len(tutorial.view(data, "p0", 0)["mobs"]) == 1
    data["battle"]["players"]["p0"]["position"] = [5, 5]
    data["mobs"][0]["position"] = [7, 5]
    assert tutorial.view(data, "p0", 0)["mobs"] == []
    assert not tactics.allowed(data, "p0", "mob", 6)


@pytest.mark.parametrize("preset_id", tactics.PRESETS)
@pytest.mark.parametrize("origin", ["explore", "travel"])
def test_all_group_spawns_are_walkable_and_distinct(preset_id, origin):
    data = party(mobs=5)
    zone, index = preset_id.rsplit("_", 1)
    data["position"] = {"road": "clearing_rosee", "rosee": "training"}.get(zone, zone)
    data["encounter_number"] = int(index)
    tactics.begin(data, 0, origin)
    preset = tactics.PRESETS[data["battle"]["preset"]]
    positions = [mob["position"] for mob in data["mobs"]]
    assert len({tuple(p) for p in positions}) == 5
    assert all(tactics.walkable(preset, p) for p in positions)


def test_cast_reserves_energy_and_immobilizes_until_completion():
    data = party(class_name="Mage")
    near(data)
    skill = next(iter(tutorial.unpack(data["characters"]["p0"]).skills.values()))
    before = data["mobs"][0]["stats"]["hp"]["current"]
    energy = data["characters"]["p0"]["energies"][0]["current"]
    act(data, "skill", skill_name=skill.name, target="mob")
    assert data["mobs"][0]["stats"]["hp"]["current"] == before
    assert data["characters"]["p0"]["energies"][0]["current"] == energy - skill.energie_cost
    assert tutorial.view(data, "p0", 0)["players"][0]["casting"]["remaining_seconds"] == 1.5
    with pytest.raises(GameError) as failure:
        act(data, "battle_move", now=3.7, x=8, y=5, path=[[8, 5]])
    assert failure.value.code == "casting"
    tactics.complete_casts(data, 4.5, lambda: .5)
    assert not data["battle"]["players"]["p0"].get("casting")
    assert not data["mobs"] or data["mobs"][0]["stats"]["hp"]["current"] < before


def test_enemy_damage_breaks_concentration_without_refunding_energy():
    data = party(class_name="Mage")
    near(data)
    skill = next(iter(tutorial.unpack(data["characters"]["p0"]).skills.values()))
    act(data, "skill", skill_name=skill.name, target="mob")
    enemy = data["mobs"][0]
    enemy["windup_until"] = 1
    reserved = data["characters"]["p0"]["energies"][0]["current"]
    messages = tactics.advance(data, 1.2, lambda: .5)
    assert not data["battle"]["players"]["p0"].get("casting")
    assert any("concentration brisée" in message for message in messages)
    assert data["characters"]["p0"]["energies"][0]["current"] == reserved
    hp = enemy["stats"]["hp"]["current"]
    tactics.complete_casts(data, 9, lambda: .5)
    assert enemy["stats"]["hp"]["current"] == hp


def test_physical_cast_survives_damage_and_invalidated_target_is_not_hit():
    data = party()
    near(data)
    act(data, "skill", skill_name="Sword Slash", target="mob")
    data["mobs"][0]["windup_until"] = .1
    tactics.advance(data, .2, lambda: .5)
    assert data["battle"]["players"]["p0"].get("casting")
    data["mobs"][0]["position"] = [0, 0]
    messages = tactics.complete_casts(data, 1.3, lambda: .5)
    assert any("cible devenue inaccessible" in message for message in messages)
    assert not data["battle"]["players"]["p0"].get("casting")


def test_two_visible_goblins_pursue_instead_of_calling_each_other():
    data = party(mobs=2)
    data["battle"]["players"]["p0"].update(position=[9, 6], hidden=False)
    data["mobs"][0]["position"] = [9, 2]
    data["mobs"][1]["position"] = [10, 3]
    before = [mob["position"][:] for mob in data["mobs"]]
    tactics.advance(data, 2.4, lambda: .5)
    assert all(mob["calling_until"] is None for mob in data["mobs"])
    assert all(mob["state"] == "chase" for mob in data["mobs"])
    assert any(mob["position"] != p for mob, p in zip(data["mobs"], before))


def test_ranged_attack_records_source_and_enemy_can_detect_at_player_range():
    data = party(class_name="Mage")
    data["battle"]["players"]["p0"].update(position=[3, 8], hidden=True)
    mob = data["mobs"][0]
    mob["position"] = [9, 8]
    act(data, "strike", target="mob")
    assert mob["target"] == "p0" and mob["state"] == "chase"
    data["battle"]["players"]["p0"]["position"] = [1, 0]
    tactics.damaged(data, mob, "p0", 4)
    assert mob["last_known"] == [1, 0] and mob["state"] == "search"
    assert mob["search_until"] == 34
    tactics.advance(data, 34, lambda: .5)
    assert mob["state"] == "patrol"


def test_patrol_paths_cover_large_walkable_area():
    for preset in tactics.PRESETS.values():
        route = tactics.patrol_route(preset, 0)
        assert all(tactics.walkable(preset, p) for p in route)
        assert max(tactics.distance(a, b) for a in route for b in route) > 7
        assert all(tactics.path(preset, a, b) for a, b in zip(route, route[1:] + route[:1]))


def test_skeleton_exists_on_map_and_attacks_without_master_action():
    data = party(mobs=2, class_name="Necromancien")
    near(data)
    act(data, "skill", skill_name="Low Skull", target="p0")
    assert not data["battle"]["summons"]
    tactics.complete_casts(data, 6, lambda: .5)
    assert len(data["battle"]["summons"]) == 1
    summon = next(iter(data["battle"]["summons"].values()))
    assert tactics.walkable(tactics.PRESETS[data["battle"]["preset"]], summon["position"])
    summon["position"] = [9, 5]
    for mob in data["mobs"]:
        mob["position"] = [9, 4]
    weaker = data["mobs"][1]
    weaker["stats"]["hp"]["current"] = 10
    before = weaker["stats"]["hp"]["current"]
    tactics.advance(data, 6, lambda: .5)
    assert weaker["stats"]["hp"]["current"] < before
    assert data["mobs"][0]["stats"]["hp"]["current"] == 18
    assert all(key == "p0" for key in data["characters"])



def test_dead_skeleton_during_master_damage_does_not_crash_simulation():
    data = party(class_name="Necromancien")
    near(data)
    act(data, "skill", skill_name="Low Skull", target="p0")
    tactics.complete_casts(data, 6, lambda: .5)
    data["characters"]["p0"]["invocations"][0]["stats"]["hp"]["current"] = 1
    next(iter(data["battle"]["summons"].values()))["position"] = [0, 0]
    character = tutorial.unpack(data["characters"]["p0"])
    character.lose_hp(tutorial.unpack(data["mobs"][0]), 6)
    data["characters"]["p0"] = tutorial.pack(character)
    tactics.advance(data, 6, lambda: .5)
    assert not data["characters"]["p0"]["invocations"]
    assert not data["battle"]["summons"]
    assert data["characters"]["p0"]["stats"]["hp"]["current"] > 0


def test_autonomous_skeleton_damage_interrupts_an_ally_call():
    data = party(mobs=2, class_name="Necromancien")
    near(data)
    act(data, "skill", skill_name="Low Skull", target="p0")
    tactics.complete_casts(data, 6, lambda: .5)
    next(iter(data["battle"]["summons"].values()))["position"] = [9, 5]
    data["mobs"][0].update(position=[9, 4], calling_until=12)
    data["mobs"][1]["position"] = [1, 4]
    tactics.advance(data, 6, lambda: .5)
    assert data["mobs"][0]["calling_until"] is None
    assert data["mobs"][0]["next_call"] == 12



def test_restored_necromancer_with_two_skeletons_survives_small_goblin_hit():
    import json

    data = party(class_name="Necromancien")
    near(data)
    act(data, "skill", skill_name="Low Skull", target="p0")
    tactics.complete_casts(data, 6, lambda: .5)
    second = deepcopy(data["characters"]["p0"]["invocations"][0])
    second["id"] = "-1"
    data["characters"]["p0"]["invocations"].append(second)
    tactics.sync_summons(data, 6)
    for index, unit in enumerate(data["battle"]["summons"].values()):
        unit["position"] = [index, 0]
    data["mobs"][0]["windup_until"] = 6
    restored = json.loads(json.dumps(data))
    messages = tactics.advance(restored, 6, lambda: .5)
    assert any("utilise Entaille" in message for message in messages)
    assert restored["mobs"][0]["windup_until"] is None
    assert restored["mobs"][0]["next_attack"] > 6
    character = tutorial.unpack(restored["characters"]["p0"])
    character.lose_hp(tutorial.unpack(restored["mobs"][0]), 1)
    assert character.is_alive()
    assert len(character.invocations.get_all()) == 2



def summoned_party(count=1, mobs=1):
    data = party(count=count, mobs=mobs, class_name="Necromancien")
    near(data)
    act(data, "skill", skill_name="Low Skull", target="p0")
    tactics.complete_casts(data, 6, lambda: .5)
    for energy in data["characters"]["p0"]["energies"]:
        energy["current"] = energy["max"]
    return data


def control_action(data, action, now=6, player="p0", **params):
    return tutorial.execute(data, player, action, params, now, GameError, lambda: .5)


def test_shared_vision_uses_living_allies_and_summons_but_range_stays_personal():
    data = summoned_party(count=2)
    unit = next(iter(data["battle"]["summons"].values()))
    data["battle"]["players"]["p0"]["position"] = [0, 9]
    data["battle"]["players"]["p1"]["position"] = [0, 8]
    data["mobs"][0]["position"] = [12, 1]
    unit["position"] = [10, 1]
    assert len(tutorial.view(data, "p0", 6)["mobs"]) == 1
    assert len(tutorial.view(data, "p1", 6)["mobs"]) == 1
    assert not tactics.allowed(data, "p0", "mob", 6)
    data["characters"]["p0"]["invocations"] = []
    tactics.sync_summons(data, 6)
    data["battle"]["players"]["p1"]["position"] = [10, 1]
    assert len(tutorial.view(data, "p0", 6)["mobs"]) == 1
    data["characters"]["p1"]["stats"]["hp"]["current"] = 0
    assert tutorial.view(data, "p0", 6)["mobs"] == []


def test_control_owned_units_charges_with_time_and_release_charges_remaining_time():
    data = summoned_party()
    key = next(iter(data["battle"]["summons"]))
    control_action(data, "control_units", units=[key])
    actor = tutorial.unpack(data["characters"]["p0"])
    energy = actor.get_energie(type(actor.energie[0]))
    before = energy.current_value
    characters = {"p0": actor}
    tactics.charge_control(data, characters, 9, [])
    assert energy.current_value == before - 1
    assert data["control_credit"]["p0"]["Mana"] == pytest.approx(.6)
    data["characters"]["p0"] = tutorial.pack(actor)
    control_action(data, "control_units", now=10.5, units=[])
    assert data["characters"]["p0"]["energies"][0]["current"] == before - 1
    assert data["control_credit"]["p0"]["Mana"] == pytest.approx(.4)
    assert not data["battle"]["summons"][key]["controlled"]


def test_control_exhaustion_and_zero_cost_rules(monkeypatch):
    data = summoned_party()
    key = next(iter(data["battle"]["summons"]))
    control_action(data, "control_units", units=[key])
    actor = tutorial.unpack(data["characters"]["p0"])
    actor.energie[0].current_value = 0
    messages = []
    tactics.charge_control(data, {"p0": actor}, 9, messages)
    assert not data["battle"]["summons"][key]["controlled"]
    assert actor.energie[0].current_value == 0
    assert messages
    monkeypatch.setitem(tactics.CONTROL_RULES, "Squelette", {"energy": None, "per_second": 0})
    data["characters"]["p0"] = tutorial.pack(actor)
    control_action(data, "control_units", now=9, units=[key])
    tactics.charge_control(data, {"p0": actor}, 1000, [])
    assert data["battle"]["summons"][key]["controlled"]
    assert actor.energie[0].current_value == 0


@pytest.mark.parametrize("ids", [["missing"], [None], "bad", ["p0:summon:0", "p0:summon:0"]])
def test_forged_control_selection_is_rejected(ids):
    data = summoned_party()
    with pytest.raises(GameError):
        control_action(data, "control_units", units=ids)
    assert not any(unit.get("controlled") for unit in data["battle"]["summons"].values())


def test_player_cannot_control_companions_invocation():
    data = summoned_party(count=2)
    key = next(iter(data["battle"]["summons"]))
    with pytest.raises(GameError) as failure:
        control_action(data, "control_units", player="p1", units=[key])
    assert failure.value.code == "forbidden_unit"


def test_manual_move_paths_are_verified_and_group_orders_are_atomic():
    data = summoned_party()
    second = deepcopy(data["characters"]["p0"]["invocations"][0])
    second["id"] = "-1"
    data["characters"]["p0"]["invocations"].append(second)
    tactics.sync_summons(data, 6)
    keys = list(data["battle"]["summons"])
    for key in keys:
        data["battle"]["summons"][key]["position"] = [9, 5]
    control_action(data, "control_units", units=keys)
    with pytest.raises(GameError):
        control_action(data, "unit_order", units=keys, order="move", target=[8, 5], paths={keys[0]: [[8, 5]], keys[1]: [[0, 0], [8, 5]]})
    assert all(unit["order"]["type"] == "hold" for unit in data["battle"]["summons"].values())
    control_action(data, "unit_order", units=keys, order="move", target=[8, 5], paths={key: [[8, 5]] for key in keys})
    tactics.advance(data, 7.2, lambda: .5)
    assert all(unit["position"] == [8, 5] for unit in data["battle"]["summons"].values())
    assert data["battle"]["players"]["p0"]["position"] == [9, 5]


def test_manual_attack_requires_shared_visibility_and_executes_without_player_hit():
    data = summoned_party()
    key, unit = next(iter(data["battle"]["summons"].items()))
    data["battle"]["players"]["p0"]["position"] = [0, 9]
    unit["position"] = [9, 5]
    data["mobs"][0]["position"] = [9, 4]
    control_action(data, "control_units", units=[key])
    control_action(data, "unit_order", units=[key], order="attack", target="mob", paths={})
    before = data["mobs"][0]["stats"]["hp"]["current"]
    tactics.advance(data, 6, lambda: .5)
    assert data["mobs"][0]["stats"]["hp"]["current"] < before
    data["mobs"][0]["position"] = [0, 0]
    with pytest.raises(GameError) as failure:
        control_action(data, "unit_order", now=10, units=[key], order="attack", target="mob", paths={})
    assert failure.value.code == "invisible_target"


def test_snapshot_exposes_invocation_stats_and_control_cost():
    data = summoned_party()
    snapshot = tutorial.view(data, "p0", 6)
    invocation = snapshot["players"][0]["invocations"][0]
    assert set(invocation["stats"]) == {"force", "endurance", "intelligence", "sagesse"}
    assert invocation["max_hp"] >= invocation["hp"]
    assert invocation["control_cost"] == {"energy": "Mana", "per_second": .4}
    assert snapshot["battle"]["summons"][invocation["id"]]["stats"]


def test_redirect_movement_preserves_position_and_step_timer_during_cooldown():
    data = party()
    act(data, "battle_move", x=1, y=4, path=[[1, 5], [1, 4]])
    unit = data["battle"]["players"]["p0"]
    timer = unit["next_move"]
    act(data, "battle_move", now=.3, x=0, y=5, path=[[0, 6], [0, 5]])
    assert unit["position"] == [1, 6]
    assert unit["next_move"] == timer
    tactics.advance(data, timer, lambda: .5)
    assert unit["position"] == [0, 6]
    assert unit["route"] == [[0, 5]]


def test_controlled_invocation_skill_consumes_own_mana_and_casts_from_own_position():
    data = summoned_party()
    key, unit = next(iter(data["battle"]["summons"].items()))
    unit["position"] = [9, 5]
    data["mobs"][0]["position"] = [9, 4]
    data["battle"]["players"]["p0"]["position"] = [0, 9]
    control_action(data, "control_units", units=[key])
    before = data["characters"]["p0"]["invocations"][0]["energies"][0]["current"]
    control_action(data, "unit_skill", units=[key], skill_name="Sword Slash", target="mob")
    cost = next(skill["cost"] for skill in unit["skills"] if skill["name"] == "Sword Slash")
    assert data["characters"]["p0"]["invocations"][0]["energies"][0]["current"] == before - cost
    assert unit["casting"]["skill_name"] == "Sword Slash"
    hp = data["mobs"][0]["stats"]["hp"]["current"]
    actors = {player: tutorial.unpack(raw) for player, raw in data["characters"].items()}
    tactics.advance_summons(data, actors, unit["casting"]["ends_at"], lambda: .5, [])
    assert not unit.get("casting")
    assert not data["mobs"] or data["mobs"][0]["stats"]["hp"]["current"] < hp


def test_invocation_skill_cannot_use_master_skill_or_remote_target():
    data = summoned_party()
    key, unit = next(iter(data["battle"]["summons"].items()))
    control_action(data, "control_units", units=[key])
    with pytest.raises(GameError) as failure:
        control_action(data, "unit_skill", units=[key], skill_name="Low Skull", target="mob")
    assert failure.value.code == "unknown_skill"
    unit["position"] = [0, 9]
    with pytest.raises(GameError) as failure:
        control_action(data, "unit_skill", units=[key], skill_name="Sword Slash", target="mob")
    assert failure.value.code == "out_of_range"


def test_movement_does_not_start_or_extend_attack_cooldown():
    data = party()
    near(data)
    act(data, "battle_move", x=8, y=5, path=[[8, 5]])
    assert data["ready"]["p0"] == 0
    act(data, "strike", now=.1, target="mob")
    attack_ready = data["ready"]["p0"]
    act(data, "battle_move", now=.2, x=10, y=5, path=[[10, 5]])
    assert data["ready"]["p0"] == attack_ready
    assert data["battle"]["players"]["p0"]["route"] == [[10, 5]]
    with pytest.raises(GameError) as failure:
        act(data, "strike", now=.3, target="mob")
    assert failure.value.code == "cooldown"


def test_movement_cannot_bypass_casting_or_stun():
    data = party()
    near(data)
    act(data, "skill", skill_name="Sword Slash", target="mob")
    with pytest.raises(GameError) as failure:
        act(data, "battle_move", now=.1, x=8, y=5, path=[[8, 5]])
    assert failure.value.code == "casting"


def test_delayed_route_skips_only_steps_already_reached_without_teleport():
    data = party()
    data["battle"]["players"]["p0"]["hidden"] = False
    act(data, "battle_move", x=1, y=4, path=[[1, 5], [1, 4]])
    tactics.advance(data, 1.2, lambda: .5)
    unit = data["battle"]["players"]["p0"]
    assert unit["position"] == [1, 5]
    timer = unit["next_move"]
    act(data, "battle_move", now=1.3, encounter=data["encounter_number"], x=1, y=3, path=[[1, 5], [1, 4], [1, 3]])
    assert unit["position"] == [1, 5]
    assert unit["route"] == [[1, 4], [1, 3]]
    assert unit["next_move"] == timer


def test_status_seconds_follow_effect_tick_and_invocation_effects_expire():
    data = summoned_party()
    effect = {"group": "stun", "type": "STUN", "name": "Étourdi", "value": 0, "duration": 2, "stat": None}
    data["characters"]["p0"]["effects"] = [deepcopy(effect)]
    invocation = data["characters"]["p0"]["invocations"][0]
    invocation["effects"] = [deepcopy(effect)]
    key = invocation["id"]
    data["effect_at"] = {"p0": 9.6, key: 9.6}
    first = tutorial.view(data, "p0", 6)
    assert first["players"][0]["effects"][0]["remaining_seconds"] == pytest.approx(2.4)
    assert first["players"][0]["invocations"][0]["effects"][0]["remaining_seconds"] == pytest.approx(2.4)
    assert tutorial.view(data, "p0", 7.5)["players"][0]["effects"][0]["remaining_seconds"] == pytest.approx(1.9)
    tutorial.advance(data, 9.61, lambda: .5)
    assert data["characters"]["p0"]["effects"][0]["duration"] == 1
    assert data["characters"]["p0"]["invocations"][0]["effects"][0]["duration"] == 1
    tutorial.advance(data, 13.22, lambda: .5)
    assert data["characters"]["p0"]["effects"] == []
    assert data["characters"]["p0"]["invocations"][0]["effects"] == []


def test_covered_stealth_movement_is_slower_and_open_ground_reveals_player():
    data = party()
    unit = data["battle"]["players"]["p0"]
    act(data, "hide")
    act(data, "battle_move", now=3.6, x=1, y=4, path=[[1, 5], [1, 4]])
    assert unit["hidden"]
    assert unit["next_move"] == pytest.approx(3.6 + tactics.STEALTH_MOVE_TIME)
    tactics.advance(data, 4.8, lambda: .5)
    assert unit["position"] == [1, 6]
    tactics.advance(data, 6, lambda: .5)
    assert unit["position"] == [1, 5]
    assert unit["hidden"]
    tactics.advance(data, 7.21, lambda: .5)
    assert unit["position"] == [1, 4]
    assert not unit["hidden"]


def test_detection_cancels_hidden_and_cover_does_not_hide_known_position():
    data = party()
    unit = data["battle"]["players"]["p0"]
    data["mobs"][0]["position"] = [1, 5]
    messages = tactics.advance(data, 0, lambda: .5)
    assert not unit["hidden"]
    assert any("repéré" in message for message in messages)
    data["mobs"][0]["position"] = [4, 6]
    data["mobs"][0]["last_known"] = unit["position"][:]
    data["mobs"][0]["state"] = "search"
    with pytest.raises(GameError) as failure:
        act(data, "hide", now=4)
    assert failure.value.code == "still_detected"


@pytest.mark.parametrize("hidden,duration", [(False, tactics.MOVE_TIME), (True, tactics.STEALTH_MOVE_TIME)])
def test_diagonal_step_scales_time_and_cannot_finish_early(hidden, duration):
    data = party()
    unit = data["battle"]["players"]["p0"]
    unit.update(position=[0, 6], hidden=hidden)
    act(data, "battle_move", x=1, y=5, path=[[1, 5]])
    deadline = duration * 2 ** .5
    assert unit["next_move"] == pytest.approx(deadline)
    tactics.advance(data, deadline - .13, lambda: .5)
    assert unit["position"] == [0, 6]
    tactics.advance(data, deadline, lambda: .5)
    assert unit["position"] == [1, 5]
    assert unit["hidden"] == hidden


def test_diagonal_path_uses_shortest_distance_and_rejects_cover_corners():
    preset = {"width": 4, "height": 4, "cover": []}
    assert tactics.path(preset, [0, 0], [2, 2]) == [[1, 1], [2, 2]]
    preset["cover"] = [[1, 0]]
    assert not tactics.valid_step(preset, [0, 0], [1, 1])
    assert tactics.path(preset, [0, 0], [1, 1]) == [[0, 1], [1, 1]]
    data = party()
    data["battle"]["players"]["p0"]["position"] = [1, 5]
    with pytest.raises(GameError) as failure:
        act(data, "battle_move", x=2, y=7, path=[[2, 7]])
    assert failure.value.code == "invalid_path"


def test_redirecting_to_diagonal_scales_remaining_time_without_resetting_it():
    data = party()
    unit = data["battle"]["players"]["p0"]
    unit.update(position=[0, 6], hidden=False)
    act(data, "battle_move", x=0, y=5, path=[[0, 5]])
    act(data, "battle_move", now=.6, x=1, y=5, path=[[1, 5]])
    assert unit["next_move"] == pytest.approx(.6 + .6 * 2 ** .5)


@pytest.mark.parametrize("kind", ["player", "invocation", "mob"])
def test_default_health_regeneration_every_game_minute(kind):
    data = party(class_name="Necromancien")
    if kind == "invocation":
        act(data, "skill", skill_name="Low Skull", target="p0")
        tactics.complete_casts(data, 6.1, lambda: .5)
        entity = data["characters"]["p0"]["invocations"][0]
    else:
        entity = data["characters"]["p0"] if kind == "player" else data["mobs"][0]
    data["hp_regen"] = {}
    entity["stats"]["hp"].update(max=100, current=50)
    progression.resources(data, 10)
    progression.resources(data, 69.99)
    def hp():
        if kind == "invocation":
            return data["characters"]["p0"]["invocations"][0]["stats"]["hp"]["current"]
        return (data["characters"]["p0"] if kind == "player" else data["mobs"][0])["stats"]["hp"]["current"]
    assert hp() == 50
    progression.resources(data, 70)
    assert hp() == 51
    progression.resources(data, 250)
    assert hp() == 54
    progression.resources(data, 250)
    assert hp() == 54


def test_health_regeneration_preserves_fractions_caps_and_never_revives():
    data = party()
    hp = data["characters"]["p0"]["stats"]["hp"]
    hp.update(max=25, current=23)
    progression.resources(data, 0)
    progression.resources(data, 60)
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == 23
    progression.resources(data, 240)
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == 24
    progression.resources(data, 600)
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == 25
    data["characters"]["p0"]["stats"]["hp"]["current"] = 0
    data["mobs"][0]["stats"]["hp"]["current"] = 0
    progression.resources(data, 1200)
    assert data["characters"]["p0"]["stats"]["hp"]["current"] == 0
    assert data["mobs"][0]["stats"]["hp"]["current"] == 0


@pytest.mark.parametrize("enemy_position,hidden", [([5, 5], True), ([1, 4], False)])
def test_covered_hidden_movement_uses_close_detection_not_visible_range(enemy_position, hidden):
    data = party()
    unit = data["battle"]["players"]["p0"]
    enemy = data["mobs"][0]
    enemy.update(position=enemy_position, next_move=1000, needs_call=False)
    assert tactics.sight(tactics.PRESETS[data["battle"]["preset"]], enemy_position, [1, 5])
    act(data, "battle_move", x=1, y=5, path=[[1, 5]])
    tactics.advance(data, unit["next_move"], lambda: .5)
    assert unit["position"] == [1, 5]
    assert unit["hidden"] == hidden
    assert (enemy.get("target") == "p0") == (not hidden)


@pytest.mark.parametrize("recipe", forge.RECIPES)
def test_forge_piece_applies_own_stats_and_upgrades_without_duplicate_bonus(recipe):
    data = party()
    data.update(quest="completed", position="forge", step="craft", battle=None, mobs=[], mob=None)
    data["inventory"]["p0"] = {item: 10000 for item in ("peau", "croc", *forge.RARE_DROPS)}
    before = deepcopy(data["characters"]["p0"]["stats"])
    act(data, "craft", recipe=recipe)
    act(data, "upgrade", recipe=recipe)
    item = forge.piece(recipe, 1)
    for stat in forge.BONUS_STATS:
        assert data["characters"]["p0"]["stats"][stat]["max"] == before[stat]["max"] + item[stat]
    snapshot = deepcopy(data)
    forge.migrate(data)
    assert data == snapshot


def test_existing_equipment_receives_new_stats_once():
    data = party()
    old = forge.piece("casque", 4)
    for stat in ("force", "intelligence", "sagesse"):
        old.pop(stat)
    data["equipment"]["p0"] = {"head": old}
    before = data["characters"]["p0"]["stats"]["intelligence"]["max"]
    forge.migrate(data)
    assert data["characters"]["p0"]["stats"]["intelligence"]["max"] == before + 4
    snapshot = deepcopy(data)
    forge.migrate(data)
    assert data == snapshot


def test_achievement_victory_awards_only_complete_real_battle():
    from jeuxRPG.multiplayer import achievements
    data = party(mobs=2)
    assert achievements.view(data)["kills"] == 0
    first = data["mobs"].pop()
    tactics.defeated(data, first, 9, lambda: .5, [])
    assert achievements.view(data)["kills"] == 1
    assert not achievements.view(data)["titles"]
    last = data["mobs"].pop()
    tactics.defeated(data, last, 30, lambda: .5, [])
    stats = achievements.view(data)
    assert stats["kills"] == 2
    assert stats["best_seconds"] == 10
    assert {"Ombre silencieuse", "Intouchable", "Éclair de la lisière", "Contre toute attente"} <= set(stats["titles"])
    achievements.victory(data, 90)
    assert achievements.view(data) == stats


def test_achievement_training_damage_alert_and_higher_level_duel():
    from jeuxRPG.multiplayer import achievements
    data = party()
    data["battle"].update(enemy_alerted=True, damage_received=True, higher_level=True)
    last = data["mobs"].pop()
    tactics.defeated(data, last, 120, lambda: .5, [])
    assert achievements.view(data)["titles"] == ["Briseur de limites"]
    training = party()
    training["training"] = True
    last = training["mobs"].pop()
    tactics.defeated(training, last, 10, lambda: .5, [])
    assert achievements.view(training)["kills"] == 0
    assert achievements.view(training)["titles"] == []


def test_knight_simple_attack_is_stronger_and_slash_has_larger_damage_bonus():
    character = tutorial.create_character({"id": "p", "name": "Knight", "class_name": "Knight"})
    force = character.force.current_value
    assert progression.simple_damage(character) > int(2 + force * .2)
    skill = deepcopy(character.skills["Sword Slash"])
    base = skill.effects["damage"].value
    progression.scale_skill(character, skill)
    assert skill.effects["damage"].value > int(base * .55 + force * .25)
    assert skill.effects["damage"].value > progression.simple_damage(character)
    assert skill.energie_cost == 10
    data = party()
    near(data)
    before = data["mobs"][0]["stats"]["hp"]["current"]
    act(data, "strike", target="mob")
    simple = before - data["mobs"][0]["stats"]["hp"]["current"]
    other = party()
    near(other)
    before = other["mobs"][0]["stats"]["hp"]["current"]
    act(other, "skill", skill_name="Sword Slash", target="mob")
    tactics.complete_casts(other, 1.21, lambda: .5)
    slash = before - other["mobs"][0]["stats"]["hp"]["current"] if other["mobs"] else before
    assert slash > simple > 0


def test_slash_bleeding_stacks_persists_and_ticks_without_commands():
    from jeuxRPG.multiplayer import bleeding
    import json
    data = party()
    near(data)
    enemy = data["mobs"][0]
    enemy["stats"]["hp"].update(max=100, current=100)
    act(data, "skill", skill_name="Sword Slash", target="mob")
    tactics.complete_casts(data, 1.21, lambda: .5)
    assert len(enemy["bleeding"]) == 1
    bleeding.apply(enemy, "p0", 30, 2)
    restored = json.loads(json.dumps(data))
    before = restored["mobs"][0]["stats"]["hp"]["current"]
    bleeding.advance(restored, 7, lambda: .5)
    assert restored["mobs"][0]["stats"]["hp"]["current"] == before
    bleeding.advance(restored, 8, lambda: .5)
    assert restored["mobs"][0]["stats"]["hp"]["current"] < before
    assert len(restored["mobs"][0]["bleeding"]) == 2
    assert bleeding.status(restored["mobs"][0], 8)[0]["name"] == "Saignement ×2"
    viewed = tutorial.view(restored, "p0", 8)
    assert any(effect["name"] == "Saignement ×2" and effect["remaining_seconds"] > 0 for effect in viewed["mobs"][0]["effects"])
    bleeding.advance(restored, 14, lambda: .5)
    bleeding.advance(restored, 20, lambda: .5)
    assert not restored["mobs"][0]["bleeding"]


def test_bleeding_death_awards_once_and_leaves_harvestable_corpse():
    from jeuxRPG.multiplayer import bleeding
    data = party()
    mob = data["mobs"][0]
    mob["stats"]["hp"]["current"] = 1
    bleeding.apply(mob, "p0", 100, 0)
    messages = bleeding.advance(data, 6, lambda: .5)
    assert not data["mobs"]
    assert len(data["battle"]["corpses"]) == 1
    assert data["step"] == "road"
    xp = data["characters"]["p0"]["exp"]
    bleeding.advance(data, 12, lambda: .5)
    assert data["characters"]["p0"]["exp"] == xp
    assert any("saignement" in message for message in messages)


def test_exit_tile_is_walkable_on_every_preset_and_direct_escape_is_rejected():
    for preset in tactics.PRESETS.values():
        assert tactics.walkable(preset, [0, preset["height"] // 2])
    data = party()
    with pytest.raises(GameError) as failure:
        act(data, "leave_battle")
    assert failure.value.code == "not_at_exit"
    assert data["battle"] and data["mobs"]


def test_walking_to_exit_flees_living_enemies_without_victory_rewards():
    data = party(count=2, mobs=2)
    unit = data["battle"]["players"]["p0"]
    unit["hidden"] = False
    before = deepcopy(data["characters"])
    act(data, "battle_move", x=0, y=5, path=[[0, 5]])
    tactics.advance(data, unit["next_move"] - .13, lambda: .5)
    assert data["battle"]
    messages = tactics.advance(data, unit["next_move"], lambda: .5)
    assert data["battle"] is None and not data["mobs"]
    assert data["step"] == "clearing"
    assert all(data["characters"][key]["exp"] == character["exp"] for key, character in before.items())
    assert not data.get("achievements", {}).get("titles")
    assert any("fuit" in message for message in messages)


def test_exit_resumes_suspended_trip_without_blocking_after_flee():
    data = party()
    data.update(step="travel", combat_step="travel", position="rosee_brume", journey=["brume"], transit={"source":"rosee", "destination":"rosee_brume", "total":300, "remaining":100, "started_at":0, "ready_at":100, "segment":100, "hazard":True, "paused_at":0})
    unit = data["battle"]["players"]["p0"]
    unit.update(hidden=False)
    act(data, "battle_move", x=0, y=5, path=[[0, 5]])
    deadline = unit["next_move"]
    tutorial.advance(data, deadline, lambda: .999)
    assert data["battle"] is None
    assert "paused_at" not in data["transit"]
    assert data["transit"]["remaining"] == 100
    assert data["journey"] == ["brume"]


def test_cached_paths_do_not_leak_mutations_or_ignore_cover_changes():
    preset = {"width": 4, "height": 4, "cover": []}
    first = tactics.path(preset, [0, 0], [2, 2])
    first[0][0] = 99
    assert tactics.path(preset, [0, 0], [2, 2]) == [[1, 1], [2, 2]]
    preset["cover"] = [[1, 0]]
    route = tactics.path(preset, [0, 0], [2, 2])
    previous = [0, 0]
    for point in route:
        assert tactics.valid_step(preset, previous, point)
        previous = point
    assert route[0] != [1, 1]


def test_limit_breaker_remembers_starting_level_difference_and_best_victory():
    from jeuxRPG.multiplayer import achievements
    data = party()
    data["mobs"][0]["level"] = data["characters"]["p0"]["level"] + 4
    tactics.begin(data, 0, "explore")
    assert data["battle"]["level_difference"] == 4
    data["characters"]["p0"]["level"] += 1
    data["mobs"].clear()
    achievements.victory(data, 120)
    row = next(r for r in achievements.view(data)["rows"] if r["name"] == "Seul contre un ennemi de niveau supérieur")
    assert row["unlocked"]
    assert row["title"] == "Briseur de limites (+4 niveaux)"
    data["battle"].update(awarded=False, level_difference=2)
    achievements.victory(data, 150)
    assert achievements.view(data)["level_difference"] == 4
