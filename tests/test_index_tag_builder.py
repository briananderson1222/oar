"""Tests for oar.index.tag_builder — TagBuilder."""

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.tag_builder import TagBuilder


class TestBuildTagPage:
    """Building individual tag pages."""

    def test_build_tag_page_creates_file(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = TagBuilder(vault, ops)
        path = builder.build_tag_page("python", ["article-1", "article-2"])
        assert path.exists()
        assert path.name == "tag-python.md"

    def test_build_tag_page_lists_articles(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = TagBuilder(vault, ops)
        path = builder.build_tag_page("python", ["my-article", "other-article"])
        content = path.read_text()
        assert "[[my-article]]" in content
        assert "[[other-article]]" in content


class TestAutoGenerateTags:
    """Auto-generating tag pages from compiled articles."""

    def test_auto_generate_tags_creates_pages(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "a.md",
            {
                "id": "a",
                "title": "A",
                "type": "concept",
                "status": "draft",
                "tags": ["python", "testing"],
            },
            "Body A.",
        )
        ops.write_compiled_article(
            "concepts",
            "b.md",
            {
                "id": "b",
                "title": "B",
                "type": "concept",
                "status": "draft",
                "tags": ["python", "web"],
            },
            "Body B.",
        )

        builder = TagBuilder(vault, ops)
        created = builder.auto_generate_tags()
        assert len(created) == 3  # python, testing, web
        tag_dir = vault.indices_dir / "tags"
        tag_files = sorted(
            p.name
            for p in tag_dir.iterdir()
            if p.suffix == ".md" and p.name != "_index.md"
        )
        assert "tag-python.md" in tag_files
        assert "tag-testing.md" in tag_files
        assert "tag-web.md" in tag_files


class TestListTags:
    """Listing tags with article counts."""

    def test_list_tags_returns_counts(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "a.md",
            {
                "id": "a",
                "title": "A",
                "type": "concept",
                "status": "draft",
                "tags": ["python", "testing"],
            },
            "Body A.",
        )
        ops.write_compiled_article(
            "concepts",
            "b.md",
            {
                "id": "b",
                "title": "B",
                "type": "concept",
                "status": "draft",
                "tags": ["python"],
            },
            "Body B.",
        )

        builder = TagBuilder(vault, ops)
        tags = builder.list_tags()
        assert "python" in tags
        assert len(tags["python"]) == 2
        assert "testing" in tags
        assert len(tags["testing"]) == 1
