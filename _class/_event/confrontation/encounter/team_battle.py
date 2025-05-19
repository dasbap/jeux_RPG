from typing import List, Dict, Optional
from ..res.team import Character, Team
import random

class TeamBattle:
    def __init__(self, teams : List[Team]):
        if len(teams < 2) : raise RuntimeError("teams number not valide")
        self.teams = teams
        self.team_active : Team = None