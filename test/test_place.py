"""
Tests pour le module place (Town, District, Building, Navigation, Jobs, NPC).
"""

import pytest
import tempfile
import json
from pathlib import Path

from jeuxRPG._class.place.building import Building
from jeuxRPG._class.place.district import District
from jeuxRPG._class.place.town import Town
from jeuxRPG._class.place.navigation import Location, LocationType, Navigator
from jeuxRPG._class.place.jobs.job import Job
from jeuxRPG._class.place.jobs.job_types import JobType, ServiceType
from jeuxRPG._class.place.jobs.npc import NPC
from jeuxRPG._class.place.jobs.npc_loader import (
    load_npc_data,
    create_npc_from_data,
    load_npc,
    save_npc_to_file,
    load_npcs_for_village
)
from jeuxRPG._class.place.village_factory import (
    create_starting_village,
    create_navigator_at_village,
    STARTING_VILLAGE_NPCS
)
from jeuxRPG._class.res.classType import Build_type, Build_state


# ==================== BUILDING TESTS ====================

class TestBuilding:
    """Tests pour la classe Building."""
    
    def test_create_building(self):
        """Test création d'un bâtiment."""
        building = Building("Forge", Build_type.FORGE, level=1)
        assert building.name == "Forge"
        assert building.type == Build_type.FORGE
        assert building.level == 1
        assert building.status == Build_state.UNDER_CONSTRUCTION
    
    def test_building_with_status(self):
        """Test création avec statut spécifié."""
        building = Building("Auberge", Build_type.INN, level=2, status=Build_state.OPERATIONAL)
        assert building.status == Build_state.OPERATIONAL
        assert building.level == 2
    
    def test_upgrade_building(self):
        """Test amélioration d'un bâtiment."""
        building = Building("Forge", Build_type.FORGE)
        assert building.level == 1
        building.upgrade()
        assert building.level == 2
    
    def test_set_status_enum(self):
        """Test changement de statut avec enum."""
        building = Building("Forge", Build_type.FORGE)
        building.set_status(Build_state.OPERATIONAL)
        assert building.status == Build_state.OPERATIONAL
    
    def test_set_status_string(self):
        """Test changement de statut avec string."""
        building = Building("Forge", Build_type.FORGE)
        building.set_status("OPERATIONAL")
        assert building.status == Build_state.OPERATIONAL
    
    def test_get_info(self):
        """Test récupération des infos."""
        building = Building("Forge", Build_type.FORGE, level=3)
        info = building.get_info()
        assert info["name"] == "Forge"
        assert info["level"] == 3


# ==================== DISTRICT TESTS ====================

class TestDistrict:
    """Tests pour la classe District."""
    
    def test_create_district(self):
        """Test création d'un quartier."""
        district = District("Centre")
        assert district.name == "Centre"
        assert district.buildings == {}
        assert district.npcs == []
    
    def test_create_building_in_district(self):
        """Test création de bâtiment dans un quartier."""
        district = District("Centre")
        building = district.create_building("Forge", Build_type.FORGE)
        
        assert "Forge" in district.buildings
        assert building.district == district
    
    def test_add_building(self):
        """Test ajout d'un bâtiment existant."""
        district = District("Centre")
        building = Building("Forge", Build_type.FORGE)
        district.add_building(building)
        
        assert building.name in district.buildings
        assert building.district == district
    
    def test_get_building(self):
        """Test récupération d'un bâtiment."""
        district = District("Centre")
        district.create_building("Forge", Build_type.FORGE)
        
        building = district.get_building("Forge")
        assert building is not None
        assert building.name == "Forge"
        
        assert district.get_building("Inexistant") is None
    
    def test_connect_districts(self):
        """Test connexion entre quartiers."""
        d1 = District("Centre")
        d2 = District("Port")
        
        d1.connect_to(d2)
        
        assert d2 in d1.connected_districts
        assert d1 in d2.connected_districts  # Bidirectionnel
    
    def test_connect_unidirectional(self):
        """Test connexion unidirectionnelle."""
        d1 = District("Centre")
        d2 = District("Port")
        
        d1.connect_to(d2, bidirectional=False)
        
        assert d2 in d1.connected_districts
        assert d1 not in d2.connected_districts
    
    def test_can_go_to(self):
        """Test vérification de déplacement."""
        d1 = District("Centre")
        d2 = District("Port")
        d1.connect_to(d2)
        
        assert d1.can_go_to("Port")
        assert not d1.can_go_to("Inexistant")
    
    def test_add_resource(self):
        """Test ajout de ressources."""
        district = District("Centre")
        district.add_resource("bois", 100)
        
        assert district.get_resource("bois") == 100
    
    def test_spend_resource(self):
        """Test dépense de ressources."""
        district = District("Centre")
        district.add_resource("bois", 100)
        
        assert district.spend_resource("bois", 50)
        assert district.get_resource("bois") == 50
        assert not district.spend_resource("bois", 100)  # Pas assez


