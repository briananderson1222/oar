"""Tests for OAR MCP server — tool definitions and handlers."""

from pathlib import Path

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.mcp_tools import (
    TOOL_DEFINITIONS,
    tool_build_indices,
    tool_get_pending_articles,
    tool_get_status,
    tool_list_articles,
    tool_list_mocs,
    tool_mark_raw_compiled,
    tool_read_article,
    tool_read_raw_article,
    tool_save_compiled_article,
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
        """All 11 expected tools are registered."""
        expected = {
            "search_wiki",
            "read_article",
            "query_wiki",
            "get_status",
            "list_mocs",
            "list_articles",
            "get_pending_articles",
            "read_raw_article",
            "save_compiled_article",
            "mark_raw_compiled",
            "build_indices",
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


class TestToolGetPendingArticles:
    """get_pending_articles tool tests."""

    def test_empty_vault_returns_empty(self, tmp_vault, monkeypatch):
        """No raw articles means empty list."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = tool_get_pending_articles()
        assert result == []

    def test_new_raw_article(self, tmp_vault, monkeypatch):
        """Raw article not in state is NEW."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write a raw article without registering it in state.
        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "new-article.md",
            {"title": "New Article"},
            "This is a new article about something.",
        )

        result = tool_get_pending_articles()
        assert len(result) == 1
        assert result[0]["status"] == "NEW"
        assert result[0]["title"] == "New Article"

    def test_uncompiled_raw_article(self, tmp_vault, monkeypatch, sample_state):
        """Raw article in state but not compiled is UNCOMPILED."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write the raw article that sample_state references.
        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "2024-01-15-test-article.md",
            {
                "id": "2024-01-15-test-article",
                "title": "Test Article About Transformers",
            },
            "This is a test article about transformer architectures.",
        )

        result = tool_get_pending_articles()
        assert len(result) == 1
        assert result[0]["status"] == "UNCOMPILED"

    def test_compiled_unchanged_article_skipped(
        self, tmp_vault, monkeypatch, sample_raw_article
    ):
        """Compiled article with same hash is skipped."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register and mark as compiled in state.
        from oar.core.hashing import content_hash
        from oar.core.state import StateManager

        vault = Vault(tmp_vault)
        state_mgr = StateManager(vault.oar_dir)
        state = state_mgr.load()
        state["articles"]["2024-01-15-test-article"] = {
            "path": "01-raw/articles/2024-01-15-test-article.md",
            "content_hash": content_hash(sample_raw_article),
            "compiled": True,
            "compiled_into": ["transformer-architecture"],
            "last_compiled": "2024-01-15T10:30:00Z",
        }
        state_mgr.save(state)

        result = tool_get_pending_articles()
        assert result == []

    def test_updated_raw_article(self, tmp_vault, monkeypatch):
        """Article with changed hash shows as UPDATED."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        from oar.core.state import StateManager

        state_mgr = StateManager(tmp_vault / ".oar")
        # Register with old hash.
        state_mgr.register_article(
            "updated-test", "01-raw/articles/updated-test.md", "sha256:oldhash"
        )
        state_mgr.mark_compiled("updated-test", ["updated-test"])
        # Write new content (different hash).
        raw_path = tmp_vault / "01-raw" / "articles" / "updated-test.md"
        raw_path.write_text(
            "---\nid: updated-test\ntitle: Updated Test\n---\nNew content.\n"
        )

        pending = tool_get_pending_articles()
        assert len(pending) == 1
        assert pending[0]["status"] == "UPDATED"
        assert pending[0]["article_id"] == "updated-test"


class TestToolReadRawArticle:
    """read_raw_article tool tests."""

    def test_read_existing_raw_article(self, tmp_vault, monkeypatch):
        """Reading an existing raw article returns metadata and body."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "my-article.md",
            {
                "id": "my-article",
                "title": "My Article",
                "source_url": "https://example.com",
            },
            "Body content of the article.",
        )

        result = tool_read_raw_article("my-article")
        assert result["article_id"] == "my-article"
        assert result["title"] == "My Article"
        assert "Body content" in result["body"]
        assert "metadata" in result

    def test_read_raw_article_by_slug(self, tmp_vault, monkeypatch):
        """Reading by slugified title works."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "article.md",
            {"title": "Cool Article"},
            "Content here.",
        )

        result = tool_read_raw_article("cool-article")
        assert result["article_id"] == "cool-article"
        assert "Content here" in result["body"]

    def test_read_raw_article_not_found(self, tmp_vault, monkeypatch):
        """Reading non-existent article returns error."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = tool_read_raw_article("nonexistent")
        assert "error" in result


