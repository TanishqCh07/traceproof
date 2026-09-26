"""Tests for traceproof/report.py.

Covers:
- render_report with PENDING-only data
- render_report with mixed verdicts (COVERED, UNTESTED, DRIFT, VIOLATION, MISSING)
- render_report with evidence history (before→after strip)
- HTML output: key structural elements present
- CSV output: correct headers and rows
- audit_pack.zip: contains all required files
- MANIFEST.sha256: hashes verify against actual zip members
- CLI `traceproof report` command
- MCP tool render_report returns expected keys
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_REQS = [
    {"req_id": "T-001", "text": "The system shall accept payments.", "area": "payments", "priority": "Critical"},
    {"req_id": "T-002", "text": "The system shall reject duplicate transactions.", "area": "payments", "priority": "High"},
    {"req_id": "T-003", "text": "The system shall log all errors.", "area": "logging", "priority": "Medium"},
    {"req_id": "T-004", "text": "The system shall not expose secrets.", "area": "security", "priority": "Critical"},
    {"req_id": "T-005", "text": "The system shall allow refunds within 30 days.", "area": "refunds", "priority": "High"},
]

# Evidence records (NDJSON)
_EV_MIXED = "\n".join([
    json.dumps({"req_id": "T-001", "verdict": "COVERED",   "code_refs": [], "test_refs": [], "rationale": "Implemented and tested.", "severity": "Critical", "timestamp": "2025-01-01T00:00:00+00:00"}),
    json.dumps({"req_id": "T-002", "verdict": "UNTESTED",  "code_refs": [], "test_refs": [], "rationale": "Code present, no test.",   "severity": "High",     "timestamp": "2025-01-01T00:00:00+00:00"}),
    json.dumps({"req_id": "T-003", "verdict": "DRIFT",     "code_refs": [], "test_refs": [], "rationale": "Wrong log level.",         "severity": "Medium",   "timestamp": "2025-01-01T00:00:00+00:00"}),
    json.dumps({"req_id": "T-004", "verdict": "VIOLATION", "code_refs": [], "test_refs": [], "rationale": "Secrets in plaintext.",    "severity": "Critical", "timestamp": "2025-01-01T00:00:00+00:00"}),
    json.dumps({"req_id": "T-005", "verdict": "MISSING",   "code_refs": [], "test_refs": [], "rationale": "No refund logic found.",   "severity": "High",     "timestamp": "2025-01-01T00:00:00+00:00"}),
]) + "\n"

# Second pass — T-001 improved, rest unchanged (gives history)
_EV_HISTORY = _EV_MIXED + json.dumps({
    "req_id": "T-002", "verdict": "COVERED", "code_refs": [], "test_refs": [],
    "rationale": "Test added.", "severity": "High", "timestamp": "2025-02-01T00:00:00+00:00",
}) + "\n"


def _make_repo(tmp_path: Path, evidence: str | None = None, reqs: list | None = None) -> Path:
    """Create a minimal fake repo with .traceproof/ artefacts."""
    repo = tmp_path / "repo"
    store = repo / ".traceproof"
    store.mkdir(parents=True)

    r = reqs if reqs is not None else _REQS
    (store / "requirements.json").write_text(json.dumps(r), encoding="utf-8")
    (store / "tests.json").write_text("[]", encoding="utf-8")

    if evidence is not None:
        (store / "evidence.json").write_text(evidence, encoding="utf-8")

    return repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# PENDING-only (no evidence)
# ---------------------------------------------------------------------------

class TestPendingOnly:
    def test_html_created(self, tmp_path: Path) -> None:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path)
        paths, summary = render_report(repo)
        assert paths.html.exists()

    def test_summary_all_pending(self, tmp_path: Path) -> None:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path)
        _, summary = render_report(repo)
        assert summary.total == 5
        assert summary.covered == 0
        assert summary.coverage_pct == 0.0
        assert summary.by_verdict.get("PENDING", 0) == 5

    def test_html_contains_pending_chip(self, tmp_path: Path) -> None:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path)
        paths, _ = render_report(repo)
        html = paths.html.read_text(encoding="utf-8")
        assert "chip-PENDING" in html

    def test_no_history_strip(self, tmp_path: Path) -> None:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path)
        paths, _ = render_report(repo)
        html = paths.html.read_text(encoding="utf-8")
        # The CSS class exists in <style>; check the *div* is not rendered
        assert '<div class="history-strip"' not in html


# ---------------------------------------------------------------------------
# Mixed verdicts
# ---------------------------------------------------------------------------

class TestMixedVerdicts:
    @pytest.fixture()
    def mixed_repo(self, tmp_path: Path) -> Path:
        return _make_repo(tmp_path, evidence=_EV_MIXED)

    def test_coverage_pct(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        _, summary = render_report(mixed_repo)
        assert summary.covered == 1
        assert summary.total == 5
        assert abs(summary.coverage_pct - 20.0) < 0.1

    def test_by_verdict_counts(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        _, summary = render_report(mixed_repo)
        assert summary.by_verdict["COVERED"]   == 1
        assert summary.by_verdict["UNTESTED"]  == 1
        assert summary.by_verdict["DRIFT"]     == 1
        assert summary.by_verdict["VIOLATION"] == 1
        assert summary.by_verdict["MISSING"]   == 1

    def test_critical_gaps(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        _, summary = render_report(mixed_repo)
        # T-004 (Critical, VIOLATION) is a gap; T-001 (Critical) is COVERED → not a gap
        assert summary.critical_gaps == 1

    def test_html_has_verdict_chips(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        html = paths.html.read_text(encoding="utf-8")
        for v in ["COVERED", "UNTESTED", "DRIFT", "VIOLATION", "MISSING"]:
            assert f"chip-{v}" in html, f"Missing chip for {v}"

    def test_html_header_elements(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        html = paths.html.read_text(encoding="utf-8")
        assert "TraceProof" in html
        assert "Requirements Traceability Matrix" in html
        assert "ring-pct" in html      # coverage ring

    def test_html_req_ids_present(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        html = paths.html.read_text(encoding="utf-8")
        for rid in ["T-001", "T-002", "T-003", "T-004", "T-005"]:
            assert rid in html

    def test_html_tinted_rows(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        html = paths.html.read_text(encoding="utf-8")
        assert "row-VIOLATION" in html
        assert "row-DRIFT" in html

    def test_csv_headers(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        reader = csv.DictReader(io.StringIO(paths.csv.read_text(encoding="utf-8")))
        assert reader.fieldnames is not None
        for col in ["req_id", "priority", "area", "text", "verdict", "rationale"]:
            assert col in reader.fieldnames

    def test_csv_row_count(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        reader = list(csv.DictReader(io.StringIO(paths.csv.read_text(encoding="utf-8"))))
        assert len(reader) == 5

    def test_csv_verdicts(self, mixed_repo: Path) -> None:
        from traceproof.report import render_report
        paths, _ = render_report(mixed_repo)
        rows = list(csv.DictReader(io.StringIO(paths.csv.read_text(encoding="utf-8"))))
        verdicts = {r["req_id"]: r["verdict"] for r in rows}
        assert verdicts["T-001"] == "COVERED"
        assert verdicts["T-004"] == "VIOLATION"


# ---------------------------------------------------------------------------
# History (before → after strip)
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_strip_present(self, tmp_path: Path) -> None:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path, evidence=_EV_HISTORY)
        paths, _ = render_report(repo)
        html = paths.html.read_text(encoding="utf-8")
        assert "history-strip" in html

    def test_history_pct_changed(self, tmp_path: Path) -> None:
        """First record: T-001 COVERED only → 20%. Latest: T-001+T-002 COVERED → 40%."""
        from traceproof.report import render_report
        repo = _make_repo(tmp_path, evidence=_EV_HISTORY)
        _, summary = render_report(repo)
        assert summary.covered == 2
        assert abs(summary.coverage_pct - 40.0) < 0.1


# ---------------------------------------------------------------------------
# ZIP contents
# ---------------------------------------------------------------------------

class TestZipContents:
    @pytest.fixture()
    def zip_path(self, tmp_path: Path) -> Path:
        from traceproof.report import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        paths, _ = render_report(repo)
        return paths.zip

    def test_zip_exists(self, zip_path: Path) -> None:
        assert zip_path.exists()
        assert zipfile.is_zipfile(zip_path)

    def test_zip_contains_html(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "rtm.html" in zf.namelist()

    def test_zip_contains_csv(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "rtm.csv" in zf.namelist()

    def test_zip_contains_evidence(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "evidence.json" in zf.namelist()

    def test_zip_contains_requirements(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "requirements.json" in zf.namelist()

    def test_zip_contains_tests(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "tests.json" in zf.namelist()

    def test_zip_contains_manifest(self, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path) as zf:
            assert "MANIFEST.sha256" in zf.namelist()


# ---------------------------------------------------------------------------
# MANIFEST hash verification
# ---------------------------------------------------------------------------

class TestManifest:
    @pytest.fixture()
    def report_outputs(self, tmp_path: Path):
        from traceproof.report import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        paths, _ = render_report(repo)
        return repo, paths

    def test_manifest_file_exists(self, report_outputs) -> None:
        repo, paths = report_outputs
        manifest = paths.html.parent / "MANIFEST.sha256"
        assert manifest.exists()

    def test_manifest_hashes_verify(self, report_outputs) -> None:
        """Every sha256 line in MANIFEST.sha256 must match the actual file in the zip."""
        repo, paths = report_outputs
        manifest_path = paths.html.parent / "MANIFEST.sha256"
        manifest_text = manifest_path.read_text(encoding="utf-8")

        with zipfile.ZipFile(paths.zip) as zf:
            for line in manifest_text.splitlines():
                # Only process hash lines (not metadata lines)
                if "  " not in line:
                    continue
                digest, name = line.split("  ", 1)
                data = zf.read(name)
                actual = hashlib.sha256(data).hexdigest()
                assert actual == digest, f"Hash mismatch for {name}"

    def test_manifest_contains_timestamp(self, report_outputs) -> None:
        repo, paths = report_outputs
        manifest = (paths.html.parent / "MANIFEST.sha256").read_text(encoding="utf-8")
        assert "generated_at:" in manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCliReport:
    def test_cli_report_creates_html(self, tmp_path: Path) -> None:
        from traceproof.cli import main
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        with pytest.raises(SystemExit) as exc:
            main(["report", "--repo", str(repo)])
        assert exc.value.code == 0
        html = repo / ".traceproof" / "reports" / "rtm.html"
        assert html.exists()

    def test_cli_report_creates_zip(self, tmp_path: Path) -> None:
        from traceproof.cli import main
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        with pytest.raises(SystemExit) as exc:
            main(["report", "--repo", str(repo)])
        assert exc.value.code == 0
        zp = repo / ".traceproof" / "reports" / "audit_pack.zip"
        assert zp.exists()

    def test_cli_report_missing_repo(self, tmp_path: Path, capsys) -> None:
        from traceproof.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["report", "--repo", str(tmp_path / "nonexistent")])
        assert exc.value.code == 1

    def test_cli_report_empty_repo_no_crash(self, tmp_path: Path) -> None:
        """Report with zero requirements should still produce HTML."""
        from traceproof.cli import main
        repo = _make_repo(tmp_path, reqs=[])
        with pytest.raises(SystemExit) as exc:
            main(["report", "--repo", str(repo)])
        assert exc.value.code == 0
        html = repo / ".traceproof" / "reports" / "rtm.html"
        assert html.exists()


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------

class TestMcpRenderReport:
    def test_returns_dict_with_paths(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        result = render_report(str(repo))
        assert isinstance(result, dict)
        assert "html" in result
        assert "csv" in result
        assert "zip" in result
        assert "summary" in result

    def test_summary_keys(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        result = render_report(str(repo))
        s = result["summary"]
        for key in ["total", "covered", "coverage_pct", "by_verdict", "critical_gaps"]:
            assert key in s, f"Missing key: {key}"

    def test_html_path_exists(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        result = render_report(str(repo))
        assert Path(result["html"]).exists()

    def test_with_spec_path(self, tmp_path: Path) -> None:
        from traceproof.mcp_server import render_report
        repo = _make_repo(tmp_path, evidence=_EV_MIXED)
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        result = render_report(str(repo), str(spec))
        assert Path(result["html"]).exists()
