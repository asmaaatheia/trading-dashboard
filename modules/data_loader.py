"""
data_loader.py
──────────────
Cached data ingestion module for the trading dashboard.
Uses @st.cache_data to ensure large price datasets (500k+ rows)
are only read from disk once per Streamlit session.
"""

import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Iterable

# Resolve paths relative to this module's location
DATA_DIR = Path(__file__).parent.parent / "data"
TRADES_FILE = DATA_DIR / "trades_ready.csv"
PRICES_FILE = DATA_DIR / "prices.csv"
NEWS_FILE_CANDIDATES = [
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_news\000000 ! 2020.01.01 - 2020.12.31 dummy-news-xport.csv"),
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_news\231223 ! 2023.06.23 - 2023.12.23  news-xport.csv"),
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_news") ,
]
SPREAD_FILE_CANDIDATES = [
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_spread\XAUUSD-pepperstoneRAZORlive-0.csv"),
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_spread\EURUSD-pepperstoneRAZORlive-0.csv"),
    Path(r"C:\Users\HP\Documents\data for the ploty\PYfiles_spread"),
]


@st.cache_data
def load_trades() -> pd.DataFrame:
    """
    Load and parse trades_ready.csv.
    Ensures datetime columns are typed correctly and
    pnl_pips column exists (derived from pnl if absent).
    """
    df = pd.read_csv(TRADES_FILE)

    # Parse datetime columns
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])

    # Derive pnl_pips if not present (1 pip = 0.0001 for EURUSD)
    if "pnl_pips" not in df.columns:
        df["pnl_pips"] = (df["pnl"] * 10000).round(1)

    # Ensure core numeric types
    df["trade_id"] = df["trade_id"].astype(int)
    df["entry_price"] = df["entry_price"].astype(float)
    df["exit_price"] = df["exit_price"].astype(float)
    df["pnl"] = df["pnl"].astype(float)
    df["duration_minutes"] = df["duration_minutes"].astype(float)

    # Derive entry_hour for chart grouping
    df["entry_hour"] = df["entry_time"].dt.hour

    return df


@st.cache_data
def load_prices() -> pd.DataFrame:
    """
    Load and parse prices.csv (1-minute EURUSD OHLC data).
    Handles both ISO datetime and the 'DD.MM.YYYY HH:MM:SS.000' format
    used by the raw data export.
    Optimizes memory via efficient float32 casting.
    """
    df = pd.read_csv(PRICES_FILE)

    # Rename columns to standard lowercase if coming from raw source
    col_map = {
        "Gmt time": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

    # Parse datetime — handle both ISO and EU format
    try:
        df["time"] = pd.to_datetime(df["time"])
    except Exception:
        df["time"] = pd.to_datetime(df["time"], format="%d.%m.%Y %H:%M:%S.%f")

    # Reduce memory footprint for large tick datasets
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col].astype("float32")

    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


