"""Resilient free market data helpers."""

from __future__ import annotations

import os
import time
from functools import lru_cache
from io import StringIO
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from yfinance import cache as yf_cache


USER_AGENT = "AlphaAgent/1.0 contact@example.com"
CACHE_DIR = os.path.join(os.getcwd(), ".cache", "yfinance")
os.makedirs(CACHE_DIR, exist_ok=True)
yf.set_tz_cache_location(CACHE_DIR)
yf_cache._CookieDBManager.set_location(CACHE_DIR)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,*/*"})


def _get(url: str, **kwargs) -> requests.Response:
    """GET with a small retry window for transient free-data hiccups."""

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = SESSION.get(url, timeout=12, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response
            last_exc = requests.HTTPError(f"{response.status_code} response from {url}")
        except Exception as exc:
            last_exc = exc
        time.sleep(0.7 * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Could not fetch {url}")


def normalize_symbol(ticker: str) -> str:
    """Normalize a ticker for free market data providers."""

    return ticker.strip().upper()


def load_yahoo_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Load price history through Yahoo's chart path without quoteSummary."""

    symbol = normalize_symbol(ticker)
    data = yf.download(symbol, period=period, auto_adjust=False, progress=False, threads=False)
    if data is None or data.empty:
        return pd.DataFrame()

    data = data.reset_index()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [column[0] if isinstance(column, tuple) else column for column in data.columns]
    return data


def load_yahoo_chart_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Load Yahoo chart JSON directly, bypassing yfinance metadata calls."""

    symbol = normalize_symbol(ticker)
    range_map = {"5d": "5d", "1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
    chart_range = range_map.get(period, "1y")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = _get(
        url,
        params={"range": chart_range, "interval": "1d", "includePrePost": "false"},
    )
    result = response.json().get("chart", {}).get("result", [])
    if not result:
        return pd.DataFrame()

    payload = result[0]
    timestamps = payload.get("timestamp") or []
    quote = (payload.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (payload.get("indicators", {}).get("adjclose") or [{}])[0]
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(timestamps, unit="s", errors="coerce"),
            "Open": quote.get("open", []),
            "High": quote.get("high", []),
            "Low": quote.get("low", []),
            "Close": quote.get("close", []),
            "Adj Close": adjusted.get("adjclose", quote.get("close", [])),
            "Volume": quote.get("volume", []),
        }
    )
    return data.dropna(subset=["Date", "Close"]).reset_index(drop=True)


def load_stooq_history(ticker: str) -> pd.DataFrame:
    """Load daily US equity prices from Stooq as a no-key fallback."""

    symbol = normalize_symbol(ticker).replace(".", "-").lower()
    url = f"https://stooq.com/q/d/l/?s={symbol}.us&i=d"
    response = _get(url)

    data = pd.read_csv(StringIO(response.text))
    if data.empty or "Date" not in data.columns:
        return pd.DataFrame()

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).sort_values("Date")
    return data.tail(260).reset_index(drop=True)


def load_price_history_resilient(ticker: str, period: str = "1y") -> tuple[pd.DataFrame, str]:
    """Return price history and the source used."""

    try:
        yahoo_chart = load_yahoo_chart_history(ticker, period=period)
        if not yahoo_chart.empty:
            return yahoo_chart, "Yahoo Finance chart API"
    except Exception:
        pass

    try:
        yahoo = load_yahoo_history(ticker, period=period)
        if not yahoo.empty:
            return yahoo, "Yahoo Finance chart"
    except Exception:
        pass

    try:
        stooq = load_stooq_history(ticker)
        if not stooq.empty:
            return stooq, "Stooq"
    except Exception:
        pass

    return pd.DataFrame(), "Unavailable"


def latest_close(history: pd.DataFrame) -> float | None:
    """Return the latest close from a normalized OHLCV dataframe."""

    if history.empty or "Close" not in history:
        return None
    close = history["Close"].dropna()
    return float(close.iloc[-1]) if not close.empty else None


@lru_cache(maxsize=256)
def get_company_name(ticker: str) -> str:
    """Return a readable company name without relying on Yahoo quoteSummary."""

    symbol = normalize_symbol(ticker)
    known_names = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "NVDA": "NVIDIA Corporation",
        "GOOGL": "Alphabet Inc.",
        "GOOG": "Alphabet Inc.",
        "AMZN": "Amazon.com, Inc.",
        "META": "Meta Platforms, Inc.",
        "TSLA": "Tesla, Inc.",
        "AMD": "Advanced Micro Devices, Inc.",
        "AVGO": "Broadcom Inc.",
    }
    return known_names.get(symbol, symbol)


def safe_fast_info(ticker: str) -> dict[str, Any]:
    """Best-effort yfinance fast_info wrapper."""

    try:
        fast_info = yf.Ticker(normalize_symbol(ticker)).fast_info
        if hasattr(fast_info, "items"):
            return dict(fast_info.items())
        return dict(fast_info or {})
    except Exception:
        return {}


@lru_cache(maxsize=1)
def sec_ticker_map() -> dict[str, str]:
    """Load SEC ticker to CIK mapping."""

    url = "https://www.sec.gov/files/company_tickers.json"
    response = _get(url)
    payload = response.json()
    return {
        item["ticker"].upper(): str(item["cik_str"]).zfill(10)
        for item in payload.values()
        if item.get("ticker") and item.get("cik_str")
    }


@lru_cache(maxsize=256)
def sec_company_facts(ticker: str) -> dict[str, Any]:
    """Load SEC XBRL company facts for a ticker."""

    cik = sec_ticker_map().get(normalize_symbol(ticker))
    if not cik:
        return {}
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    response = _get(url)
    return response.json()


def sec_fundamentals(ticker: str) -> dict[str, Any]:
    """Return useful SEC fundamentals when Yahoo quoteSummary is unavailable."""

    facts = sec_company_facts(ticker)
    revenue = latest_sec_value_from_any(
        facts,
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        annual_only=True,
    )
    net_income = latest_sec_value(facts, "NetIncomeLoss", annual_only=True)
    gross_profit = latest_sec_value(facts, "GrossProfit", annual_only=True)
    operating_income = latest_sec_value(facts, "OperatingIncomeLoss", annual_only=True)
    assets = latest_sec_value(facts, "Assets", annual_only=True)
    liabilities = latest_sec_value(facts, "Liabilities", annual_only=True)
    equity = latest_sec_value_from_any(
        facts,
        ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        annual_only=True,
    )
    cash = latest_sec_value_from_any(
        facts,
        ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        annual_only=True,
    )
    debt = latest_sec_value_from_any(
        facts,
        ["LongTermDebtAndFinanceLeaseObligationsCurrentAndNoncurrent", "LongTermDebt", "DebtCurrent"],
        annual_only=True,
    )
    shares = latest_sec_value_from_taxonomy(facts, "dei", "EntityCommonStockSharesOutstanding", annual_only=False)
    eps = latest_sec_value(facts, "EarningsPerShareDiluted", annual_only=True)
    return {
        "revenue": revenue,
        "net_income": net_income,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "cash": cash,
        "debt": debt,
        "shares": shares,
        "eps": eps,
    }


def latest_sec_value(facts: dict[str, Any], concept: str, *, annual_only: bool = False) -> float | None:
    """Return the latest USD value for a SEC us-gaap concept."""

    units = facts.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {})
    entries = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
    annual_entries = [
        item
        for item in entries
        if item.get("form") in ({"10-K"} if annual_only else {"10-K", "10-Q"})
        and item.get("val") is not None
        and item.get("end")
        and (not annual_only or ("Q" not in str(item.get("frame", ""))))
    ]
    if not annual_entries:
        return None
    latest = sorted(annual_entries, key=lambda item: item["end"])[-1]
    return float(latest["val"])


def latest_sec_value_from_any(
    facts: dict[str, Any],
    concepts: list[str],
    *,
    annual_only: bool = False,
) -> float | None:
    """Return the newest SEC value from the first concept with current data."""

    candidates = []
    for concept in concepts:
        units = facts.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {})
        entries = units.get("USD") or units.get("USD/shares") or units.get("shares") or []
        for item in entries:
            if item.get("form") not in ({"10-K"} if annual_only else {"10-K", "10-Q"}):
                continue
            if item.get("val") is None or not item.get("end"):
                continue
            if annual_only and "Q" in str(item.get("frame", "")):
                continue
            candidates.append(item)
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda item: item["end"])[-1]
    return float(latest["val"])


def latest_sec_value_from_taxonomy(
    facts: dict[str, Any],
    taxonomy: str,
    concept: str,
    *,
    annual_only: bool = False,
) -> float | None:
    """Return the latest value for a concept in a specific SEC taxonomy."""

    units = facts.get("facts", {}).get(taxonomy, {}).get(concept, {}).get("units", {})
    entries = []
    for unit_entries in units.values():
        entries.extend(unit_entries)
    filtered = [
        item
        for item in entries
        if item.get("form") in ({"10-K"} if annual_only else {"10-K", "10-Q"})
        and item.get("val") is not None
        and item.get("end")
        and (not annual_only or ("Q" not in str(item.get("frame", ""))))
    ]
    if not filtered:
        return None
    latest = sorted(filtered, key=lambda item: item["end"])[-1]
    return float(latest["val"])
