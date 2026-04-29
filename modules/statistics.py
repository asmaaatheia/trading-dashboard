"""
statistics.py
─────────────
Compute top-level KPI metrics, session analysis, and duration
bucket analysis from the trades dataframe.
"""

import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════════════════════════
# CORE KPIs
# ═══════════════════════════════════════════════════════════════════

def total_trades(df: pd.DataFrame) -> int:
    """Total number of trades in the dataset."""
    return len(df)


def win_rate(df: pd.DataFrame) -> float:
    """Win rate as a percentage. A win is pnl_pips > 0."""
    if len(df) == 0:
        return 0.0
    wins = (df["pnl_pips"] > 0).sum()
    return round((wins / len(df)) * 100, 1)


def total_pnl_pips(df: pd.DataFrame) -> float:
    """Sum of all PnL in pips."""
    return round(df["pnl_pips"].sum(), 1)


def avg_trade_pips(df: pd.DataFrame) -> float:
    """Average PnL per trade in pips."""
    if len(df) == 0:
        return 0.0
    return round(df["pnl_pips"].mean(), 2)


def avg_duration_minutes(df: pd.DataFrame) -> float:
    """Average trade duration in minutes."""
    if len(df) == 0:
        return 0.0
    return round(df["duration_minutes"].mean(), 1)


def compute_all(df: pd.DataFrame) -> dict:
    """Convenience function returning all KPIs as a dict."""
    return {
        "Total Trades": total_trades(df),
        "Win Rate (%)": win_rate(df),
        "Total PnL (pips)": total_pnl_pips(df),
        "Avg Trade (pips)": avg_trade_pips(df),
        "Avg Duration (min)": avg_duration_minutes(df),
    }


# ═══════════════════════════════════════════════════════════════════
# EQUITY CURVE & DRAWDOWN
# ═══════════════════════════════════════════════════════════════════

def compute_equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort trades by entry_time and compute cumulative PnL.
    Returns a DataFrame with columns: entry_time, cumulative_pnl.
    """
    sorted_df = df.sort_values("entry_time").copy()
    sorted_df["cumulative_pnl"] = sorted_df["pnl_pips"].cumsum()
    return sorted_df[["entry_time", "cumulative_pnl"]].reset_index(drop=True)


def max_drawdown(df: pd.DataFrame) -> float:
    """
    Compute the maximum drawdown in pips from the cumulative PnL curve.
    Drawdown = peak - trough (measured from the running maximum).
    """
    if len(df) == 0:
        return 0.0
    sorted_df = df.sort_values("entry_time")
    cumulative = sorted_df["pnl_pips"].cumsum()
    running_max = cumulative.cummax()
    drawdowns = running_max - cumulative
    return round(float(drawdowns.max()), 1)


# ═══════════════════════════════════════════════════════════════════
# SESSION ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def assign_session(hour: int) -> str:
    """
    Classify an hour (0-23) into a trading session.
    Asia:     00:00 – 06:59
    London:   07:00 – 12:59
    New York: 13:00 – 19:59
    Other:    20:00 – 23:59
    """
    if 0 <= hour < 7:
        return "Asia"
    elif 7 <= hour < 13:
        return "London"
    elif 13 <= hour < 20:
        return "New York"
    else:
        return "Other"


def session_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-session statistics: trade count, avg PnL, win rate.
    Returns a DataFrame with columns: session, count, avg_pnl, win_rate.
    """
    if len(df) == 0:
        return pd.DataFrame(columns=["session", "count", "avg_pnl", "win_rate"])

    df_copy = df.copy()
    df_copy["session"] = df_copy["entry_hour"].apply(assign_session)

    result = df_copy.groupby("session").agg(
        count=("trade_id", "count"),
        avg_pnl=("pnl_pips", "mean"),
        wins=("pnl_pips", lambda x: (x > 0).sum()),
        total=("pnl_pips", "count"),
    ).reset_index()

    result["win_rate"] = (result["wins"] / result["total"] * 100).round(1)
    result["avg_pnl"] = result["avg_pnl"].round(2)

    # Enforce consistent session order
    session_order = ["Asia", "London", "New York", "Other"]
    result["session"] = pd.Categorical(
        result["session"], categories=session_order, ordered=True
    )
    result = result.sort_values("session").reset_index(drop=True)

    return result[["session", "count", "avg_pnl", "win_rate"]]


