import json
import subprocess
import sys

import pytest

from jeuxRPG.adventure import Adventure
from jeuxRPG.adventure.catalog import Catalog, default_catalog
from jeuxRPG.adventure.frontier import FrontierState, WorldSimulation


def crew(session):
    assert 'aube-worker' in session.observe()['npcs']
    assert session.hire('aube-worker') == 4
    return session


def quiet(session, monkeypatch):
    monkeypatch.setattr(session, 'encounter', lambda **kwargs: {'outcome': 'victory'})


def hidden_site(session):
    session.location.zone = 'aube-foret'
    result = session.explore('aube-rocher')
    assert result['arrived']
    assert session.location.zone == 'aube-clairiere'
    return session


def materials(session, wood=100, stone=100):
    session.inventory.add_materials({'Land:1:wood': wood, 'Land:1:stone': stone})


def test_landmarks_reveal_hidden_zones_without_roads_and_save_discovery(tmp_path):
    session = Adventure(tmp_path / 'save.json')
    assert 'aube-clairiere' not in session.world_map()['zones']
    assert not any('aube-clairiere' in {path.source, path.destination} for path in session.catalog.paths.values())
    session.travel('aube-capitale-foret')
    observation = session.observe()
    assert observation['landmarks']['aube-rocher']['destination'] == 'inconnue'
    assert observation['landmarks']['aube-rocher']['name'] == 'Grand rocher'
    assert session.explore('aube-rocher')['arrived']
    assert 'aube-clairiere' in session.world_map()['zones']
    assert 'aube-grotte' not in session.world_map()['zones']
    assert session.observe()['landmarks']['aube-source']['destination'] == 'inconnue'
    restored = Adventure(session.path)
    assert restored.frontier.model_dump() == session.frontier.model_dump()
    assert restored.explore('aube-rocher')['arrived']
    assert restored.location.zone == 'aube-foret'


def test_unseen_landmark_is_rejected_without_mutation(tmp_path):
    session = Adventure(tmp_path / 'save.json')
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match='Repère'):
        session.explore('aube-source')
    assert session.snapshot().model_dump() == before


def test_npcs_move_without_any_player_and_resume_from_disk(tmp_path):
    simulation = WorldSimulation(default_catalog())
    initial = simulation.positions()
    report = simulation.advance(4)
    assert report['before'] == initial
    assert report['after'] != initial
    path = tmp_path / 'world.json'
    simulation.save(path)
    restored = WorldSimulation.load(path, default_catalog())
    assert restored.positions() == simulation.positions()
    assert restored.advance(3) == simulation.advance(3)
    assert not (tmp_path / 'player.json').exists()


def test_world_advancement_is_independent_of_tick_batching():
    batch = WorldSimulation(default_catalog())
    steps = WorldSimulation(default_catalog())
    batch.advance(10000)
    for _ in range(100):
        steps.advance(100)
    assert steps.state.clock == batch.state.clock
    assert steps.positions() == batch.positions()


def test_travel_meets_real_npc_and_consumes_no_event_randomness(tmp_path, monkeypatch):
    session = Adventure(tmp_path / 'save.json')
    def forbidden(*args):
        raise AssertionError('Tirage aléatoire de déplacement')
    monkeypatch.setattr(session.rng, 'random', forbidden)
    before = session.rng.getstate()
    report = session.travel('aube-capitale-village')
    assert report['arrived']
    assert any(npc['id'] == 'aube-worker' for npc in report['npc_encounters'])
    assert session.rng.getstate() == before
    assert session.hire('aube-worker') == 4
    assert 'aube-worker' not in session.simulation.positions()
    with pytest.raises(ValueError):
        session.hire('aube-worker')


def test_geometric_overlap_without_temporal_crossing_does_not_trigger_meeting():
    sim = WorldSimulation(default_catalog())
    merchant = sim.catalog.npcs['aube-merchant']
    assert not sim.crossing('aube-capitale-village', 0, .5, 8, 9, merchant)
    worker = sim.catalog.npcs['aube-worker']
    assert sim.crossing('aube-capitale-village', 0, .5, 8, 9, worker)


