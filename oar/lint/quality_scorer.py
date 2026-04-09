"""Quality scorer — score wiki articles on completeness and depth."""

from __future__ import annotations

import re
from dataclasses import dataclass

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class QualityReport:
    """Quality assessment for a single article."""

    article_id: str
    score: float  # 0.0 to 1.0
    factors: dict[str, float]  # Individual factor scores


class QualityScorer:
    """Score wiki articles on quality dimensions."""

    # Weights for each factor.
    WEIGHTS = {
        "frontmatter": 0.25,
        "content_depth": 0.25,
        "links": 0.20,
        "tags": 0.15,
        "structure": 0.15,
    }

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops
        self.fm = FrontmatterManager()

    def score_article(self, article_id: str) -> QualityReport:
        """Score a single article. Returns a QualityReport."""
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return QualityReport(article_id=article_id, score=0.0, factors={})

        meta, body = self.fm.read(path)

        factors = {
            "frontmatter": self._score_frontmatter(meta),
            "content_depth": self._score_content_depth(body),
            "links": self._score_links(body),
            "tags": self._score_tags(meta),
            "structure": self._score_structure(body),
        }

        total = sum(factors[key] * self.WEIGHTS[key] for key in self.WEIGHTS)

        return QualityReport(
            article_id=article_id,
            score=round(total, 2),
            factors=factors,
        )

    def score_all(self) -> list[QualityReport]:
        """Score all compiled articles."""
        reports: list[QualityReport] = []
        for path in self.ops.list_compiled_articles():
            meta, _ = self.fm.read(path)
            aid = meta.get("id", path.stem)
            reports.append(self.score_article(aid))
        return reports

    # ------------------------------------------------------------------
    # Factor scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _score_frontmatter(meta: dict) -> float:
        """Score based on frontmatter completeness."""
        important_fields = ["id", "title", "type", "status", "tags", "domain"]
        extra_fields = ["confidence", "complexity", "related", "aliases"]
        present = sum(1 for f in important_fields if f in meta and meta[f])
        extra = sum(1 for f in extra_fields if f in meta and meta[f])
        # Important fields are worth more.
        base_score = present / len(important_fields)
        bonus = min(extra / len(extra_fields), 1.0) * 0.3
        return min(base_score + bonus, 1.0)

    @staticmethod
    def _score_content_depth(body: str) -> float:
        """Score based on word count and depth."""
        words = len(body.split())
        if words < 50:
            return words / 50 * 0.3
        elif words < 200:
            return 0.3 + (words - 50) / 150 * 0.4
        elif words < 500:
            return 0.7 + min((words - 200) / 300, 1.0) * 0.2
        else:
            return min(0.9 + words / 5000, 1.0)

    @staticmethod
    def _score_links(body: str) -> float:
        """Score based on outbound wikilinks."""
        links = re.findall(r"\[\[([^\]|]+)", body)
        if len(links) == 0:
            return 0.0
        elif len(links) <= 2:
            return 0.4
        elif len(links) <= 5:
            return 0.7
        else:
            return min(0.7 + len(links) * 0.03, 1.0)

    @staticmethod
    def _score_tags(meta: dict) -> float:
        """Score based on tag presence and count."""
        tags = meta.get("tags", [])
        if not tags:
            return 0.0
        elif len(tags) == 1:
            return 0.4
        elif len(tags) <= 3:
            return 0.7
        else:
            return min(0.7 + len(tags) * 0.05, 1.0)

    @staticmethod
    def _score_structure(body: str) -> float:
        """Score based on heading structure."""
        headings = re.findall(r"^#{1,3}\s+.+", body, re.MULTILINE)
        if not headings:
            return 0.1
        # Good structure has an H1 or title, plus several H2 sections.
        h2_count = sum(
            1 for h in headings if h.startswith("## ") and not h.startswith("### ")
        )
        if h2_count >= 3:
            return min(0.6 + h2_count * 0.05, 1.0)
        elif h2_count >= 1:
            return 0.4
        else:
            return 0.2
