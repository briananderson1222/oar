"""Searcher — full-text search over the vault using SQLite FTS5."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oar.core.vault import Vault
    from oar.core.vault_ops import VaultOps


@dataclass
class SearchResult:
    """A single search result with ranking and context."""

    article_id: str
    title: str
    type: str
    score: float
    snippet: str  # First 200 chars of body with query terms highlighted
    path: str
    tags: list[str] = field(default_factory=list)
    backlink_count: int = 0


class Searcher:
    """Full-text search over the vault using SQLite FTS5.

    Ranking formula (deterministic):

        final_score = bm25_relevance
                      * backlink_boost
                      * title_boost

    where ``bm25_relevance = -bm25(vault_fts)`` (higher is better),
    ``backlink_boost = 1 + min(backlink_count, 10) * 0.02`` (well-connected
    notes get up to a +20% nudge), and ``title_boost`` comes from
    :func:`oar.search.ranker.rank_results` — 1.5x when every query word appears
    in the title, otherwise ``1 + 0.2 * (query∩title word overlap)``.

    When constructed with *vault* and *ops*, :meth:`search` first calls
    :meth:`oar.search.indexer.SearchIndexer.sync` to reconcile the index with
    the vault (cheap stat-compare) so results never go stale between rebuilds.
    """

    def __init__(
        self,
        db_path: Path,
        vault: "Vault | None" = None,
        ops: "VaultOps | None" = None,
    ) -> None:
        self.db_path = db_path
        self._vault = vault
        self._ops = ops
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def search(
        self,
        query: str,
        limit: int = 10,
        type_filter: str | None = None,
        domain_filter: str | None = None,
    ) -> list[SearchResult]:
        """Search the vault. Returns results ranked by the formula documented on
        the class: BM25 relevance, scaled by a backlink boost and a title boost.
        """
        import re

        # Reconcile the index with the vault (add/modify/delete) before querying.
        self._maybe_sync()

        # Build a safe FTS5 MATCH query.
        # Strategy: split query into tokens. Hyphenated words become phrase
        # queries ("fine tuning"), bare words stay as-is. This preserves the
        # intent of hyphenated terms as compound concepts.
        safe_query = query.replace('"', '""')
        # Remove FTS5 special chars that could cause parse errors.
        safe_query = re.sub(r"[*+^#]", " ", safe_query)

        # Split into tokens. Hyphenated groups become FTS5 phrase queries.
        tokens: list[str] = []
        for token in safe_query.split():
            if "-" in token:
                # "fine-tuning" → '"fine tuning"' (FTS5 phrase match).
                phrase = token.replace("-", " ").strip()
                tokens.append(f'"{phrase}"')
            else:
                tokens.append(token)

        safe_query = " ".join(tokens)

        # Use bm25 for ranking (lower = better, so negate for our score).
        if type_filter:
            sql = """
                SELECT
                    fts.article_id,
                    fts.title,
                    fts.body,
                    docs.type,
                    docs.path,
                    docs.backlink_count,
                    -bm25(vault_fts) AS score
                FROM vault_fts fts
                JOIN vault_docs docs ON docs.article_id = fts.article_id
                WHERE vault_fts MATCH ?
                  AND docs.type = ?
                ORDER BY score DESC
                LIMIT ?
            """
            rows = self.conn.execute(sql, (safe_query, type_filter, limit)).fetchall()
        else:
            sql = """
                SELECT
                    fts.article_id,
                    fts.title,
                    fts.body,
                    docs.type,
                    docs.path,
                    docs.backlink_count,
                    -bm25(vault_fts) AS score
                FROM vault_fts fts
                JOIN vault_docs docs ON docs.article_id = fts.article_id
                WHERE vault_fts MATCH ?
                ORDER BY score DESC
                LIMIT ?
            """
            rows = self.conn.execute(sql, (safe_query, limit)).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            body = row["body"] or ""
            # Build snippet: first 200 chars of body.
            snippet = body[:200]

            # Fetch tags for this article.
            tag_rows = self.conn.execute(
                "SELECT tag FROM article_tags WHERE article_id = ?",
                (row["article_id"],),
            ).fetchall()
            tags = [tr["tag"] for tr in tag_rows]

            backlink_count = row["backlink_count"] or 0
            # Backlink boost: well-connected notes get up to +20%.
            score = row["score"] * (1 + min(backlink_count, 10) * 0.02)

            results.append(
                SearchResult(
                    article_id=row["article_id"],
                    title=row["title"],
                    type=row["type"] or "",
                    score=score,
                    snippet=snippet,
                    path=row["path"] or "",
                    tags=tags,
                    backlink_count=backlink_count,
                )
            )

        # Title-boost re-rank on top of BM25 + backlink ordering.
        from oar.search.ranker import rank_results

        return rank_results(results, query)

    def _maybe_sync(self) -> None:
        """Stat-sync the index with the vault when vault/ops were provided."""
        if self._vault is None or self._ops is None:
            return
        from oar.search.indexer import SearchIndexer

        indexer = SearchIndexer(self.db_path)
        try:
            indexer.sync(self._vault, self._ops)
        finally:
            indexer.close()

    def get_article(self, article_id: str) -> dict | None:
        """Get full article metadata by ID."""
        row = self.conn.execute(
            """SELECT article_id, path, title, type, status, word_count,
                      backlink_count, created, updated, content_hash
               FROM vault_docs WHERE article_id = ?""",
            (article_id,),
        ).fetchone()

        if row is None:
            return None

        # Fetch tags.
        tag_rows = self.conn.execute(
            "SELECT tag FROM article_tags WHERE article_id = ?",
            (article_id,),
        ).fetchall()

        return {
            "article_id": row["article_id"],
            "path": row["path"],
            "title": row["title"],
            "type": row["type"],
            "status": row["status"],
            "word_count": row["word_count"],
            "backlink_count": row["backlink_count"],
            "created": row["created"],
            "updated": row["updated"],
            "content_hash": row["content_hash"],
            "tags": [tr["tag"] for tr in tag_rows],
        }

    def get_backlinks(self, article_id: str) -> list[dict]:
        """Get all articles that link to this article (from FTS body search)."""
        # Search for [[article_id]] in all article bodies.
        link_pattern = f'"[[{article_id}]]"'
        sql = """
            SELECT docs.article_id, docs.title, docs.path, docs.type
            FROM vault_fts fts
            JOIN vault_docs docs ON docs.article_id = fts.article_id
            WHERE vault_fts MATCH ?
        """
        rows = self.conn.execute(sql, (link_pattern,)).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict:
        """Get search index statistics."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM vault_docs").fetchone()
        total_docs = row["cnt"] if row else 0

        tag_row = self.conn.execute(
            "SELECT COUNT(DISTINCT tag) as cnt FROM article_tags"
        ).fetchone()
        unique_tags = tag_row["cnt"] if tag_row else 0

        type_rows = self.conn.execute(
            "SELECT type, COUNT(*) as cnt FROM vault_docs GROUP BY type"
        ).fetchall()
        by_type = {r["type"]: r["cnt"] for r in type_rows}

        return {
            "total_documents": total_docs,
            "unique_tags": unique_tags,
            "by_type": by_type,
        }

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
