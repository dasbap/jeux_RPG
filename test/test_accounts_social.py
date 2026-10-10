import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from jeuxRPG.multiplayer.service import GameService, GameError
from jeuxRPG.multiplayer.realtime_store import RuntimeStore


class Clock:
    ratio = 3
    def __init__(self):
        self.value = 0
    def now(self):
        return self.value


@pytest.fixture
def game(tmp_path):
    service = GameService(tmp_path / 'social.sqlite3', Clock(), random_source=lambda: .5)
    yield service
    service.close()


def account(game, name, class_name='Knight'):
    data = game.account_login(name, 'a-long-test-password', signup=True)
    selected = game.account_character(data['token'], 'create', name=name, class_name=class_name)
    return {**data, 'player_id': selected['selected']}


def start(game, account, field=False):
    return game.command(account['token'], uuid.uuid4().hex, 'tutorial', field_mode=field)['session']['id']


def party(game, session, **changes):
    value = json.loads(game.db.execute('SELECT data FROM tutorials WHERE session_id=?', (session,)).fetchone()[0])
    value.update(changes)
    game.db.execute('UPDATE tutorials SET data=? WHERE session_id=?', (json.dumps(value), session))
    game.record_party_locations(value)
    return value


def invite(game, sender, target):
    game.social_action(sender['token'], 'team_invite', {'username': target['account']['username']})
    return game.social_view(target['token'])['invitations'][-1]['id']


def team(game, members):
    for target in members[1:]:
        identifier = invite(game, members[0], target)
        game.social_action(target['token'], 'team_accept', {'invite_id': identifier})


def guild_invite(game, owner, target):
    game.social_action(owner['token'], 'guild_invite', {'username': target['account']['username']})
    return game.social_view(target['token'])['guild_invitations'][-1]['id']


def test_guild_create_invite_permissions_kick_and_unique_name(game):
    alice,bob,eve = [account(game,name) for name in ('AliceGuild','BobGuild','EveGuild')]
    created = game.social_action(alice['token'],'guild_create',{'name':'Gardiens de Rosée'})
    assert created['guild']['name'] == 'Gardiens de Rosée'
    assert created['guild']['role'] == 'owner'
    with pytest.raises(GameError) as failure:
        game.social_action(eve['token'],'guild_create',{'name':'gardiens de rosée'})
    assert failure.value.code == 'guild_exists'
    identifier = guild_invite(game,alice,bob)
    game.social_action(bob['token'],'guild_accept',{'invite_id':identifier})
    assert len(game.social_view(alice['token'])['guild']['members']) == 2
    with pytest.raises(GameError) as failure:
        game.social_action(bob['token'],'guild_invite',{'username':eve['account']['username']})
    assert failure.value.code == 'guild_owner_required'
    game.social_action(alice['token'],'guild_kick',{'account_id':bob['account']['id']})
    assert game.social_view(bob['token'])['guild'] is None


def test_guild_owner_transfer_and_capacity_are_authoritative(game, monkeypatch):
    from jeuxRPG.multiplayer import content
    settings = {**content.WORLD, 'guild_max_members': 3}
    monkeypatch.setattr(content,'WORLD',settings)
    alice,bob,carol,dave = [account(game,name) for name in ('GuildA','GuildB','GuildC','GuildD')]
    game.social_action(alice['token'],'guild_create',{'name':'Compagnie'})
    for target in (bob,carol):
        identifier = guild_invite(game,alice,target)
        game.social_action(target['token'],'guild_accept',{'invite_id':identifier})
    with pytest.raises(GameError) as failure:
        game.social_action(alice['token'],'guild_invite',{'username':dave['account']['username']})
    assert failure.value.code == 'guild_full'
    game.social_action(alice['token'],'guild_leave',{})
    guild = game.social_view(bob['token'])['guild']
    assert guild['owner'] == bob['account']['id']
    assert guild['role'] == 'owner'
    assert len(guild['members']) == 2


