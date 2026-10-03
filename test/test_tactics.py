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
    assert data["skill_ready"]["p0"]["Sword Slash"] == 0
    with pytest.raises(GameError) as failure:
        act(data, "strike", now=3.59, target="mob")
    assert failure.value.code == "cooldown"
    act(data, "strike", now=3.6, target="mob")
    assert data["characters"]["p0"]["energies"][0]["current"] < before
    assert data["skill_ready"]["p0"]["Sword Slash"] == 0


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
    assert low < progression.simple_damage(character) <= 22
    assert low_skill < high_skill.effects["damage"].value
    assert progression.required(1) == 500
    assert progression.required(10) > progression.required(5) > progression.required(2)


def test_client_cannot_teleport_cross_cover_or_increase_range():
    data = party()
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


def test_search_lasts_three_game_minutes_then_returns_to_patrol():
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
    assert enemy["search_until"] == pytest.approx(181.2)
    tactics.advance(data, 180, lambda: .5)
    assert enemy["state"] == "search"
    tactics.advance(data, 181.2, lambda: .5)
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
    assert data["skill_ready"]["p0"]["Blessing"] == 6
    act(data, "strike", now=3.6, target="mob")
    assert data["skill_ready"]["p0"]["Blessing"] == 6
    tutorial.advance(data, 9, lambda: .5)
    view = tutorial.view(data, "p0", 9)
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


def test_dead_ally_can_be_called_until_its_body_is_seen():
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
    assert enemy["calling_until"] == 6
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
