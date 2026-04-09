"""Tests for oar.cli.query — CLI query command (integration, LLM mocked)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.providers.base import LLMResponse
from oar.search.indexer import SearchIndexer

runner = CliRunner()


def _mock_llm_response(content: str, input_tokens: int = 100, output_tokens: int = 50):
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


def _mock_provider_response(
    content: str, input_tokens: int = 100, output_tokens: int = 50
):
    """Create a mock LLMResponse for the provider path."""
    return LLMResponse(
        content=content,
        model="mock",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=0.001,
    )


def _patch_providers(mock_provider: MagicMock):
    """Return a context manager that patches provider imports in _shared."""
    return patch("oar.cli._shared.ProviderSelector"), patch(
        "oar.cli._shared.ProviderRegistry"
    )


def _setup_mock_selector(mock_provider: MagicMock, MockSelector, MockRegistry):
    """Configure mock selector to return the given mock provider."""
    mock_selector = MagicMock()
    mock_selector.select_with_fallback.return_value = [mock_provider]
    MockSelector.return_value = mock_selector
    MockRegistry.return_value = MagicMock()
    return mock_selector


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
        "Attention is a mechanism in neural networks that allows models to "
        "focus on relevant parts of the input.",
    )

    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()


class TestQueryCLI:
    """CLI query command."""

    def test_query_cli_displays_answer(self, tmp_vault, monkeypatch):
        """Exit 0 with answer shown."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(
            "Attention is a neural network mechanism. See [[attention-mechanism]].",
            input_tokens=200,
            output_tokens=30,
        )

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            _setup_mock_selector(mock_provider, MockSelector, MockRegistry)
            result = runner.invoke(app, ["query", "What is attention?"])

        assert result.exit_code == 0
        assert "Attention" in result.output or "attention" in result.output.lower()

    def test_query_cli_json_format(self, tmp_vault, monkeypatch):
        """Valid JSON output with --format json."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(
            "See [[attention-mechanism]].",
            input_tokens=200,
            output_tokens=20,
        )

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            _setup_mock_selector(mock_provider, MockSelector, MockRegistry)
            result = runner.invoke(
                app, ["query", "What is attention?", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "answer" in data
        assert "sources_consulted" in data
