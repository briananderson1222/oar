"""Link graph — bidirectional graph of wiki article connections."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class BrokenLink:
    """A wikilink pointing to a non-existent article."""

    source_article: str
    target_id: str
    context: str  # Surrounding text of the broken link


class LinkGraph:
    """Bidirectional graph of wiki article connections.

    Nodes are article IDs (e.g., "transformer-architecture").
    Edges are wikilinks from one article to another.
    """

    def __init__(self) -> None:
        self._forward: dict[str, set[str]] = defaultdict(set)  # source → {targets}
        self._backward: dict[str, set[str]] = defaultdict(set)  # target → {sources}
        self._nodes: set[str] = set()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, article_id: str) -> None:
        """Add a node to the graph."""
        self._nodes.add(article_id)

    def add_edge(self, source: str, target: str, link_type: str = "wikilink") -> None:
        """Add a directed edge. Both nodes are auto-added."""
        self._nodes.add(source)
        self._nodes.add(target)
        self._forward[source].add(target)
        self._backward[target].add(source)

    def remove_node(self, article_id: str) -> None:
        """Remove a node and all its edges."""
        self._nodes.discard(article_id)
        # Clean up forward edges: article_id → targets
        for target in list(self._forward.get(article_id, set())):
            self._backward.get(target, set()).discard(article_id)
        self._forward.pop(article_id, None)
        # Clean up backward edges: sources → article_id
        for source in list(self._backward.get(article_id, set())):
            self._forward.get(source, set()).discard(article_id)
        self._backward.pop(article_id, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_backlinks(self, article_id: str) -> list[str]:
        """Get all article IDs that link TO this article."""
        return sorted(self._backward.get(article_id, set()))

    def get_forward_links(self, article_id: str) -> list[str]:
        """Get all article IDs this article links TO."""
        return sorted(self._forward.get(article_id, set()))

    def get_orphans(self, min_backlinks: int = 2) -> list[str]:
        """Get articles with fewer than *min_backlinks* backlinks."""
        return sorted(
            node
            for node in self._nodes
            if len(self._backward.get(node, set())) < min_backlinks
        )

    def get_connected_component(self, article_id: str, max_depth: int = 3) -> set[str]:
        """BFS to find all articles connected to this one within *max_depth* hops."""
        if article_id not in self._nodes:
            return set()
        visited: set[str] = {article_id}
        queue: list[tuple[str, int]] = [(article_id, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            # Both forward and backward neighbours count as connected.
            neighbours = self._forward.get(current, set()) | self._backward.get(
                current, set()
            )
            for neighbour in neighbours:
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append((neighbour, depth + 1))
        return visited

    def get_all_nodes(self) -> set[str]:
        """Return a copy of all node IDs."""
        return self._nodes.copy()

    def get_all_edges(self) -> list[tuple[str, str]]:
        """Return all (source, target) pairs."""
        edges: list[tuple[str, str]] = []
        for source, targets in self._forward.items():
            for target in targets:
                edges.append((source, target))
        return sorted(edges)

    def validate_links(self, existing_ids: set[str]) -> list[BrokenLink]:
        """Find all forward links pointing to IDs not in *existing_ids*."""
        broken: list[BrokenLink] = []
        for source, targets in self._forward.items():
            for target in targets:
                if target not in existing_ids:
                    broken.append(
                        BrokenLink(
                            source_article=source,
                            target_id=target,
                            context=f"[[{target}]]",
                        )
                    )
        return sorted(broken, key=lambda b: (b.source_article, b.target_id))

    def get_backlink_count(self, article_id: str) -> int:
        """Return number of articles linking to this article."""
        return len(self._backward.get(article_id, set()))

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "nodes": sorted(self._nodes),
            "edges": [{"source": s, "target": t} for s, t in self.get_all_edges()],
        }

    @classmethod
    def deserialize(cls, data: dict) -> LinkGraph:
        """Deserialize from dict."""
        graph = cls()
        for node in data.get("nodes", []):
            graph.add_node(node)
        for edge in data.get("edges", []):
            graph.add_edge(edge["source"], edge["target"])
        return graph
