from jeuxRPG.i18n import t


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
        raise ValueError(t("resource.error_add"))

    def __sub__(self, other):
        if isinstance(other, Resource) and self == other:
            if self.quantity - other.quantity < 0:
                raise ValueError(t("resource.error_negative"))
            return Resource(self.name, self.quantity - other.quantity, self.type, self.rarity)
        elif isinstance(other, int):
            if self.quantity - other < 0:
                raise ValueError(t("resource.error_negative"))
            return Resource(self.name, self.quantity - other, self.type, self.rarity)
        raise ValueError(t("resource.error_sub"))

    def __iadd__(self, other):
        if isinstance(other, Resource) and self == other:
            self.quantity += other.quantity
        elif isinstance(other, int):
            self.quantity += other
        else:
            raise ValueError(t("resource.error_invalid_add"))
        return self

    def __isub__(self, other):
        if isinstance(other, Resource) and self == other:
            if self.quantity - other.quantity < 0:
                raise ValueError(t("resource.error_negative"))
            self.quantity -= other.quantity
        elif isinstance(other, int):
            if self.quantity - other < 0:
                raise ValueError(t("resource.error_negative"))
            self.quantity -= other
        else:
            raise ValueError(t("resource.error_invalid_sub"))
        return self

    def __eq__(self, other):
        return isinstance(other, Resource) and self.name == other.name and self.type == other.type and self.rarity == other.rarity

    def __str__(self):
        return t("resource.str", quantity=self.quantity, name=self.name, type=self.type, rarity=self.rarity)

    def __repr__(self):
        return f"Resource(name='{self.name}', quantity={self.quantity}, type='{self.type}', rarity='{self.rarity}')"
