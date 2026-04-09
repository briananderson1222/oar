"""Coverage analyzer — detect concept gaps in the wiki."""

from __future__ import annotations

import re
from dataclasses import dataclass

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class ConceptGap:
    """A concept that's mentioned but doesn't have its own article."""

    concept: str  # The wikilink target
    mentioned_in: list[str]  # Article IDs that reference it
    frequency: int  # How many times it's mentioned


class CoverageAnalyzer:
    """Analyze wiki coverage — find concepts mentioned but not defined."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops
        self.fm = FrontmatterManager()

    def find_concept_gaps(self) -> list[ConceptGap]:
        """Find wikilink targets that don't resolve to existing articles.

        Scans all compiled articles for [[wikilinks]], then checks which
        targets don't have a corresponding compiled article.
        """
        # Build set of existing article IDs.
        existing_ids: set[str] = set()
        for path in self.ops.list_compiled_articles():
            meta, _ = self.fm.read(path)
            aid = meta.get("id", "")
            if aid:
                existing_ids.add(aid)
            # Also add aliases.
            for alias in meta.get("aliases", []):
                existing_ids.add(alias)

        # Scan for wikilinks.
        wikilink_pattern = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]")
        link_counts: dict[str, list[str]] = {}  # target → [source_ids]

        for path in self.ops.list_compiled_articles():
            meta, body = self.fm.read(path)
            source_id = meta.get("id", path.stem)
            for match in wikilink_pattern.finditer(body):
                target = match.group(1).strip()
                if target not in existing_ids:
                    link_counts.setdefault(target, []).append(source_id)

        # Build ConceptGap list sorted by frequency.
        gaps: list[ConceptGap] = []
        for concept, sources in sorted(
            link_counts.items(), key=lambda x: len(x[1]), reverse=True
        ):
            # Deduplicate sources.
            unique_sources = list(dict.fromkeys(sources))
            gaps.append(
                ConceptGap(
                    concept=concept,
                    mentioned_in=unique_sources,
                    frequency=len(sources),
                )
            )
        return gaps

    def coverage_score(self) -> float:
        """Return 0.0-1.0 score of concept coverage.

        (resolved links) / (total links)
        """
        wikilink_pattern = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]")
        existing_ids: set[str] = set()
        for path in self.ops.list_compiled_articles():
            meta, _ = self.fm.read(path)
            aid = meta.get("id", "")
            if aid:
                existing_ids.add(aid)
            for alias in meta.get("aliases", []):
                existing_ids.add(alias)

        total = 0
        resolved = 0
        for path in self.ops.list_compiled_articles():
            _, body = self.fm.read(path)
            for match in wikilink_pattern.finditer(body):
                target = match.group(1).strip()
                total += 1
                if target in existing_ids:
                    resolved += 1

        if total == 0:
            return 1.0
        return resolved / total
