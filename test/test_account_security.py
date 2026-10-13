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


def test_prepared_login_cannot_bypass_password_rotation():
    game = service()
    try:
        created = game.account_login('prepared', 'old-password-123', signup=True)
        prepared = game.prepare_account_login('prepared', 'old-password-123')
        changed = game.account_change_password(created['token'], 'old-password-123', 'new-password-456')
        with pytest.raises(GameError) as failure:
            game.account_login('prepared', 'old-password-123', _prepared=prepared)
        assert failure.value.code == 'unauthorized'
        assert len(game.account_sessions(changed['token'])['sessions']) == 1
    finally:
        game.close()


def test_prepared_login_respects_suspension_without_creating_session():
    game = service()
    try:
        created = game.account_login('suspended', 'password-12345', signup=True)
        prepared = game.prepare_account_login('suspended', 'password-12345')
        count = game.db.execute('SELECT COUNT(*) FROM account_sessions').fetchone()[0]
        game.db.execute('UPDATE accounts SET suspended=1 WHERE id=?', (created['account']['id'],))
        with pytest.raises(GameError) as failure:
            game.account_login('suspended', 'password-12345', _prepared=prepared)
        assert failure.value.code == 'account_suspended'
        assert game.db.execute('SELECT COUNT(*) FROM account_sessions').fetchone()[0] == count
    finally:
        game.close()


@pytest.mark.parametrize('token', [None, 42, '', 'a' * 129, 'x' * 32])
def test_invalid_or_unknown_account_token_never_authorizes(token):
    game = service()
    try:
        with pytest.raises(GameError) as failure:
            game.account_view(token)
        assert failure.value.code == 'unauthorized' and failure.value.status == 401
    finally:
        game.close()
