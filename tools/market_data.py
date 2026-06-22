"""Free market data tools backed by yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf
from langchain.tools import tool

from utils.formatters import compact_number, currency, percent, safe_round
from utils.market_sources import (
    get_company_name,
    latest_close,
    load_price_history_resilient,
    safe_fast_info,
    sec_fundamentals,
)


def _ticker(ticker: str) -> yf.Ticker:
    return yf.Ticker(ticker.strip().upper())


def _safe_get(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _latest_value(frame: pd.DataFrame, labels: list[str]) -> Any:
    if frame is None or frame.empty:
        return None
    for label in labels:
        if label in frame.index:
            series = frame.loc[label].dropna()
            if not series.empty:
                return series.iloc[0]
    return None


def _last_n_values(frame: pd.DataFrame, labels: list[str], n: int = 4) -> list[float]:
    if frame is None or frame.empty:
        return []
    for label in labels:
        if label in frame.index:
            return [float(v) for v in frame.loc[label].dropna().head(n).tolist()]
    return []


def _compute_rsi(close: pd.Series, window: int = 14) -> float | None:
    if close is None or len(close) < window + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    latest = rsi.dropna()
    return float(latest.iloc[-1]) if not latest.empty else None


@tool
def get_stock_price(ticker: str) -> dict:
    """Get current stock price, trading range, volume, and market cap for a ticker."""

    try:
        history, source = load_price_history_resilient(ticker, period="1y")
        fast_info = safe_fast_info(ticker)
        latest = latest_close(history)
        latest_row = history.dropna(subset=["Close"]).iloc[-1] if not history.empty else {}

        current_price = fast_info.get("last_price") or fast_info.get("lastPrice") or latest
        day_high = fast_info.get("day_high") or fast_info.get("dayHigh") or latest_row.get("High")
        day_low = fast_info.get("day_low") or fast_info.get("dayLow") or latest_row.get("Low")
        volume = fast_info.get("last_volume") or fast_info.get("lastVolume") or latest_row.get("Volume")
        market_cap = fast_info.get("market_cap") or fast_info.get("marketCap")
        if not market_cap and current_price:
            try:
                sec = sec_fundamentals(ticker)
                if sec.get("shares"):
                    market_cap = current_price * sec["shares"]
            except Exception:
                pass

        return {
            "ticker": ticker.upper(),
            "company": get_company_name(ticker),
            "sector": "N/A",
            "industry": "N/A",
            "current_price": safe_round(current_price),
            "day_high": safe_round(day_high),
            "day_low": safe_round(day_low),
            "52_week_high": safe_round(history["High"].max() if "High" in history else None),
            "52_week_low": safe_round(history["Low"].min() if "Low" in history else None),
            "volume": compact_number(volume),
            "market_cap": currency(market_cap),
            "currency": fast_info.get("currency", "USD"),
            "source": source,
        }
    except Exception as exc:
        return {"ticker": ticker.upper(), "error": f"Could not fetch stock price: {exc}"}


@tool
def get_financial_statements(ticker: str) -> dict:
    """Get financial statement highlights and balance-sheet health for a ticker."""

    yahoo_error = None
    try:
        stock = _ticker(ticker)
        info = {}
        try:
            info = stock.info or {}
        except Exception:
            info = {}
        quarterly_income = stock.quarterly_financials
        annual_income = stock.financials
        balance_sheet = stock.balance_sheet

        revenue_values = _last_n_values(
            quarterly_income,
            ["Total Revenue", "Operating Revenue"],
            n=4,
        )
        annual_revenue = _latest_value(annual_income, ["Total Revenue", "Operating Revenue"])
        net_income = _latest_value(annual_income, ["Net Income", "Net Income Common Stockholders"])
        gross_profit = _latest_value(annual_income, ["Gross Profit"])
        operating_income = _latest_value(annual_income, ["Operating Income"])

        total_debt = _latest_value(balance_sheet, ["Total Debt", "Long Term Debt"])
        cash = _latest_value(
            balance_sheet,
            ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
        )
        total_equity = _latest_value(balance_sheet, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
        current_assets = _latest_value(balance_sheet, ["Current Assets", "Total Current Assets"])
        current_liabilities = _latest_value(balance_sheet, ["Current Liabilities", "Total Current Liabilities Net Minority Interest"])

        gross_margin = (gross_profit / annual_revenue) if gross_profit and annual_revenue else info.get("grossMargins")
        operating_margin = (
            (operating_income / annual_revenue) if operating_income and annual_revenue else info.get("operatingMargins")
        )
        net_margin = (net_income / annual_revenue) if net_income and annual_revenue else info.get("profitMargins")
        debt_to_equity = (total_debt / total_equity) if total_debt and total_equity else info.get("debtToEquity")
        current_ratio = (
            (current_assets / current_liabilities) if current_assets and current_liabilities else info.get("currentRatio")
        )

        if not any(
            value is not None
            for value in [annual_revenue, net_income, gross_profit, operating_income, total_debt, cash, total_equity]
        ):
            raise ValueError("Yahoo Finance returned empty financial statements.")

        return {
            "ticker": ticker.upper(),
            "revenue_last_4_quarters": [currency(v) for v in revenue_values],
            "annual_revenue": currency(annual_revenue),
            "net_income": currency(net_income),
            "eps_trailing_twelve_months": safe_round(info.get("trailingEps")),
            "gross_margin": percent(gross_margin),
            "operating_margin": percent(operating_margin),
            "net_margin": percent(net_margin),
            "total_debt": currency(total_debt),
            "cash_and_equivalents": currency(cash),
            "debt_to_equity": safe_round(debt_to_equity),
            "current_ratio": safe_round(current_ratio),
            "source": "Yahoo Finance statements",
        }
    except Exception as exc:
        yahoo_error = exc
        try:
            sec = sec_fundamentals(ticker)
            revenue = sec.get("revenue")
            net_income = sec.get("net_income")
            gross_profit = sec.get("gross_profit")
            operating_income = sec.get("operating_income")
            assets = sec.get("assets")
            liabilities = sec.get("liabilities")
            equity = sec.get("equity")
            cash = sec.get("cash")
            debt = sec.get("debt")
            eps = sec.get("eps")

            if not any(value is not None for value in [revenue, net_income, assets, liabilities, eps]):
                return {"ticker": ticker.upper(), "error": f"Could not fetch financial statements: {yahoo_error}"}

            net_margin = (net_income / revenue) if net_income and revenue else None
            gross_margin = (gross_profit / revenue) if gross_profit and revenue else None
            operating_margin = (operating_income / revenue) if operating_income and revenue else None
            debt_to_equity = (debt / equity) if debt and equity else None
            current_ratio = (assets / liabilities) if assets and liabilities else None
            return {
                "ticker": ticker.upper(),
                "revenue_last_4_quarters": [],
                "annual_revenue": currency(revenue),
                "net_income": currency(net_income),
                "eps_trailing_twelve_months": safe_round(eps),
                "gross_margin": percent(gross_margin),
                "operating_margin": percent(operating_margin),
                "net_margin": percent(net_margin),
                "total_debt": currency(debt),
                "cash_and_equivalents": currency(cash),
                "debt_to_equity": safe_round(debt_to_equity),
                "current_ratio": safe_round(current_ratio),
                "source": "SEC Company Facts fallback",
            }
        except Exception as fallback_exc:
            return {
                "ticker": ticker.upper(),
                "error": f"Could not fetch financial statements: {yahoo_error}; SEC fallback also failed: {fallback_exc}",
            }


@tool
def get_stock_history(ticker: str, period: str = "1y") -> dict:
    """Get historical price summary, moving averages, RSI, and volume data."""

    try:
        history, source = load_price_history_resilient(ticker, period=period)
        if history.empty:
            return {"ticker": ticker.upper(), "error": "No historical price data returned."}

        close = history["Close"].dropna()
        volume = history["Volume"].dropna()
        latest_close = close.iloc[-1]
        start_close = close.iloc[0]
        return_pct = ((latest_close / start_close) - 1) * 100 if start_close else None

        ma_50 = close.rolling(50).mean().dropna()
        ma_200 = close.rolling(200).mean().dropna()
        rsi = _compute_rsi(close)

        return {
            "ticker": ticker.upper(),
            "period": period,
            "latest_close": safe_round(latest_close),
            "period_return": percent(return_pct),
            "period_high": safe_round(close.max()),
            "period_low": safe_round(close.min()),
            "50_day_ma": safe_round(ma_50.iloc[-1] if not ma_50.empty else None),
            "200_day_ma": safe_round(ma_200.iloc[-1] if not ma_200.empty else None),
            "rsi_14": safe_round(rsi),
            "average_volume": compact_number(volume.mean() if not volume.empty else None),
            "trend_signal": "Bullish" if not ma_50.empty and not ma_200.empty and ma_50.iloc[-1] > ma_200.iloc[-1] else "Neutral/Bearish",
            "source": source,
        }
    except Exception as exc:
        return {"ticker": ticker.upper(), "error": f"Could not fetch stock history: {exc}"}


@tool
def get_analyst_info(ticker: str) -> dict:
    """Get analyst recommendations, target prices, and earnings estimate highlights."""

    try:
        stock = _ticker(ticker)
        info = stock.info or {}
        recommendations = stock.recommendations

        latest_recommendations = []
        if recommendations is not None and not recommendations.empty:
            latest = recommendations.tail(5).reset_index()
            for _, row in latest.iterrows():
                latest_recommendations.append(
                    {
                        "firm": str(row.get("Firm", "N/A")),
                        "to_grade": str(row.get("To Grade", "N/A")),
                        "action": str(row.get("Action", "N/A")),
                    }
                )

        return {
            "ticker": ticker.upper(),
            "recommendation_key": info.get("recommendationKey", "N/A"),
            "recommendation_mean": safe_round(info.get("recommendationMean")),
            "target_mean_price": currency(info.get("targetMeanPrice")),
            "target_high_price": currency(info.get("targetHighPrice")),
            "target_low_price": currency(info.get("targetLowPrice")),
            "number_of_analysts": info.get("numberOfAnalystOpinions", "N/A"),
            "forward_eps": safe_round(info.get("forwardEps")),
            "earnings_growth": percent(info.get("earningsGrowth")),
            "revenue_growth": percent(info.get("revenueGrowth")),
            "latest_recommendations": latest_recommendations,
        }
    except Exception as exc:
        return {
            "ticker": ticker.upper(),
            "recommendation_key": "N/A",
            "recommendation_mean": "N/A",
            "target_mean_price": "N/A",
            "target_high_price": "N/A",
            "target_low_price": "N/A",
            "number_of_analysts": "N/A",
            "forward_eps": "N/A",
            "earnings_growth": "N/A",
            "revenue_growth": "N/A",
            "latest_recommendations": [],
            "source": f"Yahoo analyst endpoint unavailable: {exc}",
        }
