"""Create a disposable offline save beside the local verification artifacts."""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jeuxRPG.multiplayer import fields, guard_patrols  # noqa: E402
from jeuxRPG.multiplayer.browser_solo import SoloGame  # noqa: E402

game = SoloGame()
try:
    game.choose(
        {"action": "create", "name": "Test passages locaux", "class_name": "Knight"}
    )
    state = game.service.command(
        game.selected_token(), uuid.uuid4().hex, "tutorial", field_mode=True
    )["session"]
    now = game.service.clock.now()
    party = json.loads(
        game.db.execute(
            "SELECT data FROM tutorials WHERE session_id=?", (state["id"],)
        ).fetchone()[0]
    )
    fields.enter(party, "rosee", [44, 1], now)
    party.update(mobs=[], mob=None)
    preset = fields.MAPS["rosee"]
    party["battle"]["explored"] = [
        [x, y] for x in range(preset["width"]) for y in range(preset["height"])
    ]
    game.db.execute(
        "UPDATE tutorials SET data=? WHERE session_id=?",
        (json.dumps(party), state["id"]),
    )
    # Keep a real patrol on this disposable fixture's starting map. In the
    # normal world guards may currently be visiting a different district.
    life = game.service.world_life
    world = life.load(1, now)
    group_id, group = next(
        (key, g) for key, g in world["patrols"].items() if g["kind"] == "guards"
    )
    group.update(map="rosee", since=now * life.speed)
    group["squad"] = guard_patrols.create(
        group_id, life.simulation.catalog["maps"]["rosee"], fields.MAPS["rosee"], now
    )
    with game.service._transaction():
        life.save(1, world)
    target = ROOT / ".data/zone-desktop-fixture.sqlite3"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(game.save())
    print("Isolated test save prepared for local Windows zone transitions.")
finally:
    game.close()
