from copy import deepcopy
import json
import os
from pathlib import Path
import random
import tempfile
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from jeuxRPG._class.character import Character, CharacterMeta
from jeuxRPG._class._event.confrontation.encounter.fight import Fight
from jeuxRPG._class.res.character.stats import basic_stat
from jeuxRPG._class.res.classType import SkillType, DamageType
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect
from .equipment import Family, Gear, Inventory, Positive, Quantity, Slot


class EnergyState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    maximum: Quantity
    current: Quantity
    regen_rate: Annotated[float, Field(ge=0, le=1)]


class PlayerState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    name: str
    class_name: str
    level: Positive
    exp: Quantity
    stats: dict[str, Quantity]
    hp: Quantity
    energies: list[EnergyState]


class SaveState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: StrictInt = 1
    player: PlayerState
    inventory: Inventory
    battles: Quantity = 0
    wins: Quantity = 0
    losses: Quantity = 0
    draws: Quantity = 0
    rng_state: list[Any]


STAT_NAMES = ("HP", "Force", "Endurance", "Intelligence", "Sagesse")
ENERGY_TYPES = {name: getattr(basic_stat, name) for name in ("Mana", "Aura", "Ki", "Foie")}


def as_tuple(value):
    return tuple(as_tuple(item) for item in value) if isinstance(value, list) else value


