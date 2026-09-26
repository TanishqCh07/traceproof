"""MCP server — exposes the TraceProof engine to Bob over stdio (MCP 2.x).

Entry point: ``python -m traceproof.mcp_server``

Tools
-----
extract_requirements  Parse a spec document and return requirement dicts.
index_repo            Walk a repo and return compact symbol/test summary.
run_tests             Run pytest inside a repo and return pass/fail results.
record_evidence       Append an evidence record to the store.
get_matrix            Build and return the full RTM for a repo.
get_gaps              Return gap rows sorted by severity.
render_report         Stub — returns a placeholder message until step 3.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="traceproof",
    title="TraceProof",
    description="Requirements traceability audit engine for Bob.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQ_FILE = "requirements.json"
_STORE_DIR = ".traceproof"


def _load_requirements(repo_path: str | Path) -> list[Any]:
    """Load requirements from <repo>/.traceproof/requirements.json.

    Returns the parsed list, or raises a descriptive RuntimeError when the
    file does not exist (caller should tell the LLM to run scan first).
    """
    p = Path(repo_path) / _STORE_DIR / _REQ_FILE
    if not p.exists():
        raise RuntimeError(
            f"No requirements.json found at '{p}'. "
            "Please run `traceproof scan --spec <spec> --repo <repo>` first, "
            "or call extract_requirements and ensure the file is written."
        )
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tool: extract_requirements
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Parse a specification document (PDF, DOCX, Markdown, or .txt) and return "
        "a list of requirement objects {req_id, text, area, priority}. "
        "Also writes <spec_dir>/.traceproof/requirements.json when spec_path is inside "
        "a repo — but for isolated extraction the caller must persist the list manually."
    )
)
def extract_requirements(spec_path: str) -> list[dict[str, Any]]:
    """Extract requirements from a specification document.

    Args:
        spec_path: Absolute or repo-relative path to the specification file.

    Returns:
        List of requirement dicts with keys req_id, text, area, priority.
    """
    from traceproof.extract import extract_requirements as _extract
    from traceproof.models import requirement_to_dict

    reqs = _extract(spec_path)
    return [requirement_to_dict(r) for r in reqs]


# ---------------------------------------------------------------------------
# Tool: index_repo
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Walk a repository and build a compact symbol and test index. "
        "Returns {symbols: [{name, kind, file, line}], tests: [{name, kind, file, line, node}], "
        "totals: {symbols, tests}}."
    )
)
def index_repo(repo_path: str) -> dict[str, Any]:
    """Index a Python repository.

    Args:
        repo_path: Absolute or relative path to the repository root.

    Returns:
        Compact dict with keys 'symbols', 'tests', and 'totals'.
    """
    from traceproof.index import index_repo as _index

    idx = _index(repo_path)
    symbols = [
        {"name": s.name, "kind": s.kind, "file": s.path, "line": s.line}
        for s in idx.symbols
    ]
    tests = [
        {"name": t.name, "kind": "test", "file": t.path, "line": t.line, "node": t.node}
        for t in idx.tests
    ]
    return {
        "symbols": symbols,
        "tests": tests,
        "totals": {"symbols": len(symbols), "tests": len(tests)},
    }


# ---------------------------------------------------------------------------
# Tool: run_tests
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Run pytest inside a repository and return individual test results. "
        "Returns {results: [{node, file, line, passed}], totals: {total, passed, failed, skipped}}."
    )
)
def run_tests(repo_path: str) -> dict[str, Any]:
    """Run pytest inside a repository.

    Args:
        repo_path: Absolute or relative path to the repository root.

    Returns:
        Dict with 'results' list and 'totals' summary.
    """
    from traceproof.runner import run_tests as _run

    refs = _run(repo_path)
    results = [
        {"node": r.node, "file": r.path, "line": r.line, "passed": r.passed}
        for r in refs
    ]
    total = len(results)
    passed = sum(1 for r in results if r["passed"] is True)
    failed = sum(1 for r in results if r["passed"] is False)
    skipped = total - passed - failed
    return {
        "results": results,
        "totals": {"total": total, "passed": passed, "failed": failed, "skipped": skipped},
    }


# ---------------------------------------------------------------------------
# Tool: record_evidence
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Append an evidence record to the store at <repo>/.traceproof/evidence.json. "
        "code_refs is a list of 'file:line' strings (e.g. 'payflow/payments.py:42'). "
        "test_refs is a list of pytest node IDs (e.g. 'tests/test_payments.py::test_foo'). "
        "Returns the stored record dict on success, or an error message string when the "
        "anti-hallucination guard rejects a code reference."
    )
)
def record_evidence(
    repo_path: str,
    req_id: str,
    verdict: str,
    code_refs: list[str],
    test_refs: list[str],
    rationale: str,
) -> dict[str, Any] | str:
    """Record audit evidence for a requirement.

    Args:
        repo_path: Absolute or relative path to the repository root.
        req_id: Requirement identifier (e.g. 'PF-001').
        verdict: One of COVERED, UNTESTED, DRIFT, VIOLATION, MISSING.
        code_refs: List of 'file:line' strings pointing to implementing code.
        test_refs: List of pytest node IDs for related tests.
        rationale: Free-text explanation for this verdict.

    Returns:
        Stored evidence dict on success, or an error message string on validation
        failure (no exception is raised so the caller can surface the message).
    """
    from traceproof.models import CodeRef, Evidence, TestRef, Verdict
    from traceproof.store import record

    # Parse verdict
    try:
        v = Verdict(verdict.upper())
    except ValueError:
        valid = [x.value for x in Verdict]
        return f"Invalid verdict '{verdict}'. Must be one of: {valid}"

    # Parse code_refs: "file:line"
    parsed_code: list[CodeRef] = []
    for ref_str in code_refs:
        parts = ref_str.rsplit(":", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            return (
                f"Malformed code_ref '{ref_str}'. "
                "Expected format 'relative/file/path.py:LINE_NUMBER'."
            )
        parsed_code.append(
            CodeRef(req_id=req_id, path=parts[0], line=int(parts[1]), symbol="")
        )

    # Parse test_refs: pytest node IDs — derive path from "path/to/test.py::test_name"
    parsed_tests: list[TestRef] = []
    for node in test_refs:
        file_part = node.split("::")[0]
        parsed_tests.append(
            TestRef(req_id=req_id, path=file_part, line=0, node=node, passed=None)
        )

    # Load requirements to derive severity (priority)
    severity = ""
    try:
        reqs_data = _load_requirements(repo_path)
        for r in reqs_data:
            if r.get("req_id") == req_id:
                severity = r.get("priority", "")
                break
    except RuntimeError:
        pass  # severity stays empty; not fatal

    ev = Evidence(
        req_id=req_id,
        verdict=v,
        code_refs=parsed_code,
        test_refs=parsed_tests,
        rationale=rationale,
        severity=severity,
    )

    try:
        record(ev, repo_path)
    except ValueError as exc:
        return f"Evidence rejected by anti-hallucination guard: {exc}"

    return ev.to_dict()


# ---------------------------------------------------------------------------
# Tool: get_matrix
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Build and return the full requirements traceability matrix (RTM) for a repo. "
        "Requires <repo>/.traceproof/requirements.json (run scan first). "
        "Returns {summary: {...}, rows: [{req_id, text, verdict, rationale, ...}]}."
    )
)
def get_matrix(repo_path: str) -> dict[str, Any]:
    """Build the RTM from stored requirements + evidence.

    Args:
        repo_path: Absolute or relative path to the repository root.

    Returns:
        Full matrix dict with 'summary' and 'rows'.
    """
    from traceproof.matrix import build_matrix
    from traceproof.models import requirement_from_dict
    from traceproof.store import latest as latest_evidence

    reqs_data = _load_requirements(repo_path)
    requirements = [requirement_from_dict(d) for d in reqs_data]
    evidence = latest_evidence(repo_path)
    matrix = build_matrix(requirements, evidence, [])
    return matrix.to_dict()


# ---------------------------------------------------------------------------
# Tool: get_gaps
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Return gap rows (non-COVERED requirements) sorted by severity. "
        "severity filter is optional: pass 'Critical', 'High', 'Medium', or 'Low' to narrow results. "
        "Returns {gaps: [{req_id, text, priority, verdict, rationale}], total_gaps: N}."
    )
)
def get_gaps(repo_path: str, severity: str | None = None) -> dict[str, Any]:
    """Return gap rows from the RTM, optionally filtered by priority/severity.

    Args:
        repo_path: Absolute or relative path to the repository root.
        severity: Optional priority filter — 'Critical', 'High', 'Medium', or 'Low'.

    Returns:
        Dict with 'gaps' list and 'total_gaps' count.
    """
    from traceproof.matrix import build_matrix
    from traceproof.models import requirement_from_dict
    from traceproof.store import latest as latest_evidence

    reqs_data = _load_requirements(repo_path)
    requirements = [requirement_from_dict(d) for d in reqs_data]
    evidence = latest_evidence(repo_path)
    matrix = build_matrix(requirements, evidence, [])

    gaps = matrix.summary.gaps
    if severity:
        gaps = [g for g in gaps if g.requirement.priority.lower() == severity.lower()]

    return {
        "gaps": [
            {
                "req_id": g.requirement.req_id,
                "text": g.requirement.text,
                "priority": g.requirement.priority,
                "verdict": g.verdict,
                "rationale": g.rationale,
            }
            for g in gaps
        ],
        "total_gaps": len(gaps),
    }


# ---------------------------------------------------------------------------
# Tool: render_report
# ---------------------------------------------------------------------------

@mcp.tool(
    description=(
        "Render the RTM as a human-readable report. "
        "Writes <repo>/.traceproof/reports/rtm.html, rtm.csv, and audit_pack.zip. "
        "Returns {html, csv, zip, summary} with paths and headline statistics."
    )
)
def render_report(repo_path: str, spec_path: str | None = None) -> dict[str, Any]:
    """Render the RTM HTML/CSV/ZIP report.

    Args:
        repo_path: Absolute or relative path to the repository root.
        spec_path: Optional path to the specification document (for display only).

    Returns:
        Dict with keys 'html', 'csv', 'zip' (file paths) and 'summary' (statistics).
    """
    from traceproof.report import render_report as _render

    paths, summary = _render(repo_path, spec_path)
    return {
        "html": str(paths.html),
        "csv": str(paths.csv),
        "zip": str(paths.zip),
        "summary": {
            "total": summary.total,
            "covered": summary.covered,
            "coverage_pct": summary.coverage_pct,
            "by_verdict": summary.by_verdict,
            "critical_gaps": summary.critical_gaps,
            "commit_sha": summary.commit_sha,
            "generated_at": summary.generated_at,
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
