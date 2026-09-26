"""Regression tests for traceproof/store.py — fix #2.

Verifies:
- record() is safe under concurrent calls (no data corruption).
- record_batch() writes all records in one atomic operation.
- record_evidence_batch MCP tool works end-to-end.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from traceproof.models import CodeRef, Evidence, TestRef, Verdict
from traceproof.store import record, record_batch, latest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_ev(req_id: str, verdict: Verdict = Verdict.COVERED) -> Evidence:
    return Evidence(req_id=req_id, verdict=verdict, rationale="auto")


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fix #2a: concurrent record() calls do not corrupt the store
# ---------------------------------------------------------------------------

def test_concurrent_records_no_corruption(tmp_path: Path) -> None:
    """Write 50 evidence records from 10 threads in parallel; every record must
    be intact and correctly counted in the store."""
    n_threads = 10
    per_thread = 5
    errors: list[Exception] = []

    def worker(thread_id: int) -> None:
        for i in range(per_thread):
            ev = _make_ev(f"REQ-{thread_id:02d}-{i:02d}")
            try:
                record(ev, tmp_path)
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Exceptions during concurrent writes: {errors}"

    store = tmp_path / ".traceproof" / "evidence.json"
    assert store.exists()
    lines = [l for l in store.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == n_threads * per_thread, (
        f"Expected {n_threads * per_thread} records, got {len(lines)}"
    )
    # Every line must be valid JSON with a req_id
    for line in lines:
        data = json.loads(line)
        assert "req_id" in data


def test_concurrent_records_all_readable(tmp_path: Path) -> None:
    """After concurrent writes, latest() must return one record per req_id."""
    req_ids = [f"PF-{i:03d}" for i in range(20)]
    errors: list[Exception] = []

    def worker(req_id: str) -> None:
        try:
            record(_make_ev(req_id), tmp_path)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(r,)) for r in req_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    result = latest(tmp_path)
    assert set(result.keys()) == set(req_ids)


# ---------------------------------------------------------------------------
# Fix #2b: record_batch — all-or-nothing write
# ---------------------------------------------------------------------------

def test_record_batch_success(tmp_path: Path) -> None:
    """record_batch writes all records and returns no errors."""
    evs = [_make_ev(f"B-{i:02d}") for i in range(5)]
    errors = record_batch(evs, tmp_path)
    assert errors == []

    store = tmp_path / ".traceproof" / "evidence.json"
    lines = [l for l in store.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 5


def test_record_batch_rejects_on_bad_code_ref(tmp_path: Path) -> None:
    """If any record in the batch has a bad code_ref, no records are written."""
    bad_ref = CodeRef(req_id="B-01", path="nonexistent.py", line=1, symbol="fn")
    evs = [
        _make_ev("B-00"),
        Evidence(req_id="B-01", verdict=Verdict.COVERED, code_refs=[bad_ref]),
        _make_ev("B-02"),
    ]
    errors = record_batch(evs, tmp_path)
    assert errors, "Expected validation errors"
    # No store written
    store = tmp_path / ".traceproof" / "evidence.json"
    assert not store.exists(), "Store should not exist when batch fails validation"


def test_record_batch_all_in_single_write(tmp_path: Path) -> None:
    """All records from record_batch appear in the store with correct content."""
    evs = [
        Evidence(req_id=f"C-{i:02d}", verdict=Verdict.MISSING, rationale=f"r{i}")
        for i in range(4)
    ]
    record_batch(evs, tmp_path)
    result = latest(tmp_path)
    for ev in evs:
        assert ev.req_id in result
        assert result[ev.req_id].verdict == Verdict.MISSING


# ---------------------------------------------------------------------------
# Fix #2c: record_evidence_batch MCP tool
# ---------------------------------------------------------------------------

def test_mcp_record_evidence_batch_success(tmp_path: Path) -> None:
    """record_evidence_batch stores N records and returns {stored: N}."""
    from traceproof.mcp_server import record_evidence_batch

    # Create a real source file so code_refs validate
    src = tmp_path / "payflow" / "service.py"
    _write_file(src, "# line1\n# line2\n")

    records = [
        {
            "req_id": "X-001",
            "verdict": "COVERED",
            "code_refs": ["payflow/service.py:1"],
            "test_refs": ["tests/test_x.py::test_foo"],
            "rationale": "Covered.",
        },
        {
            "req_id": "X-002",
            "verdict": "MISSING",
            "code_refs": [],
            "test_refs": [],
            "rationale": "Nothing here.",
        },
    ]
    result = record_evidence_batch(str(tmp_path), records)
    assert result == {"stored": 2}

    store = tmp_path / ".traceproof" / "evidence.json"
    lines = [l for l in store.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2


def test_mcp_record_evidence_batch_rejects_bad_verdict(tmp_path: Path) -> None:
    """record_evidence_batch returns {errors: [...]} on invalid verdict."""
    from traceproof.mcp_server import record_evidence_batch

    records = [
        {
            "req_id": "Y-001",
            "verdict": "BOGUS",
            "code_refs": [],
            "test_refs": [],
            "rationale": "Bad.",
        },
    ]
    result = record_evidence_batch(str(tmp_path), records)
    assert "errors" in result
    assert len(result["errors"]) >= 1


def test_mcp_record_evidence_batch_no_partial_write(tmp_path: Path) -> None:
    """If any record in the batch fails, the store must not be created at all."""
    from traceproof.mcp_server import record_evidence_batch

    records = [
        {
            "req_id": "Z-001",
            "verdict": "COVERED",
            "code_refs": ["totally/nonexistent.py:1"],
            "test_refs": [],
            "rationale": "Bad ref.",
        },
    ]
    record_evidence_batch(str(tmp_path), records)
    store = tmp_path / ".traceproof" / "evidence.json"
    assert not store.exists(), "Store must not be created when batch validation fails"
