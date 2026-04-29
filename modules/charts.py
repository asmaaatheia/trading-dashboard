"""
charts.py
─────────
Interactive Plotly chart factory for the trading dashboard.
Each function returns a plotly Figure object ready for st.plotly_chart().
Includes: exit reason, PnL distribution, hourly analysis,
equity curve, session analysis, and duration analysis charts.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from modules import statistics as stats


# ── Shared styling constants ─────────────────────────────────────────
TEMPLATE = "plotly_dark"
COLOR_WIN = "#00c9a7"
COLOR_LOSS = "#ff6b6b"
COLOR_NEUTRAL = "#7c8db5"
COLOR_EQUITY = "#6c63ff"
COLOR_DRAWDOWN = "#ff6b6b"

SESSION_COLORS = {
    "Asia": "#ffd93d",
    "London": "#6bcb77",
    "New York": "#4d96ff",
    "Other": "#7c8db5",
}

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# ═══════════════════════════════════════════════════════════════════
# ORIGINAL CHARTS
# ═══════════════════════════════════════════════════════════════════

def exit_reason_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart showing count of trades grouped by exit_reason."""
    counts = df["exit_reason"].value_counts().reset_index()
    counts.columns = ["Exit Reason", "Count"]
    color_map = {"TP": COLOR_WIN, "SL": COLOR_LOSS}

    fig = px.bar(
        counts, x="Exit Reason", y="Count",
        color="Exit Reason", color_discrete_map=color_map,
        template=TEMPLATE, title="Trades by Exit Reason",
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=30, l=30, r=20))
    return fig


def pnl_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Histogram of PnL (pips) distribution, colour-coded win/loss."""
    df_copy = df.copy()
    df_copy["outcome"] = df_copy["pnl_pips"].apply(
        lambda x: "Win" if x > 0 else "Loss"
    )
    color_map = {"Win": COLOR_WIN, "Loss": COLOR_LOSS}

    fig = px.histogram(
        df_copy, x="pnl_pips", color="outcome",
        color_discrete_map=color_map, nbins=30,
        template=TEMPLATE, title="PnL Distribution (pips)",
        labels={"pnl_pips": "PnL (pips)"},
    )
    fig.update_layout(barmode="overlay", margin=dict(t=40, b=30, l=30, r=20))
    fig.update_traces(opacity=0.75)
    return fig


def trades_by_hour_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of trade count by entry hour (0-23)."""
    hourly = df.groupby("entry_hour").size().reset_index(name="Count")
    fig = px.bar(
        hourly, x="entry_hour", y="Count",
        template=TEMPLATE, title="Trades by Entry Hour",
        labels={"entry_hour": "Hour (UTC)", "Count": "Number of Trades"},
        color_discrete_sequence=[COLOR_NEUTRAL],
    )
    fig.update_layout(margin=dict(t=40, b=30, l=30, r=20))
    return fig


def avg_pnl_by_hour_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of average PnL (pips) by entry hour. Green=positive, red=negative."""
    hourly = df.groupby("entry_hour")["pnl_pips"].mean().reset_index()
    hourly.columns = ["Hour", "Avg PnL (pips)"]
    hourly["color"] = hourly["Avg PnL (pips)"].apply(
        lambda x: COLOR_WIN if x >= 0 else COLOR_LOSS
    )

    fig = go.Figure(go.Bar(
        x=hourly["Hour"], y=hourly["Avg PnL (pips)"],
        marker_color=hourly["color"],
    ))
    fig.update_layout(
        template=TEMPLATE, title="Average PnL by Entry Hour",
        xaxis_title="Hour (UTC)", yaxis_title="Avg PnL (pips)",
        margin=dict(t=40, b=30, l=30, r=20),
    )
    return fig


def trades_by_weekday_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap of trade count by weekday and entry hour."""
    df_copy = df.copy()
    df_copy["weekday"] = df_copy["entry_time"].dt.day_name()

    pivot = df_copy.pivot_table(
        index="weekday",
        columns="entry_hour",
        values="trade_id",
        aggfunc="count",
        fill_value=0,
    )
    pivot = pivot.reindex(WEEKDAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)), fill_value=0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Blues",
            hovertemplate=(
                "Weekday: %{y}<br>"
                "Hour: %{x}:00<br>"
                "Trades: %{z}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Trade Count by Weekday & Entry Hour",
        xaxis_title="Entry Hour (UTC)",
        yaxis_title="Weekday",
        margin=dict(t=45, b=30, l=30, r=20),
        height=360,
    )
    return fig


