"""Tests for oar.cli.lint — CLI lint command (integration)."""

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

runner = CliRunner()


class TestLintCLI:
    """CLI lint command."""

    def test_lint_quick_cli(self, tmp_vault):
        """Quick lint exits 0 on clean vault."""
        result = runner.invoke(
            app,
            ["lint", "--quick"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0

    def test_lint_with_issues(self, tmp_vault):
        """Shows issues in output when problems exist."""
        ops = VaultOps(Vault(tmp_vault))
        # Write article with mismatched word count to trigger an issue.
        ops.write_compiled_article(
            "concepts",
            "bad-count.md",
            {
                "id": "bad-count",
                "title": "Bad Count",
                "type": "concept",
                "status": "draft",
                "word_count": 999,
            },
            "Just a few words.",
        )

        result = runner.invoke(
            app,
            ["lint", "--quick"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        # Should show the mismatch issue in output.
        assert "mismatch" in result.output.lower() or "issues" in result.output.lower()