def test_guild_persists_across_runtime_restart():
    store = RuntimeStore({})
    alice,bob = [account(store.service,name) for name in ('PersistGuildA','PersistGuildB')]
    store.service.social_action(alice['token'],'guild_create',{'name':'Persistants'})
    identifier = guild_invite(store.service,alice,bob)
    store.service.social_action(bob['token'],'guild_accept',{'invite_id':identifier})
    store.capture()
    restored = RuntimeStore({},json.loads(store.snapshot()))
    try:
        view = restored.service.social_view(bob['token'])
        assert view['guild']['name'] == 'Persistants'
        assert len(view['guild']['members']) == 2
    finally:
        restored.close()
        store.close()


def test_accounts_password_sessions_and_character_ownership(game):
    alice = account(game, 'Alice')
    stored = game.db.execute('SELECT password_hash FROM accounts').fetchone()[0]
    assert stored.startswith('scrypt$') and 'a-long-test-password' not in stored
    assert alice['token'] not in str([tuple(row) for row in game.db.execute('SELECT * FROM account_sessions')])
    with pytest.raises(GameError, match='déjà utilisé'):
        game.account_login('alice', 'a-long-test-password', signup=True)
    with pytest.raises(GameError) as failure:
        game.account_login('Alice', 'another-test-password')
    assert failure.value.status == 401
    logged = game.account_login('ALICE', 'a-long-test-password')
    assert logged['account']['id'] == alice['account']['id']
    with pytest.raises(GameError) as failure:
        game.state(logged['token'])
    assert failure.value.code == 'character_required'
    game.account_character(logged['token'], 'select', player_id=alice['player_id'])
    with pytest.raises(GameError) as failure:
        game.account_character(alice['token'], 'create', name='Second', class_name='Knight')
    assert failure.value.code == 'class_exists'
    other_class = next(name for name in game.classes if name != 'Knight')
    second = game.account_character(alice['token'], 'create', name='Other', class_name=other_class)
    assert len(second['characters']) == 2
    assert game.state(logged['token'])['player']['id'] == second['selected']
    bob = account(game, 'Bob')
    with pytest.raises(GameError) as failure:
        game.account_character(bob['token'], 'select', player_id=alice['player_id'])
    assert failure.value.status == 404
    game.account_logout(alice['token'])
    with pytest.raises(GameError) as failure:
        game.state(alice['token'])
    assert failure.value.status == 401


def test_team_capacity_races_and_independent_tutorials(game):
    players = [account(game, 'user_' + str(index)) for index in range(5)]
    rooms = [start(game, player) for player in players]
    assert len(set(rooms)) == 5
    invites = [invite(game, players[0], target) for target in players[1:]]
    def accept(index):
        try:
            game.social_action(players[index]['token'], 'team_accept', {'invite_id': invites[index-1]})
            return True
        except GameError as error:
            assert error.code == 'team_full'
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        accepted = list(pool.map(accept, range(1,5)))
    assert sum(accepted) == 3
    result = game.social_view(players[0]['token'])['team']
    assert len(result['members']) == 4
    party(game, rooms[0], position='rosee', step='village', visited=['clearing','rosee'])
    assert game.state(players[1]['token'])['session']['tutorial']['position'] == 'clearing'
    assert all(game.state(player['token'])['session']['id'] == room for player, room in zip(players, rooms))
    with pytest.raises(GameError) as failure:
        game.command(players[0]['token'], uuid.uuid4().hex, 'attack', session_id=rooms[0], revision=0)
    assert failure.value.code == 'pvp_disabled'


def test_friends_invites_privacy_and_team_chat(game):
    alice, bob, outsider = [account(game, name) for name in ('Alice','Bob','Eve')]
    game.social_action(alice['token'], 'friend_add', {'username': 'bob'})
    with pytest.raises(GameError):
        game.social_action(alice['token'], 'friend_accept', {'account_id': bob['account']['id']})
    game.social_action(bob['token'], 'friend_accept', {'account_id': alice['account']['id']})
    assert game.social_view(alice['token'])['friends'][0]['username'] == 'Bob'
    identifier = invite(game, alice, bob)
    with pytest.raises(GameError):
        game.social_action(outsider['token'], 'team_accept', {'invite_id': identifier})
    game.social_action(bob['token'], 'team_accept', {'invite_id': identifier})
    for player in (alice,bob,outsider):
        start(game, player)
        game.state(player['token'])
    room = game.state(alice['token'])['session']['id']
    game.send_chat(alice['token'], 'group', 'Salut les alliés', room)
    assert game.state(bob['token'])['chat']['group'][-1]['message'] == 'Salut les alliés'
    assert not game.state(outsider['token'])['chat']['group']
    game.social_action(bob['token'], 'team_leave', {})
    assert not game.state(bob['token'])['chat']['group']
    game.social_action(alice['token'], 'friend_remove', {'account_id': bob['account']['id']})
    assert not game.social_view(bob['token'])['friends']


