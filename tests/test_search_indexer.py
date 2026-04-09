"""Tests for oar.search.indexer — SearchIndexer."""

from pathlib import Path

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.search.indexer import SearchDocument, SearchIndexer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Return a path for the search database."""
    path = tmp_path / "search.db"
    return path


@pytest.fixture
def indexer(db_path):
    """Create a SearchIndexer connected to a temp database."""
    idx = SearchIndexer(db_path)
    yield idx
    idx.close()


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
    count = indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()

    return tmp_vault, db_path, count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitSchema:
    """Schema initialization."""

    def test_init_schema_creates_tables(self, db_path):
        indexer = SearchIndexer(db_path)
        # Check that vault_docs table exists.
        row = indexer.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_docs'"
        ).fetchone()
        assert row is not None

        # Check that FTS virtual table exists.
        row = indexer.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_fts'"
        ).fetchone()
        assert row is not None

        # Check that article_tags table exists.
        row = indexer.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='article_tags'"
        ).fetchone()
        assert row is not None

        indexer.close()


class TestIndexArticle:
    """Single article indexing."""

    def test_index_article_adds_to_fts(self, indexer):
        doc = SearchDocument(
            article_id="test-article",
            title="Test Article",
            path="concepts/test.md",
            type="concept",
            body="This is a test article about machine learning.",
            tags="machine learning",
        )
        indexer.index_article(doc)

        # Verify it's searchable.
        row = indexer.conn.execute(
            "SELECT * FROM vault_fts WHERE vault_fts MATCH ?",
            ("machine learning",),
        ).fetchone()
        assert row is not None
        assert row["article_id"] == "test-article"

    def test_index_article_upserts(self, indexer):
        doc = SearchDocument(
            article_id="test-article",
            title="Original Title",
            path="concepts/test.md",
            type="concept",
            body="Original body content.",
        )
        indexer.index_article(doc)

        # Now update with new content.
        updated_doc = SearchDocument(
            article_id="test-article",
            title="Updated Title",
            path="concepts/test.md",
            type="concept",
            body="Updated body content about neural networks.",
        )
        indexer.index_article(updated_doc)

        # Should have only one entry.
        rows = indexer.conn.execute(
            "SELECT * FROM vault_docs WHERE article_id = ?",
            ("test-article",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["title"] == "Updated Title"

        # FTS should also have only one entry.
        fts_rows = indexer.conn.execute(
            "SELECT * FROM vault_fts WHERE article_id = ?",
            ("test-article",),
        ).fetchall()
        assert len(fts_rows) == 1

    def test_index_article_stores_metadata(self, indexer):
        doc = SearchDocument(
            article_id="meta-test",
            title="Metadata Test",
            path="methods/test.md",
            type="method",
            body="Body text.",
            tags="ml ai",
            aliases="machine-intelligence",
        )
        metadata = {
            "status": "draft",
            "word_count": 2,
            "backlink_count": 5,
            "created": "2024-01-01",
            "updated": "2024-06-01",
        }
        indexer.index_article(doc, metadata=metadata)

        row = indexer.conn.execute(
            "SELECT * FROM vault_docs WHERE article_id = ?",
            ("meta-test",),
        ).fetchone()
        assert row["status"] == "draft"
        assert row["word_count"] == 2
        assert row["backlink_count"] == 5
        assert row["created"] == "2024-01-01"
        assert row["updated"] == "2024-06-01"

        # Tags stored.
        tag_rows = indexer.conn.execute(
            "SELECT tag FROM article_tags WHERE article_id = ? ORDER BY tag",
            ("meta-test",),
        ).fetchall()
        tags = [r["tag"] for r in tag_rows]
        assert "ai" in tags
        assert "ml" in tags


class TestIndexVault:
    """Full vault indexing."""

    def test_index_vault_scans_all(self, indexed_vault):
        tmp_vault, db_path, count = indexed_vault
        # Should have indexed all 3 articles.
        indexer = SearchIndexer(db_path)
        rows = indexer.conn.execute("SELECT * FROM vault_docs").fetchall()
        assert len(rows) == 3
        indexer.close()

    def test_index_vault_returns_count(self, indexed_vault):
        tmp_vault, db_path, count = indexed_vault
        assert count == 3


class TestRemoveArticle:
    """Removing articles from the index."""

    def test_remove_article_deletes_from_fts(self, indexed_vault):
        tmp_vault, db_path, count = indexed_vault
        indexer = SearchIndexer(db_path)

        # Verify article exists first.
        row = indexer.conn.execute(
            "SELECT * FROM vault_docs WHERE article_id = ?",
            ("fine-tuning",),
        ).fetchone()
        assert row is not None

        indexer.remove_article("fine-tuning")

        # Should no longer exist.
        row = indexer.conn.execute(
            "SELECT * FROM vault_docs WHERE article_id = ?",
            ("fine-tuning",),
        ).fetchone()
        assert row is None

        # FTS should also be clean.
        fts_row = indexer.conn.execute(
            "SELECT * FROM vault_fts WHERE article_id = ?",
            ("fine-tuning",),
        ).fetchone()
        assert fts_row is None

        # Tags should be clean.
        tag_rows = indexer.conn.execute(
            "SELECT * FROM article_tags WHERE article_id = ?",
            ("fine-tuning",),
        ).fetchall()
        assert len(tag_rows) == 0

        indexer.close()