def test_complete_camp_village_road_relay_flow_and_persistence(tmp_path, monkeypatch):
    session = crew(Adventure(tmp_path / 'save.json'))
    quiet(session, monkeypatch)
    hidden_site(session)
    gathered = session.gather()
    assert gathered == {'Land:1:wood': 4, 'Land:1:stone': 3}
    materials(session)
    before = dict(session.inventory.materials)
    camp = session.establish_camp('Passage des Sources')
    assert camp['cost']['workers'] == 2
    assert session.inventory.materials['Land:1:wood'] == before['Land:1:wood'] - 4
    assert session.frontier.settlements['aube-clairiere'].stage == 'camp'
    assert session.rest_at_camp('night')['night']
    village = session.upgrade_village()
    assert village['cost']['workers'] == 4
    assert session.current_zone.kind == 'village' and session.current_zone.inn
    assert not session.can_craft
    road = session.connect_village('aube-capitale')['path']
    assert road in session.available_paths()
    assert session.build_relay(road)['path'] == road
    result = session.travel(road, stop_at_relay=True)
    assert result['stopped_at_relay'] and not result['arrived']
    assert session.location.route == road
    assert not session.can_craft
    assert session.rest_at_inn('day')['hour'] == 6
    restored = Adventure(session.path)
    assert restored.location.model_dump() == session.location.model_dump()
    assert restored.frontier.model_dump() == session.frontier.model_dump()
    assert restored.travel(road)['arrived']
    assert restored.location.zone == 'aube-capitale'
    assert restored.travel(road)['arrived']
    assert restored.current_zone.name == 'Passage des Sources'
    assert restored.current_zone.kind == 'village'
    assert 'aube-clairiere' in restored.world_map()['settlements']


def test_new_road_is_used_by_npcs_to_visit_created_village(tmp_path, monkeypatch):
    session = crew(Adventure(tmp_path / 'save.json'))
    quiet(session, monkeypatch)
    hidden_site(session)
    materials(session)
    session.establish_camp('Carrefour')
    session.upgrade_village()
    road = session.connect_village('aube-capitale')['path']
    merchant = session.catalog.npcs['aube-merchant']
    assert road in session.simulation.itinerary(merchant)
    assert any(session.simulation.position(merchant, hour)['zone'] == 'aube-clairiere' for hour in range(8, 60))


def test_missing_labor_and_materials_are_atomic(tmp_path):
    session = Adventure(tmp_path / 'save.json')
    session.location.zone = 'aube-foret'
    materials(session)
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match='Main-d'):
        session.establish_camp('Sans ouvriers')
    assert session.snapshot().model_dump() == before
    session.location.zone = 'aube-capitale'
    crew(session)
    session.location.zone = 'aube-foret'
    session.inventory.materials.clear()
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match='Matériaux'):
        session.establish_camp('Sans matériaux')
    assert session.snapshot().model_dump() == before


def test_non_strategic_camp_cannot_become_village(tmp_path):
    session = crew(Adventure(tmp_path / 'save.json'))
    session.location.zone = 'aube-grotte'
    session.frontier.discovered.append('aube-grotte')
    materials(session)
    session.establish_camp('Abri')
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match='stratégique'):
        session.upgrade_village()
    assert session.snapshot().model_dump() == before


@pytest.mark.parametrize('destination', ['missing', 'aube-grotte', 'cendres-capitale', 'aube-clairiere'])
def test_invalid_village_connections_are_atomic(tmp_path, destination, monkeypatch):
    session = crew(Adventure(tmp_path / 'save.json'))
    quiet(session, monkeypatch)
    hidden_site(session)
    materials(session)
    session.establish_camp('Sources')
    session.upgrade_village()
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError):
        session.connect_village(destination)
    assert session.snapshot().model_dump() == before


