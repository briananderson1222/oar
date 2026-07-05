"""Context builder — assemble LLM context from raw and compiled articles."""

from __future__ import annotations

from pathlib import Path
import re

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


class CompileContextBuilder:
    """Build LLM context from raw and compiled articles for compilation."""

    def __init__(self, vault: Vault, ops: VaultOps) -> None:
        self.vault = vault
        self.ops = ops

    def build_single_context(
        self,
        raw_path: Path,
        *,
        strategy: str = "default",
        max_chars: int = 32000,
    ) -> str:
        """Build context for compiling a single raw article.

        Returns a context string appropriate for the selected strategy.
        """
        _, body = self.ops.read_article(raw_path)
        if strategy == "transcript_excerpt":
            return self._build_transcript_context(body, max_chars=max_chars)
        if len(body) > max_chars:
            return body[:max_chars] + "\n\n[TRUNCATED]"
        return body

    def build_multi_context(
        self, raw_articles: list[Path], max_tokens: int = 50000
    ) -> str:
        """Build context from multiple raw articles for merging.

        Concatenates articles with headers, respecting token limit.
        Rough estimate: 1 token ≈ 4 characters.
        """
        parts: list[str] = []
        total_chars = 0
        max_chars = max_tokens * 4

        for path in raw_articles:
            fm, body = self.ops.read_article(path)
            title = fm.get("title", path.stem)
            section = f"## Source: {title}\n\n{body}\n\n---\n\n"

            if total_chars + len(section) > max_chars:
                # Truncate this section to fit.
                remaining = max_chars - total_chars
                if remaining > 200:
                    section = section[:remaining] + "\n\n[TRUNCATED]"
                    parts.append(section)
                break

            parts.append(section)
            total_chars += len(section)

        return "".join(parts)

    def find_related_raw_articles(
        self, article_id: str, max_articles: int = 5
    ) -> list[Path]:
        """Find raw articles that might be related based on title/content overlap.

        Simple heuristic: check for common words in titles.
        Returns up to *max_articles* paths.
        """
        source_path = self.ops.get_article_by_id(article_id)
        if not source_path:
            return []

        fm, _ = self.ops.read_article(source_path)
        title_words = set(fm.get("title", "").lower().split())
        # Remove common stop words.
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "in",
            "for",
            "to",
            "is",
            "on",
            "with",
        }
        title_words -= stop_words

        if not title_words:
            return []

        candidates: list[tuple[int, Path]] = []
        for raw_path in self.ops.list_raw_articles():
            if raw_path == source_path:
                continue
            other_fm, _ = self.ops.read_article(raw_path)
            other_title_words = (
                set(other_fm.get("title", "").lower().split()) - stop_words
            )
            overlap = len(title_words & other_title_words)
            if overlap > 0:
                candidates.append((overlap, raw_path))

        # Sort by overlap count descending.
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [path for _, path in candidates[:max_articles]]

    def build_existing_context(self, compiled_id: str) -> str | None:
        """Get existing compiled article content for update/diff operations."""
        path = self.ops.get_article_by_id(compiled_id)
        if not path:
            return None
        _, body = self.ops.read_article(path)
        return body

    @staticmethod
    def _normalize_transcript_line(line: str) -> str:
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        return line

    def _build_transcript_context(self, body: str, *, max_chars: int) -> str:
        """Reduce a transcript into representative excerpts for compile."""
        cleaned_lines: list[str] = []
        prev = None
        for raw_line in body.splitlines():
            line = self._normalize_transcript_line(raw_line)
            if not line:
                continue
            if re.fullmatch(r"Kind:\s+captions", line, re.IGNORECASE):
                continue
            if re.fullmatch(r"Language:\s+\w[\w-]*", line, re.IGNORECASE):
                continue
            if prev == line:
                continue
            prev = line
            cleaned_lines.append(line)

        if not cleaned_lines:
            return body[:max_chars] + ("\n\n[TRUNCATED]" if len(body) > max_chars else "")

        total_chars = sum(len(line) + 1 for line in cleaned_lines)
        if total_chars <= max_chars:
            return "\n".join(cleaned_lines)

        segment_count = 5
        window_size = max(20, len(cleaned_lines) // 20)
        starts = []
        if len(cleaned_lines) <= window_size * segment_count:
            starts = list(range(0, len(cleaned_lines), window_size))
        else:
            max_start = max(0, len(cleaned_lines) - window_size)
            starts = sorted(
                {
                    int(round(i * max_start / max(1, segment_count - 1)))
                    for i in range(segment_count)
                }
            )

        excerpts: list[str] = []
        for idx, start in enumerate(starts, start=1):
            chunk = cleaned_lines[start : start + window_size]
            if not chunk:
                continue
            excerpts.append(f"## Excerpt {idx}\n" + "\n".join(chunk))

        result = "\n\n".join(excerpts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n\n[TRUNCATED]"
        return result
