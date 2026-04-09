"""Tests for oar.cli.export — CLI export command (integration)."""

from pathlib import Path

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

runner = CliRunner()


def _setup_vault_with_content(tmp_vault):
    """Create a vault with compiled articles and answers."""
    vault = Vault(tmp_vault)
    ops = VaultOps(vault)
    ops.write_compiled_article(
        "concepts",
        "attention.md",
        {
            "id": "attention",
            "title": "Attention Mechanism",
            "type": "concept",
            "status": "draft",
            "tags": ["attention"],
        },
        "# Attention\n\nAttention is important in neural networks.\n",
    )
    # Create an answer file for finetune export.
    answers_dir = tmp_vault / "04-outputs" / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    ops.fm.write(
        answers_dir / "answer-1.md",
        {"question": "What is attention?", "title": "Attention Answer"},
        "Attention is a mechanism for focusing on input.",
    )
    return vault, ops


class TestExportCLI:
    """CLI export command."""

    def test_export_html_cli(self, tmp_vault):
        _setup_vault_with_content(tmp_vault)
        output_dir = tmp_vault / "cli-export"
        result = runner.invoke(
            app,
            ["export", "--format", "html", "--output", str(output_dir)],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
        assert (output_dir / "index.html").exists()

    def test_export_finetune_cli(self, tmp_vault):
        _setup_vault_with_content(tmp_vault)
        output_dir = tmp_vault / "cli-finetune-export"
        result = runner.invoke(
            app,
            ["export", "--format", "finetune", "--output", str(output_dir)],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
