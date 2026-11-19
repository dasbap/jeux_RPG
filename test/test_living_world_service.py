import json
import uuid

import pytest
from test_living_world import no_network  # noqa: F401
from test_single_runtime import d1  # noqa: F401

from jeuxRPG.multiplayer.d1_client import D1Client
from jeuxRPG.multiplayer.distributed import PresenceRegistry
from jeuxRPG.multiplayer.realtime_store import RuntimeStore
from jeuxRPG.multiplayer.service import GameError, GameService


class Clock:
    ratio = 3
    value = 0

    def now(self):
        return self.value


@pytest.fixture
def game(tmp_path):
    service = GameService(
        tmp_path / "local.sqlite3",
        clock=Clock(),
        presence_registry=PresenceRegistry(),
        living_world=True,
        log_directory="-",
    )
    yield service
    service.close()


def prepare(game, name="Alice"):
    player = game.register(name, "Knight")
    session = game.command(player["token"], uuid.uuid4().hex, "tutorial")["session"]
    town = sorted(game.world_life.simulation.catalog["towns"])[0]
    party = json.loads(
        game.db.execute(
            "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
        ).fetchone()[0]
    )
    party.update(
        position=town,
        battle=None,
        mobs=[],
        mob=None,
        transit=None,
        journey=[],
        field_mode=False,
    )
    party.pop("field_map", None)
    party["gold"][player["player"]["id"]] = 1000
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(party), session["id"]),
    )
    return player, session, town


def party_of(game, session):
    return json.loads(
        game.db.execute(
            "SELECT data FROM tutorials WHERE session_id=?", (session["id"],)
        ).fetchone()[0]
    )


def test_shared_market_stock_and_idempotent_purchase(game):
    alice, session, town = prepare(game)
    bob, bob_session, _ = prepare(game, "Bob")
    offer = game.state(alice["token"])["session"]["tutorial"]["living_world"][
        "merchant"
    ]["stock"][0]
    params = {
        "session_id": session["id"],
        "revision": 0,
        "item": offer["id"],
        "quantity": 4,
        "unit_price": offer["unit_price"],
    }
    request = uuid.uuid4().hex
    game.command(alice["token"], request, "world_buy", **params)
    game.command(alice["token"], request, "world_buy", **params)
    assert (
        party_of(game, session)["gold"][alice["player"]["id"]]
        == 1000 - offer["unit_price"] * 4
    )
    seen_by_bob = game.state(bob["token"])["session"]["tutorial"]["living_world"][
        "merchant"
    ]
    assert (
        next(item for item in seen_by_bob["stock"] if item["id"] == offer["id"])[
            "quantity"
        ]
        == 1
    )
    with pytest.raises(GameError) as error:
        game.command(
            bob["token"],
            uuid.uuid4().hex,
            "world_buy",
            **{**params, "session_id": bob_session["id"], "quantity": 2},
        )
    assert error.value.code == "merchant_stock"
    assert party_of(game, bob_session)["gold"][bob["player"]["id"]] == 1000
    assert game.world_life.load(1, 0)["merchant"]["town"] == town


def test_market_rejects_remote_purchase_and_changed_price_without_spending(game):
    alice, session, town = prepare(game)
    offer = game.state(alice["token"])["session"]["tutorial"]["living_world"][
        "merchant"
    ]["stock"][0]
    params = {
        "session_id": session["id"],
        "revision": 0,
        "item": offer["id"],
        "quantity": 1,
        "unit_price": offer["unit_price"] + 1,
    }
    with pytest.raises(GameError) as error:
        game.command(alice["token"], uuid.uuid4().hex, "world_buy", **params)
    assert error.value.code == "world_price_changed"
    party = party_of(game, session)
    party["position"] = next(
        key for key in game.world_life.simulation.catalog["towns"] if key != town
    )
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(party), session["id"]),
    )
    with pytest.raises(GameError) as error:
        game.command(
            alice["token"],
            uuid.uuid4().hex,
            "world_buy",
            **{**params, "unit_price": offer["unit_price"]},
        )
    assert error.value.code == "merchant_absent"
    assert party_of(game, session)["gold"][alice["player"]["id"]] == 1000


