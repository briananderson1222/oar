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

    def test_build_auto_discovers_dropped_file(self, tmp_vault, monkeypatch):
        """Dropping a .md into 01-raw/ without register_article() still gets compiled."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write a raw file WITHOUT calling state_mgr.register_article().
        raw_path = tmp_vault / "01-raw" / "articles" / "dropped-article.md"
        raw_path.write_text(
            "---\n"
            "id: dropped-article\n"
            "title: Dropped Article\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "This was dropped directly into 01-raw.\n"
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
        output_lower = result.output.lower()
        # The file should have been auto-registered.
        assert "auto-registered" in output_lower
        # The file should have been compiled (compile step ran).
        assert "compiled" in output_lower

    def test_build_auto_discovers_special_chars_filename(self, tmp_vault, monkeypatch):
        """Files with spaces/parens in name get slugified IDs."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))
        # Drop a file with special chars — no id field.
        raw_path = tmp_vault / "01-raw" / "articles" / "Agent Client Protocol (ACP).md"
        raw_path.write_text(
            "---\n"
            "title: Agent Client Protocol (ACP)\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content about ACP.\n"
        )
        mock_provider = MagicMock()
        mock_provider.complete.return_value = _mock_provider_response(_make_llm_json())
        mock_selector = MagicMock()
        mock_selector.select_with_fallback.return_value = [mock_provider]
        with (
            patch("oar.cli._shared.ProviderSelector") as MockSelector,
            patch("oar.cli._shared.ProviderRegistry") as MockRegistry,
        ):
            MockSelector.return_value = mock_selector
            MockRegistry.return_value = MagicMock()
            result = runner.invoke(app, ["build"])
        assert result.exit_code == 0
        assert (
            "auto-registered" in result.output.lower()
            or "compiled" in result.output.lower()
        )
        # Verify it was registered with a slugified ID.
        from oar.core.state import StateManager

        state_mgr = StateManager(tmp_vault / ".oar")
        state = state_mgr.load()
        assert "agent-client-protocol-acp" in state["articles"]

    def test_build_skips_already_compiled(self, tmp_vault, monkeypatch):
        """Already-compiled articles are skipped; LLM provider is not called."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Register an article AND mark it as compiled.
        state_mgr = StateManager(tmp_vault / ".oar")
        state_mgr.register_article(
            "already-done", "01-raw/articles/already-done.md", "sha256:abc"
        )
        state_mgr.mark_compiled("already-done", ["already-done"])

        # Write the raw file so auto-discovery can see it.
        raw_path = tmp_vault / "01-raw" / "articles" / "already-done.md"
        raw_path.write_text(
            "---\n"
            "id: already-done\n"
            "title: Already Done\n"
            "source_type: article\n"
            "compiled: true\n"
            "---\n\n"
            "Already compiled content.\n"
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
        output_lower = result.output.lower()
        # Should report nothing to compile.
        assert "nothing to compile" in output_lower
        # The compile step should NOT have been called.
        mock_provider.complete.assert_not_called()
        # Index and lint still run.
        assert "lint" in output_lower or "passed" in output_lower

    def test_build_idempotent(self, tmp_vault, monkeypatch):
        """Running oar build twice: second run skips already-compiled articles."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write a raw file without registration — will be auto-discovered.
        raw_path = tmp_vault / "01-raw" / "articles" / "idempotent-test.md"
        raw_path.write_text(
            "---\n"
            "id: idempotent-test\n"
            "title: Idempotent Test\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Content for idempotent test.\n"
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

            # First build — should compile the article.
            result1 = runner.invoke(app, ["build"])
            assert result1.exit_code == 0
            assert "compiled" in result1.output.lower()

            # Reset mock call tracker for the second run.
            mock_provider.complete.reset_mock()

            # Second build — should find nothing to compile.
            result2 = runner.invoke(app, ["build"])
            assert result2.exit_code == 0
            output2_lower = result2.output.lower()
            assert "nothing to compile" in output2_lower
            # The LLM provider should NOT have been called a second time.
            mock_provider.complete.assert_not_called()
