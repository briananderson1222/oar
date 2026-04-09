"""Result ranking — re-rank search results considering multiple signals."""

from __future__ import annotations

from oar.search.searcher import SearchResult


def rank_results(results: list[SearchResult], query: str) -> list[SearchResult]:
    """Re-rank search results considering multiple signals.

    Signals:
    - FTS relevance score (primary, from bm25)
    - Title exact match (boost by 1.5x)
    - Title word overlap (boost by 1.2x per matching word)
    """
    query_words = set(query.lower().split())

    for result in results:
        title_words = set(result.title.lower().split())
        # Boost if query words appear in the title.
        overlap = query_words & title_words
        if overlap:
            # Title contains all query words → strong boost.
            if query_words.issubset(title_words):
                result.score *= 1.5
            elif overlap:
                # Partial overlap → proportional boost.
                result.score *= 1.0 + 0.2 * len(overlap)

    return sorted(results, key=lambda r: r.score, reverse=True)
