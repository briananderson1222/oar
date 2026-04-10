"""Compiler — orchestrate single-article compilation via LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

import re

from oar.compile.concept_extractor import ConceptExtractor, ConceptSuggestion
from oar.compile.context_builder import CompileContextBuilder
from oar.compile.default_prompt import COMPILE_PROMPT
from oar.compile.multi_prompt import MULTI_COMPILE_PROMPT
from oar.core.frontmatter import FrontmatterManager
from oar.core.slug import slugify
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.router import LLMRouter


@dataclass
class CompileResult:
    """Result of compiling a single raw article."""

    raw_id: str
    compiled_id: str
    compiled_path: Path
    tokens_used: int
    cost_usd: float
    success: bool
    error: str = ""


@dataclass
class MultiCompileResult:
    """Result of compiling with concept extraction."""

    main_result: CompileResult
    concept_suggestions: list[ConceptSuggestion] = field(default_factory=list)
    related_updates: list[str] = field(default_factory=list)


class Compiler:
    """Orchestrate compilation of raw articles into structured wiki notes."""

    def __init__(
        self,
        vault: Vault,
        ops: VaultOps,
        router: LLMRouter,
        state_manager: StateManager,
    ) -> None:
        self.vault = vault
        self.ops = ops
        self.router = router
        self.state = state_manager
        self.context_builder = CompileContextBuilder(vault, ops)
        self.concept_extractor = ConceptExtractor(router)

    def compile_article(self, raw_path: Path) -> CompileResult:
        """Compile a single raw article into a wiki article.

        Steps:
        1. Read raw article (metadata + body)
        2. Build prompt with raw article content
        3. Call LLM to generate compiled article
        4. Parse LLM response (expect JSON with frontmatter + body)
        5. Determine article type and write to appropriate subdir
        6. Update state.json
        7. Return CompileResult
        """
        fm = FrontmatterManager()
        try:
            metadata, body = fm.read(raw_path)
        except Exception as exc:
            return CompileResult(
                raw_id="",
                compiled_id="",
                compiled_path=raw_path,
                tokens_used=0,
                cost_usd=0.0,
                success=False,
                error=str(exc),
            )

        raw_id: str = metadata.get("id", raw_path.stem)
        title: str = metadata.get("title", raw_path.stem)

        # Build prompt.
        prompt_template = Template(COMPILE_PROMPT)
        prompt_text = prompt_template.render(title=title, content=body)
        messages = [{"role": "user", "content": prompt_text}]

        # Call LLM.
        try:
            llm_response = self.router.complete(
                messages=messages,
                task="compile",
            )
        except Exception as exc:
            return CompileResult(
                raw_id=raw_id,
                compiled_id="",
                compiled_path=raw_path,
                tokens_used=0,
                cost_usd=0.0,
                success=False,
                error=str(exc),
            )

        # Parse LLM response — expect JSON with "frontmatter" and "body".
        try:
            # Strip markdown code fences if present.
            content = llm_response.content.strip()
            if content.startswith("```"):
                # Remove first and last line.
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            parsed = json.loads(content)
            llm_frontmatter = parsed.get("frontmatter", {})
            llm_body = parsed.get("body", "")
        except (json.JSONDecodeError, AttributeError) as exc:
            return CompileResult(
                raw_id=raw_id,
                compiled_id="",
                compiled_path=raw_path,
                tokens_used=llm_response.input_tokens + llm_response.output_tokens,
                cost_usd=llm_response.cost_usd,
                success=False,
                error=f"Failed to parse LLM response: {exc}",
            )

        # Determine type → subdir mapping.
        article_type = llm_frontmatter.get("type", "concept")
        type_to_subdir: dict[str, str] = {
            "concept": "concepts",
            "entity": "entities",
            "method": "methods",
            "comparison": "comparisons",
            "tutorial": "tutorials",
            "timeline": "timelines",
        }
        subdir = type_to_subdir.get(article_type, "concepts")

        # Build compiled article ID (slug from title).
        compiled_id = slugify(title)

        # Assemble compiled frontmatter.
        now = datetime.now(timezone.utc).isoformat()
        compiled_meta = {
            "id": compiled_id,
            "title": title,
            "aliases": [],
            "created": now,
            "updated": now,
            "version": 1,
            "type": article_type,
            "domain": llm_frontmatter.get("domain", []),
            "tags": llm_frontmatter.get("tags", []),
            "status": "draft",
            "confidence": llm_frontmatter.get("confidence", 0.0),
            "sources": [f"[[{raw_id}]]"],
            "source_count": 1,
            "related": llm_frontmatter.get("related", []),
            "prerequisite_for": [],
            "see_also": [],
            "word_count": len(llm_body.split()),
            "read_time_min": max(1, len(llm_body.split()) // 200),
            "backlink_count": 0,
            "complexity": llm_frontmatter.get("complexity", "intermediate"),
        }

        # Write compiled article.
        filename = f"{compiled_id}.md"
        compiled_path = self.ops.write_compiled_article(
            subdir, filename, compiled_meta, llm_body
        )

        # Update state.
        self.state.mark_compiled(raw_id, [compiled_id])

        return CompileResult(
            raw_id=raw_id,
            compiled_id=compiled_id,
            compiled_path=compiled_path,
            tokens_used=llm_response.input_tokens + llm_response.output_tokens,
            cost_usd=llm_response.cost_usd,
            success=True,
        )

    def compile_single(self, article_id: str) -> CompileResult:
        """Compile by article ID (looks up in state)."""
        raw_path = self.ops.get_article_by_id(article_id)
        if raw_path is None:
            return CompileResult(
                raw_id=article_id,
                compiled_id="",
                compiled_path=Path(),
                tokens_used=0,
                cost_usd=0.0,
                success=False,
                error=f"Article not found: {article_id}",
            )
        return self.compile_article(raw_path)

    def compile_all(
        self, limit: int = 10, max_cost: float = 5.00
    ) -> list[CompileResult]:
        """Compile all uncompiled articles, respecting budget."""
        uncompiled = self.state.get_uncompiled()
        results: list[CompileResult] = []
        for article_id in uncompiled[:limit]:
            # Check budget before each call.
            if not self.router.cost_tracker.check_budget(max_cost):
                break
            result = self.compile_single(article_id)
            results.append(result)
            if not result.success:
                continue  # Still try next articles.
        return results

    # ------------------------------------------------------------------
    # Multi-article compilation
    # ------------------------------------------------------------------

    def compile_multi(self, raw_ids: list[str]) -> CompileResult:
        """Compile multiple raw articles into one compiled article.

        1. Find all raw articles by IDs
        2. Build combined context
        3. Send to LLM with multi-article prompt
        4. Parse response and write compiled article
        5. Mark ALL source articles as compiled
        """
        # Collect raw article paths and metadata.
        raw_paths: list[Path] = []
        raw_titles: list[str] = []
        for aid in raw_ids:
            path = self.ops.get_article_by_id(aid)
            if path is None:
                return CompileResult(
                    raw_id=",".join(raw_ids),
                    compiled_id="",
                    compiled_path=Path(),
                    tokens_used=0,
                    cost_usd=0.0,
                    success=False,
                    error=f"Article not found: {aid}",
                )
            raw_paths.append(path)
            fm, _ = self.ops.read_article(path)
            raw_titles.append(fm.get("title", aid))

        # Build combined context from all raw articles.
        combined_context = self.context_builder.build_multi_context(raw_paths)

        # Build prompt from multi-article template.
        prompt_text = MULTI_COMPILE_PROMPT.format(content=combined_context)
        messages = [{"role": "user", "content": prompt_text}]

        # Call LLM.
        try:
            llm_response = self.router.complete(
                messages=messages,
                task="compile",
            )
        except Exception as exc:
            return CompileResult(
                raw_id=",".join(raw_ids),
                compiled_id="",
                compiled_path=Path(),
                tokens_used=0,
                cost_usd=0.0,
                success=False,
                error=str(exc),
            )

        # Parse LLM response — expect JSON with "frontmatter" and "body".
        try:
            content = llm_response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            parsed = json.loads(content)
            llm_frontmatter = parsed.get("frontmatter", {})
            llm_body = parsed.get("body", "")
        except (json.JSONDecodeError, AttributeError) as exc:
            return CompileResult(
                raw_id=",".join(raw_ids),
                compiled_id="",
                compiled_path=Path(),
                tokens_used=llm_response.input_tokens + llm_response.output_tokens,
                cost_usd=llm_response.cost_usd,
                success=False,
                error=f"Failed to parse LLM response: {exc}",
            )

        # Determine type → subdir mapping.
        article_type = llm_frontmatter.get("type", "concept")
        type_to_subdir: dict[str, str] = {
            "concept": "concepts",
            "entity": "entities",
            "method": "methods",
            "comparison": "comparisons",
            "tutorial": "tutorials",
            "timeline": "timelines",
        }
        subdir = type_to_subdir.get(article_type, "concepts")

        # Build compiled article ID from first title (or combined).
        combined_title = raw_titles[0] if len(raw_titles) == 1 else raw_titles[0]
        compiled_id = slugify(combined_title)

        # Assemble compiled frontmatter.
        now = datetime.now(timezone.utc).isoformat()
        source_links = [f"[[{aid}]]" for aid in raw_ids]
        compiled_meta = {
            "id": compiled_id,
            "title": combined_title,
            "aliases": [],
            "created": now,
            "updated": now,
            "version": 1,
            "type": article_type,
            "domain": llm_frontmatter.get("domain", []),
            "tags": llm_frontmatter.get("tags", []),
            "status": "draft",
            "confidence": llm_frontmatter.get("confidence", 0.0),
            "sources": source_links,
            "source_count": len(raw_ids),
            "related": llm_frontmatter.get("related", []),
            "prerequisite_for": [],
            "see_also": [],
            "word_count": len(llm_body.split()),
            "read_time_min": max(1, len(llm_body.split()) // 200),
            "backlink_count": 0,
            "complexity": llm_frontmatter.get("complexity", "intermediate"),
        }

        # Write compiled article.
        filename = f"{compiled_id}.md"
        compiled_path = self.ops.write_compiled_article(
            subdir, filename, compiled_meta, llm_body
        )

        # Mark ALL source articles as compiled.
        for aid in raw_ids:
            self.state.mark_compiled(aid, [compiled_id])

        return CompileResult(
            raw_id=",".join(raw_ids),
            compiled_id=compiled_id,
            compiled_path=compiled_path,
            tokens_used=llm_response.input_tokens + llm_response.output_tokens,
            cost_usd=llm_response.cost_usd,
            success=True,
        )

    # ------------------------------------------------------------------
    # Compile with concept extraction
    # ------------------------------------------------------------------

    def compile_with_concepts(self, raw_id: str) -> MultiCompileResult:
        """Compile article then extract concept suggestions.

        1. Compile the article normally
        2. Run concept extraction on the compiled body
        3. Return both the compile result and suggestions
        """
        result = self.compile_single(raw_id)
        if not result.success:
            return MultiCompileResult(main_result=result)

        # Read the compiled article body for concept extraction.
        compiled_path = result.compiled_path
        fm = FrontmatterManager()
        _, body = fm.read(compiled_path)

        # Extract concepts from compiled body.
        suggestions = self.concept_extractor.extract_concepts(body, result.compiled_id)

        return MultiCompileResult(
            main_result=result,
            concept_suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Cascade updates
    # ------------------------------------------------------------------

    def cascade_update(self, compiled_id: str) -> list[str]:
        """Find articles that should be recompiled after this article changed.

        Returns list of compiled article IDs that reference this article
        via [[wikilinks]].
        """
        related: list[str] = []
        pattern = re.compile(rf"\[\[{re.escape(compiled_id)}\]\]")

        for compiled_path in self.ops.list_compiled_articles():
            fm = FrontmatterManager()
            meta, body = fm.read(compiled_path)
            article_id = meta.get("id", "")
            # Don't flag the article itself.
            if article_id == compiled_id:
                continue
            if pattern.search(body):
                related.append(article_id)

        return related
