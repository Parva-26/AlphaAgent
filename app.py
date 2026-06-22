"""AlphaAgent Streamlit application."""

from __future__ import annotations

import uuid
from datetime import datetime
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from graph.debate_graph import run_debate_workflow
from graph.research_graph import run_research_workflow
from utils.config import COST_CONFIG, get_groq_api_key
from utils.cost_tracker import cost_tracker
from utils.formatters import currency, normalize_ticker, render_markdown_sections, safe_round
from utils.market_sources import get_company_name, latest_close, load_price_history_resilient, safe_fast_info, sec_fundamentals
from utils.rate_limiter import rate_limiter


load_dotenv()


st.set_page_config(
    page_title="AlphaAgent",
    page_icon="AA",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    """Apply futuristic cyan-on-black styling."""

    st.markdown(
        """
        <style>
        :root {
            --bg: #02050a;
            --panel: rgba(5, 13, 22, 0.88);
            --panel-2: rgba(8, 24, 38, 0.82);
            --ink: #e8fbff;
            --muted: #8fb9c4;
            --line: rgba(103, 232, 249, 0.24);
            --cyan: #67e8f9;
            --cyan-2: #22d3ee;
            --blue: #38bdf8;
            --green: #7dd3fc;
            --red: #fb7185;
        }

        .stApp {
            background:
                linear-gradient(rgba(103, 232, 249, 0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(103, 232, 249, 0.035) 1px, transparent 1px),
                radial-gradient(circle at 18% 0%, rgba(34, 211, 238, 0.18), transparent 28rem),
                linear-gradient(180deg, #02050a 0%, #04111d 58%, #02050a 100%);
            background-size: 44px 44px, 44px 44px, auto, auto;
            color: var(--ink);
        }

        section[data-testid="stSidebar"] {
            background: rgba(2, 8, 14, 0.96);
            border-right: 1px solid var(--line);
            box-shadow: 12px 0 40px rgba(34, 211, 238, 0.06);
        }

        .block-container {
            padding-top: 1.3rem;
            padding-bottom: 1.5rem;
            max-width: 1500px;
        }

        .alpha-header {
            border: 1px solid var(--line);
            background: linear-gradient(135deg, rgba(5, 13, 22, 0.94), rgba(9, 32, 50, 0.82));
            padding: 1.25rem 1.35rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            box-shadow: 0 0 32px rgba(34, 211, 238, 0.08), inset 0 1px 0 rgba(232, 251, 255, 0.08);
        }

        .alpha-title {
            font-size: 2.45rem;
            line-height: 1;
            font-weight: 800;
            letter-spacing: 0;
            margin: 0;
            color: var(--ink);
            text-shadow: 0 0 22px rgba(103, 232, 249, 0.45);
        }

        .alpha-subtitle {
            color: var(--muted);
            font-size: 0.98rem;
            margin-top: 0.35rem;
        }

        .status-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.75rem 0 1rem;
        }

        .metric-tile {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 0.8rem;
            min-height: 5.25rem;
            box-shadow: inset 0 1px 0 rgba(232, 251, 255, 0.06);
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 0.35rem;
        }

        .metric-value {
            color: var(--cyan);
            font-size: 1.45rem;
            font-weight: 750;
            overflow-wrap: anywhere;
        }

        .terminal-panel {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 1rem;
            box-shadow: inset 0 1px 0 rgba(232, 251, 255, 0.06);
        }

        .data-fallback {
            border: 1px solid rgba(103, 232, 249, 0.34);
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(5, 13, 22, 0.94), rgba(7, 26, 40, 0.84));
            padding: 1rem;
            color: var(--ink);
        }

        .data-fallback strong {
            color: var(--cyan);
            display: block;
            margin-bottom: 0.25rem;
        }

        .small-muted {
            color: var(--muted);
            font-size: 0.86rem;
        }

        .footer-budget {
            border-top: 1px solid var(--line);
            margin-top: 1.4rem;
            padding-top: 0.7rem;
            color: var(--muted);
            font-size: 0.85rem;
        }

        .stButton > button {
            width: 100%;
            border-radius: 8px;
            border: 1px solid rgba(103, 232, 249, 0.7);
            background: linear-gradient(135deg, #67e8f9, #38bdf8);
            color: #02050a;
            font-weight: 800;
            min-height: 2.8rem;
            box-shadow: 0 0 24px rgba(34, 211, 238, 0.22);
        }

        .stButton > button:hover {
            border-color: #e8fbff;
            box-shadow: 0 0 30px rgba(103, 232, 249, 0.34);
        }

        .stButton > button:disabled {
            color: #647986;
            background: #07111a;
            border-color: rgba(103, 232, 249, 0.16);
            box-shadow: none;
        }

        div[data-testid="stMetric"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.75rem;
            background: var(--panel);
        }

        div[data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid var(--line);
            background: rgba(5, 13, 22, 0.92);
        }

        @media (max-width: 900px) {
            .status-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .alpha-title {
                font-size: 1.9rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    """Initialize and reset session-local counters."""

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    today = datetime.utcnow().date().isoformat()
    if st.session_state.get("session_day") != today:
        st.session_state.session_day = today
        st.session_state.session_requests = 0
        st.session_state.session_tokens = 0
        st.session_state.last_result = None
        st.session_state.last_mode = None
        st.session_state.last_ticker = None


@st.cache_data(ttl=900, show_spinner=False)
def load_price_history(ticker: str) -> pd.DataFrame:
    """Load recent price history for the UI chart."""

    history, _ = load_price_history_resilient(ticker, period="1y")
    return history


@st.cache_data(ttl=900, show_spinner=False)
def load_company_snapshot(ticker: str) -> dict:
    """Load display-only company information."""

    history, source = load_price_history_resilient(ticker, period="1y")
    fast_info = safe_fast_info(ticker)
    try:
        sec = sec_fundamentals(ticker)
    except Exception:
        sec = {}
    price = fast_info.get("last_price") or fast_info.get("lastPrice") or latest_close(history)
    market_cap = fast_info.get("market_cap") or fast_info.get("marketCap")
    if not market_cap and price and sec.get("shares"):
        market_cap = price * sec["shares"]
    eps = sec.get("eps")
    return {
        "name": get_company_name(ticker),
        "sector": "N/A",
        "industry": "N/A",
        "price": price,
        "market_cap": market_cap,
        "forward_pe": (price / eps) if price and eps else None,
        "target_mean": None,
        "source": source,
    }


def build_price_chart(history: pd.DataFrame, ticker: str) -> go.Figure:
    """Create a compact terminal-style price chart."""

    fig = go.Figure()
    if not history.empty:
        fig.add_trace(
            go.Candlestick(
                x=history["Date"],
                open=history["Open"],
                high=history["High"],
                low=history["Low"],
                close=history["Close"],
                increasing_line_color="#67e8f9",
                decreasing_line_color="#fb7185",
                name=ticker,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=history["Date"],
                y=history["Close"].rolling(50).mean(),
                mode="lines",
                name="50D MA",
                line=dict(color="#38bdf8", width=1.6),
            )
        )

    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=28, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2, 8, 14, 0.74)",
        font=dict(color="#e8fbff"),
        title=dict(text=f"{ticker} 1Y Price Action", x=0.02, font=dict(size=16)),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
        yaxis=dict(gridcolor="rgba(103, 232, 249, 0.14)", tickprefix="$"),
        legend=dict(orientation="h", y=1.05, x=0.72),
    )
    return fig


def render_header() -> None:
    """Render app masthead."""

    st.markdown(
        """
        <div class="alpha-header">
          <div class="alpha-title">AlphaAgent</div>
          <div class="alpha-subtitle">
            Multi-agent AI investment research terminal powered by LangGraph, LangChain, Groq, yfinance, and DuckDuckGo.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_budget_sidebar() -> None:
    """Render request and budget status in the sidebar."""

    status = cost_tracker.get_status()
    session_status = rate_limiter.get_session_status(st.session_state.session_id)

    st.sidebar.markdown("### Groq Guardrails")
    st.sidebar.metric("Estimated Cost", status["total_cost"], f"{status['remaining_budget']} left")
    st.sidebar.metric(
        "Session Requests",
        f"{st.session_state.session_requests}",
        f"{session_status['hourly_remaining']} hourly left",
    )
    st.sidebar.metric(
        "Daily Capacity",
        f"{session_status['daily_used']} / {session_status['daily_limit']}",
        f"{session_status['daily_remaining']} left",
    )
    st.sidebar.metric("Session Tokens", f"{st.session_state.session_tokens:,}")

    st.sidebar.caption("Hard stop at $4.90 estimated Groq usage. Request limits reset by UTC day.")


def render_market_fallback(ticker: str, message: str) -> None:
    """Render a calm fallback when market data is unavailable."""

    st.markdown(
        f"""
        <div class="data-fallback">
          <strong>Market feed unavailable for {escape(ticker)}</strong>
          <div class="small-muted">
            {escape(message)} The research agents can still run with web search and financial tools when data returns.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_snapshot(ticker: str) -> None:
    """Render company snapshot and price chart."""

    try:
        snapshot = load_company_snapshot(ticker)
        history = load_price_history(ticker)
    except Exception as exc:
        render_market_fallback(ticker, f"Could not load the yfinance snapshot: {exc}")
        return

    if history.empty and not snapshot.get("price"):
        render_market_fallback(ticker, "Yahoo Finance returned no recent price data.")
        return

    company_name = escape(str(snapshot["name"]))

    st.markdown(
        f"""
        <div class="status-strip">
          <div class="metric-tile"><div class="metric-label">Company</div><div class="metric-value">{company_name}</div></div>
          <div class="metric-tile"><div class="metric-label">Price</div><div class="metric-value">{currency(snapshot['price'])}</div></div>
          <div class="metric-tile"><div class="metric-label">Market Cap</div><div class="metric-value">{currency(snapshot['market_cap'])}</div></div>
          <div class="metric-tile"><div class="metric-label">Forward P/E</div><div class="metric-value">{safe_round(snapshot['forward_pe'])}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_col, detail_col = st.columns([2.2, 1])
    with chart_col:
        st.plotly_chart(build_price_chart(history, ticker), use_container_width=True)
    with detail_col:
        st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
        st.markdown("#### Market Context")
        st.write(f"Sector: **{snapshot['sector']}**")
        st.write(f"Industry: **{snapshot['industry']}**")
        st.write(f"Mean target: **{currency(snapshot['target_mean'])}**")
        if not history.empty:
            start = history["Close"].iloc[0]
            end = history["Close"].iloc[-1]
            one_year = ((end / start) - 1) * 100 if start else 0
            st.write(f"1Y move: **{one_year:.2f}%**")
            st.write(f"1Y high: **{currency(history['High'].max())}**")
            st.write(f"1Y low: **{currency(history['Low'].min())}**")
        st.markdown(
            f'<div class="small-muted">Snapshot source: {escape(snapshot.get("source", "free market data"))}. Data may be delayed or incomplete.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def can_run_request() -> tuple[bool, str]:
    """Check all app-level request gates."""

    api_key = get_groq_api_key()
    if not api_key or api_key == "your_api_key_here":
        return False, "Add your Groq API key to .env as GROQ_API_KEY before running agent analysis."

    allowed, message = rate_limiter.is_allowed(st.session_state.session_id)
    if not allowed:
        return False, f"Rate limit: {message}"

    if not cost_tracker.can_afford_request():
        return False, "API budget limit reached. Free-tier guardrail has disabled further requests."

    return True, "OK"


def run_analysis(ticker: str, mode: str) -> dict | None:
    """Run the selected LangGraph workflow with rate and cost checks."""

    allowed, message = can_run_request()
    if not allowed:
        st.warning(message)
        return None

    before = cost_tracker.get_status()
    rate_limiter.log_request(st.session_state.session_id)
    st.session_state.session_requests += 1

    with st.spinner("Agents are gathering data, arguing the case, and writing the note..."):
        try:
            if mode == "Multi-Agent Debate":
                result = run_debate_workflow(ticker)
            else:
                result = run_research_workflow(ticker)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            return None

    after = cost_tracker.get_status()
    token_delta = int(after["total_tokens"]) - int(before["total_tokens"])
    st.session_state.session_tokens += max(0, token_delta)
    result["token_delta"] = max(0, token_delta)
    result["cost_delta"] = float(after["raw_total_cost"]) - float(before["raw_total_cost"])
    return result


def render_result(result: dict, mode: str) -> None:
    """Render analysis output."""

    if not result:
        return
    if result.get("error"):
        st.error(result["error"])
        return

    st.success(
        f"Analysis complete. Tokens used: {result.get('token_delta', 0):,}. "
        f"Estimated cost: ${result.get('cost_delta', 0):.4f}."
    )

    if mode == "Multi-Agent Debate":
        tabs = st.tabs(["Research Note", "Bull Agent", "Bear Agent", "Arbiter Verdict"])
        with tabs[0]:
            st.markdown(result.get("research_note", "No research note returned."))
        with tabs[1]:
            st.markdown(render_markdown_sections(result.get("bull_thesis", "No bull thesis returned.")))
        with tabs[2]:
            st.markdown(render_markdown_sections(result.get("bear_thesis", "No bear thesis returned.")))
        with tabs[3]:
            st.markdown(render_markdown_sections(result.get("verdict", "No verdict returned.")))
    else:
        st.markdown(result.get("research_note", "No research note returned."))


def render_footer() -> None:
    """Render running budget status in the footer."""

    status = cost_tracker.get_status()
    st.markdown('<div class="footer-budget">', unsafe_allow_html=True)
    if status["budget_exceeded"]:
        st.error("API budget exceeded. Free-tier limit reached.")
    else:
        st.caption(
            f"Cost: {status['total_cost']} / ${COST_CONFIG.displayed_free_tier_usd:.2f} | "
            f"Requests: {status['total_requests']} | "
            f"Budget: {status['remaining_budget']} | "
            "Educational research only, not investment advice."
        )
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    """Run the Streamlit app."""

    inject_css()
    init_session_state()
    render_header()

    st.sidebar.markdown("## Research Console")
    ticker = normalize_ticker(st.sidebar.text_input("Ticker", value="AAPL", max_chars=12))
    mode = st.sidebar.radio("Workflow", ["Multi-Agent Debate", "Deep Research"], index=0)
    run_button = st.sidebar.button("Run Analysis", disabled=cost_tracker.get_status()["budget_exceeded"])
    render_budget_sidebar()

    if ticker:
        render_snapshot(ticker)
    else:
        st.info("Enter a ticker to begin.")

    if run_button and ticker:
        result = run_analysis(ticker, mode)
        if result:
            st.session_state.last_result = result
            st.session_state.last_mode = mode
            st.session_state.last_ticker = ticker

    if st.session_state.get("last_result"):
        st.markdown("## Agent Output")
        st.caption(f"{st.session_state.last_mode} for {st.session_state.last_ticker}")
        render_result(st.session_state.last_result, st.session_state.last_mode)
    else:
        st.markdown(
            """
            <div class="terminal-panel">
              <strong>Ready.</strong>
              <div class="small-muted">
                Choose a workflow and run analysis. AlphaAgent will use only free data sources:
                yfinance for market and financial data, DuckDuckGo for web research, and Groq for agent reasoning.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_footer()


if __name__ == "__main__":
    main()
