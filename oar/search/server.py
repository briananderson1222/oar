"""Search server — lightweight FastAPI web UI for searching and browsing the wiki."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.search.indexer import SearchIndexer
from oar.search.searcher import Searcher

app = FastAPI(title="OAR Search", version="0.1.0")

# Global state (set by create_app)
_vault: Vault | None = None
_ops: VaultOps | None = None
_db_path: Path | None = None


def create_app(vault_path: str) -> FastAPI:
    """Create and configure the FastAPI app."""
    global _vault, _ops, _db_path

    _vault = Vault(Path(vault_path))
    _ops = VaultOps(_vault)

    _db_path = _vault.oar_dir / "search-index" / "search.db"
    if not _db_path.exists():
        # Build index on first run
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        indexer = SearchIndexer(_db_path)
        indexer.index_vault(_vault, _ops)
        indexer.close()

    return app


def _get_searcher() -> Searcher:
    """Create a new Searcher for the current thread.

    SQLite connections are thread-local, so we create one per request
    to avoid 'created in a different thread' errors.
    """
    return Searcher(_db_path)


@app.get("/", response_class=HTMLResponse)
async def search_page(q: str = Query(default="", description="Search query")):
    """Serve the search UI."""
    html = SEARCH_HTML_TEMPLATE.replace("{{QUERY}}", q)
    if q:
        searcher = _get_searcher()
        results = searcher.search(q, limit=20)
        searcher.close()
        results_html = _render_results(results, q)
        html = html.replace("{{RESULTS}}", results_html)
    else:
        html = html.replace("{{RESULTS}}", "")
    return html


@app.get("/api/search")
async def api_search(q: str, limit: int = 10, type: str = None):
    """JSON search API."""
    searcher = _get_searcher()
    results = searcher.search(q, limit=limit, type_filter=type)
    searcher.close()
    return {
        "results": [
            {
                "id": r.article_id,
                "title": r.title,
                "type": r.type,
                "score": r.score,
                "snippet": r.snippet,
                "tags": r.tags,
            }
            for r in results
        ]
    }


@app.get("/api/article/{article_id}")
async def api_article(article_id: str):
    """Get full article content."""
    path = _ops.get_article_by_id(article_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")
    fm, body = _ops.read_article(path)
    return {"id": article_id, "frontmatter": fm, "body": body}


@app.get("/api/stats")
async def api_stats():
    """Get vault statistics."""
    searcher = _get_searcher()
    stats = searcher.get_stats()
    searcher.close()
    return stats


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

SEARCH_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
    <title>OAR Wiki Search</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; background: #1a1a2e; color: #e0e0e0; }
        h1 { margin-bottom: 1rem; color: #64b5f6; }
        .search-box { width: 100%; padding: 12px 16px; font-size: 1.1rem; border: 2px solid #3a3a5c; border-radius: 8px; background: #2a2a4a; color: #e0e0e0; margin-bottom: 2rem; }
        .search-box:focus { outline: none; border-color: #64b5f6; }
        .result { padding: 1rem; margin-bottom: 1rem; background: #2a2a4a; border-radius: 8px; }
        .result h3 { color: #64b5f6; margin-bottom: 0.5rem; }
        .result .meta { color: #888; font-size: 0.85rem; margin-bottom: 0.5rem; }
        .result .snippet { color: #ccc; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; }
        .badge-concept { background: #4a148c; }
        .badge-entity { background: #1b5e20; }
        .badge-method { background: #e65100; }
        .badge-comparison { background: #0d47a1; }
        mark { background: #ffd54f; color: #000; padding: 0 2px; border-radius: 2px; }
    </style>
</head>
<body>
    <h1>OAR Wiki Search</h1>
    <form method="get" action="/">
        <input class="search-box" type="text" name="q" placeholder="Search the wiki..." value="{{QUERY}}" autofocus>
    </form>
    {{RESULTS}}
</body>
</html>"""


def _render_results(results, query: str) -> str:
    """Render search results as HTML."""
    if not results:
        return '<p style="color:#888">No results found.</p>'

    html = ""
    for r in results:
        badge_class = f"badge-{r.type}" if r.type else ""
        tags_html = " ".join(f'<span class="badge">{t}</span>' for t in r.tags[:5])
        html += f"""
        <div class="result">
            <h3>{r.title}</h3>
            <div class="meta">
                <span class="badge {badge_class}">{r.type}</span>
                Score: {r.score:.2f} | {tags_html}
            </div>
            <div class="snippet">{r.snippet[:200]}</div>
        </div>"""
    return html
