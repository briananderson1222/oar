"""Tests for oar.query.engine — QueryEngine (all litellm calls mocked)."""

from unittest.mock import MagicMock, patch

from oar.core.link_resolver import LinkResolver
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.index.moc_builder import MocBuilder
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import LLMRouter
from oar.query.context_manager import ContextManager
from oar.query.engine import QueryEngine
from oar.query.tools import ToolExecutor
from oar.search.indexer import SearchIndexer
from oar.search.searcher import Searcher


def _mock_llm_response(content: str, input_tokens: int = 100, output_tokens: int = 50):
    """Build a mock litellm response object."""
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


def _setup_vault(tmp_vault):
    """Create vault components for testing."""
    vault = Vault(tmp_vault)
    ops = VaultOps(vault)

    ops.write_compiled_article(
        "concepts",
        "attention-mechanism.md",
        {
            "id": "attention-mechanism",
            "title": "Attention Mechanism",
            "type": "concept",
            "tags": ["attention"],
            "status": "draft",
            "related": ["transformer-architecture"],
            "word_count": 30,
        },
        "Attention is a mechanism in neural networks.",
    )
    ops.write_compiled_article(
        "concepts",
        "transformer-architecture.md",
        {
            "id": "transformer-architecture",
            "title": "Transformer Architecture",
            "type": "concept",
            "tags": ["transformer"],
            "status": "draft",
            "related": ["attention-mechanism"],
            "word_count": 40,
        },
        "The Transformer uses self-attention.",
    )

    # Build search index.
    db_path = tmp_vault / ".oar" / "search-index" / "search.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    indexer = SearchIndexer(db_path)
    indexer.index_vault(vault, ops)
    indexer.close()

    searcher = Searcher(db_path)
    link_resolver = LinkResolver(vault, ops)
    moc_builder = MocBuilder(vault, ops)
    context_manager = ContextManager(vault, ops, link_resolver)
    tool_executor = ToolExecutor(vault, ops, searcher, link_resolver, moc_builder)

    return context_manager, tool_executor


class TestQueryBasic:
    """Basic query functionality."""

    def test_query_returns_answer(self, tmp_path):
        """QueryResult with answer text."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                "Attention is a neural network mechanism. See [[attention-mechanism]].",
                input_tokens=200,
                output_tokens=30,
            )
            result = engine.query("What is attention?")

        assert result.answer
        assert "attention" in result.answer.lower() or "Attention" in result.answer

    def test_query_has_sources(self, tmp_path):
        """Sources extracted from [[wikilinks]] in answer."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                "See [[attention-mechanism]] and [[transformer-architecture]]."
            )
            result = engine.query("What is attention?")

        assert "attention-mechanism" in result.sources_consulted
        assert "transformer-architecture" in result.sources_consulted

    def test_query_tracks_cost(self, tmp_path):
        """Cost > 0 after query."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                "Answer.", input_tokens=100, output_tokens=50
            )
            result = engine.query("test")

        assert result.cost_usd > 0

    def test_query_tracks_tokens(self, tmp_path):
        """Tokens > 0."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                "Answer.", input_tokens=100, output_tokens=50
            )
            result = engine.query("test")

        assert result.tokens_used > 0


class TestQueryWithToolCalls:
    """Tool call handling in agentic loop."""

    def test_query_with_tool_call(self, tmp_path):
        """Mock LLM returns tool call → executed → follow-up response."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        # First call: LLM requests a tool call. Second call: final answer.
        tool_call_response = _mock_llm_response(
            '<tool_call name="search_wiki">{"query": "attention"}</tool_call',
            input_tokens=200,
            output_tokens=20,
        )
        final_response = _mock_llm_response(
            "Based on search results, attention is a mechanism. See [[attention-mechanism]].",
            input_tokens=300,
            output_tokens=40,
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = [tool_call_response, final_response]
            result = engine.query("What is attention?")

        assert result.tool_calls == 1
        assert "attention" in result.answer.lower() or "Attention" in result.answer
        assert "attention-mechanism" in result.sources_consulted

    def test_query_max_iterations(self, tmp_path):
        """Stops after max iterations even if tool calls continue."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router, max_iterations=2)

        # Every response contains a tool call — engine should stop at max_iterations.
        tool_call_resp = _mock_llm_response(
            '<tool_call name="search_wiki">{"query": "test"}</tool_call',
            input_tokens=100,
            output_tokens=10,
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = tool_call_resp
            result = engine.query("keep calling tools")

        assert result.tool_calls >= 1
        # Should have stopped without infinite loop.


class TestExtractToolCalls:
    """Tool call parsing from LLM output."""

    def test_extract_tool_calls_xml_format(self, tmp_path):
        """Parses <tool_call name="...">...</tool_call pattern."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        calls = engine._extract_tool_calls(
            'Let me search.\n<tool_call name="search_wiki">{"query": "attention"}</tool_call'
        )
        assert len(calls) == 1
        assert calls[0]["name"] == "search_wiki"
        assert calls[0]["arguments"]["query"] == "attention"

    def test_extract_tool_calls_json_format(self, tmp_path):
        """Parses ```json blocks with tool_call key."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        calls = engine._extract_tool_calls(
            '```json\n{"tool": "read_article", "arguments": {"article_id": "test"}}\n```'
        )
        assert len(calls) == 1
        assert calls[0]["name"] == "read_article"
        assert calls[0]["arguments"]["article_id"] == "test"

    def test_extract_tool_calls_no_calls(self, tmp_path):
        """No tool calls in plain text."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        calls = engine._extract_tool_calls("Just a regular answer with no tool calls.")
        assert len(calls) == 0


class TestExtractSources:
    """Source extraction from [[wikilinks]]."""

    def test_extract_sources_from_wikilinks(self, tmp_path):
        """Extracts [[links]] from answer text."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        sources = engine._extract_sources(
            "See [[attention-mechanism]] and [[transformer-architecture]] for details."
        )
        assert "attention-mechanism" in sources
        assert "transformer-architecture" in sources

    def test_extract_sources_with_display_text(self, tmp_path):
        """Extracts links ignoring display text: [[link|Display]]."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        sources = engine._extract_sources(
            "See [[attention-mechanism|Attention]] for more."
        )
        assert "attention-mechanism" in sources

    def test_extract_sources_no_links(self, tmp_path):
        """No sources when answer has no wikilinks."""
        context_manager, tool_executor = _setup_vault(tmp_path)
        tracker = CostTracker(tmp_path)
        router = LLMRouter("claude-sonnet-4-20250514", tracker)
        engine = QueryEngine(context_manager, tool_executor, router)

        sources = engine._extract_sources("Just plain text with no links.")
        assert len(sources) == 0
