"""
Loader pour charger les PNJ depuis les fichiers JSON.
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from jeuxRPG._class.place.jobs.job import Job
from jeuxRPG._class.place.jobs.job_types import JobType
from jeuxRPG._class.place.jobs.npc import NPC

if TYPE_CHECKING:
    from jeuxRPG._class.place.building import Building
    from jeuxRPG._class.place.town import Town


# Chemin par défaut vers les fichiers NPC
DEFAULT_NPC_PATH = Path(__file__).parent.parent.parent.parent.parent / ".data" / "saves" / "npcs"


def get_npc_path() -> Path:
    """Retourne le chemin vers le dossier des PNJ."""
    return DEFAULT_NPC_PATH


def load_npc_from_file(filepath: str | Path) -> dict:
    """
    Charge les données brutes d'un PNJ depuis un fichier JSON.
    
    Args:
        filepath: Chemin vers le fichier JSON
        
    Returns:
        dict: Données brutes du PNJ
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_npc_data(npc_id: str, npc_path: Path | None = None) -> dict | None:
    """
    Charge les données d'un PNJ par son ID.
    
    Args:
        npc_id: Identifiant du PNJ (nom du fichier sans .json)
        npc_path: Chemin personnalisé vers le dossier des PNJ
        
    Returns:
        dict | None: Données du PNJ ou None si non trouvé
    """
    path = npc_path or get_npc_path()
    filepath = path / f"{npc_id}.json"
    
    if not filepath.exists():
        return None
    
    return load_npc_from_file(filepath)


def create_npc_from_data(
    data: dict, 
    location_resolver: Callable | None = None
) -> NPC:
    """
    Crée un objet NPC à partir des données JSON.
    
    Args:
        data: Dictionnaire des données du PNJ
        location_resolver: Fonction pour résoudre la location en objet Building
                          Signature: (town: str, district: str, building: str | None) -> Building | None
    
    Returns:
        NPC: L'objet NPC créé
    """
    # Créer le Job
    job_data = data.get("job", {})
    job_type = JobType[job_data.get("type", "MERCHANT")]
    
    job = Job(
        name=job_data.get("name", data["name"]),
        job_type=job_type,
        level=job_data.get("level", 1)
    )
    
    # Ajouter les recettes
    for recipe in job_data.get("recipes", []):
        job.add_recipe(recipe)
    
    # Résoudre le bâtiment depuis la location complète
    location = None
    location_data = data.get("location")
    if location_data and location_resolver:
        if isinstance(location_data, dict):
            town = location_data.get("town")
            district = location_data.get("district")
            building = location_data.get("building")
            if building:  # Seulement si un bâtiment est spécifié
                location = location_resolver(town, district, building)
        elif isinstance(location_data, str):
            # Rétrocompatibilité avec l'ancien format
            location = location_resolver(None, None, location_data)
    
    # Créer le NPC
    npc = NPC(
        name=data["name"],
        job=job,
        location=location,
        dialogues=data.get("dialogues"),
        inventory=data.get("inventory", []),
        gold=data.get("gold", 100),
        quests=data.get("quests", [])
    )
    
    return npc


def load_npc(
    npc_id: str, 
    location_resolver: Callable | None = None,
    npc_path: Path | None = None
) -> NPC | None:
    """
    Charge et crée un NPC depuis un fichier JSON.
    
    Args:
        npc_id: Identifiant du PNJ
        location_resolver: Fonction pour résoudre la location
        npc_path: Chemin personnalisé vers le dossier des PNJ
    
    Returns:
        NPC | None: L'objet NPC ou None si non trouvé
    """
    data = load_npc_data(npc_id, npc_path)
    if data is None:
        return None
    
    return create_npc_from_data(data, location_resolver)


def load_all_npcs(
    npc_path: Path | None = None,
    location_resolver: Callable | None = None
) -> list[NPC]:
    """
    Charge tous les PNJ depuis le dossier.
    
    Args:
        npc_path: Chemin personnalisé vers le dossier des PNJ
        location_resolver: Fonction pour résoudre les bâtiments
    
    Returns:
        list[NPC]: Liste de tous les PNJ
    """
    path = npc_path or get_npc_path()
    npcs = []
    
    if not path.exists():
        return npcs
    
    for filepath in path.glob("*.json"):
        try:
            data = load_npc_from_file(filepath)
            npc = create_npc_from_data(data, location_resolver)
            npcs.append(npc)
        except Exception as e:
            print(f"Erreur chargement NPC {filepath}: {e}")
    
    return npcs


def load_npcs_for_village(
    village: "Town",
    npc_ids: list[str] | None = None,
    npc_path: Path | None = None
) -> list[NPC]:
    """
    Charge des PNJ et les associe aux bâtiments d'un village.
    
    Args:
        village: Le village pour la résolution des bâtiments
        npc_ids: Liste des IDs de PNJ à charger (None = tous)
        npc_path: Chemin personnalisé vers le dossier des PNJ
    
    Returns:
        list[NPC]: Liste des PNJ chargés
    """
    def location_resolver(town_name: str | None, district_name: str | None, building_name: str | None):
        """Résout une location vers un Building."""
        if not building_name:
            return None
        # Si town_name correspond, chercher dans le village
        if town_name is None or town_name == village.name:
            if district_name:
                district = village.get_district(district_name)
                if district:
                    return district.get_building(building_name)
            # Fallback: chercher dans tout le village
            return village.find_building_by_name(building_name)
        return None
    
    if npc_ids is None:
        return load_all_npcs(npc_path, location_resolver)
    
    npcs = []
    for npc_id in npc_ids:
        npc = load_npc(npc_id, location_resolver, npc_path)
        if npc:
            npcs.append(npc)
    
    return npcs


def save_npc_to_file(npc: NPC, npc_id: str, npc_path: Path | None = None) -> Path:
    """
    Sauvegarde un NPC dans un fichier JSON.
    
    Args:
        npc: L'objet NPC à sauvegarder
        npc_id: Identifiant pour le fichier
        npc_path: Chemin personnalisé
    
    Returns:
        Path: Chemin du fichier créé
    """
    path = npc_path or get_npc_path()
    path.mkdir(parents=True, exist_ok=True)
    
    filepath = path / f"{npc_id}.json"
    
    # Construire la location avec la structure complète
    location_data = None
    if npc.location:
        building = npc.location
        district = getattr(building, 'district', None)
        town = getattr(district, 'town', None) if district else None
        location_data = {
            "town": town.name if town else None,
            "district": district.name if district else None,
            "building": building.name
        }
    
    data = {
        "id": npc_id,
        "name": npc.name,
        "job": {
            "name": npc.job.name,
            "type": npc.job.job_type.name,
            "level": npc.job.level,
            "recipes": npc.job.recipes
        },
        "location": location_data,
        "gold": npc.gold,
        "inventory": npc.inventory,
        "quests": npc.quests,
        "dialogues": npc.dialogues
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath
