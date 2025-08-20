import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = Path(os.getenv("BOTKIRITOGAME", Path(__file__).parent.parent))
    CLASS_DIR = BASE_DIR / "_class"
    SUBS_DIR = CLASS_DIR / "sub_character"
    
    DEBUG = os.getenv("DEBUG_MODE", "False") == "True"
    DB_URL = os.getenv("DATABASE_URL")
    
    PROJECT_STRUCTURE = {
        "root": str(BASE_DIR),
        "_class": {
            "sub_character": ["knight.py"],
            "mob": ["mob.py"],
            "_event": {
                "confrontation": {
                    "encounter": ["fight.py", "team_battle.py"],
                    "res": ["team.py"]
                }
            },
            "stats": ["basic_stat.py", "stat.py"]
        },
        "_function":{
            "Character":["level_up_f"],
            "skill":["custom"]
        }
    }

config = Config()