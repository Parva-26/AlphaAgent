"""Valuation and sector comparison tools."""

from __future__ import annotations

from typing import Any

import yfinance as yf
from duckduckgo_search import DDGS
from langchain.tools import tool

from utils.formatters import currency, percent, safe_round
from utils.market_sources import latest_close, load_price_history_resilient, safe_fast_info, sec_fundamentals


def _info(ticker: str) -> dict[str, Any]:
    try:
        return yf.Ticker(ticker.strip().upper()).info or {}
    except Exception:
        return {}


def _enterprise_value(info: dict[str, Any]) -> float | None:
    ev = info.get("enterpriseValue")
    if ev:
        return float(ev)
    market_cap = info.get("marketCap")
    debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    if market_cap:
        return float(market_cap + debt - cash)
    return None


@tool
def calculate_valuation_metrics(ticker: str) -> dict:
    """Calculate common valuation metrics for a ticker using free yfinance data."""

    try:
        info = _info(ticker)
        history, source = load_price_history_resilient(ticker, period="1y")
        fast_info = safe_fast_info(ticker)
        try:
            sec = sec_fundamentals(ticker)
        except Exception:
            sec = {}
        price = latest_close(history)
        market_cap = info.get("marketCap") or fast_info.get("market_cap") or fast_info.get("marketCap")
        if not market_cap and price and sec.get("shares"):
            market_cap = price * sec["shares"]
        debt = info.get("totalDebt") or sec.get("debt") or 0
        cash = info.get("totalCash") or sec.get("cash") or 0
        ev = _enterprise_value(info) or (market_cap + debt - cash if market_cap else None)
        ebitda = info.get("ebitda")
        ev_to_ebitda = (ev / ebitda) if ev and ebitda else None
        growth = info.get("earningsGrowth") or info.get("revenueGrowth")
        eps = info.get("trailingEps") or sec.get("eps")
        trailing_pe = info.get("trailingPE") or ((price / eps) if price and eps else None)
        revenue = sec.get("revenue")
        equity = sec.get("equity")
        price_to_sales = info.get("priceToSalesTrailing12Months") or ((market_cap / revenue) if market_cap and revenue else None)
        price_to_book = info.get("priceToBook") or ((market_cap / equity) if market_cap and equity else None)
        peg = (trailing_pe / (growth * 100)) if trailing_pe and growth else info.get("pegRatio")

        return {
            "ticker": ticker.upper(),
            "latest_price": safe_round(price),
            "market_cap": currency(market_cap),
            "enterprise_value": currency(ev),
            "trailing_pe": safe_round(trailing_pe),
            "forward_pe": safe_round(info.get("forwardPE")),
            "price_to_sales": safe_round(price_to_sales),
            "price_to_book": safe_round(price_to_book),
            "ev_to_ebitda": safe_round(ev_to_ebitda),
            "peg_ratio": safe_round(peg),
            "dividend_yield": percent(info.get("dividendYield")),
            "free_cash_flow": currency(info.get("freeCashflow")),
            "price_data_source": source,
            "fundamental_source": "Yahoo Finance metadata plus SEC Company Facts fallback",
        }
    except Exception as exc:
        return {"ticker": ticker.upper(), "error": f"Could not calculate valuation metrics: {exc}"}


@tool
def compare_to_sector(ticker: str) -> str:
    """Compare a company to broad sector metrics using yfinance and free web search."""

    try:
        info = _info(ticker)
        sector = info.get("sector", "unknown sector")
        industry = info.get("industry", "unknown industry")
        own_metrics = (
            f"{ticker.upper()} trades at trailing P/E {safe_round(info.get('trailingPE'))}, "
            f"forward P/E {safe_round(info.get('forwardPE'))}, P/S "
            f"{safe_round(info.get('priceToSalesTrailing12Months'))}, and P/B "
            f"{safe_round(info.get('priceToBook'))}."
        )
        query = f"{sector} sector average valuation metrics PE price sales price book"
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return f"Sector: {sector}. Industry: {industry}. {own_metrics} No sector benchmark search results found."

        formatted = []
        for result in results:
            formatted.append(
                f"- {result.get('title', 'Untitled')}: {result.get('body', 'No summary')} "
                f"({result.get('href', '')})"
            )
        return (
            f"Sector: {sector}. Industry: {industry}.\n"
            f"{own_metrics}\n\nFree web benchmark references:\n" + "\n".join(formatted)
        )
    except Exception as exc:
        return f"Could not compare {ticker.upper()} to sector: {exc}"
