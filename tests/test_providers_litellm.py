"""Tests for oar.llm.providers.litellm_provider — LitellmProvider (mocked litellm)."""

import os
from unittest.mock import MagicMock, patch

from oar.llm.providers.litellm_provider import LitellmProvider


def _make_provider() -> LitellmProvider:
    return LitellmProvider()


class TestLitellmAvailable:
    """available property."""

    def test_litellm_available_with_anthropic_key(self):
        p = _make_provider()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123"}):
            assert p.available is True

    def test_litellm_available_with_openai_key(self):
        p = _make_provider()
        env = {"OPENAI_API_KEY": "sk-test-456"}
        with patch.dict(os.environ, env, clear=False):
            # Remove ANTHROPIC key if present.
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ["OPENAI_API_KEY"] = "sk-test-456"
            assert p.available is True

    def test_litellm_not_available_without_key(self):
        p = _make_provider()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            assert p.available is False


class TestLitellmComplete:
    """complete() delegation."""

    def test_litellm_complete_returns_response(self):
        p = _make_provider()
        mock_usage = MagicMock(prompt_tokens=100, completion_tokens=50)
        mock_response = MagicMock(
            usage=mock_usage,
            choices=[MagicMock(message=MagicMock(content="Hello back"))],
        )
        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            resp = p.complete(
                messages=[{"role": "user", "content": "Hi"}],
                model="claude-sonnet-4-20250514",
            )
        assert resp.content == "Hello back"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.model == "claude-sonnet-4-20250514"
        mock_comp.assert_called_once()