def test_duplicate_camp_road_and_relay_are_rejected_without_cost(tmp_path, monkeypatch):
    session = crew(Adventure(tmp_path / 'save.json'))
    quiet(session, monkeypatch)
    hidden_site(session)
    materials(session)
    session.establish_camp('Sources')
    with pytest.raises(ValueError):
        session.establish_camp('Second camp')
    session.upgrade_village()
    road = session.connect_village('aube-capitale')['path']
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError, match='déjà'):
        session.connect_village('aube-capitale')
    assert session.snapshot().model_dump() == before
    session.build_relay(road)
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError):
        session.build_relay(road)
    assert session.snapshot().model_dump() == before


def test_player_loads_clock_and_activity_from_independent_world_save(tmp_path):
    world_path = tmp_path / 'world.json'
    simulation = WorldSimulation(default_catalog())
    simulation.advance(12)
    simulation.save(world_path)
    session = Adventure(tmp_path / 'player.json', world_save=world_path)
    assert session.location.elapsed_hours == 20
    session.advance_world(4)
    assert WorldSimulation.load(world_path, default_catalog()).state.clock == 24
    assert Adventure(session.path, world_save=world_path).location.elapsed_hours == 24


@pytest.mark.parametrize('mutation', [
    lambda d: d['landmarks']['aube-rocher'].update(destination='missing'),
    lambda d: d['landmarks']['aube-rocher'].update(destination='cendres-clairiere'),
    lambda d: d['sites']['aube-foret'].update(resources=[{'material': 'missing:wood', 'minimum': 1, 'maximum': 2}]),
    lambda d: d['constructions']['camp'].update(materials={'missing:wood': 2}),
    lambda d: d['frontier'].update(camp='missing'),
    lambda d: d['npcs']['aube-worker'].update(itinerary=['missing']),
    lambda d: d['npcs']['aube-worker'].update(itinerary=['aube-capitale-village']),
    lambda d: d['npcs']['aube-worker'].update(workforce=0),
    lambda d: d['patrols']['aube-nocturne-1'].update(creature='missing'),
    lambda d: d['patrols']['aube-nocturne-1'].update(level=21),
])
def test_invalid_frontier_resources_are_rejected(mutation):
    data = default_catalog().model_dump()
    mutation(data)
    with pytest.raises(ValueError):
        Catalog.model_validate(data)


@pytest.mark.parametrize('mutation', [
    lambda d: d['frontier'].update(discovered=['missing']),
    lambda d: d['frontier'].update(hired_npcs=['aube-worker']),
    lambda d: d['frontier'].update(relays=['missing']),
    lambda d: d['frontier'].update(settlements={'aube-grotte': {'name': 'Illégal', 'stage': 'village'}}, discovered=['aube-grotte']),
    lambda d: d['location'].update(route='missing', route_destination='aube-village', route_progress=1),
])
def test_invalid_saved_frontier_is_rejected_without_rewrite(tmp_path, mutation):
    session = Adventure(tmp_path / 'save.json')
    session.save()
    data = json.loads(session.path.read_text(encoding='utf-8'))
    mutation(data)
    session.path.write_text(json.dumps(data), encoding='utf-8')
    before = session.path.read_bytes()
    with pytest.raises(ValueError):
        Adventure(session.path)
    assert session.path.read_bytes() == before