@st.cache_data
def calculate_mae_mfe(trades: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE)
    by slicing the high-frequency price dataframe for each trade's active window.
    """
    if len(trades) == 0:
        return trades

    trades_copy = trades.copy()
    mfe_list = []
    mae_list = []

    for _, row in trades_copy.iterrows():
        mask = (prices["time"] >= row["entry_time"]) & (prices["time"] <= row["exit_time"])
        window = prices.loc[mask]
        
        if window.empty:
            mfe_list.append(0.0)
            mae_list.append(0.0)
            continue

        max_high = window["high"].max()
        min_low = window["low"].min()

        entry_price = float(row["entry_price"])
        if row["direction"] == "Long":
            mfe = (max_high - entry_price) * 10000
            mae = (min_low - entry_price) * 10000
        else:
            mfe = (entry_price - min_low) * 10000
            mae = (entry_price - max_high) * 10000
            
        mfe_list.append(round(mfe, 1))
        mae_list.append(round(mae, 1))

    trades_copy["mfe"] = mfe_list
    trades_copy["mae"] = mae_list
    return trades_copy


def get_price_window(
    prices: pd.DataFrame,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    before_minutes: int = 30,
    after_minutes: int = 30,
) -> pd.DataFrame:
    """
    Efficient slice of the prices dataframe around a specific trade window.
    Returns rows from (entry_time - before_minutes) to (exit_time + after_minutes).
    """
    window_start = entry_time - pd.Timedelta(minutes=before_minutes)
    window_end = exit_time + pd.Timedelta(minutes=after_minutes)

    mask = (prices["time"] >= window_start) & (prices["time"] <= window_end)
    return prices.loc[mask].copy()


def _iter_news_lines(news_path: Path) -> Iterable[str]:
    """Yield non-empty lines from the exported news CSV."""
    with news_path.open("r", encoding="cp1252", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield line


def _parse_news_line(line: str) -> dict | None:
    """
    Parse the malformed news export line format where the event text may contain commas.
    Expected logical columns: Time, Event, Currency, Impact, Forecast, Result
    """
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 6:
        return None

    return {
        "Time": parts[0],
        "Event": ",".join(parts[1:-4]).strip(),
        "Currency": parts[-4],
        "Impact": parts[-3],
        "Forecast": parts[-2],
        "Result": parts[-1],
    }


def _resolve_news_file() -> Path | None:
    """Find the news export file from known local locations."""
    for candidate in NEWS_FILE_CANDIDATES:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            matches = sorted(candidate.glob("*news-xport.csv"))
            if matches:
                return matches[0]
    return None


def _resolve_spread_file() -> Path | None:
    """Find the spread export file from known local locations."""
    for candidate in SPREAD_FILE_CANDIDATES:
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            preferred = sorted(candidate.glob("XAUUSD-pepperstoneRAZORlive-0.csv"))
            if preferred:
                return preferred[0]
            matches = sorted(candidate.glob("*-peppers*")) + sorted(candidate.glob("*.csv"))
            if matches:
                return matches[0]
    return None


@st.cache_data
def load_news() -> pd.DataFrame:
    """
    Load and normalize the external news export used by the shared news app.
    """
    news_path = _resolve_news_file()
    if news_path is None:
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
                "entry_hour",
                "month",
                "month_day",
                "weekday",
                "weekday_name",
                "week_number",
                "month_day_title",
            ]
        )

    lines = list(_iter_news_lines(news_path))
    if not lines:
        return pd.DataFrame()

    rows = []
    for line in lines[1:]:
        parsed = _parse_news_line(line)
        if parsed is not None:
            rows.append(parsed)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["Time"], format="%Y.%m.%d %H:%M")
    df["date"] = df["timestamp"].dt.date
    df["time"] = df["timestamp"].dt.time
    df["event"] = df["Event"].astype(str)
    df["currency"] = df["Currency"].astype(str)
    df["impact"] = df["Impact"].fillna("None").astype(str)
    df["forecast"] = pd.to_numeric(df["Forecast"], errors="coerce")
    df["result"] = pd.to_numeric(df["Result"], errors="coerce")
    df["entry_hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.month
    df["month_day"] = df["timestamp"].dt.day
    df["weekday"] = df["timestamp"].dt.weekday
    df["weekday_name"] = df["timestamp"].dt.day_name()

    subset = df.drop_duplicates(subset=["month", "month_day"]).copy()
    subset["week_number"] = subset["timestamp"].apply(
        lambda ts: ((ts.day - 1) // 7) + 1
    )
    week_map = subset.set_index(["month", "month_day"])["week_number"].to_dict()
    df["week_number"] = df.apply(
        lambda row: week_map[(row["month"], row["month_day"])], axis=1
    )
    df["month_day_title"] = df.apply(
        lambda row: f"{row['weekday_name'][:2].lower()}{int(row['week_number'])}",
        axis=1,
    )

    return df[
        [
            "timestamp",
            "date",
            "time",
            "event",
            "currency",
            "impact",
            "forecast",
            "result",
            "entry_hour",
            "month",
            "month_day",
            "weekday",
            "weekday_name",
            "week_number",
            "month_day_title",
        ]
    ].sort_values("timestamp").reset_index(drop=True)


@st.cache_data
def load_spread_data() -> pd.DataFrame:
    """
    Load and normalize the local spread export used by the shared news/spread app.
    """
    spread_path = _resolve_spread_file()
    if spread_path is None:
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
                "entry_hour",
                "month",
                "month_day",
                "weekday",
                "weekday_name",
                "week_number",
                "month_day_title",
            ]
        )

    df = pd.read_csv(spread_path)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["TimeStamp"], format="%Y.%m.%d %H:%M:%S")
    df["date"] = df["timestamp"].dt.date
    df["time"] = df["timestamp"].dt.time
    df["pair"] = df["Pair"].astype(str)
    df["spread"] = pd.to_numeric(df["Spread"], errors="coerce")
    df["price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["tick_volume"] = pd.to_numeric(df["TickVolume"], errors="coerce")
    df["atr"] = pd.to_numeric(df["ATR"], errors="coerce")
    df["entry_hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.month
    df["month_day"] = df["timestamp"].dt.day
    df["weekday"] = df["timestamp"].dt.weekday
    df["weekday_name"] = df["timestamp"].dt.day_name()

    subset = df.drop_duplicates(subset=["month", "month_day"]).copy()
    subset["week_number"] = subset["timestamp"].apply(
        lambda ts: ((ts.day - 1) // 7) + 1
    )
    week_map = subset.set_index(["month", "month_day"])["week_number"].to_dict()
    df["week_number"] = df.apply(
        lambda row: week_map[(row["month"], row["month_day"])], axis=1
    )
    df["month_day_title"] = df.apply(
        lambda row: f"{row['weekday_name'][:2].lower()}{int(row['week_number'])}",
        axis=1,
    )

    return df[
        [
            "timestamp",
            "date",
            "time",
            "pair",
            "spread",
            "price",
            "tick_volume",
            "atr",
            "entry_hour",
            "month",
            "month_day",
            "weekday",
            "weekday_name",
            "week_number",
            "month_day_title",
        ]
    ].sort_values("timestamp").reset_index(drop=True)
