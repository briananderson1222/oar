"""MCP tool definitions — OAR tools exposed via MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_vault_path() -> Path | None:
    """Find the vault path using the same logic as CLI."""
    import os

    env_path = os.environ.get("OAR_VAULT")
    if env_path:
        p = Path(env_path)
        if (p / ".oar" / "state.json").exists():
            return p
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".oar" / "state.json").exists():
            return parent
    return None


def _build_components():
    """Build vault components for tool execution."""
    from oar.cli._shared import build_router
    from oar.core.vault import Vault
    from oar.core.vault_ops import VaultOps

    vault_path = _resolve_vault_path()
    if vault_path is None:
        raise ValueError(
            "No OAR vault found. Set OAR_VAULT or run from a vault directory."
        )

    vault = Vault(vault_path)
    ops = VaultOps(vault)
    router, cost_tracker, config = build_router(vault_path)
    return vault, ops, router, cost_tracker, config


# ------------------------------------------------------------------
# Tool implementations
# ------------------------------------------------------------------


def tool_search_wiki(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Full-text search over wiki articles.

    Args:
        query: Search query string
        limit: Maximum results to return

    Returns:
        List of search results with title, path, snippet, score
    """
    from oar.search.indexer import SearchIndexer
    from oar.search.searcher import Searcher

    vault, ops, *_ = _build_components()

    # Ensure index exists.
    db_path = vault.oar_dir / "search-index" / "search.db"
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        indexer = SearchIndexer(db_path)
        indexer.index_vault(vault, ops)
        indexer.close()

    searcher = Searcher(db_path)
    results = searcher.search(query, limit=limit)

    return [
        {
            "article_id": r.article_id,
            "title": r.title,
            "path": r.path,
            "snippet": r.snippet,
            "score": r.score,
            "tags": r.tags,
        }
        for r in results
    ]


def tool_read_article(article_id: str) -> dict[str, Any]:
    """Read a compiled wiki article by ID.

    Args:
        article_id: The article ID to read

    Returns:
        Article metadata and body content
    """
    from oar.core.frontmatter import FrontmatterManager

    vault, ops, *_ = _build_components()
    path = ops.get_article_by_id(article_id)
    if not path:
        return {"error": f"Article not found: {article_id}"}

    fm = FrontmatterManager()
    meta, body = fm.read(path)
    return {
        "id": article_id,
        "metadata": meta,
        "body": body,
        "path": str(path),
    }


def tool_list_articles(
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List compiled wiki articles, optionally filtered.

    Args:
        category: Filter by article type (concept, method, comparison, etc.)
        tags: Filter by tags (articles must have ALL specified tags)

    Returns:
        List of article summaries
    """
    from oar.core.frontmatter import FrontmatterManager

    vault, ops, *_ = _build_components()
    fm = FrontmatterManager()

    articles = []
    for path in ops.list_compiled_articles():
        meta, body = fm.read(path)
        aid = meta.get("id", path.stem)

        # Filter by category.
        if category and meta.get("type") != category:
            continue

        # Filter by tags.
        if tags:
            article_tags = set(meta.get("tags", []))
            if not all(t in article_tags for t in tags):
                continue

        articles.append(
            {
                "id": aid,
                "title": meta.get("title", aid),
                "type": meta.get("type", ""),
                "tags": meta.get("tags", []),
                "word_count": meta.get("word_count", 0),
                "path": str(path),
            }
        )

    return articles


def tool_query_wiki(question: str) -> dict[str, Any]:
    """Ask a question against the wiki knowledge base.

    Args:
        question: Natural language question

    Returns:
        Answer with sources consulted and citations
    """
    from oar.core.link_resolver import LinkResolver
    from oar.index.moc_builder import MocBuilder
    from oar.query.context_manager import ContextManager
    from oar.query.engine import QueryEngine
    from oar.query.tools import ToolExecutor
    from oar.search.indexer import SearchIndexer
    from oar.search.searcher import Searcher

    vault, ops, router, cost_tracker, config = _build_components()

    # Ensure search index.
    db_path = vault.oar_dir / "search-index" / "search.db"
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        indexer = SearchIndexer(db_path)
        indexer.index_vault(vault, ops)
        indexer.close()

    link_resolver = LinkResolver(vault, ops)
    moc_builder = MocBuilder(vault, ops)
    context_manager = ContextManager(vault, ops, link_resolver)
    searcher = Searcher(db_path)
    tool_executor = ToolExecutor(vault, ops, searcher, link_resolver, moc_builder)
    engine = QueryEngine(context_manager, tool_executor, router)

    result = engine.query(question)
    return {
        "answer": result.answer,
        "sources_consulted": result.sources_consulted,
        "tool_calls": result.tool_calls,
        "tokens_used": result.tokens_used,
        "cost_usd": result.cost_usd,
    }


def tool_get_status() -> dict[str, Any]:
    """Get vault statistics and status.

    Returns:
        Vault statistics including article counts and last activity
    """
    import json

    vault, ops, *_ = _build_components()
    state_file = vault.oar_dir / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    stats = state.get("stats", {})

    return {
        "vault_path": str(vault.path),
        "raw_articles": stats.get("raw_articles", 0),
        "compiled_articles": stats.get("compiled_articles", 0),
        "total_words": stats.get("total_words", 0),
        "last_compile": state.get("last_compile"),
        "last_lint": state.get("last_lint"),
    }


def tool_list_mocs() -> list[dict[str, Any]]:
    """List all Maps of Content (MOCs) in the wiki.

    Returns:
        List of MOCs with their article counts
    """
    from oar.index.moc_builder import MocBuilder

    vault, ops, *_ = _build_components()
    moc_builder = MocBuilder(vault, ops)
    return moc_builder.list_mocs()


# ------------------------------------------------------------------
# Tool registry
# ------------------------------------------------------------------

TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "search_wiki": {
        "description": "Full-text search over wiki articles",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        "handler": tool_search_wiki,
    },
    "read_article": {
        "description": "Read a compiled wiki article by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "article_id": {"type": "string", "description": "Article ID"},
            },
            "required": ["article_id"],
        },
        "handler": tool_read_article,
    },
    "list_articles": {
        "description": "List compiled wiki articles, optionally filtered by category and tags",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by type (concept, method, etc.)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags",
                },
            },
        },
        "handler": tool_list_articles,
    },
    "query_wiki": {
        "description": "Ask a question against the wiki knowledge base",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question",
                },
            },
            "required": ["question"],
        },
        "handler": tool_query_wiki,
    },
    "get_status": {
        "description": "Get vault statistics and status",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_get_status,
    },
    "list_mocs": {
        "description": "List all Maps of Content in the wiki",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_list_mocs,
    },
}
