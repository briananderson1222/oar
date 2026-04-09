"""Tool definitions for the LLM agent — search, read, and navigate the wiki."""

from __future__ import annotations

from typing import Any


# Tool definitions following the Claude/OpenAI tool use schema.
WIKI_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_wiki",
        "description": (
            "Search the compiled wiki for articles matching a query. "
            "Returns list of articles with title, type, score, and snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 10,
                },
                "type": {
                    "type": "string",
                    "description": "Filter: concept|entity|method|comparison|tutorial",
                    "default": None,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_article",
        "description": (
            "Read the full content of a wiki article by its ID "
            "(e.g., 'attention-mechanism')"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "Article ID to read",
                },
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "get_backlinks",
        "description": "Get all articles that link TO a given article",
        "input_schema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "Article ID",
                },
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "get_related",
        "description": "Get related articles from an article's frontmatter",
        "input_schema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "Article ID",
                },
                "depth": {
                    "type": "integer",
                    "description": "1=direct, 2=two hops",
                    "default": 1,
                },
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "list_mocs",
        "description": "List all Maps of Content (topic gateways)",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


class ToolExecutor:
    """Execute tool calls from the LLM agent."""

    def __init__(self, vault, ops, searcher, link_resolver, moc_builder):
        self.vault = vault
        self.ops = ops
        self.searcher = searcher
        self.resolver = link_resolver
        self.moc_builder = moc_builder
        self._tools: dict[str, Any] = {
            "search_wiki": self._search_wiki,
            "read_article": self._read_article,
            "get_backlinks": self._get_backlinks,
            "get_related": self._get_related,
            "list_mocs": self._list_mocs,
        }

    def execute(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call and return the result as a string."""
        handler = self._tools.get(tool_name)
        if not handler:
            return f"Error: Unknown tool '{tool_name}'"
        try:
            return handler(**arguments)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return the list of tool definitions for the LLM."""
        return WIKI_TOOLS

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _search_wiki(self, query: str, limit: int = 10, type: str = None) -> str:
        """Search wiki and return formatted results."""
        results = self.searcher.search(query, limit=limit, type_filter=type)
        if not results:
            return "No articles found matching the query."
        lines: list[str] = []
        for r in results:
            lines.append(
                f"- **{r.title}** (id: {r.article_id}, type: {r.type}, "
                f"score: {r.score:.2f})"
            )
            lines.append(f"  {r.snippet[:150]}...")
        return "\n".join(lines)

    def _read_article(self, article_id: str) -> str:
        """Read full article content."""
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return f"Article '{article_id}' not found."
        fm, body = self.ops.read_article(path)
        title = fm.get("title", article_id)
        return f"# {title}\n\n{body}"

    def _get_backlinks(self, article_id: str) -> str:
        """Get articles linking to this one."""
        graph = self.resolver.build_graph()
        backlinks = graph.get_backlinks(article_id)
        if not backlinks:
            return f"No articles link to '{article_id}'."
        return f"Articles linking to '{article_id}':\n" + "\n".join(
            f"- {bid}" for bid in backlinks
        )

    def _get_related(self, article_id: str, depth: int = 1) -> str:
        """Get related articles from frontmatter."""
        path = self.ops.get_article_by_id(article_id)
        if not path:
            return f"Article '{article_id}' not found."
        fm, _ = self.ops.read_article(path)
        related = fm.get("related", [])
        if not related:
            return f"No related articles listed for '{article_id}'."
        return f"Related to '{article_id}':\n" + "\n".join(f"- {r}" for r in related)

    def _list_mocs(self) -> str:
        """List all MOCs."""
        mocs = self.moc_builder.list_mocs()
        if not mocs:
            return "No Maps of Content found."
        lines = ["Available Maps of Content:"]
        for moc in mocs:
            lines.append(
                f"- **{moc['title']}** ({moc.get('article_count', '?')} articles)"
            )
        return "\n".join(lines)
