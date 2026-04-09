"""Tests for oar.compile.concept_extractor — ConceptExtractor (LLM mocked)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from oar.compile.concept_extractor import ConceptExtractor, ConceptSuggestion
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import LLMRouter


def _setup_extractor(tmp_path: Path):
    """Create a ConceptExtractor with a mocked router."""
    tracker = CostTracker(tmp_path / "cost")
    router = LLMRouter("claude-sonnet-4-20250514", tracker)
    return ConceptExtractor(router), router


def _mock_llm_response(content: str):
    """Create a mock LLMResponse."""
    return MagicMock(
        content=content,
        model="claude-sonnet-4-20250514",
        input_tokens=500,
        output_tokens=200,
        cost_usd=0.001,
    )


class TestExtractConcepts:
    """extract_concepts returns concept suggestions."""

    def test_extract_concepts_returns_suggestions(self, tmp_path):
        extractor, router = _setup_extractor(tmp_path)

        suggestions_json = json.dumps(
            [
                {
                    "title": "Attention Mechanism",
                    "slug": "attention-mechanism",
                    "type": "concept",
                    "reason": "Core concept referenced throughout",
                    "priority": 1,
                },
                {
                    "title": "Self-Attention",
                    "slug": "self-attention",
                    "type": "method",
                    "reason": "Key technique explained in detail",
                    "priority": 2,
                },
            ]
        )

        with patch.object(
            router, "complete", return_value=_mock_llm_response(suggestions_json)
        ):
            results = extractor.extract_concepts(
                "Article about transformers and attention.", "transformer-arch"
            )

        assert len(results) == 2
        assert all(isinstance(s, ConceptSuggestion) for s in results)

    def test_extract_concepts_has_slugs(self, tmp_path):
        extractor, router = _setup_extractor(tmp_path)

        suggestions_json = json.dumps(
            [
                {
                    "title": "Positional Encoding",
                    "slug": "positional-encoding",
                    "type": "concept",
                    "reason": "Important sub-topic",
                    "priority": 1,
                },
            ]
        )

        with patch.object(
            router, "complete", return_value=_mock_llm_response(suggestions_json)
        ):
            results = extractor.extract_concepts("Content here.", "test-id")

        for s in results:
            assert s.slug != ""
            assert isinstance(s.slug, str)

    def test_extract_concepts_prioritizes(self, tmp_path):
        extractor, router = _setup_extractor(tmp_path)

        suggestions_json = json.dumps(
            [
                {
                    "title": "High Priority",
                    "slug": "high-priority",
                    "type": "concept",
                    "reason": "Very important",
                    "priority": 1,
                },
                {
                    "title": "Low Priority",
                    "slug": "low-priority",
                    "type": "entity",
                    "reason": "Less important",
                    "priority": 3,
                },
            ]
        )

        with patch.object(
            router, "complete", return_value=_mock_llm_response(suggestions_json)
        ):
            results = extractor.extract_concepts("Content here.", "test-id")

        priorities = [s.priority for s in results]
        assert 1 in priorities
        assert 3 in priorities

    def test_extract_concepts_fallback_on_error(self, tmp_path):
        extractor, router = _setup_extractor(tmp_path)

        # Body with wikilinks that the heuristic should extract.
        body = "See [[attention-mechanism]] and [[positional-encoding]] for details."

        with patch.object(router, "complete", side_effect=Exception("LLM unavailable")):
            results = extractor.extract_concepts(body, "test-id")

        # Should fall back to heuristic extraction of wikilinks.
        assert len(results) > 0
        assert all(isinstance(s, ConceptSuggestion) for s in results)
        slugs = [s.slug for s in results]
        assert "attention-mechanism" in slugs
        assert "positional-encoding" in slugs
