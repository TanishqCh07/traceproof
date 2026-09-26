"""Tests for traceproof/cli.py — scan and check exit codes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from traceproof.cli import main
from traceproof.models import Evidence, Requirement, Verdict, requirement_to_dict
from traceproof.store import record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_spec(path: Path, content: str = "") -> None:
    """Write a minimal markdown spec file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content:
        content = (
            "| PF-001 | Payments | High | The system SHALL process payments. |\n"
            "| PF-002 | Refunds  | Critical | The system SHALL process refunds. |\n"
        )
    path.write_text(content, encoding="utf-8")


def _seed_requirements(repo: Path, reqs: list[Requirement]) -> None:
    traceproof_dir = repo / ".traceproof"
    traceproof_dir.mkdir(parents=True, exist_ok=True)
    (traceproof_dir / "requirements.json").write_text(
        json.dumps([requirement_to_dict(r) for r in reqs], indent=2),
        encoding="utf-8",
    )


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal fake repo with a python file and a pytest config."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "dummy.py").write_text("# placeholder\n", encoding="utf-8")
    # No tests — avoids running a real pytest subprocess in unit tests
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    return repo


# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------

def test_scan_creates_artefacts(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    _write_spec(spec)
    repo = _make_repo(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(["scan", "--spec", str(spec), "--repo", str(repo)])
    assert exc.value.code == 0

    traceproof_dir = repo / ".traceproof"
    assert (traceproof_dir / "requirements.json").exists()
    assert (traceproof_dir / "index.json").exists()
    assert (traceproof_dir / "tests.json").exists()


def test_scan_requirements_json_content(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    _write_spec(spec)
    repo = _make_repo(tmp_path)

    with pytest.raises(SystemExit):
        main(["scan", "--spec", str(spec), "--repo", str(repo)])

    data = json.loads((repo / ".traceproof" / "requirements.json").read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    ids = {r["req_id"] for r in data}
    assert "PF-001" in ids
    assert "PF-002" in ids


def test_scan_exits_1_on_missing_spec(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--spec", str(tmp_path / "no_such.md"), "--repo", str(repo)])
    assert exc.value.code == 1


def test_scan_exits_1_on_missing_repo(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    _write_spec(spec)
    with pytest.raises(SystemExit) as exc:
        main(["scan", "--spec", str(spec), "--repo", str(tmp_path / "no_repo")])
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# check command — coverage threshold
# ---------------------------------------------------------------------------

def test_check_exits_1_when_coverage_below_threshold(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    reqs = [
        Requirement("PF-001", "Req 1", "payments", "High"),
        Requirement("PF-002", "Req 2", "payments", "High"),
    ]
    _seed_requirements(repo, reqs)
    # No evidence → 0% coverage

    with pytest.raises(SystemExit) as exc:
        main(["check", "--repo", str(repo), "--min-coverage", "50"])
    assert exc.value.code == 1


def test_check_exits_0_when_coverage_meets_threshold(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    reqs = [Requirement("PF-001", "Req 1", "payments", "High")]
    _seed_requirements(repo, reqs)

    record(Evidence(req_id="PF-001", verdict=Verdict.COVERED), repo)

    with pytest.raises(SystemExit) as exc:
        main(["check", "--repo", str(repo), "--min-coverage", "100"])
    assert exc.value.code == 0


def test_check_exits_1_on_violation(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    reqs = [Requirement("PF-001", "Req 1", "payments", "High")]
    _seed_requirements(repo, reqs)

    record(Evidence(req_id="PF-001", verdict=Verdict.VIOLATION), repo)

    with pytest.raises(SystemExit) as exc:
        main(["check", "--repo", str(repo), "--min-coverage", "0"])
    assert exc.value.code == 1


def test_check_exits_1_on_no_requirements_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["check", "--repo", str(repo), "--min-coverage", "0"])
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# report stub
# ---------------------------------------------------------------------------

def test_report_stub_exits_0(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["report", "--output", str(tmp_path / "out.html")])
    assert exc.value.code == 0