# ═══════════════════════════════════════════════════════════════════
# DURATION BUCKET ANALYSIS
# ═══════════════════════════════════════════════════════════════════

DURATION_BUCKETS = [
    ("0-30 min", 0, 30),
    ("30-60 min", 30, 60),
    ("1-2 hours", 60, 120),
    ("2-4 hours", 120, 240),
    ("4+ hours", 240, float("inf")),
]


def assign_duration_bucket(minutes: float) -> str:
    """Classify a duration (minutes) into a human-readable bucket."""
    for label, low, high in DURATION_BUCKETS:
        if low <= minutes < high:
            return label
    return "4+ hours"


def duration_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-bucket statistics: trade count, avg PnL.
    Returns a DataFrame with columns: bucket, count, avg_pnl.
    """
    if len(df) == 0:
        return pd.DataFrame(columns=["bucket", "count", "avg_pnl"])

    df_copy = df.copy()
    df_copy["bucket"] = df_copy["duration_minutes"].apply(assign_duration_bucket)

    result = df_copy.groupby("bucket").agg(
        count=("trade_id", "count"),
        avg_pnl=("pnl_pips", "mean"),
    ).reset_index()

    result["avg_pnl"] = result["avg_pnl"].round(2)

    # Enforce consistent bucket order
    bucket_order = [b[0] for b in DURATION_BUCKETS]
    result["bucket"] = pd.Categorical(
        result["bucket"], categories=bucket_order, ordered=True
    )
    result = result.sort_values("bucket").reset_index(drop=True)

    return result


def strategy_insights(df: pd.DataFrame) -> dict:
    """Compute highest and lowest performing strategy classifications across standard granularities."""
    if len(df) == 0:
        return {}
    
    insights = {}

    # ── Entry Hour ───────────────────────────────────────────────
    hourly = df.groupby("entry_hour").agg(
        avg_pnl=("pnl_pips", "mean"),
        count=("trade_id", "count")
    ).reset_index()
    if not hourly.empty:
        best_hour_idx = hourly["avg_pnl"].idxmax()
        worst_hour_idx = hourly["avg_pnl"].idxmin()
        insights["Best Entry Hour"] = {
            "label": f"{int(hourly.loc[best_hour_idx, 'entry_hour']):02d}:00 UTC",
            "val": hourly.loc[best_hour_idx, "avg_pnl"],
            "count": int(hourly.loc[best_hour_idx, "count"])
        }
        insights["Worst Entry Hour"] = {
            "label": f"{int(hourly.loc[worst_hour_idx, 'entry_hour']):02d}:00 UTC",
            "val": hourly.loc[worst_hour_idx, "avg_pnl"],
            "count": int(hourly.loc[worst_hour_idx, "count"])
        }

    # ── Session ──────────────────────────────────────────────────
    ss = session_stats(df)
    ss = ss[ss["count"] > 0]
    if not ss.empty:
        best_sess_idx = ss["avg_pnl"].idxmax()
        worst_sess_idx = ss["avg_pnl"].idxmin()
        insights["Best Session"] = {
            "label": str(ss.loc[best_sess_idx, "session"]),
            "val": ss.loc[best_sess_idx, "avg_pnl"],
            "count": int(ss.loc[best_sess_idx, "count"])
        }
        insights["Worst Session"] = {
            "label": str(ss.loc[worst_sess_idx, "session"]),
            "val": ss.loc[worst_sess_idx, "avg_pnl"],
            "count": int(ss.loc[worst_sess_idx, "count"])
        }

    # ── Duration Bucket ──────────────────────────────────────────
    ds = duration_stats(df)
    ds = ds[ds["count"] > 0]
    if not ds.empty:
        best_dur_idx = ds["avg_pnl"].idxmax()
        worst_dur_idx = ds["avg_pnl"].idxmin()
        insights["Best Duration"] = {
            "label": str(ds.loc[best_dur_idx, "bucket"]),
            "val": ds.loc[best_dur_idx, "avg_pnl"],
            "count": int(ds.loc[best_dur_idx, "count"])
        }
        insights["Worst Duration"] = {
            "label": str(ds.loc[worst_dur_idx, "bucket"]),
            "val": ds.loc[worst_dur_idx, "avg_pnl"],
            "count": int(ds.loc[worst_dur_idx, "count"])
        }

    return insights


def _safe_div(numerator: float, denominator: float) -> float:
    """Division helper that returns 0 when the denominator is 0."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _max_consecutive(values: pd.Series, predicate) -> int:
    """Return the longest consecutive run matching predicate(value)."""
    best = 0
    current = 0
    for value in values:
        if predicate(value):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def advanced_kpis(df: pd.DataFrame) -> dict:
    """
    Compute higher-signal performance statistics beyond the top-level KPIs.
    """
    if len(df) == 0:
        return {
            "Gross Profit": 0.0,
            "Gross Loss": 0.0,
            "Profit Factor": 0.0,
            "Expectancy": 0.0,
            "Avg Win": 0.0,
            "Avg Loss": 0.0,
            "Reward/Risk": 0.0,
            "Median Trade": 0.0,
            "Std Dev": 0.0,
            "Best Trade": 0.0,
            "Worst Trade": 0.0,
            "Max Win Streak": 0,
            "Max Loss Streak": 0,
        }

    pnl = df["pnl_pips"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = float(losses.sum()) if not losses.empty else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0

    return {
        "Gross Profit": round(gross_profit, 1),
        "Gross Loss": round(gross_loss, 1),
        "Profit Factor": round(_safe_div(gross_profit, abs(gross_loss)), 2),
        "Expectancy": round(float(pnl.mean()), 2),
        "Avg Win": round(avg_win, 2),
        "Avg Loss": round(avg_loss, 2),
        "Reward/Risk": round(_safe_div(avg_win, abs(avg_loss)), 2),
        "Median Trade": round(float(pnl.median()), 2),
        "Std Dev": round(float(pnl.std(ddof=0)), 2),
        "Best Trade": round(float(pnl.max()), 1),
        "Worst Trade": round(float(pnl.min()), 1),
        "Max Win Streak": _max_consecutive(pnl.tolist(), lambda x: x > 0),
        "Max Loss Streak": _max_consecutive(pnl.tolist(), lambda x: x < 0),
    }


def hourly_performance_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dense hour-by-hour summary table inspired by the shared apps.
    """
    if len(df) == 0:
        return pd.DataFrame()

    result = (
        df.groupby("entry_hour")
        .agg(
            trades=("trade_id", "count"),
            win_rate=("pnl_pips", lambda x: (x > 0).mean() * 100),
            total_pnl=("pnl_pips", "sum"),
            avg_pnl=("pnl_pips", "mean"),
            median_pnl=("pnl_pips", "median"),
            avg_mae=("mae", "mean"),
            avg_mfe=("mfe", "mean"),
            avg_duration=("duration_minutes", "mean"),
        )
        .reset_index()
        .rename(columns={"entry_hour": "hour"})
    )

    for column in [
        "win_rate",
        "total_pnl",
        "avg_pnl",
        "median_pnl",
        "avg_mae",
        "avg_mfe",
        "avg_duration",
    ]:
        result[column] = result[column].round(2)

    return result


def weekday_performance_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Dense weekday summary table inspired by the shared apps.
    """
    if len(df) == 0:
        return pd.DataFrame()

    df_copy = df.copy()
    df_copy["weekday"] = df_copy["entry_time"].dt.day_name()
    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    result = (
        df_copy.groupby("weekday")
        .agg(
            trades=("trade_id", "count"),
            win_rate=("pnl_pips", lambda x: (x > 0).mean() * 100),
            total_pnl=("pnl_pips", "sum"),
            avg_pnl=("pnl_pips", "mean"),
            median_pnl=("pnl_pips", "median"),
            avg_mae=("mae", "mean"),
            avg_mfe=("mfe", "mean"),
            avg_duration=("duration_minutes", "mean"),
        )
        .reset_index()
    )

    result["weekday"] = pd.Categorical(
        result["weekday"], categories=weekday_order, ordered=True
    )
    result = result.sort_values("weekday").reset_index(drop=True)

    for column in [
        "win_rate",
        "total_pnl",
        "avg_pnl",
        "median_pnl",
        "avg_mae",
        "avg_mfe",
        "avg_duration",
    ]:
        result[column] = result[column].round(2)

    return result
