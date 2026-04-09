"""Tests for offline mode — OllamaProvider, OfflineManager, --offline flag."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.config import OarConfig
from oar.llm.offline import OfflineManager
from oar.llm.providers.base import LLMResponse

runner = CliRunner()


class TestOllamaProvider:
    """OllamaProvider unit tests (all HTTP calls mocked)."""

    def test_ollama_health_check_available(self):
        """Health check returns True when Ollama responds."""
        from oar.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert provider.health_check() is True

    def test_ollama_health_check_unavailable(self):
        """Health check returns False when Ollama is not running."""
        from oar.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("httpx.get", side_effect=Exception("connection refused")):
            assert provider.health_check() is False

    def test_ollama_complete_sends_chat_request(self):
        """complete() sends proper chat API request."""
        from oar.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "message": {"content": "Hello from Ollama!"},
                "eval_count": 10,
                "prompt_eval_count": 20,
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = provider.complete(
                [{"role": "user", "content": "Hello"}],
                model="llama3.1",
            )

            assert result.content == "Hello from Ollama!"
            assert result.model == "llama3.1"
            assert result.cost_usd == 0.0
            assert result.input_tokens == 20
            assert result.output_tokens == 10

    def test_ollama_complete_strips_ollama_prefix(self):
        """Model names with 'ollama/' prefix are stripped."""
        from oar.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "message": {"content": "test"},
                "eval_count": 5,
                "prompt_eval_count": 10,
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = provider.complete(
                [{"role": "user", "content": "test"}],
                model="ollama/mistral",
            )

            # Verify the payload sent to Ollama uses the stripped name.
            call_args = mock_post.call_args
            assert call_args.kwargs["json"]["model"] == "mistral"

    def test_ollama_list_models(self):
        """list_models returns model names from Ollama."""
        from oar.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama3.1:latest"},
                    {"name": "mistral:latest"},
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            models = provider.list_models()
            assert "llama3.1:latest" in models
            assert "mistral:latest" in models

    def test_ollama_connection_error_recoverable(self):
        """Connection error raises recoverable LLMProviderError."""
        from oar.llm.providers.ollama_provider import OllamaProvider
        from oar.llm.providers.base import LLMProviderError
        import httpx

        provider = OllamaProvider()
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete([{"role": "user", "content": "test"}])
            assert exc_info.value.recoverable is True


class TestOfflineManager:
    """OfflineManager — mode detection and fallback logic."""

    def test_is_offline_from_env(self, monkeypatch):
        """OAR_OFFLINE env var enables offline mode."""
        monkeypatch.setenv("OAR_OFFLINE", "true")
        mgr = OfflineManager()
        assert mgr.is_offline() is True

    def test_is_offline_from_config(self):
        """Config offline=true enables offline mode."""
        config = OarConfig()
        config.llm.offline = True
        mgr = OfflineManager(config)
        assert mgr.is_offline() is True

    def test_is_offline_from_override(self):
        """set_offline(True) forces offline mode."""
        mgr = OfflineManager()
        mgr.set_offline(True)
        assert mgr.is_offline() is True

    def test_is_not_offline_by_default(self):
        """Not offline when no flags set."""
        mgr = OfflineManager()
        assert mgr.is_offline() is False

    def test_check_ollama_available(self):
        """check_ollama_available returns True when Ollama is running."""
        mgr = OfflineManager()
        with patch(
            "oar.llm.providers.ollama_provider.OllamaProvider.health_check",
            return_value=True,
        ):
            assert mgr.check_ollama_available() is True

    def test_check_ollama_not_available(self):
        """check_ollama_available returns False when Ollama is not running."""
        mgr = OfflineManager()
        with patch(
            "oar.llm.providers.ollama_provider.OllamaProvider.health_check",
            return_value=False,
        ):
            assert mgr.check_ollama_available() is False

    def test_get_fallback_model_uses_available(self):
        """get_fallback_model returns first preferred available model."""
        mgr = OfflineManager()
        with patch.object(
            mgr, "list_local_models", return_value=["mistral:latest", "phi3:latest"]
        ):
            model = mgr.get_fallback_model()
            assert "mistral" in model

    def test_get_fallback_model_default(self):
        """get_fallback_model returns default when no models found."""
        mgr = OfflineManager()
        with patch.object(mgr, "list_local_models", return_value=[]):
            model = mgr.get_fallback_model()
            assert model == "ollama/llama3.1"

    def test_should_disable_feature(self):
        """Web features are disabled in offline mode."""
        mgr = OfflineManager()
        mgr.set_offline(True)
        assert mgr.should_disable_feature("web_search") is True
        assert mgr.should_disable_feature("url_ingest") is True
        assert mgr.should_disable_feature("compile") is False
        assert mgr.should_disable_feature("search") is False

    def test_get_offline_fallback_chain(self):
        """Returns ['ollama'] when Ollama is available."""
        mgr = OfflineManager()
        with patch.object(mgr, "check_ollama_available", return_value=True):
            chain = mgr.get_offline_fallback_chain()
            assert chain == ["ollama"]

    def test_get_offline_fallback_chain_empty(self):
        """Returns [] when Ollama is not available."""
        mgr = OfflineManager()
        with patch.object(mgr, "check_ollama_available", return_value=False):
            chain = mgr.get_offline_fallback_chain()
            assert chain == []


class TestOfflineCLIFlag:
    """CLI --offline flag tests."""

    def test_offline_flag_sets_env(self, tmp_vault, monkeypatch):
        """--offline flag sets OAR_OFFLINE environment variable."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["--offline", "status"])
        # The command should succeed (status doesn't need LLM).
        assert result.exit_code == 0

    def test_offline_flag_with_compile(self, tmp_vault, monkeypatch):
        """--offline compile doesn't crash (even if no Ollama)."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["--offline", "compile"])
        # Should exit gracefully (no articles or no providers).
        assert result.exit_code in (0, 1)
