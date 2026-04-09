"""Tests for oar.export.slides — Marp slide generation."""

from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.export.slides import SlideExporter


class TestSlideExporter:
    """SlideExporter.export_article_as_slides() behaviour."""

    def _make_vault_with_article(self, tmp_vault):
        """Create a vault with a compiled article for slide export."""
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
            "# Transformer Architecture\n\n"
            "> TL;DR: A neural network based on self-attention.\n\n"
            "## Overview\n\nThe Transformer architecture revolutionized NLP.\n\n"
            "## Key Components\n\nSelf-attention and feed-forward layers.\n\n"
            "## Applications\n\nMachine translation, text generation.\n",
        )
        return vault, ops

    def test_export_article_as_slides_creates_file(self, tmp_vault):
        vault, ops = self._make_vault_with_article(tmp_vault)
        exporter = SlideExporter(vault, ops)
        output_path = tmp_vault / "slides-output" / "test-slides.md"
        result = exporter.export_article_as_slides(
            "transformer-architecture", output_path
        )
        assert result.exists()

    def test_export_article_has_marp_header(self, tmp_vault):
        vault, ops = self._make_vault_with_article(tmp_vault)
        exporter = SlideExporter(vault, ops)
        output_path = tmp_vault / "slides-output" / "test-slides.md"
        exporter.export_article_as_slides("transformer-architecture", output_path)
        content = output_path.read_text()
        assert "marp: true" in content

    def test_export_article_splits_sections(self, tmp_vault):
        vault, ops = self._make_vault_with_article(tmp_vault)
        exporter = SlideExporter(vault, ops)
        output_path = tmp_vault / "slides-output" / "test-slides.md"
        exporter.export_article_as_slides("transformer-architecture", output_path)
        content = output_path.read_text()
        # Should have multiple slide separators.
        assert content.count("---") >= 2

    def test_export_article_not_found_raises(self, tmp_vault):
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        exporter = SlideExporter(vault, ops)
        try:
            exporter.export_article_as_slides("nonexistent-article")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "not found" in str(e)
