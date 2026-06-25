from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOC_ROOT = ROOT / "__doc__"
MIRROR_ROOT = DOC_ROOT / "mirror"

EXCLUDE_DIRS = {
    "__doc__",
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

EXCLUDE_FILES = {
    ".DS_Store",
}

KNOWN_DESCRIPTIONS = {
    "__init__.py": "Package initializer.",
    "main.py": "Main application entry point.",
    "config.py": "Configuration values and environment setup.",
    "requirements.txt": "Project dependencies.",
    "README.md": "Project overview and usage instructions.",
    "pytest.ini": "Pytest configuration file.",
    "_class": "Domain classes: characters, mobs, skills, places, and stats.",
    "_core": "Core game logic, controllers, factories, and save system.",
    "_function": "Functional helpers grouped by feature.",
    "_balance": "Simulation and balancing tools.",
    "i18n": "Localization resources.",
    "test": "Automated test suite.",
}

FRENCH_HINTS = {
    "retourne",
    "charge",
    "sauvegarde",
    "chemin",
    "données",
    "dossier",
    "gère",
    "résout",
    "compétence",
    "dégâts",
    "soin",
    "résurrection",
    "pnj",
    "fichier",
    "classe",
    "méthode",
    "test",
    "enregistre",
    "retourne",
    "depuis",
    "avec",
    "pour",
    "sans",
    "erreur",
}

ENGLISH_HINTS = {
    "get",
    "set",
    "check",
    "create",
    "load",
    "save",
    "update",
    "initialize",
    "return",
    "compute",
    "apply",
    "validate",
    "restore",
    "remove",
    "add",
    "translate",
    "clear",
    "build",
    "execute",
    "test",
    "manager",
    "character",
    "skill",
}


def describe(name: str, is_dir: bool) -> str:
    if name in KNOWN_DESCRIPTIONS:
        return KNOWN_DESCRIPTIONS[name]

    lower_name = name.lower()

    if is_dir:
        if lower_name.startswith("_"):
            return "Internal module namespace."
        if "cache" in lower_name:
            return "Cache directory."
        if "sample" in lower_name:
            return "Sample data used for tests or demos."
        if "set" in lower_name:
            return "Data sets for configuration or simulation."
        if "translation" in lower_name:
            return "Localization translation resources."
        return "Directory containing related project resources."

    if lower_name.endswith(".py"):
        return "Python source file."
    if lower_name.endswith(".md"):
        return "Markdown documentation file."
    if lower_name.endswith(".bat"):
        return "Windows batch script for automation."
    if lower_name.endswith(".ini"):
        return "Initialization/configuration file."
    if lower_name.startswith("."):
        return "Hidden configuration file."
    return "Project file."


def iter_children(directory: Path) -> list[Path]:
    children: list[Path] = []
    for child in directory.iterdir():
        if child.name in EXCLUDE_FILES:
            continue
        if child.is_dir() and child.name in EXCLUDE_DIRS:
            continue
        children.append(child)

    return sorted(children, key=lambda item: (item.is_file(), item.name.lower()))


def build_tree_lines(root: Path, prefix: str = "") -> list[str]:
    lines: list[str] = []
    children = iter_children(root)

    for index, child in enumerate(children):
        connector = "└── " if index == len(children) - 1 else "├── "
        lines.append(f"{prefix}{connector}{child.name}")

        if child.is_dir():
            extension = "    " if index == len(children) - 1 else "│   "
            lines.extend(build_tree_lines(child, prefix + extension))

    return lines


def write_text(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def relative_path(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def doc_path_for_directory(src_dir: Path) -> Path:
    if src_dir == ROOT:
        return MIRROR_ROOT / "README.md"
    return MIRROR_ROOT / relative_path(src_dir) / "README.md"


def doc_path_for_file(src_file: Path) -> Path:
    return MIRROR_ROOT / (relative_path(src_file) + ".md")


def infer_role_from_name(symbol_name: str, symbol_kind: str) -> str:
    lower_name = symbol_name.lower()

    if symbol_kind == "class":
        if lower_name.endswith("mixin"):
            return "Provides reusable behavior to be composed into another class."
        if lower_name.endswith("factory"):
            return "Builds and initializes domain objects."
        if lower_name.endswith("controller"):
            return "Coordinates workflow and orchestrates game flow logic."
        if lower_name.endswith("manager"):
            return "Manages state and lifecycle for a subsystem."
        if lower_name.endswith("skill"):
            return "Represents a skill definition and behavior."
        if lower_name.endswith("character"):
            return "Represents a character entity in the game domain."
        if lower_name.startswith("test"):
            return "Groups automated test scenarios for related behavior."
        return "Defines a domain model or behavior container."

    if lower_name == "__init__":
        return "Initializes object state and validates constructor inputs."
    if lower_name == "__new__":
        return "Allocates and prepares a new instance before initialization."
    if lower_name == "__str__":
        return "Builds a human-readable string representation of the object."
    if lower_name == "__repr__":
        return "Builds a developer-oriented representation of the object."
    if lower_name.startswith("test_"):
        return "Verifies expected behavior through an automated test case."
    if lower_name == "wrapped":
        return "Wraps the original callable to inject additional behavior."
    if lower_name.startswith("get_"):
        return "Returns or retrieves data from object state."
    if lower_name.endswith("_path"):
        return "Resolves and returns a filesystem path."
    if lower_name.startswith("set_"):
        return "Updates object state with a provided value."
    if lower_name.startswith("clear_"):
        return "Clears cached or temporary state for the module."
    if lower_name.startswith("reset_"):
        return "Resets state to a default baseline value."
    if lower_name.startswith("has_") or lower_name.startswith("is_"):
        return "Evaluates a condition and returns a boolean result."
    if lower_name.startswith("can_"):
        return "Checks whether an action is allowed in the current context."
    if lower_name.startswith("add_"):
        return "Adds an element to a collection or state container."
    if lower_name.startswith("remove_") or lower_name.startswith("delete_"):
        return "Removes an element from a collection or persisted state."
    if lower_name.startswith("create_") or lower_name.startswith("build_"):
        return "Creates and initializes a new object or resource."
    if lower_name.startswith("load_"):
        return "Loads data from storage or resource files."
    if lower_name.startswith("save_"):
        return "Persists data to storage."
    if lower_name.startswith("update_"):
        return "Updates existing state based on new inputs."
    if lower_name.startswith("validate_"):
        return "Validates input or state against expected constraints."
    if lower_name.startswith("consume_"):
        return "Consumes a resource from current state."
    if "register" in lower_name:
        return "Registers an object in a shared registry or collection."
    if lower_name.startswith("execute") or lower_name.startswith("_execute"):
        return "Executes the core action logic for this operation."
    if "cooldown" in lower_name:
        return "Manages cooldown state for action availability."
    if "resolver" in lower_name:
        return "Resolves references into concrete domain objects."
    if lower_name.startswith("gain_") or lower_name.startswith("restore_"):
        return "Restores or increases a resource value."
    if lower_name.startswith("change_"):
        return "Replaces one state element with another."
    if lower_name.startswith("apply_"):
        return "Applies an effect, rule, or transformation."
    if lower_name.startswith("calculate_") or lower_name.startswith("compute_"):
        return "Computes a derived value from current inputs and state."
    if lower_name == "main":
        return "Program entry point that triggers execution flow."
    return "Implements a specific behavior in the module."


def is_probably_french(text: str) -> bool:
    lower_text = text.lower()
    token_hits = sum(1 for token in FRENCH_HINTS if token in lower_text)
    accented_hits = sum(1 for char in lower_text if char in "éèêàùâîôçëïü")
    return token_hits >= 1 or accented_hits >= 2


def is_probably_english(text: str) -> bool:
    lower_text = text.lower()
    if is_probably_french(lower_text):
        return False
    english_hits = sum(1 for token in ENGLISH_HINTS if token in lower_text)
    return english_hits >= 1


def infer_role_from_docstring(docstring: str | None, fallback: str) -> str:
    if not docstring:
        return fallback
    first_line = docstring.strip().splitlines()[0].strip()
    if not first_line:
        return fallback
    if not is_probably_english(first_line):
        return fallback
    if first_line.endswith("."):
        return first_line
    return f"{first_line}."


def extract_python_symbols(src_file: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        source = src_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = src_file.read_text(encoding="latin-1")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    classes: list[dict[str, str]] = []
    functions: list[dict[str, str]] = []

    def qualify_name(scope: list[str], name: str) -> str:
        if not scope:
            return name
        return ".".join([*scope, name])

    def decorate_function_name(qualified_name: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "property":
                return f"{qualified_name} (property)"
            if isinstance(decorator, ast.Attribute) and decorator.attr in {"setter", "deleter"}:
                return f"{qualified_name} ({decorator.attr})"
        return qualified_name

    class SymbolCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            qualified_name = qualify_name(self.scope, node.name)
            class_role = infer_role_from_docstring(
                ast.get_docstring(node),
                infer_role_from_name(node.name, symbol_kind="class"),
            )
            classes.append({"name": qualified_name, "role": class_role})

            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            qualified_name = qualify_name(self.scope, node.name)
            display_name = decorate_function_name(qualified_name, node)
            function_role = infer_role_from_docstring(
                ast.get_docstring(node),
                infer_role_from_name(node.name, symbol_kind="function"),
            )
            functions.append({"name": display_name, "role": function_role})

            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            qualified_name = qualify_name(self.scope, node.name)
            display_name = decorate_function_name(qualified_name, node)
            function_role = infer_role_from_docstring(
                ast.get_docstring(node),
                infer_role_from_name(node.name, symbol_kind="function"),
            )
            functions.append({"name": display_name, "role": function_role})

            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

    SymbolCollector().visit(tree)

    return classes, functions


def generate_directory_doc(src_dir: Path) -> None:
    children = iter_children(src_dir)
    section = "/" if src_dir == ROOT else f"/{relative_path(src_dir)}"

    lines = [
        f"# Directory: `{section}`",
        "",
        "## Description",
        "",
        "Root project directory." if src_dir == ROOT else describe(src_dir.name, is_dir=True),
        "",
        "## Contents",
        "",
        "| Name | Type | Description |",
        "|---|---|---|",
    ]

    for child in children:
        child_type = "Directory" if child.is_dir() else "File"
        lines.append(f"| `{child.name}` | {child_type} | {describe(child.name, child.is_dir())} |")

    lines.append("")
    write_text(doc_path_for_directory(src_dir), "\n".join(lines))


def generate_file_doc(src_file: Path) -> None:
    section = f"/{relative_path(src_file)}"
    classes: list[dict[str, str]] = []
    functions: list[dict[str, str]] = []

    if src_file.suffix.lower() == ".py":
        classes, functions = extract_python_symbols(src_file)

    if classes or functions:
        role_line = "Defines executable behavior through the symbols listed below."
    else:
        role_line = "Supports project structure and configuration for this module."

    lines = [
        f"# File: `{section}`",
        "",
        "## Description",
        "",
        describe(src_file.name, is_dir=False),
        "",
        "## Role",
        "",
        role_line,
        "",
    ]

    if classes:
        lines.extend([
            "## Classes",
            "",
            "| Class | Role |",
            "|---|---|",
        ])
        for class_symbol in classes:
            lines.append(f"| `{class_symbol['name']}` | {class_symbol['role']} |")
        lines.append("")

    if functions:
        lines.extend([
            "## Functions",
            "",
            "| Function | Role |",
            "|---|---|",
        ])
        for function_symbol in functions:
            lines.append(f"| `{function_symbol['name']}` | {function_symbol['role']} |")
        lines.append("")

    write_text(doc_path_for_file(src_file), "\n".join(lines))


def walk_paths(root: Path):
    yield root
    for child in iter_children(root):
        if child.is_dir():
            yield from walk_paths(child)
        else:
            yield child


def now_utc_string() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_index_and_tree() -> None:
    tree_lines = [ROOT.name] + build_tree_lines(ROOT)

    tree_markdown = "\n".join(
        [
            "# Project Tree",
            "",
            f"_Generated on {now_utc_string()}_",
            "",
            "```text",
            *tree_lines,
            "```",
            "",
        ]
    )
    write_text(DOC_ROOT / "TREE.md", tree_markdown)

    index_markdown = "\n".join(
        [
            "# Documentation Index",
            "",
            f"_Generated on {now_utc_string()}_",
            "",
            "- [Project Tree](./TREE.md)",
            "- [Mirrored Structure](./mirror/README.md)",
            "",
            "The `mirror` folder reproduces the project tree in Markdown.",
            "Each directory has a `README.md`, and each file has a dedicated `*.md` page.",
            "",
        ]
    )
    write_text(DOC_ROOT / "README.md", index_markdown)


def main() -> None:
    MIRROR_ROOT.mkdir(parents=True, exist_ok=True)

    for path in walk_paths(ROOT):
        if path == DOC_ROOT:
            continue

        if path.is_dir():
            if path.name in EXCLUDE_DIRS and path != ROOT:
                continue
            generate_directory_doc(path)
        else:
            if path.name in EXCLUDE_FILES:
                continue
            generate_file_doc(path)

    generate_index_and_tree()
    print(f"Documentation generated in: {DOC_ROOT}")


if __name__ == "__main__":
    main()
