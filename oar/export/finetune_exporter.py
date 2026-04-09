"""Fine-tuning data exporter — convert wiki content into training-ready JSONL."""

from __future__ import annotations

import json
from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


class FinetuneExporter:
    """Export wiki data for fine-tuning."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops

    def export_qa_pairs(self, output_path: Path) -> int:
        """Export Q&A outputs as training data JSONL.

        Each line: {"messages": [{"role": "user", "content": question},
                                  {"role": "assistant", "content": answer}]}
        Returns count of exported pairs.
        """
        answers_dir = self.vault.path / "04-outputs" / "answers"
        if not answers_dir.exists():
            return 0

        count = 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for answer_path in sorted(answers_dir.glob("*.md")):
                fm, body = self.ops.read_article(answer_path)
                question = fm.get("question", fm.get("title", ""))
                if question and body:
                    entry = {
                        "messages": [
                            {"role": "user", "content": question},
                            {"role": "assistant", "content": body.strip()},
                        ]
                    }
                    f.write(json.dumps(entry) + "\n")
                    count += 1
        return count

    def export_articles_as_summaries(self, output_path: Path) -> int:
        """Export compiled articles as instruction-following data.

        Each line: {"messages": [{"role": "user", "content": "Write an article about X"},
                                  {"role": "assistant", "content": article_body}]}
        Returns count of exported articles.
        """
        count = 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for article_path in self.ops.list_compiled_articles():
                fm, body = self.ops.read_article(article_path)
                title = fm.get("title", article_path.stem)
                if title and body:
                    entry = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"Write an article about {title}",
                            },
                            {"role": "assistant", "content": body.strip()},
                        ]
                    }
                    f.write(json.dumps(entry) + "\n")
                    count += 1
        return count
