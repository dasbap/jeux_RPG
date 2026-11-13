from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tokenize
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INCLUDE = ("*.py", "*.md", "pyproject.toml", "requirements*.txt")
MANIFEST_NAME = ".generated-pages.json"


@dataclass(frozen=True)
class Settings:
    root: Path
    output: Path
    include: tuple[str, ...]
    descriptions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        root = self.root.resolve()
        output = self.output.resolve()
        if not root.is_dir():
            raise ValueError(f"Project directory does not exist: {root}")
        if root == output or root.is_relative_to(output):
            raise ValueError(
                "The output must not be the project root or one of its parents."
            )
        patterns = tuple(pattern.replace("\\", "/") for pattern in self.include)
        if not patterns:
            raise ValueError("The allowlist must contain at least one include pattern.")
        for pattern in patterns:
            if (
                not pattern
                or pattern.startswith("/")
                or PureWindowsPath(pattern).drive
                or ".." in PurePosixPath(pattern).parts
            ):
                raise ValueError(
                    f"Include patterns must stay relative to the project: {pattern!r}"
                )
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "output", output)
        object.__setattr__(self, "include", patterns)


def load_settings(
    root: Path,
    output: Path | None = None,
    config: Path | None = None,
    include: list[str] | None = None,
) -> Settings:
    root = root.resolve()
    config_path = config if config is not None else root / "__doc__" / "docs.toml"
    values = {}
    if config is not None or config_path.exists():
        with config_path.open("rb") as source:
            document = tomllib.load(source)
        values = document.get("documentation", {})
        if not isinstance(values, dict):
            raise ValueError("[documentation] must be a TOML table.")
    allowed_keys = {"include", "output", "descriptions"}
    if unknown := values.keys() - allowed_keys:
        raise ValueError(
            f"Unknown documentation settings: {', '.join(sorted(unknown))}"
        )
    patterns = (
        include if include is not None else values.get("include", list(DEFAULT_INCLUDE))
    )
    if not isinstance(patterns, list) or not all(
        isinstance(item, str) for item in patterns
    ):
        raise ValueError("documentation.include must be a list of glob patterns.")
    destination = values.get("output", "__doc__")
    if not isinstance(destination, str) or not destination:
        raise ValueError("documentation.output must be a nonempty path.")
    descriptions = values.get("descriptions", {})
    if not isinstance(descriptions, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in descriptions.items()
    ):
        raise ValueError("documentation.descriptions must map names or paths to text.")
    return Settings(
        root,
        output if output is not None else root / destination,
        tuple(patterns),
        descriptions,
    )


def select_files(settings: Settings) -> tuple[list[Path], list[str]]:
    """Select explicit files, rejecting symbolic links and the generated output."""
    selected = set()
    unmatched = []
    for pattern in settings.include:
        matched = False
        for path in settings.root.glob(pattern):
            relative = path.relative_to(settings.root)
            if any(
                parent.is_symlink()
                for parent in (
                    path,
                    *[settings.root / ancestor for ancestor in relative.parents],
                )
            ):
                continue
            if not path.is_file() or path.resolve().is_relative_to(settings.output):
                continue
            selected.add(path)
            matched = True
        if not matched:
            unmatched.append(pattern)
    return sorted(
        selected, key=lambda path: path.relative_to(settings.root).as_posix()
    ), unmatched


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


