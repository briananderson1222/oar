"""Tests for oar.compile.compiler — Compiler (LLM mocked)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from oar.compile.compiler import Compiler, CompileResult
from oar.core.state import StateManager
from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import LLMRouter


def _make_llm_json(frontmatter: dict | None = None, body: str | None = None) -> str:
    """Build a valid LLM JSON response string."""
    if frontmatter is None:
        frontmatter = {
            "type": "concept",
            "domain": ["machine-learning"],
            "tags": ["test", "example"],
            "related": [],
            "complexity": "intermediate",
            "confidence": 0.85,
        }
    if body is None:
        body = (
            "# Test Article\n\n"
            "> **TL;DR**: A test article.\n\n"
            "## Overview\n\nThis is a test.\n\n"
            "## Key Ideas\n\n- Test idea\n"
        )
    return json.dumps({"frontmatter": frontmatter, "body": body})


def _mock_llm_response(
    content: str, input_tokens: int = 1000, output_tokens: int = 500
):
    return MagicMock(
        usage=MagicMock(prompt_tokens=input_tokens, completion_tokens=output_tokens),
        choices=[MagicMock(message=MagicMock(content=content))],
    )


def _setup_compiler(tmp_vault: Path):
    """Build a Compiler with a real vault and mocked router."""
    vault = Vault(tmp_vault)
    ops = VaultOps(vault)
    tracker = CostTracker(tmp_vault / ".oar")
    state_mgr = StateManager(tmp_vault / ".oar")
    router = LLMRouter("claude-sonnet-4-20250514", tracker)
    compiler = Compiler(vault, ops, router, state_mgr)
    return compiler, tracker, state_mgr, router


class TestCompileArticle:
    """compile_article creates compiled files from raw articles."""

    def test_compile_article_creates_compiled_file(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        # Write a raw article.
        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "test-article.md",
            {
                "id": "test-article",
                "title": "Test Article About Transformers",
                "source_type": "article",
                "compiled": False,
            },
            "This is about transformers and attention.",
        )
        state_mgr.register_article(
            "test-article", "01-raw/articles/test-article.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_article(raw_path)

        assert result.success is True
        assert result.compiled_path.exists()
        # File should be in 02-compiled/concepts/
        assert "02-compiled" in str(result.compiled_path)

    def test_compile_article_has_valid_frontmatter(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "fm-test.md",
            {
                "id": "fm-test",
                "title": "Frontmatter Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content here.",
        )
        state_mgr.register_article(
            "fm-test", "01-raw/articles/fm-test.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_article(raw_path)

        assert result.success is True
        # Read the compiled file and check frontmatter.
        fm_mgr = compiler.ops.fm
        meta, body = fm_mgr.read(result.compiled_path)
        assert "id" in meta
        assert "title" in meta
        assert "type" in meta
        assert "status" in meta
        assert meta["status"] == "draft"

    def test_compile_article_has_body_sections(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "body-test.md",
            {
                "id": "body-test",
                "title": "Body Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content for body test.",
        )
        state_mgr.register_article(
            "body-test", "01-raw/articles/body-test.md", "sha256:abc"
        )

        body_text = (
            "# Body Test\n\n"
            "> **TL;DR**: Body test article.\n\n"
            "## Overview\n\nOverview text.\n\n"
            "## Key Ideas\n\n- Idea 1\n"
        )
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                _make_llm_json(body=body_text)
            )
            result = compiler.compile_article(raw_path)

        assert result.success is True
        fm_mgr = compiler.ops.fm
        meta, body = fm_mgr.read(result.compiled_path)
        assert "TL;DR" in body
        assert "Overview" in body

    def test_compile_article_updates_state(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "state-test.md",
            {
                "id": "state-test",
                "title": "State Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content for state test.",
        )
        state_mgr.register_article(
            "state-test", "01-raw/articles/state-test.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_article(raw_path)

        assert result.success is True
        state = state_mgr.load()
        article = state["articles"]["state-test"]
        assert article["compiled"] is True

    def test_compile_article_records_cost(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "cost-test.md",
            {
                "id": "cost-test",
                "title": "Cost Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content for cost test.",
        )
        state_mgr.register_article(
            "cost-test", "01-raw/articles/cost-test.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                _make_llm_json(), input_tokens=500, output_tokens=200
            )
            result = compiler.compile_article(raw_path)

        assert result.success is True
        assert tracker.get_session_cost() > 0
        assert result.cost_usd > 0

    def test_compile_article_handles_llm_error(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        raw_path = ops.write_raw_article(
            "error-test.md",
            {
                "id": "error-test",
                "title": "Error Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content that will fail.",
        )
        state_mgr.register_article(
            "error-test", "01-raw/articles/error-test.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("API error")
            result = compiler.compile_article(raw_path)

        assert result.success is False
        assert "API error" in result.error


class TestCompileSingle:
    """compile_single — compile by article ID."""

    def test_compile_single_by_id(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        ops.write_raw_article(
            "single-test.md",
            {
                "id": "single-test",
                "title": "Single Test",
                "source_type": "article",
                "compiled": False,
            },
            "Content for single compile.",
        )
        state_mgr.register_article(
            "single-test", "01-raw/articles/single-test.md", "sha256:abc"
        )

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_single("single-test")

        assert result.success is True
        assert result.raw_id == "single-test"


class TestCompileAll:
    """compile_all — batch compilation with budget."""

    def test_compile_all_processes_multiple(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        for i in range(3):
            aid = f"batch-{i}"
            ops.write_raw_article(
                f"{aid}.md",
                {
                    "id": aid,
                    "title": f"Batch Article {i}",
                    "source_type": "article",
                    "compiled": False,
                },
                f"Content for batch article {i}.",
            )
            state_mgr.register_article(aid, f"01-raw/articles/{aid}.md", f"sha256:{i}")

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            results = compiler.compile_all()

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_compile_all_respects_max_cost(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)

        ops = VaultOps(Vault(tmp_vault))
        for i in range(5):
            aid = f"budget-{i}"
            ops.write_raw_article(
                f"{aid}.md",
                {
                    "id": aid,
                    "title": f"Budget Article {i}",
                    "source_type": "article",
                    "compiled": False,
                },
                f"Content for budget article {i}.",
            )
            state_mgr.register_article(aid, f"01-raw/articles/{aid}.md", f"sha256:{i}")

        with patch("litellm.completion") as mock_completion:
            # Each call costs ~0.0105 (1000 input + 500 output at Sonnet pricing).
            mock_completion.return_value = _mock_llm_response(
                _make_llm_json(), input_tokens=1000, output_tokens=500
            )
            # max_cost=0.0105: first call goes through (session=0 < 0.0105),
            # after first call session=0.0105 which is NOT < 0.0105, so only 1 runs.
            results = compiler.compile_all(max_cost=0.0105)

        # First call goes through (budget 0 < 0.0105), but stops after.
        assert len(results) == 1
        assert results[0].success is True


class TestCompileMulti:
    """compile_multi — merge multiple raw articles into one compiled article."""

    def test_compile_multi_merges_articles(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        # Write two raw articles on related topics.
        for i, (aid, title) in enumerate(
            [
                ("multi-a", "Machine Learning Basics"),
                ("multi-b", "Machine Learning Advanced"),
            ]
        ):
            ops.write_raw_article(
                f"{aid}.md",
                {
                    "id": aid,
                    "title": title,
                    "source_type": "article",
                    "compiled": False,
                },
                f"Content for {title}.",
            )
            state_mgr.register_article(aid, f"01-raw/articles/{aid}.md", f"sha256:{i}")

        multi_body = (
            "# Machine Learning\n\n"
            "> **TL;DR**: Merged article.\n\n"
            "## Overview\n\nCombined content.\n"
        )
        multi_fm = {
            "type": "concept",
            "domain": ["machine-learning"],
            "tags": ["ml", "merged"],
            "related": [],
            "complexity": "intermediate",
            "confidence": 0.8,
        }

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(
                _make_llm_json(frontmatter=multi_fm, body=multi_body)
            )
            result = compiler.compile_multi(["multi-a", "multi-b"])

        assert result.success is True
        assert result.compiled_path.exists()

    def test_compile_multi_has_combined_sources(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        for i, (aid, title) in enumerate(
            [
                ("src-a", "Source Article Alpha"),
                ("src-b", "Source Article Beta"),
            ]
        ):
            ops.write_raw_article(
                f"{aid}.md",
                {
                    "id": aid,
                    "title": title,
                    "source_type": "article",
                    "compiled": False,
                },
                f"Content for {title}.",
            )
            state_mgr.register_article(aid, f"01-raw/articles/{aid}.md", f"sha256:{i}")

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_multi(["src-a", "src-b"])

        assert result.success is True
        # Check the compiled article's frontmatter has both sources.
        fm_mgr = compiler.ops.fm
        meta, _ = fm_mgr.read(result.compiled_path)
        sources = meta.get("sources", [])
        assert "[[src-a]]" in sources
        assert "[[src-b]]" in sources

    def test_compile_multi_marks_all_compiled(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        for i, (aid, title) in enumerate(
            [
                ("mark-a", "Mark Article Alpha"),
                ("mark-b", "Mark Article Beta"),
            ]
        ):
            ops.write_raw_article(
                f"{aid}.md",
                {
                    "id": aid,
                    "title": title,
                    "source_type": "article",
                    "compiled": False,
                },
                f"Content for {title}.",
            )
            state_mgr.register_article(aid, f"01-raw/articles/{aid}.md", f"sha256:{i}")

        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response(_make_llm_json())
            result = compiler.compile_multi(["mark-a", "mark-b"])

        assert result.success is True
        state = state_mgr.load()
        assert state["articles"]["mark-a"]["compiled"] is True
        assert state["articles"]["mark-b"]["compiled"] is True


class TestCompileWithConcepts:
    """compile_with_concepts — compile then extract concepts."""

    def test_compile_with_concepts_suggests_new(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        ops.write_raw_article(
            "concept-test.md",
            {
                "id": "concept-test",
                "title": "Concept Test Article",
                "source_type": "article",
                "compiled": False,
            },
            "Content about transformers and attention mechanisms.",
        )
        state_mgr.register_article(
            "concept-test", "01-raw/articles/concept-test.md", "sha256:abc"
        )

        concepts_json = json.dumps(
            [
                {
                    "title": "Attention Mechanism",
                    "slug": "attention-mechanism",
                    "type": "concept",
                    "reason": "Core sub-topic",
                    "priority": 1,
                }
            ]
        )

        with patch("litellm.completion") as mock_completion:
            # First call: compile_article → returns valid compile JSON
            # Second call: concept_extractor → returns concepts JSON array
            mock_completion.side_effect = [
                _mock_llm_response(_make_llm_json()),
                _mock_llm_response(concepts_json),
            ]
            mresult = compiler.compile_with_concepts("concept-test")

        assert mresult.main_result.success is True
        assert len(mresult.concept_suggestions) >= 1
        assert any(s.slug == "attention-mechanism" for s in mresult.concept_suggestions)


class TestCascadeUpdate:
    """cascade_update — find articles that reference a changed article."""

    def test_cascade_update_flags_related(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        # Write compiled article that references "target-id".
        ops.write_compiled_article(
            "concepts",
            "referrer.md",
            {
                "id": "referrer",
                "title": "Referrer Article",
                "type": "concept",
                "status": "draft",
            },
            "See [[target-id]] for more details.",
        )
        # Write another compiled article that also references "target-id".
        ops.write_compiled_article(
            "concepts",
            "referrer2.md",
            {
                "id": "referrer2",
                "title": "Second Referrer",
                "type": "concept",
                "status": "draft",
            },
            "Also related to [[target-id]].",
        )

        related = compiler.cascade_update("target-id")
        assert "referrer" in related
        assert "referrer2" in related

    def test_cascade_update_no_related(self, tmp_vault):
        compiler, tracker, state_mgr, router = _setup_compiler(tmp_vault)
        ops = VaultOps(Vault(tmp_vault))

        # Write a compiled article with no backlinks to our target.
        ops.write_compiled_article(
            "concepts",
            "unrelated.md",
            {
                "id": "unrelated",
                "title": "Unrelated Article",
                "type": "concept",
                "status": "draft",
            },
            "This has no wikilinks.",
        )

        related = compiler.cascade_update("nonexistent-id")
        assert related == []
