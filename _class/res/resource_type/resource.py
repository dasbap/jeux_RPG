class Resource:
    def __init__(self, name, quantity=0, r_type="générique", rarity="commun"):
        self.name = name
        self.quantity = quantity
        self.type = r_type
        self.rarity = rarity

    def __add__(self, other):
        if isinstance(other, Resource) and self == other:
            return Resource(self.name, self.quantity + other.quantity, self.type, self.rarity)
        elif isinstance(other, int):
            return Resource(self.name, self.quantity + other, self.type, self.rarity)
        raise ValueError("Impossible d'ajouter une ressource différente ou invalide.")

    def __sub__(self, other):
        if isinstance(other, Resource) and self == other:
            if self.quantity - other.quantity < 0:
                raise ValueError("Quantité négative interdite.")
            return Resource(self.name, self.quantity - other.quantity, self.type, self.rarity)
        elif isinstance(other, int):
            if self.quantity - other < 0:
                raise ValueError("Quantité négative interdite.")
            return Resource(self.name, self.quantity - other, self.type, self.rarity)
        raise ValueError("Impossible de soustraire une ressource différente ou invalide.")

    def __iadd__(self, other):
        if isinstance(other, Resource) and self == other:
            self.quantity += other.quantity
        elif isinstance(other, int):
            self.quantity += other
        else:
            raise ValueError("Ajout invalide.")
        return self

    def __isub__(self, other):
        if isinstance(other, Resource) and self == other:
            if self.quantity - other.quantity < 0:
                raise ValueError("Quantité négative interdite.")
            self.quantity -= other.quantity
        elif isinstance(other, int):
            if self.quantity - other < 0:
                raise ValueError("Quantité négative interdite.")
            self.quantity -= other
        else:
            raise ValueError("Soustraction invalide.")
        return self

    def __eq__(self, other):
        return isinstance(other, Resource) and self.name == other.name and self.type == other.type and self.rarity == other.rarity

    def __str__(self):
        return f"{self.quantity}x {self.name} ({self.type}, rareté: {self.rarity})"

    def __repr__(self):
        return f"Resource(name='{self.name}', quantity={self.quantity}, type='{self.type}', rarity='{self.rarity}')"
