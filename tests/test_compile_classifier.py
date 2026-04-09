"""Tests for oar.compile.classifier — ArticleClassifier (LLM mocked)."""

import json
from unittest.mock import MagicMock, patch

from oar.compile.classifier import ArticleClassifier
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import LLMRouter


def _mock_llm_response(content: str, input_tokens: int = 100, output_tokens: int = 50):
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


class TestClassify:
    """Classification returns structured results."""

    def test_classify_returns_type(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        classifier = ArticleClassifier(router)

        classification_json = json.dumps(
            {
                "type": "concept",
                "domain": ["machine-learning"],
                "tags": ["neural-network", "attention"],
                "complexity": "intermediate",
                "confidence": 0.9,
            }
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(classification_json)
            result = classifier.classify(
                "Transformers", "Some content about transformers."
            )

        assert result["type"] == "concept"

    def test_classify_returns_tags(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        classifier = ArticleClassifier(router)

        classification_json = json.dumps(
            {
                "type": "method",
                "domain": ["nlp"],
                "tags": ["tokenization", "bpe"],
                "complexity": "advanced",
                "confidence": 0.8,
            }
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(classification_json)
            result = classifier.classify("BPE Tokenization", "Content about BPE.")

        assert isinstance(result["tags"], list)
        assert "tokenization" in result["tags"]
        assert "bpe" in result["tags"]

    def test_classify_fallback_on_error(self, tmp_path):
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        classifier = ArticleClassifier(router)

        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("API unavailable")
            result = classifier.classify("Some Title", "Some content.")

        # Should return heuristic defaults.
        assert result["type"] == "concept"
        assert result["domain"] == ["general"]
        assert result["tags"] == []
        assert result["complexity"] == "intermediate"
        assert result["confidence"] == 0.3
