"""Tests for oar.compile.context_builder — CompileContextBuilder."""

from pathlib import Path

from oar.compile.context_builder import CompileContextBuilder
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


def _setup_builder(tmp_vault: Path):
    """Create a CompileContextBuilder with a real vault."""
    vault = Vault(tmp_vault)
    ops = VaultOps(vault)
    return CompileContextBuilder(vault, ops), ops


class TestBuildSingleContext:
    """build_single_context returns the raw article body."""

    def test_build_single_context_includes_body(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        raw_path = ops.write_raw_article(
            "single-ctx.md",
            {"id": "single-ctx", "title": "Single Context", "source_type": "article"},
            "This is the body text of the article.",
        )

        result = builder.build_single_context(raw_path)
        assert "This is the body text of the article." in result


class TestBuildMultiContext:
    """build_multi_context combines multiple articles."""

    def test_build_multi_context_combines_articles(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        p1 = ops.write_raw_article(
            "multi-1.md",
            {"id": "multi-1", "title": "Article One", "source_type": "article"},
            "Content of article one.",
        )
        p2 = ops.write_raw_article(
            "multi-2.md",
            {"id": "multi-2", "title": "Article Two", "source_type": "article"},
            "Content of article two.",
        )

        result = builder.build_multi_context([p1, p2])
        assert "Article One" in result
        assert "Article Two" in result
        assert "Content of article one." in result
        assert "Content of article two." in result

    def test_build_multi_context_respects_token_limit(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        # Create two large articles.
        big_body = "x" * 10000  # 10k chars each
        p1 = ops.write_raw_article(
            "big-1.md",
            {"id": "big-1", "title": "Big Article One", "source_type": "article"},
            big_body,
        )
        p2 = ops.write_raw_article(
            "big-2.md",
            {"id": "big-2", "title": "Big Article Two", "source_type": "article"},
            big_body,
        )

        # Set a very small token limit so only part of the first fits.
        result = builder.build_multi_context([p1, p2], max_tokens=10)
        # Should be truncated — not contain the second article at all.
        assert "Big Article Two" not in result
        assert len(result) <= 10 * 4 + 200  # Roughly max_tokens*4 + overhead

    def test_build_multi_context_empty_list(self, tmp_vault):
        builder, _ = _setup_builder(tmp_vault)
        result = builder.build_multi_context([])
        assert result == ""


class TestFindRelatedRawArticles:
    """find_related_raw_articles finds articles by title overlap."""

    def test_find_related_by_title_overlap(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        # Write source article.
        source = ops.write_raw_article(
            "source.md",
            {
                "id": "source",
                "title": "Machine Learning Basics",
                "source_type": "article",
            },
            "Content about ML basics.",
        )
        # Write related article.
        related = ops.write_raw_article(
            "related.md",
            {
                "id": "related",
                "title": "Machine Learning Advanced",
                "source_type": "article",
            },
            "Content about advanced ML.",
        )
        # Write unrelated article.
        unrelated = ops.write_raw_article(
            "unrelated.md",
            {
                "id": "unrelated",
                "title": "Cooking Italian Pasta",
                "source_type": "article",
            },
            "Content about cooking.",
        )

        results = builder.find_related_raw_articles("source")
        result_ids = []
        for p in results:
            fm, _ = ops.read_article(p)
            result_ids.append(fm.get("id"))

        assert "related" in result_ids
        assert "unrelated" not in result_ids

    def test_find_related_returns_empty_for_no_match(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        source = ops.write_raw_article(
            "unique.md",
            {
                "id": "unique",
                "title": "Quantum Entanglement Physics",
                "source_type": "article",
            },
            "Content about quantum physics.",
        )
        other = ops.write_raw_article(
            "other.md",
            {
                "id": "other",
                "title": "Cooking Italian Pasta",
                "source_type": "article",
            },
            "Content about cooking.",
        )

        results = builder.find_related_raw_articles("unique")
        assert results == []


class TestBuildExistingContext:
    """build_existing_context gets compiled article content."""

    def test_build_existing_context_returns_body(self, tmp_vault):
        builder, ops = _setup_builder(tmp_vault)

        ops.write_compiled_article(
            "concepts",
            "test-concept.md",
            {
                "id": "test-concept",
                "title": "Test Concept",
                "type": "concept",
                "status": "draft",
            },
            "This is the compiled article body.",
        )

        result = builder.build_existing_context("test-concept")
        assert result is not None
        assert "This is the compiled article body." in result

    def test_build_existing_context_returns_none_for_missing(self, tmp_vault):
        builder, _ = _setup_builder(tmp_vault)

        result = builder.build_existing_context("nonexistent-article")
        assert result is None
