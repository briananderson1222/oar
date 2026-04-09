"""Concept extractor — identify sub-concepts in compiled text for standalone articles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from oar.llm.router import LLMRouter


@dataclass
class ConceptSuggestion:
    """A suggestion for a sub-concept that deserves its own article."""

    title: str
    slug: str
    type: str  # concept | entity | method
    reason: str
    priority: int  # 1=high, 3=low


class ConceptExtractor:
    """Identify sub-concepts in compiled text that should become separate articles."""

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    def extract_concepts(
        self, compiled_body: str, article_id: str
    ) -> list[ConceptSuggestion]:
        """Use LLM to identify sub-concepts in compiled article text.

        Falls back to heuristic extraction if LLM fails.
        """
        prompt = f"""Analyze this wiki article and identify sub-concepts that deserve their own separate articles.

Article ID: {article_id}
Content:
{compiled_body[:3000]}

Return a JSON array of objects with keys: title (str), slug (str), type (concept|entity|method), reason (why it deserves its own article), priority (1=high, 3=low).

Only suggest genuinely important sub-concepts that have enough depth for a standalone article. Maximum 5 suggestions.

Return ONLY the JSON array, no markdown."""

        try:
            response = self.router.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3,
                task="extract",
            )
            suggestions = json.loads(response.content)
            return [
                ConceptSuggestion(
                    title=s["title"],
                    slug=s["slug"],
                    type=s.get("type", "concept"),
                    reason=s.get("reason", ""),
                    priority=s.get("priority", 3),
                )
                for s in suggestions
            ]
        except Exception:
            # Heuristic fallback: extract [[wikilinks]] mentioned but not expanded.
            return self._heuristic_extract(compiled_body)

    @staticmethod
    def _heuristic_extract(text: str) -> list[ConceptSuggestion]:
        """Fallback: extract [[wikilinks]] as concept suggestions."""
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)
        return [
            ConceptSuggestion(
                title=link.replace("-", " ").title(),
                slug=link.strip().lower().replace(" ", "-"),
                type="concept",
                reason=f"Referenced in article as [[{link}]]",
                priority=3,
            )
            for link in links[:5]
        ]
