from _class.sub_character.archer import Archer  # Correct import
from _class.mob.mob import Mob
from _class._event.duel import Duel

# Création des personnages
player = Archer("12234411", "bob")  # Un archer (joueur)
goblin = Mob("00001", "goblin", 350)  # Un gobelin (ennemi)

# Affichage des personnages pour vérifier les stats
print(player)
print(goblin)



goblin.lose_hp(player, 20)

print(goblin)