"""Tests for oar.cli.search — CLI search --serve option."""

from unittest.mock import patch

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
            "tags": ["attention"],
            "status": "draft",
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks.",
    )

    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(Vault(tmp_vault), ops)
    indexer.close()


class TestSearchServeCLI:
    """CLI search --serve option."""

    def test_search_serve_cli(self, tmp_vault):
        """--serve should parse correctly and invoke uvicorn (mocked)."""
        _setup_indexed_vault(tmp_vault)

        with patch("oar.cli.search.uvicorn") as mock_uvicorn:
            result = runner.invoke(
                app,
                ["search", "--serve"],
                env={"OAR_VAULT": str(tmp_vault)},
            )
            # uvicorn.run should have been called
            assert mock_uvicorn.run.called
            assert result.exit_code == 0

    def test_search_serve_custom_port(self, tmp_vault):
        """--serve --port should pass port to uvicorn."""
        _setup_indexed_vault(tmp_vault)

        with patch("oar.cli.search.uvicorn") as mock_uvicorn:
            result = runner.invoke(
                app,
                ["search", "--serve", "--port", "4242"],
                env={"OAR_VAULT": str(tmp_vault)},
            )
            assert result.exit_code == 0
            call_kwargs = mock_uvicorn.run.call_args
            # Verify port is passed (either positional or keyword).
            assert 4242 in call_kwargs.args or call_kwargs.kwargs.get("port") == 4242