def avg_pnl_by_weekday_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap of average PnL by weekday and entry hour."""
    df_copy = df.copy()
    df_copy["weekday"] = df_copy["entry_time"].dt.day_name()

    pivot = df_copy.pivot_table(
        index="weekday",
        columns="entry_hour",
        values="pnl_pips",
        aggfunc="mean",
    )
    pivot = pivot.reindex(WEEKDAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)))

    max_abs = float(pivot.abs().max().max()) if not pivot.empty else 1.0
    max_abs = max(max_abs, 1.0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="RdYlGn",
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            hovertemplate=(
                "Weekday: %{y}<br>"
                "Hour: %{x}:00<br>"
                "Avg PnL: %{z:.2f} pips<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Average PnL by Weekday & Entry Hour",
        xaxis_title="Entry Hour (UTC)",
        yaxis_title="Weekday",
        margin=dict(t=45, b=30, l=30, r=20),
        height=360,
    )
    return fig


def total_pnl_by_weekday_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap of total PnL by weekday and entry hour."""
    df_copy = df.copy()
    df_copy["weekday"] = df_copy["entry_time"].dt.day_name()

    pivot = df_copy.pivot_table(
        index="weekday",
        columns="entry_hour",
        values="pnl_pips",
        aggfunc="sum",
        fill_value=0,
    )
    pivot = pivot.reindex(WEEKDAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)), fill_value=0)

    max_abs = float(pivot.abs().max().max()) if not pivot.empty else 1.0
    max_abs = max(max_abs, 1.0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="RdYlGn",
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            hovertemplate=(
                "Weekday: %{y}<br>"
                "Hour: %{x}:00<br>"
                "Total PnL: %{z:.1f} pips<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Total PnL by Weekday & Entry Hour",
        xaxis_title="Entry Hour (UTC)",
        yaxis_title="Weekday",
        margin=dict(t=45, b=30, l=30, r=20),
        height=360,
    )
    return fig


def mae_by_weekday_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap of average MAE by weekday and entry hour."""
    df_copy = df.copy()
    df_copy["weekday"] = df_copy["entry_time"].dt.day_name()

    pivot = df_copy.pivot_table(
        index="weekday",
        columns="entry_hour",
        values="mae",
        aggfunc="mean",
    )
    pivot = pivot.reindex(WEEKDAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)))

    min_mae = float(np.nanmin(pivot.values)) if not pivot.empty else -1.0
    min_mae = min(min_mae, -1.0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Reds_r",
            zmax=0,
            zmin=min_mae,
            hovertemplate=(
                "Weekday: %{y}<br>"
                "Hour: %{x}:00<br>"
                "Avg MAE: %{z:.2f} pips<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Average MAE by Weekday & Entry Hour",
        xaxis_title="Entry Hour (UTC)",
        yaxis_title="Weekday",
        margin=dict(t=45, b=30, l=30, r=20),
        height=360,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════
# EQUITY CURVE
# ═══════════════════════════════════════════════════════════════════

def equity_curve_chart(df: pd.DataFrame) -> go.Figure:
    """
    Line chart of cumulative PnL over time with max drawdown shading.
    """
    equity = stats.compute_equity_curve(df)

    fig = go.Figure()

    # Cumulative PnL line
    fig.add_trace(go.Scatter(
        x=equity["entry_time"],
        y=equity["cumulative_pnl"],
        mode="lines",
        line=dict(color=COLOR_EQUITY, width=2),
        name="Cumulative PnL",
        fill="tozeroy",
        fillcolor="rgba(108, 99, 255, 0.1)",
    ))

    # Running max line (for drawdown reference)
    running_max = equity["cumulative_pnl"].cummax()
    fig.add_trace(go.Scatter(
        x=equity["entry_time"],
        y=running_max,
        mode="lines",
        line=dict(color=COLOR_WIN, width=1, dash="dot"),
        name="Peak Equity",
        opacity=0.5,
    ))

    fig.update_layout(
        template=TEMPLATE,
        title="Equity Curve (Cumulative PnL in Pips)",
        xaxis_title="Time",
        yaxis_title="Cumulative PnL (pips)",
        margin=dict(t=50, b=30, l=50, r=20),
        height=350,
        hovermode="x unified",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════
# SESSION ANALYSIS CHARTS
# ═══════════════════════════════════════════════════════════════════

def session_count_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of trade count by trading session."""
    ss = stats.session_stats(df)
    fig = px.bar(
        ss, x="session", y="count",
        color="session", color_discrete_map=SESSION_COLORS,
        template=TEMPLATE, title="Trades by Session",
        labels={"session": "Session", "count": "Count"},
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=30, l=30, r=20))
    return fig


