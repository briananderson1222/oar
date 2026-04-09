"""Tests for oar.search.server — FastAPI web search UI."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.search.indexer import SearchIndexer
from oar.search.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def indexed_vault(tmp_vault):
    """Create a vault with compiled articles and a search index."""
    ops = VaultOps(Vault(tmp_vault))

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

    return tmp_vault


@pytest.fixture
def client(indexed_vault):
    """Return a TestClient wired to the indexed vault."""
    app = create_app(str(indexed_vault))
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests — HTML search page
# ---------------------------------------------------------------------------


class TestSearchPage:
    """GET / — HTML search page."""

    def test_search_page_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "OAR Wiki Search" in resp.text

    def test_search_page_with_query(self, client):
        resp = client.get("/", params={"q": "attention"})
        assert resp.status_code == 200
        assert "Attention Mechanism" in resp.text

    def test_search_page_empty_query(self, client):
        resp = client.get("/", params={"q": ""})
        assert resp.status_code == 200
        # Empty query should render the page without a results section.
        # The template replaces {{RESULTS}} with "" for no query.
        assert "OAR Wiki Search" in resp.text


# ---------------------------------------------------------------------------
# Tests — JSON search API
# ---------------------------------------------------------------------------


class TestApiSearch:
    """GET /api/search — JSON search endpoint."""

    def test_api_search_returns_json(self, client):
        resp = client.get("/api/search", params={"q": "attention"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1

    def test_api_search_results_structure(self, client):
        resp = client.get("/api/search", params={"q": "attention"})
        data = resp.json()
        result = data["results"][0]
        for key in ("id", "title", "type", "score", "snippet", "tags"):
            assert key in result, f"Missing key: {key}"

    def test_api_search_limit(self, client):
        resp = client.get("/api/search", params={"q": "neural", "limit": 1})
        data = resp.json()
        assert len(data["results"]) <= 1

    def test_api_search_type_filter(self, client):
        resp = client.get("/api/search", params={"q": "neural", "type": "method"})
        data = resp.json()
        for r in data["results"]:
            assert r["type"] == "method"


# ---------------------------------------------------------------------------
# Tests — Article API
# ---------------------------------------------------------------------------


class TestApiArticle:
    """GET /api/article/{article_id} — single article endpoint."""

    def test_api_article_found(self, client):
        resp = client.get("/api/article/attention-mechanism")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "attention-mechanism"
        assert "frontmatter" in data
        assert "body" in data

    def test_api_article_not_found(self, client):
        resp = client.get("/api/article/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Stats API
# ---------------------------------------------------------------------------


class TestApiStats:
    """GET /api/stats — vault statistics endpoint."""

    def test_api_stats_returns_data(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert data["total_documents"] == 3
        assert "by_type" in data
