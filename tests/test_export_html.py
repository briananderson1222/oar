"""Tests for oar.export.html_exporter — HTML static site export."""

from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.export.html_exporter import HTMLExporter


class TestHTMLExporter:
    """HTMLExporter.export() behaviour."""

    def _make_vault_with_articles(self, tmp_vault):
        """Create a vault with compiled articles for export."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        ops.write_compiled_article(
            "concepts",
            "transformer-architecture.md",
            {
                "id": "transformer-architecture",
                "title": "Transformer Architecture",
                "type": "concept",
                "status": "draft",
                "tags": ["transformer", "attention"],
            },
            "# Transformer Architecture\n\nThe Transformer is a neural network architecture.\n\n## Overview\n\nIt uses self-attention.\n",
        )
        ops.write_compiled_article(
            "methods",
            "fine-tuning.md",
            {
                "id": "fine-tuning",
                "title": "Fine-Tuning",
                "type": "method",
                "status": "mature",
                "tags": ["training"],
            },
            "# Fine-Tuning\n\nFine-tuning adapts a pre-trained model.\n",
        )
        return vault, ops

    def test_export_creates_output_dir(self, tmp_vault):
        vault, ops = self._make_vault_with_articles(tmp_vault)
        exporter = HTMLExporter(vault, ops)
        output_dir = tmp_vault / "html-output"
        exporter.export(output_dir)
        assert output_dir.is_dir()

    def test_export_creates_html_files(self, tmp_vault):
        vault, ops = self._make_vault_with_articles(tmp_vault)
        exporter = HTMLExporter(vault, ops)
        output_dir = tmp_vault / "html-output"
        count = exporter.export(output_dir)
        assert count == 2
        # Check that HTML files exist.
        html_files = list(output_dir.rglob("*.html"))
        stems = {f.stem for f in html_files}
        assert "transformer-architecture" in stems
        assert "fine-tuning" in stems

    def test_export_creates_index(self, tmp_vault):
        vault, ops = self._make_vault_with_articles(tmp_vault)
        exporter = HTMLExporter(vault, ops)
        output_dir = tmp_vault / "html-output"
        exporter.export(output_dir)
        assert (output_dir / "index.html").exists()

    def test_export_returns_count(self, tmp_vault):
        vault, ops = self._make_vault_with_articles(tmp_vault)
        exporter = HTMLExporter(vault, ops)
        output_dir = tmp_vault / "html-output"
        count = exporter.export(output_dir)
        assert count == 2

    def test_export_empty_vault(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        exporter = HTMLExporter(vault, ops)
        output_dir = tmp_vault / "html-output"
        count = exporter.export(output_dir)
        assert count == 0
        # Should still create index.
        assert (output_dir / "index.html").exists()