def session_pnl_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of average PnL by trading session."""
    ss = stats.session_stats(df)
    ss["color"] = ss["avg_pnl"].apply(lambda x: COLOR_WIN if x >= 0 else COLOR_LOSS)

    fig = go.Figure(go.Bar(
        x=ss["session"], y=ss["avg_pnl"],
        marker_color=ss["color"],
    ))
    fig.update_layout(
        template=TEMPLATE, title="Avg PnL by Session",
        xaxis_title="Session", yaxis_title="Avg PnL (pips)",
        margin=dict(t=40, b=30, l=30, r=20),
    )
    return fig


def session_winrate_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of win rate by trading session."""
    ss = stats.session_stats(df)

    fig = px.bar(
        ss, x="session", y="win_rate",
        color="session", color_discrete_map=SESSION_COLORS,
        template=TEMPLATE, title="Win Rate by Session",
        labels={"session": "Session", "win_rate": "Win Rate (%)"},
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=30, l=30, r=20))
    # Add 50% reference line
    fig.add_hline(y=50, line_dash="dash", line_color="#555", opacity=0.7)
    return fig


# ═══════════════════════════════════════════════════════════════════
# DURATION ANALYSIS CHARTS
# ═══════════════════════════════════════════════════════════════════

def duration_count_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of trade count per duration bucket."""
    ds = stats.duration_stats(df)
    fig = px.bar(
        ds, x="bucket", y="count",
        template=TEMPLATE, title="Trades by Duration",
        labels={"bucket": "Duration", "count": "Count"},
        color_discrete_sequence=[COLOR_NEUTRAL],
    )
    fig.update_layout(margin=dict(t=40, b=30, l=30, r=20))
    return fig


def duration_pnl_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of average PnL per duration bucket."""
    ds = stats.duration_stats(df)
    ds["color"] = ds["avg_pnl"].apply(lambda x: COLOR_WIN if x >= 0 else COLOR_LOSS)

    fig = go.Figure(go.Bar(
        x=ds["bucket"], y=ds["avg_pnl"],
        marker_color=ds["color"],
    ))
    fig.update_layout(
        template=TEMPLATE, title="Avg PnL by Duration",
        xaxis_title="Duration", yaxis_title="Avg PnL (pips)",
        margin=dict(t=40, b=30, l=30, r=20),
    )
    return fig


def pnl_violin_by_hour_chart(df: pd.DataFrame) -> go.Figure:
    """Violin chart of trade PnL by entry hour."""
    fig = px.violin(
        df,
        x="entry_hour",
        y="pnl_pips",
        box=True,
        points="all",
        template=TEMPLATE,
        title="PnL Distribution by Entry Hour",
        labels={"entry_hour": "Hour (UTC)", "pnl_pips": "PnL (pips)"},
    )
    fig.update_layout(margin=dict(t=45, b=30, l=30, r=20), showlegend=False)
    return fig


def mae_violin_by_hour_chart(df: pd.DataFrame) -> go.Figure:
    """Violin chart of MAE by entry hour."""
    fig = px.violin(
        df,
        x="entry_hour",
        y="mae",
        box=True,
        points="all",
        template=TEMPLATE,
        title="MAE Distribution by Entry Hour",
        labels={"entry_hour": "Hour (UTC)", "mae": "MAE (pips)"},
    )
    fig.update_layout(margin=dict(t=45, b=30, l=30, r=20), showlegend=False)
    return fig