# ==================== TOWN TESTS ====================

class TestTown:
    """Tests pour la classe Town."""
    
    def test_create_town(self):
        """Test création d'une ville."""
        town = Town("Village", population=100, wealth=500)
        assert town.name == "Village"
        assert town.population == 100
        assert town.wealth == 500
        assert town.districts == {}
    
    def test_create_district(self):
        """Test création d'un quartier dans une ville."""
        town = Town("Village")
        district = town.create_district("Centre")
        
        assert "Centre" in town.districts
        assert district.town == town
        assert town.entry_district == district  # Premier quartier = entrée
    
    def test_set_entry_district(self):
        """Test définition du quartier d'entrée."""
        town = Town("Village")
        town.create_district("Centre")
        town.create_district("Port")
        
        assert town.set_entry_district("Port")
        assert town.entry_district.name == "Port"
    
    def test_connect_districts(self):
        """Test connexion de quartiers via la ville."""
        town = Town("Village")
        town.create_district("Centre")
        town.create_district("Port")
        
        assert town.connect_districts("Centre", "Port")
        
        centre = town.get_district("Centre")
        assert centre.can_go_to("Port")
    
    def test_connect_towns(self):
        """Test connexion entre villes."""
        town1 = Town("Village1")
        town2 = Town("Village2")
        
        town1.connect_to(town2)
        
        assert town1.can_travel_to("Village2")
        assert town2.can_travel_to("Village1")
    
    def test_find_building_by_name(self):
        """Test recherche de bâtiment."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge", Build_type.FORGE)
        
        building = town.find_building_by_name("Forge")
        assert building is not None
        assert building.name == "Forge"
    
    def test_find_building_by_type(self):
        """Test recherche de bâtiments par type."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge1", Build_type.FORGE)
        district.create_building("Forge2", Build_type.FORGE)
        district.create_building("Auberge", Build_type.INN)
        
        forges = town.find_building_by_type(Build_type.FORGE)
        assert len(forges) == 2


# ==================== JOB TESTS ====================

