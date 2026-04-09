"""Tests for CLI provider wiring — verify query and lint commands use providers."""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from typer.testing import CliRunner

from oar.cli.main import app
from oar.cli._shared import find_vault_path, build_router
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.providers.base import LLMResponse
from oar.search.indexer import SearchIndexer

runner = CliRunner()


def _setup_indexed_vault(tmp_vault):
    """Create a vault with compiled articles and a search index."""
    ops = VaultOps(Vault(tmp_vault))

    ops.write_compiled_article(
        "concepts",
        "attention-mechanism.md",
        {
            "id": "attention-mechanism",
            "title": "Attention Mechanism",
            "type": "concept",
            "tags": ["attention", "neural-network"],
            "status": "draft",
            "related": [],
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks.",
    )

    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()


class TestSharedBuildRouter:
    """Tests for oar.cli._shared.build_router."""

    def test_build_router_returns_router_with_provider_selector(self, tmp_vault):
        """build_router creates a router with a provider_selector when providers are available."""
        with (
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
        ):
            mock_selector = MagicMock()
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            router, cost_tracker, config = build_router(tmp_vault)

            assert router is not None
            assert cost_tracker is not None
            assert config is not None
            # The router should have the provider_selector set.
            assert router._provider_selector is mock_selector

    def test_build_router_falls_back_when_providers_fail(self, tmp_vault):
        """build_router creates a router without providers when import fails."""
        with patch(
            "oar.cli._shared.ProviderSelector", side_effect=RuntimeError("nope")
        ):
            router, cost_tracker, config = build_router(tmp_vault)

            assert router is not None
            assert router._provider_selector is None
            assert router._provider is None

    def test_build_router_uses_config_model(self, tmp_vault):
        """build_router uses config's default_model when no model arg given."""
        router, _, config = build_router(tmp_vault)
        assert router.default_model == config.llm.default_model

    def test_build_router_overrides_model(self, tmp_vault):
        """build_router uses the explicit model argument when given."""
        router, _, _ = build_router(tmp_vault, model="gpt-4")
        assert router.default_model == "gpt-4"


class TestQueryProviderWiring:
    """Tests verifying query command uses provider path."""

    def test_query_uses_provider_when_available(self, tmp_vault, monkeypatch):
        """Query command routes through ProviderSelector."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(
            content="Based on the wiki, attention is a neural network mechanism.",
            model="claude-sonnet",
            input_tokens=200,
            output_tokens=30,
            cost_usd=0.003,
        )

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            result = runner.invoke(app, ["query", "What is attention?"])

        assert result.exit_code == 0

    def test_query_falls_back_to_litellm_without_providers(
        self, tmp_vault, monkeypatch
    ):
        """Query command falls back to litellm when no providers available."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        with (
            patch("oar.cli._shared.ProviderSelector", side_effect=RuntimeError("nope")),
            patch("litellm.completion") as mock_completion,
        ):
            mock_completion.return_value = MagicMock(
                usage=MagicMock(prompt_tokens=200, completion_tokens=30),
                choices=[
                    MagicMock(message=MagicMock(content="Attention is a mechanism."))
                ],
            )
            result = runner.invoke(app, ["query", "What is attention?"])

        assert result.exit_code == 0


class TestLintProviderWiring:
    """Tests verifying lint command uses provider path for consistency checks."""

    def test_lint_consistency_uses_provider(self, tmp_vault, monkeypatch):
        """Lint consistency check routes through ProviderSelector."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        # Write a compiled article for consistency checking.
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "test-article.md",
            {
                "id": "test-article",
                "title": "Test Article",
                "type": "concept",
                "status": "draft",
                "word_count": 20,
            },
            "This is test content about neural networks.",
        )

        mock_provider = MagicMock()
        mock_provider.complete.return_value = LLMResponse(
            content="[]",
            model="claude-sonnet",
            input_tokens=100,
            output_tokens=10,
            cost_usd=0.001,
        )

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            result = runner.invoke(app, ["lint"])

        assert result.exit_code == 0
        mock_provider.complete.assert_called()

    def test_lint_quick_skips_llm(self, tmp_vault, monkeypatch):
        """Lint --quick skips LLM consistency checks entirely."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        with patch("oar.cli._shared.build_router") as mock_build:
            result = runner.invoke(app, ["lint", "--quick"])

        assert result.exit_code == 0
        # build_router should NOT be called for --quick mode.
        mock_build.assert_not_called()

    def test_lint_consistency_graceful_fallback(self, tmp_vault, monkeypatch):
        """Lint falls back gracefully when LLM calls fail."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "test.md",
            {
                "id": "test",
                "title": "Test",
                "type": "concept",
                "status": "draft",
                "word_count": 10,
            },
            "Short content.",
        )

        with patch(
            "oar.cli._shared.ProviderSelector",
            side_effect=RuntimeError("nope"),
        ):
            result = runner.invoke(app, ["lint"])

        # Should not crash — LLM checks are optional.
        assert result.exit_code == 0


class TestFindVaultPath:
    """Tests for the shared find_vault_path utility."""

    def test_finds_vault_from_env(self, tmp_vault, monkeypatch):
        """Finds vault via OAR_VAULT env var."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        assert find_vault_path() == tmp_vault

    def test_returns_none_without_vault(self, tmp_path, monkeypatch):
        """Returns None when no vault found."""
        monkeypatch.delenv("OAR_VAULT", raising=False)
        monkeypatch.chdir(tmp_path)
        assert find_vault_path() is None
