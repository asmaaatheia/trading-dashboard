"""
News analysis helpers for the integrated dashboard tab.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


TEMPLATE = "plotly_dark"
IMPACT_ORDER = ["None", "Low", "Moderate", "High"]
TIMING_ORDER = ["Before Entry", "At Entry", "After Entry"]
WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
MONTH_DAY_ORDER = [
    f"{day}{week}"
    for week in range(5, 0, -1)
    for day in ["su", "sa", "fr", "th", "we", "tu", "mo"]
]


def filter_news(
    df: pd.DataFrame,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    event_search: str = "",
    date_range: tuple | list | None = None,
) -> pd.DataFrame:
    """Apply dashboard-side news filters."""
    if df.empty:
        return df

    filtered = df.copy()

    if currencies:
        filtered = filtered[filtered["currency"].isin(currencies)]
    if impacts:
        filtered = filtered[filtered["impact"].isin(impacts)]
    if event_search:
        filtered = filtered[
            filtered["event"].str.contains(event_search, case=False, na=False)
        ]
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["timestamp"].dt.date >= start_date)
            & (filtered["timestamp"].dt.date <= end_date)
        ]

    return filtered.reset_index(drop=True)


def filter_spread(
    df: pd.DataFrame,
    date_range: tuple | list | None = None,
) -> pd.DataFrame:
    """Apply dashboard-side date filtering to spread data."""
    if df.empty:
        return df

    filtered = df.copy()
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["timestamp"].dt.date >= start_date)
            & (filtered["timestamp"].dt.date <= end_date)
        ]
    return filtered.reset_index(drop=True)


def news_summary(df: pd.DataFrame) -> dict:
    """Compact KPI summary for the news tab."""
    if df.empty:
        return {
            "Total News": 0,
            "High Impact": 0,
            "Currencies": 0,
            "Busiest Hour": "-",
            "Busiest Day": "-",
        }

    busiest_hour = (
        df.groupby("entry_hour")["event"].count().sort_values(ascending=False).index[0]
    )
    busiest_day = (
        df.groupby("weekday_name")["event"].count().reindex(WEEKDAY_ORDER).fillna(0).sort_values(ascending=False).index[0]
    )
    return {
        "Total News": int(len(df)),
        "High Impact": int((df["impact"] == "High").sum()),
        "Currencies": int(df["currency"].nunique()),
        "Busiest Hour": f"{int(busiest_hour):02d}:00",
        "Busiest Day": busiest_day,
    }


def news_impact_heatmap(
    df: pd.DataFrame,
    selected_month_day: str | None = None,
    selected_hour: int | None = None,
) -> go.Figure:
    """Heatmap of news counts by month-day title and hour."""
    pivot = df.pivot_table(
        index="month_day_title",
        columns="entry_hour",
        values="event",
        aggfunc="count",
        fill_value=0,
    )
    pivot = pivot.reindex(MONTH_DAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)), fill_value=0)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            text=pivot.values,
            texttemplate="%{text}",
            colorscale="Viridis",
            hovertemplate=(
                "Month day: %{y}<br>"
                "Hour: %{x}:00<br>"
                "News count: %{z}<extra></extra>"
            ),
        )
    )

    if selected_month_day is not None and selected_hour is not None:
        try:
            y_index = pivot.index.tolist().index(selected_month_day)
            fig.add_shape(
                type="rect",
                x0=selected_hour - 0.5,
                x1=selected_hour + 0.5,
                y0=y_index - 0.5,
                y1=y_index + 0.5,
                xref="x",
                yref="y",
                line=dict(color="#90EE90", width=3),
            )
        except ValueError:
            pass

    fig.update_layout(
        template=TEMPLATE,
        title="Count of News",
        xaxis_title="Hour",
        yaxis_title="Month Day",
        margin=dict(t=40, b=20, l=20, r=20),
        height=650,
    )
    fig.update_xaxes(tickmode="linear")
    return fig


def _violin_color_sequence(selected_labels: list[str] | None, label: str) -> str:
    return "#90EE90" if selected_labels and label in selected_labels else "#7c8db5"


def _highlight_violin_trace(fig: go.Figure, target_label) -> go.Figure:
    """Highlight the violin trace whose name matches the selected label."""
    for trace in fig.data:
        trace.line.color = "#D3D3D3"

    target_as_str = str(target_label)
    for trace in fig.data:
        if str(trace.name) == target_as_str:
            trace.line.color = "#90EE90"
            break

    return fig


def news_count_by_hour_violin(df: pd.DataFrame, selected_hour: int | None = None) -> go.Figure:
    """Violin chart of count of news per day, grouped by hour."""
    agg = (
        df.groupby(["date", "entry_hour"])["event"]
        .count()
        .reset_index(name="count")
    )
    rows = []
    for hour in range(24):
        hour_data = agg.loc[agg["entry_hour"] == hour, "count"].tolist() or [0]
        rows.extend([{"label": hour, "count": value} for value in hour_data])

    chart_df = pd.DataFrame(rows)
    fig = px.violin(
        chart_df,
        x="label",
        y="count",
        box=True,
        points="all",
        template=TEMPLATE,
        title="Count of News per Hour",
        labels={"label": "Hour", "count": "Count of News per Day"},
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=320)
    if selected_hour is not None:
        return _highlight_violin_trace(fig, selected_hour)
    return fig


def news_count_by_weekday_violin(
    df: pd.DataFrame, selected_weekday_name: str | None = None
) -> go.Figure:
    """Violin chart of count of news per day, grouped by weekday."""
    agg = (
        df.groupby(["weekday_name", "date"])["event"]
        .count()
        .reset_index(name="count")
    )
    rows = []
    for weekday in WEEKDAY_ORDER:
        day_data = agg.loc[agg["weekday_name"] == weekday, "count"].tolist() or [0]
        rows.extend([{"label": weekday, "count": value} for value in day_data])

    chart_df = pd.DataFrame(rows)
    fig = px.violin(
        chart_df,
        x="label",
        y="count",
        box=True,
        points="all",
        template=TEMPLATE,
        title="Count of News per Weekday",
        labels={"label": "Weekday", "count": "Count of News per Day"},
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=320)
    if selected_weekday_name in WEEKDAY_ORDER:
        return _highlight_violin_trace(fig, selected_weekday_name)
    return fig


def news_count_by_month_day_violin(
    df: pd.DataFrame, selected_month_day: str | None = None
) -> go.Figure:
    """Violin chart of count of news per day, grouped by month-day title."""
    agg = (
        df.groupby(["month_day_title", "date"])["event"]
        .count()
        .reset_index(name="count")
    )
    rows = []
    for day_title in MONTH_DAY_ORDER:
        day_data = agg.loc[agg["month_day_title"] == day_title, "count"].tolist() or [0]
        rows.extend([{"label": day_title, "count": value} for value in day_data])

    chart_df = pd.DataFrame(rows)
    fig = px.violin(
        chart_df,
        x="label",
        y="count",
        box=True,
        points="all",
        template=TEMPLATE,
        title="Count of News per Month Day",
        labels={"label": "Month Day", "count": "Count of News per Day"},
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=320)
    if selected_month_day in MONTH_DAY_ORDER:
        return _highlight_violin_trace(fig, selected_month_day)
    return fig


def news_impact_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Simple bar chart of impact counts."""
    impact_counts = (
        df["impact"]
        .value_counts()
        .reindex(IMPACT_ORDER, fill_value=0)
        .reset_index()
    )
    impact_counts.columns = ["impact", "count"]
    fig = px.bar(
        impact_counts,
        x="impact",
        y="count",
        template=TEMPLATE,
        title="News by Impact",
        color="impact",
        color_discrete_map={
            "High": "#ff6b6b",
            "Moderate": "#ffd93d",
            "Low": "#4d96ff",
            "None": "#7c8db5",
        },
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=320)
    return fig


