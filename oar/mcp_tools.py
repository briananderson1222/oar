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


def _build_vault_only():
    """Build vault components without LLM router. For retrieval-only tools."""
    from oar.core.vault import Vault
    from oar.core.vault_ops import VaultOps

    vault_path = _resolve_vault_path()
    if vault_path is None:
        raise ValueError(
            "No OAR vault found. Set OAR_VAULT or run from a vault directory."
        )

    vault = Vault(vault_path)
    ops = VaultOps(vault)
    return vault, ops


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


def tool_get_wiki_context(
    question: str,
    max_tokens: int = 50000,
) -> dict[str, Any]:
    """Get relevant wiki context for a question. No LLM call — pure retrieval.

    Use this when you (the agent) want to answer a question yourself.
    Returns relevant article content so you can think and respond.
    Does NOT call any LLM — it searches, scores, and assembles context
    using keyword matching and the vault's index structure.

    Args:
        question: The question or topic to find context for
        max_tokens: Approximate token budget for returned context

    Returns:
        Dict with context text, sources list, and token estimate
    """
    from oar.core.link_resolver import LinkResolver
    from oar.query.context_manager import ContextManager

    vault, ops = _build_vault_only()

    link_resolver = LinkResolver(vault, ops)
    context_manager = ContextManager(vault, ops, link_resolver)

    ctx = context_manager.build_context(question, max_tokens=max_tokens)

    sources = [s["source"] for s in ctx.sections]

    return {
        "context": ctx.render(),
        "sources": sources,
        "tokens_estimated": ctx.total_tokens,
        "utilization": round(ctx.utilization, 2),
    }


