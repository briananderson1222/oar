"""Search indexer — builds and manages SQLite FTS5 search index over vault articles."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps


@dataclass
class SearchDocument:
    """A document ready for indexing into the FTS5 search engine."""

    article_id: str
    title: str
    path: str
    type: str  # concept | entity | method | moc | tag | ...
    body: str
    tags: str = ""  # space-separated
    aliases: str = ""  # space-separated
    mtime: float | None = None  # source file mtime (for staleness sync)
    size: int | None = None  # source file size in bytes (for staleness sync)


class SearchIndexer:
    """Build and manage SQLite FTS5 search index over vault articles."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create FTS5 virtual table and metadata tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS vault_docs (
                id INTEGER PRIMARY KEY,
                article_id TEXT UNIQUE NOT NULL,
                path TEXT NOT NULL,
                title TEXT NOT NULL,
                type TEXT,
                status TEXT,
                word_count INTEGER,
                backlink_count INTEGER DEFAULT 0,
                created TEXT,
                updated TEXT,
                content_hash TEXT,
                mtime REAL,
                size INTEGER
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
                article_id,
                title,
                body,
                tags,
                aliases,
                tokenize='porter unicode61'
            );

            CREATE TABLE IF NOT EXISTS article_tags (
                article_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (article_id, tag)
            );

            CREATE INDEX IF NOT EXISTS idx_vault_docs_type ON vault_docs(type);
            CREATE INDEX IF NOT EXISTS idx_vault_docs_article_id ON vault_docs(article_id);
        """)
        # Migration: add mtime/size columns to pre-existing databases.
        existing_cols = {
            row[1] for row in self.conn.execute("PRAGMA table_info(vault_docs)")
        }
        if "mtime" not in existing_cols:
            self.conn.execute("ALTER TABLE vault_docs ADD COLUMN mtime REAL")
        if "size" not in existing_cols:
            self.conn.execute("ALTER TABLE vault_docs ADD COLUMN size INTEGER")
        self.conn.commit()

    def index_article(self, doc: SearchDocument, metadata: dict | None = None) -> None:
        """Add or update a single article in the search index."""
        meta = metadata or {}

        # Remove existing entry if it exists (for clean upsert).
        existing = self.conn.execute(
            "SELECT id FROM vault_docs WHERE article_id = ?",
            (doc.article_id,),
        ).fetchone()

        if existing:
            # Delete old FTS entry and doc row.
            self.conn.execute(
                "DELETE FROM vault_fts WHERE article_id = ?",
                (doc.article_id,),
            )
            self.conn.execute(
                "DELETE FROM vault_docs WHERE article_id = ?",
                (doc.article_id,),
            )
            self.conn.execute(
                "DELETE FROM article_tags WHERE article_id = ?",
                (doc.article_id,),
            )

        # Insert into vault_docs.
        self.conn.execute(
            """INSERT INTO vault_docs
               (article_id, path, title, type, status, word_count, backlink_count,
                created, updated, content_hash, mtime, size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc.article_id,
                doc.path,
                doc.title,
                doc.type,
                meta.get("status"),
                meta.get("word_count", len(doc.body.split())),
                meta.get("backlink_count", 0),
                meta.get("created"),
                meta.get("updated"),
                meta.get("content_hash"),
                doc.mtime,
                doc.size,
            ),
        )

        # Insert into FTS.
        self.conn.execute(
            """INSERT INTO vault_fts (article_id, title, body, tags, aliases)
               VALUES (?, ?, ?, ?, ?)""",
            (doc.article_id, doc.title, doc.body, doc.tags, doc.aliases),
        )

        # Insert tags.
        if doc.tags:
            for tag in doc.tags.split():
                self.conn.execute(
                    "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
                    (doc.article_id, tag),
                )

        self.conn.commit()

    def index_vault(self, vault: Vault, ops: VaultOps) -> int:
        """Index all articles in the vault. Returns count of indexed articles."""
        # Clear existing index.
        self.conn.execute("DELETE FROM vault_fts")
        self.conn.execute("DELETE FROM vault_docs")
        self.conn.execute("DELETE FROM article_tags")
        self.conn.commit()

        count = 0
        for path in ops.list_compiled_articles():
            meta, body = ops.read_article(path)
            doc = self._build_doc(vault, path, meta, body)
            self.index_article(doc, metadata=meta)
            count += 1

        return count

    @staticmethod
    def _build_doc(vault: Vault, path: Path, meta: dict, body: str) -> SearchDocument:
        """Build a :class:`SearchDocument` from a vault article path + metadata."""
        article_id = meta.get("id", path.stem)
        title = meta.get("title", path.stem)
        article_type = meta.get("type", "concept")
        tags_list = meta.get("tags", [])
        aliases_list = meta.get("aliases", [])

        try:
            rel_path = str(path.relative_to(vault.path))
        except ValueError:
            rel_path = str(path)

        try:
            st = path.stat()
            mtime: float | None = st.st_mtime
            size: int | None = st.st_size
        except OSError:
            mtime = None
            size = None

        return SearchDocument(
            article_id=article_id,
            title=title,
            path=rel_path,
            type=article_type,
            body=body,
            tags=" ".join(tags_list)
            if isinstance(tags_list, list)
            else str(tags_list),
            aliases=" ".join(aliases_list)
            if isinstance(aliases_list, list)
            else str(aliases_list),
            mtime=mtime,
            size=size,
        )

    def sync(self, vault: Vault, ops: VaultOps) -> dict[str, int]:
        """Incrementally reconcile the index with the vault via stat comparison.

        Compares each compiled article's ``(mtime, size)`` against the stored
        values. Unchanged docs are skipped without reading the file; new and
        changed docs are (re)indexed; docs whose backing file has disappeared are
        removed. Cheap enough to run before every query at hundreds of docs.

        Returns a dict of counts: ``added``, ``updated``, ``removed``,
        ``unchanged``.
        """
        rows = self.conn.execute(
            "SELECT article_id, path, mtime, size FROM vault_docs"
        ).fetchall()
        by_path = {row["path"]: row for row in rows}

        seen_paths: set[str] = set()
        added = updated = unchanged = 0

        for path in ops.list_compiled_articles():
            try:
                st = path.stat()
            except OSError:
                continue
            try:
                rel_path = str(path.relative_to(vault.path))
            except ValueError:
                rel_path = str(path)
            seen_paths.add(rel_path)

            existing = by_path.get(rel_path)
            if (
                existing is not None
                and existing["mtime"] == st.st_mtime
                and existing["size"] == st.st_size
            ):
                unchanged += 1
                continue

            # New or changed → read + (re)index (upsert keyed by article_id).
            meta, body = ops.read_article(path)
            doc = self._build_doc(vault, path, meta, body)
            self.index_article(doc, metadata=meta)
            if existing is None:
                added += 1
            else:
                updated += 1

        # Deletions: index rows whose backing file is gone.
        removed = 0
        for rel_path, row in by_path.items():
            if rel_path not in seen_paths:
                self.remove_article(row["article_id"])
                removed += 1

        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "unchanged": unchanged,
        }

    def remove_article(self, article_id: str) -> None:
        """Remove an article from the index."""
        self.conn.execute(
            "DELETE FROM vault_fts WHERE article_id = ?",
            (article_id,),
        )
        self.conn.execute(
            "DELETE FROM vault_docs WHERE article_id = ?",
            (article_id,),
        )
        self.conn.execute(
            "DELETE FROM article_tags WHERE article_id = ?",
            (article_id,),
        )
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
