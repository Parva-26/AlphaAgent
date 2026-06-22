"""Free web search tools using DuckDuckGo."""

from __future__ import annotations

from duckduckgo_search import DDGS
from langchain.tools import tool


def _search(query: str, max_results: int = 3) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        return [{"title": "Search unavailable", "href": "", "body": f"DuckDuckGo search failed: {exc}"}]


def _format_results(results: list[dict]) -> str:
    if not results:
        return "No search results found."
    lines = []
    for index, result in enumerate(results, start=1):
        title = result.get("title", "Untitled")
        href = result.get("href") or result.get("url") or ""
        body = result.get("body", "No summary available.")
        lines.append(f"{index}. {title}\nSource: {href}\nSummary: {body}")
    return "\n\n".join(lines)


@tool
def search_stock_news(query: str) -> str:
    """Search recent stock news for a ticker or company using free DuckDuckGo results."""

    cleaned = query.strip()
    if "stock news" not in cleaned.lower():
        cleaned = f"{cleaned} stock news"
    return _format_results(_search(cleaned, max_results=3))


@tool
def search_sec_filings(ticker: str) -> str:
    """Search for SEC 10-K and 10-Q filing links for a ticker using free DuckDuckGo results."""

    query = f"{ticker.strip().upper()} 10-K 10-Q SEC filings"
    return _format_results(_search(query, max_results=3))

