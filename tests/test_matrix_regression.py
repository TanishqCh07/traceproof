"""Regression tests for fix #3 — tests.json join in matrix/report.

Verifies:
- build_matrix enriches test_refs with pass/fail from tests.json
- Path separator normalisation (backslash vs forward slash)
- render_report loads tests.json and produces ✓/✗ icons in HTML
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from traceproof.matrix import build_matrix
from traceproof.models import Evidence, Requirement, TestRef, Verdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(req_id: str, priority: str = "High") -> Requirement:
    return Requirement(req_id=req_id, text=f"Req {req_id}", area="A", priority=priority)


def _ev(req_id: str, nodes: list[str], verdict: Verdict = Verdict.COVERED) -> Evidence:
    return Evidence(
        req_id=req_id,
        verdict=verdict,
        test_refs=[
            TestRef(req_id=req_id, path=n.split("::")[0], line=0, node=n, passed=None)
            for n in nodes
        ],
        rationale="auto",
    )


def _test_ref(node: str, passed: bool | None) -> TestRef:
    return TestRef(req_id="", path=node.split("::")[0], line=0, node=node, passed=passed)


# ---------------------------------------------------------------------------
# Fix #3a: build_matrix enriches test_refs with pass/fail
# ---------------------------------------------------------------------------

def test_build_matrix_enriches_test_refs_with_pass() -> None:
    """Test refs should show passed=True after joining with test_results."""
    reqs = [_req("T-001")]
    evidence = {"T-001": _ev("T-001", ["tests/test_foo.py::test_a"])}
    test_results = [_test_ref("tests/test_foo.py::test_a", True)]

    matrix = build_matrix(reqs, evidence, test_results)
    row = matrix.rows[0]
    assert len(row.test_refs) == 1
    assert row.test_refs[0].passed is True, (
        "TestRef.passed should be True after join with test_results"
    )


def test_build_matrix_enriches_test_refs_with_fail() -> None:
    """Test refs should show passed=False and downgrade COVERED→UNTESTED."""
    reqs = [_req("T-001")]
    evidence = {"T-001": _ev("T-001", ["tests/test_foo.py::test_a"])}
    test_results = [_test_ref("tests/test_foo.py::test_a", False)]

    matrix = build_matrix(reqs, evidence, test_results)
    row = matrix.rows[0]
    assert row.test_refs[0].passed is False
    assert row.verdict == Verdict.UNTESTED.value, (
        "COVERED verdict should be downgraded to UNTESTED when test is failing"
    )


def test_build_matrix_unknown_node_stays_none() -> None:
    """A test node not in test_results keeps passed=None (unknown)."""
    reqs = [_req("T-001")]
    evidence = {"T-001": _ev("T-001", ["tests/test_foo.py::test_a"])}
    test_results = [_test_ref("tests/test_other.py::test_b", True)]

    matrix = build_matrix(reqs, evidence, test_results)
    row = matrix.rows[0]
    assert row.test_refs[0].passed is None


# ---------------------------------------------------------------------------
# Fix #3b: path separator normalisation
# ---------------------------------------------------------------------------

def test_build_matrix_normalises_backslash_separators() -> None:
    """Windows backslash paths in test_results nodes must match forward-slash
    nodes in evidence test_refs."""
    reqs = [_req("W-001")]
    # Evidence node uses forward slash (as stored by traceproof)
    evidence = {"W-001": _ev("W-001", ["tests/test_win.py::test_w"])}
    # test_results from Windows pytest may use backslashes
    win_node = "tests\\test_win.py::test_w"
    test_results = [_test_ref(win_node, True)]

    matrix = build_matrix(reqs, evidence, test_results)
    row = matrix.rows[0]
    assert row.test_refs[0].passed is True, (
        "Backslash node in test_results should match forward-slash node in evidence"
    )


# ---------------------------------------------------------------------------
# Fix #3c: report renders ✓ icon when tests.json present
# ---------------------------------------------------------------------------

def _write_fixture(repo: Path) -> None:
    """Create a minimal .traceproof dir with requirements.json, evidence.json,
    and tests.json containing a passing test."""
    td = repo / ".traceproof"
    td.mkdir(parents=True, exist_ok=True)

    reqs = [{"req_id": "R-001", "text": "Shall do X.", "area": "core", "priority": "High"}]
    (td / "requirements.json").write_text(json.dumps(reqs), encoding="utf-8")

    ev = {
        "req_id": "R-001",
        "verdict": "COVERED",
        "code_refs": [],
        "test_refs": [
            {"req_id": "R-001", "path": "tests/test_x.py", "line": 0,
             "node": "tests/test_x.py::test_shall_do_x", "passed": None}
        ],
        "rationale": "Implemented.",
        "severity": "High",
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    ev_file = td / "evidence.json"
    ev_file.write_text(json.dumps(ev) + "\n", encoding="utf-8")

    tests = [
        {"node": "tests/test_x.py::test_shall_do_x", "file": "tests/test_x.py",
         "line": 1, "passed": True}
    ]
    (td / "tests.json").write_text(json.dumps(tests), encoding="utf-8")


def test_report_html_shows_pass_icon_when_tests_json_present(tmp_path: Path) -> None:
    """The rendered HTML must contain ✓ (pass icon) when tests.json has passed=True
    for a test node referenced in evidence."""
    from traceproof.report import render_report

    _write_fixture(tmp_path)
    paths, summary = render_report(tmp_path)
    html = paths.html.read_text(encoding="utf-8")

    assert "✓" in html, (
        "HTML report should contain ✓ (pass icon) when tests.json shows test passed"
    )
    # Should NOT contain ? (unknown) for the known test
    # (The ? icon appears in class test-unkn)
    # The test node should appear as test-pass, not test-unkn
    assert "test-pass" in html, "Expected .test-pass CSS class in HTML report"


def test_report_html_shows_fail_icon_when_test_failed(tmp_path: Path) -> None:
    """The rendered HTML must contain ✗ (fail icon) when tests.json has passed=False."""
    from traceproof.report import render_report

    _write_fixture(tmp_path)
    # Overwrite tests.json with a failing result
    tests = [
        {"node": "tests/test_x.py::test_shall_do_x", "file": "tests/test_x.py",
         "line": 1, "passed": False}
    ]
    (tmp_path / ".traceproof" / "tests.json").write_text(
        json.dumps(tests), encoding="utf-8"
    )
    paths, summary = render_report(tmp_path)
    html = paths.html.read_text(encoding="utf-8")

    assert "✗" in html, (
        "HTML report should contain ✗ (fail icon) when tests.json shows test failed"
    )
    assert "test-fail" in html, "Expected .test-fail CSS class in HTML report"


def test_report_verdict_not_downgraded_without_tests_json(tmp_path: Path) -> None:
    """Without tests.json the verdict stays COVERED (no downgrade)."""
    from traceproof.report import render_report

    _write_fixture(tmp_path)
    (tmp_path / ".traceproof" / "tests.json").unlink()

    paths, summary = render_report(tmp_path)
    assert summary.covered == 1, "COVERED verdict should be preserved when tests.json absent"
