from __future__ import annotations

import os
from pathlib import Path

import json
import argparse
from .simulator import (
    run_matrix_to_file,
    simulate_one_vs_all,
    simulate_skill_duel,
    simulate_tower,
    analyze_summary,
)
from .loader import apply_class_overrides, apply_skill_overrides


def _write(path: str, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Run balance simulations and write JSON reports")
    parser.add_argument("--mode", choices=["matrix", "one_vs_all", "skill_duel", "tower"], default="matrix")
    parser.add_argument("--matches", type=int, default=10)
    parser.add_argument("--out", default=".data/balance/report.json")
    parser.add_argument("--print-analysis", dest="print_analysis", action="store_true",
                        help="Print a human-readable analysis to stdout")

    # Optional overrides for class/skill definitions
    parser.add_argument("--class-overrides", dest="class_overrides", default=None,
                        help="Path to JSON with class table patches (e.g., base_stats.hp)")
    parser.add_argument("--skill-overrides", dest="skill_overrides", default=None,
                        help="Path to JSON with skill patches (effects, energy, cooldown)")

    # one_vs_all
    parser.add_argument("--class", dest="cls", help="Class name for one_vs_all mode")

    # skill_duel
    parser.add_argument("--class-a", dest="class_a")
    parser.add_argument("--class-b", dest="class_b")
    parser.add_argument("--skill", dest="skill_name")
    parser.add_argument("--adv", dest="adv_mode", default="neutral")
    parser.add_argument(
        "--force",
        dest="force_side",
        default="none",
        help="Who to force to use the skill: A, B, both, or none (default: none)"
    )
    parser.add_argument("--seed", dest="seed", type=int, default=None)

    # tower
    parser.add_argument("--tower-class", dest="tower_class", default="Knight")
    parser.add_argument("--difficulty", dest="difficulty", default="easy")
    parser.add_argument("--floors", dest="floors", type=int, default=20)
    parser.add_argument("--start-floor", dest="start_floor", type=int, default=1)
    parser.add_argument("--enemies-per-floor", dest="enemies_per_floor", type=int, default=1)
    parser.add_argument(
        "--resolution",
        dest="resolution",
        default="combat",
        choices=["combat", "reward_curve", "xp_curve", "forced"],
        help="combat runs real fights; reward_curve forces clears while awarding XP for level-curve checks.",
    )

    args = parser.parse_args()

    mode = (args.mode or "matrix").lower()
    matches = int(args.matches)
    out = args.out

    # Apply optional overrides if provided
    if args.class_overrides:
        try:
            applied = apply_class_overrides(args.class_overrides)
            if applied:
                print(f"[overrides] Applied class overrides for: {', '.join(sorted(applied.keys()))}")
        except Exception as e:
            print(f"[warn] Failed to apply class overrides: {e}")
    if args.skill_overrides:
        try:
            applied = apply_skill_overrides(args.skill_overrides)
            if applied:
                print(f"[overrides] Applied skill overrides: {len(applied)} changes")
        except Exception as e:
            print(f"[warn] Failed to apply skill overrides: {e}")

    if mode == "matrix":
        path = run_matrix_to_file(matches_per_pair=matches, out_path=out)
        print(f"Balance simulation complete -> {path}")
        if args.print_analysis:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summary = data.get("summary", {})
                analysis = data.get("analysis", {})
                print("\n=== Matrix Summary (win_rate, dmg/energy, avg_rounds) ===")
                for cls, s in summary.items():
                    wr = s.get("win_rate", 0.0)
                    dpe = s.get("damage_per_energy", 0.0)
                    avg_r = s.get("avg_rounds", 0.0)
                    print(f"- {cls}: {wr:.1%} | dpe={dpe:.2f} | rounds={avg_r:.2f}")
                hints = analysis.get("hints", []) if isinstance(analysis, dict) else analysis
                if hints:
                    print("\n=== Hints ===")
                    for h in hints:
                        print(f"- {h}")
            except Exception as e:
                print(f"[warn] Could not print analysis: {e}")
        return

    if mode == "tower":
        res = simulate_tower(
            class_name=args.tower_class,
            difficulty=args.difficulty,
            floors=args.floors,
            start_floor=args.start_floor,
            enemies_per_floor=args.enemies_per_floor,
            seed=args.seed,
            resolution=args.resolution,
        )
        _write(out, res)
        print(f"tower simulation complete -> {out}")
        if args.print_analysis:
            print("\n=== Tower Summary ===")
            print(
                f"- {res['class']} {res['difficulty']} {res['resolution']}: "
                f"floor {res['start_floor']}->{res['target_floor']}, "
                f"reached {res['reached_floor']}, level {res['start_level']}->{res['final_level']}"
            )
        return

    if mode == "one_vs_all":
        cls = args.cls
        if not cls:
            raise SystemExit("--class is required for one_vs_all")
        res = simulate_one_vs_all(cls, matches=matches)
        res["analysis"] = analyze_summary({cls: {
            "wins": sum(1 for v in res["vs"] if v["side_a"]["wins"] > v["side_b"]["wins"]),
            "losses": sum(1 for v in res["vs"] if v["side_b"]["wins"] > v["side_a"]["wins"]),
            "draws": sum(1 for v in res["vs"] if v["draws"] > 0),
            "damage_dealt": sum(v["side_a"]["damage_dealt"] for v in res["vs"]),
            "energy_spent": {},
            "rounds": sum(v["side_a"]["rounds"] for v in res["vs"]),
        }})
        _write(out, res)
        print(f"one_vs_all complete -> {out}")
        if args.print_analysis:
            try:
                total = len(res.get("vs", []))
                w = sum(1 for v in res.get("vs", []) if v["side_a"]["wins"] > v["side_b"]["wins"])
                l = sum(1 for v in res.get("vs", []) if v["side_b"]["wins"] > v["side_a"]["wins"])
                d = sum(1 for v in res.get("vs", []) if v["draws"] > 0)
                print("\n=== One vs All Summary ===")
                print(f"- total matchups: {total} | W-L-D: {w}-{l}-{d}")
                hints = res.get("analysis", {}).get("hints", [])
                if hints:
                    print("\n=== Hints ===")
                    for h in hints:
                        print(f"- {h}")
            except Exception as e:
                print(f"[warn] Could not print analysis: {e}")
        return

    if mode == "skill_duel":
        a = args.class_a
        b = args.class_b
        s = args.skill_name
        adv = args.adv_mode
        force_side = args.force_side
        seed = args.seed
        fs = (force_side or "NONE").strip().upper()
        forcing_enabled = fs not in {"NONE", "NO", "OFF"}
        if not (a and b):
            raise SystemExit("--class-a and --class-b are required for skill_duel")
        if forcing_enabled and not s:
            raise SystemExit("--skill is required when forcing is enabled. Use --force none to disable forcing.")
        res = simulate_skill_duel(a, b, s, matches=matches, advantage_mode=adv, force_side=force_side, seed=seed)
        _write(out, res)
        print(f"skill_duel complete -> {out}")
        if args.print_analysis:
            try:
                print("\n=== Skill Duel Summary ===")
                print(f"- Class A: {a} | Class B: {b} | Skill: {s or 'natural'}")
                for mode, d in res.get("modes", {}).items():
                    fights = max(1, int(d.get("fights", 0)))
                    wr = d.get("side_a", {}).get("wins", 0) / fights
                    rounds = d.get("side_a", {}).get("rounds", 0)
                    dmg_a = d.get("side_a", {}).get("damage_dealt", 0)
                    dmg_b = d.get("side_b", {}).get("damage_dealt", 0)
                    en_a = sum((d.get("side_a", {}).get("energy_spent", {}) or {}).values()) or 1
                    en_b = sum((d.get("side_b", {}).get("energy_spent", {}) or {}).values()) or 1
                    dpe_a = dmg_a / en_a
                    dpe_b = dmg_b / en_b
                    print(f"  * {mode}: win_rate={wr:.1%} | rounds={rounds} | dpe(A)={dpe_a:.2f} dpe(B)={dpe_b:.2f}")
            except Exception as e:
                print(f"[warn] Could not print analysis: {e}")
        return

    raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