def duration_violin_by_hour_chart(df: pd.DataFrame) -> go.Figure:
    """Violin chart of trade duration by entry hour."""
    fig = px.violin(
        df,
        x="entry_hour",
        y="duration_minutes",
        box=True,
        points="all",
        template=TEMPLATE,
        title="Duration Distribution by Entry Hour",
        labels={"entry_hour": "Hour (UTC)", "duration_minutes": "Duration (min)"},
    )
    fig.update_layout(margin=dict(t=45, b=30, l=30, r=20), showlegend=False)
    return fig


def _optimization_thresholds(series: pd.Series, positive: bool) -> np.ndarray:
    """Generate sensible optimization thresholds from the observed excursion range."""
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return np.array([1.0]) if positive else np.array([-1.0])

    if positive:
        upper = max(float(clean.max()), 1.0)
        thresholds = np.linspace(1.0, upper, 25)
    else:
        lower = min(float(clean.min()), -1.0)
        thresholds = np.linspace(-1.0, lower, 25)

    return np.unique(np.round(thresholds, 1))


def stop_loss_optimization_chart(df: pd.DataFrame) -> go.Figure:
    """
    Estimate total PnL if every trade were capped by a fixed stop loss.
    Uses MAE as a simplified trigger condition.
    """
    thresholds = _optimization_thresholds(df["mae"], positive=False)
    total_pnl = []
    stopped_trades = []

    for stop_loss in thresholds:
        adjusted = df["pnl_pips"].where(df["mae"] >= stop_loss, stop_loss)
        total_pnl.append(float(adjusted.sum()))
        stopped_trades.append(int((df["mae"] < stop_loss).sum()))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=thresholds,
            y=total_pnl,
            fill="tozeroy",
            fillcolor="rgba(255, 107, 107, 0.20)",
            line=dict(color=COLOR_LOSS, width=2),
            customdata=np.array(stopped_trades).reshape(-1, 1),
            hovertemplate=(
                "Stop Loss: %{x:.1f} pips<br>"
                "Estimated Total PnL: %{y:.1f} pips<br>"
                "Triggered Trades: %{customdata[0]}<extra></extra>"
            ),
            name="Estimated PnL",
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Stop Loss Optimization",
        xaxis_title="Stop Loss (pips)",
        yaxis_title="Estimated Total PnL (pips)",
        margin=dict(t=45, b=30, l=30, r=20),
        height=350,
        hovermode="x unified",
    )
    fig.update_xaxes(autorange="reversed")
    return fig


def take_profit_optimization_chart(df: pd.DataFrame) -> go.Figure:
    """
    Estimate total PnL if every trade were capped by a fixed take profit.
    Uses MFE as a simplified trigger condition.
    """
    thresholds = _optimization_thresholds(df["mfe"], positive=True)
    total_pnl = []
    hit_trades = []

    for take_profit in thresholds:
        adjusted = df["pnl_pips"].where(df["mfe"] < take_profit, take_profit)
        total_pnl.append(float(adjusted.sum()))
        hit_trades.append(int((df["mfe"] >= take_profit).sum()))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=thresholds,
            y=total_pnl,
            fill="tozeroy",
            fillcolor="rgba(0, 201, 167, 0.20)",
            line=dict(color=COLOR_WIN, width=2),
            customdata=np.array(hit_trades).reshape(-1, 1),
            hovertemplate=(
                "Take Profit: %{x:.1f} pips<br>"
                "Estimated Total PnL: %{y:.1f} pips<br>"
                "Triggered Trades: %{customdata[0]}<extra></extra>"
            ),
            name="Estimated PnL",
        )
    )
    fig.update_layout(
        template=TEMPLATE,
        title="Take Profit Optimization",
        xaxis_title="Take Profit (pips)",
        yaxis_title="Estimated Total PnL (pips)",
        margin=dict(t=45, b=30, l=30, r=20),
        height=350,
        hovermode="x unified",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════
# MAE / MFE & DRAWDOWN CHARTS
# ═══════════════════════════════════════════════════════════════════

def drawdown_chart(df: pd.DataFrame) -> go.Figure:
    """Area chart of drawdown from peak equity."""
    equity = stats.compute_equity_curve(df)
    running_max = equity["cumulative_pnl"].cummax()
    drawdown = equity["cumulative_pnl"] - running_max

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity["entry_time"],
        y=drawdown,
        mode="lines",
        line=dict(color=COLOR_DRAWDOWN, width=1),
        name="Drawdown",
        fill="tozeroy",
        fillcolor="rgba(255, 107, 107, 0.2)",
    ))
    fig.update_layout(
        template=TEMPLATE,
        title="Drawdown (Pips)",
        xaxis_title="Time",
        yaxis_title="Drawdown (pips)",
        margin=dict(t=50, b=30, l=50, r=20),
        height=250,
        hovermode="x unified",
    )
    return fig


