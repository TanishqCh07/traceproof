"""Requirements traceability matrix builder.

:func:`build_matrix` joins :class:`~traceproof.models.Requirement` objects,
latest :class:`~traceproof.models.Evidence` records and live
:class:`~traceproof.models.TestRef` pass/fail results into a
:class:`Matrix` — the RTM.

Downgrade rule
--------------
A ``COVERED`` verdict whose cited test node appears in *test_results* with
``passed=False`` is downgraded to ``UNTESTED`` (the test exists but is
currently failing, so the behaviour is not actually verified).

PENDING
-------
Requirements that have no evidence record at all are assigned the synthetic
status ``"PENDING"`` and are **not** counted as covered.

Gap ordering
------------
Gaps are sorted by priority: Critical → High → Medium → Low.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traceproof.models import CodeRef, Evidence, Requirement, TestRef, Verdict

_PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


@dataclass
class MatrixRow:
    """One row in the RTM — one requirement and its current audit status."""

    requirement: Requirement
    verdict: str          # Verdict.value or "PENDING"
    rationale: str
    code_refs: list[CodeRef]
    test_refs: list[TestRef]
    is_gap: bool          # True when verdict is not COVERED

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.requirement.req_id,
            "text": self.requirement.text,
            "area": self.requirement.area,
            "priority": self.requirement.priority,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "code_refs": [
                {"path": r.path, "line": r.line, "symbol": r.symbol}
                for r in self.code_refs
            ],
            "test_refs": [
                {"node": r.node, "path": r.path, "line": r.line, "passed": r.passed}
                for r in self.test_refs
            ],
            "is_gap": self.is_gap,
        }


@dataclass
class MatrixSummary:
    """Aggregate statistics derived from the RTM rows."""

    total: int
    covered: int
    coverage_pct: float   # COVERED / total * 100, or 0.0 when total == 0
    by_verdict: dict[str, int]    # verdict string → count
    by_priority: dict[str, int]   # priority → count of all requirements (not just gaps)
    gaps: list[MatrixRow]         # non-COVERED rows, sorted Critical→Low

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "covered": self.covered,
            "coverage_pct": round(self.coverage_pct, 1),
            "by_verdict": self.by_verdict,
            "by_priority": self.by_priority,
            "gaps": [r.to_dict() for r in self.gaps],
        }


@dataclass
class Matrix:
    """Full requirements traceability matrix."""

    rows: list[MatrixRow] = field(default_factory=list)
    summary: MatrixSummary = field(
        default_factory=lambda: MatrixSummary(
            total=0, covered=0, coverage_pct=0.0,
            by_verdict={}, by_priority={}, gaps=[]
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "summary": self.summary.to_dict(),
        }


def build_matrix(
    requirements: list[Requirement],
    evidence: dict[str, Evidence],
    test_results: list[TestRef],
) -> Matrix:
    """Build the RTM from requirements, evidence and live test results.

    Args:
        requirements: All requirements from the spec.
        evidence: Mapping of ``req_id`` → latest :class:`Evidence` (from
            :func:`~traceproof.store.latest`).
        test_results: Flat list of :class:`TestRef` objects returned by
            :func:`~traceproof.runner.run_tests`.  Used to check whether tests
            cited in ``COVERED`` evidence are currently passing.

    Returns:
        A :class:`Matrix` with one :class:`MatrixRow` per requirement plus a
        :class:`MatrixSummary`.
    """
    # Build a fast lookup: normalised test node → passed bool.
    # Normalise to forward slashes so Windows backslash paths match.
    def _norm_node(node: str) -> str:
        return node.replace("\\", "/")

    node_passed: dict[str, bool | None] = {
        _norm_node(t.node): t.passed for t in test_results
    }

    rows: list[MatrixRow] = []

    for req in requirements:
        ev = evidence.get(req.req_id)

        if ev is None:
            # No evidence yet — PENDING
            rows.append(MatrixRow(
                requirement=req,
                verdict="PENDING",
                rationale="",
                code_refs=[],
                test_refs=[],
                is_gap=True,
            ))
            continue

        verdict_str = ev.verdict.value

        # Enrich test_refs with current pass/fail from tests.json lookup
        enriched_tests = []
        for tr in ev.test_refs:
            result = node_passed.get(_norm_node(tr.node), tr.passed)
            if result is not tr.passed:
                enriched_tests.append(
                    TestRef(
                        req_id=tr.req_id,
                        path=tr.path,
                        line=tr.line,
                        node=tr.node,
                        passed=result,
                    )
                )
            else:
                enriched_tests.append(tr)

        # Downgrade COVERED → UNTESTED if any cited test is currently failing
        if ev.verdict == Verdict.COVERED and enriched_tests:
            any_failing = any(t.passed is False for t in enriched_tests)
            if any_failing:
                verdict_str = Verdict.UNTESTED.value

        is_gap = verdict_str != Verdict.COVERED.value

        rows.append(MatrixRow(
            requirement=req,
            verdict=verdict_str,
            rationale=ev.rationale,
            code_refs=ev.code_refs,
            test_refs=enriched_tests,
            is_gap=is_gap,
        ))

    # ------------------------------------------------------------------ summary
    total = len(rows)
    covered = sum(1 for r in rows if r.verdict == Verdict.COVERED.value)
    coverage_pct = (covered / total * 100) if total > 0 else 0.0

    by_verdict: dict[str, int] = {}
    for row in rows:
        by_verdict[row.verdict] = by_verdict.get(row.verdict, 0) + 1

    by_priority: dict[str, int] = {}
    for req in requirements:
        by_priority[req.priority] = by_priority.get(req.priority, 0) + 1

    gaps = sorted(
        [r for r in rows if r.is_gap],
        key=lambda r: _PRIORITY_ORDER.get(r.requirement.priority, 99),
    )

    summary = MatrixSummary(
        total=total,
        covered=covered,
        coverage_pct=coverage_pct,
        by_verdict=by_verdict,
        by_priority=by_priority,
        gaps=gaps,
    )

    return Matrix(rows=rows, summary=summary)
