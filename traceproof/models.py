"""Data model for TraceProof — single source of truth for all shared types.

All other modules import from here; never redefine these types elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    """Audit verdict for a single requirement."""

    COVERED = "COVERED"
    UNTESTED = "UNTESTED"
    DRIFT = "DRIFT"
    VIOLATION = "VIOLATION"
    MISSING = "MISSING"


@dataclass
class Requirement:
    """A single requirement extracted from a specification document."""

    req_id: str
    text: str
    area: str
    priority: str  # Critical | High | Medium | Low


@dataclass
class CodeRef:
    """A reference to the line in the codebase that implements a requirement."""

    req_id: str
    path: str   # repo-relative path
    line: int
    symbol: str  # function / class name


@dataclass
class TestRef:
    """A reference to a pytest test that asserts a requirement's behaviour."""

    req_id: str
    path: str
    line: int
    node: str        # pytest node id, e.g. "tests/test_foo.py::test_bar"
    passed: bool | None = None  # None = not yet run


@dataclass
class Evidence:
    """Audit evidence record for one requirement (appended to the evidence store)."""

    req_id: str
    verdict: Verdict
    code_refs: list[CodeRef] = field(default_factory=list)
    test_refs: list[TestRef] = field(default_factory=list)
    rationale: str = ""
    severity: str = ""  # derived from Requirement.priority at record time
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------ JSON helpers

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON output."""
        return {
            "req_id": self.req_id,
            "verdict": self.verdict.value,
            "code_refs": [
                {"req_id": r.req_id, "path": r.path, "line": r.line, "symbol": r.symbol}
                for r in self.code_refs
            ],
            "test_refs": [
                {
                    "req_id": r.req_id,
                    "path": r.path,
                    "line": r.line,
                    "node": r.node,
                    "passed": r.passed,
                }
                for r in self.test_refs
            ],
            "rationale": self.rationale,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        """Deserialise from a plain dict (e.g. loaded from evidence.json)."""
        code_refs = [
            CodeRef(
                req_id=r["req_id"],
                path=r["path"],
                line=r["line"],
                symbol=r["symbol"],
            )
            for r in data.get("code_refs", [])
        ]
        test_refs = [
            TestRef(
                req_id=r["req_id"],
                path=r["path"],
                line=r["line"],
                node=r["node"],
                passed=r.get("passed"),
            )
            for r in data.get("test_refs", [])
        ]
        return cls(
            req_id=data["req_id"],
            verdict=Verdict(data["verdict"]),
            code_refs=code_refs,
            test_refs=test_refs,
            rationale=data.get("rationale", ""),
            severity=data.get("severity", ""),
            timestamp=data.get("timestamp", ""),
        )


def requirement_to_dict(req: Requirement) -> dict[str, Any]:
    """Serialise a Requirement to a plain dict."""
    return {
        "req_id": req.req_id,
        "text": req.text,
        "area": req.area,
        "priority": req.priority,
    }


def requirement_from_dict(data: dict[str, Any]) -> Requirement:
    """Deserialise a Requirement from a plain dict."""
    return Requirement(
        req_id=data["req_id"],
        text=data["text"],
        area=data["area"],
        priority=data["priority"],
    )