def mae_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Histogram of MAE (pips)."""
    fig = px.histogram(
        df, x="mae", nbins=40,
        template=TEMPLATE, title="MAE Distribution (pips)",
        color_discrete_sequence=[COLOR_LOSS]
    )
    fig.update_layout(margin=dict(t=40, b=30, l=30, r=20))
    return fig


def mfe_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Histogram of MFE (pips)."""
    fig = px.histogram(
        df, x="mfe", nbins=40,
        template=TEMPLATE, title="MFE Distribution (pips)",
        color_discrete_sequence=[COLOR_WIN]
    )
    fig.update_layout(margin=dict(t=40, b=30, l=30, r=20))
    return fig


def mfe_vs_mae_chart(df: pd.DataFrame) -> go.Figure:
    """Clickable scatter plot of MFE vs MAE with detailed per-trade hover context."""
    if len(df) == 0:
        return go.Figure()

    df_copy = df.copy().reset_index(drop=True)

    mae_threshold = df_copy["mae"].quantile(0.10)
    mfe_threshold = df_copy["mfe"].quantile(0.90)
    df_copy["is_outlier"] = (
        ((df_copy["mae"] <= mae_threshold) & (df_copy["pnl_pips"] > 0)) |
        ((df_copy["mfe"] >= mfe_threshold) & (df_copy["pnl_pips"] < 0))
    )

    abs_pnl = df_copy["pnl_pips"].abs()
    max_abs_pnl = float(abs_pnl.max()) if len(abs_pnl) else 1.0
    max_abs_pnl = max(max_abs_pnl, 1.0)
    df_copy["marker_size"] = 8 + (abs_pnl / max_abs_pnl) * 12
    df_copy["marker_symbol"] = df_copy["direction"].map(
        {"Long": "triangle-up", "Short": "triangle-down"}
    ).fillna("circle")
    customdata = df_copy[
        [
            "trade_id",
            "direction",
            "pnl_pips",
            "duration_minutes",
            "entry_time",
            "exit_reason",
            "entry_price",
            "exit_price",
        ]
    ].values

    max_color = max(float(df_copy["pnl_pips"].abs().max()), 1.0)

    fig = go.Figure(
        data=go.Scatter(
            x=df_copy["mae"],
            y=df_copy["mfe"],
            mode="markers",
            customdata=customdata,
            marker=dict(
                size=df_copy["marker_size"],
                color=df_copy["pnl_pips"],
                colorscale="RdYlGn",
                cmin=-max_color,
                cmax=max_color,
                colorbar=dict(title="PnL (pips)"),
                symbol=df_copy["marker_symbol"],
                line=dict(color="rgba(255,255,255,0.75)", width=1),
                opacity=0.85,
            ),
            hovertemplate=(
                "Trade ID: %{customdata[0]}<br>"
                "Direction: %{customdata[1]}<br>"
                "PnL: %{customdata[2]:+.1f} pips<br>"
                "MAE: %{x:.1f} pips<br>"
                "MFE: %{y:.1f} pips<br>"
                "Duration: %{customdata[3]:.0f} min<br>"
                "Entry: %{customdata[4]}<br>"
                "Exit Reason: %{customdata[5]}<br>"
                "Entry Price: %{customdata[6]:.5f}<br>"
                "Exit Price: %{customdata[7]:.5f}<extra></extra>"
            ),
            name="Trades",
        )
    )

    fig.add_hline(y=0, line_dash="dash", line_color="#aaaaaa", opacity=0.4)
    fig.add_vline(x=0, line_dash="dash", line_color="#aaaaaa", opacity=0.4)
    fig.update_layout(
        template=TEMPLATE,
        title="MFE vs MAE Analysis",
        xaxis_title="MAE (pips)",
        yaxis_title="MFE (pips)",
        margin=dict(t=45, b=30, l=30, r=40),
        height=520,
        clickmode="event+select",
    )
    return fig
