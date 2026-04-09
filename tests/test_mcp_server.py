"""Tests for OAR MCP server — tool definitions and handlers."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.mcp_tools import (
    TOOL_DEFINITIONS,
    tool_get_status,
    tool_list_articles,
    tool_list_mocs,
    tool_read_article,
    tool_search_wiki,
)


def _setup_vault_with_articles(tmp_vault):
    """Create a vault with compiled articles for testing."""
    ops = VaultOps(Vault(tmp_vault))

    ops.write_compiled_article(
        "concepts",
        "attention.md",
        {
            "id": "attention",
            "title": "Attention Mechanism",
            "type": "concept",
            "tags": ["attention", "neural-network"],
            "status": "draft",
            "related": [],
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks.",
    )

    ops.write_compiled_article(
        "concepts",
        "transformer.md",
        {
            "id": "transformer",
            "title": "Transformer Architecture",
            "type": "concept",
            "tags": ["transformer", "neural-network"],
            "status": "draft",
            "related": ["attention"],
            "word_count": 50,
        },
        "The Transformer uses [[attention]] mechanisms for processing sequences.",
    )

    return ops


class TestMCPToolDefinitions:
    """Verify tool definitions are properly configured."""

    def test_all_tools_have_required_fields(self):
        """Every tool has name, description, parameters, and handler."""
        for name, defn in TOOL_DEFINITIONS.items():
            assert "description" in defn, f"{name} missing description"
            assert "parameters" in defn, f"{name} missing parameters"
            assert "handler" in defn, f"{name} missing handler"
            assert callable(defn["handler"]), f"{name} handler not callable"

    def test_tool_schemas_valid(self):
        """All tool parameter schemas have type='object'."""
        for name, defn in TOOL_DEFINITIONS.items():
            schema = defn["parameters"]
            assert schema["type"] == "object", f"{name} schema type is not 'object'"
            assert "properties" in schema, f"{name} missing properties"

    def test_expected_tools_registered(self):
        """All 6 expected tools are registered."""
        expected = {
            "search_wiki",
            "read_article",
            "query_wiki",
            "get_status",
            "list_mocs",
            "list_articles",
        }
        assert set(TOOL_DEFINITIONS.keys()) == expected


class TestToolGetStatus:
    """get_status tool tests."""

    def test_get_status_returns_vault_info(self, tmp_vault, monkeypatch):
        """get_status returns vault statistics."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = tool_get_status()
        assert "vault_path" in result
        assert "raw_articles" in result
        assert "compiled_articles" in result
        assert result["vault_path"] == str(tmp_vault)


class TestToolReadArticle:
    """read_article tool tests."""

    def test_read_article_existing(self, tmp_vault, monkeypatch):
        """Reading an existing article returns metadata and body."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_read_article("attention")
        assert result["id"] == "attention"
        assert "Attention" in result["body"]
        assert "metadata" in result

    def test_read_article_not_found(self, tmp_vault, monkeypatch):
        """Reading a non-existent article returns error."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = tool_read_article("nonexistent")
        assert "error" in result


class TestToolListArticles:
    """list_articles tool tests."""

    def test_list_articles_returns_all(self, tmp_vault, monkeypatch):
        """list_articles returns all compiled articles."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_list_articles()
        assert len(result) >= 2
        ids = [a["id"] for a in result]
        assert "attention" in ids
        assert "transformer" in ids

    def test_list_articles_filter_by_category(self, tmp_vault, monkeypatch):
        """list_articles filters by category/type."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_list_articles(category="concept")
        assert all(a["type"] == "concept" for a in result)

    def test_list_articles_filter_by_tags(self, tmp_vault, monkeypatch):
        """list_articles filters by tags."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_list_articles(tags=["attention"])
        assert len(result) >= 1
        assert result[0]["id"] == "attention"


class TestToolSearchWiki:
    """search_wiki tool tests."""

    def test_search_wiki_returns_results(self, tmp_vault, monkeypatch):
        """search_wiki returns matching articles."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        # Build search index first.
        from oar.search.indexer import SearchIndexer

        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        db_path = tmp_vault / ".oar" / "search-index" / "search.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        indexer = SearchIndexer(db_path)
        indexer.index_vault(vault, ops)
        indexer.close()

        results = tool_search_wiki("attention")
        assert isinstance(results, list)


class TestToolListMocs:
    """list_mocs tool tests."""

    def test_list_mocs_returns_list(self, tmp_vault, monkeypatch):
        """list_mocs returns a list (may be empty for new vault)."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_list_mocs()
        assert isinstance(result, list)


class TestMCPServerCreation:
    """Test that the MCP server can be created."""

    def test_create_server_no_error(self):
        """Server creates without error."""
        try:
            from oar.mcp_server import create_server

            server = create_server()
            assert server is not None
        except ImportError:
            pytest.skip("mcp package not installed")

    def test_server_has_tool_handlers(self):
        """Server has list_tools and call_tool handlers."""
        try:
            from oar.mcp_server import create_server

            server = create_server()
            assert hasattr(server, "list_tools")
            assert hasattr(server, "call_tool")
        except ImportError:
            pytest.skip("mcp package not installed")
