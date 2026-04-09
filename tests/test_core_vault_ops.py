"""Tests for oar.core.vault_ops — VaultOps."""

from pathlib import Path

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
