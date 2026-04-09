"""Searcher — full-text search over the vault using SQLite FTS5."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


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


class Searcher:
    """Full-text search over the vault using SQLite FTS5."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def search(
        self,
        query: str,
        limit: int = 10,
        type_filter: str | None = None,
        domain_filter: str | None = None,
    ) -> list[SearchResult]:
        """Search the vault. Returns ranked results."""
        import re

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

            results.append(
                SearchResult(
                    article_id=row["article_id"],
                    title=row["title"],
                    type=row["type"] or "",
                    score=row["score"],
                    snippet=snippet,
                    path=row["path"] or "",
                    tags=tags,
                )
            )

        return results

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
