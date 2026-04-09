"""Tests for oar.lint.consistency — ConsistencyChecker (LLM mocked)."""

from unittest.mock import MagicMock, patch

from oar.core.vault import Vault
from oar.core.vault_ops import VaultOps
from oar.llm.cost_tracker import CostTracker
from oar.llm.router import LLMRouter, LLMResponse
from oar.lint.consistency import ConsistencyChecker
from oar.lint.structural import LintIssue


def _make_router(tmp_path) -> LLMRouter:
    """Create a router with a real cost tracker."""
    tracker = CostTracker(tmp_path / ".oar")
    return LLMRouter("test-model", tracker)


def _mock_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )


class TestCheckConsistency:
    """check_consistency."""

    def test_check_consistency_returns_issues(self, tmp_vault):
        """Returns LintIssue list from LLM response."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "test-art.md",
            {"id": "test-art", "title": "Test", "type": "concept", "status": "draft"},
            "This is the article body about transformers.",
        )

        router = _make_router(tmp_vault)
        checker = ConsistencyChecker(Vault(tmp_vault), ops, router)

        llm_output = '[{"article_id": "test-art", "severity": "warning", "message": "Missing details", "suggestion": "Add more info"}]'

        with patch.object(router, "complete", return_value=_mock_response(llm_output)):
            issues = checker.check_consistency()

        assert len(issues) == 1
        assert isinstance(issues[0], LintIssue)
        assert issues[0].category == "inconsistent"
        assert issues[0].article_id == "test-art"

    def test_check_consistency_respects_max_cost(self, tmp_vault):
        """Stops at budget — no LLM calls when budget exhausted."""
        ops = VaultOps(Vault(tmp_vault))
        ops.write_compiled_article(
            "concepts",
            "budget-art.md",
            {
                "id": "budget-art",
                "title": "Budget",
                "type": "concept",
                "status": "draft",
            },
            "Body text for budget test.",
        )

        router = _make_router(tmp_vault)
        # Pre-spend over budget.
        router.cost_tracker._session_cost = 10.0

        checker = ConsistencyChecker(Vault(tmp_vault), ops, router)

        with patch.object(router, "complete") as mock_complete:
            issues = checker.check_consistency(max_cost=0.50)

        mock_complete.assert_not_called()
        assert issues == []


class TestSuggestConnections:
    """suggest_connections."""

    def test_suggest_connections_returns_suggestions(self, tmp_vault):
        """Returns connection suggestions from LLM."""
        ops = VaultOps(Vault(tmp_vault))
        # Need at least 2 articles.
        ops.write_compiled_article(
            "concepts",
            "art-a.md",
            {"id": "art-a", "title": "Article A", "type": "concept", "status": "draft"},
            "Content about machine learning fundamentals.",
        )
        ops.write_compiled_article(
            "concepts",
            "art-b.md",
            {"id": "art-b", "title": "Article B", "type": "concept", "status": "draft"},
            "Content about neural networks and deep learning.",
        )

        router = _make_router(tmp_vault)
        checker = ConsistencyChecker(Vault(tmp_vault), ops, router)

        llm_output = '[{"article_id": "art-a", "message": "Should link to art-b", "suggestion": "Add [[art-b]]"}]'

        with patch.object(router, "complete", return_value=_mock_response(llm_output)):
            issues = checker.suggest_connections()

        assert len(issues) == 1
        assert issues[0].category == "connection"
        assert issues[0].article_id == "art-a"
