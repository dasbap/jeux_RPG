import sqlite3

import pytest

from jeuxRPG.multiplayer.service import GameError, GameService


def service():
    connection = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
    connection.row_factory = sqlite3.Row
    return GameService(connection=connection)


def test_password_change_rotates_token_and_revokes_old_sessions():
    game = service()
    try:
        created = game.account_login("alice", "old-password-123", signup=True)
        old_token = created["token"]
        game.account_login("alice", "old-password-123")
        assert len(game.account_sessions(old_token)["sessions"]) == 2
        changed = game.account_change_password(
            old_token, "old-password-123", "new-password-456"
        )
        new_token = changed["token"]
        with pytest.raises(GameError) as error:
            game.account_view(old_token)
        assert error.value.code == "unauthorized"
        sessions = game.account_sessions(new_token)["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        with pytest.raises(GameError):
            game.account_login("alice", "old-password-123")
        assert game.account_login("alice", "new-password-456")["token"]
    finally:
        game.close()


def test_logout_all_revokes_every_session():
    game = service()
    try:
        first = game.account_login("bob", "password-12345", signup=True)["token"]
        second = game.account_login("bob", "password-12345")["token"]
        assert game.account_logout_all(first) == {"ok": True}
        for token in (first, second):
            with pytest.raises(GameError) as error:
                game.account_view(token)
            assert error.value.code == "unauthorized"
    finally:
        game.close()
