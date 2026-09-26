"""Tests for traceproof/store.py — evidence store validation and persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from traceproof.models import CodeRef, Evidence, TestRef, Verdict
from traceproof.store import history, latest, record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(req_id: str = "PF-001", verdict: Verdict = Verdict.COVERED) -> Evidence:
    return Evidence(
        req_id=req_id,
        verdict=verdict,
        rationale="test rationale",
        severity="High",
    )


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# record() — happy-path
# ---------------------------------------------------------------------------

def test_record_creates_store_dir(tmp_path: Path) -> None:
    ev = _make_evidence()
    record(ev, tmp_path)
    store = tmp_path / ".traceproof" / "evidence.json"
    assert store.exists()


def test_record_appends_valid_json(tmp_path: Path) -> None:
    ev = _make_evidence()
    record(ev, tmp_path)
    record(ev, tmp_path)
    lines = (tmp_path / ".traceproof" / "evidence.json").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert obj["req_id"] == "PF-001"


def test_record_with_valid_code_ref(tmp_path: Path) -> None:
    # Create a real file with known content
    src = tmp_path / "payflow" / "service.py"
    _write_file(src, "line1\nline2\nline3\n")

    ref = CodeRef(req_id="PF-001", path="payflow/service.py", line=2, symbol="some_fn")
    ev = Evidence(req_id="PF-001", verdict=Verdict.COVERED, code_refs=[ref])
    record(ev, tmp_path)  # should not raise

    store = tmp_path / ".traceproof" / "evidence.json"
    assert store.exists()


# ---------------------------------------------------------------------------
# record() — validation guard (anti-hallucination)
# ---------------------------------------------------------------------------

def test_record_raises_on_missing_file(tmp_path: Path) -> None:
    ref = CodeRef(req_id="PF-001", path="nonexistent/file.py", line=1, symbol="fn")
    ev = Evidence(req_id="PF-001", verdict=Verdict.COVERED, code_refs=[ref])
    with pytest.raises(ValueError, match="does not exist"):
        record(ev, tmp_path)


def test_record_raises_on_line_out_of_range_above(tmp_path: Path) -> None:
    src = tmp_path / "service.py"
    _write_file(src, "line1\nline2\n")  # 2 lines
    ref = CodeRef(req_id="PF-001", path="service.py", line=99, symbol="fn")
    ev = Evidence(req_id="PF-001", verdict=Verdict.COVERED, code_refs=[ref])
    with pytest.raises(ValueError, match="out of range"):
        record(ev, tmp_path)


def test_record_raises_on_line_zero(tmp_path: Path) -> None:
    src = tmp_path / "service.py"
    _write_file(src, "line1\n")
    ref = CodeRef(req_id="PF-001", path="service.py", line=0, symbol="fn")
    ev = Evidence(req_id="PF-001", verdict=Verdict.COVERED, code_refs=[ref])
    with pytest.raises(ValueError, match="out of range"):
        record(ev, tmp_path)


# ---------------------------------------------------------------------------
# latest() — folding by req_id
# ---------------------------------------------------------------------------

def test_latest_empty_when_no_store(tmp_path: Path) -> None:
    assert latest(tmp_path) == {}


def test_latest_returns_last_record(tmp_path: Path) -> None:
    ev1 = Evidence(req_id="PF-001", verdict=Verdict.MISSING, rationale="first")
    ev2 = Evidence(req_id="PF-001", verdict=Verdict.COVERED, rationale="second")
    record(ev1, tmp_path)
    record(ev2, tmp_path)
    result = latest(tmp_path)
    assert result["PF-001"].verdict == Verdict.COVERED
    assert result["PF-001"].rationale == "second"


def test_latest_multiple_requirements(tmp_path: Path) -> None:
    record(Evidence(req_id="PF-001", verdict=Verdict.COVERED), tmp_path)
    record(Evidence(req_id="PF-002", verdict=Verdict.MISSING), tmp_path)
    result = latest(tmp_path)
    assert set(result.keys()) == {"PF-001", "PF-002"}


# ---------------------------------------------------------------------------
# history()
# ---------------------------------------------------------------------------

def test_history_empty_when_no_store(tmp_path: Path) -> None:
    assert history("PF-001", tmp_path) == []


def test_history_returns_all_records_for_req(tmp_path: Path) -> None:
    record(Evidence(req_id="PF-001", verdict=Verdict.MISSING), tmp_path)
    record(Evidence(req_id="PF-001", verdict=Verdict.COVERED), tmp_path)
    record(Evidence(req_id="PF-002", verdict=Verdict.DRIFT), tmp_path)
    h = history("PF-001", tmp_path)
    assert len(h) == 2
    assert h[0].verdict == Verdict.MISSING
    assert h[1].verdict == Verdict.COVERED


def test_history_excludes_other_requirements(tmp_path: Path) -> None:
    record(Evidence(req_id="PF-002", verdict=Verdict.DRIFT), tmp_path)
    assert history("PF-001", tmp_path) == []
