"""Tests for oar.cli.compile — compile CLI command (integration, LLM mocked)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.state import StateManager
from oar.llm.providers.base import LLMResponse

runner = CliRunner()


def _mock_llm_response(
    content: str, input_tokens: int = 1000, output_tokens: int = 500
):
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


def _mock_provider_response(
    content: str, input_tokens: int = 1000, output_tokens: int = 500
):
    """Create a mock LLMResponse for the provider path."""
    return LLMResponse(
        content=content,
        model="mock",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=0.01,
    )


def _make_llm_json():
    return json.dumps(
        {
            "frontmatter": {
                "type": "concept",
                "domain": ["machine-learning"],
                "tags": ["test"],
                "related": [],
                "complexity": "intermediate",
                "confidence": 0.85,
            },
            "body": "# CLI Test\n\n> **TL;DR**: CLI test.\n\n## Overview\n\nTest overview.\n",
        }
    )


class TestCompileCLI:
    """CLI compile command."""

    def test_compile_article_cli(self, tmp_vault, monkeypatch):
        """Compile a specific article by ID via CLI."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register an article in state.
        state_mgr = StateManager(tmp_vault / ".oar")
        state_mgr.register_article(
            "cli-test", "01-raw/articles/cli-test.md", "sha256:abc"
        )

        # Write a raw article.
        raw_path = tmp_vault / "01-raw" / "articles" / "cli-test.md"
        raw_path.write_text(
            "---\n"
            "id: cli-test\n"
            "title: CLI Test Article\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content for CLI test.\n"
        )

        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(_make_llm_json())

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()
            result = runner.invoke(app, ["compile", "--article", "cli-test"])

        assert result.exit_code == 0
        assert "Compiled" in result.output or "compiled" in result.output.lower()

    def test_compile_no_uncompiled(self, tmp_vault, monkeypatch):
        """Informative message when nothing to compile."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # No articles registered — nothing to compile.
        result = runner.invoke(app, ["compile"])
        assert result.exit_code == 0
        assert "No uncompiled" in result.output or "Nothing to do" in result.output