class Adventure:
    def __init__(self, path: str | Path, class_name="Knight", name="Héros", seed=42):
        self.path = Path(path)
        self.rng = random.Random(seed)
        self.inventory = Inventory()
        self.battles = self.wins = self.losses = self.draws = 0
        self._bonuses = {}
        if self.path.exists():
            self._load()
        else:
            cls = CharacterMeta._classes.get(class_name.lower())
            if cls is None or not cls.is_playable:
                raise ValueError("Classe jouable inconnue")
            self.player = Character.create(class_name, "local-player", name)
        self._prepare_player()

    def _prepare_player(self):
        if not any(skill.skill_type in {SkillType.DAMAGE, SkillType.INVOCATION} for skill in self.player.skills.values()):
            self.player.skills["Frappe de bâton"] = Skill(name="Frappe de bâton", skill_type=SkillType.DAMAGE,
                                                       damage_type=DamageType.PHYSICAL,
                                                       effects={"damage": SkillEffect(value=6)}, energie_cost=0,
                                                       energie_target=type(self.player.energie[0]), cooldown=0)

    def _load(self):
        state = SaveState.model_validate_json(self.path.read_text(encoding="utf-8"))
        if state.version != 1:
            raise ValueError("Version de sauvegarde non prise en charge")
        p = state.player
        cls = CharacterMeta._classes.get(p.class_name.lower())
        if cls is None or not cls.is_playable or set(p.stats) != set(STAT_NAMES):
            raise ValueError("Personnage sauvegardé invalide")
        if p.stats["HP"] < 1 or p.exp >= p.level * 100:
            raise ValueError("Progression sauvegardée invalide")
        if not p.energies or len({energy.kind for energy in p.energies}) != len(p.energies):
            raise ValueError("Énergies dupliquées")
        self.player = Character.create(p.class_name, p.user_id, p.name)
        self.player.level, self.player.exp = p.level, p.exp
        for stat, value in p.stats.items():
            self.player.get_stat(stat).update_base_value(value)
        self.player.energie.clear()
        for energy in p.energies:
            if energy.kind not in ENERGY_TYPES or energy.current > energy.maximum:
                raise ValueError("Énergie sauvegardée invalide")
            restored = ENERGY_TYPES[energy.kind](energy.maximum, energy.regen_rate)
            restored.current_value = energy.current
            self.player.add_energie(restored)
        self.player._init_status_stats()
        for key, skills in self.player.class_skills_dict.items():
            if key.startswith("level ") and int(key[6:]) <= p.level:
                self.player.skills.update(deepcopy(skills))
        for threshold, upgrade in self.player.class_table["upgrade_stats"].items():
            if threshold <= p.level:
                upgrade.pop("new", None)
        self.inventory = state.inventory
        self.refresh_equipment()
        if p.hp > self.player.hp.value:
            raise ValueError("Points de vie sauvegardés invalides")
        self.player.hp.current_value = p.hp
        self.battles, self.wins, self.losses, self.draws = state.battles, state.wins, state.losses, state.draws
        if self.wins + self.losses + self.draws != self.battles:
            raise ValueError("Compteurs de combats incohérents")
        try:
            self.rng.setstate(as_tuple(state.rng_state))
        except (ValueError, TypeError, IndexError) as error:
            raise ValueError("État aléatoire sauvegardé invalide") from error

    def refresh_equipment(self):
        bonuses = self.inventory.bonuses()
        hp = self.player.hp.current_value
        for name in STAT_NAMES:
            stat = self.player.get_stat(name)
            stat.update_base_value(stat.value - self._bonuses.get(name, 0) + bonuses.get(name, 0))
        self._bonuses = bonuses
        self.player.hp.current_value = min(hp, self.player.hp.value)

    def snapshot(self):
        p = self.player
        return SaveState(
            player=PlayerState(user_id=p.user_id, name=p.name, class_name=p.char_class,
                               level=p.level, exp=p.exp, hp=p.hp.current_value,
                               stats={name: p.get_stat(name).value - self._bonuses.get(name, 0) for name in STAT_NAMES},
                               energies=[EnergyState(kind=type(energy).__name__, maximum=energy.value,
                                                     current=energy.current_value, regen_rate=energy.regen_rate)
                                         for energy in p.energie]),
            inventory=self.inventory, battles=self.battles, wins=self.wins, losses=self.losses,
            draws=self.draws, rng_state=json.loads(json.dumps(self.rng.getstate())),
        )

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(self.snapshot().model_dump_json(indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def craft(self, recipe_id):
        identifier = self.inventory.craft(recipe_id)
        self.save()
        return identifier

    def equip(self, identifier):
        self.inventory.equip(identifier)
        self.refresh_equipment()
        self.save()

    def unequip(self, slot):
        self.inventory.unequip(Slot(slot))
        self.refresh_equipment()
        self.save()

    def auto_craft(self):
        crafted = []
        families = {":".join(recipe.split(":")[:2]) for recipe in self.inventory.recipes()}
        for prefix in sorted(families, key=lambda value: int(value.split(":")[1]), reverse=True):
            family, tier = prefix.split(":")
            gears = [Gear(family=family, tier=int(tier), slot=slot) for slot in Slot]
            owned = {gear.slot: identifier for identifier, gear in self.inventory.items.items()
                     if gear.family.value == family and gear.tier == int(tier)}
            required = {}
            for gear in gears:
                if gear.slot not in owned:
                    for key, amount in gear.ingredients.items():
                        required[key] = required.get(key, 0) + amount
            prospective = Inventory(items={f"item-{index:06d}": gear for index, gear in enumerate(gears, 1)},
                                    equipped={gear.slot: f"item-{index:06d}" for index, gear in enumerate(gears, 1)}, next_id=4)
            if sum(prospective.bonuses().values()) <= sum(self.inventory.bonuses().values()):
                continue
            if any(self.inventory.materials.get(key, 0) < amount for key, amount in required.items()):
                continue
            for gear in gears:
                identifier = owned.get(gear.slot)
                if identifier is None:
                    identifier = self.inventory.craft(gear.recipe_id)
                    crafted.append(identifier)
                self.inventory.equip(identifier)
            self.refresh_equipment()
            return crafted
        for recipe in self.inventory.recipes():
            family, tier, slot = recipe.split(":")
            existing = self.inventory.equipped.get(Slot(slot))
            if existing and self.inventory.items[existing].tier >= int(tier):
                continue
            try:
                identifier = self.inventory.craft(recipe)
            except ValueError:
                continue
            self.inventory.equip(identifier)
            crafted.append(identifier)
        self.refresh_equipment()
        return crafted

    def encounter(self, max_rounds=200, auto_craft=False):
        if type(max_rounds) is not int or max_rounds < 1:
            raise ValueError("Nombre de rounds invalide")
        family = self.rng.choice(list(Family))
        enemy_level = max(1, self.player.level - 1)
        enemy = self.create_enemy(family, enemy_level)
        level, exp = self.player.level, self.player.exp
        if not self.player.is_alive():
            self.player.hp.set_max()
        fight = Fight(self.player, enemy, name=f"Arène {self.battles + 1}")
        global_state = random.getstate()
        random.setstate(self.rng.getstate())
        rounds = 0
        try:
            while rounds < max_rounds and not fight.is_over():
                fight.start_round(rest=True)
                fight.clear_log()
                rounds += 1
            won = self.player.is_alive() and not enemy.is_alive()
            lost = not self.player.is_alive()
        finally:
            self.rng.setstate(random.getstate())
            random.setstate(global_state)
            fight.end()
        self.battles += 1
        self.wins += int(won)
        self.losses += int(lost)
        self.draws += int(not won and not lost)
        loot = {}
        if won:
            tier = 1 + (enemy_level - 1) // 5
            hide, trophy = self.rng.randint(2, 4), self.rng.randint(1, 2)
            self.inventory.add_loot(family, tier, hide, trophy)
            loot = {"family": family.value, "tier": tier, "hide": hide, "trophy": trophy}
        elif lost:
            self.player.level, self.player.exp = level, exp
        self.player.invocations.kill_all()
        for stat in [self.player.hp, self.player.force, self.player.endurance, self.player.intelligence, self.player.sagesse, *self.player.energie]:
            stat.clear_effects()
            stat.set_max()
        for skill in self.player.skills.values():
            skill.reset_cooldown()
        for key in ("stun", "invulnerability", "buff", "debuff"):
            self.player.status["alteration"][key].clear()
        self.player.status["alteration"]["Damage"]["Incoming"].clear()
        for values in self.player.status["alteration"]["Damage"]["Reduction"].values():
            values.clear()
        crafted = self.auto_craft() if auto_craft else []
        self.save()
        return {"battle": self.battles, "enemy": family.value, "enemy_level": enemy_level,
                "outcome": "victory" if won else "defeat" if lost else "draw", "rounds": rounds,
                "loot": loot, "crafted": crafted, "level": self.player.level}

    def create_enemy(self, family, level):
        if type(level) is not int or level < 1:
            raise ValueError("Niveau de créature invalide")
        enemy = Character.create(family.value, f"enemy-{self.battles + 1}", family.value)
        for threshold, upgrade in enemy.class_table["upgrade_stats"].items():
            count = max(0, level - max(2, threshold) + 1)
            if not count:
                continue
            for key, value in upgrade.items():
                if isinstance(key, type) and key.__name__ in STAT_NAMES:
                    enemy.get_stat(key.__name__).upgrade_base_value(value * count)
            for energy_type, value in upgrade.get("Energie", {}).items():
                enemy.get_energie(energy_type).upgrade_base_value(value * count)
        for key, skills in enemy.class_skills_dict.items():
            if key.startswith("level ") and int(key[6:]) <= level:
                enemy.skills.update(deepcopy(skills))
        enemy.level = level
        return enemy

    def status(self):
        return {"name": self.player.name, "class": self.player.char_class, "level": self.player.level,
                "exp": self.player.exp, "hp": self.player.hp.current_value, "hp_max": self.player.hp.value,
                "battles": self.battles, "wins": self.wins, "losses": self.losses, "draws": self.draws,
                "bonuses": self.inventory.bonuses(), "equipped": {slot.value: identifier for slot, identifier in self.inventory.equipped.items()}}
