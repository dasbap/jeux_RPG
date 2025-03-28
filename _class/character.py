from .skill import Skill
from .stats.basic_stat import HP,Energie,Endurance,Force,Sagesse,Intelligence

class Character:
    """Character
    Classe de base pour tous les personnages.
    
    Attributes:
    - user_id (str): Identifiant unique du joueur
    - name (str): Nom du personnage
    - char_class (str): Classe du personnage (ex: "Warrior", "Mage", "Rogue", etc.)
    - hp (HP): Points de vie
    - force (Force): dégât physique
    - endurance (Endurance): Endurance physique
    - inteligence (Intelligence): dégât magique
    - energie default (Mana): Points d'énergie
    - sagesse (Sagesse): Modifie la quantité d'exp gagner
    - skills (dict): Dictionnaire des compétences du personnage
    - status (dict): Dictionnaire des effets actifs du personnage
    - level (int): Niveau du personnage
    - exp (int): Expérience du personnage
    
    Methods:
    - level_up_available(): Vérifie si le personnage peut augmenter son niveau
    - exp_for_level_up(): Calcule l'XP nécessaire pour le prochain niveau
    - gain_exp(exp: int): Gagne de l'XP et monte de niveau si possible
    - lose_hp(value: int): Perd des points de vie et génère de l'XP si nécessaire
    - is_alive(): Vérifie si le personnage est en vie
    - get_skills(): Récupère les compétences du personnage
    - level_up(): Augmente le niveau du personnage et applique les bonus
    - gain_energie(amount: int): Gagne de l'energie
    - get_status(): Récupère les effets actifs du personnage
    """
    class_skills_dict = {}
    
    def __init__(self, user_id: str, name: str, hp: int = 1, force: int = 1, endurance: int = 1, inteligence : int = 1, energie: int = 0, sagesse : int = 1, skills: dict = None):
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Invalid user_id")
        if not name or hp <= 0 or force <= 0 or endurance <= 0 or energie < 0:
            raise ValueError("Invalid character creation parameters")

        self.user_id = user_id
        self.name = name
        self.char_class = self.__class__.__name__
        self.hp = HP(hp)
        self.force = Force(force)
        self.endurance = Endurance(endurance)
        self.inteligence = Intelligence(inteligence)
        self.energie : Energie = Energie("energie",energie)
        self.sagesse = Sagesse(sagesse)
        self.skills = skills or {}
        self.status = {}
        self.level = 1
        self.exp = 0

    def drop_xp(self, target: 'Character') -> str:
        """Transfère l'XP au vainqueur et ajuste le niveau du perdant."""
        xp_given = self.level * 50 + self.exp
        target.gain_exp(xp_given)
        self.exp = 0
        self.level = max(1, self.level - 5)
        return f"{target.name} gained {xp_given} XP from {self.name}."

    def is_alive(self) -> bool:
        return self.hp > 0

    def lose_hp(self, attacker: 'Character', value: int) -> str:
        if value <= 0:
            raise ValueError("HP loss must be positive")
        self.hp = max(0, self.hp - value)
        return f"{attacker.name} dealt {value} damage to {self.name}."

    def gain_hp(self, value: int) -> None:
        if value <= 0:
            raise ValueError("HP gain must be positive")
        self.hp += value

    def get_skill(self, name_skill: str) -> Skill:
        """Récupère une compétence par son nom."""
        if skill := self.skills.get(name_skill):
            return skill
        raise KeyError(f"Skill '{name_skill}' not found for {self.name}")

    def get_skill_dict(self) -> dict:
        return self.skills.copy()

    def level_up_available(self) -> bool:
        """Vérifie si le personnage peut monter de niveau."""
        return self.exp >= self.exp_for_level_up()

    def exp_for_level_up(self) -> int:
        """Calcule l'XP nécessaire pour le prochain niveau."""
        return self.level * 100

    def gain_exp(self, exp: int) -> None:
        """Gagne de l'XP et monte de niveau si possible."""
        if exp <= 0:
            raise ValueError("XP must be positive")
        self.exp += exp
        while self.level_up_available():
            self.level_up()

    def level_up(self) -> None:
        """Augmente le niveau du personnage et améliore ses statistiques."""
        if not self.level_up_available():
            return  
        
        self.exp -= self.exp_for_level_up()
        self.level += 1
        self.hp += 50
        self.force += 5
        self.endurance += 5
        self.energie += 20
        
        if skills_to_add := self.class_skills_dict.get(f"level {self.level}"):
            self.skills.update(skills_to_add)
    
    def gain_energie(self, amount) -> None:
        if amount < 0:
            raise ValueError("energie gain must be positive")
        self.energie = self.energie + amount
    
    def resurrected_by(self, who):
        self.hp
        return f"{self.name} has been resurrected by {who}."

    def __str__(self):
        return f"{self.name} ({self.char_class}) Lvl {self.level} | HP: {self.hp}, FOR: {self.force}, END: {self.endurance}, Energie: {self.energie} | Skills: {', '.join(self.skills)}"

    def __repr__(self):
        return f"<Character {self.name} {self.char_class}>"