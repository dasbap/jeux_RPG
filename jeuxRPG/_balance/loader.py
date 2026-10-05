from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping
import json

from jeuxRPG._class.res.character import table_stat_subclass as tables
from jeuxRPG._class.skills.skill import Skill
from jeuxRPG._class.skills.skillEffect import SkillEffect

# Map class display names to their class tables (dicts)
CLASS_TABLES: Dict[str, Dict[str, Any]] = {
    "Knight": getattr(tables, "knight_table", None),
    "Mage": getattr(tables, "mage_table", None),
    "Archer": getattr(tables, "archer_table", None),
    "Priest": getattr(tables, "priest_table", None),
    "Necromancien": getattr(tables, "necromancien_table", None),
    # Creatures
    "Goblin": getattr(tables, "goblin_table", None),
    "Orc": getattr(tables, "orc_table", None),
    "DragonWhelp": getattr(tables, "dragon_whelp_table", None),
}


def _read_json(maybe_path: str | Path | Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(maybe_path, (str, Path)):
        p = Path(maybe_path)
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    elif isinstance(maybe_path, Mapping):
        return dict(maybe_path)
    else:
        raise TypeError("Expected file path or mapping for overrides")


def _deep_update_dict(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_update_dict(target[k], v)
        else:
            target[k] = v


def apply_class_overrides(overrides: str | Path | Mapping[str, Any]) -> Dict[str, Any]:
    data = _read_json(overrides)
    applied: Dict[str, Any] = {}
    for class_name, patch in data.items():
        table = CLASS_TABLES.get(class_name)
        if not isinstance(table, dict):
            continue
        if isinstance(patch, dict):
            _deep_update_dict(table, patch)
            applied[class_name] = True
    return applied


def apply_skill_overrides(overrides: str | Path | Mapping[str, Any]) -> Dict[str, Any]:
    """
    Structure example:
    {
      "Knight": {
        "level 1": {
          "Sword Slash": {
            "energie_cost": 7,
            "cooldown": 1,
            "effects": {
              "damage": {"value": 12}
            }
          }
        }
      }
    }
    """
    data = _read_json(overrides)
    applied: Dict[str, Any] = {}

    for class_name, levels in data.items():
        table = CLASS_TABLES.get(class_name)
        if not isinstance(table, dict):
            continue
        class_skills = table.get("class_skills_dict")
        if not isinstance(class_skills, dict):
            continue

        for level_key, skills_patch in levels.items():
            level_skills = class_skills.get(level_key)
            if not isinstance(level_skills, dict):
                continue
            for skill_name, patch in skills_patch.items():
                skill_obj = level_skills.get(skill_name)
                if not isinstance(skill_obj, Skill):
                    continue
                # Simple attributes
                for attr in ("energie_cost", "cooldown", "description"):
                    if attr in patch:
                        setattr(skill_obj, attr, patch[attr])
                # Effects updates
                effects_patch = patch.get("effects")
                if isinstance(effects_patch, dict):
                    for eff_key, eff_vals in effects_patch.items():
                        eff_obj = skill_obj.effects.get(eff_key)
                        if isinstance(eff_obj, SkillEffect) and isinstance(eff_vals, dict):
                            if "value" in eff_vals and eff_vals["value"] is not None:
                                eff_obj.value = eff_vals["value"]
                            if "duration" in eff_vals and eff_vals["duration"] is not None:
                                eff_obj.duration = eff_vals["duration"]
                            if "name" in eff_vals and eff_vals["name"]:
                                eff_obj.name = eff_vals["name"]
                applied[f"{class_name}:{level_key}:{skill_name}"] = True

    return applied
