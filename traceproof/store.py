"""Append-only evidence store backed by a newline-delimited JSON file.

The store lives at ``<repo>/.traceproof/evidence.json``.  Every call to
:func:`record` appends a single JSON object as a new line.  History is never
mutated; callers retrieve the *latest* record per requirement via
:func:`latest` and the full history for one requirement via :func:`history`.

An anti-hallucination guard in :func:`record` validates every :class:`CodeRef`
— the referenced file must exist inside the repo **and** the cited line must
fall within the file's actual length.  A :class:`ValueError` is raised if
either check fails.
"""
from __future__ import annotations

import json
from pathlib import Path

from traceproof.models import Evidence


_STORE_DIR = ".traceproof"
_STORE_FILE = "evidence.json"


def _store_path(repo_path: str | Path) -> Path:
    return Path(repo_path) / _STORE_DIR / _STORE_FILE


def _validate_code_refs(evidence: Evidence, repo_path: Path) -> None:
    """Raise ValueError if any CodeRef points to a missing file or invalid line."""
    for ref in evidence.code_refs:
        target = repo_path / ref.path
        if not target.exists():
            raise ValueError(
                f"CodeRef validation failed for req_id='{evidence.req_id}': "
                f"file '{ref.path}' does not exist under repo '{repo_path}'."
            )
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if ref.line < 1 or ref.line > len(lines):
            raise ValueError(
                f"CodeRef validation failed for req_id='{evidence.req_id}': "
                f"line {ref.line} is out of range for '{ref.path}' "
                f"(file has {len(lines)} lines)."
            )


def record(evidence: Evidence, repo_path: str | Path) -> None:
    """Append *evidence* to the store after validating all code references.

    Args:
        evidence: The :class:`~traceproof.models.Evidence` record to persist.
        repo_path: Root directory of the repository.  The store file is created
            at ``<repo_path>/.traceproof/evidence.json``.

    Raises:
        ValueError: If any :class:`~traceproof.models.CodeRef` in *evidence*
            references a file that does not exist under *repo_path*, or cites
            a line number outside the file's actual line count.
    """
    root = Path(repo_path)
    _validate_code_refs(evidence, root)

    store = _store_path(root)
    store.parent.mkdir(parents=True, exist_ok=True)

    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(evidence.to_dict()) + "\n")


def latest(repo_path: str | Path) -> dict[str, Evidence]:
    """Return the most-recent evidence record per requirement.

    Reads the entire store and folds by ``req_id``, keeping the **last** entry
    encountered (newest-last append order).

    Args:
        repo_path: Root directory of the repository.

    Returns:
        Mapping of ``req_id`` → latest :class:`~traceproof.models.Evidence`.
        Empty dict when no store file exists yet.
    """
    store = _store_path(Path(repo_path))
    if not store.exists():
        return {}

    result: dict[str, Evidence] = {}
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            ev = Evidence.from_dict(data)
            result[ev.req_id] = ev  # last one wins
        except (json.JSONDecodeError, KeyError):
            continue  # skip malformed lines

    return result


def history(req_id: str, repo_path: str | Path) -> list[Evidence]:
    """Return the full chronological evidence history for *req_id*.

    Args:
        req_id: The requirement identifier to filter on.
        repo_path: Root directory of the repository.

    Returns:
        List of :class:`~traceproof.models.Evidence` records in append order
        (oldest first).  Empty list when no records exist for *req_id*.
    """
    store = _store_path(Path(repo_path))
    if not store.exists():
        return []

    results: list[Evidence] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if data.get("req_id") == req_id:
                results.append(Evidence.from_dict(data))
        except (json.JSONDecodeError, KeyError):
            continue

    return results
