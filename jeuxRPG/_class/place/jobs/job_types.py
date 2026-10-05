from enum import Enum, auto


class JobType(Enum):
    """Types de métiers disponibles pour les joueurs et PNJ."""
    
    # Artisanat
    BLACKSMITH = auto()      # Forgeron - armes/armures
    ALCHEMIST = auto()       # Alchimiste - potions
    ENCHANTER = auto()       # Enchanteur - améliore équipement
    TAILOR = auto()          # Tailleur - vêtements/robes
    JEWELER = auto()         # Joaillier - bijoux/accessoires
    CARPENTER = auto()       # Charpentier - arcs/bâtons/meubles
    
    # Récolte
    MINER = auto()           # Mineur - minerais
    FARMER = auto()          # Fermier - cultures
    HERBALIST = auto()       # Herboriste - plantes
    HUNTER = auto()          # Chasseur - peaux/viande
    FISHER = auto()          # Pêcheur - poissons
    LUMBERJACK = auto()      # Bûcheron - bois
    
    # Services
    MERCHANT = auto()        # Marchand - commerce
    INNKEEPER = auto()       # Aubergiste - repos/nourriture
    PRIEST = auto()          # Prêtre - soins/bénédictions
    GUARD = auto()           # Garde - protection
    MAYOR = auto()           # Maire - administration
    BANKER = auto()          # Banquier - stockage/prêts
    
    # Spéciaux
    ADVENTURER = auto()      # Aventurier - quêtes diverses
    SCHOLAR = auto()         # Érudit - connaissances/livres


class ServiceType(Enum):
    """Types de services qu'un métier peut offrir."""
    
    BUY = auto()             # Acheter des objets au joueur
    SELL = auto()            # Vendre des objets au joueur
    CRAFT = auto()           # Fabriquer des objets
    REPAIR = auto()          # Réparer équipement
    UPGRADE = auto()         # Améliorer équipement
    HEAL = auto()            # Soigner
    BLESS = auto()           # Bénir (buff temporaire)
    REST = auto()            # Offrir repos (récupération)
    STORE = auto()           # Stocker objets (coffre)
    QUEST = auto()           # Donner des quêtes
    TEACH = auto()           # Enseigner compétences
    TRANSPORT = auto()       # Téléporter/voyager
