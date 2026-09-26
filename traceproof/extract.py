"""Requirement extractor — parses PDF, DOCX and Markdown spec documents.

Strategy per format:
  PDF  — try pdfplumber table extraction first (structured SRS tables); fall back to
         plain-text regex scan when no table rows are found.
  DOCX — scan python-docx tables then paragraph text.
  MD   — regex scan on raw text.

All paths are parameters; no hard-coded demo paths.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from traceproof.models import Requirement

# Default pattern: 2-5 uppercase letters followed by a hyphen and 3 digits, e.g. PF-003
_DEFAULT_ID_PATTERN = r"\b[A-Z]{2,5}-\d{3}\b"

_VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}


def _normalise_text(text: str) -> str:
    """Collapse internal whitespace and newlines within a cell or paragraph."""
    return re.sub(r"\s+", " ", text).strip()


def _parse_priority(raw: str) -> str:
    """Return a canonical priority string, or 'Medium' when unrecognised."""
    cleaned = _normalise_text(raw).title()
    return cleaned if cleaned in _VALID_PRIORITIES else "Medium"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _extract_from_pdf(path: Path, id_pattern: str) -> list[Requirement]:
    """Extract requirements from a PDF file using pdfplumber."""
    try:
        import pdfplumber  # optional at import time; checked at call time
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pdfplumber is required for PDF extraction: pip install pdfplumber") from exc

    reqs: dict[str, Requirement] = {}
    id_re = re.compile(id_pattern)

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                _parse_table_rows(table, id_re, reqs)

        # Fall back to text scan if table extraction found nothing
        if not reqs:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
            _extract_from_text(full_text, id_re, reqs)

    return list(reqs.values())


def _parse_table_rows(
    table: list[list[str | None]],
    id_re: re.Pattern[str],
    reqs: dict[str, Requirement],
) -> None:
    """Parse rows from a pdfplumber table into the reqs dict.

    Expects rows shaped as [ID, Area, Priority, Requirement text] or similar.
    Skips header rows and rows that don't start with a recognised req ID.
    """
    for row in table:
        if not row:
            continue
        cells = [_normalise_text(c or "") for c in row]
        if len(cells) < 4:
            continue
        req_id_cell = cells[0]
        if not id_re.fullmatch(req_id_cell):
            continue  # header or non-requirement row
        req_id = req_id_cell
        area = cells[1]
        priority = _parse_priority(cells[2])
        text = _normalise_text(cells[3])
        if req_id not in reqs:
            reqs[req_id] = Requirement(req_id=req_id, text=text, area=area, priority=priority)


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def _extract_from_docx(path: Path, id_pattern: str) -> list[Requirement]:
    """Extract requirements from a DOCX file using python-docx."""
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise ImportError("python-docx is required for DOCX extraction: pip install python-docx") from exc

    reqs: dict[str, Requirement] = {}
    id_re = re.compile(id_pattern)
    doc = docx.Document(str(path))

    # Scan tables first (structured SRS format)
    for table in doc.tables:
        rows = [[_normalise_text(cell.text) for cell in row.cells] for row in table.rows]
        _parse_table_rows(rows, id_re, reqs)

    # Fall back to paragraph scan
    if not reqs:
        full_text = "\n".join(p.text for p in doc.paragraphs)
        _extract_from_text(full_text, id_re, reqs)

    return list(reqs.values())


# ---------------------------------------------------------------------------
# Markdown / plain text
# ---------------------------------------------------------------------------

def _extract_from_markdown(path: Path, id_pattern: str) -> list[Requirement]:
    """Extract requirements from a Markdown or plain-text file."""
    text = path.read_text(encoding="utf-8")
    reqs: dict[str, Requirement] = {}
    id_re = re.compile(id_pattern)
    _extract_from_text(text, id_re, reqs)
    return list(reqs.values())


def _extract_from_text(
    text: str,
    id_re: re.Pattern[str],
    reqs: dict[str, Requirement],
) -> None:
    """Scan free text for requirement IDs and extract surrounding context.

    Looks for lines/blocks of the form:
      PF-001  <area>  <priority>  <text>   (pipe/table delimited or space-aligned)
      or just:
      PF-001: <text>

    When structured columns are not found the full sentence containing the ID
    is captured as text with area="" and priority="Medium".
    """
    # Try pipe-table rows: | PF-001 | Area | Priority | text |
    pipe_row_re = re.compile(
        r"\|\s*(" + id_re.pattern + r")\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
    )
    for m in pipe_row_re.finditer(text):
        req_id, area, priority, req_text = m.group(1), m.group(2), m.group(3), m.group(4)
        if req_id not in reqs:
            reqs[req_id] = Requirement(
                req_id=req_id,
                text=_normalise_text(req_text),
                area=_normalise_text(area),
                priority=_parse_priority(priority),
            )

    # Plain "PF-001: text" or "PF-001 text" lines (fallback)
    if not reqs:
        line_re = re.compile(r"(" + id_re.pattern + r")[:\s]\s*(.+)")
        for m in line_re.finditer(text):
            req_id = m.group(1)
            req_text = _normalise_text(m.group(2))
            if req_id not in reqs:
                reqs[req_id] = Requirement(
                    req_id=req_id, text=req_text, area="", priority="Medium"
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, Callable[[Path, str], list[Requirement]]] = {
    ".pdf": _extract_from_pdf,
    ".docx": _extract_from_docx,
    ".md": _extract_from_markdown,
    ".txt": _extract_from_markdown,
}


def extract_requirements(
    path: str | Path,
    id_pattern: str = _DEFAULT_ID_PATTERN,
) -> list[Requirement]:
    """Parse a spec document and return deduplicated requirements.

    Supported formats: PDF, DOCX, Markdown (.md), plain text (.txt).

    Args:
        path: Path to the specification document.
        id_pattern: Regex pattern for requirement IDs (default: ``r"\\b[A-Z]{2,5}-\\d{3}\\b"``).

    Returns:
        List of :class:`~traceproof.models.Requirement` objects, deduplicated by ``req_id``,
        in the order first encountered.

    Raises:
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec file not found: {p}")
    suffix = p.suffix.lower()
    extractor = _EXTRACTORS.get(suffix)
    if extractor is None:
        raise ValueError(
            f"Unsupported spec format '{suffix}'. Supported: {list(_EXTRACTORS)}"
        )
    return extractor(p, id_pattern)
