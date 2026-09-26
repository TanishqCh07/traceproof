"""Regression tests for traceproof/runner.py — fix #1.

Verifies:
- run_tests resolves a relative repo_path to an absolute path before passing
  to subprocess (so cwd + junit xml always refer to the same filesystem root).
- run_tests uses sys.executable (not a bare "python" or "pytest" command).
- Persisting results to .traceproof/tests.json when called via the MCP tool.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from traceproof.runner import run_tests, _parse_junit


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> Path:
    """Return a minimal repo directory with a single passing test."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_example.py").write_text(
        "def test_always_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    return repo


# ---------------------------------------------------------------------------
# Fix #1a: repo_path is resolved to absolute inside run_tests
# ---------------------------------------------------------------------------

def test_run_tests_resolves_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_tests must call subprocess with an absolute cwd, even if a relative
    repo_path string is supplied."""
    captured_kwargs: list[dict] = []

    def fake_run(cmd, **kwargs):
        captured_kwargs.append(kwargs)
        # Simulate success with no tests
        return mock.Mock(returncode=5, stdout="", stderr="")

    monkeypatch.chdir(tmp_path)
    # Create minimal repo under tmp_path
    repo = _make_repo(tmp_path)
    relative = repo.relative_to(tmp_path)  # e.g. "myrepo"

    with mock.patch("subprocess.run", side_effect=fake_run):
        try:
            run_tests(str(relative))
        except Exception:
            pass

    assert captured_kwargs, "subprocess.run was never called"
    cwd_used = Path(captured_kwargs[0]["cwd"])
    assert cwd_used.is_absolute(), (
        f"cwd passed to subprocess should be absolute, got: {cwd_used}"
    )


def test_run_tests_uses_sys_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_tests must use sys.executable as the Python interpreter, not a bare string."""
    captured_cmds: list[list] = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(list(cmd))
        return mock.Mock(returncode=5, stdout="", stderr="")

    repo = _make_repo(tmp_path)
    with mock.patch("subprocess.run", side_effect=fake_run):
        try:
            run_tests(str(repo))
        except Exception:
            pass

    assert captured_cmds, "subprocess.run was never called"
    assert captured_cmds[0][0] == sys.executable, (
        f"First element of command should be sys.executable={sys.executable!r}, "
        f"got {captured_cmds[0][0]!r}"
    )


def test_run_tests_junit_path_is_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The --junitxml argument must use an absolute path so it's accessible
    regardless of the subprocess cwd."""
    captured_cmds: list[list] = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(list(cmd))
        return mock.Mock(returncode=5, stdout="", stderr="")

    repo = _make_repo(tmp_path)
    with mock.patch("subprocess.run", side_effect=fake_run):
        try:
            run_tests(str(repo))
        except Exception:
            pass

    assert captured_cmds, "subprocess.run was never called"
    junitxml_arg = next(
        (a for a in captured_cmds[0] if a.startswith("--junitxml=")), None
    )
    assert junitxml_arg is not None, "--junitxml argument not found in command"
    xml_path = Path(junitxml_arg.split("=", 1)[1])
    assert xml_path.is_absolute(), (
        f"--junitxml path should be absolute, got: {xml_path}"
    )


# ---------------------------------------------------------------------------
# Fix #1b: _parse_junit normalises node IDs from classname
# ---------------------------------------------------------------------------

def test_parse_junit_returns_empty_for_missing_file(tmp_path: Path) -> None:
    refs = _parse_junit(str(tmp_path / "nonexistent.xml"))
    assert refs == []


def test_parse_junit_returns_empty_for_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.xml"
    p.write_text("", encoding="utf-8")
    refs = _parse_junit(str(p))
    assert refs == []


def test_parse_junit_passes_and_failures(tmp_path: Path) -> None:
    xml = tmp_path / "junit.xml"
    xml.write_text(
        '<?xml version="1.0"?>'
        '<testsuites>'
        '<testsuite name="tests">'
        '<testcase classname="tests.test_foo" name="test_a" file="tests/test_foo.py" line="1"/>'
        '<testcase classname="tests.test_foo" name="test_b" file="tests/test_foo.py" line="5">'
        '<failure message="assert False"/>'
        '</testcase>'
        '</testsuite>'
        '</testsuites>',
        encoding="utf-8",
    )
    refs = _parse_junit(str(xml))
    assert len(refs) == 2
    nodes = {r.node: r.passed for r in refs}
    assert nodes["tests/test_foo.py::test_a"] is True
    assert nodes["tests/test_foo.py::test_b"] is False


# ---------------------------------------------------------------------------
# Fix #1c: MCP run_tests persists tests.json
# ---------------------------------------------------------------------------

def test_mcp_run_tests_persists_tests_json(tmp_path: Path) -> None:
    """After calling the MCP run_tests tool, .traceproof/tests.json must exist."""
    from traceproof.mcp_server import run_tests as mcp_run_tests

    # Build a real minimal repo
    repo = _make_repo(tmp_path)
    result = mcp_run_tests(str(repo))
    tests_file = repo / ".traceproof" / "tests.json"
    assert tests_file.exists(), "tests.json was not persisted by mcp run_tests"
    data = json.loads(tests_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == result["totals"]["total"]


def test_mcp_run_tests_persists_tests_json_relative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP run_tests must persist tests.json even when repo_path is relative."""
    from traceproof.mcp_server import run_tests as mcp_run_tests

    repo = _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    rel = str(repo.relative_to(tmp_path))
    result = mcp_run_tests(rel)
    tests_file = repo / ".traceproof" / "tests.json"
    assert tests_file.exists(), "tests.json was not persisted when repo_path was relative"
