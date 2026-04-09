"""QueryEngine — agentic Q&A engine with tool use over the wiki."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from oar.llm.router import LLMRouter
from oar.query.context_manager import ContextManager
from oar.query.tools import ToolExecutor


@dataclass
class QueryResult:
    """Result of a wiki query."""

    answer: str
    sources_consulted: list[str]
    tool_calls: int
    tokens_used: int
    cost_usd: float


class QueryEngine:
    """Agentic Q&A engine with tool use.

    Runs a multi-step loop:
    1. Build context from vault via ContextManager
    2. Create system prompt with context
    3. Call LLM — if response contains tool calls, execute them and loop
    4. Return final answer with [[citation]] sources
    """

    def __init__(
        self,
        context_manager: ContextManager,
        tool_executor: ToolExecutor,
        router: LLMRouter,
        max_iterations: int = 5,
    ):
        self.context_manager = context_manager
        self.tool_executor = tool_executor
        self.router = router
        self.max_iterations = max_iterations

    def query(self, question: str, max_tokens: int = 100000) -> QueryResult:
        """Answer a question using the wiki.

        1. Build context from vault
        2. Create system prompt with context + tool definitions
        3. Run agentic loop: LLM -> tool calls -> results -> LLM
        4. Return final answer with citations
        """
        # Build context
        ctx = self.context_manager.build_context(question, max_tokens=max_tokens)
        context_text = ctx.render()

        # System prompt
        system_prompt = (
            "You are a knowledgeable research assistant with access to a personal wiki.\n"
            "Answer questions based on the wiki content. Use [[wikilinks]] to reference articles.\n"
            "When citing information, use the format: [[article-id]]\n\n"
            f"## Wiki Context\n{context_text}\n\n"
            "## Instructions\n"
            "- Answer based on the wiki content provided\n"
            "- Use [[wikilinks]] to reference specific articles\n"
            "- If you need more information, use the search_wiki or read_article tools\n"
            "- Be specific and cite your sources\n"
            "- If the wiki doesn't contain relevant information, say so"
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        # Agentic loop
        tool_calls_made = 0
        total_tokens = 0
        total_cost = 0.0
        assistant_content = ""

        for iteration in range(self.max_iterations):
            # Call LLM
            response = self.router.complete(
                messages=messages,
                max_tokens=4096,
                temperature=0.5,
                task="query",
            )
            total_tokens += response.input_tokens + response.output_tokens
            total_cost += response.cost_usd
            assistant_content = response.content

            # Check for tool calls
            tool_calls = self._extract_tool_calls(assistant_content)

            if not tool_calls:
                # No tool calls — this is the final answer
                sources = self._extract_sources(assistant_content)
                return QueryResult(
                    answer=assistant_content,
                    sources_consulted=sources,
                    tool_calls=tool_calls_made,
                    tokens_used=total_tokens,
                    cost_usd=total_cost,
                )

            # Execute tool calls
            tool_calls_made += len(tool_calls)
            messages.append({"role": "assistant", "content": assistant_content})

            for tc in tool_calls:
                result = self.tool_executor.execute(tc["name"], tc["arguments"])
                messages.append(
                    {
                        "role": "user",
                        "content": f"Tool result for {tc['name']}: {result}",
                    }
                )

        # Max iterations reached — return last response
        sources = self._extract_sources(assistant_content)
        return QueryResult(
            answer=assistant_content,
            sources_consulted=sources,
            tool_calls=tool_calls_made,
            tokens_used=total_tokens,
            cost_usd=total_cost,
        )

    def _extract_tool_calls(self, content: str) -> list[dict]:
        """Extract tool call requests from LLM response.

        Looks for two patterns:
        1. <tool_call name="...">JSON args</tool_call
        2. ```json blocks with "tool" and "arguments" keys
        """
        calls: list[dict] = []

        # Pattern 1: <tool_call name="...">...</tool_call
        pattern = r'<tool_call\s+name="(\w+)">\s*(.*?)\s*</tool_call'
        matches = re.findall(pattern, content, re.DOTALL)
        for name, args_str in matches:
            try:
                args = json.loads(args_str)
                calls.append({"name": name, "arguments": args})
            except json.JSONDecodeError:
                pass

        # Pattern 2: ```json blocks with tool_call key
        json_pattern = r"```json\s*(.*?)\s*```"
        json_matches = re.findall(json_pattern, content, re.DOTALL)
        for jm in json_matches:
            try:
                data = json.loads(jm)
                if "tool" in data and "arguments" in data:
                    calls.append({"name": data["tool"], "arguments": data["arguments"]})
            except json.JSONDecodeError:
                pass

        return calls

    def _extract_sources(self, text: str) -> list[str]:
        """Extract [[wikilinks]] from the answer text."""
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        return list(set(re.findall(pattern, text)))
