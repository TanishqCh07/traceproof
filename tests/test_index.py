"""Tests for traceproof.index — AST-based repository indexer."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from traceproof.index import RepoIndex, SymbolEntry, TestEntry, index_repo

# Path to the demo payflow repo (relative to workspace root).
DEMO_REPO = Path("demo/payflow")
EXPECTED_TEST_COUNT = 27


class TestDemoRepo:
    """Integration tests against the real demo/payflow codebase."""

    def test_finds_all_demo_tests(self):
        idx = index_repo(DEMO_REPO)
        assert len(idx.tests) == EXPECTED_TEST_COUNT, (
            f"Expected {EXPECTED_TEST_COUNT} tests, found {len(idx.tests)}: "
            + ", ".join(t.name for t in idx.tests)
        )

    def test_all_tests_have_node_ids(self):
        idx = index_repo(DEMO_REPO)
        for t in idx.tests:
            assert "::" in t.node, f"Bad node id: {t.node}"
            assert t.name in t.node

    def test_finds_refund_window_constant(self):
        idx = index_repo(DEMO_REPO)
        matches = [s for s in idx.symbols if s.name == "REFUND_WINDOW"]
        assert len(matches) >= 1, "REFUND_WINDOW constant not found"
        rw = matches[0]
        assert rw.kind == "constant"
        assert "service.py" in rw.path
        assert rw.line > 0
        # The value should capture the timedelta expression
        assert "60" in rw.value or "timedelta" in rw.value, (
            f"Expected value to contain '60' or 'timedelta', got: {rw.value!r}"
        )

    def test_finds_max_requests_per_minute_constant(self):
        idx = index_repo(DEMO_REPO)
        matches = [s for s in idx.symbols if s.name == "MAX_REQUESTS_PER_MINUTE"]
        assert len(matches) >= 1, "MAX_REQUESTS_PER_MINUTE constant not found"
        assert matches[0].value == "20"

    def test_finds_payment_service_class(self):
        idx = index_repo(DEMO_REPO)
        classes = [s for s in idx.symbols if s.name == "PaymentService"]
        assert len(classes) >= 1

    def test_test_names_include_expected_tests(self):
        idx = index_repo(DEMO_REPO)
        test_names = {t.name for t in idx.tests}
        expected = {
            "test_happy_path_lifecycle",
            "test_rejects_unsupported_currency",
            "test_rate_limit_per_merchant",
            "test_idempotent_create_returns_same_payment",
        }
        missing = expected - test_names
        assert not missing, f"Missing expected tests: {missing}"

    def test_test_paths_are_relative(self):
        idx = index_repo(DEMO_REPO)
        for t in idx.tests:
            assert not Path(t.path).is_absolute(), f"Path should be relative: {t.path}"

    def test_no_venv_files_indexed(self):
        idx = index_repo(DEMO_REPO)
        for s in idx.symbols:
            assert ".venv" not in s.path and "venv" not in s.path.lower().split("/")[0]
        for t in idx.tests:
            assert ".venv" not in t.path

    def test_symbols_by_name_helper(self):
        idx = index_repo(DEMO_REPO)
        matches = idx.symbols_by_name("REFUND_WINDOW")
        assert len(matches) >= 1
        assert all(s.name == "REFUND_WINDOW" for s in matches)

    def test_req_id_in_comment_captured(self):
        """Comments like '# PF-003 idempotency' should associate the ID with nearby symbols."""
        idx = index_repo(DEMO_REPO)
        # service.py has '# PF-003 idempotency' and '# PF-012: ...' style comments
        all_req_ids: list[str] = []
        for s in idx.symbols:
            all_req_ids.extend(s.req_ids)
        for t in idx.tests:
            all_req_ids.extend(t.req_ids)
        assert "PF-003" in all_req_ids, "PF-003 comment not picked up from service.py"

    def test_test_asserted_literals_captured(self):
        """Tests that assert e.value.code == '...' should have the code string captured."""
        idx = index_repo(DEMO_REPO)
        currency_test = next(
            (t for t in idx.tests if t.name == "test_rejects_unsupported_currency"), None
        )
        assert currency_test is not None
        assert "UNSUPPORTED_CURRENCY" in currency_test.asserted_literals, (
            f"Expected 'UNSUPPORTED_CURRENCY' in asserted_literals, "
            f"got: {currency_test.asserted_literals}"
        )


class TestSyntheticRepo:
    """Unit tests against a small synthetic repository written to a tmp dir."""

    def _write_repo(self, tmp_path: Path, files: dict[str, str]) -> Path:
        for rel, content in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(content))
        return tmp_path

    def test_constant_extracted(self, tmp_path: Path):
        self._write_repo(tmp_path, {"pkg/cfg.py": """\
            \"\"\"Config.\"\"\"
            TIMEOUT = 30
        """})
        idx = index_repo(tmp_path)
        matches = idx.symbols_by_name("TIMEOUT")
        assert len(matches) == 1
        assert matches[0].kind == "constant"
        assert matches[0].value == "30"

    def test_function_extracted(self, tmp_path: Path):
        self._write_repo(tmp_path, {"pkg/utils.py": """\
            \"\"\"Utils.\"\"\"
            def helper():
                \"\"\"Does nothing.\"\"\"
                pass
        """})
        idx = index_repo(tmp_path)
        fns = [s for s in idx.symbols if s.name == "helper"]
        assert len(fns) == 1
        assert fns[0].kind == "function"
        assert "Does nothing" in fns[0].docstring

    def test_test_function_goes_to_tests_not_symbols(self, tmp_path: Path):
        self._write_repo(tmp_path, {"tests/test_foo.py": """\
            \"\"\"Tests.\"\"\"
            def test_something():
                assert 1 + 1 == 2
        """})
        idx = index_repo(tmp_path)
        assert any(t.name == "test_something" for t in idx.tests)
        assert not any(s.name == "test_something" for s in idx.symbols)

    def test_venv_skipped(self, tmp_path: Path):
        self._write_repo(tmp_path, {
            "src/app.py": '"""App."""\nVAL = 1\n',
            ".venv/lib/foo.py": '"""Should not index."""\nSECRET = 99\n',
        })
        idx = index_repo(tmp_path)
        assert not any(s.name == "SECRET" for s in idx.symbols)
        assert any(s.name == "VAL" for s in idx.symbols)

    def test_req_id_in_inline_comment(self, tmp_path: Path):
        self._write_repo(tmp_path, {"src/svc.py": """\
            \"\"\"Service.\"\"\"
            WINDOW = 30  # PF-005 refund window
        """})
        idx = index_repo(tmp_path)
        matches = idx.symbols_by_name("WINDOW")
        assert len(matches) == 1
        assert "PF-005" in matches[0].req_ids

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            index_repo("/nonexistent/path/to/repo")

    def test_returns_repo_index_instance(self, tmp_path: Path):
        idx = index_repo(tmp_path)
        assert isinstance(idx, RepoIndex)