def test_presence_across_tutorials_capacity_and_realms(game):
    game.realm_count = 3
    players = [game.register('Player '+str(index),'Knight') for index in range(121)]
    for player in players[:120]:
        game.state(player['token'])
    assert [sum(p['realm'] == realm for p in game.runtime_presence.values()) for realm in range(1,4)] == [40,40,40]
    with pytest.raises(GameError) as failure:
        game.state(players[120]['token'])
    assert failure.value.code == 'server_full'
    first, second = players[:2]
    for player in (first,second):
        game.command(player['token'], uuid.uuid4().hex, 'tutorial', field_mode=True)
    state = game.state(first['token'])
    assert second['player']['id'] in {p['id'] for p in state['presence']['nearby']}
    assert state['presence']['nearby'][0]['map'] == 'clearing'
    game.runtime_presence[players[119]['player']['id']]['seen'] = time.monotonic() - 61
    assert game.state(players[120]['token'])['presence']['realm'] == 3
    assert len(game.runtime_presence) == 120


def test_rallies_are_optional_and_require_same_zone_outside_exploration(game):
    alice,bob = [account(game,name) for name in ('Alice','Bob')]
    rooms = [start(game,p) for p in (alice,bob)]
    team(game,[alice,bob])
    for p,room in zip((alice,bob), rooms):
        party(game,room,position='rosee',step='village',visited=['clearing','rosee'],battle=None,mobs=[],mob=None)
        game.state(p['token'])
    game.social_action(alice['token'],'rally',{'destination':'rosee'})
    rally = game.social_view(bob['token'])['rallies'][0]
    assert not game.state(bob['token'])['session']['tutorial']['moving']
    game.social_action(bob['token'],'rally_accept',{'rally_id':rally['id']})
    assert not game.state(bob['token'])['session']['tutorial']['moving']
    party(game,rooms[1],position='clearing')
    with pytest.raises(GameError):
        game.social_action(bob['token'],'rally_accept',{'rally_id':rally['id']})
    game.social_action(alice['token'],'realm',{'realm':1})
    party(game,rooms[1],position='rosee')
    game.social_action(bob['token'],'realm',{'realm':1})
    game.social_action(bob['token'],'join_ally',{'player_id':alice['player_id']})
    assert game.state(bob['token'])['session']['id'] == rooms[1]


def test_wait_on_road_does_not_resume_on_refresh_and_allows_encounters(game):
    alice,bob = [account(game,name) for name in ('Alice','Bob')]
    rooms=[start(game,p) for p in (alice,bob)]
    team(game,[alice,bob])
    for p,room in zip((alice,bob),rooms):
        party(game,room,position='rosee',step='village',visited=['clearing','rosee','lisiere'],battle=None,mobs=[],mob=None)
        game.state(p['token'])
    session = game.state(alice['token'])['session']
    game.command(alice['token'],uuid.uuid4().hex,'move',session_id=rooms[0],revision=session['revision'],destination='lisiere')
    game.clock.value += 3
    game.social_action(alice['token'],'wait',{})
    game.clock.value += 15
    game.tick()
    value=game.state(alice['token'])['session']['tutorial']
    assert value['transit']['waiting'] and not value['moving']
    game.social_action(bob['token'],'join_ally',{'player_id':alice['player_id']})
    for _ in range(20):
        game.clock.value += 1
        game.tick()
    joined=game.state(bob['token'])['session']['tutorial']
    assert joined['transit']['waiting']
    assert joined['transit']['source'] == value['transit']['source']
    assert joined['transit']['destination'] == value['transit']['destination']
    game.social_action(alice['token'],'resume',{})
    assert game.state(alice['token'])['session']['tutorial']['moving']
    assert not game.state(bob['token'])['session']['tutorial']['moving']


