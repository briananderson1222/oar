"""Tests for oar.cli.query --save — integration tests (LLM mocked)."""

import json
from pathlib import Path
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


class TestQuerySave:
    """--save flag integration tests."""

    def test_query_save_creates_output_file(self, tmp_vault, monkeypatch):
        """--save produces a file in 04-outputs/answers/."""
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
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            result = runner.invoke(app, ["query", "What is attention?", "--save"])

        assert result.exit_code == 0

        # Check that a file was created in 04-outputs/answers/
        answers_dir = tmp_vault / "04-outputs" / "answers"
        answer_files = list(answers_dir.glob("*.md"))
        # Exclude _index.md
        answer_files = [f for f in answer_files if f.name != "_index.md"]
        assert len(answer_files) >= 1

        # Verify the content has the answer text
        content = answer_files[0].read_text()
        assert "Attention" in content

    def test_query_save_confirmation(self, tmp_vault, monkeypatch):
        """Rich output shows confirmation message with file path."""
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
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            result = runner.invoke(app, ["query", "What is attention?", "--save"])

        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_query_save_updates_backlinks(self, tmp_vault, monkeypatch):
        """--save updates cited article with see_also backlink."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(
            "Attention is a mechanism. See [[attention-mechanism]].",
            input_tokens=200,
            output_tokens=30,
        )

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()

            result = runner.invoke(app, ["query", "What is attention?", "--save"])

        assert result.exit_code == 0

        # The cited article should have been updated with see_also
        from oar.core.frontmatter import FrontmatterManager

        article_path = tmp_vault / "02-compiled" / "concepts" / "attention-mechanism.md"
        fm = FrontmatterManager()
        meta, _ = fm.read(article_path)

        see_also = meta.get("see_also", [])
        # Should contain a link to the output
        wikilinks = [l for l in see_also if l.startswith("[[")]
        assert len(wikilinks) >= 1

    def test_query_without_save_no_file(self, tmp_vault, monkeypatch):
        """Without --save, no output file is created."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        _setup_indexed_vault(tmp_vault)

        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(
            "Attention is a mechanism.",
            input_tokens=200,
            output_tokens=20,
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

        answers_dir = tmp_vault / "04-outputs" / "answers"
        answer_files = [f for f in answers_dir.glob("*.md") if f.name != "_index.md"]
        assert len(answer_files) == 0
