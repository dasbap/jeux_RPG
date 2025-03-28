from _class.sub_character.archer import Archer
from _class.mob.mob import Mob
from _class._event.duel import Duel


player = Archer("12234411","bob")

goblin = Mob("00001","goblin", 350)

print(player)
print(goblin)

combat = Duel(player,goblin)
combat.add_to_controlled_entities(player, "controlled")
combat.add_to_controlled_entities(goblin, "bot")

print(combat.player_action(player, "Arrow Rain", goblin))

print(goblin)