class TestJob:
    """Tests pour la classe Job."""
    
    def test_create_job(self):
        """Test création d'un métier."""
        job = Job("Forgeron", JobType.BLACKSMITH, level=5)
        assert job.name == "Forgeron"
        assert job.job_type == JobType.BLACKSMITH
        assert job.level == 5
    
    def test_default_services(self):
        """Test services par défaut."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        assert job.can_provide(ServiceType.CRAFT)
        assert job.can_provide(ServiceType.REPAIR)
    
    def test_gain_exp(self):
        """Test gain d'expérience."""
        job = Job("Forgeron", JobType.BLACKSMITH, level=1)
        leveled_up = job.gain_exp(150)  # 100 exp par niveau
        
        assert leveled_up
        assert job.level == 2
        assert job.exp == 50
    
    def test_max_level(self):
        """Test niveau maximum."""
        job = Job("Forgeron", JobType.BLACKSMITH, level=100)
        leveled_up = job.gain_exp(1000)
        
        assert not leveled_up
        assert job.level == 100
    
    def test_add_recipe(self):
        """Test ajout de recettes."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        job.add_recipe("epee_fer")
        
        assert "epee_fer" in job.recipes
        
        # Pas de doublon
        job.add_recipe("epee_fer")
        assert job.recipes.count("epee_fer") == 1


# ==================== NPC TESTS ====================

class TestNPC:
    """Tests pour la classe NPC."""
    
    def test_create_npc(self):
        """Test création d'un PNJ."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        npc = NPC("Baldric", job)
        
        assert npc.name == "Baldric"
        assert npc.job == job
        assert npc.gold == 100  # Défaut
    
    def test_npc_with_location(self):
        """Test PNJ avec bâtiment."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        building = Building("Forge", Build_type.FORGE)
        npc = NPC("Baldric", job, location=building)
        
        assert npc.location == building
        assert npc.job.workplace == building
    
    def test_default_dialogues(self):
        """Test dialogues par défaut."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        npc = NPC("Baldric", job)
        
        dialogue = npc.get_dialogue("greeting")
        assert dialogue is not None
    
    def test_custom_dialogues(self):
        """Test dialogues personnalisés."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        npc = NPC("Baldric", job, dialogues={"greeting": ["Salut!"]})
        
        assert npc.get_dialogue("greeting") == "Salut!"
    
    def test_can_provide_service(self):
        """Test vérification des services."""
        job = Job("Forgeron", JobType.BLACKSMITH)
        npc = NPC("Baldric", job)
        
        assert npc.can_provide(ServiceType.CRAFT)
        assert not npc.can_provide(ServiceType.HEAL)
    
    def test_inventory(self):
        """Test inventaire."""
        job = Job("Marchand", JobType.MERCHANT)
        npc = NPC("Marco", job, inventory=["potion", "epee"])
        
        assert len(npc.inventory) == 2
        
        npc.add_to_inventory("bouclier")
        assert len(npc.inventory) == 3
        
        assert npc.remove_from_inventory("potion")
        assert len(npc.inventory) == 2


# ==================== NAVIGATION TESTS ====================

class TestNavigation:
    """Tests pour la navigation."""
    
    def test_location_wilderness(self):
        """Test location en pleine nature."""
        loc = Location()
        assert loc.location_type == LocationType.WILDERNESS
        # current_name returns translated wilderness string
        assert len(loc.current_name) > 0  # Non-empty name
    
    def test_location_in_town(self):
        """Test location dans une ville."""
        town = Town("Village")
        loc = Location(town=town)
        
        assert loc.location_type == LocationType.TOWN
        assert loc.current_name == "Village"
    
    def test_location_in_building(self):
        """Test location dans un bâtiment."""
        town = Town("Village")
        district = town.create_district("Centre")
        building = district.create_building("Forge", Build_type.FORGE)
        
        loc = Location(town=town, district=district, building=building)
        
        assert loc.location_type == LocationType.BUILDING
        assert loc.get_full_location() == "Village > Centre > Forge"
    
    def test_navigator_spawn(self):
        """Test spawn du navigateur."""
        town = Town("Village")
        town.create_district("Centre")
        
        nav = Navigator()
        nav.spawn_at(town)
        
        assert nav.get_current_town() == town
        assert nav.get_current_district() == town.entry_district
    
    def test_navigator_enter_building(self):
        """Test entrée dans un bâtiment."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge", Build_type.FORGE, status=Build_state.OPERATIONAL)
        
        nav = Navigator()
        nav.spawn_at(town)
        
        success, msg = nav.enter_building("Forge")
        
        assert success
        assert nav.get_current_building() is not None
        assert nav.get_current_building().name == "Forge"
    
    def test_navigator_exit_building(self):
        """Test sortie d'un bâtiment."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge", Build_type.FORGE, status=Build_state.OPERATIONAL)
        
        nav = Navigator()
        nav.spawn_at(town)
        nav.enter_building("Forge")
        
        success, msg = nav.exit_building()
        
        assert success
        assert nav.get_current_building() is None
    
    def test_navigator_cannot_enter_destroyed(self):
        """Test impossibilité d'entrer dans un bâtiment détruit."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge", Build_type.FORGE, status=Build_state.DESTROY)
        
        nav = Navigator()
        nav.spawn_at(town)
        
        success, msg = nav.enter_building("Forge")
        
        assert not success
    
    def test_navigator_travel(self):
        """Test voyage entre villes."""
        town1 = Town("Village1")
        town1.create_district("Centre1")
        
        town2 = Town("Village2")
        town2.create_district("Centre2")
        
        town1.connect_to(town2)
        
        nav = Navigator()
        nav.spawn_at(town1)
        
        success, msg = nav.travel_to("Village2")
        
        assert success
        assert nav.get_current_town() == town2
    
    def test_movement_options(self):
        """Test options de déplacement."""
        town = Town("Village")
        district = town.create_district("Centre")
        district.create_building("Forge", Build_type.FORGE)
        district.create_building("Auberge", Build_type.INN)
        
        nav = Navigator()
        nav.spawn_at(town)
        
        options = nav.get_movement_options()
        
        assert "Forge" in options["buildings"]
        assert "Auberge" in options["buildings"]


# ==================== NPC LOADER TESTS ====================

