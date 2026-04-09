"""Web augmenter — fill missing article metadata from web search."""

from __future__ import annotations

from typing import Any

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.lint.structural import LintIssue


class WebAugmenter:
    """Augment articles with missing metadata from web search.

    Uses httpx to search the web (DuckDuckGo API or similar) for missing
    fields like author, published date, and source URL.
    """

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops
        self.fm = FrontmatterManager()

    def find_missing_metadata(self) -> list[dict[str, Any]]:
        """Find compiled articles with missing metadata fields.

        Returns list of dicts with 'article_id', 'path', 'missing_fields'.
        """
        check_fields = ["author", "published", "source_url"]
        results: list[dict[str, Any]] = []

        for path in self.ops.list_compiled_articles():
            meta, _ = self.fm.read(path)
            article_id = meta.get("id", path.stem)
            missing = [f for f in check_fields if not meta.get(f)]
            if missing:
                results.append(
                    {
                        "article_id": article_id,
                        "path": path,
                        "missing_fields": missing,
                        "title": meta.get("title", article_id),
                    }
                )
        return results

    def augment_article(
        self, article_id: str, query_hint: str | None = None
    ) -> list[LintIssue]:
        """Try to fill missing metadata for an article via web search.

        Returns LintIssues describing what was found (or not).
        """
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return []

        meta, _ = self.fm.read(path)
        title = meta.get("title", article_id)
        missing = [f for f in ("author", "published", "source_url") if not meta.get(f)]

        if not missing:
            return [
                LintIssue(
                    severity="info",
                    category="web-augment",
                    article_id=article_id,
                    message="All metadata fields already present",
                )
            ]

        # Try web search for the title.
        search_query = query_hint or title
        results = self._search(search_query)

        if not results:
            return [
                LintIssue(
                    severity="info",
                    category="web-augment",
                    article_id=article_id,
                    message=f"No web results found for '{search_query}'",
                )
            ]

        # Parse the first result to fill gaps.
        top_result = results[0]
        updates: dict[str, Any] = {}
        issues: list[LintIssue] = []

        if "author" in missing and "author" in top_result:
            updates["author"] = top_result["author"]
            issues.append(
                LintIssue(
                    severity="info",
                    category="web-augment",
                    article_id=article_id,
                    message=f"Found author: {top_result['author']}",
                    suggestion="Run with --fix to apply",
                )
            )

        if "published" in missing and "date" in top_result:
            updates["published"] = top_result["date"]
            issues.append(
                LintIssue(
                    severity="info",
                    category="web-augment",
                    article_id=article_id,
                    message=f"Found date: {top_result['date']}",
                    suggestion="Run with --fix to apply",
                )
            )

        return (
            issues
            if issues
            else [
                LintIssue(
                    severity="info",
                    category="web-augment",
                    article_id=article_id,
                    message=f"Could not fill missing fields from web: {missing}",
                )
            ]
        )

    def _search(self, query: str) -> list[dict]:
        """Perform a web search. Returns list of result dicts.

        Uses DuckDuckGo Instant Answer API (no key required).
        Mocked in tests.
        """
        try:
            import httpx

            response = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            results: list[dict] = []
            abstract = data.get("AbstractText", "")
            source = data.get("AbstractSource", "")
            if abstract:
                results.append(
                    {
                        "snippet": abstract[:200],
                        "source": source,
                    }
                )

            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(
                        {
                            "snippet": topic["Text"][:200],
                            "source": topic.get("FirstURL", ""),
                        }
                    )
            return results
        except Exception:
            return []
