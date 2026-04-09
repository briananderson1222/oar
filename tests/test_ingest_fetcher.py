"""Tests for oar.ingest.fetcher — URLFetcher."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from oar.ingest.fetcher import FetchResult, URLFetcher


class TestURLFetcherFetch:
    """URLFetcher.fetch behaviour with mocked HTTP."""

    SAMPLE_HTML = """\
<html>
<head>
    <title>Test Page Title</title>
    <meta name="author" content="Jane Doe">
    <meta property="article:published_time" content="2024-06-15">
</head>
<body>
    <article>
        <h1>Test Page Title</h1>
        <p>This is the first paragraph of the article.</p>
        <p>This is the second paragraph with more content.</p>
    </article>
</body>
</html>"""

    def _mock_response(self, html: str, status_code: int = 200) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.text = html
        return resp

    def test_fetch_url_extracts_title(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response(self.SAMPLE_HTML)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        result = fetcher.fetch("https://example.com/article")
        assert result.title == "Test Page Title"

    def test_fetch_url_extracts_content(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response(self.SAMPLE_HTML)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        result = fetcher.fetch("https://example.com/article")
        assert "first paragraph" in result.content
        assert "second paragraph" in result.content

    def test_fetch_url_handles_timeout(self, mocker):
        fetcher = URLFetcher()
        mocker.patch.object(
            fetcher.client,
            "get",
            side_effect=httpx.TimeoutException("timeout"),
        )

        with pytest.raises(Exception):
            fetcher.fetch("https://slow.example.com")

    def test_fetch_url_handles_404(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response("Not Found", status_code=404)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        with pytest.raises(Exception):
            fetcher.fetch("https://example.com/missing")

    def test_fetch_url_computes_word_count(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response(self.SAMPLE_HTML)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        result = fetcher.fetch("https://example.com/article")
        assert result.word_count > 0

    def test_fetch_url_extracts_author(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response(self.SAMPLE_HTML)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        result = fetcher.fetch("https://example.com/article")
        assert result.author == "Jane Doe"

    def test_fetch_url_extracts_published_date(self, mocker):
        fetcher = URLFetcher()
        mock_resp = self._mock_response(self.SAMPLE_HTML)
        mocker.patch.object(fetcher.client, "get", return_value=mock_resp)

        result = fetcher.fetch("https://example.com/article")
        assert result.published_date == "2024-06-15"
