from functools import lru_cache


@lru_cache(maxsize=1)
def catalogue():
    from .content import DATA
    from .map_building import MOBS
    from .skill_catalog import install
    from jeuxRPG._class.res.character.class_models import playable
    identifiers = (*playable(DATA.get('templates')), *install(DATA, MOBS))
    names = {item['id']: item['name'] for item in [*DATA.get('templates', {}).get('classes', []), *DATA.get('classes', [])]}
    return [{'id': identifier, 'name': names.get(identifier, identifier)} for identifier in identifiers]
