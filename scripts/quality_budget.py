"""Prevent measured complexity and coverage regressions without hiding legacy debt."""

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def duplicate_windows(baseline=None):
    """Exact AST windows of three statements, at least 20 AST nodes; no similarity claim."""
    locations = defaultdict(list)
    paths = (
        [
            Path(name)
            for name in subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", baseline, "jeuxRPG"], text=True
            ).splitlines()
            if name.endswith(".py")
        ]
        if baseline
        else sorted(Path("jeuxRPG").rglob("*.py"))
    )
    for path in paths:
        source = (
            subprocess.check_output(["git", "show", f"{baseline}:{path}"], text=True)
            if baseline
            else path.read_text()
        )
        tree = ast.parse(source)
        seen = set()
        for node in ast.walk(tree):
            for _, body in ast.iter_fields(node):
                if not isinstance(body, list) or not all(
                    isinstance(item, ast.stmt) for item in body
                ):
                    continue
                for index in range(len(body) - 2):
                    window = body[index : index + 3]
                    start, end = window[0].lineno, window[-1].end_lineno
                    if (
                        sum(1 for stmt in window for _ in ast.walk(stmt)) < 20
                        or (start, end) in seen
                    ):
                        continue
                    seen.add((start, end))
                    fingerprint = ast.dump(
                        ast.Module(body=window, type_ignores=[]),
                        include_attributes=False,
                    )
                    locations[fingerprint].append(f"{path}:{start}-{end}")
    groups = [items for items in locations.values() if len(items) > 1]
    return {
        "method": "exact AST / 3 statements / >=20 AST nodes, overlapping windows possible",
        "groups": len(groups),
        "extra_occurrences": sum(len(items) - 1 for items in groups),
        "locations": groups,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage")
    parser.add_argument("--inventory")
    parser.add_argument("--baseline")
    args = parser.parse_args()
    issues = []
    process = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format", "json", "jeuxRPG"],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode not in (0, 1):
        raise RuntimeError(process.stderr)
    current_lint = json.loads(process.stdout)
    if current_lint:
        issues.append(
            f"Lint: {len(current_lint)} diagnostics ; aucun diagnostic autorisé."
        )
    print(f"Lint: {len(current_lint)} diagnostics.")
    duplicates = duplicate_windows()
    if duplicates["groups"] > 22 or duplicates["extra_occurrences"] > 24:
        issues.append(
            "Duplication exacte supérieure au budget courant (22 groupes / 24 occurrences supplémentaires)."
        )
    if args.coverage:
        data = json.loads(Path(args.coverage).read_text())["totals"]
        lines = data["covered_lines"] / data["num_statements"] * 100
        branches = data["covered_branches"] / data["num_branches"] * 100
        print(f"Coverage: lines={lines:.2f}% branches={branches:.2f}%")
        if lines < 77 or branches < 70:
            issues.append(
                "Couverture minimale actuelle: 77% lignes / 70% branches; objectif futur 85/80."
            )
    if args.inventory:
        report = {
            "before": duplicate_windows(args.baseline) if args.baseline else None,
            "after": duplicate_windows(),
        }
        Path(args.inventory).write_text(json.dumps(report, indent=2) + "\n")
    if issues:
        raise SystemExit("\n".join(issues))
    print("Budgets respectes.")


if __name__ == "__main__":
    main()
