"""
Factory pour créer le village de départ.

Ce module contient les fonctions pour générer un village de départ
complet avec tous les bâtiments. Les PNJ sont chargés depuis les
fichiers JSON dans .data/saves/npcs/
"""

from jeuxRPG._class.place.town import Town
from jeuxRPG._class.place.navigation import Navigator
from jeuxRPG._class.place.jobs.npc_loader import load_npcs_for_village
from jeuxRPG._class.res.classType import Build_type, Build_state


# Liste des PNJ du village de départ
STARTING_VILLAGE_NPCS = [
    "elara",        # Aubergiste
    "baldric",      # Forgeron
    "marco",        # Marchand
    "pere_thomas",  # Prêtre
    "maire_henri",  # Maire
    "pierre",       # Garde
    "jacques",      # Garde
]


def create_starting_village(
    name: str = "Vallon Paisible",
    load_npcs: bool = True
) -> Town:
    """
    Crée un village de départ complet.
    
    Le village contient :
    - 1 quartier central avec tous les bâtiments essentiels
    - PNJ chargés depuis .data/saves/npcs/ (si load_npcs=True)
    - Bâtiments : Auberge, Forge, Boutique, Temple, Mairie
    
    Args:
        name: Nom du village (défaut: "Vallon Paisible")
        load_npcs: Charger les PNJ depuis les fichiers JSON
    
    Returns:
        Town: Le village de départ configuré
    """
    # === Créer la ville ===
    village = Town(
        name=name,
        population=150,
        wealth=500,
        reputation=50
    )
    
    # === Créer le quartier central ===
    centre = village.create_district("Place Centrale")
    
    # === Créer les bâtiments ===
    centre.create_building(
        "L'Étoile du Voyageur",
        Build_type.INN,
        level=2,
        status=Build_state.OPERATIONAL
    )
    
    centre.create_building(
        "La Forge Ardente",
        Build_type.FORGE,
        level=1,
        status=Build_state.OPERATIONAL
    )
    
    centre.create_building(
        "Bazar du Coin",
        Build_type.SHOP,
        level=1,
        status=Build_state.OPERATIONAL
    )
    
    centre.create_building(
        "Temple de la Lumière",
        Build_type.TEMPLE,
        level=2,
        status=Build_state.OPERATIONAL
    )
    
    centre.create_building(
        "Maison du Conseil",
        Build_type.TOWN_HALL,
        level=1,
        status=Build_state.OPERATIONAL
    )
    
    # === Définir l'entrée ===
    village.set_entry_district("Place Centrale")
    
    # === Charger les PNJ depuis les fichiers JSON ===
    if load_npcs:
        npcs = load_npcs_for_village(village, STARTING_VILLAGE_NPCS)
        for npc in npcs:
            centre.add_npc(npc)
    
    return village


def create_navigator_at_village(village: Town | None = None) -> Navigator:
    """
    Crée un navigateur positionné dans le village de départ.
    
    Args:
        village: Village où spawner (créé automatiquement si None)
    
    Returns:
        Navigator: Navigateur prêt à l'emploi
    """
    if village is None:
        village = create_starting_village()
    
    navigator = Navigator()
    navigator.spawn_at(village)
    return navigator


# === Villages alternatifs ===

# Liste des PNJ pour villages alternatifs
COASTAL_VILLAGE_NPCS: list[str] = []  # À définir dans .data/saves/npcs/
MOUNTAIN_VILLAGE_NPCS: list[str] = []  # À définir dans .data/saves/npcs/


def create_coastal_village(name: str = "Port-Azur", load_npcs: bool = True) -> Town:
    """Crée un village côtier avec port."""
    village = Town(name=name, population=200, wealth=800, reputation=40)
    
    port = village.create_district("Le Port")
    port.create_building("Taverne du Marin", Build_type.INN)
    port.create_building("Les Docks", Build_type.HARBOR)
    port.create_building("Marché aux Poissons", Build_type.MARKET)
    
    village.set_entry_district("Le Port")
    
    if load_npcs and COASTAL_VILLAGE_NPCS:
        npcs = load_npcs_for_village(village, COASTAL_VILLAGE_NPCS)
        for npc in npcs:
            port.add_npc(npc)
    
    return village


def create_mountain_village(name: str = "Pic-Rocheux", load_npcs: bool = True) -> Town:
    """Crée un village de montagne avec mine."""
    village = Town(name=name, population=100, wealth=600, reputation=30)
    
    centre = village.create_district("Place de la Mine")
    centre.create_building("Auberge du Mineur", Build_type.INN)
    centre.create_building("Grande Forge", Build_type.FORGE, level=3)
    centre.create_building("Entrée de la Mine", Build_type.SHOP)
    
    village.set_entry_district("Place de la Mine")
    
    if load_npcs and MOUNTAIN_VILLAGE_NPCS:
        npcs = load_npcs_for_village(village, MOUNTAIN_VILLAGE_NPCS)
        for npc in npcs:
            centre.add_npc(npc)
    
    return village
