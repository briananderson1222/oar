"""Tests for oar.cli.build — build CLI command (integration, LLM mocked)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.state import StateManager
from oar.llm.providers.base import LLMResponse

runner = CliRunner()


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
            "body": "# Test\n\n> **TL;DR**: Test.\n\n## Overview\n\nTest.\n",
        }
    )


class TestBuildCLI:
    """CLI build command."""

    def test_build_no_vault(self, monkeypatch):
        """Run oar build with no vault → exit code 1, error message."""
        # Ensure no OAR_VAULT is set and we're in a dir without a vault.
        monkeypatch.delenv("OAR_VAULT", raising=False)
        result = runner.invoke(app, ["build"])
        assert result.exit_code == 1
        assert "No OAR vault found" in result.output or "vault" in result.output.lower()

    def test_build_nothing_to_do(self, tmp_vault, monkeypatch):
        """Empty vault (no raw articles) → exit code 0, nothing-to-build message."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        result = runner.invoke(app, ["build"])
        assert result.exit_code == 0
        assert (
            "Nothing to compile" in result.output or "Nothing to build" in result.output
        )

    def test_build_with_uncompiled(self, tmp_vault, monkeypatch):
        """Build with one registered raw article → full pipeline runs."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register article in state.
        state_mgr = StateManager(tmp_vault / ".oar")
        state_mgr.register_article(
            "test-id", "01-raw/articles/test-id.md", "sha256:abc"
        )

        # Write the actual raw file.
        raw_path = tmp_vault / "01-raw" / "articles" / "test-id.md"
        raw_path.write_text(
            "---\n"
            "id: test-id\n"
            "title: Test\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content.\n"
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
            result = runner.invoke(app, ["build"])

        assert result.exit_code == 0
        # Verify compilation happened.
        output_lower = result.output.lower()
        assert "compiled" in output_lower
        # Verify indexing happened (MOC, tag, or index mentioned).
        assert "moc" in output_lower or "tag" in output_lower or "index" in output_lower
        # Verify lint happened (issues/checks/passed).
        assert (
            "lint" in output_lower
            or "issues" in output_lower
            or "passed" in output_lower
        )

    def test_build_compile_fails_gracefully(self, tmp_vault, monkeypatch):
        """When LLM provider throws, build reports error but doesn't crash."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register article in state.
        state_mgr = StateManager(tmp_vault / ".oar")
        state_mgr.register_article(
            "test-id", "01-raw/articles/test-id.md", "sha256:abc"
        )

        # Write the actual raw file.
        raw_path = tmp_vault / "01-raw" / "articles" / "test-id.md"
        raw_path.write_text(
            "---\n"
            "id: test-id\n"
            "title: Test\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content.\n"
        )

        mock_provider = MagicMock()
        mock_provider.complete.side_effect = RuntimeError("LLM unavailable")

        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            mock_selector = MagicMock()
            mock_selector.select_with_fallback.return_value = [mock_provider]
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()
            result = runner.invoke(app, ["build"])

        # Should not crash with traceback — exit code 0 or 1 is fine.
        assert result.exit_code in (0, 1)
        # The error is reported in the results table (✗ marker) or error message.
        output_lower = result.output.lower()
        assert (
            "error" in output_lower
            or "failed" in output_lower
            or "unavailable" in output_lower
            or "✗" in result.output
        )

    def test_build_dry_run(self, tmp_vault, monkeypatch):
        """oar build --dry-run shows what would be done without doing it."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register article in state.
        state_mgr = StateManager(tmp_vault / ".oar")
        state_mgr.register_article(
            "test-id", "01-raw/articles/test-id.md", "sha256:abc"
        )

        # Write the actual raw file.
        raw_path = tmp_vault / "01-raw" / "articles" / "test-id.md"
        raw_path.write_text(
            "---\n"
            "id: test-id\n"
            "title: Test\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content.\n"
        )

        result = runner.invoke(app, ["build", "--dry-run"])
        assert result.exit_code == 0
        # Should mention pending or "would compile" without actually compiling.
        output_lower = result.output.lower()
        assert (
            "pending" in output_lower
            or "would" in output_lower
            or "dry" in output_lower
        )
        # Should NOT show actual compilation results.
        assert "Compiled" not in result.output
