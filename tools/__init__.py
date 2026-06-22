"""LangChain-compatible finance and research tools."""

from .financials import calculate_valuation_metrics, compare_to_sector
from .market_data import (
    get_analyst_info,
    get_financial_statements,
    get_stock_history,
    get_stock_price,
)
from .news_search import search_sec_filings, search_stock_news

ALL_TOOLS = [
    get_stock_price,
    get_financial_statements,
    get_stock_history,
    get_analyst_info,
    search_stock_news,
    search_sec_filings,
    calculate_valuation_metrics,
    compare_to_sector,
]
