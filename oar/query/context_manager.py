"""Context manager — builds optimal context windows for Q&A queries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from oar.core.link_graph import LinkGraph
from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps

# Rough token estimation: 1 token ≈ 4 characters for English text
CHARS_PER_TOKEN = 4


@dataclass
class ContextWindow:
    """Assembled context for a query."""

    total_tokens: int = 0
    max_tokens: int = 100000
    sections: list[dict] = field(default_factory=list)  # {source, tokens, content}

    @property
    def remaining_tokens(self) -> int:
        return self.max_tokens - self.total_tokens

    @property
    def utilization(self) -> float:
        return self.total_tokens / self.max_tokens if self.max_tokens > 0 else 0.0

    def add_section(self, source: str, content: str) -> bool:
        """Add a section if it fits. Returns True if added."""
        tokens = self._estimate_tokens(content)
        if self.total_tokens + tokens > self.max_tokens:
            return False
        self.sections.append({"source": source, "tokens": tokens, "content": content})
        self.total_tokens += tokens
        return True

    def add_section_truncated(self, source: str, content: str) -> bool:
        """Add a section, truncating if necessary to fit remaining budget."""
        remaining = self.remaining_tokens
        if remaining <= 0:
            return False
        truncation_suffix = "\n\n[TRUNCATED]"
        max_chars = remaining * CHARS_PER_TOKEN
        if len(content) > max_chars:
            # Account for the suffix length when truncating
            content = (
                content[: max(0, max_chars - len(truncation_suffix))]
                + truncation_suffix
            )
        tokens = self._estimate_tokens(content)
        self.sections.append({"source": source, "tokens": tokens, "content": content})
        self.total_tokens += tokens
        return True

    def render(self) -> str:
        """Render all sections into a single context string."""
        parts = []
        for section in self.sections:
            parts.append(f"--- {section['source']} ---\n\n{section['content']}")
        return "\n\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)


class ContextManager:
    """Build context windows for Q&A queries using progressive context loading.

    Strategy (from ARCHITECTURE.md §9.3):
    Phase 1: Read master index (~3K tokens) → identify relevant MOCs
    Phase 2: Read relevant MOCs (~6K tokens) → identify relevant articles
    Phase 3: Read full text of top articles (~30-50K tokens)
    Phase 4: Add related article summaries (~10K tokens)
    Phase 5: Add raw source excerpts if needed (~5K tokens)
    """

    def __init__(self, vault: Vault, ops: VaultOps, resolver: LinkResolver):
        self.vault = vault
        self.ops = ops
        self.resolver = resolver

    def build_context(self, query: str, max_tokens: int = 100000) -> ContextWindow:
        """Build a context window for a query using progressive loading.

        Steps:
        1. Load master index
        2. Identify relevant MOCs (keyword matching)
        3. Read relevant MOC files
        4. From MOCs, identify top candidate articles
        5. Score candidates by relevance to query
        6. Read full text of top candidates (within budget)
        7. Return assembled ContextWindow
        """
        ctx = ContextWindow(max_tokens=max_tokens)

        # Phase 1: Master index
        master_path = self.vault.indices_dir / "_master-index.md"
        if master_path.exists():
            _, body = self.ops.read_article(master_path)
            ctx.add_section("master-index", body)

        # Phase 2: Find relevant MOCs
        moc_ids = self._find_relevant_mocs(query)
        moc_articles: list[tuple[str, int]] = []  # (article_id, relevance_hint)
        for moc_id in moc_ids:
            moc_path = self.vault.indices_dir / "moc" / f"{moc_id}.md"
            if moc_path.exists():
                _, body = self.ops.read_article(moc_path)
                ctx.add_section(f"moc:{moc_id}", body)
                # Extract [[links]] from MOC body as candidate articles
                links = self.resolver.extract_wikilinks(body)
                for link in links:
                    moc_articles.append((link, 1))  # relevance hint

        # Phase 3: Score and read candidate articles
        candidates = self._score_candidates(query, moc_articles)
        for article_id, score in candidates:
            if ctx.remaining_tokens <= 500:
                break
            path = self.ops.get_article_by_id(article_id)
            if path:
                _, body = self.ops.read_article(path)
                ctx.add_section_truncated(f"article:{article_id}", body)

        return ctx

    def build_context_for_articles(
        self, article_ids: list[str], max_tokens: int = 100000
    ) -> ContextWindow:
        """Build context from specific article IDs (for targeted queries)."""
        ctx = ContextWindow(max_tokens=max_tokens)
        for aid in article_ids:
            path = self.ops.get_article_by_id(aid)
            if path:
                _, body = self.ops.read_article(path)
                ctx.add_section_truncated(f"article:{aid}", body)
        return ctx

    def get_article_summary(self, article_id: str) -> str | None:
        """Get a brief summary of an article (TL;DR + first paragraph)."""
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return None
        _, body = self.ops.read_article(path)
        # Extract content up to first ## heading
        match = re.search(r"^##", body, re.MULTILINE)
        if match:
            return body[: match.start()].strip()
        return body[:500]

    # Words too short to be meaningful for keyword matching
    _stop_words = frozenset(
        {
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
            "how",
            "what",
            "why",
            "does",
        }
    )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Tokenize text into lowercase words, splitting on non-alphanumeric chars."""
        return {w for w in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(w) > 1}

    def _find_relevant_mocs(self, query: str) -> list[str]:
        """Find MOCs relevant to a query using keyword matching."""
        moc_dir = self.vault.indices_dir / "moc"
        if not moc_dir.exists():
            return []

        query_words = self._tokenize(query) - self._stop_words

        scored: list[tuple[int, str]] = []
        for moc_path in moc_dir.glob("moc-*.md"):
            _, body = self.ops.read_article(moc_path)
            body_words = self._tokenize(body)
            overlap = len(query_words & body_words)
            if overlap > 0:
                scored.append((overlap, moc_path.stem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [moc_id for _, moc_id in scored[:3]]

    def _score_candidates(
        self, query: str, moc_articles: list[tuple[str, int]]
    ) -> list[tuple[str, float]]:
        """Score article candidates by relevance to query.

        Factors:
        - Query keyword overlap with title + body
        - MOC appearance (boost)
        - Backlink count (proxy for importance)
        """
        query_words = self._tokenize(query) - self._stop_words

        seen: dict[str, int] = {}
        for article_id, moc_hint in moc_articles:
            if article_id in seen:
                seen[article_id] += moc_hint
            else:
                seen[article_id] = moc_hint

        scored: list[tuple[str, float]] = []
        graph = self.resolver.build_graph()

        for article_id, base_score in seen.items():
            path = self.ops.get_article_by_id(article_id)
            if not path:
                continue

            fm, body = self.ops.read_article(path)
            title = fm.get("title", "")
            title_words = self._tokenize(title)
            body_lower = body[:2000].lower()

            # Score components
            title_overlap = len(query_words & title_words) * 3  # Title matches worth 3x
            body_overlap = sum(1 for w in query_words if w in body_lower)
            backlinks = graph.get_backlink_count(article_id)
            backlink_score = min(backlinks / 10, 1.0)  # Normalize to 0-1

            total = base_score + title_overlap + body_overlap * 0.5 + backlink_score
            scored.append((article_id, total))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
