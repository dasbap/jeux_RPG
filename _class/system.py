

class CharacterSystem:
    """Système central de gestion des personnages."""
    
    @staticmethod
    def create(class_name: str, *args, **kwargs) -> Character:
        """Crée un personnage du type spécifié."""
        char_class = CharacterMeta._classes.get(class_name.lower())
        if not char_class:
            raise ValueError(f"Classe {class_name} introuvable")
        return char_class(*args, **kwargs)
    
    @staticmethod
    def register_class(char_class: Type[Character]) -> None:
        """Enregistre une nouvelle classe de personnage."""
        CharacterMeta._classes[char_class.__name__.lower()] = char_class
    
    @staticmethod
    def list_classes() -> Dict[str, Type[Character]]:
        """Liste toutes les classes disponibles."""
        return CharacterMeta._classes.copy()