def test_failed_receipt_rolls_back_player_currency_and_world_stock(game):
    alice, session, _ = prepare(game)
    offer = game.state(alice["token"])["session"]["tutorial"]["living_world"][
        "merchant"
    ]["stock"][0]
    before = game.db.execute(
        "SELECT value FROM meta WHERE key='world_life:1'"
    ).fetchone()[0]
    game.db.execute(
        "CREATE TEMP TRIGGER reject_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'test failure'); END"
    )
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        game.command(
            alice["token"],
            uuid.uuid4().hex,
            "world_buy",
            session_id=session["id"],
            revision=0,
            item=offer["id"],
            quantity=1,
            unit_price=offer["unit_price"],
        )
    assert party_of(game, session)["gold"][alice["player"]["id"]] == 1000
    assert (
        game.db.execute("SELECT value FROM meta WHERE key='world_life:1'").fetchone()[0]
        == before
    )
    assert game.world_life.load(1, 0)["merchant"]["stock"][offer["id"]] == 5


def test_world_moves_without_any_player_and_recovers_after_service_restart(
    game, tmp_path
):
    game.tick()
    before = game.world_life.load(1, 0)
    assert not game.runtime_presence
    game.clock.value = 8000
    for _ in range(10):
        game.tick()
    after = game.world_life.load(1, 8000)
    assert after["processed"] > before["processed"]
    assert after["towns"] != before["towns"]
    reopened = GameService(
        tmp_path / "local.sqlite3",
        clock=game.clock,
        presence_registry=PresenceRegistry(),
        living_world=True,
        log_directory="-",
    )
    try:
        reopened.tick()
        assert reopened.world_life.load(1, 8000) == after
    finally:
        reopened.close()


def test_help_is_shared_charged_once_and_checkpoints_gold(game):
    alice, session, town = prepare(game)
    game.clock.value = 7200
    game.tick()
    request = uuid.uuid4().hex
    params = {
        "session_id": session["id"],
        "revision": 0,
        "town": town,
        "kind": "defend",
    }
    game.command(alice["token"], request, "world_help", **params)
    game.command(alice["token"], request, "world_help", **params)
    assert game.world_life.load(1, 7200)["towns"][town]["raid"]["support"] == 5
    party = party_of(game, session)
    assert party["gold"][alice["player"]["id"]] == 990
    assert party["autosave_checkpoint"] > 0


def test_meta_world_calendar_uses_the_existing_fenced_snapshot_batch(d1):  # noqa: F811
    environment = {
        "RPG_RUNTIME_MODE": "single",
        "RPG_DATABASE_BACKEND": "d1",
        "RPG_D1_WORKER_URL": "https://isolated.invalid",
        "RPG_D1_SERVICE_TOKEN": "local-test-token-" * 3,
        "RPG_LIVING_WORLD": "1",
    }
    clock = Clock()
    client = D1Client(environment)
    fence, snapshot = client.claim_snapshot()
    store = RuntimeStore(environment, snapshot, clock=clock)
    try:
        store.tick()
        assert ("meta", ("world_life:1",)) in store.pending
        batch = store.pending_batch()
        store.persist(fence, batch)
        store.saved(batch)
        store.tick()
        assert ("meta", ("world_life:1",)) not in store.pending
        clock.value = 8000
        store.tick()
        assert ("meta", ("world_life:1",)) in store.pending
        batch = store.pending_batch()
        store.persist(fence, batch)
        store.saved(batch)
        durable = json.loads(store.snapshot())
    finally:
        store.close()
    restored = RuntimeStore(environment, durable, clock=clock)
    try:
        expected = json.loads(
            next(
                row["value"] for row in durable["meta"] if row["key"] == "world_life:1"
            )
        )
        assert restored.service.world_life.load(1, 8000) == expected
    finally:
        restored.close()


def test_disabled_world_preserves_the_existing_game_and_creates_no_calendar(tmp_path):
    service = GameService(
        tmp_path / "off.sqlite3",
        clock=Clock(),
        presence_registry=PresenceRegistry(),
        living_world=False,
        log_directory="-",
    )
    try:
        service.tick()
        assert service.world_life is None
        assert not service.db.execute(
            "SELECT 1 FROM meta WHERE key LIKE 'world_life:%'"
        ).fetchone()
    finally:
        service.close()


