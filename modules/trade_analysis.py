"""
trade_analysis.py
─────────────────
Deep-dive investigation module.
Generates detailed trade info cards and contextual candlestick charts
with optional EMA overlays for individual trade drill-down.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.data_loader import get_price_window


# ── Styling constants ────────────────────────────────────────────────
COLOR_ENTRY = "#00c9a7"
COLOR_EXIT = "#ff6b6b"
COLOR_BULL = "#26a69a"
COLOR_BEAR = "#ef5350"
COLOR_EMA20 = "#ffd93d"
COLOR_EMA50 = "#4d96ff"


def get_trade_details(df: pd.DataFrame, trade_id: int) -> dict:
    """
    Extract all relevant fields for a single trade as a dict.
    Returns None if trade_id not found.
    """
    row = df[df["trade_id"] == trade_id]
    if row.empty:
        return None

    row = row.iloc[0]
    return {
        "Trade ID": int(row["trade_id"]),
        "Direction": row["direction"],
        "Entry Time": row["entry_time"],
        "Exit Time": row["exit_time"],
        "Entry Price": round(float(row["entry_price"]), 5),
        "Exit Price": round(float(row["exit_price"]), 5),
        "Duration (min)": float(row["duration_minutes"]),
        "PnL (pips)": float(row["pnl_pips"]),
        "Exit Reason": row["exit_reason"],
    }


def create_candlestick_chart(
    prices: pd.DataFrame,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    entry_price: float,
    exit_price: float,
    direction: str,
    show_ema_20: bool = False,
    show_ema_50: bool = False,
) -> go.Figure:
    """
    Create a Plotly candlestick chart centred on a specific trade.
    Overlays entry/exit markers and optional EMA indicators.

    Parameters
    ----------
    prices : pd.DataFrame
        The full prices dataframe (will be sliced internally).
    entry_time / exit_time : pd.Timestamp
        Trade boundaries.
    entry_price / exit_price : float
        For marker placement on the y-axis.
    direction : str
        'Long' or 'Short'.
    show_ema_20 : bool
        If True, overlay a 20-period EMA on the chart.
    show_ema_50 : bool
        If True, overlay a 50-period EMA on the chart.
    """
    # Widen the price window when EMAs are enabled so they have
    # enough history to warm up before the visible trade area.
    extra_before = 60 if (show_ema_20 or show_ema_50) else 30
    window = get_price_window(prices, entry_time, exit_time,
                              before_minutes=extra_before, after_minutes=30)

    if window.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No price data available for this time window",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="#ff6b6b"),
        )
        fig.update_layout(template="plotly_dark")
        return fig

    # ── Base candlestick ─────────────────────────────────────────
    fig = go.Figure(data=[
        go.Candlestick(
            x=window["time"],
            open=window["open"],
            high=window["high"],
            low=window["low"],
            close=window["close"],
            increasing_line_color=COLOR_BULL,
            decreasing_line_color=COLOR_BEAR,
            name="EURUSD M1",
        )
    ])

    # ── EMA overlays ─────────────────────────────────────────────
    if show_ema_20:
        ema20 = window["close"].ewm(span=20, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=window["time"], y=ema20,
            mode="lines",
            line=dict(color=COLOR_EMA20, width=1.5),
            name="EMA 20",
            opacity=0.85,
        ))

    if show_ema_50:
        ema50 = window["close"].ewm(span=50, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=window["time"], y=ema50,
            mode="lines",
            line=dict(color=COLOR_EMA50, width=1.5),
            name="EMA 50",
            opacity=0.85,
        ))

    # ── Entry marker ─────────────────────────────────────────────
    entry_symbol = "triangle-up" if direction == "Long" else "triangle-down"
    entry_pos = "top center" if direction == "Long" else "bottom center"
    fig.add_trace(go.Scatter(
        x=[entry_time], y=[entry_price],
        mode="markers+text",
        marker=dict(size=14, color=COLOR_ENTRY, symbol=entry_symbol),
        text=[f"ENTRY ({direction})"],
        textposition=entry_pos,
        textfont=dict(color=COLOR_ENTRY, size=11),
        name="Entry", showlegend=True,
    ))

    # ── Exit marker ──────────────────────────────────────────────
    exit_symbol = "triangle-down" if direction == "Long" else "triangle-up"
    exit_pos = "bottom center" if direction == "Long" else "top center"
    fig.add_trace(go.Scatter(
        x=[exit_time], y=[exit_price],
        mode="markers+text",
        marker=dict(size=14, color=COLOR_EXIT, symbol=exit_symbol),
        text=["EXIT"],
        textposition=exit_pos,
        textfont=dict(color=COLOR_EXIT, size=11),
        name="Exit", showlegend=True,
    ))

    # ── Layout polish ────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        title=f"Market Context — {direction} Trade",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=True,   # zoom slider enabled
        hovermode="x unified",            # rich hover tooltips
        margin=dict(t=50, b=30, l=50, r=20),
        height=500,
    )

    return fig


def render_trade_investigation(
    trades: pd.DataFrame,
    prices: pd.DataFrame,
    selected_trade_id: int | None,
    key_prefix: str = "investigation",
    heading: str = "### 🔍 Trade Investigation",
) -> None:
    """
    Render trade details and the surrounding candlestick chart for one trade.
    """
    if selected_trade_id is None:
        st.info("Select a trade to investigate it in detail.")
        return

    st.markdown(f"{heading} — #{selected_trade_id}")
    details = get_trade_details(trades, selected_trade_id)

    if not details:
        st.warning(
            f"Trade ID {selected_trade_id} was not found in the current filtered dataset."
        )
        return

    info_col, chart_col = st.columns([1, 3])

    with info_col:
        st.markdown("**Trade Details**")
        for key, value in details.items():
            if key == "PnL (pips)":
                color = "green" if value >= 0 else "red"
                st.markdown(f"**{key}:** :{color}[{value:+.1f}]")
            elif isinstance(value, pd.Timestamp):
                st.markdown(f"**{key}:** {value.strftime('%Y-%m-%d %H:%M')}")
            else:
                st.markdown(f"**{key}:** {value}")

        st.markdown("---")
        st.markdown("**Indicators**")
        show_ema_20 = st.checkbox("Show EMA 20", value=False, key=f"{key_prefix}_ema20")
        show_ema_50 = st.checkbox("Show EMA 50", value=False, key=f"{key_prefix}_ema50")

    with chart_col:
        fig = create_candlestick_chart(
            prices=prices,
            entry_time=details["Entry Time"],
            exit_time=details["Exit Time"],
            entry_price=details["Entry Price"],
            exit_price=details["Exit Price"],
            direction=details["Direction"],
            show_ema_20=show_ema_20,
            show_ema_50=show_ema_50,
        )
        st.plotly_chart(fig, use_container_width=True)