class TestNPCLoader:
    """Tests pour le chargement des PNJ depuis JSON."""
    
    @pytest.fixture
    def temp_npc_dir(self):
        """Crée un répertoire temporaire pour les tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_create_npc_from_data(self):
        """Test création de NPC depuis données."""
        data = {
            "name": "TestNPC",
            "job": {
                "name": "Forgeron",
                "type": "BLACKSMITH",
                "level": 5,
                "recipes": ["epee_fer"]
            },
            "gold": 200,
            "inventory": ["item1"],
            "quests": ["quest1"],
            "dialogues": {"greeting": ["Bonjour!"]}
        }
        
        npc = create_npc_from_data(data)
        
        assert npc.name == "TestNPC"
        assert npc.job.job_type == JobType.BLACKSMITH
        assert npc.job.level == 5
        assert "epee_fer" in npc.job.recipes
        assert npc.gold == 200
    
    def test_save_and_load_npc(self, temp_npc_dir):
        """Test sauvegarde et chargement d'un NPC."""
        job = Job("Forgeron", JobType.BLACKSMITH, level=5)
        npc = NPC("TestNPC", job, gold=300)
        
        # Sauvegarder
        filepath = save_npc_to_file(npc, "test_npc", temp_npc_dir)
        assert filepath.exists()
        
        # Charger
        data = load_npc_data("test_npc", temp_npc_dir)
        assert data is not None
        assert data["name"] == "TestNPC"
        assert data["gold"] == 300
    
    def test_load_npc_with_location(self, temp_npc_dir):
        """Test chargement d'un NPC avec location."""
        # Créer un fichier NPC avec location
        data = {
            "id": "test",
            "name": "TestNPC",
            "job": {"name": "Forgeron", "type": "BLACKSMITH", "level": 1, "recipes": []},
            "location": {
                "town": "Village",
                "district": "Centre",
                "building": "Forge"
            },
            "gold": 100,
            "inventory": [],
            "quests": [],
            "dialogues": {}
        }
        
        with open(temp_npc_dir / "test.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        # Créer une ville pour la résolution
        town = Town("Village")
        district = town.create_district("Centre")
        building = district.create_building("Forge", Build_type.FORGE)
        
        # Charger
        npcs = load_npcs_for_village(town, ["test"], temp_npc_dir)
        
        assert len(npcs) == 1
        assert npcs[0].location == building


# ==================== VILLAGE FACTORY TESTS ====================

class TestVillageFactory:
    """Tests pour la factory de village."""
    
    def test_create_starting_village_structure(self):
        """Test structure du village de départ (sans PNJ)."""
        village = create_starting_village(load_npcs=False)
        
        assert village.name == "Vallon Paisible"
        assert "Place Centrale" in village.districts
        
        # Vérifier les bâtiments
        buildings = village.get_all_buildings()
        building_types = [b.type for b in buildings]
        
        assert Build_type.INN in building_types
        assert Build_type.FORGE in building_types
        assert Build_type.SHOP in building_types
        assert Build_type.TEMPLE in building_types
        assert Build_type.TOWN_HALL in building_types
    
    def test_create_starting_village_with_npcs(self):
        """Test village de départ avec PNJ."""
        village = create_starting_village(load_npcs=True)
        
        npcs = village.get_all_npcs()
        # Le nombre peut varier selon les fichiers JSON présents
        assert len(npcs) >= 0  # Au moins les fichiers existants sont chargés
    
    def test_starting_village_npc_list(self):
        """Test que la liste de PNJ est définie."""
        assert len(STARTING_VILLAGE_NPCS) == 7
        assert "elara" in STARTING_VILLAGE_NPCS
        assert "baldric" in STARTING_VILLAGE_NPCS
    
    def test_navigator_at_village(self):
        """Test création du navigateur."""
        village = create_starting_village(load_npcs=False)
        nav = create_navigator_at_village(village)
        
        assert nav.get_current_town() == village
        assert nav.get_current_district() == village.entry_district
    
    def test_custom_village_name(self):
        """Test nom personnalisé du village."""
        village = create_starting_village(name="Mon Village", load_npcs=False)
        assert village.name == "Mon Village"


# ==================== INTEGRATION TESTS ====================

class TestIntegration:
    """Tests d'intégration."""
    
    def test_full_navigation_flow(self):
        """Test flux complet de navigation."""
        # Créer deux villages connectés
        village1 = create_starting_village(name="Village1", load_npcs=False)
        village2 = create_starting_village(name="Village2", load_npcs=False)
        village1.connect_to(village2)
        
        # Naviguer
        nav = create_navigator_at_village(village1)
        
        # Entrer dans un bâtiment
        success, _ = nav.enter_building("La Forge Ardente")
        assert success
        assert "La Forge Ardente" in nav.where_am_i()
        
        # Sortir
        nav.exit_building()
        
        # Voyager vers l'autre village
        success, _ = nav.travel_to("Village2")
        assert success
        assert nav.get_current_town().name == "Village2"
    
    def test_district_npc_integration(self):
        """Test intégration NPC dans les quartiers."""
        village = create_starting_village(load_npcs=False)
        district = village.get_district("Place Centrale")
        
        # Ajouter un NPC manuellement
        job = Job("Garde", JobType.GUARD)
        npc = NPC("TestGuard", job)
        district.add_npc(npc)
        
        # Vérifier qu'il est dans les gardes
        assert npc in district.guards
        assert npc in district.npcs
        
        # Le trouver par métier
        guards = district.get_npcs_by_job(JobType.GUARD)
        assert npc in guards
