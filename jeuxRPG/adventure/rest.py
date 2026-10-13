def restore_until(adventure, until):
    rules = adventure.catalog.geography
    target = rules.day_start if until == "day" else rules.night_start
    hours = (target - adventure.location.elapsed_hours % 24) % 24 or 24
    adventure._advance_hours(hours)
    adventure.player.hp.set_max()
    for energy in adventure.player.energie:
        energy.set_max()
    adventure.save()
    return {"rested_hours": hours, "hour": target, "night": adventure.is_night}
