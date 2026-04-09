"""Tests for oar.core.link_resolver — LinkResolver."""

import pytest

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.core.link_resolver import LinkResolver
from oar.core.link_graph import LinkGraph


class TestExtractWikilinks:
    """Wikilink extraction from text."""

    def test_extract_wikilinks_basic(self):
        resolver = LinkResolver.__new__(LinkResolver)
        text = "See [[attention]] and [[transformer]] for details."
        result = resolver.extract_wikilinks(text)
        assert result == ["attention", "transformer"]

    def test_extract_wikilinks_with_display(self):
        resolver = LinkResolver.__new__(LinkResolver)
        text = "The [[transformer|Transformer Arch]] changed NLP."
        result = resolver.extract_wikilinks(text)
        assert result == ["transformer"]

    def test_extract_wikilinks_no_links(self):
        resolver = LinkResolver.__new__(LinkResolver)
        text = "This is plain text with no links at all."
        assert resolver.extract_wikilinks(text) == []

    def test_extract_wikilinks_deduplicates(self):
        resolver = LinkResolver.__new__(LinkResolver)
        text = "[[foo]] is related to [[foo]]."
        assert resolver.extract_wikilinks(text) == ["foo"]

    def test_extract_wikilinks_normalizes_case(self):
        resolver = LinkResolver.__new__(LinkResolver)
        text = "[[Transformer Architecture]] is important."
        result = resolver.extract_wikilinks(text)
        assert result == ["transformer-architecture"]


class TestBuildGraph:
    """Building the full link graph from vault articles."""

    def test_build_graph_empty_vault(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        assert isinstance(graph, LinkGraph)
        assert graph.get_all_nodes() == set()

    def test_build_graph_scans_compiled_articles(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "attention.md",
            {
                "id": "attention",
                "title": "Attention",
                "type": "concept",
                "status": "draft",
            },
            "# Attention\n\nSelf-attention mechanism.",
        )
        ops.write_compiled_article(
            "concepts",
            "transformer.md",
            {
                "id": "transformer",
                "title": "Transformer",
                "type": "concept",
                "status": "draft",
            },
            "# Transformer\n\nSee [[attention]].",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        nodes = graph.get_all_nodes()
        assert "attention" in nodes
        assert "transformer" in nodes

    def test_build_graph_has_correct_edges(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "article-a.md",
            {
                "id": "article-a",
                "title": "Article A",
                "type": "concept",
                "status": "draft",
            },
            "# A\n\nSee [[article-b]] for more.",
        )
        ops.write_compiled_article(
            "concepts",
            "article-b.md",
            {
                "id": "article-b",
                "title": "Article B",
                "type": "concept",
                "status": "draft",
            },
            "# B\n\nRelated: [[article-a]].",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        assert "article-a" in graph.get_forward_links("article-b")
        assert "article-b" in graph.get_forward_links("article-a")

    def test_build_graph_includes_frontmatter_links(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "main-topic.md",
            {
                "id": "main-topic",
                "title": "Main Topic",
                "type": "concept",
                "status": "draft",
                "related": ["[[related-topic]]"],
            },
            "# Main Topic\n\nNo body links.",
        )
        ops.write_compiled_article(
            "concepts",
            "related-topic.md",
            {
                "id": "related-topic",
                "title": "Related Topic",
                "type": "concept",
                "status": "draft",
            },
            "# Related Topic",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        assert "related-topic" in graph.get_forward_links("main-topic")


class TestFindOrphans:
    """Detecting orphan articles."""

    def test_find_orphans_identifies_isolated(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        # Well-connected article
        ops.write_compiled_article(
            "concepts",
            "hub.md",
            {"id": "hub", "title": "Hub", "type": "concept", "status": "draft"},
            "# Hub\n\nSee [[connected-a]] and [[connected-b]].",
        )
        ops.write_compiled_article(
            "concepts",
            "connected-a.md",
            {
                "id": "connected-a",
                "title": "Connected A",
                "type": "concept",
                "status": "draft",
            },
            "# A\n\nSee [[hub]] and [[connected-b]].",
        )
        ops.write_compiled_article(
            "concepts",
            "connected-b.md",
            {
                "id": "connected-b",
                "title": "Connected B",
                "type": "concept",
                "status": "draft",
            },
            "# B\n\nSee [[hub]] and [[connected-a]].",
        )
        # Isolated article — no one links to it
        ops.write_compiled_article(
            "concepts",
            "isolated.md",
            {
                "id": "isolated",
                "title": "Isolated",
                "type": "concept",
                "status": "draft",
            },
            "# Isolated\n\nNo outgoing links.",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        orphans = resolver.find_orphans(graph, min_backlinks=2)
        assert "isolated" in orphans


class TestFindBrokenLinks:
    """Detecting links to non-existent articles."""

    def test_find_broken_links_detects_missing(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "real-article.md",
            {
                "id": "real-article",
                "title": "Real Article",
                "type": "concept",
                "status": "draft",
            },
            "# Real\n\nSee [[phantom-article]] for details.",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        broken = resolver.find_broken_links(graph)
        broken_targets = [b.target_id for b in broken]
        assert "phantom-article" in broken_targets

    def test_find_broken_links_none_when_all_valid(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "alpha.md",
            {"id": "alpha", "title": "Alpha", "type": "concept", "status": "draft"},
            "# Alpha\n\nSee [[beta]].",
        )
        ops.write_compiled_article(
            "concepts",
            "beta.md",
            {"id": "beta", "title": "Beta", "type": "concept", "status": "draft"},
            "# Beta\n\nSee [[alpha]].",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        broken = resolver.find_broken_links(graph)
        assert broken == []


class TestUpdateGraph:
    """Incremental graph updates."""

    def test_update_graph_incremental(self, tmp_vault):
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "topic-a.md",
            {"id": "topic-a", "title": "Topic A", "type": "concept", "status": "draft"},
            "# A\n\nSee [[topic-b]].",
        )
        ops.write_compiled_article(
            "concepts",
            "topic-b.md",
            {"id": "topic-b", "title": "Topic B", "type": "concept", "status": "draft"},
            "# B\n\nSee [[topic-a]].",
        )
        resolver = LinkResolver(Vault(tmp_vault), ops)
        graph = resolver.build_graph()
        assert "topic-b" in graph.get_forward_links("topic-a")

        # Now update topic-a to link to something new instead
        ops.write_compiled_article(
            "concepts",
            "topic-a.md",
            {
                "id": "topic-a",
                "title": "Topic A Updated",
                "type": "concept",
                "status": "draft",
            },
            "# A Updated\n\nSee [[topic-c]].",
        )
        ops.write_compiled_article(
            "concepts",
            "topic-c.md",
            {"id": "topic-c", "title": "Topic C", "type": "concept", "status": "draft"},
            "# C",
        )

        updated = resolver.update_graph(graph, ["topic-a"])
        assert "topic-c" in updated.get_forward_links("topic-a")
        assert "topic-b" not in updated.get_forward_links("topic-a")
        # topic-b's backlinks should be updated
        assert "topic-a" not in updated.get_backlinks("topic-b")
