from _class.sub_character.chevalier import Chevalier
from _class.mob.mob import Mob

chevalier = Chevalier("12345678", "Bob")
goblin = Mob("00001", "goblin")

print(chevalier)
print(goblin)

goblin.gain_exp(20)
print(goblin)

chevalier.lose_hp(chevalier, 15)

print(chevalier)

