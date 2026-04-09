"""Tests for oar.cli.compile --pending flag."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from oar.cli.main import app

runner = CliRunner()


class TestCompilePendingCLI:
    """oar compile --pending flag tests."""

    def test_compile_pending_shows_queue(self, tmp_vault, monkeypatch):
        """--pending shows pending articles needing compilation."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        # Write a raw article.
        raw_path = tmp_vault / "01-raw" / "articles" / "pending-test.md"
        raw_path.write_text(
            "---\n"
            "id: pending-test\n"
            "title: Pending Test\n"
            "source_type: article\n"
            "compiled: false\n"
            "---\n\n"
            "Some content.\n"
        )

        result = runner.invoke(app, ["compile", "--pending"])
        assert result.exit_code == 0
        # Should show the article in the pending queue.
        assert (
            "pending-test" in result.output
            or "NEW" in result.output
            or "Pending" in result.output
        )

    def test_compile_pending_no_work(self, tmp_vault, monkeypatch):
        """--pending shows nothing to compile when all is up to date."""
        monkeypatch.setenv("OAR_VAULT", str(tmp_vault))

        result = runner.invoke(app, ["compile", "--pending"])
        assert result.exit_code == 0
        # Should show "nothing" or "no" in some form.
        output_lower = result.output.lower()
        assert (
            "nothing" in output_lower or "no " in output_lower or "0 " in output_lower
        )
