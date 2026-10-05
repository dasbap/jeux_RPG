import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
coverage = json.loads((root / "coverage.json").read_text())
coverage["files"] = {name.replace("\\", "/"): data for name, data in coverage["files"].items()}
rows = []
for path in sorted((root / "jeuxRPG").rglob("*.py")):
    relative = path.relative_to(root).as_posix()
    data = coverage["files"].get(relative, {})
    missing = set(data.get("missing_lines", []))
    executed = set(data.get("executed_lines", []))
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            lines = set(range(body[0].lineno, node.end_lineno + 1)) if body else set()
            hits = lines & executed
            misses = lines & missing
            doc = ast.get_docstring(node)
            role = doc.splitlines()[0] if doc else "Rôle non documenté"
            rows.append({"file": relative, "function": node.name, "line": node.lineno, "role": role, "executed_lines": len(hits), "missing_lines": len(misses)})
(root / "function-audit.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(rows)} fonctions recensées, {sum(row['executed_lines'] == 0 for row in rows)} sans ligne exécutée")
