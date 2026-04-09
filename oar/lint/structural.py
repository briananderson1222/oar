"""Structural lint checks — non-LLM checks on wiki article structure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from oar.core.frontmatter import FrontmatterManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class LintIssue:
    """A single lint finding."""

    severity: str  # "error" | "warning" | "info"
    category: str  # "missing-field", "broken-link", "orphan", "stub", "inconsistent", "connection"
    article_id: str
    message: str
    suggestion: str = ""


class StructuralChecker:
    """Non-LLM structural checks on wiki articles."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops
        self.fm = FrontmatterManager()

    def check_all(self) -> list[LintIssue]:
        """Run all structural checks."""
        issues: list[LintIssue] = []
        issues.extend(self.check_missing_frontmatter())
        issues.extend(self.check_required_fields())
        issues.extend(self.check_empty_sections())
        issues.extend(self.check_word_counts())
        return issues

    def check_missing_frontmatter(self) -> list[LintIssue]:
        """Find .md files without valid YAML frontmatter."""
        issues: list[LintIssue] = []
        all_paths = self.ops.list_raw_articles() + self.ops.list_compiled_articles()
        for path in all_paths:
            meta, body = self.fm.read(path)
            if not meta:
                article_id = path.stem
                issues.append(
                    LintIssue(
                        severity="error",
                        category="missing-field",
                        article_id=article_id,
                        message=f"Article {path.name} has no YAML frontmatter",
                        suggestion="Add frontmatter with at least id and title",
                    )
                )
        return issues

    def check_required_fields(self) -> list[LintIssue]:
        """Verify all compiled articles have required frontmatter fields."""
        required = ("id", "title", "type", "status")
        issues: list[LintIssue] = []
        for path in self.ops.list_compiled_articles():
            meta, _ = self.fm.read(path)
            article_id = meta.get("id", path.stem)
            for field in required:
                if field not in meta:
                    issues.append(
                        LintIssue(
                            severity="error",
                            category="missing-field",
                            article_id=article_id,
                            message=f"Missing required field: {field}",
                            suggestion=f"Add '{field}' to frontmatter",
                        )
                    )
        return issues

    def check_empty_sections(self) -> list[LintIssue]:
        """Find articles with empty sections (## heading with no content)."""
        heading_pattern = re.compile(r"^##\s+.+", re.MULTILINE)
        issues: list[LintIssue] = []
        all_paths = self.ops.list_raw_articles() + self.ops.list_compiled_articles()
        for path in all_paths:
            meta, body = self.fm.read(path)
            article_id = meta.get("id", path.stem)
            empty_count = 0
            for m in heading_pattern.finditer(body):
                start = m.end()
                next_heading = heading_pattern.search(body, start)
                section_content = (
                    body[start : next_heading.start()] if next_heading else body[start:]
                )
                if not section_content.strip():
                    empty_count += 1
            if empty_count:
                issues.append(
                    LintIssue(
                        severity="warning",
                        category="stub",
                        article_id=article_id,
                        message=f"Article has {empty_count} empty section(s)",
                        suggestion="Add content under empty headings or remove them",
                    )
                )
        return issues

    def check_word_counts(self) -> list[LintIssue]:
        """Verify frontmatter word_count matches actual body word count."""
        issues: list[LintIssue] = []
        all_paths = self.ops.list_raw_articles() + self.ops.list_compiled_articles()
        for path in all_paths:
            meta, body = self.fm.read(path)
            if "word_count" not in meta:
                continue
            article_id = meta.get("id", path.stem)
            declared = meta["word_count"]
            actual = self.ops.compute_word_count(body)
            if declared != actual:
                issues.append(
                    LintIssue(
                        severity="warning",
                        category="inconsistent",
                        article_id=article_id,
                        message=(
                            f"Word count mismatch: frontmatter says {declared}, "
                            f"actual is {actual}"
                        ),
                        suggestion=f"Update word_count to {actual}",
                    )
                )
        return issues
