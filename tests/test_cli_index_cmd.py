"""Tests for oar.cli.index_cmd — CLI index command (integration)."""

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

runner = CliRunner()


class TestIndexRebuildCLI:
    """oar index --rebuild behaviour."""

    def test_index_rebuild_cli(self, tmp_vault):
        # Add some compiled articles so MOCs/tags have content.
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "a.md",
            {
                "id": "a",
                "title": "A",
                "type": "concept",
                "status": "draft",
                "domain": ["ml"],
                "tags": ["python"],
            },
            "Body A.",
        )
        ops.write_compiled_article(
            "concepts",
            "b.md",
            {
                "id": "b",
                "title": "B",
                "type": "concept",
                "status": "draft",
                "domain": ["ml"],
                "tags": ["python"],
            },
            "Body B.",
        )

        result = runner.invoke(
            app,
            ["index", "--rebuild"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0


class TestIndexUpdateCLI:
    """oar index --update behaviour."""

    def test_index_update_cli(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "c.md",
            {
                "id": "c",
                "title": "C",
                "type": "concept",
                "status": "draft",
                "domain": ["testing"],
                "tags": ["pytest"],
            },
            "Body C.",
        )
        ops.write_compiled_article(
            "concepts",
            "d.md",
            {
                "id": "d",
                "title": "D",
                "type": "concept",
                "status": "draft",
                "domain": ["testing"],
                "tags": ["pytest"],
            },
            "Body D.",
        )

        result = runner.invoke(
            app,
            ["index", "--update"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
