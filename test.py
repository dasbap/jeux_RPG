from _class import Mob, Character, Team, TeamBattle
from _class._event.confrontation.encounter.fight import Fight


# Création des personnages
knight = Character.create("Knight", "the one", "bob")
mage = Character.create("Mage", "the one", "lis")
archer = Character.create("Archer", "the one", "arrow")
priest = Character.create("Priest", "the goat", "saint")

orc = Character.create("Mob", "orc", "Gull")
goblin = Character.create("Mob", "goblin", "knack")
troll = Character.create("Mob", "troll", "slut")

# Création des équipes
equipe_joueurs = Team("Héros", [knight, mage, archer])
equipe_monstres = Team("Monstres", [orc, goblin, troll])

combat = Fight(equipe_joueurs, equipe_monstres)
