"""Consistency lint checks — LLM-powered checks for factual accuracy."""

from __future__ import annotations

import json

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.router import LLMRouter
from oar.lint.structural import LintIssue


class ConsistencyChecker:
    """LLM-powered consistency checks."""

    def __init__(self, vault: Vault, ops: VaultOps, router: LLMRouter) -> None:
        self.vault = vault
        self.ops = ops
        self.router = router

    def check_consistency(
        self,
        article_ids: list[str] | None = None,
        max_cost: float = 1.00,
    ) -> list[LintIssue]:
        """Check articles for factual inconsistencies.

        Sends article text to LLM asking it to identify:
        - Contradictions between articles
        - Missing important information
        - Outdated claims

        Batches articles (up to 3 per call) for efficiency.
        """
        articles = self._resolve_articles(article_ids)
        if not articles:
            return []

        issues: list[LintIssue] = []
        batch_size = 3

        for i in range(0, len(articles), batch_size):
            if not self.router.cost_tracker.check_budget(max_cost):
                break

            batch = articles[i : i + batch_size]
            batch_text = self._format_batch(batch)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a wiki consistency checker. "
                        "Review the following articles and identify any "
                        "factual inconsistencies, contradictions, "
                        "missing important information, or outdated claims. "
                        "Respond with a JSON array of issues. Each issue "
                        'should have keys: "article_id", "severity" '
                        '("warning" or "info"), "message", "suggestion". '
                        "If no issues are found, respond with an empty array []."
                    ),
                },
                {"role": "user", "content": batch_text},
            ]

            response = self.router.complete(messages, task="lint-consistency")

            batch_issues = self._parse_llm_issues(response.content, "inconsistent")
            issues.extend(batch_issues)

        return issues

    def suggest_connections(
        self,
        max_cost: float = 0.50,
    ) -> list[LintIssue]:
        """Suggest new [[links]] between articles that should be connected.

        Sends article summaries to LLM for connection analysis.
        """
        articles = self._resolve_articles(None)
        if len(articles) < 2:
            return []

        issues: list[LintIssue] = []
        summaries = self._build_summaries(articles)
        batch_size = 5

        for i in range(0, len(summaries), batch_size):
            if not self.router.cost_tracker.check_budget(max_cost):
                break

            batch = summaries[i : i + batch_size]
            batch_text = "\n\n".join(batch)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a wiki connection advisor. "
                        "Review the following article summaries and suggest "
                        "new wikilink connections between articles that should "
                        "be related but currently are not. "
                        "Respond with a JSON array of suggestions. Each "
                        'suggestion should have keys: "article_id", '
                        '"message", "suggestion". '
                        "If no suggestions, respond with []."
                    ),
                },
                {"role": "user", "content": batch_text},
            ]

            response = self.router.complete(messages, task="lint-connections")

            batch_issues = self._parse_llm_issues(response.content, "connection")
            issues.extend(batch_issues)

        return issues

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_articles(
        self, article_ids: list[str] | None
    ) -> list[tuple[dict, str]]:
        """Resolve article IDs to (metadata, body) pairs.

        When article_ids is None, returns all compiled articles.
        """
        if article_ids is not None:
            result = []
            for aid in article_ids:
                path = self.ops.get_article_by_id(aid)
                if path:
                    meta, body = self.ops.read_article(path)
                    result.append((meta, body))
            return result

        return [self.ops.read_article(p) for p in self.ops.list_compiled_articles()]

    def _format_batch(self, articles: list[tuple[dict, str]]) -> str:
        """Format a batch of articles for LLM review."""
        parts: list[str] = []
        for meta, body in articles:
            aid = meta.get("id", "unknown")
            title = meta.get("title", "Untitled")
            parts.append(f"## Article: {title} (id: {aid})\n\n{body}")
        return "\n\n---\n\n".join(parts)

    def _build_summaries(self, articles: list[tuple[dict, str]]) -> list[str]:
        """Build short summaries of articles for connection analysis."""
        summaries: list[str] = []
        for meta, body in articles:
            aid = meta.get("id", "unknown")
            title = meta.get("title", "Untitled")
            tags = meta.get("tags", [])
            related = meta.get("related", [])
            # First 100 words as summary
            words = body.split()[:100]
            summary = " ".join(words)
            summaries.append(
                f"Article: {title} (id: {aid})\n"
                f"Tags: {tags}\n"
                f"Related: {related}\n"
                f"Summary: {summary}"
            )
        return summaries

    def _parse_llm_issues(self, content: str, category: str) -> list[LintIssue]:
        """Parse LLM JSON response into LintIssue list."""
        try:
            # Try to extract JSON from the response.
            text = content.strip()
            # Handle markdown code blocks.
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last lines (code fences).
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)

            data = json.loads(text)
            if not isinstance(data, list):
                return []

            issues: list[LintIssue] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                issues.append(
                    LintIssue(
                        severity=item.get("severity", "info"),
                        category=category,
                        article_id=item.get("article_id", "unknown"),
                        message=item.get("message", ""),
                        suggestion=item.get("suggestion", ""),
                    )
                )
            return issues
        except (json.JSONDecodeError, ValueError):
            return []