def tool_query_wiki(
    question: str,
    provider: str | None = None,
    model: str | None = None,
    max_cost: float = 0.50,
) -> dict[str, Any]:
    """Ask a question against the wiki knowledge base.

    Retrieves context from the vault, then calls an LLM to answer.
    Requires an LLM provider to be available.

    Args:
        question: Natural language question
        provider: LLM provider to use (e.g. "claude-cli", "codex-cli", "opencode-cli", "ollama", "litellm"). Uses config default if not specified.
        model: Model name override (e.g. "claude-sonnet-4-20250514"). Uses config default if not specified.
        max_cost: Maximum spend in USD for this query (default 0.50)

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
    from oar.cli._shared import build_router, VALID_PROVIDERS

    vault_path = _resolve_vault_path()
    if vault_path is None:
        raise ValueError("No OAR vault found.")

    # Validate provider if specified.
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider: '{provider}'. "
            f"Valid providers: {sorted(VALID_PROVIDERS)}"
        )

    vault, ops = _build_vault_only()

    # Build router with optional provider/model override.
    router, cost_tracker, config = build_router(
        vault_path, model=model, provider=provider
    )

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


def tool_get_pending_articles() -> list[dict[str, Any]]:
    """Get raw articles that need compiling.

    Returns list of pending articles with id, title, path, and status
    (NEW, UNCOMPILED, or UPDATED).
    """
    from oar.core.hashing import has_content_changed
    from oar.core.slug import slugify
    from oar.core.state import StateManager

    vault, ops, *_ = _build_components()
    state_mgr = StateManager(vault.oar_dir)
    state = state_mgr.load()
    articles_state = state.get("articles", {})

    pending: list[dict[str, Any]] = []
    for path in ops.list_raw_articles():
        meta, body = ops.read_article(path)
        title = meta.get("title", path.stem)

        # Determine article ID: prefer id field, then slugify(title), then slugify(stem).
        article_id = meta.get("id") or slugify(title) or slugify(path.stem)

        word_count = len(body.split())
        entry = articles_state.get(article_id)

        if entry is None:
            # Not tracked in state at all.
            status = "NEW"
        elif not entry.get("compiled", False):
            # Tracked but never compiled.
            status = "UNCOMPILED"
        elif has_content_changed(path, entry.get("content_hash", "")):
            # Was compiled but content has changed since.
            status = "UPDATED"
        else:
            # Already compiled and unchanged — skip.
            continue

        pending.append(
            {
                "article_id": article_id,
                "title": title,
                "path": str(path),
                "status": status,
                "word_count": word_count,
            }
        )

    return pending


def tool_read_raw_article(article_id: str) -> dict[str, Any]:
    """Read a raw (uncompiled) article by ID.

    Returns the article's metadata and full body content.
    """
    vault, ops, *_ = _build_components()
    path = ops.get_article_by_id(article_id)
    if not path:
        return {"error": f"Raw article not found: {article_id}"}

    meta, body = ops.read_article(path)
    return {
        "article_id": article_id,
        "title": meta.get("title", ""),
        "metadata": meta,
        "body": body,
        "path": str(path),
    }


def tool_save_compiled_article(
    title: str,
    body: str,
    article_type: str = "concept",
    tags: list[str] | None = None,
    domain: list[str] | None = None,
    related: list[str] | None = None,
    source_ids: list[str] | None = None,
    status: str = "draft",
    confidence: float = 0.9,
) -> dict[str, Any]:
    """Save a compiled wiki article. Handles frontmatter, file placement, and state.

    The agent provides the title and body content. This tool handles:
    - Generating the article ID (slug from title)
    - Creating proper YAML frontmatter
    - Writing to the correct subdirectory (02-compiled/{type}s/)
    - Updating state.json
    - Computing word count and read time

    Args:
        title: Article title
        body: Full article body in markdown (with [[wikilinks]])
        article_type: concept, method, comparison, entity, tutorial, timeline
        tags: List of tags
        domain: Domain categories (e.g. ["machine-learning", "nlp"]). Derived from tags if not provided.
        related: List of related article IDs (will be wrapped in [[ ]])
        source_ids: Raw article IDs this was compiled from (marks them as compiled)
        status: stub, draft, mature, review
        confidence: 0.0-1.0 confidence score
    """
    from datetime import datetime, timezone

    from oar.core.hashing import content_hash_string
    from oar.core.slug import slugify
    from oar.core.state import StateManager

    vault, ops, *_ = _build_components()

    # Generate ID and filename.
    article_id = slugify(title)
    filename = f"{article_id}.md"

    # Wrap related IDs in wikilinks.
    related_links: list[str] = []
    if related:
        for r in related:
            if not r.startswith("[["):
                related_links.append(f"[[{r}]]")
            else:
                related_links.append(r)

    # Wrap source IDs in wikilinks.
    source_links: list[str] = []
    if source_ids:
        for s in source_ids:
            if not s.startswith("[["):
                source_links.append(f"[[{s}]]")
            else:
                source_links.append(s)

    # Compute word count and read time.
    word_count = len(body.split())
    read_time = max(1, word_count // 200)

    # Derive domain from tags if not provided.
    effective_tags = tags or []
    effective_domain = (
        domain if domain else (effective_tags[:2] if effective_tags else [])
    )

    # Build frontmatter (same pattern as add_note.py).
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "id": article_id,
        "title": title,
        "aliases": [],
        "created": now,
        "updated": now,
        "version": 1,
        "type": article_type,
        "domain": effective_domain,
        "tags": effective_tags,
        "status": status,
        "confidence": confidence,
        "sources": source_links,
        "source_count": len(source_links),
        "related": related_links,
        "word_count": word_count,
        "read_time_min": read_time,
        "backlink_count": 0,
    }

    # Write the compiled article.
    path = ops.write_compiled_article(article_type + "s", filename, metadata, body)

    # Register in state.
    state_mgr = StateManager(vault.oar_dir)
    state_mgr.register_article(
        article_id,
        str(path.relative_to(vault.path)),
        content_hash_string(body),
    )

    # Update compiled count in stats.
    state = state_mgr.load()
    compiled_count = len(ops.list_compiled_articles())
    state.setdefault("stats", {})["compiled_articles"] = compiled_count
    state["stats"]["total_words"] = state["stats"].get("total_words", 0) + word_count
    state_mgr.save(state)

    # Mark source raw articles as compiled.
    if source_ids:
        for raw_id in source_ids:
            state_mgr.mark_compiled(raw_id, [article_id])

    return {
        "article_id": article_id,
        "title": title,
        "path": str(path),
        "word_count": word_count,
    }


def tool_mark_raw_compiled(
    raw_article_id: str,
    compiled_article_id: str,
) -> dict[str, Any]:
    """Mark a raw article as compiled, linked to its compiled output.

    Args:
        raw_article_id: The raw article ID to mark as compiled
        compiled_article_id: The compiled article ID it was compiled into
    """
    from oar.core.state import StateManager

    vault, ops, *_ = _build_components()
    state_mgr = StateManager(vault.oar_dir)
    state_mgr.mark_compiled(raw_article_id, [compiled_article_id])

    return {
        "status": "ok",
        "raw_id": raw_article_id,
        "compiled_id": compiled_article_id,
    }


def tool_build_indices() -> dict[str, Any]:
    """Rebuild all wiki indices: MOCs, tag pages, orphan/stub lists, master index.

    Run after adding or updating articles to keep cross-references current.
    """
    from oar.core.link_resolver import LinkResolver
    from oar.index.moc_builder import MocBuilder
    from oar.index.orphan_tracker import OrphanTracker
    from oar.index.tag_builder import TagBuilder

    vault, ops, *_ = _build_components()

    # Build MOCs.
    moc_builder = MocBuilder(vault, ops)
    mocs = moc_builder.auto_generate_mocs()

    # Build tag pages.
    tag_builder = TagBuilder(vault, ops)
    tag_pages = tag_builder.auto_generate_tags()

    # Build orphan and stub pages.
    link_resolver = LinkResolver(vault, ops)
    orphan_tracker = OrphanTracker(vault, ops, link_resolver)
    orphans = orphan_tracker.write_orphans_page()
    stubs = orphan_tracker.write_stubs_page()
    orphan_tracker.write_recent_page()

    # Build master index.
    moc_list = moc_builder.list_mocs()
    moc_builder.build_master_index(moc_list)

    return {
        "mocs": len(mocs),
        "tags": len(tag_pages),
        "orphans": len(orphans),
        "stubs": len(stubs),
    }


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
    "get_wiki_context": {
        "description": "Get relevant wiki context for a question — pure retrieval, no LLM call. Use this to gather context and answer questions yourself.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question or topic to find context for",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Approximate token budget for context (default 50000)",
                    "default": 50000,
                },
            },
            "required": ["question"],
        },
        "handler": tool_get_wiki_context,
    },
    "query_wiki": {
        "description": "Ask a question — retrieves context then calls a subprocess LLM to answer. Requires an LLM provider (claude-cli, codex-cli, opencode-cli, ollama, or litellm). Prefer get_wiki_context for agent-driven Q&A (no subprocess needed).",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question",
                },
                "provider": {
                    "type": "string",
                    "description": "LLM provider to use. Must be one of: claude-cli, codex-cli, opencode-cli, ollama, litellm. Uses config default if not specified.",
                },
                "model": {
                    "type": "string",
                    "description": "Model name override (e.g. claude-sonnet-4-20250514). Uses config default if not specified.",
                },
                "max_cost": {
                    "type": "number",
                    "description": "Maximum spend in USD for this query",
                    "default": 0.50,
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
    "get_pending_articles": {
        "description": "Get raw articles that need compiling, with their status (NEW, UNCOMPILED, or UPDATED)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_get_pending_articles,
    },
    "read_raw_article": {
        "description": "Read a raw (uncompiled) article by ID, returning metadata and full body",
        "parameters": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "The raw article ID to read",
                },
            },
            "required": ["article_id"],
        },
        "handler": tool_read_raw_article,
    },
    "save_compiled_article": {
        "description": "Save a compiled wiki article. Handles frontmatter, file placement, state tracking, and marking source raw articles as compiled.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Article title",
                },
                "body": {
                    "type": "string",
                    "description": "Full article body in markdown (with [[wikilinks]])",
                },
                "article_type": {
                    "type": "string",
                    "description": "Article type: concept, method, comparison, entity, tutorial, timeline",
                    "default": "concept",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags",
                },
                "domain": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Domain categories (e.g. ['machine-learning', 'nlp']). Derived from tags if not provided.",
                },
                "related": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related article IDs (wrapped in [[ ]] automatically)",
                },
                "source_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Raw article IDs this was compiled from (marks them as compiled)",
                },
                "status": {
                    "type": "string",
                    "description": "Article status: stub, draft, mature, review",
                    "default": "draft",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0",
                    "default": 0.9,
                },
            },
            "required": ["title", "body"],
        },
        "handler": tool_save_compiled_article,
    },
    "mark_raw_compiled": {
        "description": "Mark a raw article as compiled, linked to its compiled output",
        "parameters": {
            "type": "object",
            "properties": {
                "raw_article_id": {
                    "type": "string",
                    "description": "The raw article ID to mark as compiled",
                },
                "compiled_article_id": {
                    "type": "string",
                    "description": "The compiled article ID it was compiled into",
                },
            },
            "required": ["raw_article_id", "compiled_article_id"],
        },
        "handler": tool_mark_raw_compiled,
    },
    "build_indices": {
        "description": "Rebuild all wiki indices: MOCs, tag pages, orphan/stub lists, master index",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_build_indices,
    },
}
