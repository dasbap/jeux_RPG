import json

import pytest

from jeuxRPG.adventure import Adventure
from jeuxRPG.adventure.catalog import Catalog, default_catalog


def village_session(tmp_path, level, item_level=1, sets=True):
    data = default_catalog().model_dump()
    data['zones']['aube-village']['settlement_level'] = level
    data['equipment']['Goblin:helmet']['minimum_level'] = item_level
    if not sets:
        data['sets'] = {}
    path = tmp_path / 'resources.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    session = Adventure(tmp_path / 'player.json', resources=path)
    session.location.zone = 'aube-village'
    session.inventory.add_loot('Goblin', 1, 7, 3)
    return session, path


@pytest.mark.parametrize('level,item_level,allowed', [(10, 4, True), (10, 5, False), (11, 5, True), (11, 6, False), (2, 1, False), (3, 1, True)])
def test_village_craft_uses_strict_half_level_boundary(tmp_path, level, item_level, allowed):
    session, resources = village_session(tmp_path, level, item_level)
    session.save()
    before = session.snapshot().model_dump()
    file_before = session.path.read_bytes()
    assert session.status()['village_level'] == level
    assert session.status()['craft_max_level'] == (level - 1) // 2
    if allowed:
        identifier = session.craft('Goblin:1:helmet')
        assert session.inventory.items[identifier].required_level == item_level
        assert Adventure(session.path, resources=resources).status() == session.status()
    else:
        with pytest.raises(ValueError, match='strictement inférieur'):
            session.craft('Goblin:1:helmet')
        assert session.snapshot().model_dump() == before
        assert session.path.read_bytes() == file_before


@pytest.mark.parametrize('sets', [True, False])
def test_auto_craft_filters_full_sets_and_individual_recipes(tmp_path, sets):
    session, _ = village_session(tmp_path, 12, sets=sets)
    session.inventory.add_loot('Goblin', 2, 7, 3)
    before = {key: amount for key, amount in session.inventory.materials.items() if ':2:' in key}
    crafted = session.auto_craft()
    assert len(crafted) == 3
    assert all(session.inventory.items[key].required_level < 6 for key in crafted)
    assert {key: amount for key, amount in session.inventory.materials.items() if ':2:' in key} == before


def test_founded_village_and_legacy_settlement_use_site_level(tmp_path):
    session = Adventure(tmp_path / 'player.json')
    session.hire('aube-worker')
    session.location.zone = 'aube-clairiere'
    session.frontier.discovered.append('aube-clairiere')
    session.inventory.add_materials({'Land:1:wood': 30, 'Land:1:stone': 30})
    session.establish_camp('Sources')
    session.upgrade_village()
    assert session.village_level == 5 and session.craft_max_level == 2
    session.inventory.add_loot('Goblin', 1, 7, 3)
    session.inventory.add_loot('Goblin', 2, 7, 3)
    session.craft('Goblin:1:helmet')
    with pytest.raises(ValueError, match='moitié'):
        session.craft('Goblin:2:helmet')
    data = session.snapshot().model_dump()
    del data['frontier']['settlements']['aube-clairiere']['level']
    session.path.write_text(json.dumps(data), encoding='utf-8')
    restored = Adventure(session.path)
    assert restored.village_level == 5 and restored.can_craft
    with pytest.raises(ValueError, match='moitié'):
        restored.craft('Goblin:2:helmet')


def test_city_craft_is_not_limited_by_half_settlement_level(tmp_path):
    session, _ = village_session(tmp_path, 10, 5)
    session.location.zone = 'aube-capitale'
    assert session.craft('Goblin:1:helmet') in session.inventory.items
    assert session.village_level is None and session.craft_max_level is None


def test_village_level_above_world_cap_is_invalid():
    data = default_catalog().model_dump()
    data['zones']['aube-village']['settlement_level'] = 21
    with pytest.raises(ValueError, match='plafond'):
        Catalog.model_validate(data)
