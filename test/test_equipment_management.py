from copy import deepcopy

import pytest
from test_tutorial import command, reach_forge
from test_tutorial import game as tutorial_game

from jeuxRPG.multiplayer import forge, tutorial
from jeuxRPG.multiplayer.service import GameError

game = tutorial_game


@pytest.fixture
def equipped(monkeypatch):
    monkeypatch.setattr(forge, "rosee_unlocked", lambda *args: True)
    recipes = deepcopy(forge.RECIPES)
    recipes["replacement_veste"] = {**recipes["veste"], "name": "Veste de rechange"}
    monkeypatch.setattr(forge, "RECIPES", recipes)
    monkeypatch.setattr(forge, "GAMEPLAY", {**forge.GAMEPLAY, "recipes": recipes})
    party = tutorial.new_party([{"id": "p", "name": "Test", "class_name": "Knight"}])
    party.update(position="forge", battle=None, transit=None)
    party["inventory"]["p"] = {
        key: 10000 for recipe in forge.RECIPES.values() for key in recipe["cost"]
    }
    forge.execute(party, "p", "craft", "veste", GameError)
    return party


def test_remove_and_restore_preserve_item_level_and_recalculate_stats_without_healing(
    equipped,
):
    party = equipped
    forge.execute(party, "p", "upgrade", "veste", GameError)
    piece = deepcopy(party["equipment"]["p"]["torso"])
    stats = deepcopy(party["characters"]["p"]["stats"])
    party["characters"]["p"]["stats"]["hp"]["current"] = 5
    forge.change_equipment(party, "p", "unequip", "veste", GameError)
    assert "torso" not in party["equipment"]["p"]
    assert party["stored_equipment"]["p"]["veste"] == piece
    assert (
        party["characters"]["p"]["stats"]["hp"]["max"]
        == stats["hp"]["max"] - piece["hp"]
    )
    for _ in range(3):
        forge.change_equipment(party, "p", "equip", "veste", GameError)
        assert party["characters"]["p"]["stats"]["hp"]["current"] == 5
        forge.change_equipment(party, "p", "unequip", "veste", GameError)
    forge.change_equipment(party, "p", "equip", "veste", GameError)
    assert party["equipment"]["p"]["torso"] == piece
    assert party["stored_equipment"]["p"] == {}
    assert all(
        party["characters"]["p"]["stats"][stat]["max"] == value["max"]
        for stat, value in stats.items()
    )


def test_crafting_replacement_keeps_old_piece_and_stored_upgrade_does_not_apply_bonuses(
    equipped,
):
    party = equipped
    other = next(
        key
        for key, recipe in forge.RECIPES.items()
        if recipe["slot"] == "torso" and key != "veste"
    )
    forge.execute(party, "p", "craft", other, GameError)
    assert "veste" in party["stored_equipment"]["p"]
    before = deepcopy(party["characters"]["p"]["stats"])
    forge.execute(party, "p", "upgrade", "veste", GameError)
    assert party["stored_equipment"]["p"]["veste"]["level"] == 1
    assert party["characters"]["p"]["stats"] == before
    row = next(
        item for item in forge.catalogue(party, "p") if item["recipe"] == "veste"
    )
    assert row["equipped"] is None and row["owned"]["level"] == 1
    forge.change_equipment(party, "p", "equip", "veste", GameError)
    assert party["equipment"]["p"]["torso"]["level"] == 1
    assert other in party["stored_equipment"]["p"]


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(transit={"source": "forge"}),
        lambda p: p.update(battle={"players": {}}),
        lambda p: p["characters"]["p"]["stats"]["hp"].update(current=0),
        lambda p: p.update(
            field_map="clearing",
            battle={"players": {"p": {"casting": {"name": "Soin"}}}},
        ),
    ],
)
def test_unavailable_actions_do_not_remove_items_or_stats(equipped, change):
    change(equipped)
    before = deepcopy(equipped)
    with pytest.raises(GameError, match="hors combat"):
        forge.change_equipment(equipped, "p", "unequip", "veste", GameError)
    assert equipped == before


def test_unowned_items_and_repeated_removals_are_rejected(equipped):
    with pytest.raises(GameError, match="possédez"):
        forge.change_equipment(equipped, "p", "equip", "casque", GameError)
    forge.change_equipment(equipped, "p", "unequip", "veste", GameError)
    before = deepcopy(equipped)
    with pytest.raises(GameError, match="pas équipée"):
        forge.change_equipment(equipped, "p", "unequip", "veste", GameError)
    assert equipped == before


def test_authenticated_commands_persist_storage_and_update_player_view(game):
    player = game.register("Armurier", "Knight")
    token = player["token"]
    reach_forge(game, token)
    command(game, token, "craft", recipe="veste")
    removed = command(game, token, "unequip", recipe="veste")
    me = next(p for p in removed["tutorial"]["players"] if p["id"] == removed["me"])
    assert not me["gear"] and me["stored_gear"][0]["recipe"] == "veste"
    worn = command(game, token, "equip", recipe="veste")
    me = next(p for p in worn["tutorial"]["players"] if p["id"] == worn["me"])
    assert me["gear"][0]["recipe"] == "veste" and not me["stored_gear"]