def news_currency_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart of news counts by currency."""
    currency_counts = (
        df["currency"]
        .value_counts()
        .reset_index()
    )
    currency_counts.columns = ["currency", "count"]
    fig = px.bar(
        currency_counts,
        x="currency",
        y="count",
        template=TEMPLATE,
        title="News by Currency",
        color_discrete_sequence=["#7c8db5"],
    )
    fig.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=320)
    return fig


def news_rows_for_heatmap_cell(
    df: pd.DataFrame, month_day_title: str | None, hour: int | None
) -> pd.DataFrame:
    """Return the subset of news rows associated with a clicked heatmap cell."""
    if month_day_title is None or hour is None or df.empty:
        return pd.DataFrame(columns=["date", "time", "event", "currency", "impact", "forecast", "result"])

    rows = df[
        (df["month_day_title"] == month_day_title) & (df["entry_hour"] == int(hour))
    ].copy()
    return rows[
        ["date", "time", "event", "currency", "impact", "forecast", "result"]
    ].sort_values(["date", "time"]).reset_index(drop=True)


def _avg_line_per_hour(matrix_values: np.ndarray) -> np.ndarray:
    """Average non-null heatmap values per hour."""
    arr = np.array(matrix_values, dtype=float)
    with np.errstate(invalid="ignore"):
        averages = np.nanmean(arr, axis=0)
    return averages


def _spread_heatmap_base(
    df: pd.DataFrame,
    aggfunc: str,
    title: str,
    selected_month_day: str | None = None,
    selected_hour: int | None = None,
) -> go.Figure:
    """Build a spread heatmap with an overlaid average-per-hour line."""
    pivot = df.pivot_table(
        index="month_day_title",
        columns="entry_hour",
        values="spread",
        aggfunc=aggfunc,
    )
    pivot = pivot.reindex(MONTH_DAY_ORDER)
    pivot = pivot.reindex(columns=list(range(24)))

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Viridis",
            hovertemplate=(
                "Month day: %{y}<br>"
                "Hour: %{x}:00<br>"
                f"{title}: %{{z:.2f}}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    avg_line = _avg_line_per_hour(pivot.values)
    fig.add_trace(
        go.Scatter(
            x=list(range(24)),
            y=avg_line,
            mode="lines+markers",
            line=dict(color="#ffa500", width=2),
            marker=dict(size=6),
            name="Hourly Avg",
            hovertemplate="Hour: %{x}:00<br>Avg Spread: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )

    if selected_month_day is not None and selected_hour is not None:
        try:
            y_index = pivot.index.tolist().index(selected_month_day)
            fig.add_shape(
                type="rect",
                x0=selected_hour - 0.5,
                x1=selected_hour + 0.5,
                y0=y_index - 0.5,
                y1=y_index + 0.5,
                xref="x",
                yref="y",
                line=dict(color="#90EE90", width=3),
            )
        except ValueError:
            pass

    fig.update_layout(
        template=TEMPLATE,
        title=title,
        margin=dict(t=40, b=20, l=20, r=20),
        height=650,
        showlegend=False,
        hovermode="x",
    )
    fig.update_xaxes(title_text="Hour", tickmode="linear")
    fig.update_yaxes(title_text="Month Day", secondary_y=False)
    fig.update_yaxes(title_text="Avg Spread", secondary_y=True, showgrid=False)
    return fig


def mean_spread_heatmap(
    df: pd.DataFrame,
    selected_month_day: str | None = None,
    selected_hour: int | None = None,
) -> go.Figure:
    """Mean spread heatmap aligned to the clicked news heatmap cell."""
    return _spread_heatmap_base(
        df,
        aggfunc="mean",
        title="Mean Spread",
        selected_month_day=selected_month_day,
        selected_hour=selected_hour,
    )


def max_spread_heatmap(
    df: pd.DataFrame,
    selected_month_day: str | None = None,
    selected_hour: int | None = None,
) -> go.Figure:
    """Max spread heatmap aligned to the clicked news heatmap cell."""
    return _spread_heatmap_base(
        df,
        aggfunc="max",
        title="Max Spread",
        selected_month_day=selected_month_day,
        selected_hour=selected_hour,
    )


def spread_rows_for_heatmap_cell(
    df: pd.DataFrame, month_day_title: str | None, hour: int | None
) -> pd.DataFrame:
    """Return spread rows for the selected month-day / hour bucket."""
    if month_day_title is None or hour is None or df.empty:
        return pd.DataFrame(
            columns=["date", "time", "pair", "spread", "price", "tick_volume", "atr"]
        )

    rows = df[
        (df["month_day_title"] == month_day_title) & (df["entry_hour"] == int(hour))
    ].copy()
    return rows[
        ["date", "time", "pair", "spread", "price", "tick_volume", "atr"]
    ].sort_values(["date", "time"]).reset_index(drop=True)


def news_rows_for_trade_window(
    df: pd.DataFrame,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    before_minutes: int = 60,
    after_minutes: int = 60,
) -> pd.DataFrame:
    """Return news rows around a selected trade window."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "date",
                "time",
                "event",
                "currency",
                "impact",
                "forecast",
                "result",
                "minutes_from_entry",
                "minutes_from_exit",
            ]
        )

    window_start = entry_time - pd.Timedelta(minutes=before_minutes)
    window_end = exit_time + pd.Timedelta(minutes=after_minutes)

    rows = df[
        (df["timestamp"] >= window_start) & (df["timestamp"] <= window_end)
    ].copy()
    if rows.empty:
        return rows

    rows["minutes_from_entry"] = (
        (rows["timestamp"] - entry_time).dt.total_seconds() / 60.0
    ).round(1)
    rows["minutes_from_exit"] = (
        (rows["timestamp"] - exit_time).dt.total_seconds() / 60.0
    ).round(1)
    return rows.sort_values("timestamp").reset_index(drop=True)


