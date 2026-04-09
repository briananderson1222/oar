"""Tests for oar.search.searcher — Searcher."""

from pathlib import Path

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.search.indexer import SearchDocument, SearchIndexer
from oar.search.searcher import Searcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def indexed_vault(tmp_vault):
    """Create a vault with compiled articles and a search index."""
    ops = VaultOps(Vault(tmp_vault))

    # Create some compiled articles.
    ops.write_compiled_article(
        "concepts",
        "attention-mechanism.md",
        {
            "id": "attention-mechanism",
            "title": "Attention Mechanism",
            "type": "concept",
            "tags": ["attention", "neural-network"],
            "status": "draft",
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks that allows models to "
        "focus on relevant parts of the input. Self-attention computes "
        "weighted representations.",
    )
    ops.write_compiled_article(
        "concepts",
        "transformer-architecture.md",
        {
            "id": "transformer-architecture",
            "title": "Transformer Architecture",
            "type": "concept",
            "tags": ["transformer", "architecture"],
            "status": "mature",
            "word_count": 40,
        },
        "The Transformer is a neural network architecture based entirely on "
        "attention mechanisms. It uses multi-head self-attention and "
        "feed-forward layers.",
    )
    ops.write_compiled_article(
        "methods",
        "fine-tuning.md",
        {
            "id": "fine-tuning",
            "title": "Fine-Tuning",
            "type": "method",
            "tags": ["training", "fine-tuning"],
            "status": "draft",
            "word_count": 25,
        },
        "Fine-tuning is the process of adapting a pre-trained model to a "
        "specific task by training it further on task-specific data.",
    )

    # Build search index.
    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()

    return tmp_vault, db_path


@pytest.fixture
def searcher(indexed_vault):
    """Return a Searcher connected to the indexed vault."""
    _, db_path = indexed_vault
    s = Searcher(db_path)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearch:
    """Full-text search."""

    def test_search_finds_matching_article(self, searcher):
        results = searcher.search("attention mechanism")
        assert len(results) >= 1
        ids = [r.article_id for r in results]
        assert "attention-mechanism" in ids

    def test_search_returns_empty_for_no_match(self, searcher):
        results = searcher.search("xyzzyplughnothingatall")
        assert results == []

    def test_search_limits_results(self, searcher):
        results = searcher.search("neural network", limit=2)
        assert len(results) <= 2

    def test_search_type_filter(self, searcher):
        results = searcher.search("neural", type_filter="method")
        # "fine-tuning" is type method but its body doesn't mention "neural".
        # "attention-mechanism" and "transformer-architecture" are type "concept".
        for r in results:
            assert r.type == "method"

    def test_search_result_has_snippet(self, searcher):
        results = searcher.search("attention")
        assert len(results) >= 1
        for r in results:
            assert len(r.snippet) > 0

    def test_search_result_has_score(self, searcher):
        results = searcher.search("attention")
        assert len(results) >= 1
        for r in results:
            assert r.score > 0

    def test_search_multiple_terms(self, searcher):
        """AND search — both terms must match for top results."""
        results = searcher.search("attention mechanism")
        assert len(results) >= 1
        # The attention-mechanism article should be the top result.
        assert results[0].article_id == "attention-mechanism"

    def test_search_hyphenated_query(self, searcher):
        """Hyphenated terms become FTS5 phrase queries."""
        # "fine-tuning" becomes "fine tuning" phrase — matches the article.
        results = searcher.search("fine-tuning")
        assert len(results) >= 1
        ids = [r.article_id for r in results]
        assert "fine-tuning" in ids

    def test_search_hyphenated_phrase_match(self, searcher):
        """Hyphenated query matches as phrase, not loose AND terms."""
        # "self-attention" becomes phrase "self attention".
        # Both attention and transformer articles mention it.
        results = searcher.search("self-attention")
        assert len(results) >= 1
        ids = [r.article_id for r in results]
        assert "attention-mechanism" in ids

    def test_search_hyphenated_multiword(self, searcher):
        """Multiple hyphenated terms work correctly."""
        results = searcher.search("self-attention mechanism")
        assert len(results) >= 1


class TestGetArticle:
    """Retrieving individual articles."""

    def test_get_article_found(self, searcher):
        article = searcher.get_article("attention-mechanism")
        assert article is not None
        assert article["article_id"] == "attention-mechanism"
        assert article["title"] == "Attention Mechanism"
        assert article["type"] == "concept"

    def test_get_article_not_found(self, searcher):
        article = searcher.get_article("does-not-exist")
        assert article is None


class TestGetStats:
    """Search index statistics."""

    def test_get_stats_returns_counts(self, searcher):
        stats = searcher.get_stats()
        assert stats["total_documents"] == 3
        assert "by_type" in stats
        assert stats["by_type"]["concept"] == 2
        assert stats["by_type"]["method"] == 1