def write_text(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")


def infer_class_role(symbol_name: str) -> str:
    lower_name = symbol_name.lower()

    suffixes = {
        "mixin": "Provides reusable behavior to be composed into another class.",
        "factory": "Builds and initializes domain objects.",
        "controller": "Coordinates workflow and orchestrates game flow logic.",
        "manager": "Manages state and lifecycle for a subsystem.",
        "skill": "Represents a skill definition and behavior.",
        "character": "Represents a character entity in the game domain.",
    }
    for suffix, role in suffixes.items():
        if lower_name.endswith(suffix):
            return role
    if lower_name.startswith("test"):
        return "Groups automated test scenarios for related behavior."
    return "Defines a domain model or behavior container."


def infer_role_from_name(symbol_name: str, symbol_kind: str) -> str:
    if symbol_kind == "class":
        return infer_class_role(symbol_name)
    lower_name = symbol_name.lower()
    rules = (
        (
            lower_name == "__init__",
            "Initializes object state and validates constructor inputs.",
        ),
        (
            lower_name == "__new__",
            "Allocates and prepares a new instance before initialization.",
        ),
        (
            lower_name == "__str__",
            "Builds a human-readable string representation of the object.",
        ),
        (
            lower_name == "__repr__",
            "Builds a developer-oriented representation of the object.",
        ),
        (
            lower_name.startswith("test_"),
            "Verifies expected behavior through an automated test case.",
        ),
        (
            lower_name == "wrapped",
            "Wraps the original callable to inject additional behavior.",
        ),
        (lower_name.startswith("get_"), "Returns or retrieves data from object state."),
        (lower_name.endswith("_path"), "Resolves and returns a filesystem path."),
        (lower_name.startswith("set_"), "Updates object state with a provided value."),
        (
            lower_name.startswith("clear_"),
            "Clears cached or temporary state for the module.",
        ),
        (lower_name.startswith("reset_"), "Resets state to a default baseline value."),
        (
            lower_name.startswith("has_") or lower_name.startswith("is_"),
            "Evaluates a condition and returns a boolean result.",
        ),
        (
            lower_name.startswith("can_"),
            "Checks whether an action is allowed in the current context.",
        ),
        (
            lower_name.startswith("add_"),
            "Adds an element to a collection or state container.",
        ),
        (
            lower_name.startswith("remove_") or lower_name.startswith("delete_"),
            "Removes an element from a collection or persisted state.",
        ),
        (
            lower_name.startswith("create_") or lower_name.startswith("build_"),
            "Creates and initializes a new object or resource.",
        ),
        (lower_name.startswith("load_"), "Loads data from storage or resource files."),
        (lower_name.startswith("save_"), "Persists data to storage."),
        (
            lower_name.startswith("update_"),
            "Updates existing state based on new inputs.",
        ),
        (
            lower_name.startswith("validate_"),
            "Validates input or state against expected constraints.",
        ),
        (lower_name.startswith("consume_"), "Consumes a resource from current state."),
        (
            "register" in lower_name,
            "Registers an object in a shared registry or collection.",
        ),
        (
            lower_name.startswith("execute") or lower_name.startswith("_execute"),
            "Executes the core action logic for this operation.",
        ),
        ("cooldown" in lower_name, "Manages cooldown state for action availability."),
        ("resolver" in lower_name, "Resolves references into concrete domain objects."),
        (
            lower_name.startswith("gain_") or lower_name.startswith("restore_"),
            "Restores or increases a resource value.",
        ),
        (lower_name.startswith("change_"), "Replaces one state element with another."),
        (
            lower_name.startswith("apply_"),
            "Applies an effect, rule, or transformation.",
        ),
        (
            lower_name.startswith("calculate_") or lower_name.startswith("compute_"),
            "Computes a derived value from current inputs and state.",
        ),
        (lower_name == "main", "Program entry point that triggers execution flow."),
    )
    return next(
        (role for matches, role in rules if matches),
        "Implements a specific behavior in the module.",
    )


def infer_role_from_docstring(docstring: str | None, fallback: str) -> str:
    if not docstring:
        return fallback
    first_line = docstring.strip().splitlines()[0].strip()
    if not first_line:
        return fallback
    if first_line.endswith("."):
        return first_line
    return f"{first_line}."


def extract_python_symbols(
    src_file: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        with tokenize.open(src_file) as source:
            tree = ast.parse(source.read(), filename=str(src_file))
    except (OSError, SyntaxError, UnicodeError):
        return [], []

    classes: list[dict[str, str]] = []
    functions: list[dict[str, str]] = []

    def qualify_name(scope: list[str], name: str) -> str:
        if not scope:
            return name
        return ".".join([*scope, name])

    def decorate_function_name(
        qualified_name: str, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "property":
                return f"{qualified_name} (property)"
            if isinstance(decorator, ast.Attribute) and decorator.attr in {
                "setter",
                "deleter",
            }:
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
            classes.append(
                {"name": qualified_name, "role": class_role, "line": str(node.lineno)}
            )

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
            functions.append(
                {"name": display_name, "role": function_role, "line": str(node.lineno)}
            )

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
            functions.append(
                {"name": display_name, "role": function_role, "line": str(node.lineno)}
            )

            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

    SymbolCollector().visit(tree)

    return classes, functions


def markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


class Documentation:
    """Render every page and the tree from a single allowlisted snapshot."""

    def __init__(self, settings: Settings, files: list[Path]) -> None:
        self.settings = settings
        self.files = files
        self.pages: dict[str, str] = {}
        directories = {settings.root}
        for path in files:
            directories.update(
                parent
                for parent in path.parents
                if parent.is_relative_to(settings.root)
            )
        self.children: dict[Path, list[Path]] = {
            directory: [] for directory in directories
        }
        for path in directories | set(files):
            if path != settings.root:
                self.children[path.parent].append(path)
        for children in self.children.values():
            children.sort(
                key=lambda path: (
                    path not in directories,
                    path.name.casefold(),
                    path.name,
                )
            )

    def relative(self, path: Path) -> str:
        return path.relative_to(self.settings.root).as_posix()

    def page_for(self, path: Path) -> Path:
        relative = "" if path == self.settings.root else self.relative(path)
        if path in self.children:
            return Path("mirror") / relative / "README.md"
        return Path("mirror") / (relative + ".md")

    def link(self, source_page: Path, target: Path) -> str:
        start = (self.settings.output / source_page).parent
        try:
            relative = os.path.relpath(target, start)
        except ValueError:
            # Windows cannot form a relative path between two different drives.
            return target.resolve().as_uri()
        return quote(Path(relative).as_posix(), safe="/")

    def description(self, path: Path) -> str:
        custom = self.settings.descriptions
        return custom.get(
            self.relative(path),
            custom.get(path.name, describe(path.name, path in self.children)),
        )

    def add(self, page: Path, lines: list[str]) -> None:
        self.pages[page.as_posix()] = "\n".join(lines) + "\n"

    def tree_lines(self, directory: Path, prefix: str = "") -> list[str]:
        lines = []
        children = self.children[directory]
        for index, child in enumerate(children):
            last = index == len(children) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{child.name}")
            if child in self.children:
                lines.extend(
                    self.tree_lines(child, prefix + ("    " if last else "│   "))
                )
        return lines

    def directory_page(self, directory: Path) -> None:
        page = self.page_for(directory)
        section = (
            "/" if directory == self.settings.root else "/" + self.relative(directory)
        )
        lines = [
            f"# Directory: `{section}`",
            "",
            "## Description",
            "",
            "Root project directory."
            if directory == self.settings.root
            else self.description(directory),
            "",
            "## Contents",
            "",
            "| Name | Type | Description |",
            "|---|---|---|",
        ]
        for child in self.children[directory]:
            target = self.settings.output / self.page_for(child)
            name = markdown_cell(child.name)
            kind = "Directory" if child in self.children else "File"
            lines.append(
                f"| [{name}]({self.link(page, target)}) | {kind} | {markdown_cell(self.description(child))} |"
            )
        if not self.children[directory]:
            lines.extend(["", "No files match the allowlist."])
        self.add(page, lines)

    def file_page(self, source: Path) -> None:
        page = self.page_for(source)
        source_link = self.link(page, source)
        lines = [
            f"# File: `/{self.relative(source)}`",
            "",
            f"[View source]({source_link})",
            "",
            "## Description",
            "",
            self.description(source),
            "",
        ]
        if source.suffix.lower() == ".py":
            classes, functions = extract_python_symbols(source)
            for title, symbols in (("Classes", classes), ("Functions", functions)):
                if not symbols:
                    continue
                lines.extend(
                    [
                        f"## {title}",
                        "",
                        "| Symbol | Role | Source line |",
                        "|---|---|---|",
                    ]
                )
                for symbol in symbols:
                    line = symbol["line"]
                    lines.append(
                        f"| `{markdown_cell(symbol['name'])}` | {markdown_cell(symbol['role'])} | [{line}]({source_link}#L{line}) |"
                    )
                lines.append("")
        self.add(page, lines)

    def render(self) -> dict[str, str]:
        for directory in sorted(self.children):
            self.directory_page(directory)
        for source in self.files:
            self.file_page(source)
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.add(
            Path("TREE.md"),
            [
                "# Project Tree",
                "",
                f"_Generated on {timestamp}_",
                "",
                "```text",
                self.settings.root.name,
                *self.tree_lines(self.settings.root),
                "```",
                "",
            ],
        )
        self.add(
            Path("README.md"),
            [
                "# Documentation Index",
                "",
                f"_Generated on {timestamp}_",
                "",
                "- [Project Tree](./TREE.md)",
                "- [Mirrored Structure](./mirror/README.md)",
                "",
                f"Documented source files: {len(self.files)}.",
                "",
                "Only files matching the configured allowlist are documented.",
                "",
                "## Include patterns",
                "",
                *[f"- `{pattern}`" for pattern in self.settings.include],
                "",
            ],
        )
        return self.pages


def write_pages(settings: Settings, pages: dict[str, str]) -> list[str]:
    """Remove stale owned pages only when their generated content is unchanged."""
    manifest = settings.output / MANIFEST_NAME
    if manifest.is_symlink() or not manifest.resolve().is_relative_to(settings.output):
        raise ValueError(
            "The generated-page manifest must stay inside the output directory."
        )
    previous = {}
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(previous, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in previous.items()
        ):
            raise ValueError(f"Invalid generated-page manifest: {manifest}")
    preserved = []
    for name in previous.keys() - pages.keys():
        path = settings.output / name
        if path.is_symlink() or not path.resolve().is_relative_to(settings.output):
            raise ValueError(f"Generated page escapes the output directory: {name}")
        if path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() == previous[name]:
                path.unlink()
            else:
                preserved.append(name)
    for name, content in pages.items():
        path = settings.output / name
        if path.is_symlink() or not path.resolve().is_relative_to(settings.output):
            raise ValueError(f"Generated page escapes the output directory: {name}")
        write_text(path, content)
    hashes = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in pages.items()
    }
    write_text(manifest, json.dumps(hashes, ensure_ascii=False, indent=2) + "\n")
    return preserved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Markdown documentation from a configurable file allowlist."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Project root (defaults to this repository).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory, relative to the project root unless absolute.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="TOML settings file (default: ROOT/__doc__/docs.toml).",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Include glob, repeatable; replaces the configured allowlist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected files without writing documentation.",
    )
    args = parser.parse_args(argv)
    try:
        output = args.root / args.output if args.output is not None else None
        settings = load_settings(args.root, output, args.config, args.include)
        files, unmatched = select_files(settings)
        if args.dry_run:
            for path in files:
                print(path.relative_to(settings.root).as_posix())
        else:
            pages = Documentation(settings, files).render()
            for name in write_pages(settings, pages):
                print(f"Preserved manually edited stale page: {name}")
            print(
                f"Documentation generated in: {settings.output} ({len(files)} files, {len(pages)} pages)"
            )
        for pattern in unmatched:
            print(f"No files matched: {pattern}")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
