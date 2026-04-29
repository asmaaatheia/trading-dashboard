"""
filters.py
──────────
Sidebar filter panel for the trading dashboard.
Renders Streamlit widgets and returns a filtered DataFrame
that all downstream charts, KPIs, and tables consume.
"""

import streamlit as st
import pandas as pd


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Render sidebar filter controls and return the filtered DataFrame.
    All filters are applied cumulatively (AND logic).

    Parameters
    ----------
    df : pd.DataFrame
        The full trades DataFrame (must have entry_time, direction,
        exit_reason, entry_hour, pnl_pips, duration_minutes columns).

    Returns
    -------
    pd.DataFrame
        Filtered copy of the input DataFrame.
    """
    st.sidebar.markdown("## 🔧 Filters")
    st.sidebar.markdown("---")

    filtered = df.copy()

    # ── Direction filter ─────────────────────────────────────────
    direction_filter = st.sidebar.radio(
        "Direction",
        options=["Both", "Long only", "Short only"],
        index=0,
        key="filter_direction",
    )
    if direction_filter == "Long only":
        filtered = filtered[filtered["direction"] == "Long"]
    elif direction_filter == "Short only":
        filtered = filtered[filtered["direction"] == "Short"]

    # ── Exit reason filter ───────────────────────────────────────
    reasons = sorted(df["exit_reason"].unique().tolist())
    selected_reasons = st.sidebar.multiselect(
        "Exit Reason",
        options=reasons,
        default=reasons,
        key="filter_exit_reason",
    )
    if selected_reasons:
        filtered = filtered[filtered["exit_reason"].isin(selected_reasons)]

    st.sidebar.markdown("---")

    # ── Entry hour range ─────────────────────────────────────────
    hour_min, hour_max = int(df["entry_hour"].min()), int(df["entry_hour"].max())
    selected_hours = st.sidebar.slider(
        "Entry Hour Range",
        min_value=hour_min,
        max_value=hour_max,
        value=(hour_min, hour_max),
        key="filter_hours",
    )
    filtered = filtered[
        (filtered["entry_hour"] >= selected_hours[0])
        & (filtered["entry_hour"] <= selected_hours[1])
    ]

    # ── PnL range (pips) ────────────────────────────────────────
    pnl_min = float(df["pnl_pips"].min())
    pnl_max = float(df["pnl_pips"].max())
    selected_pnl = st.sidebar.slider(
        "PnL Range (pips)",
        min_value=pnl_min,
        max_value=pnl_max,
        value=(pnl_min, pnl_max),
        step=0.1,
        key="filter_pnl",
    )
    filtered = filtered[
        (filtered["pnl_pips"] >= selected_pnl[0])
        & (filtered["pnl_pips"] <= selected_pnl[1])
    ]

    st.sidebar.markdown("---")

    # ── Date range ───────────────────────────────────────────────
    date_min = df["entry_time"].min().date()
    date_max = df["entry_time"].max().date()
    selected_dates = st.sidebar.date_input(
        "Date Range",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
        key="filter_dates",
    )
    # date_input returns a tuple when given a range default
    if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        filtered = filtered[
            (filtered["entry_time"].dt.date >= start_date)
            & (filtered["entry_time"].dt.date <= end_date)
        ]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Showing **{len(filtered)}** / {len(df)} trades")

    # ── CSV Export ───────────────────────────────────────────────
    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Download Filtered Trades",
        data=csv_data,
        file_name="filtered_trades.csv",
        mime="text/csv",
        key="download_filtered_trades",
    )

    return filtered