def test_account_and_social_persistence_does_not_save_positions(monkeypatch):
    store=RuntimeStore({})
    alice=account(store.service,'Alice');bob=account(store.service,'Bob')
    rooms=[start(store.service,p,field=True) for p in (alice,bob)]
    team(store.service,[alice,bob]);store.capture(now=100)
    assert store.due == 105
    assert any(table == 'accounts' for table,key in store.pending)
    assert any(table == 'team_members' for table,key in store.pending)
    restored=RuntimeStore({},json.loads(store.snapshot()))
    assert len(restored.service.account_view(alice['token'])['characters']) == 1
    assert len(restored.service.social_view(bob['token'])['team']['members']) == 2
    store.saved(store.pending_batch())
    for _ in range(10):
        store.service.state(alice['token'])
        store.service.state(bob['token'])
        store.capture()
    assert not store.pending
    restored.close();store.close()


def test_authorized_reset_is_atomic_once_and_keeps_new_accounts(game):
    from jeuxRPG.multiplayer.account_rollout import reset_test_players, RESET_KEY, FENCE_FLOOR
    old=account(game,'OldTest')
    start(game,old)
    game.db.execute("INSERT INTO meta VALUES('content_marker','keep')")
    assert reset_test_players(game.db)
    for table in ('players','accounts','account_sessions','tutorials','members','sessions'):
        assert game.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    assert game.db.execute("SELECT value FROM meta WHERE key='content_marker'").fetchone()[0] == 'keep'
    assert int(game.db.execute("SELECT value FROM meta WHERE key='runtime_fence'").fetchone()[0]) == FENCE_FLOOR
    fresh=account(game,'NewPlayer')
    assert not reset_test_players(game.db)
    assert game.account_view(fresh['token'])['account']['username'] == 'NewPlayer'
    assert game.db.execute('SELECT value FROM meta WHERE key=?',(RESET_KEY,)).fetchone()[0] == 'done'


def test_waiting_can_spawn_a_hostile_encounter(game):
    from jeuxRPG.multiplayer import tutorial
    player=account(game,'RoadPlayer');room=start(game,player)
    value=party(game,room,position='rosee_lisiere',step='hunt',visited=['clearing','rosee','lisiere'],battle=None,mobs=[],mob=None,
                transit={'source':'rosee','destination':'lisiere','total':600,'remaining':600,'segment':150,'started_at':0,'ready_at':150,'paused_at':1,'waiting':True,'next_encounter':10,'hazard':True})
    messages=tutorial.advance(value,11,lambda:0)
    assert value['battle'] and value['mobs']
    assert value['transit']['waiting']


def test_suspension_and_revocation_apply_to_the_account(game):
    from jeuxRPG.multiplayer.admin import update_account
    player=account(game,'Player')
    other=game.account_login('Player','a-long-test-password')
    game.account_character(other['token'],'select',player_id=player['player_id'])
    update_account(game,{'player_id':player['player_id'],'action':'suspend'})
    with pytest.raises(GameError) as failure:game.account_view(other['token'])
    assert failure.value.status == 403
    update_account(game,{'player_id':player['player_id'],'action':'restore'})
    update_account(game,{'player_id':player['player_id'],'action':'revoke'})
    for token in (player['token'],other['token']):
        with pytest.raises(GameError) as failure:game.account_view(token)
        assert failure.value.status == 401


def test_production_ticks_only_recently_active_players():
    clock=Clock()
    store=RuntimeStore({},clock=clock)
    store.service.legacy_auth=False
    alice=account(store.service,'Active');bob=account(store.service,'Offline')
    a=start(store.service,alice,field=True);b=start(store.service,bob,field=True)
    store.service.runtime_presence[bob['player_id']]['seen']=time.monotonic()-61
    before=store.db.execute('SELECT data FROM tutorials WHERE session_id=?',(b,)).fetchone()[0]
    active_before=store.db.execute('SELECT data FROM tutorials WHERE session_id=?',(a,)).fetchone()[0]
    clock.value=20
    store.tick()
    assert store.db.execute('SELECT data FROM tutorials WHERE session_id=?',(b,)).fetchone()[0] == before
    assert store.db.execute('SELECT data FROM tutorials WHERE session_id=?',(a,)).fetchone()[0] != active_before
    store.close()
