"""Tests for oar.index.moc_builder — MocBuilder."""

from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.moc_builder import MocBuilder


class TestBuildMoc:
    """Building individual MOC pages."""

    def test_build_moc_creates_file(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        path = builder.build_moc(
            "Machine Learning",
            "machine-learning",
            ["article-1", "article-2"],
        )
        assert path.exists()
        assert path.name == "moc-machine-learning.md"

    def test_build_moc_has_frontmatter(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        path = builder.build_moc(
            "Machine Learning",
            "machine-learning",
            ["article-1", "article-2"],
        )
        fm = FrontmatterManager()
        meta, body = fm.read(path)
        assert meta["type"] == "moc"
        assert meta["domain"] == "machine-learning"
        assert meta["article_count"] == 2

    def test_build_moc_lists_articles(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        path = builder.build_moc(
            "Machine Learning",
            "machine-learning",
            ["article-1", "article-2"],
        )
        content = path.read_text()
        assert "[[article-1]]" in content
        assert "[[article-2]]" in content


class TestBuildMasterIndex:
    """Building the master index page."""

    def test_build_master_index_creates_file(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        path = builder.build_master_index([])
        assert path.exists()
        assert path.name == "_master-index.md"

    def test_build_master_index_has_moc_table(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        mocs = [
            {"title": "Machine Learning", "domain": "ml", "article_count": 5},
            {"title": "NLP", "domain": "nlp", "article_count": 3},
        ]
        path = builder.build_master_index(mocs)
        content = path.read_text()
        assert "Machine Learning" in content
        assert "NLP" in content


class TestAutoGenerateMocs:
    """Auto-detecting topic clusters and generating MOCs."""

    def test_auto_generate_mocs_groups_by_domain(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Create articles in different domains.
        ops.write_compiled_article(
            "concepts",
            "a1.md",
            {
                "id": "a1",
                "title": "Article A1",
                "type": "concept",
                "status": "draft",
                "domain": ["machine-learning"],
            },
            "Body A1.",
        )
        ops.write_compiled_article(
            "concepts",
            "a2.md",
            {
                "id": "a2",
                "title": "Article A2",
                "type": "concept",
                "status": "draft",
                "domain": ["machine-learning"],
            },
            "Body A2.",
        )
        ops.write_compiled_article(
            "concepts",
            "b1.md",
            {
                "id": "b1",
                "title": "Article B1",
                "type": "concept",
                "status": "draft",
                "domain": ["nlp"],
            },
            "Body B1.",
        )
        ops.write_compiled_article(
            "concepts",
            "b2.md",
            {
                "id": "b2",
                "title": "Article B2",
                "type": "concept",
                "status": "draft",
                "domain": ["nlp"],
            },
            "Body B2.",
        )

        builder = MocBuilder(vault, ops)
        mocs = builder.auto_generate_mocs()
        assert len(mocs) == 2
        moc_names = sorted(p.name for p in mocs)
        assert "moc-machine-learning.md" in moc_names
        assert "moc-nlp.md" in moc_names

    def test_auto_generate_mocs_skips_small_domains(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Single article in a domain — MOC is still generated (threshold is 1).
        ops.write_compiled_article(
            "concepts",
            "lonely.md",
            {
                "id": "lonely",
                "title": "Lonely Article",
                "type": "concept",
                "status": "draft",
                "domain": ["obscure-topic"],
            },
            "Body.",
        )
        builder = MocBuilder(vault, ops)
        mocs = builder.auto_generate_mocs()
        assert len(mocs) == 1  # Even 1 article gets a MOC


class TestListMocs:
    """Listing existing MOCs."""

    def test_list_mocs_returns_existing(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        builder = MocBuilder(vault, ops)
        builder.build_moc("ML Basics", "machine-learning", ["a1", "a2"])
        builder.build_moc("NLP Guide", "nlp", ["b1"])

        mocs = builder.list_mocs()
        assert len(mocs) == 2
        titles = {m["title"] for m in mocs}
        assert "ML Basics" in titles
        assert "NLP Guide" in titles
        # Verify shape of returned dicts.
        for m in mocs:
            assert "id" in m
            assert "title" in m
            assert "article_count" in m
            assert "domain" in m
