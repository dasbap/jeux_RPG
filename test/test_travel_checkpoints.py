import json
from types import SimpleNamespace

from test_realtime import ENV, adventure, mutate

from jeuxRPG.multiplayer import tutorial, world
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


def test_same_zone_arrival_is_saved_and_restored_without_periodic_rewrites():
    clock = SimpleNamespace(now=lambda: 30, ratio=3)
    store = RuntimeStore(ENV, clock=clock)
    try:
        _, room = adventure(store)
        destination = world.PLACES["rosee"]["points"][0]["id"]
        assert world.zone_of(destination) == world.zone_of("rosee")

        def departing(party):
            party.update(
                position="rosee",
                step="village",
                field_mode=False,
                battle=None,
                mobs=[],
                mob=None,
                journey=[],
                transit={
                    "source": "rosee",
                    "destination": destination,
                    "total": 30,
                    "remaining": 30,
                    "segment": 30,
                    "started_at": 0,
                    "ready_at": 30,
                    "hazard": False,
                },
            )

        mutate(store, room, departing)
        store.capture()
        store.saved(store.pending_batch())
        mutate(
            store,
            room,
            lambda party: tutorial.continue_journey(party, 30, lambda: 1, []),
        )
        store.capture()
        saved = json.loads(store.pending[("tutorials", (room,))]["data"])
        assert saved["position"] == destination
        assert saved["transit"] is None
        store.saved(store.pending_batch())
        for _ in range(3):
            store.capture()
            assert not store.pending
        snapshot = json.loads(store.snapshot())
    finally:
        store.close()
    restored = RuntimeStore(ENV, snapshot, clock=clock)
    try:
        party = json.loads(
            restored.db.execute(
                "SELECT data FROM tutorials WHERE session_id=?", (room,)
            ).fetchone()[0]
        )
        assert party["position"] == destination and party["transit"] is None
    finally:
        restored.close()
