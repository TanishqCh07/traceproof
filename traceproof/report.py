"""Report generator for TraceProof — produces HTML, CSV, and audit-pack ZIP.

Public API
----------
render_report(repo_path, spec_path=None) -> ReportPaths
    Builds ``<repo>/.traceproof/reports/rtm.html``, ``rtm.csv``, and
    ``audit_pack.zip`` (containing both, plus ``evidence.json``,
    ``requirements.json``, ``tests.json``, and ``MANIFEST.sha256``).

    Returns a :class:`ReportPaths` dataclass with the absolute paths to each
    output file plus a :class:`ReportSummary` with headline statistics.

No network calls are made.  The Jinja2 template is loaded from
``traceproof/templates/rtm.html.j2`` (shipped alongside this module).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jinja2

from traceproof.matrix import MatrixRow, MatrixSummary, build_matrix
from traceproof.models import requirement_from_dict
from traceproof.store import latest as latest_evidence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STORE_DIR = ".traceproof"
_REPORTS_DIR = "reports"
_EVIDENCE_FILE = "evidence.json"
_REQS_FILE = "requirements.json"
_TESTS_FILE = "tests.json"


# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------

@dataclass
class ReportPaths:
    """Paths to every file produced by :func:`render_report`."""

    html: Path
    csv: Path
    zip: Path


@dataclass
class ReportSummary:
    """Headline statistics returned alongside :class:`ReportPaths`."""

    total: int
    covered: int
    coverage_pct: float
    by_verdict: dict[str, int]
    critical_gaps: int
    commit_sha: str
    generated_at: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _git_sha(repo_path: Path) -> str:
    """Return the short HEAD commit SHA for *repo_path*, or '' on failure."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def _load_requirements(repo_path: Path) -> list[Any]:
    """Load requirements from ``<repo>/.traceproof/requirements.json``."""
    p = repo_path / _STORE_DIR / _REQS_FILE
    if not p.exists():
        return []
    return [requirement_from_dict(d) for d in json.loads(p.read_text(encoding="utf-8"))]


def _load_tests(repo_path: Path) -> list[Any]:
    """Return TestRef-like dicts from tests.json (or [] when absent)."""
    from traceproof.models import TestRef

    p = repo_path / _STORE_DIR / _TESTS_FILE
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    # Support both the old CLI format {req_id, path, line, node, passed}
    # and the MCP run_tests format {node, file, line, passed}
    refs: list[Any] = []
    for item in data:
        node = item.get("node", "")
        passed = item.get("passed")
        path = item.get("path") or item.get("file", "")
        line = item.get("line", 0)
        refs.append(TestRef(req_id="", path=path, line=line, node=node, passed=passed))
    return refs