@pytest.mark.parametrize("quantity", [-1, 0, 11, True, 1.5, "1"])
def test_invalid_quantity_cannot_change_shared_stock_or_gold(game, quantity):
    alice, session, _ = prepare(game)
    before = party_of(game, session)
    offer = game.state(alice["token"])["session"]["tutorial"]["living_world"][
        "merchant"
    ]["stock"][0]
    with pytest.raises(GameError) as error:
        game.command(
            alice["token"],
            uuid.uuid4().hex,
            "world_buy",
            session_id=session["id"],
            revision=0,
            item=offer["id"],
            quantity=quantity,
            unit_price=offer["unit_price"],
        )
    assert error.value.code == "invalid_world_trade"
    assert party_of(game, session)["gold"] == before["gold"]
    assert game.world_life.load(1, 0)["merchant"]["stock"][offer["id"]] == 5


def test_physical_caravan_proximity_and_fog_are_authoritative(game):
    from jeuxRPG.multiplayer import fields, tactics

    alice, session, town = prepare(game)
    player_id = alice["player"]["id"]
    catalog = game.world_life.simulation.catalog
    anchor = catalog["maps"][town]["route"][0]
    definition = fields.MAPS[town]
    distant = next(
        [x, y]
        for y in range(1, definition["height"] - 1)
        for x in range(1, definition["width"] - 1)
        if tactics.walkable(definition, [x, y]) and tactics.distance([x, y], anchor) > 3
    )
    party = party_of(game, session)
    fields.enter(party, town, distant, 0)
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(party), session["id"]),
    )
    view = game.state(alice["token"])["session"]["tutorial"]
    assert view["field_map"] == town
    assert not view["living_world"]["can_trade"]
    explored = {tuple(point) for point in view["battle"]["explored"]}
    assert all(
        tuple(round(c) for c in actor["position"]) in explored
        for actor in view["living_world"]["nearby"]
    )
    offer = view["living_world"]["merchant"]["stock"][0]
    with pytest.raises(GameError) as error:
        game.command(
            alice["token"],
            uuid.uuid4().hex,
            "world_buy",
            session_id=session["id"],
            revision=0,
            item=offer["id"],
            quantity=1,
            unit_price=offer["unit_price"],
        )
    assert error.value.code == "world_too_far"
    party["battle"]["players"][player_id]["position"] = anchor
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(party), session["id"]),
    )
    assert game.state(alice["token"])["session"]["tutorial"]["living_world"][
        "can_trade"
    ]


def test_realm_mutations_are_isolated(game):
    alice, session, town = prepare(game)
    with game._transaction():
        untouched = json.loads(json.dumps(game.world_life.advance(2, 0)))
    game.command(
        alice["token"],
        uuid.uuid4().hex,
        "world_help",
        session_id=session["id"],
        revision=0,
        town=town,
        kind="supply",
    )
    assert game.world_life.load(2, 0) == untouched
    assert (
        game.world_life.load(1, 0)["towns"][town]["food"]
        == untouched["towns"][town]["food"] + 5
    )


def test_gold_only_help_and_calendar_checkpoint_together(d1):  # noqa: F811
    environment = {
        "RPG_RUNTIME_MODE": "single",
        "RPG_DATABASE_BACKEND": "d1",
        "RPG_D1_WORKER_URL": "https://isolated.invalid",
        "RPG_D1_SERVICE_TOKEN": "local-test-token-" * 3,
        "RPG_LIVING_WORLD": "1",
    }
    store = RuntimeStore(environment, clock=Clock())
    try:
        store.service.legacy_auth = True
        alice, session, town = prepare(store.service)
        store.capture()
        store.saved(store.pending_batch())
        store.service.command(
            alice["token"],
            uuid.uuid4().hex,
            "world_help",
            session_id=session["id"],
            revision=0,
            town=town,
            kind="supply",
        )
        store.capture(dirty_only=True)
        batch = store.pending_batch()
        assert ("meta", ("world_life:1",)) in batch
        assert ("tutorials", (session["id"],)) in batch
        party = json.loads(batch[("tutorials", (session["id"],))]["data"])
        assert party["gold"][alice["player"]["id"]] == 990
        assert any(table == "receipts" for table, _ in batch)
    finally:
        store.close()


def test_living_world_changes_survive_the_delta_protocol(game):
    from jeuxRPG.multiplayer.state_bundles import encode

    alice, _, _ = prepare(game)
    state = game.state(alice["token"])
    first = encode(state)
    key = "session/tutorial/living_world"
    assert first["bundles"][key]["towns"]
    game.clock.value = 7200
    game.tick()
    delta = encode(game.state(alice["token"]), json.dumps(first["hashes"]))
    assert delta["bundles"][key]["towns"][0]["raid"]
