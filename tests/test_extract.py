"""Tests for traceproof.extract — requirement extraction from spec documents."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from traceproof.extract import extract_requirements
from traceproof.models import Requirement

# Path to the demo PDF spec (relative to workspace root).
DEMO_PDF = Path("demo/specs/PayFlow_SRS_v1.2.pdf")
EXPECTED_COUNT = 14
VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}


class TestPdfExtraction:
    """Tests against the real PayFlow SRS PDF."""

    def test_returns_exactly_14_requirements(self):
        reqs = extract_requirements(DEMO_PDF)
        assert len(reqs) == EXPECTED_COUNT, (
            f"Expected {EXPECTED_COUNT} requirements, got {len(reqs)}: "
            + ", ".join(r.req_id for r in reqs)
        )

    def test_all_req_ids_match_pattern(self):
        reqs = extract_requirements(DEMO_PDF)
        for r in reqs:
            assert r.req_id.startswith("PF-"), f"Unexpected req_id: {r.req_id}"

    def test_no_duplicate_req_ids(self):
        reqs = extract_requirements(DEMO_PDF)
        ids = [r.req_id for r in reqs]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_all_have_non_empty_area(self):
        reqs = extract_requirements(DEMO_PDF)
        for r in reqs:
            assert r.area.strip(), f"{r.req_id} has empty area"

    def test_all_have_valid_priority(self):
        reqs = extract_requirements(DEMO_PDF)
        for r in reqs:
            assert r.priority in VALID_PRIORITIES, (
                f"{r.req_id} has invalid priority: {r.priority!r}"
            )

    def test_all_have_non_empty_text(self):
        reqs = extract_requirements(DEMO_PDF)
        for r in reqs:
            assert r.text.strip(), f"{r.req_id} has empty text"

    def test_critical_requirements_present(self):
        reqs = extract_requirements(DEMO_PDF)
        by_id = {r.req_id: r for r in reqs}
        critical_ids = {"PF-002", "PF-003", "PF-006", "PF-007", "PF-008", "PF-011"}
        for rid in critical_ids:
            assert rid in by_id, f"Expected critical requirement {rid} not found"
            assert by_id[rid].priority == "Critical", (
                f"{rid} should be Critical, got {by_id[rid].priority!r}"
            )

    def test_pf005_refund_window_text(self):
        """PF-005 should mention 30 days (not 60)."""
        reqs = extract_requirements(DEMO_PDF)
        pf005 = next((r for r in reqs if r.req_id == "PF-005"), None)
        assert pf005 is not None, "PF-005 not found"
        assert "30" in pf005.text, f"Expected '30 days' in PF-005 text, got: {pf005.text}"

    def test_returns_requirement_instances(self):
        reqs = extract_requirements(DEMO_PDF)
        for r in reqs:
            assert isinstance(r, Requirement)

    def test_pf008_area_contains_security(self):
        reqs = extract_requirements(DEMO_PDF)
        pf008 = next(r for r in reqs if r.req_id == "PF-008")
        assert "Security" in pf008.area or "PCI" in pf008.area, (
            f"PF-008 area should mention Security or PCI-DSS, got: {pf008.area!r}"
        )


class TestMarkdownExtraction:
    """Tests against a synthetic Markdown spec."""

    def test_pipe_table_extraction(self, tmp_path: Path):
        md = textwrap.dedent("""\
            # Spec

            | ID | Area | Priority | Requirement |
            |---|---|---|---|
            | TP-001 | Auth | High | The system SHALL require login. |
            | TP-002 | Data | Critical | Data SHALL be encrypted at rest. |
        """)
        spec = tmp_path / "spec.md"
        spec.write_text(md)
        reqs = extract_requirements(spec)
        assert len(reqs) == 2
        ids = {r.req_id for r in reqs}
        assert ids == {"TP-001", "TP-002"}

    def test_markdown_priority_parsed(self, tmp_path: Path):
        md = "| TP-001 | Auth | Critical | The system SHALL require login. |\n"
        spec = tmp_path / "spec.md"
        spec.write_text(md)
        reqs = extract_requirements(spec)
        assert reqs[0].priority == "Critical"

    def test_markdown_deduplication(self, tmp_path: Path):
        md = textwrap.dedent("""\
            | TP-001 | Auth | High | First occurrence. |
            | TP-001 | Auth | High | Duplicate, should be ignored. |
        """)
        spec = tmp_path / "spec.md"
        spec.write_text(md)
        reqs = extract_requirements(spec)
        assert len(reqs) == 1

    def test_plain_text_fallback(self, tmp_path: Path):
        txt = "TP-001: The system shall require authentication.\n"
        spec = tmp_path / "spec.md"
        spec.write_text(txt)
        reqs = extract_requirements(spec)
        assert len(reqs) == 1
        assert reqs[0].req_id == "TP-001"


class TestErrorHandling:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_requirements("nonexistent_spec.pdf")

    def test_unsupported_extension_raises(self, tmp_path: Path):
        f = tmp_path / "spec.csv"
        f.write_text("data")
        with pytest.raises(ValueError, match="Unsupported spec format"):
            extract_requirements(f)


class TestModelRoundtrip:
    """Ensure Requirement serialisation helpers work."""

    def test_to_dict_from_dict_roundtrip(self):
        from traceproof.models import requirement_from_dict, requirement_to_dict

        original = Requirement(req_id="PF-001", text="Some text", area="Auth", priority="High")
        d = requirement_to_dict(original)
        restored = requirement_from_dict(d)
        assert restored == original

    def test_evidence_roundtrip(self):
        from traceproof.models import CodeRef, Evidence, TestRef, Verdict

        ev = Evidence(
            req_id="PF-001",
            verdict=Verdict.COVERED,
            code_refs=[CodeRef(req_id="PF-001", path="src/foo.py", line=10, symbol="foo")],
            test_refs=[TestRef(req_id="PF-001", path="tests/t.py", line=5, node="tests/t.py::test_foo", passed=True)],
            rationale="Fully implemented.",
            severity="High",
            timestamp="2025-01-01T00:00:00+00:00",
        )
        d = ev.to_dict()
        restored = Evidence.from_dict(d)
        assert restored.req_id == ev.req_id
        assert restored.verdict == Verdict.COVERED
        assert restored.code_refs[0].path == "src/foo.py"
        assert restored.test_refs[0].passed is True
