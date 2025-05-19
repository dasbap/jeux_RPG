# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables du fichier .env
load_dotenv()

# Configuration de base
class Config:
    # Chemins
    BASE_DIR = Path(os.getenv("BOTKIRITOGAME", Path(__file__).parent.parent))
    CLASS_DIR = BASE_DIR / "_class"
    SUBS_DIR = CLASS_DIR / "sub_character"
    
    # Paramètres
    DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
    DB_URL = os.getenv("DATABASE_URL")
    
    # Structure projet (documentation)
    PROJECT_STRUCTURE = {
        "root": str(BASE_DIR),
        "_class": {
            "sub_character": ["mage.py", "archer.py", "knight.py", "priest.py"],
            "mob": ["mob.py"],
            "_event": {
                "confrontation": {
                    "encounter": ["fight.py", "team_battle.py"],
                    "res": ["team.py"]
                }
            },
            "stats": ["basic_stat.py", "stat.py"]
        }
    }

# Instance de configuration
config = Config()