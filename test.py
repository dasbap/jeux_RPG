print("import")

from _class._event.confrontation.encounter.team_battle import TeamBattle
from _class.character import Character
from _class.res.team.team import Team


print("creation")

knight = Character.create("Knight", "0000000", "bob")

bad_knight = Character.create("Knight", "1111111", "bad guy")

necrom = Character.create("necromancien", "2222222", "lich")

print("start")

print("xp")
print(knight.gain_exp(500000))

print("create battle")
Team("knigths", knight)

Team("bad guys", [bad_knight,necrom])

combat = TeamBattle(knight.team,bad_knight.team)


input("fight")

# combat.auto_battle()

# print("log")
# for fight in combat.fights:
#     print(fight.log_message)
#     print(fight.round)
#     print(fight._get_alive_participant())

print(knight.use_skill("Shield Bash", bad_knight))

input("restart")

