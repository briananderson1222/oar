"""Tests for oar.llm.providers.registry — ProviderRegistry."""

from unittest.mock import MagicMock, patch

from oar.llm.providers.registry import ProviderRegistry


class TestDetectAvailable:
    """detect_available() checks provider availability."""

    def test_detect_available_finds_installed(self):
        registry = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.available = True
        mock_provider.name = "claude-cli"

        with patch.object(registry, "_load_provider", return_value=mock_provider):
            available = registry.detect_available(["claude-cli"])
        assert "claude-cli" in available

    def test_detect_available_skips_missing(self):
        registry = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.available = False
        mock_provider.name = "codex-cli"

        with patch.object(registry, "_load_provider", return_value=mock_provider):
            available = registry.detect_available(["codex-cli"])
        assert "codex-cli" not in available


class TestGet:
    """get() lazy instantiation."""

    def test_get_instantiates_provider(self):
        registry = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.name = "claude-cli"

        with patch.object(registry, "_load_provider", return_value=mock_provider):
            result = registry.get("claude-cli")
        assert result is mock_provider

    def test_get_caches_provider(self):
        """Same provider instance returned on repeated calls."""
        registry = ProviderRegistry()
        # Pre-seed the cache to verify get() returns the cached instance.
        mock_provider = MagicMock()
        mock_provider.name = "claude-cli"
        registry._cache["claude-cli"] = mock_provider

        result1 = registry.get("claude-cli")
        result2 = registry.get("claude-cli")
        assert result1 is result2
        assert result1 is mock_provider


class TestGetHealthy:
    """get_healthy() checks health before returning."""

    def test_get_healthy_returns_healthy_provider(self):
        registry = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = True
        mock_provider.name = "claude-cli"

        with patch.object(registry, "_load_provider", return_value=mock_provider):
            result = registry.get_healthy("claude-cli")
        assert result is mock_provider

    def test_get_healthy_returns_none_for_unhealthy(self):
        registry = ProviderRegistry()
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = False
        mock_provider.name = "broken"

        with patch.object(registry, "_load_provider", return_value=mock_provider):
            result = registry.get_healthy("broken")
        assert result is None
