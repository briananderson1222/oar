"""Tests for oar.search.ranker — result ranking."""

from oar.search.ranker import rank_results
from oar.search.searcher import SearchResult


class TestRankResults:
    """Search result ranking."""

    def test_rank_results_sorted_by_score(self):
        results = [
            SearchResult(
                article_id="low",
                title="Low Score",
                type="concept",
                score=1.0,
                snippet="body",
                path="a.md",
            ),
            SearchResult(
                article_id="high",
                title="High Score",
                type="concept",
                score=5.0,
                snippet="body",
                path="b.md",
            ),
            SearchResult(
                article_id="mid",
                title="Mid Score",
                type="concept",
                score=3.0,
                snippet="body",
                path="c.md",
            ),
        ]
        ranked = rank_results(results, "test")
        ids = [r.article_id for r in ranked]
        assert ids == ["high", "mid", "low"]

    def test_rank_results_title_match_boosted(self):
        """Articles whose title matches the query should be boosted."""
        results = [
            SearchResult(
                article_id="no-match",
                title="Unrelated Topic",
                type="concept",
                score=3.0,
                snippet="body",
                path="a.md",
            ),
            SearchResult(
                article_id="title-match",
                title="Attention Mechanism",
                type="concept",
                score=3.0,
                snippet="body",
                path="b.md",
            ),
        ]
        ranked = rank_results(results, "attention mechanism")
        # The title-matching result should now be ranked first.
        assert ranked[0].article_id == "title-match"
        assert ranked[0].score > ranked[1].score
