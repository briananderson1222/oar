"""Tests for oar.cli.search — CLI search command (integration)."""

import json

from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
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
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks that allows models to "
        "focus on relevant parts of the input.",
    )
    ops.write_compiled_article(
        "methods",
        "fine-tuning.md",
        {
            "id": "fine-tuning",
            "title": "Fine-Tuning",
            "type": "method",
            "tags": ["training"],
            "status": "draft",
            "word_count": 25,
        },
        "Fine-tuning is the process of adapting a pre-trained model.",
    )

    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()


class TestSearchCLI:
    """CLI search command."""

    def test_search_cli_table_format(self, tmp_vault):
        _setup_indexed_vault(tmp_vault)
        result = runner.invoke(
            app,
            ["search", "attention"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
        assert "Attention" in result.output

    def test_search_cli_json_format(self, tmp_vault):
        _setup_indexed_vault(tmp_vault)
        result = runner.invoke(
            app,
            ["search", "attention", "--format", "json"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["article_id"] == "attention-mechanism"

    def test_search_cli_no_results(self, tmp_vault):
        _setup_indexed_vault(tmp_vault)
        result = runner.invoke(
            app,
            ["search", "xyzzyplughnothingatall"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0
        assert "No results" in result.output
