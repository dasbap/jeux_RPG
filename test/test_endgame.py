from copy import deepcopy
import json
import uuid

import pytest

from jeuxRPG.multiplayer import content, forge, realtime_store, state_bundles, tutorial
from jeuxRPG.multiplayer.service import GameError, GameService
from test.test_controller import project


def definition(**values):
    return {**deepcopy(content.DEFAULTS['endgame'][0]), 'min_level': 1, 'count': 2, 'reward_xp': 25, **values}


@pytest.fixture
def contracts(monkeypatch):
    items = [definition()]
    monkeypatch.setattr(content, 'DATA', {**content.DATA, 'endgame': items})
    return items


def party():
    value = tutorial.new_party([{'id': 'p', 'name': 'Vétéran', 'class_name': 'Knight'}])
    tutorial.migrate(value, 0)
    value.update(step='complete', position='forge', battle=None, mobs=[], mob=None, transit=None)
    return value


def test_contract_locks_and_matching_events(contracts):
    value = party()
    value['step'] = 'hunt'
    content.endgame_event(value, 'kill', 'goblin')
    assert content.endgame_view(value)[0]['status'] == 'locked'
    assert content.endgame_states(value)['veteran_hunt']['progress'] == 0
    with pytest.raises(GameError, match='Terminez'):
        content.claim_endgame(value, 'veteran_hunt', GameError)
    value['step'] = 'complete'
    contracts[0].update(min_level=5)
    content.endgame_event(value, 'kill', 'goblin')
    assert content.endgame_view(value)[0]['status'] == 'locked'
    contracts[0].update(min_level=1, zone='lisiere')
    content.endgame_event(value, 'kill', 'orc', 'lisiere')
    content.endgame_event(value, 'kill', 'goblin', 'rosee')
    assert content.endgame_states(value)['veteran_hunt']['progress'] == 0
    content.endgame_event(value, 'kill', 'goblin', 'lisiere')
    assert content.endgame_states(value)['veteran_hunt']['progress'] == 1


@pytest.mark.parametrize('repeatable', [True, False])
def test_reward_requires_completion_and_cannot_be_duplicated(contracts, repeatable):
    contracts[0]['repeatable'] = repeatable
    value = party()
    with pytest.raises(GameError) as failure:
        content.claim_endgame(value, 'veteran_hunt', GameError)
    assert failure.value.code == 'endgame_incomplete'
    for _ in range(4):
        content.endgame_event(value, 'kill', 'goblin')
    assert content.endgame_view(value)[0]['progress'] == 2
    before = value['characters']['p']['exp']
    content.claim_endgame(value, 'veteran_hunt', GameError)
    assert value['characters']['p']['exp'] == before + 25
    assert content.endgame_states(value)['veteran_hunt']['completions'] == 1
    with pytest.raises(GameError):
        content.claim_endgame(value, 'veteran_hunt', GameError)
    assert value['characters']['p']['exp'] == before + 25
    assert content.endgame_view(value)[0]['status'] == ('active' if repeatable else 'completed')


def test_crafting_advances_contract_and_compact_state(contracts):
    contracts[0].update(kind='craft', target='veste', count=1)
    value = party()
    value['inventory']['p'] = dict(forge.RECIPES['veste']['cost'])
    before = realtime_store.progress_signature(value)
    forge.execute(value, 'p', 'craft', 'veste', GameError)
    assert content.endgame_view(value)[0]['status'] == 'claimable'
    assert realtime_store.progress_signature(value) != before
    snapshot = tutorial.view(value, 'p', 0)
    assert state_bundles.split({'session': {'tutorial': snapshot}})['session/tutorial/endgame'][0]['status'] == 'claimable'


def test_claim_receipt_and_progress_survive_restart(tmp_path, contracts):
    database = tmp_path / 'endgame.sqlite3'
    game = GameService(database, random_source=lambda: .5)
    user = game.register('Vétéran', 'Knight')
    state = game.command(user['token'], uuid.uuid4().hex, 'tutorial')['session']
    value = json.loads(game.db.execute('SELECT data FROM tutorials WHERE session_id=?', (state['id'],)).fetchone()[0])
    value.update(step='complete', battle=None, mobs=[], mob=None, transit=None)
    for _ in range(2):
        content.endgame_event(value, 'kill', 'goblin')
    game.db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(value), state['id']))
    request = uuid.uuid4().hex
    params = {'session_id': state['id'], 'revision': state['revision'], 'challenge': 'veteran_hunt'}
    first = game.command(user['token'], request, 'endgame_claim', **params)
    assert game.command(user['token'], request, 'endgame_claim', **params) == first
    game.close()
    restored = GameService(database, random_source=lambda: .5)
    try:
        saved = json.loads(restored.db.execute('SELECT data FROM tutorials WHERE session_id=?', (state['id'],)).fetchone()[0])
        assert saved['endgame']['veteran_hunt'] == {'progress': 0, 'completions': 1, 'claimed': False}
    finally:
        restored.close()


def test_controller_migration_rename_and_invalid_reference(tmp_path, monkeypatch):
    p = project(tmp_path)
    assert p.content['endgame'] == content.DEFAULTS['endgame']
    p.rename('endgame', 'veteran_hunt', 'renamed_hunt')
    p.save()
    monkeypatch.setattr(content, 'DATA', p.content)
    value = party()
    value['endgame'] = {'veteran_hunt': {'progress': 2, 'completions': 3, 'claimed': False}}
    assert content.endgame_states(value)['renamed_hunt']['completions'] == 3
    p.content['endgame'][0]['target'] = 'unknown_species'
    with pytest.raises(ValueError, match='espèce endgame'):
        p.validate()


def test_claim_rejects_unknown_low_level_and_busy_party(contracts):
    value = party()
    with pytest.raises(GameError) as failure:
        content.claim_endgame(value, 'unknown', GameError)
    assert failure.value.code == 'unknown_endgame'
    contracts[0]['min_level'] = 5
    with pytest.raises(GameError) as failure:
        content.claim_endgame(value, 'veteran_hunt', GameError)
    assert failure.value.code == 'endgame_level'
    contracts[0]['min_level'] = 1
    for _ in range(2):
        content.endgame_event(value, 'kill', 'goblin')
    value['battle'] = {'hostiles_alive': True}
    with pytest.raises(GameError) as failure:
        content.claim_endgame(value, 'veteran_hunt', GameError)
    assert failure.value.code == 'endgame_busy'
    assert content.endgame_states(value)['veteran_hunt']['completions'] == 0


def test_defeated_creature_advances_contract_but_training_does_not(contracts):
    from jeuxRPG.multiplayer import tactics
    value = party()
    value['position'] = 'clearing'
    tutorial.spawn(value, 0, lambda: .5, [], origin='explore')
    value['step'] = 'complete'
    tactics.defeated(value, value['mobs'][0], 0, lambda: .5, [])
    assert content.endgame_states(value)['veteran_hunt']['progress'] == 1
    value['training'] = True
    tactics.defeated(value, value['mobs'][0], 0, lambda: .5, [])
    assert content.endgame_states(value)['veteran_hunt']['progress'] == 1