def _first_coverage_pct(repo_path: Path) -> float | None:
    """Return the coverage % implied by the *first* evidence record in the store.

    Reads all records and counts how many distinct req_ids had their first
    verdict as COVERED.  Returns ``None`` when the store is empty or missing.
    """
    ev_path = repo_path / _STORE_DIR / _EVIDENCE_FILE
    if not ev_path.exists():
        return None

    lines = [l.strip() for l in ev_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None

    # Fold by req_id keeping the *first* occurrence (oldest first in NDJSON)
    first: dict[str, str] = {}
    for line in lines:
        try:
            d = json.loads(line)
            rid = d.get("req_id", "")
            if rid and rid not in first:
                first[rid] = d.get("verdict", "")
        except json.JSONDecodeError:
            continue

    if not first:
        return None

    covered_first = sum(1 for v in first.values() if v == "COVERED")
    return covered_first / len(first) * 100


def _sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _ring_dasharray(pct: float, r: float = 38.0) -> tuple[float, float]:
    """Return (arc_length, gap_length) for an SVG circle of radius *r*."""
    circumference = 2 * math.pi * r
    arc = circumference * pct / 100.0
    return round(arc, 2), round(circumference - arc, 2)


# ---------------------------------------------------------------------------
# HTML render
# ---------------------------------------------------------------------------

def _render_html(
    rows: list[MatrixRow],
    summary: MatrixSummary,
    spec_name: str,
    commit_sha: str,
    generated_at: str,
    history_pct: float | None,
) -> str:
    """Render the Jinja2 template to an HTML string."""
    tmpl_dir = Path(__file__).parent / "templates"
    loader = jinja2.FileSystemLoader(str(tmpl_dir))
    env = jinja2.Environment(loader=loader, autoescape=True)

    arc, gap = _ring_dasharray(summary.coverage_pct)

    tmpl = env.get_template("rtm.html.j2")
    return tmpl.render(
        rows=rows,
        summary=summary,
        spec_name=spec_name,
        commit_sha=commit_sha,
        generated_at=generated_at,
        history_pct=history_pct,
        ring_arc=arc,
        ring_gap=gap,
    )


# ---------------------------------------------------------------------------
# CSV render
# ---------------------------------------------------------------------------

def _render_csv(rows: list[MatrixRow]) -> str:
    """Return the RTM as a CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "req_id", "priority", "area", "text",
        "verdict", "code_refs", "tests", "rationale",
    ])
    for row in rows:
        code = "; ".join(f"{r.path}:{r.line}" for r in row.code_refs)
        tests = "; ".join(r.node for r in row.test_refs)
        writer.writerow([
            row.requirement.req_id,
            row.requirement.priority,
            row.requirement.area,
            row.requirement.text,
            row.verdict,
            code,
            tests,
            row.rationale,
        ])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def _build_manifest(
    files: dict[str, Path],
    spec_path: str,
    commit_sha: str,
    generated_at: str,
) -> str:
    """Return the MANIFEST.sha256 text content.

    Format (one entry per line)::

        <sha256>  <filename>
        spec_path: <spec_path>
        commit: <commit_sha>
        generated_at: <generated_at>
    """
    lines: list[str] = []
    for name, path in files.items():
        lines.append(f"{_sha256_file(path)}  {name}")
    lines.append(f"spec_path: {spec_path}")
    lines.append(f"commit: {commit_sha}")
    lines.append(f"generated_at: {generated_at}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_report(
    repo_path: str | Path,
    spec_path: str | Path | None = None,
) -> tuple[ReportPaths, ReportSummary]:
    """Render the RTM report for *repo_path*.

    Reads ``<repo>/.traceproof/requirements.json`` and
    ``<repo>/.traceproof/evidence.json``, builds the matrix, and writes:

    * ``<repo>/.traceproof/reports/rtm.html``  — self-contained HTML report
    * ``<repo>/.traceproof/reports/rtm.csv``   — flat CSV export
    * ``<repo>/.traceproof/reports/audit_pack.zip`` — zip containing all
      of the above plus ``evidence.json``, ``requirements.json``,
      ``tests.json``, and ``MANIFEST.sha256``.

    Args:
        repo_path: Root directory of the target repository.
        spec_path: Optional path to the specification document (used only
            for display in the report header and the manifest).

    Returns:
        A ``(ReportPaths, ReportSummary)`` tuple.
    """
    repo = Path(repo_path).resolve()
    out_dir = repo / _STORE_DIR / _REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── load data ──────────────────────────────────────────────────────────
    requirements = _load_requirements(repo)
    evidence = latest_evidence(repo)
    test_results = _load_tests(repo)
    matrix = build_matrix(requirements, evidence, test_results)
    rows = matrix.rows
    summary = matrix.summary

    # ── metadata ───────────────────────────────────────────────────────────
    commit_sha = _git_sha(repo)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    spec_name = Path(spec_path).name if spec_path else ""
    history_pct = _first_coverage_pct(repo)
    # Only show history strip when coverage actually changed
    if history_pct is not None and abs(history_pct - summary.coverage_pct) < 0.05:
        history_pct = None

    # ── HTML ───────────────────────────────────────────────────────────────
    html_path = out_dir / "rtm.html"
    html_content = _render_html(
        rows, summary, spec_name, commit_sha, generated_at, history_pct
    )
    html_path.write_text(html_content, encoding="utf-8")

    # ── CSV ────────────────────────────────────────────────────────────────
    csv_path = out_dir / "rtm.csv"
    csv_path.write_text(_render_csv(rows), encoding="utf-8", newline="")

    # ── audit_pack.zip ─────────────────────────────────────────────────────
    store_dir = repo / _STORE_DIR
    ev_src    = store_dir / _EVIDENCE_FILE
    reqs_src  = store_dir / _REQS_FILE
    tests_src = store_dir / _TESTS_FILE

    # Build manifest first (needs the actual files to hash)
    pack_files: dict[str, Path] = {"rtm.html": html_path, "rtm.csv": csv_path}
    for name, src in [
        (_EVIDENCE_FILE,  ev_src),
        (_REQS_FILE,      reqs_src),
        (_TESTS_FILE,     tests_src),
    ]:
        if src.exists():
            pack_files[name] = src

    manifest_text = _build_manifest(
        pack_files,
        str(spec_path) if spec_path else "",
        commit_sha,
        generated_at,
    )
    manifest_path = out_dir / "MANIFEST.sha256"
    manifest_path.write_text(manifest_text, encoding="utf-8")

    zip_path = out_dir / "audit_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arc_name, src_path in pack_files.items():
            zf.write(src_path, arc_name)
        zf.writestr("MANIFEST.sha256", manifest_text)

    # ── result ─────────────────────────────────────────────────────────────
    critical_gaps = sum(
        1 for g in summary.gaps if g.requirement.priority == "Critical"
    )
    rp = ReportPaths(html=html_path, csv=csv_path, zip=zip_path)
    rs = ReportSummary(
        total=summary.total,
        covered=summary.covered,
        coverage_pct=round(summary.coverage_pct, 1),
        by_verdict=summary.by_verdict,
        critical_gaps=critical_gaps,
        commit_sha=commit_sha,
        generated_at=generated_at,
    )
    return rp, rs