class TestToolSaveCompiledArticle:
    """save_compiled_article tool tests."""

    def test_save_basic_article(self, tmp_vault, monkeypatch):
        """Saving a basic article creates the file and returns metadata."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        result = tool_save_compiled_article(
            title="Attention Mechanism",
            body="Attention is a mechanism in neural networks.",
            article_type="concept",
            tags=["attention", "neural-network"],
        )

        assert result["article_id"] == "attention-mechanism"
        assert result["title"] == "Attention Mechanism"
        assert result["word_count"] > 0
        assert "path" in result

        # Verify file was written.
        path = Path(result["path"])
        assert path.exists()

    def test_save_with_source_ids_marks_compiled(
        self, tmp_vault, monkeypatch, sample_state
    ):
        """Providing source_ids marks raw articles as compiled in state."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        from oar.core.state import StateManager

        result = tool_save_compiled_article(
            title="Test Compiled",
            body="Compiled content.",
            source_ids=["2024-01-15-test-article"],
        )

        # Verify source was marked as compiled.
        vault = Vault(tmp_vault)
        state_mgr = StateManager(vault.oar_dir)
        state = state_mgr.load()
        raw_entry = state["articles"]["2024-01-15-test-article"]
        assert raw_entry["compiled"] is True
        assert result["article_id"] in raw_entry["compiled_into"]

    def test_save_with_related_and_tags(self, tmp_vault, monkeypatch):
        """Related IDs are wrapped in wikilinks, tags stored as-is."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        result = tool_save_compiled_article(
            title="Related Test",
            body="Body content.",
            tags=["ml", "ai"],
            related=["some-article", "another-article"],
        )

        # Verify frontmatter by reading the file.
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        meta, body = ops.read_article(Path(result["path"]))
        assert "[[some-article]]" in meta["related"]
        assert "[[another-article]]" in meta["related"]
        assert "ml" in meta["tags"]
        assert "ai" in meta["tags"]

    def test_save_derives_domain_from_tags(self, tmp_vault, monkeypatch):
        """Domain is derived from first 2 tags when not explicitly provided."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        from oar.core.frontmatter import FrontmatterManager

        result = tool_save_compiled_article(
            title="Domain Test",
            body="Testing domain derivation.",
            tags=["machine-learning", "nlp", "transformers"],
        )
        assert result["article_id"] == "domain-test"
        # Read back and verify domain was set.
        fm = FrontmatterManager()
        path = tmp_vault / "02-compiled" / "concepts" / "domain-test.md"
        meta, _ = fm.read(path)
        assert meta["domain"] == ["machine-learning", "nlp"]

    def test_save_uses_explicit_domain(self, tmp_vault, monkeypatch):
        """Explicit domain overrides tag derivation."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        from oar.core.frontmatter import FrontmatterManager

        tool_save_compiled_article(
            title="Explicit Domain Test",
            body="Testing explicit domain.",
            tags=["tag1", "tag2"],
            domain=["custom-domain", "another"],
        )
        fm = FrontmatterManager()
        path = tmp_vault / "02-compiled" / "concepts" / "explicit-domain-test.md"
        meta, _ = fm.read(path)
        assert meta["domain"] == ["custom-domain", "another"]


class TestToolMarkRawCompiled:
    """mark_raw_compiled tool tests."""

    def test_mark_existing_raw(self, tmp_vault, monkeypatch, sample_state):
        """Marking an existing raw article updates state."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        result = tool_mark_raw_compiled(
            raw_article_id="2024-01-15-test-article",
            compiled_article_id="my-compiled-note",
        )

        assert result["status"] == "ok"
        assert result["raw_id"] == "2024-01-15-test-article"
        assert result["compiled_id"] == "my-compiled-note"

        # Verify state was updated.
        from oar.core.state import StateManager

        vault = Vault(tmp_vault)
        state_mgr = StateManager(vault.oar_dir)
        state = state_mgr.load()
        entry = state["articles"]["2024-01-15-test-article"]
        assert entry["compiled"] is True
        assert "my-compiled-note" in entry["compiled_into"]


class TestToolBuildIndices:
    """build_indices tool tests."""

    def test_build_indices_returns_counts(self, tmp_vault, monkeypatch):
        """build_indices returns count of generated indices."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_build_indices()
        assert "mocs" in result
        assert "tags" in result
        assert "orphans" in result
        assert "stubs" in result
        assert isinstance(result["mocs"], int)
        assert isinstance(result["tags"], int)

    def test_build_indices_creates_tag_pages(self, tmp_vault, monkeypatch):
        """build_indices creates tag pages for article tags."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_vault_with_articles(tmp_vault)

        result = tool_build_indices()
        assert result["tags"] >= 1

        # Verify tag page files exist.
        tags_dir = tmp_vault / "03-indices" / "tags"
        tag_files = list(tags_dir.glob("tag-*.md"))
        assert len(tag_files) >= 1

    def test_build_indices_creates_mocs(self, tmp_vault, monkeypatch):
        """build_indices generates MOCs when articles have domains."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        # Save an article with domain.
        tool_save_compiled_article(
            title="MOC Test Article",
            body="Testing MOC generation.",
            tags=["test"],
            domain=["test-domain"],
        )
        result = tool_build_indices()
        assert result["mocs"] >= 1
        # Verify MOC file exists.
        moc_dir = tmp_vault / "03-indices" / "moc"
        moc_files = [
            f
            for f in moc_dir.iterdir()
            if f.name.startswith("moc-") and f.name != "_index.md"
        ]
        assert len(moc_files) >= 1


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
