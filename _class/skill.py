class Skill:
    def __init__(self, name: str, skill_type: str, value: int, mana_cost: int, stats_target: str = None, fonction_disigned: callable = None):
        """
        Classe représentant une compétence.

        :param name: Nom du sort
        :param skill_type: Type de sort (peut être défini librement)
        :param value: Valeur de l'effet (dégâts, soin, boost, etc. Pour "resurrect", 1 = réanimation)
        :param mana_cost: Coût en mana
        :param stats_target: Stat à affecter pour les buff/debuff (ex: "attack", "defense")
        :param fonction_disigned: Fonction personnalisée pour l'action du sort
        """
        if mana_cost < 0:
            raise ValueError("Le coût en mana ne peut pas être négatif.")
        if value < 0:
            raise ValueError("La valeur de l'effet ne peut pas être négative.")
        if skill_type not in ["damage", "heal", "buff", "debuff", "resurrect"] and fonction_disigned is None:
            raise ValueError("Le type de sort doit être 'damage', 'heal', 'buff', 'debuff', ou doit avoir une fonction personnalisée.")

        self.name = name
        self.skill_type = skill_type 
        self.value = value
        self.mana_cost = mana_cost
        self.stats_target = stats_target
        self.action = fonction_disigned or self.get_default_action()

    def __str__(self):
        return f"{self.name} ({self.skill_type}) - Valeur: {self.value}, Coût en mana: {self.mana_cost}"

    def get_action(self, caster, target):
        """
        Applique l'effet du sort à la cible en appelant la méthode correspondante
        selon l'action personnalisée définie ou une action par défaut.

        :param caster: Le personnage qui lance le sort
        :param target: La cible qui subira l'effet
        :return: Description de l'action effectuée
        """
        if callable(self.action):
            try:
                
                return self.action(caster, target)
            except TypeError:
                return f"L'action personnalisée de {self.name} est invalide."
        return f"Aucune action définie pour {self.name}."

    def get_default_action(self):
        """
        Retourne la fonction d'action par défaut en fonction du type de sort.
        Cette méthode est appelée si aucune fonction personnalisée n'est fournie.
        """
        print(f"default action call {self.skill_type}, {self.name}")
        if self.skill_type == "damage":
            return self.default_damage_action
        elif self.skill_type == "heal":
            return self.default_heal_action
        elif self.skill_type == "buff":
            return self.default_buff_action
        elif self.skill_type == "debuff":
            return self.default_debuff_action
        elif self.skill_type == "resurrect":
            return self.default_resurrect_action
        return None

    def default_damage_action(self, caster, target):
        """Inflige des dégâts à la cible."""
        target.lose_hp(caster,self.value)
        return f"{caster.name} inflige {self.value} dégâts à {target.name}!"

    def default_heal_action(self, caster, target):
        """Soigne la cible."""
        target.gain_hp(self.value)
        return f"{caster.name} soigne {target.name} de {self.value} HP!"

    def default_resurrect_action(self, caster, target):
        """Ressuscite la cible si elle est morte."""
        if not target.is_alive():
            target.resurrected_by(caster)
            return f"{caster.name} utilise {self.name} sur {target.name}!"
        return f"{target.name} ne peux pas être ressuscité!"

    def default_buff_action(self, caster, target):
        """Applique un buff (ex: augmentation des stats)."""
        value = target.buff_stat(self.stats_target, self.value)
        return f"{caster.name} augmente {self.stats_target} de {target.name} de {value}!"

    def default_debuff_action(self, caster, target):
        """Applique un debuff (ex: diminution des stats)."""
        value = target.debuff_stat(self.stats_target, self.value)
        return f"{caster.name} réduit {self.stats_target} de {target.name} de {value}!"
