"""Tests for traceproof/matrix.py — downgrade logic, gap ordering, coverage."""
from __future__ import annotations

from traceproof.matrix import build_matrix
from traceproof.models import CodeRef, Evidence, Requirement, TestRef, Verdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(req_id: str, priority: str = "High") -> Requirement:
    return Requirement(req_id=req_id, text=f"Requirement {req_id}", area="payments", priority=priority)


def _ev(req_id: str, verdict: Verdict, test_nodes: list[str] | None = None) -> Evidence:
    test_refs = [
        TestRef(req_id=req_id, path="tests/test_foo.py", line=1, node=n, passed=None)
        for n in (test_nodes or [])
    ]
    return Evidence(req_id=req_id, verdict=verdict, test_refs=test_refs)


def _pass(node: str) -> TestRef:
    return TestRef(req_id="", path="", line=0, node=node, passed=True)


def _fail(node: str) -> TestRef:
    return TestRef(req_id="", path="", line=0, node=node, passed=False)


# ---------------------------------------------------------------------------
# PENDING — no evidence
# ---------------------------------------------------------------------------

def test_pending_when_no_evidence() -> None:
    reqs = [_req("PF-001")]
    matrix = build_matrix(reqs, {}, [])
    assert len(matrix.rows) == 1
    assert matrix.rows[0].verdict == "PENDING"
    assert matrix.rows[0].is_gap is True


def test_pending_not_counted_as_covered() -> None:
    reqs = [_req("PF-001")]
    matrix = build_matrix(reqs, {}, [])
    assert matrix.summary.covered == 0
    assert matrix.summary.coverage_pct == 0.0


# ---------------------------------------------------------------------------
# COVERED stays COVERED when tests pass
# ---------------------------------------------------------------------------

def test_covered_stays_covered_when_test_passes() -> None:
    reqs = [_req("PF-001")]
    ev = _ev("PF-001", Verdict.COVERED, test_nodes=["tests/test_foo.py::test_bar"])
    test_results = [_pass("tests/test_foo.py::test_bar")]
    matrix = build_matrix(reqs, {"PF-001": ev}, test_results)
    assert matrix.rows[0].verdict == "COVERED"
    assert matrix.summary.covered == 1
    assert matrix.summary.coverage_pct == 100.0


# ---------------------------------------------------------------------------
# COVERED downgraded to UNTESTED when cited test is failing
# ---------------------------------------------------------------------------

def test_covered_downgraded_to_untested_when_test_fails() -> None:
    reqs = [_req("PF-001")]
    ev = _ev("PF-001", Verdict.COVERED, test_nodes=["tests/test_foo.py::test_bar"])
    test_results = [_fail("tests/test_foo.py::test_bar")]
    matrix = build_matrix(reqs, {"PF-001": ev}, test_results)
    assert matrix.rows[0].verdict == "UNTESTED"
    assert matrix.rows[0].is_gap is True
    assert matrix.summary.covered == 0


def test_covered_no_downgrade_when_test_not_in_results() -> None:
    """COVERED stays COVERED if the test node isn't in test_results at all."""
    reqs = [_req("PF-001")]
    ev = _ev("PF-001", Verdict.COVERED, test_nodes=["tests/test_foo.py::test_bar"])
    matrix = build_matrix(reqs, {"PF-001": ev}, [])
    assert matrix.rows[0].verdict == "COVERED"


# ---------------------------------------------------------------------------
# Gap ordering: Critical > High > Medium > Low
# ---------------------------------------------------------------------------

def test_gap_ordering_by_priority() -> None:
    reqs = [
        _req("PF-001", priority="Low"),
        _req("PF-002", priority="Critical"),
        _req("PF-003", priority="Medium"),
        _req("PF-004", priority="High"),
    ]
    matrix = build_matrix(reqs, {}, [])
    gap_ids = [r.requirement.req_id for r in matrix.summary.gaps]
    # Expected order: Critical (PF-002), High (PF-004), Medium (PF-003), Low (PF-001)
    assert gap_ids == ["PF-002", "PF-004", "PF-003", "PF-001"]


# ---------------------------------------------------------------------------
# Coverage percentage
# ---------------------------------------------------------------------------

def test_coverage_pct_partial() -> None:
    reqs = [_req("PF-001"), _req("PF-002"), _req("PF-003"), _req("PF-004")]
    ev1 = _ev("PF-001", Verdict.COVERED)
    ev2 = _ev("PF-002", Verdict.COVERED)
    evidence = {"PF-001": ev1, "PF-002": ev2}
    matrix = build_matrix(reqs, evidence, [])
    assert matrix.summary.covered == 2
    assert matrix.summary.coverage_pct == 50.0


def test_coverage_pct_zero_when_no_requirements() -> None:
    matrix = build_matrix([], {}, [])
    assert matrix.summary.coverage_pct == 0.0


# ---------------------------------------------------------------------------
# by_verdict counts
# ---------------------------------------------------------------------------

def test_by_verdict_counts() -> None:
    reqs = [_req("PF-001"), _req("PF-002"), _req("PF-003")]
    evidence = {
        "PF-001": _ev("PF-001", Verdict.COVERED),
        "PF-002": _ev("PF-002", Verdict.MISSING),
    }
    matrix = build_matrix(reqs, evidence, [])
    assert matrix.summary.by_verdict["COVERED"] == 1
    assert matrix.summary.by_verdict["MISSING"] == 1
    assert matrix.summary.by_verdict["PENDING"] == 1
