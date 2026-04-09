"""Tests for oar.cli.ingest — CLI ingest command (integration)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from oar.cli.main import app
from oar.core.vault import Vault


runner = CliRunner()


class TestIngestFileCLI:
    """oar ingest --file behaviour."""

    def test_ingest_file_cli(self, tmp_vault):
        # Create a source file.
        source = tmp_vault / "article.md"
        source.write_text("# Test\n\nSome content to import.")

        result = runner.invoke(
            app,
            ["ingest", "--file", str(source)],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        # Command should succeed.
        assert result.exit_code == 0

        # A new file should exist in 01-raw/articles/.
        articles_dir = tmp_vault / "01-raw" / "articles"
        md_files = [
            f
            for f in articles_dir.iterdir()
            if f.suffix == ".md" and f.name != "_index.md"
        ]
        assert len(md_files) >= 1

    def test_ingest_file_updates_state(self, tmp_vault):
        import json

        source = tmp_vault / "note.md"
        source.write_text("Content for state tracking.")

        result = runner.invoke(
            app,
            ["ingest", "--file", str(source)],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0

        state_file = tmp_vault / ".oar" / "state.json"
        state = json.loads(state_file.read_text())
        assert state["stats"]["raw_articles"] >= 1
        # At least one article registered with a hash.
        articles = state.get("articles", {})
        assert len(articles) >= 1
        for article_id, info in articles.items():
            assert info["content_hash"].startswith("sha256:")

    def test_ingest_no_source_errors(self, tmp_vault):
        result = runner.invoke(
            app,
            ["ingest"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        # Should indicate an error — no source provided.
        assert result.exit_code != 0

    def test_ingest_url_cli_mocked(self, tmp_vault, mocker):
        """Mock HTTP fetch and verify raw article is created from URL."""
        from oar.ingest.fetcher import URLFetcher

        html = """\
<html>
<head><title>Mocked Article</title></head>
<body><article><p>This is mocked web content.</p></article></body>
</html>"""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.text = html

        # Patch the client's get method on any URLFetcher instance.
        mocker.patch.object(httpx.Client, "get", return_value=mock_resp)

        result = runner.invoke(
            app,
            ["ingest", "--url", "https://example.com/mocked"],
            env={"OAR_VAULT": str(tmp_vault)},
        )
        assert result.exit_code == 0

        articles_dir = tmp_vault / "01-raw" / "articles"
        md_files = [
            f
            for f in articles_dir.iterdir()
            if f.suffix == ".md" and f.name != "_index.md"
        ]
        assert len(md_files) >= 1
        content = md_files[0].read_text()
        assert "Mocked Article" in content or "mocked" in content.lower()
