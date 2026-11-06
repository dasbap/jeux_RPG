import sqlite3
from contextlib import closing

import pytest

from jeuxRPG.multiplayer.schema import initialize
from scripts.freeze_turso_writes import FROZEN_FENCE, freeze, restore
from scripts.prepare_d1_import import generate_import


def test_freeze_changes_only_the_runtime_fence():
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as db:
        initialize(db)
        db.execute("INSERT INTO meta VALUES('runtime_fence','5790000000000000')")
        db.execute("INSERT INTO meta VALUES('world_state','keep')")
        assert freeze(db)["previous_fence"] == 5790000000000000
        assert db.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()[0] == str(FROZEN_FENCE)
        assert db.execute("SELECT value FROM meta WHERE key='world_state'").fetchone()[0] == "keep"
        assert freeze(db)["frozen"]
        assert not db.in_transaction
        assert not restore(db, 5790000000000000)["frozen"]
        with pytest.raises(RuntimeError):
            restore(db, 5790000000000000)


def test_final_import_resets_only_the_new_backend_fence(tmp_path):
    source = tmp_path / "source.sqlite3"
    with closing(sqlite3.connect(source, isolation_level=None)) as db:
        initialize(db)
        db.execute("INSERT INTO meta VALUES('runtime_fence',?)", (str(FROZEN_FENCE),))
        db.execute("INSERT INTO meta VALUES('world_state','keep')")
    original = source.read_bytes()
    output = tmp_path / "private.sql"
    generate_import(source, output, reset_runtime_fence=True)
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as target:
        initialize(target)
        target.executescript("BEGIN;\n" + output.read_text(encoding="utf-8") + "\nCOMMIT;")
        assert target.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()[0] == "0"
        assert target.execute("SELECT value FROM meta WHERE key='world_state'").fetchone()[0] == "keep"
    assert source.read_bytes() == original
