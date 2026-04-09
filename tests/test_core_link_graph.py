"""Tests for oar.core.link_graph — LinkGraph data structure."""

from oar.core.link_graph import BrokenLink, LinkGraph


class TestAddNode:
    """Adding nodes to the graph."""

    def test_add_node(self):
        graph = LinkGraph()
        graph.add_node("transformer-architecture")
        assert "transformer-architecture" in graph.get_all_nodes()


class TestAddEdge:
    """Adding edges creates forward links, backlinks, and auto-adds nodes."""

    def test_add_edge_creates_forward_link(self):
        graph = LinkGraph()
        graph.add_edge("attention-mechanism", "transformer-architecture")
        assert "transformer-architecture" in graph.get_forward_links(
            "attention-mechanism"
        )

    def test_add_edge_creates_backlink(self):
        graph = LinkGraph()
        graph.add_edge("attention-mechanism", "transformer-architecture")
        assert "attention-mechanism" in graph.get_backlinks("transformer-architecture")

    def test_add_edge_auto_adds_nodes(self):
        graph = LinkGraph()
        graph.add_edge("source-article", "target-article")
        nodes = graph.get_all_nodes()
        assert "source-article" in nodes
        assert "target-article" in nodes


class TestGetBacklinks:
    """Retrieving backlinks (articles linking TO a target)."""

    def test_get_backlinks_multiple(self):
        graph = LinkGraph()
        graph.add_edge("article-a", "target")
        graph.add_edge("article-b", "target")
        graph.add_edge("article-c", "target")
        backlinks = graph.get_backlinks("target")
        assert backlinks == ["article-a", "article-b", "article-c"]

    def test_get_backlinks_empty(self):
        graph = LinkGraph()
        graph.add_node("lonely-article")
        assert graph.get_backlinks("lonely-article") == []


class TestGetForwardLinks:
    """Retrieving forward links (links FROM an article)."""

    def test_get_forward_links(self):
        graph = LinkGraph()
        graph.add_edge("hub", "topic-a")
        graph.add_edge("hub", "topic-b")
        graph.add_edge("hub", "topic-c")
        forward = graph.get_forward_links("hub")
        assert forward == ["topic-a", "topic-b", "topic-c"]

    def test_get_forward_links_empty(self):
        graph = LinkGraph()
        graph.add_node("isolated")
        assert graph.get_forward_links("isolated") == []


class TestGetOrphans:
    """Finding orphan articles with few backlinks."""

    def test_get_orphans(self):
        graph = LinkGraph()
        # "hub" has 2 backlinks → NOT orphan (min_backlinks=2)
        graph.add_edge("a", "hub")
        graph.add_edge("b", "hub")
        # "isolated" has 0 backlinks → orphan
        graph.add_node("isolated")
        # "semi" has 1 backlink → orphan (below threshold of 2)
        graph.add_edge("c", "semi")
        orphans = graph.get_orphans(min_backlinks=2)
        assert "isolated" in orphans
        assert "semi" in orphans
        assert "hub" not in orphans

    def test_get_orphans_none(self):
        graph = LinkGraph()
        # Fully connected: every node has ≥2 backlinks
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        graph.add_edge("b", "a")
        graph.add_edge("b", "c")
        graph.add_edge("c", "a")
        graph.add_edge("c", "b")
        assert graph.get_orphans(min_backlinks=2) == []


class TestGetConnectedComponent:
    """BFS-based connected component discovery."""

    def test_get_connected_component_depth1(self):
        graph = LinkGraph()
        # a → b, a → c; b → d
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        graph.add_edge("b", "d")
        component = graph.get_connected_component("a", max_depth=1)
        # Direct neighbors (forward + backward) within 1 hop
        assert "a" in component
        assert "b" in component
        assert "c" in component
        assert "d" not in component  # 2 hops away

    def test_get_connected_component_depth2(self):
        graph = LinkGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "d")
        component = graph.get_connected_component("a", max_depth=2)
        assert "a" in component
        assert "b" in component
        assert "c" in component
        assert "d" not in component  # 3 hops away

    def test_get_connected_component_isolated(self):
        graph = LinkGraph()
        graph.add_node("lonely")
        component = graph.get_connected_component("lonely", max_depth=3)
        assert component == {"lonely"}


class TestValidateLinks:
    """Detecting broken links (edges pointing to non-existent articles)."""

    def test_validate_links_finds_broken(self):
        graph = LinkGraph()
        graph.add_edge("source", "existing-target")
        graph.add_edge("source", "missing-target")
        existing = {"source", "existing-target"}
        broken = graph.validate_links(existing)
        broken_ids = [(b.source_article, b.target_id) for b in broken]
        assert ("source", "missing-target") in broken_ids
        assert ("source", "existing-target") not in broken_ids

    def test_validate_links_all_valid(self):
        graph = LinkGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        existing = {"a", "b"}
        assert graph.validate_links(existing) == []

    def test_validate_links_context_included(self):
        graph = LinkGraph()
        graph.add_edge("source-article", "missing-target")
        broken = graph.validate_links({"source-article"})
        assert len(broken) == 1
        assert broken[0].context != ""
        assert "missing-target" in broken[0].context


class TestRemoveNode:
    """Removing a node cleans up all associated edges."""

    def test_remove_node(self):
        graph = LinkGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "b")
        graph.remove_node("b")
        assert "b" not in graph.get_all_nodes()
        assert graph.get_forward_links("a") == []
        assert graph.get_backlinks("c") == []
        assert "c" in graph.get_all_nodes()


class TestSerialize:
    """Serialization roundtrip."""

    def test_serialize_deserialize_roundtrip(self):
        graph = LinkGraph()
        graph.add_edge("attention", "transformer")
        graph.add_edge("mlp", "transformer")
        graph.add_node("isolated")
        data = graph.serialize()
        restored = LinkGraph.deserialize(data)
        assert restored.get_all_nodes() == graph.get_all_nodes()
        assert sorted(restored.get_all_edges()) == sorted(graph.get_all_edges())


class TestGetAllEdges:
    """Retrieving all edges as (source, target) pairs."""

    def test_get_all_edges(self):
        graph = LinkGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "a")
        edges = graph.get_all_edges()
        assert ("a", "b") in edges
        assert ("b", "c") in edges
        assert ("c", "a") in edges
        assert len(edges) == 3
