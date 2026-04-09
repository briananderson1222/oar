"""OutputFiler — save Q&A outputs to the vault and update backlinks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.slug import slugify
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.query.engine import QueryResult


@dataclass
class FiledOutput:
    """Metadata about a filed output."""

    path: Path
    article_id: str
    cited_articles: list[str]
    filed_into: list[str]  # Articles where this output was referenced


class OutputFiler:
    """Save Q&A outputs to the vault and update backlinks."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops
        self.fm = FrontmatterManager()

    def file_answer(self, question: str, result: QueryResult) -> FiledOutput:
        """Save a Q&A answer to 04-outputs/answers/ and update cited articles.

        Steps:
        1. Generate article_id: YYYY-MM-DD-{slug}
        2. Write file to 04-outputs/answers/{article_id}.md with frontmatter
        3. For each cited article, add this answer to its ``see_also`` field
        4. Return FiledOutput with path and metadata
        """
        # Generate ID
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        slug = slugify(question)
        article_id = f"{date_str}-{slug}"[:80]

        # Build frontmatter
        metadata = {
            "id": article_id,
            "title": question[:200],
            "type": "answer",
            "question": question,
            "asked": now.isoformat(),
            "sources_consulted": result.sources_consulted,
            "tool_calls": result.tool_calls,
            "tokens_used": result.tokens_used,
            "cost_usd": round(result.cost_usd, 4),
            "word_count": self.ops.compute_word_count(result.answer),
        }

        # Write to 04-outputs/answers/
        answers_dir = self.vault.path / "04-outputs" / "answers"
        answers_dir.mkdir(parents=True, exist_ok=True)
        output_path = answers_dir / f"{article_id}.md"
        self.fm.write(output_path, metadata, result.answer)

        # Update cited articles
        filed_into: list[str] = []
        for cited_id in result.sources_consulted:
            if self._add_reference_to_article(cited_id, article_id):
                filed_into.append(cited_id)

        return FiledOutput(
            path=output_path,
            article_id=article_id,
            cited_articles=result.sources_consulted,
            filed_into=filed_into,
        )

    def file_report(
        self, title: str, content: str, sources: list[str] | None = None
    ) -> FiledOutput:
        """Save a longer report to 04-outputs/reports/."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        slug = slugify(title)
        article_id = f"{date_str}-{slug}"[:80]

        metadata = {
            "id": article_id,
            "title": title,
            "type": "report",
            "created": now.isoformat(),
            "sources_consulted": sources or [],
            "word_count": self.ops.compute_word_count(content),
        }

        reports_dir = self.vault.path / "04-outputs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"{article_id}.md"
        self.fm.write(output_path, metadata, content)

        return FiledOutput(
            path=output_path,
            article_id=article_id,
            cited_articles=sources or [],
            filed_into=[],
        )

    def _add_reference_to_article(self, article_id: str, output_id: str) -> bool:
        """Add a reference to a Q&A output in a compiled article's frontmatter.

        Updates the ``see_also`` field to include a wikilink to the output.
        """
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return False

        try:
            fm, body = self.fm.read(path)
            see_also = fm.get("see_also", [])
            # Ensure it's a list
            if not isinstance(see_also, list):
                see_also = [see_also] if see_also else []
            new_link = f"[[{output_id}]]"
            if new_link not in see_also:
                see_also.append(new_link)
                self.fm.update_metadata(path, {"see_also": see_also})
            return True
        except Exception:
            return False
