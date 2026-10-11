"""Compare path results and cold CPU cost with an explicit repository revision."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import time

from jeuxRPG.multiplayer import tactics


def measure(baseline):
    source = subprocess.check_output(
        ["git", "show", baseline + ":jeuxRPG/multiplayer/tactics.py"], text=True
    )
    tree = ast.parse(source)
    node = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "cached_path"
    )
    old = dict(vars(tactics))
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "<baseline-path>", "exec"),
        old,
    )
    functions = [old["cached_path"], tactics.cached_path]
    cases = []
    for preset in tactics.PRESETS.values():
        cover = tuple(tuple(p) for p in preset["cover"] + preset.get("blocked", []))
        points = [
            (x, y)
            for x in range(preset["width"])
            for y in range(preset["height"])
            if tactics.walkable(preset, (x, y))
        ]
        if points:
            for point in points[:: max(1, len(points) // 12)]:
                cases.append(
                    (preset["width"], preset["height"], cover, points[0], point)
                )
    timings, expected = [], None
    for function in functions:
        samples = []
        for _ in range(3):
            function.cache_clear()
            started = time.process_time()
            results = [function(*case) for case in cases]
            samples.append(time.process_time() - started)
            if expected is None:
                expected = results
            assert results == expected, "A route or tie-breaking decision changed"
        timings.append(min(samples))
    return {
        "baseline": baseline,
        "cases": len(cases),
        "identical": True,
        "cold_cpu_seconds": timings,
        "cpu_change_percent": round(100 * (timings[1] / timings[0] - 1), 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = measure(args.baseline)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
