from jeuxRPG._class.character import Character

def level_up_f(target : Character, level_target) -> None:
    """_summary_
    
    Role:
        level up using auto exp, use only when create a new Character or a Boss phase
        
    Args:
        target (Character): a new born or a boss switching pahse
        level_target (_type_): the level needed, if the actual level is already higher than the target, nothing happened

    Returns:
        Character: the Character after the leveling
    """
    if target.level < level_target:
        target.gain_exp(target._required_exp_for_next_level())
        level_up_f(target, level_target)