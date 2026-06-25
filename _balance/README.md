# Balance Module (Tuning)

This folder centralizes data-driven tuning for classes and skills (heroic-fantasy theme). Use JSON overrides to tweak stats, energies, advantages, and skill parameters without editing source tables.

- Do not auto-import this module. Call its loader functions explicitly at app startup.
- Keep overrides small and explicit: only set what you want to change.

## Files
- loader.py: functions to apply overrides to in-memory class tables and skill objects.
- samples/classes_override.json: example class overrides (base stats, advantages, etc.).
- samples/skills_override.json: example skill overrides (cost, cooldown, effects values/durations).
- simulator.py: run class-vs-class simulations and compute metrics.
- run_simulation.py: CLI entry to run the full matrix and write a JSON report.

## Usage (example)
```python
from jeuxRPG._balance.loader import apply_class_overrides, apply_skill_overrides

# Apply a set of class tweaks from JSON files
apply_class_overrides("jeuxRPG/_balance/samples/classes_override.json")
apply_skill_overrides("jeuxRPG/_balance/samples/skills_override.json")
```

### Enable via environment (recommended for runtime)
- Set `BOTKIRITO_BALANCE_ENABLE=1` to auto-apply default set `jeuxRPG/_balance/sets/v1_*.json` at app startup (loaded in data.py).
- Optionally override paths:
	- `BOTKIRITO_BALANCE_CLASSES=path/to/classes.json`
	- `BOTKIRITO_BALANCE_SKILLS=path/to/skills.json`

### Run simulations (matrix)
- Quick run and report:
	```powershell
	$env:BOTKIRITO_BALANCE_MATCHES="10"
	.venv/Scripts/python.exe -m jeuxRPG._balance.run_simulation
	```
- Outputs a JSON report to `.data/balance/report.json` by default. Override with `BOTKIRITO_BALANCE_REPORT`.

### Report content
- `pairs`: per-pair duel aggregates (wins, rounds, damage dealt, hp lost, energy spent, skill usage).
- `summary`: per-class aggregates with `win_rate`, `damage_per_energy`, and `avg_rounds`.
- `analysis.hints`: simple suggestions based on thresholds.

## Advanced modes

### One vs All
Run one class against all others:
```powershell
$env:BOTKIRITO_BALANCE_MODE="one_vs_all"
$env:BOTKIRITO_CLASS="Knight"
$env:BOTKIRITO_BALANCE_MATCHES="25"
.venv/Scripts/python.exe -m jeuxRPG._balance.run_simulation
```

### Skill-focused duel with advantage modes
Force a specific skill to be used and test advantage scenarios:
```powershell
$env:BOTKIRITO_BALANCE_MODE="skill_duel"
$env:BOTKIRITO_CLASS_A="Knight"
$env:BOTKIRITO_CLASS_B="Mage"
$env:BOTKIRITO_SKILL_NAME="Sword Slash"
# advantage modes: neutral | weak | resist | all
$env:BOTKIRITO_ADVANTAGE_MODE="all"
# force who uses the skill: A | B | both
$env:BOTKIRITO_FORCE_SIDE="A"
.venv/Scripts/python.exe -m jeuxRPG._balance.run_simulation
```
This writes a JSON report containing per-mode results (neutral/weak/resist) when `ADVANTAGE_MODE=all`.

## Scope
- Classes: base_stats, upgrade_stats, advantage, class_type (use existing enum names), and optionally class_skills_dict structure (with caution).
- Skills: attributes like energie_cost, cooldown, description; per-effect fields: value, duration, name.

## Notes
- No runtime side effects at import: the loader only runs when called.
- Tests should remain green if you refrain from auto-applying overrides during import.
- Prefer JSON to avoid extra dependencies.