def test_headless_cli_runs_without_player_file_and_is_reusable(tmp_path):
    world = tmp_path / 'world.json'
    result = subprocess.run([sys.executable, 'main.py', '--mode', 'world', '--world-save', str(world), '--ticks', '4', '--interval', '0'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert WorldSimulation.load(world, default_catalog()).state.clock == 12
    assert list(tmp_path.glob('*.json')) == [world]
    assert '"before"' in result.stdout and '"after"' in result.stdout


def test_cli_observation_exploration_and_recruitment(tmp_path):
    result = subprocess.run([sys.executable, 'main.py', '--interactive', '--save', str(tmp_path / 'player.json')],
                            input='observer\nrecruter aube-worker\nvoyager aube-capitale-foret\nobserver\nexplorer aube-rocher\nrecolter\nquitter\n',
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    session = Adventure(tmp_path / 'player.json')
    assert session.location.zone == 'aube-clairiere'
    assert session.workforce == 4
    assert session.inventory.materials['Land:1:wood'] == 4


@pytest.mark.performance
def test_long_headless_simulation_does_not_replay_each_hour():
    from time import perf_counter

    simulation = WorldSimulation(default_catalog())
    start = perf_counter()
    simulation.advance(10000000)
    assert perf_counter() - start < 2
    assert simulation.state.clock == 10000008


def test_opening_a_road_does_not_teleport_npcs(tmp_path, monkeypatch):
    session = crew(Adventure(tmp_path / 'save.json'))
    quiet(session, monkeypatch)
    hidden_site(session)
    materials(session)
    session.establish_camp('Sources')
    session.upgrade_village()
    reference = WorldSimulation(session.catalog, session.frontier.model_copy(deep=True))
    reference.advance(session.catalog.constructions['road'].hours)
    expected = reference.positions()
    session.connect_village('aube-capitale')
    assert session.simulation.positions() == expected
    merchant = session.catalog.npcs['aube-merchant']
    epochs = session.frontier.routing_history['aube-merchant']
    boundary = epochs[-1].clock
    assert session.simulation.position(merchant, boundary)['zone'] == merchant.start_zone
    assert any(session.simulation.position(merchant, hour)['zone'] == 'aube-clairiere' for hour in range(boundary, boundary + 20))


def test_no_workers_can_be_created_by_recruiting_unknown_or_merchant(tmp_path):
    session = Adventure(tmp_path / 'save.json')
    before = session.snapshot().model_dump()
    for key in ['missing', 'aube-merchant']:
        with pytest.raises(ValueError):
            session.hire(key)
        assert session.snapshot().model_dump() == before


def test_legacy_save_without_frontier_starts_simulation_at_saved_clock(tmp_path):
    session = Adventure(tmp_path / 'save.json')
    session.advance_world(12)
    data = session.snapshot().model_dump()
    del data['frontier']
    session.path.write_text(json.dumps(data), encoding='utf-8')
    restored = Adventure(session.path)
    assert restored.frontier.clock == 20
    assert restored.location.elapsed_hours == 20
    assert restored.simulation.positions() == session.simulation.positions()


def test_concurrent_world_ticks_do_not_overwrite_each_other(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / 'world.json'
    catalog = default_catalog()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: WorldSimulation.tick_file(path, catalog, 1), range(8)))
    assert WorldSimulation.load(path, catalog).state.clock == 16


def test_world_driver_keeps_player_constructions_and_player_sees_new_clock(tmp_path, monkeypatch):
    path = tmp_path / 'world.json'
    session = crew(Adventure(tmp_path / 'player.json', world_save=path))
    quiet(session, monkeypatch)
    hidden_site(session)
    materials(session)
    session.establish_camp('Sources')
    session.upgrade_village()
    road = session.connect_village('aube-capitale')['path']
    session.build_relay(road)
    before = session.frontier.clock
    WorldSimulation.tick_file(path, session.catalog, 5)
    session.observe()
    assert session.location.elapsed_hours == before + 5
    world = WorldSimulation.load(path, session.catalog)
    assert world.state.settlements['aube-clairiere'].stage == 'village'
    assert road in world.state.roads and road in world.state.relays
    session.save()
    assert WorldSimulation.load(path, session.catalog).state.clock == before + 5


def test_roads_and_routing_history_cannot_be_forged_in_save(tmp_path):
    catalog = default_catalog()
    state = FrontierState(routing_history={'missing': [{'clock': 8, 'paths': ['aube-capitale-village']}]})
    with pytest.raises(ValueError, match='Historique'):
        WorldSimulation(catalog, state)


@pytest.mark.parametrize('kwargs', [{'family': 'missing'}, {'enemy_level': True}, {'enemy_level': 0}, {'enemy_level': 1.5}])
def test_explicit_encounter_inputs_are_validated_before_world_changes(tmp_path, kwargs):
    session = Adventure(tmp_path / 'save.json')
    before = session.snapshot().model_dump()
    with pytest.raises(ValueError):
        session.encounter(**kwargs)
    assert session.snapshot().model_dump() == before
