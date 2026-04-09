"""Classifier — LLM-based article type and tag classification."""

from __future__ import annotations

import json

from oar.llm.router import LLMRouter


CLASSIFICATION_PROMPT = """\
Classify this article. Respond with ONLY a JSON object (no markdown fences).

Title: {title}

Content (excerpt):
{excerpt}

JSON keys:
- "type": one of concept, entity, method, comparison, tutorial, timeline
- "domain": array of domain strings (e.g. ["machine-learning", "nlp"])
- "tags": array of descriptive tag strings
- "complexity": one of beginner, intermediate, advanced
- "confidence": float 0.0 to 1.0
"""


class ArticleClassifier:
    """Classify articles by type, domain, and tags using LLM."""

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    def classify(self, title: str, content: str) -> dict:
        """Return classification dict with: type, domain, tags, complexity, confidence.

        Falls back to heuristic defaults if LLM fails.
        """
        excerpt = content[:2000]
        prompt = CLASSIFICATION_PROMPT.format(title=title, excerpt=excerpt)
        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.router.complete(
                messages=messages,
                max_tokens=512,
                temperature=0.1,
                task="classify",
            )

            # Parse response.
            text = response.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

            result = json.loads(text)
            return {
                "type": result.get("type", "concept"),
                "domain": result.get("domain", ["general"]),
                "tags": result.get("tags", []),
                "complexity": result.get("complexity", "intermediate"),
                "confidence": result.get("confidence", 0.5),
            }
        except Exception:
            # Fallback to heuristic defaults.
            return self._fallback_classify(title, content)

    @staticmethod
    def _fallback_classify(title: str, content: str) -> dict:
        """Heuristic fallback when LLM classification fails."""
        return {
            "type": "concept",
            "domain": ["general"],
            "tags": [],
            "complexity": "intermediate",
            "confidence": 0.3,
        }
