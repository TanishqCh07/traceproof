"""Test runner — invokes pytest in a target repo and parses results into TestRef objects.

Uses subprocess (sys.executable) so the same Python interpreter that runs TraceProof
is used for the target repo's tests.  The runner never raises on test *failures*; it
only raises if pytest itself cannot be executed (missing, import error, etc.).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from traceproof.models import TestRef


def run_tests(repo_path: str | Path, timeout: int = 120) -> list[TestRef]:
    """Run ``pytest`` inside *repo_path* and return one :class:`TestRef` per test case.

    Args:
        repo_path: Root directory of the target repository.
        timeout: Maximum seconds to wait for the pytest process (default 120).

    Returns:
        A list of :class:`~traceproof.models.TestRef` objects.  Each entry has
        ``req_id=""`` (the caller maps tests to requirements later), ``passed``
        set to ``True``/``False`` based on the JUnit XML outcome, and ``line``
        set to the line number reported by pytest (0 when not available).

    Raises:
        FileNotFoundError: If *repo_path* does not exist.
        RuntimeError: If pytest itself cannot be started (e.g. missing from the
            environment) — but **not** on ordinary test failures.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path not found: {root}")

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        junit_path = Path(tmp.name).resolve()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit_path}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Could not launch pytest via '{sys.executable}': {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"pytest timed out after {timeout}s in {root}"
        ) from exc

    # Exit code 0 = all passed, 1 = some failed, 2 = usage error, 3 = internal error, 5 = no tests
    # We only raise for exit codes that mean pytest itself could not run.
    if result.returncode in (2, 3, 4):
        raise RuntimeError(
            f"pytest could not run in {root} (exit code {result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )

    return _parse_junit(str(junit_path))


def _parse_junit(xml_path: str) -> list[TestRef]:
    """Parse a JUnit XML file produced by pytest and return :class:`TestRef` objects."""
    path = Path(xml_path)
    if not path.exists() or path.stat().st_size == 0:
        return []

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return []

    refs: list[TestRef] = []
    for tc in tree.iter("testcase"):
        classname = tc.get("classname", "")
        name = tc.get("name", "")
        file_attr = tc.get("file", "")
        line_attr = tc.get("line", "0")

        # Build the pytest node id: classname uses "." separators — convert to path
        if classname:
            node = f"{classname.replace('.', '/')}.py::{name}"
        else:
            node = name

        # Determine pass/fail: presence of <failure> or <error> child means failed
        failed = tc.find("failure") is not None or tc.find("error") is not None
        skipped = tc.find("skipped") is not None

        refs.append(
            TestRef(
                req_id="",
                path=file_attr,
                line=int(line_attr) if line_attr.isdigit() else 0,
                node=node,
                passed=None if skipped else (not failed),
            )
        )

    return refs
