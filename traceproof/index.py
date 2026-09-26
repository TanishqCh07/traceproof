"""Repository indexer — builds a symbol table and test index from a Python codebase.

Uses the ``ast`` module for static analysis; no code is imported or executed.

For each Python file (skipping .venv, __pycache__ and hidden directories) the
indexer collects:
  - Module-level constants (simple assignments whose value is a literal).
  - Top-level and nested functions/methods (with docstrings).
  - Classes (with docstrings).
  - Pytest test functions (``test_*``), including the string literals and names
    they reference in ``assert`` statements and ``pytest.raises`` calls.
  - Inline comments that mention a requirement ID (e.g. ``# PF-003``).

All paths returned are relative to the repo root.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_ID_PATTERN = re.compile(r"\b[A-Z]{2,5}-\d{3}\b")

# Directories to skip unconditionally
_SKIP_DIRS = {"__pycache__", ".venv", "venv", ".git", ".tox", ".mypy_cache", "node_modules"}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class SymbolEntry:
    """A code symbol (function, class, or constant) found in the repo."""

    name: str
    kind: str           # "function" | "class" | "constant" | "method"
    path: str           # repo-relative path
    line: int
    docstring: str = ""
    value: str = ""     # for constants: string representation of the literal value
    req_ids: list[str] = field(default_factory=list)   # IDs mentioned in nearby comments


@dataclass
class TestEntry:
    """A pytest test function found in the repo."""

    name: str
    path: str           # repo-relative path
    line: int
    node: str           # pytest node id, e.g. "tests/test_foo.py::test_bar"
    asserted_literals: list[str] = field(default_factory=list)  # string/int literals in asserts
    req_ids: list[str] = field(default_factory=list)            # IDs mentioned in name or comments


@dataclass
class RepoIndex:
    """Full index of a repository."""

    symbols: list[SymbolEntry] = field(default_factory=list)
    tests: list[TestEntry] = field(default_factory=list)

    def symbols_by_name(self, name: str) -> list[SymbolEntry]:
        """Return all symbols whose name exactly matches *name*."""
        return [s for s in self.symbols if s.name == name]

    def tests_mentioning(self, req_id: str) -> list[TestEntry]:
        """Return all tests that mention *req_id* in their name or comments."""
        return [t for t in self.tests if req_id in t.req_ids]


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _literal_value(node: ast.expr) -> str | None:
    """Return a compact string representation of a literal AST node, or None."""
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Call):
        # e.g. timedelta(days=60)
        func = ast.unparse(node) if hasattr(ast, "unparse") else None
        return func
    if hasattr(ast, "unparse"):
        return ast.unparse(node)
    return None


def _collect_string_literals(node: ast.AST) -> list[str]:
    """Walk *node* and collect all string constant values."""
    results: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            results.append(child.value)
        elif isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
            results.append(str(child.value))
    return results


def _extract_req_ids_from_text(text: str) -> list[str]:
    return _DEFAULT_ID_PATTERN.findall(text)


def _get_docstring(node: ast.AST) -> str:
    """Return the docstring of a function/class node, or empty string."""
    body = getattr(node, "body", [])
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        val = body[0].value.value
        if isinstance(val, str):
            return val.strip()
    return ""


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------

def _analyse_file(
    filepath: Path,
    rel_path: str,
    source_lines: list[str],
) -> tuple[list[SymbolEntry], list[TestEntry]]:
    """Parse one Python file and return (symbols, tests)."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return [], []

    symbols: list[SymbolEntry] = []
    tests: list[TestEntry] = []

    def _req_ids_near_line(lineno: int, window: int = 3) -> list[str]:
        """Collect requirement IDs from source comments within *window* lines of *lineno*."""
        ids: list[str] = []
        start = max(0, lineno - window - 1)
        end = min(len(source_lines), lineno + window)
        for line in source_lines[start:end]:
            if "#" in line:
                comment = line[line.index("#"):]
                ids.extend(_extract_req_ids_from_text(comment))
        return list(dict.fromkeys(ids))  # deduplicate, preserve order

    for node in ast.walk(tree):
        # Module-level constants: simple Name = <literal> assignments
        if isinstance(node, ast.Assign):
            # Only module-level (parent is Module) — check by col_offset
            if node.col_offset == 0 and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    val_str = _literal_value(node.value) or ""
                    req_ids = _req_ids_near_line(node.lineno)
                    symbols.append(SymbolEntry(
                        name=target.id,
                        kind="constant",
                        path=rel_path,
                        line=node.lineno,
                        value=val_str,
                        req_ids=req_ids,
                    ))

        # Functions and methods
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = _get_docstring(node)
            req_ids = _req_ids_near_line(node.lineno)
            # Add IDs mentioned inside the function body comments
            for child in ast.walk(node):
                pass  # comments are not in the AST; handled via source_lines below
            # Also scan function body source lines for req id comments
            for i in range(node.lineno - 1, min(len(source_lines), node.end_lineno or node.lineno)):
                line = source_lines[i]
                if "#" in line:
                    comment = line[line.index("#"):]
                    for rid in _extract_req_ids_from_text(comment):
                        if rid not in req_ids:
                            req_ids.append(rid)

            is_test = node.name.startswith("test_")
            kind = "method" if node.col_offset > 0 else "function"

            if is_test:
                # Collect asserted literals from the entire test body
                asserted: list[str] = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Assert):
                        asserted.extend(_collect_string_literals(child.test))
                    # pytest.raises(...)
                    elif isinstance(child, ast.Call):
                        if _is_pytest_raises(child):
                            for arg in child.args:
                                asserted.extend(_collect_string_literals(arg))
                # Also pick up req IDs from the test name itself
                for rid in _extract_req_ids_from_text(node.name):
                    if rid not in req_ids:
                        req_ids.append(rid)
                node_id = f"{rel_path}::{node.name}"
                tests.append(TestEntry(
                    name=node.name,
                    path=rel_path,
                    line=node.lineno,
                    node=node_id,
                    asserted_literals=asserted,
                    req_ids=req_ids,
                ))
            else:
                symbols.append(SymbolEntry(
                    name=node.name,
                    kind=kind,
                    path=rel_path,
                    line=node.lineno,
                    docstring=docstring,
                    req_ids=req_ids,
                ))

        # Classes
        elif isinstance(node, ast.ClassDef):
            docstring = _get_docstring(node)
            req_ids = _req_ids_near_line(node.lineno)
            symbols.append(SymbolEntry(
                name=node.name,
                kind="class",
                path=rel_path,
                line=node.lineno,
                docstring=docstring,
                req_ids=req_ids,
            ))

    return symbols, tests


def _is_pytest_raises(node: ast.Call) -> bool:
    """Return True if *node* is a ``pytest.raises(...)`` call."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "raises":
        if isinstance(func.value, ast.Name) and func.value.id == "pytest":
            return True
    return False


def _should_skip(path: Path) -> bool:
    """Return True if the directory or file should be skipped during indexing."""
    for part in path.parts:
        if part in _SKIP_DIRS or part.startswith("."):
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_repo(path: str | Path) -> RepoIndex:
    """Walk *path* recursively and build a :class:`RepoIndex`.

    Skips ``.venv``, ``__pycache__`` and hidden directories.

    Args:
        path: Root directory of the repository to index.

    Returns:
        A :class:`RepoIndex` containing all discovered symbols and tests.

    Raises:
        FileNotFoundError: If *path* does not exist or is not a directory.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"Repository path not found: {root}")
    if not root.is_dir():
        raise ValueError(f"Expected a directory, got: {root}")

    index = RepoIndex()

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root)
        if _should_skip(rel):
            continue
        source_lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        syms, tests = _analyse_file(py_file, str(rel).replace("\\", "/"), source_lines)
        index.symbols.extend(syms)
        index.tests.extend(tests)

    return index
