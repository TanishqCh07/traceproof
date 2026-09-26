"""Tests for traceproof/mcp_server.py — calls each tool function directly.

All tests run against a temporary copy of demo/payflow so the original
demo artefacts are never mutated.  No MCP/stdio transport is involved;
each tool function is imported and called as a plain Python function.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEMO_REPO = Path(__file__).parent.parent / "demo" / "payflow"


@pytest.fixture()
def payflow_copy(tmp_path: Path) -> Path:
    """Return a fresh temporary copy of demo/payflow for each test."""
    dest = tmp_path / "payflow"
    shutil.copytree(str(DEMO_REPO), str(dest))
    return dest


# ---------------------------------------------------------------------------
# extract_requirements
# ---------------------------------------------------------------------------

class TestExtractRequirements:
    def test_returns_list_of_dicts(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import extract_requirements

        # The demo ships a spec inside its README; use the pre-built requirements.json
        # to avoid needing a spec file — instead we call extract on the existing MD readme.
        spec = payflow_copy / "README.md"
        result = extract_requirements(str(spec))
        assert isinstance(result, list)
        # README may or may not have structured IDs; result can be empty — just verify shape
        for item in result:
            assert "req_id" in item
            assert "text" in item

    def test_returns_requirements_from_stored_json(self, payflow_copy: Path) -> None:
        """Smoke test: parse a small inline markdown snippet."""
        from traceproof.mcp_server import extract_requirements

        spec = payflow_copy / "test_spec.md"
        spec.write_text(
            "| PF-001 | Currency | High | The system SHALL accept INR. |\n",
            encoding="utf-8",
        )
        result = extract_requirements(str(spec))
        assert len(result) >= 1
        assert result[0]["req_id"] == "PF-001"
        assert result[0]["priority"] == "High"

    def test_raises_on_missing_file(self) -> None:
        from traceproof.mcp_server import extract_requirements

        with pytest.raises(FileNotFoundError):
            extract_requirements("/nonexistent/path/spec.md")


# ---------------------------------------------------------------------------
# index_repo
# ---------------------------------------------------------------------------

class TestIndexRepo:
    def test_returns_compact_structure(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import index_repo

        result = index_repo(str(payflow_copy))
        assert "symbols" in result
        assert "tests" in result
        assert "totals" in result
        assert result["totals"]["symbols"] == len(result["symbols"])
        assert result["totals"]["tests"] == len(result["tests"])

    def test_symbol_keys(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import index_repo

        result = index_repo(str(payflow_copy))
        for sym in result["symbols"]:
            assert set(sym.keys()) >= {"name", "kind", "file", "line"}

    def test_test_keys(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import index_repo

        result = index_repo(str(payflow_copy))
        for t in result["tests"]:
            assert set(t.keys()) >= {"name", "kind", "file", "line", "node"}
            assert t["kind"] == "test"

    def test_finds_payflow_symbols(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import index_repo

        result = index_repo(str(payflow_copy))
        names = {s["name"] for s in result["symbols"]}
        # payflow/service.py should contribute symbols
        assert len(names) > 0

    def test_raises_on_missing_path(self) -> None:
        from traceproof.mcp_server import index_repo

        with pytest.raises(FileNotFoundError):
            index_repo("/nonexistent/repo")


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    def test_returns_results_and_totals(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import run_tests

        result = run_tests(str(payflow_copy))
        assert "results" in result
        assert "totals" in result
        totals = result["totals"]
        assert "total" in totals
        assert "passed" in totals
        assert "failed" in totals
        assert "skipped" in totals

    def test_totals_are_consistent(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import run_tests

        result = run_tests(str(payflow_copy))
        totals = result["totals"]
        assert totals["total"] == len(result["results"])
        assert totals["passed"] + totals["failed"] + totals["skipped"] == totals["total"]

    def test_result_keys(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import run_tests

        result = run_tests(str(payflow_copy))
        for r in result["results"]:
            assert set(r.keys()) >= {"node", "file", "line", "passed"}


# ---------------------------------------------------------------------------
# record_evidence
# ---------------------------------------------------------------------------

class TestRecordEvidence:
    def test_records_valid_evidence(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        # payflow/service.py line 1 should exist
        service_py = payflow_copy / "payflow" / "service.py"
        assert service_py.exists()

        result = record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-001",
            verdict="COVERED",
            code_refs=["payflow/service.py:1"],
            test_refs=["tests/test_payments.py::test_happy_path_lifecycle"],
            rationale="Implemented and tested.",
        )
        assert isinstance(result, dict)
        assert result["req_id"] == "PF-001"
        assert result["verdict"] == "COVERED"

    def test_returns_error_on_bad_code_ref_file(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        result = record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-001",
            verdict="COVERED",
            code_refs=["nonexistent/file.py:5"],
            test_refs=[],
            rationale="Does not exist.",
        )
        assert isinstance(result, str)
        assert "anti-hallucination" in result.lower() or "validation" in result.lower()

    def test_returns_error_on_bad_code_ref_line(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        result = record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-001",
            verdict="COVERED",
            code_refs=["payflow/service.py:999999"],
            test_refs=[],
            rationale="Line way out of range.",
        )
        assert isinstance(result, str)
        assert "anti-hallucination" in result.lower() or "validation" in result.lower()

    def test_returns_error_on_malformed_code_ref(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        result = record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-001",
            verdict="COVERED",
            code_refs=["payflow/service.py"],  # missing :line
            test_refs=[],
            rationale="Malformed.",
        )
        assert isinstance(result, str)
        assert "malformed" in result.lower() or "format" in result.lower()

    def test_returns_error_on_invalid_verdict(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        result = record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-001",
            verdict="BOGUS",
            code_refs=[],
            test_refs=[],
            rationale="Bad verdict.",
        )
        assert isinstance(result, str)
        assert "verdict" in result.lower() or "invalid" in result.lower()

    def test_evidence_persisted_to_disk(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import record_evidence

        service_py = payflow_copy / "payflow" / "service.py"
        record_evidence(
            repo_path=str(payflow_copy),
            req_id="PF-007",
            verdict="UNTESTED",
            code_refs=[f"payflow/service.py:1"],
            test_refs=[],
            rationale="No test yet.",
        )
        store_file = payflow_copy / ".traceproof" / "evidence.json"
        assert store_file.exists()
        lines = [l for l in store_file.read_text().splitlines() if l.strip()]
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["req_id"] == "PF-007"


# ---------------------------------------------------------------------------
# get_matrix
# ---------------------------------------------------------------------------

class TestGetMatrix:
    def test_returns_matrix_structure(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import get_matrix

        result = get_matrix(str(payflow_copy))
        assert "summary" in result
        assert "rows" in result
        summary = result["summary"]
        assert "total" in summary
        assert "covered" in summary
        assert "coverage_pct" in summary

    def test_rows_match_requirements(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import get_matrix

        result = get_matrix(str(payflow_copy))
        # payflow has 14 requirements in requirements.json
        assert result["summary"]["total"] == 14
        assert len(result["rows"]) == 14

    def test_error_when_no_requirements_file(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import get_matrix

        with pytest.raises(RuntimeError, match="requirements.json"):
            get_matrix(str(tmp_path))


# ---------------------------------------------------------------------------
# get_gaps
# ---------------------------------------------------------------------------

class TestGetGaps:
    def test_returns_gaps_structure(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import get_gaps

        result = get_gaps(str(payflow_copy))
        assert "gaps" in result
        assert "total_gaps" in result
        assert result["total_gaps"] == len(result["gaps"])

    def test_all_gaps_have_required_keys(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import get_gaps

        result = get_gaps(str(payflow_copy))
        for gap in result["gaps"]:
            assert set(gap.keys()) >= {"req_id", "text", "priority", "verdict", "rationale"}

    def test_severity_filter(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import get_gaps

        critical_gaps = get_gaps(str(payflow_copy), severity="Critical")
        all_gaps = get_gaps(str(payflow_copy))
        assert critical_gaps["total_gaps"] <= all_gaps["total_gaps"]
        for gap in critical_gaps["gaps"]:
            assert gap["priority"] == "Critical"

    def test_no_requirements_file_raises(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import get_gaps

        with pytest.raises(RuntimeError, match="requirements.json"):
            get_gaps(str(tmp_path))


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------

class TestRenderReport:
    def test_returns_stub_string(self, payflow_copy: Path) -> None:
        from traceproof.mcp_server import render_report

        result = render_report(str(payflow_copy))
        assert isinstance(result, str)
        assert "step 3" in result.lower()
