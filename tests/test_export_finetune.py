"""Tests for oar.export.finetune_exporter — fine-tuning data export."""

import json
from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.export.finetune_exporter import FinetuneExporter


class TestFinetuneExporterQA:
    """FinetuneExporter.export_qa_pairs() behaviour."""

    def test_export_qa_pairs_empty(self, tmp_vault):
        """Returns 0 when no answers directory exists."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        exporter = FinetuneExporter(vault, ops)
        output_path = tmp_vault / "qa-output.jsonl"
        count = exporter.export_qa_pairs(output_path)
        assert count == 0

    def test_export_qa_pairs_creates_jsonl(self, tmp_vault):
        """Creates a valid JSONL file from answer files."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        # Create answer files.
        answers_dir = tmp_vault / "04-outputs" / "answers"
        answers_dir.mkdir(parents=True, exist_ok=True)
        ops.fm.write(
            answers_dir / "answer-1.md",
            {"question": "What is attention?", "title": "Attention Answer"},
            "Attention is a mechanism that allows models to focus on input.",
        )
        ops.fm.write(
            answers_dir / "answer-2.md",
            {"question": "What is a transformer?", "title": "Transformer Answer"},
            "A transformer is a neural network based on self-attention.",
        )
        exporter = FinetuneExporter(vault, ops)
        output_path = tmp_vault / "qa-output.jsonl"
        count = exporter.export_qa_pairs(output_path)
        assert count == 2
        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_export_qa_pairs_correct_format(self, tmp_vault):
        """Each JSONL line has the expected messages array format."""
        vault = Vault(tmp_vault)
        ops = VaultOps(vault)
        answers_dir = tmp_vault / "04-outputs" / "answers"
        answers_dir.mkdir(parents=True, exist_ok=True)
        ops.fm.write(
            answers_dir / "answer-1.md",
            {"question": "What is RL?", "title": "RL Answer"},
            "RL is reinforcement learning.",
        )
        exporter = FinetuneExporter(vault, ops)
        output_path = tmp_vault / "qa-output.jsonl"
        exporter.export_qa_pairs(output_path)
        lines = output_path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert "messages" in entry
        assert len(entry["messages"]) == 2
        assert entry["messages"][0]["role"] == "user"
        assert entry["messages"][0]["content"] == "What is RL?"
        assert entry["messages"][1]["role"] == "assistant"
        assert "reinforcement learning" in entry["messages"][1]["content"]


class TestFinetuneExporterSummaries:
    """FinetuneExporter.export_articles_as_summaries() behaviour."""

    def test_export_articles_as_summaries(self, tmp_vault):
        """Exports compiled articles as instruction-following JSONL."""
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
            },
            "Attention is a mechanism that lets models focus on input.",
        )
        ops.write_compiled_article(
            "methods",
            "fine-tuning.md",
            {
                "id": "fine-tuning",
                "title": "Fine-Tuning Methods",
                "type": "method",
                "status": "mature",
            },
            "Fine-tuning adapts pre-trained models to specific tasks.",
        )
        exporter = FinetuneExporter(vault, ops)
        output_path = tmp_vault / "summaries.jsonl"
        count = exporter.export_articles_as_summaries(output_path)
        assert count == 2
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert "messages" in entry
        assert entry["messages"][0]["role"] == "user"
        assert "Attention Mechanism" in entry["messages"][0]["content"]
        assert entry["messages"][1]["role"] == "assistant"
