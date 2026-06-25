from jeuxRPG._class.character import Character
from jeuxRPG._class.res.character.table_stat_subclass import archer_table


class Archer(Character):
    """Classe représentant un Archer, spécialisé dans les attaques à distance."""
    
    is_playable: bool = True
    class_skills_dict = archer_table["class_skills_dict"]
    
    def __init__(self, user_id: str, name: str):
        """Initialise un Archer avec ses statistiques de base.
        
        Args:
            user_id: Identifiant unique du joueur
            name: Nom du personnage
        """
        super().__init__(
            user_id=user_id,
            name=name,
            class_table=archer_table.copy(),
        )