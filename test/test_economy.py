import json
import uuid

import pytest

from jeuxRPG.multiplayer import content, economy, tutorial
from jeuxRPG.multiplayer.service import GameError, GameService


class Clock:
    ratio = 3
    def __init__(self):
        self.value = 0
    def now(self):
        return self.value


def account(game, name):
    data = game.account_login(name, "a-long-test-password", signup=True)
    selected = game.account_character(data["token"], "create", name=name, class_name="Knight")
    return {**data, "player_id": selected["selected"]}


def start(game, user):
    return game.command(user["token"], uuid.uuid4().hex, "tutorial")["session"]["id"]


def set_party(game, room, player, *, item=0, gold=100, position="rosee"):
    party = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (room,)).fetchone()[0])
    party.update(position=position, battle=None, mobs=[], mob=None, transit=None, journey=[])
    party.setdefault("inventory", {})[player] = {"peau": item}
    party.setdefault("gold", {})[player] = gold
    game.db.execute("UPDATE tutorials SET data=? WHERE session_id=?", (json.dumps(party), room))
    game.record_party_locations(party)
    return party


def team(game, owner, member):
    game.social_action(owner["token"], "team_invite", {"username": member["account"]["username"]})
    invite = game.social_view(member["token"])["invitations"][0]["id"]
    game.social_action(member["token"], "team_accept", {"invite_id": invite})


def test_merchant_buy_sell_is_conservative(monkeypatch):
    party = tutorial.new_party([{"id":"p","name":"Marchandage","class_name":"Knight"}])
    monkeypatch.setattr(content, "WORLD", {**content.WORLD, "starting_gold":100, "trade_max_quantity":99})
    monkeypatch.setattr(content, "DATA", {**content.DATA, "economy":[{"id":"peau","name":"Peau","buy":8,"sell":4}]})
    economy.migrate(party)
    merchant = {"id":"shop","name":"Marchand","merchant":True}
    assert economy.execute(party, "p", merchant, "buy", "peau", 2, GameError) == ["Achat : 2 Peau pour 16 or."]
    assert party["gold"]["p"] == 84
    assert party["inventory"]["p"]["peau"] == 2
    assert economy.execute(party, "p", merchant, "sell", "peau", 1, GameError) == ["Vente : 1 Peau pour 4 or."]
    assert party["gold"]["p"] == 88
    assert party["inventory"]["p"]["peau"] == 1


def test_merchant_rejects_invalid_or_unaffordable_transactions(monkeypatch):
    monkeypatch.setattr(content, "WORLD", {**content.WORLD, "starting_gold":3, "trade_max_quantity":2})
    party = tutorial.new_party([{"id":"p","name":"Marchandage","class_name":"Knight"}])
    monkeypatch.setattr(content, "DATA", {**content.DATA, "economy":[{"id":"peau","name":"Peau","buy":8,"sell":4}]})
    economy.migrate(party)
    merchant = {"id":"shop","name":"Marchand","merchant":True}
    before = json.dumps(party, sort_keys=True)
    with pytest.raises(GameError) as failure:
        economy.execute(party, "p", merchant, "buy", "peau", 1, GameError)
    assert failure.value.code == "missing_gold"
    assert json.dumps(party, sort_keys=True) == before
    with pytest.raises(GameError) as failure:
        economy.execute(party, "p", merchant, "buy", "peau", 3, GameError)
    assert failure.value.code == "invalid_quantity"


def test_trade_between_nearby_allies_updates_two_saves_once(tmp_path):
    game = GameService(tmp_path / "trade.sqlite3", Clock(), random_source=lambda:.5)
    try:
        alice, bob = account(game, "TradeAlice"), account(game, "TradeBob")
        aroom, broom = start(game, alice), start(game, bob)
        team(game, alice, bob)
        set_party(game, aroom, alice["player_id"], item=5, gold=100)
        set_party(game, broom, bob["player_id"], item=0, gold=10)
        game.state(alice["token"]); game.state(bob["token"])
        revision = game.state(alice["token"])["session"]["revision"]
        request_id = uuid.uuid4().hex
        params = dict(session_id=aroom, revision=revision, target_player=bob["player_id"], item="peau", quantity=2, gold=25)
        first = game.command(alice["token"], request_id, "trade", **params)
        second = game.command(alice["token"], request_id, "trade", **params)
        assert first == second
        source = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (aroom,)).fetchone()[0])
        target = json.loads(game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (broom,)).fetchone()[0])
        assert source["inventory"][alice["player_id"]]["peau"] == 3
        assert target["inventory"][bob["player_id"]]["peau"] == 2
        assert source["gold"][alice["player_id"]] == 75
        assert target["gold"][bob["player_id"]] == 35
    finally:
        game.close()


def test_trade_rejects_non_allies_and_distance_without_mutation(tmp_path):
    game = GameService(tmp_path / "trade.sqlite3", Clock(), random_source=lambda:.5)
    try:
        alice, bob = account(game, "FarAlice"), account(game, "FarBob")
        aroom, broom = start(game, alice), start(game, bob)
        set_party(game, aroom, alice["player_id"], item=5, gold=100, position="rosee")
        set_party(game, broom, bob["player_id"], item=0, gold=10, position="brume")
        game.state(alice["token"]); game.state(bob["token"])
        revision = game.state(alice["token"])["session"]["revision"]
        params = dict(session_id=aroom, revision=revision, target_player=bob["player_id"], item="peau", quantity=1, gold=0)
        before = game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (aroom,)).fetchone()[0]
        with pytest.raises(GameError) as failure:
            game.command(alice["token"], uuid.uuid4().hex, "trade", **params)
        assert failure.value.code == "trade_forbidden"
        team(game, alice, bob)
        with pytest.raises(GameError) as failure:
            game.command(alice["token"], uuid.uuid4().hex, "trade", **params)
        assert failure.value.code == "trade_distance"
        assert game.db.execute("SELECT data FROM tutorials WHERE session_id=?", (aroom,)).fetchone()[0] == before
    finally:
        game.close()