def spread_rows_for_trade_window(
    df: pd.DataFrame,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    before_minutes: int = 60,
    after_minutes: int = 60,
) -> pd.DataFrame:
    """Return spread rows around a selected trade window."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "date",
                "time",
                "pair",
                "spread",
                "price",
                "tick_volume",
                "atr",
                "minutes_from_entry",
            ]
        )

    window_start = entry_time - pd.Timedelta(minutes=before_minutes)
    window_end = exit_time + pd.Timedelta(minutes=after_minutes)

    rows = df[
        (df["timestamp"] >= window_start) & (df["timestamp"] <= window_end)
    ].copy()
    if rows.empty:
        return rows

    rows["minutes_from_entry"] = (
        (rows["timestamp"] - entry_time).dt.total_seconds() / 60.0
    ).round(1)
    return rows.sort_values("timestamp").reset_index(drop=True)


def trade_news_window_summary(
    news_rows: pd.DataFrame,
) -> dict[str, str | int | float]:
    """Compact KPI summary for nearby news around one trade."""
    if news_rows.empty:
        return {
            "Nearby News": 0,
            "High Impact": 0,
            "Currencies": 0,
            "Nearest Event": "-",
            "Nearest Minutes": "-",
        }

    nearest = news_rows.iloc[
        news_rows["minutes_from_entry"].abs().sort_values().index[0]
    ]
    return {
        "Nearby News": int(len(news_rows)),
        "High Impact": int((news_rows["impact"] == "High").sum()),
        "Currencies": int(news_rows["currency"].nunique()),
        "Nearest Event": str(nearest["event"])[:40] or "-",
        "Nearest Minutes": f"{float(abs(nearest['minutes_from_entry'])):.1f}",
    }


def trade_news_timeline_chart(
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    news_rows: pd.DataFrame,
    spread_rows: pd.DataFrame,
) -> go.Figure:
    """Timeline of nearby news and spread context around a selected trade."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    impact_rank = {"None": 0, "Low": 1, "Moderate": 2, "High": 3}
    impact_color = {
        "None": "#7c8db5",
        "Low": "#4d96ff",
        "Moderate": "#ffd93d",
        "High": "#ff6b6b",
    }

    if not news_rows.empty:
        plotted_news = news_rows.copy()
        plotted_news["impact_rank"] = plotted_news["impact"].map(impact_rank).fillna(0)
        plotted_news["color"] = plotted_news["impact"].map(impact_color).fillna("#7c8db5")

        fig.add_trace(
            go.Scatter(
                x=plotted_news["timestamp"],
                y=plotted_news["impact_rank"],
                mode="markers",
                marker=dict(
                    size=12,
                    color=plotted_news["color"],
                    line=dict(color="#ffffff", width=1),
                ),
                name="News",
                customdata=np.stack(
                    [
                        plotted_news["event"],
                        plotted_news["currency"],
                        plotted_news["impact"],
                        plotted_news["minutes_from_entry"],
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "Time: %{x|%Y-%m-%d %H:%M}<br>"
                    "Event: %{customdata[0]}<br>"
                    "Currency: %{customdata[1]}<br>"
                    "Impact: %{customdata[2]}<br>"
                    "Minutes from entry: %{customdata[3]}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    if not spread_rows.empty:
        fig.add_trace(
            go.Scatter(
                x=spread_rows["timestamp"],
                y=spread_rows["spread"],
                mode="lines",
                line=dict(color="#26c6da", width=2),
                name="Spread",
                hovertemplate=(
                    "Time: %{x|%Y-%m-%d %H:%M}<br>"
                    "Spread: %{y:.2f}<extra></extra>"
                ),
            ),
            secondary_y=True,
        )

    fig.add_vline(x=entry_time, line_color="#00c9a7", line_width=2)
    fig.add_vline(x=exit_time, line_color="#ff6b6b", line_width=2)
    fig.add_annotation(
        x=entry_time,
        y=1.02,
        yref="paper",
        text="Entry",
        showarrow=False,
        font=dict(color="#00c9a7"),
    )
    fig.add_annotation(
        x=exit_time,
        y=1.02,
        yref="paper",
        text="Exit",
        showarrow=False,
        font=dict(color="#ff6b6b"),
    )

    if news_rows.empty and spread_rows.empty:
        fig.add_annotation(
            text="No nearby news or spread rows were found for this trade window.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="#d3d3d3"),
        )

    fig.update_layout(
        template=TEMPLATE,
        title="News And Spread Around Selected Trade",
        margin=dict(t=50, b=20, l=20, r=20),
        height=420,
        hovermode="x unified",
    )
    fig.update_yaxes(
        title_text="News Impact",
        secondary_y=False,
        tickmode="array",
        tickvals=[0, 1, 2, 3],
        ticktext=["None", "Low", "Moderate", "High"],
        range=[-0.5, 3.5],
    )
    fig.update_yaxes(title_text="Spread", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="Time")
    return fig


def trade_news_overlap(
    trades: pd.DataFrame,
    news: pd.DataFrame,
    window_minutes: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Join trades to nearby news events using an entry-time window.
    Returns the overlap rows and a summary-by-impact table.
    """
    if trades.empty or news.empty:
        return pd.DataFrame(), pd.DataFrame()

    trade_min = trades["entry_time"].min()
    trade_max = trades["entry_time"].max()
    news_min = news["timestamp"].min()
    news_max = news["timestamp"].max()

    if trade_max < news_min or news_max < trade_min:
        return pd.DataFrame(), pd.DataFrame()

    rows = []
    window = pd.Timedelta(minutes=window_minutes)

    trade_subset = trades.copy()
    if "mae" not in trade_subset.columns:
        trade_subset["mae"] = np.nan
    if "mfe" not in trade_subset.columns:
        trade_subset["mfe"] = np.nan
    trade_subset = trade_subset[
        ["trade_id", "entry_time", "direction", "pnl_pips", "mae", "mfe", "duration_minutes"]
    ].copy()
    news_subset = news[
        ["timestamp", "event", "currency", "impact"]
    ].copy()

    for trade in trade_subset.itertuples(index=False):
        candidates = news_subset[
            (news_subset["timestamp"] >= trade.entry_time - window)
            & (news_subset["timestamp"] <= trade.entry_time + window)
        ].copy()
        if candidates.empty:
            continue
        candidates["signed_minutes_from_entry"] = (
            (candidates["timestamp"] - trade.entry_time).dt.total_seconds() / 60.0
        )
        candidates["minutes_from_entry"] = candidates["signed_minutes_from_entry"].abs()
        nearest = candidates.sort_values("minutes_from_entry").iloc[0]
        signed_minutes = float(nearest["signed_minutes_from_entry"])
        if signed_minutes <= -5:
            timing_bucket = "Before Entry"
        elif signed_minutes >= 5:
            timing_bucket = "After Entry"
        else:
            timing_bucket = "At Entry"
        rows.append(
            {
                "trade_id": int(trade.trade_id),
                "entry_time": trade.entry_time,
                "direction": trade.direction,
                "pnl_pips": float(trade.pnl_pips),
                "mae": float(trade.mae),
                "mfe": float(trade.mfe),
                "duration_minutes": float(trade.duration_minutes),
                "news_time": nearest["timestamp"],
                "event": nearest["event"],
                "currency": nearest["currency"],
                "impact": nearest["impact"],
                "minutes_from_entry": float(nearest["minutes_from_entry"]),
                "signed_minutes_from_entry": signed_minutes,
                "timing_bucket": timing_bucket,
            }
        )

    overlap = pd.DataFrame(rows)
    if overlap.empty:
        return overlap, pd.DataFrame()

    summary = (
        overlap.groupby("impact")
        .agg(
            trades=("trade_id", "count"),
            avg_pnl=("pnl_pips", "mean"),
            median_pnl=("pnl_pips", "median"),
            win_rate=("pnl_pips", lambda x: (x > 0).mean() * 100),
            avg_mae=("mae", "mean"),
            avg_mfe=("mfe", "mean"),
            avg_minutes_from_entry=("minutes_from_entry", "mean"),
            avg_signed_minutes=("signed_minutes_from_entry", "mean"),
        )
        .reindex(IMPACT_ORDER)
        .dropna(how="all")
        .reset_index()
    )

    for column in [
        "avg_pnl",
        "median_pnl",
        "win_rate",
        "avg_mae",
        "avg_mfe",
        "avg_minutes_from_entry",
        "avg_signed_minutes",
    ]:
        summary[column] = summary[column].round(2)

    return overlap, summary


def _profit_factor(pnl_series: pd.Series) -> float:
    """Compute profit factor for a group of trade pnl values."""
    gross_profit = pnl_series[pnl_series > 0].sum()
    gross_loss = pnl_series[pnl_series < 0].sum()
    if gross_profit <= 0 and gross_loss == 0:
        return 0.0
    if gross_loss == 0:
        return float("inf")
    return float(gross_profit / abs(gross_loss))


def strategy_news_kpis(
    trades: pd.DataFrame,
    overlap: pd.DataFrame,
) -> dict[str, float]:
    """Compare trades near news versus trades without matched news."""
    if trades.empty:
        return {
            "near_news_trades": 0,
            "near_news_share": 0.0,
            "avg_pnl_near_news": 0.0,
            "avg_pnl_away_news": 0.0,
            "win_rate_near_news": 0.0,
            "win_rate_away_news": 0.0,
        }

    if overlap.empty:
        return {
            "near_news_trades": 0,
            "near_news_share": 0.0,
            "avg_pnl_near_news": 0.0,
            "avg_pnl_away_news": float(trades["pnl_pips"].mean()),
            "win_rate_near_news": 0.0,
            "win_rate_away_news": float((trades["pnl_pips"] > 0).mean() * 100),
        }

    near_ids = set(overlap["trade_id"].astype(int).tolist())
    away_trades = trades[~trades["trade_id"].isin(near_ids)].copy()

    return {
        "near_news_trades": int(len(overlap)),
        "near_news_share": float(len(overlap) / len(trades) * 100),
        "avg_pnl_near_news": float(overlap["pnl_pips"].mean()),
        "avg_pnl_away_news": float(away_trades["pnl_pips"].mean()) if not away_trades.empty else 0.0,
        "win_rate_near_news": float((overlap["pnl_pips"] > 0).mean() * 100),
        "win_rate_away_news": float((away_trades["pnl_pips"] > 0).mean() * 100) if not away_trades.empty else 0.0,
    }


def _group_strategy_performance(
    overlap: pd.DataFrame,
    group_col: str,
    min_trades: int = 1,
    top_n: int | None = None,
    order: list[str] | None = None,
) -> pd.DataFrame:
    """Aggregate overlap rows into strategy-performance statistics by category."""
    if overlap.empty or group_col not in overlap.columns:
        return pd.DataFrame()

    rows = []
    for group_value, group_df in overlap.groupby(group_col):
        pnl = group_df["pnl_pips"]
        rows.append(
            {
                group_col: group_value,
                "trades": int(len(group_df)),
                "win_rate": float((pnl > 0).mean() * 100),
                "avg_pnl": float(pnl.mean()),
                "median_pnl": float(pnl.median()),
                "total_pnl": float(pnl.sum()),
                "avg_mae": float(group_df["mae"].mean()),
                "avg_mfe": float(group_df["mfe"].mean()),
                "avg_minutes_from_entry": float(group_df["minutes_from_entry"].mean()),
                "avg_signed_minutes": float(group_df["signed_minutes_from_entry"].mean()),
                "profit_factor": _profit_factor(pnl),
            }
        )

    summary = pd.DataFrame(rows)
    summary = summary[summary["trades"] >= min_trades].copy()
    if summary.empty:
        return summary

    for column in [
        "win_rate",
        "avg_pnl",
        "median_pnl",
        "total_pnl",
        "avg_mae",
        "avg_mfe",
        "avg_minutes_from_entry",
        "avg_signed_minutes",
    ]:
        summary[column] = summary[column].round(2)

    summary["profit_factor"] = summary["profit_factor"].replace(np.inf, 999.0).round(2)

    if order is not None:
        summary[group_col] = pd.Categorical(summary[group_col], categories=order, ordered=True)
        summary = summary.sort_values(group_col)
    else:
        summary = summary.sort_values(["avg_pnl", "win_rate"], ascending=[False, False])

    if top_n is not None:
        summary = summary.head(top_n)

    return summary.reset_index(drop=True)


def impact_strategy_performance(overlap: pd.DataFrame) -> pd.DataFrame:
    """Strategy stats grouped by matched news impact."""
    return _group_strategy_performance(
        overlap,
        group_col="impact",
        min_trades=1,
        order=IMPACT_ORDER,
    )


def currency_strategy_performance(
    overlap: pd.DataFrame,
    min_trades: int = 3,
    top_n: int = 10,
) -> pd.DataFrame:
    """Strategy stats grouped by matched news currency."""
    return _group_strategy_performance(
        overlap,
        group_col="currency",
        min_trades=min_trades,
        top_n=top_n,
    )


def timing_strategy_performance(overlap: pd.DataFrame) -> pd.DataFrame:
    """Strategy stats grouped by whether the matched news was before or after entry."""
    return _group_strategy_performance(
        overlap,
        group_col="timing_bucket",
        min_trades=1,
        order=TIMING_ORDER,
    )


def direction_strategy_performance(overlap: pd.DataFrame) -> pd.DataFrame:
    """Strategy stats grouped by trade direction near news."""
    return _group_strategy_performance(
        overlap,
        group_col="direction",
        min_trades=1,
        order=["Long", "Short"],
    )


def event_strategy_performance(
    overlap: pd.DataFrame,
    min_trades: int = 3,
    top_n: int = 12,
) -> pd.DataFrame:
    """Strategy stats grouped by matched news event text."""
    return _group_strategy_performance(
        overlap,
        group_col="event",
        min_trades=min_trades,
        top_n=top_n,
    )


def strategy_metric_bar_chart(
    summary_df: pd.DataFrame,
    category_col: str,
    metric_col: str,
    title: str,
    color_positive: str = "#26a69a",
    color_negative: str = "#ef5350",
) -> go.Figure:
    """Bar chart for grouped strategy metrics."""
    if summary_df.empty:
        fig = go.Figure()
        fig.update_layout(template=TEMPLATE, title=title, height=320)
        return fig

    chart_df = summary_df.copy()
    if metric_col == "avg_pnl":
        chart_df["bar_color"] = np.where(
            chart_df[metric_col] >= 0,
            color_positive,
            color_negative,
        )
    else:
        chart_df["bar_color"] = "#7c8db5"

    fig = px.bar(
        chart_df,
        x=category_col,
        y=metric_col,
        template=TEMPLATE,
        title=title,
        color="bar_color",
        color_discrete_map="identity",
        hover_data=["trades", "win_rate", "avg_mae", "avg_mfe", "profit_factor"],
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=40, b=20, l=20, r=20),
        height=320,
    )
    return fig


def impact_vs_trade_scatter(overlap: pd.DataFrame) -> go.Figure:
    """Scatter of trade outcome vs news timing, colored by impact."""
    if overlap.empty:
        fig = go.Figure()
        fig.update_layout(template=TEMPLATE, title="PnL Vs News Timing", height=360)
        return fig

    fig = px.scatter(
        overlap,
        x="minutes_from_entry",
        y="pnl_pips",
        color="impact",
        template=TEMPLATE,
        title="Trade PnL Vs Minutes To Matched News",
        color_discrete_map={
            "High": "#ff6b6b",
            "Moderate": "#ffd93d",
            "Low": "#4d96ff",
            "None": "#7c8db5",
        },
        hover_data=["trade_id", "event", "currency", "mae", "mfe", "duration_minutes"],
    )
    fig.update_layout(
        margin=dict(t=40, b=20, l=20, r=20),
        height=360,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#d3d3d3")
    return fig


def event_strategy_bar_chart(
    summary_df: pd.DataFrame,
    selected_event: str | None = None,
    metric_col: str = "avg_pnl",
) -> go.Figure:
    """Horizontal event ranking chart with optional selected-event highlight."""
    if summary_df.empty:
        fig = go.Figure()
        fig.update_layout(template=TEMPLATE, title="Event Ranking", height=420)
        return fig

    chart_df = summary_df.copy()
    chart_df = chart_df.sort_values(metric_col, ascending=True)
    if metric_col == "avg_pnl":
        default_colors = np.where(chart_df[metric_col] >= 0, "#26a69a", "#ef5350")
    else:
        default_colors = np.full(len(chart_df), "#7c8db5", dtype=object)
    chart_df["bar_color"] = default_colors
    if selected_event:
        chart_df.loc[chart_df["event"] == selected_event, "bar_color"] = "#90EE90"

    fig = px.bar(
        chart_df,
        x=metric_col,
        y="event",
        orientation="h",
        template=TEMPLATE,
        title="Event Ranking",
        color="bar_color",
        color_discrete_map="identity",
        hover_data=["trades", "win_rate", "avg_mae", "avg_mfe", "profit_factor"],
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=40, b=20, l=20, r=20),
        height=420,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="#d3d3d3")
    return fig


def filter_overlap_for_event(
    overlap: pd.DataFrame,
    event_name: str | None = None,
) -> pd.DataFrame:
    """Filter overlap rows to one selected event for drill-down."""
    if overlap.empty or not event_name:
        return overlap
    return overlap[overlap["event"] == event_name].copy().reset_index(drop=True)
