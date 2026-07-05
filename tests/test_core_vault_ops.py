"""Tests for oar.core.vault_ops — VaultOps."""


from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


class TestListRawArticles:
    """Listing raw articles."""

    def test_list_raw_articles_empty(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        assert ops.list_raw_articles() == []

    def test_list_raw_articles_finds_files(self, tmp_vault):
        articles_dir = tmp_vault / "01-raw" / "articles"
        (articles_dir / "article-a.md").write_text("---\nid: a\n---\nBody A")
        (articles_dir / "article-b.md").write_text("---\nid: b\n---\nBody B")
        ops = VaultOps(Vault(tmp_vault))
        found = ops.list_raw_articles()
        names = sorted(p.name for p in found)
        assert names == ["article-a.md", "article-b.md"]

    def test_list_raw_articles_skips_index(self, tmp_vault):
        articles_dir = tmp_vault / "01-raw" / "articles"
        # _index.md should be excluded (already created by vault.init())
        (articles_dir / "article-a.md").write_text("---\nid: a\n---\nBody A")
        ops = VaultOps(Vault(tmp_vault))
        found = ops.list_raw_articles()
        names = [p.name for p in found]
        assert "_index.md" not in names
        assert "article-a.md" in names


class TestListCompiledArticles:
    """Listing compiled articles."""

    def test_list_compiled_articles_finds_recursively(self, tmp_vault):
        compiled = tmp_vault / "02-compiled"
        concepts = compiled / "concepts"
        entities = compiled / "entities"
        (concepts / "concept-1.md").write_text("---\nid: c1\n---\nBody")
        (entities / "entity-1.md").write_text("---\nid: e1\n---\nBody")
        ops = VaultOps(Vault(tmp_vault))
        found = ops.list_compiled_articles()
        names = sorted(p.name for p in found)
        assert "concept-1.md" in names
        assert "entity-1.md" in names

    def test_list_compiled_articles_with_subdir(self, tmp_vault):
        compiled = tmp_vault / "02-compiled"
        concepts = compiled / "concepts"
        entities = compiled / "entities"
        (concepts / "concept-1.md").write_text("---\nid: c1\n---\nBody")
        (entities / "entity-1.md").write_text("---\nid: e1\n---\nBody")
        ops = VaultOps(Vault(tmp_vault))
        found = ops.list_compiled_articles(subdir="concepts")
        names = [p.name for p in found]
        assert "concept-1.md" in names
        assert "entity-1.md" not in names

    def test_list_compiled_articles_skips_index(self, tmp_vault):
        compiled = tmp_vault / "02-compiled"
        concepts = compiled / "concepts"
        (concepts / "my-note.md").write_text("---\nid: n1\n---\nBody")
        ops = VaultOps(Vault(tmp_vault))
        found = ops.list_compiled_articles()
        names = [p.name for p in found]
        assert "_index.md" not in names
        assert "my-note.md" in names


class TestWriteArticles:
    """Writing raw and compiled articles."""

    def test_write_raw_article_creates_file(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        path = ops.write_raw_article(
            "test.md",
            {"id": "w1", "title": "Written Raw"},
            "Raw body text.",
        )
        assert path.exists()
        meta, body = ops.fm.read(path)
        assert meta["id"] == "w1"
        assert "Raw body text." in body

    def test_write_compiled_article_creates_in_subdir(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        path = ops.write_compiled_article(
            "concepts",
            "test-concept.md",
            {"id": "c1", "title": "Written Concept", "type": "concept"},
            "Concept body.",
        )
        assert path.exists()
        assert "concepts" in str(path)
        meta, body = ops.fm.read(path)
        assert meta["id"] == "c1"
        assert "Concept body." in body


class TestReadArticle:
    """Reading articles."""

    def test_read_article_roundtrip(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        original_meta = {"id": "rt1", "title": "Roundtrip", "source_type": "article"}
        original_body = "Roundtrip body content."
        path = ops.write_raw_article("roundtrip.md", original_meta, original_body)
        meta, body = ops.read_article(path)
        assert meta["id"] == "rt1"
        assert meta["title"] == "Roundtrip"
        assert "Roundtrip body content." in body


class TestGetArticleById:
    """Finding articles by id in frontmatter."""

    def test_get_article_by_id_found(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "findme.md",
            {"id": "target-id", "title": "Find Me"},
            "Body.",
        )
        result = ops.get_article_by_id("target-id")
        assert result is not None
        assert result.name == "findme.md"

    def test_get_article_by_id_not_found(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "other.md",
            {"id": "other-id", "title": "Other"},
            "Body.",
        )
        assert ops.get_article_by_id("nonexistent") is None

    def test_get_article_by_id_slug_fallback(self, tmp_vault):
        """Match by slugified title when no id field exists."""
        ops = VaultOps(Vault(tmp_vault))
        # Write article with title but no id.
        path = tmp_vault / "02-compiled" / "concepts" / "some-article.md"
        path.write_text("---\ntitle: Some Article\n---\nBody.\n")
        # Should find it by slugified title.
        result = ops.get_article_by_id("some-article")
        assert result is not None
        assert result == path

    def test_get_article_by_id_slug_with_special_chars(self, tmp_vault):
        """Match files with spaces/parens in name via slugified title."""
        ops = VaultOps(Vault(tmp_vault))
        path = tmp_vault / "02-compiled" / "concepts" / "acp.md"
        path.write_text("---\ntitle: Agent Client Protocol (ACP) - CLI\n---\nBody.\n")
        result = ops.get_article_by_id("agent-client-protocol-acp-cli")
        assert result is not None


class TestComputeHelpers:
    """Word count and read time calculations."""

    def test_compute_word_count(self):
        ops = VaultOps.__new__(VaultOps)
        assert ops.compute_word_count("hello world foo") == 3

    def test_compute_read_time(self):
        ops = VaultOps.__new__(VaultOps)
        assert ops.compute_read_time(400) == 2

    def test_compute_read_time_minimum(self):
        ops = VaultOps.__new__(VaultOps)
        assert ops.compute_read_time(0) == 1


class TestGetArticleById:
    """get_article_by_id — O(1) state fast path with scan fallback."""

    def test_fast_path_from_state(self, tmp_vault):
        from oar.core.state import StateManager

        ops = VaultOps(Vault(tmp_vault))
        path = ops.write_compiled_article(
            "concepts",
            "alpha.md",
            {"id": "alpha", "title": "Alpha", "type": "concept", "status": "draft"},
            "Body.",
        )
        rel = str(path.relative_to(tmp_vault))
        StateManager((tmp_vault / ".oar")).register_article("alpha", rel, "hash")

        found = ops.get_article_by_id("alpha")
        assert found == path

    def test_stale_state_falls_back_to_scan(self, tmp_vault):
        from oar.core.state import StateManager

        ops = VaultOps(Vault(tmp_vault))
        # Register a path that does not exist on disk.
        StateManager((tmp_vault / ".oar")).register_article(
            "beta", "02-compiled/concepts/GONE.md", "hash"
        )
        # But the real file exists elsewhere with the matching id.
        real = ops.write_compiled_article(
            "concepts",
            "beta-real.md",
            {"id": "beta", "title": "Beta", "type": "concept", "status": "draft"},
            "Body.",
        )
        found = ops.get_article_by_id("beta")
        assert found == real

    def test_unregistered_article_found_by_scan(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        # Written directly, never registered in state.
        path = ops.write_compiled_article(
            "concepts",
            "gamma.md",
            {"id": "gamma", "title": "Gamma", "type": "concept", "status": "draft"},
            "Body.",
        )
        assert ops.get_article_by_id("gamma") == path

    def test_missing_article_returns_none(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        assert ops.get_article_by_id("nope") is None
