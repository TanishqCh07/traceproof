"""Command-line interface for TraceProof.

Commands
--------
scan   --spec PATH --repo PATH
    Extract requirements, index the repo, run tests, write artefacts to
    ``<repo>/.traceproof/`` and print a short summary.

check  --repo PATH --min-coverage N
    Exit 1 if coverage < N or any VIOLATION exists; print the reason.

report --output PATH [--format html|md]
    Stub — full implementation coming in step 3.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_scan(args: argparse.Namespace) -> int:
    """Extract requirements, index the repo, run tests, write artefacts."""
    from traceproof.extract import extract_requirements
    from traceproof.index import index_repo
    from traceproof.models import requirement_to_dict
    from traceproof.runner import run_tests
    from traceproof.matrix import build_matrix

    spec_path = Path(args.spec)
    repo_path = Path(args.repo)

    if not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 1
    if not repo_path.exists():
        print(f"ERROR: repo path not found: {repo_path}", file=sys.stderr)
        return 1

    # --- extract requirements
    print(f"Extracting requirements from {spec_path} …")
    requirements = extract_requirements(spec_path)
    print(f"  Found {len(requirements)} requirements.")

    # --- index the repo
    print(f"Indexing repository {repo_path} …")
    repo_index = index_repo(repo_path)
    print(f"  Symbols: {len(repo_index.symbols)}, Tests: {len(repo_index.tests)}")

    # --- run tests
    print("Running tests …")
    try:
        test_results = run_tests(repo_path)
        passed = sum(1 for t in test_results if t.passed is True)
        failed = sum(1 for t in test_results if t.passed is False)
        print(f"  Tests: {len(test_results)} total, {passed} passed, {failed} failed.")
    except RuntimeError as exc:
        print(f"  WARNING: could not run tests — {exc}", file=sys.stderr)
        test_results = []

    # --- write artefacts
    traceproof_dir = repo_path / ".traceproof"
    traceproof_dir.mkdir(parents=True, exist_ok=True)

    reqs_file = traceproof_dir / "requirements.json"
    reqs_file.write_text(
        json.dumps([requirement_to_dict(r) for r in requirements], indent=2),
        encoding="utf-8",
    )

    index_file = traceproof_dir / "index.json"
    index_data = {
        "symbols": [
            {
                "name": s.name,
                "kind": s.kind,
                "path": s.path,
                "line": s.line,
                "docstring": s.docstring,
                "value": s.value,
                "req_ids": s.req_ids,
            }
            for s in repo_index.symbols
        ],
        "tests": [
            {
                "name": t.name,
                "path": t.path,
                "line": t.line,
                "node": t.node,
                "asserted_literals": t.asserted_literals,
                "req_ids": t.req_ids,
            }
            for t in repo_index.tests
        ],
    }
    index_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    tests_file = traceproof_dir / "tests.json"
    tests_file.write_text(
        json.dumps(
            [
                {
                    "req_id": t.req_id,
                    "path": t.path,
                    "line": t.line,
                    "node": t.node,
                    "passed": t.passed,
                }
                for t in test_results
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    # --- build matrix from existing evidence (if any)
    from traceproof.store import latest as latest_evidence

    evidence = latest_evidence(repo_path)
    matrix = build_matrix(requirements, evidence, test_results)
    s = matrix.summary

    print()
    print("=== TraceProof Scan Summary ===")
    print(f"  Requirements : {s.total}")
    print(f"  Covered      : {s.covered} ({s.coverage_pct:.1f}%)")
    print(f"  Pending      : {s.by_verdict.get('PENDING', 0)}")
    print(f"  Gaps         : {len(s.gaps)}")
    if s.by_verdict:
        print("  Breakdown    :", ", ".join(f"{k}={v}" for k, v in sorted(s.by_verdict.items())))
    print(f"  Artefacts    : {traceproof_dir}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """Exit 1 if coverage < min_coverage or any VIOLATION exists."""
    from traceproof.models import requirement_from_dict
    from traceproof.runner import run_tests
    from traceproof.store import latest as latest_evidence
    from traceproof.matrix import build_matrix

    repo_path = Path(args.repo)
    if not repo_path.exists():
        print(f"ERROR: repo path not found: {repo_path}", file=sys.stderr)
        return 1

    # Load requirements from stored artefact if present, else error out
    reqs_file = repo_path / ".traceproof" / "requirements.json"
    if not reqs_file.exists():
        print(
            "ERROR: no requirements.json found — run 'traceproof scan' first.",
            file=sys.stderr,
        )
        return 1

    requirements = [
        requirement_from_dict(d)
        for d in json.loads(reqs_file.read_text(encoding="utf-8"))
    ]

    # Run tests to get fresh pass/fail data
    try:
        test_results = run_tests(repo_path)
    except RuntimeError as exc:
        print(f"WARNING: could not run tests — {exc}", file=sys.stderr)
        test_results = []

    evidence = latest_evidence(repo_path)
    matrix = build_matrix(requirements, evidence, test_results)
    s = matrix.summary

    failures: list[str] = []

    if s.coverage_pct < args.min_coverage:
        failures.append(
            f"Coverage {s.coverage_pct:.1f}% is below required {args.min_coverage}%"
        )

    violations = [r for r in matrix.rows if r.verdict == "VIOLATION"]
    if violations:
        ids = ", ".join(r.requirement.req_id for r in violations)
        failures.append(f"VIOLATION(s) found: {ids}")

    if failures:
        print("CHECK FAILED:")
        for msg in failures:
            print(f"  - {msg}")
        return 1

    print(
        f"CHECK PASSED: coverage {s.coverage_pct:.1f}% >= {args.min_coverage}%, no violations."
    )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """Stub — report generation coming in step 3."""
    print("report: coming in step 3 (not yet implemented).")
    return 0


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``traceproof`` console script."""
    parser = argparse.ArgumentParser(
        prog="traceproof",
        description="Requirements traceability audit tool.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    scan_p = sub.add_parser("scan", help="Extract, index, run tests, write artefacts.")
    scan_p.add_argument("--spec", required=True, metavar="PATH", help="Path to spec document.")
    scan_p.add_argument("--repo", required=True, metavar="PATH", help="Path to target repo.")

    # check
    check_p = sub.add_parser("check", help="CI gate: exit 1 if coverage below threshold.")
    check_p.add_argument("--repo", required=True, metavar="PATH", help="Path to target repo.")
    check_p.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        metavar="N",
        help="Minimum coverage percentage (default: 80).",
    )

    # report (stub)
    report_p = sub.add_parser("report", help="Render RTM report (coming in step 3).")
    report_p.add_argument("--output", required=True, metavar="PATH", help="Output file path.")
    report_p.add_argument(
        "--format", choices=["html", "md"], default="html", help="Output format."
    )

    args = parser.parse_args(argv)

    dispatch = {"scan": _cmd_scan, "check": _cmd_check, "report": _cmd_report}
    rc = dispatch[args.command](args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
