"""Tests for oar.query.output_filer — OutputFiler (no LLM calls)."""

import re
from datetime import datetime
from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.query.engine import QueryResult
from oar.query.output_filer import FiledOutput, OutputFiler


def _make_result(
    answer: str = "Test answer.",
    sources: list[str] | None = None,
    tool_calls: int = 0,
    tokens_used: int = 150,
    cost_usd: float = 0.003,
) -> QueryResult:
    """Convenience factory for QueryResult."""
    return QueryResult(
        answer=answer,
        sources_consulted=sources or [],
        tool_calls=tool_calls,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
    )


class TestFileAnswer:
    """file_answer creates a properly formatted answer file."""

    def test_file_answer_creates_file(self, tmp_vault):
        """Answer file exists in 04-outputs/answers/."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result(answer="It is 42.")
        filed = filer.file_answer("What is the meaning?", result)

        assert filed.path.exists()
        assert filed.path.parent == tmp_vault / "04-outputs" / "answers"

    def test_file_answer_has_correct_frontmatter(self, tmp_vault):
        """Frontmatter includes id, type, question, sources."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result(
            answer="It is 42.",
            sources=["some-article"],
            tool_calls=1,
            tokens_used=200,
            cost_usd=0.005,
        )
        filed = filer.file_answer("What is the meaning?", result)

        fm = FrontmatterManager()
        meta, body = fm.read(filed.path)

        assert meta["id"] == filed.article_id
        assert meta["type"] == "answer"
        assert meta["question"] == "What is the meaning?"
        assert meta["sources_consulted"] == ["some-article"]
        assert meta["tool_calls"] == 1
        assert meta["tokens_used"] == 200
        assert meta["cost_usd"] == 0.005

    def test_file_answer_content_preserved(self, tmp_vault):
        """Answer text appears in file body."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        answer_text = "The answer involves [[attention-mechanism]] and self-attention."
        result = _make_result(answer=answer_text)
        filed = filer.file_answer("Explain attention", result)

        fm = FrontmatterManager()
        meta, body = fm.read(filed.path)

        assert answer_text in body

    def test_file_answer_generates_id(self, tmp_vault):
        """Article ID format: YYYY-MM-DD-slug."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result()
        filed = filer.file_answer("What is transformer architecture?", result)

        # Should match YYYY-MM-DD-slug pattern
        pattern = r"^\d{4}-\d{2}-\d{2}-what-is-transformer-architecture$"
        assert re.match(pattern, filed.article_id), f"ID was: {filed.article_id}"

    def test_file_answer_updates_cited_articles(
        self, tmp_vault, sample_compiled_article
    ):
        """Cited article's see_also gets updated with output link."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result(
            answer="See [[transformer-architecture]] for details.",
            sources=["transformer-architecture"],
        )
        filed = filer.file_answer("What is a transformer?", result)

        # Check that the compiled article was updated.
        fm = FrontmatterManager()
        meta, _ = fm.read(sample_compiled_article)
        see_also = meta.get("see_also", [])

        assert f"[[{filed.article_id}]]" in see_also
        assert "transformer-architecture" in filed.filed_into

    def test_file_answer_skips_missing_citations(self, tmp_vault):
        """No error when a cited article doesn't exist."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result(
            answer="Something.",
            sources=["nonexistent-article"],
        )
        filed = filer.file_answer("Mystery question?", result)

        # Should succeed without error, just no backlinks added.
        assert filed.path.exists()
        assert filed.filed_into == []

    def test_file_answer_returns_filed_output(self, tmp_vault):
        """Return type is FiledOutput with correct fields."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        result = _make_result(sources=["source-a", "source-b"])
        filed = filer.file_answer("Test question?", result)

        assert isinstance(filed, FiledOutput)
        assert isinstance(filed.path, Path)
        assert isinstance(filed.article_id, str)
        assert filed.cited_articles == ["source-a", "source-b"]

    def test_file_answer_word_count(self, tmp_vault):
        """Word count is computed and stored in frontmatter."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        answer = "This is a test answer with exactly eight words."
        result = _make_result(answer=answer)
        filed = filer.file_answer("Word count test", result)

        fm = FrontmatterManager()
        meta, _ = fm.read(filed.path)

        assert meta["word_count"] == len(answer.split())


class TestFileReport:
    """file_report saves reports to 04-outputs/reports/."""

    def test_file_report_creates_file(self, tmp_vault):
        """Report file exists in 04-outputs/reports/."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        filed = filer.file_report(
            title="Weekly Summary",
            content="# Weekly Summary\n\nThis week was productive.",
        )

        assert filed.path.exists()
        assert filed.path.parent == tmp_vault / "04-outputs" / "reports"

    def test_file_report_has_metadata(self, tmp_vault):
        """Frontmatter has type: report, title, sources."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        filed = filer.file_report(
            title="Weekly Summary",
            content="Report body here.",
            sources=["article-a", "article-b"],
        )

        fm = FrontmatterManager()
        meta, body = fm.read(filed.path)

        assert meta["type"] == "report"
        assert meta["title"] == "Weekly Summary"
        assert meta["sources_consulted"] == ["article-a", "article-b"]
        assert "Report body here." in body

    def test_file_report_no_sources(self, tmp_vault):
        """Report with no sources defaults to empty list."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        filer = OutputFiler(vault, ops)

        filed = filer.file_report(title="No Sources", content="Body.")

        fm = FrontmatterManager()
        meta, _ = fm.read(filed.path)

        assert meta["sources_consulted"] == []
        assert filed.cited_articles == []
