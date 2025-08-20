from jeuxRPG._class.sub_character.knight import Knight
from jeuxRPG._core.factory.Character_factory import Character_factory
from jeuxRPG._core.game_controller import GameController

gamecontroller = GameController()

gamecontroller.set_factory_target(Character_factory, Knight)
gamecontroller.update_factory_attribute(Character_factory,{"name":"bob","id":"0002"})


knight : Knight = gamecontroller.factory_create(Character_factory)

print(knight)