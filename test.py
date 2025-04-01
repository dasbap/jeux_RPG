from _class.sub_character.chevalier import Chevalier
from _class.mob.mob import Mob
from _class._event.duel import Duel
chevalier = Chevalier("12345678", "Bob")
goblin = Mob("00001", "goblin")

combat = Duel(chevalier, goblin)

combat.add_to_controlled_entities(chevalier, "controlled")
combat.add_to_controlled_entities(goblin, "bot")

combat.start()