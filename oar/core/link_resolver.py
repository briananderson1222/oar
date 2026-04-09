"""Link resolver — extract wikilinks from articles and build link graph."""

from __future__ import annotations

import re
from pathlib import Path

from oar.core.link_graph import BrokenLink, LinkGraph
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

# Regex matching [[link]] and [[link|display text]]
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Frontmatter fields that contain wikilink references.
_LINK_FIELDS = ("related", "see_also", "prerequisite_for")


class LinkResolver:
    """Extract wikilinks from articles and build link graph."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops

    # ------------------------------------------------------------------
    # Link extraction
    # ------------------------------------------------------------------

    def extract_wikilinks(self, text: str) -> list[str]:
        """Extract all [[wikilink]] targets from text.

        Returns list of link targets (without display text).
        Deduplicates while preserving order.
        """
        matches = WIKILINK_PATTERN.findall(text)
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            # Normalise: strip whitespace, lowercase, replace spaces with hyphens.
            target = m.strip().lower().replace(" ", "-")
            if target not in seen:
                seen.add(target)
                result.append(target)
        return result

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self) -> LinkGraph:
        """Scan all compiled articles and build complete link graph.

        For each compiled article:
        1. Add node with article_id from frontmatter
        2. Extract [[wikilinks]] from body text
        3. Extract links from frontmatter fields (related, see_also, prerequisite_for)
        4. Add edges for each link
        """
        graph = LinkGraph()
        for path in self.ops.list_compiled_articles():
            self._add_article_to_graph(graph, path)
        return graph

    def update_graph(self, graph: LinkGraph, changed_articles: list[str]) -> LinkGraph:
        """Incrementally update graph for changed articles.

        Re-scans only the specified articles, updating their edges.
        """
        changed_set = set(changed_articles)
        # Remove old edges for changed articles (but keep nodes).
        for article_id in changed_articles:
            graph.remove_node(article_id)
        # Re-scan only the changed articles.
        for path in self.ops.list_compiled_articles():
            fm, _ = self.ops.read_article(path)
            article_id = fm.get("id")
            if article_id and article_id in changed_set:
                self._add_article_to_graph(graph, path)
        return graph

    # ------------------------------------------------------------------
    # Convenience queries
    # ------------------------------------------------------------------

    def get_backlink_count(self, graph: LinkGraph, article_id: str) -> int:
        """Get number of articles linking to this article."""
        return graph.get_backlink_count(article_id)

    def find_orphans(self, graph: LinkGraph, min_backlinks: int = 2) -> list[str]:
        """Find articles with fewer than *min_backlinks*."""
        return graph.get_orphans(min_backlinks)

    def find_broken_links(self, graph: LinkGraph) -> list[BrokenLink]:
        """Find links pointing to non-existent articles."""
        existing: set[str] = set()
        for path in self.ops.list_compiled_articles():
            fm, _ = self.ops.read_article(path)
            if "id" in fm:
                existing.add(fm["id"])
        return graph.validate_links(existing)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_article_to_graph(self, graph: LinkGraph, path: Path) -> None:
        """Read a single article file and add its nodes/edges to *graph*."""
        fm, body = self.ops.read_article(path)
        article_id = fm.get("id")
        if not article_id:
            return
        graph.add_node(article_id)

        # Wikilinks from body text.
        for target in self.extract_wikilinks(body):
            graph.add_edge(article_id, target)

        # Wikilinks from structured frontmatter fields.
        for field in _LINK_FIELDS:
            field_val = fm.get(field, [])
            if isinstance(field_val, list):
                for item in field_val:
                    for target in self.extract_wikilinks(str(item)):
                        graph.add_edge(article_id, target)
