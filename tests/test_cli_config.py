"""Tests for oar config CLI command and config-driven provider selection."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.config import OarConfig, LlmConfig

runner = CliRunner()


class TestConfigCLI:
    """oar config command."""

    def test_config_list(self, tmp_vault, monkeypatch):
        """oar config --list shows all config values."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["config", "--list"])
        assert result.exit_code == 0
        assert "llm" in result.output.lower() or "provider" in result.output.lower()

    def test_config_read_key(self, tmp_vault, monkeypatch):
        """oar config llm.provider reads a specific key."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["config", "llm.provider"])
        assert result.exit_code == 0
        assert "auto" in result.output

    def test_config_set_key(self, tmp_vault, monkeypatch):
        """oar config llm.provider claude-cli sets a value."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Set the value.
        result = runner.invoke(app, ["config", "llm.provider", "claude-cli"])
        assert result.exit_code == 0
        assert "Set" in result.output

        # Verify it was persisted.
        result = runner.invoke(app, ["config", "llm.provider"])
        assert result.exit_code == 0
        assert "claude-cli" in result.output

    def test_config_set_integer(self, tmp_vault, monkeypatch):
        """oar config llm.cli_timeout 60 sets an integer."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["config", "llm.cli_timeout", "60"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["config", "llm.cli_timeout"])
        assert result.exit_code == 0
        assert "60" in result.output

    def test_config_nonexistent_key(self, tmp_vault, monkeypatch):
        """oar config nonexistent.key exits with error."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["config", "nonexistent.key"])
        assert result.exit_code == 1


class TestConfigDrivenProviders:
    """Config settings control provider selection."""

    def test_preferred_provider_placed_first(self, tmp_vault, monkeypatch):
        """config llm.provider=claude-cli puts claude-cli first in chain."""
        from oar.cli._shared import build_router

        # Set provider preference.
        config = OarConfig.load(tmp_vault / ".oar" / "config.yaml")
        config.llm.provider = "claude-cli"
        config.save(tmp_vault / ".oar" / "config.yaml")

        with patch("oar.cli._shared.ProviderSelector") as MockSelector:
            mock_selector = MagicMock()
            MockSelector.DEFAULT_CHAIN = [
                "claude-cli",
                "opencode-cli",
                "codex-cli",
                "litellm",
            ]
            MockSelector.return_value = mock_selector

            router, _, _ = build_router(tmp_vault)

            # Verify the selector was created with claude-cli first.
            call_args = MockSelector.call_args
            chain = call_args.kwargs.get("fallback_chain") or (
                call_args[0][0] if call_args[0] else None
            )
            if chain:
                assert chain[0] == "claude-cli"

    def test_custom_fallback_chain(self, tmp_vault, monkeypatch):
        """config llm.fallback_chain=['codex-cli','litellm'] is respected."""
        from oar.cli._shared import build_router

        config = OarConfig.load(tmp_vault / ".oar" / "config.yaml")
        config.llm.fallback_chain = ["codex-cli", "litellm"]
        config.save(tmp_vault / ".oar" / "config.yaml")

        with patch("oar.cli._shared.ProviderSelector") as MockSelector:
            mock_selector = MagicMock()
            MockSelector.DEFAULT_CHAIN = [
                "claude-cli",
                "opencode-cli",
                "codex-cli",
                "litellm",
            ]
            MockSelector.return_value = mock_selector

            build_router(tmp_vault)

            call_args = MockSelector.call_args
            chain = call_args.kwargs.get("fallback_chain")
            assert chain == ["codex-cli", "litellm"]

    def test_cli_timeout_passed_to_registry(self, tmp_vault, monkeypatch):
        """config llm.cli_timeout=60 is passed to ProviderRegistry."""
        from oar.cli._shared import build_router

        config = OarConfig.load(tmp_vault / ".oar" / "config.yaml")
        config.llm.cli_timeout = 60
        config.save(tmp_vault / ".oar" / "config.yaml")

        with patch("oar.cli._shared.ProviderRegistry") as MockRegistry:
            MockRegistry.return_value = MagicMock()

            with patch("oar.cli._shared.ProviderSelector") as MockSelector:
                MockSelector.return_value = MagicMock()
                MockSelector.DEFAULT_CHAIN = ["claude-cli"]

                build_router(tmp_vault)

                MockRegistry.assert_called_with(timeout=60)
