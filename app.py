"""
Main Streamlit application for the Trading Analysis Dashboard.
Run with: streamlit run app.py
"""

import pandas as pd
import streamlit as st

try:
    from streamlit_plotly_events import plotly_events
except ImportError:
    plotly_events = None

from modules.data_loader import (
    load_trades,
    load_prices,
    calculate_mae_mfe,
    load_news,
    load_spread_data,
)
from modules import statistics as stats
from modules import charts
from modules import news_analysis
from modules.filters import render_sidebar_filters
from modules.trade_analysis import get_trade_details, render_trade_investigation


st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    div[data-testid="stHorizontalBlock"] > div { padding: 0 4px; }
    .section-header { margin-top: 8px; margin-bottom: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)


all_trades = load_trades()
prices = load_prices()
all_trades = calculate_mae_mfe(all_trades, prices)
all_news = load_news()
all_spread = load_spread_data()
trades = render_sidebar_filters(all_trades)

if len(trades) == 0:
    st.warning("No trades match the current filters. Adjust the sidebar filters.")
    st.stop()

st.markdown("## 📊 Trading Analysis Dashboard")
st.markdown("---")

(
    tab_overview,
    tab_equity,
    tab_behavior,
    tab_session,
    tab_duration,
    tab_investigation,
    tab_news,
) = st.tabs(
    [
        "Overview",
        "Equity Analysis",
        "Trade Behavior",
        "Session Analysis",
        "Duration Analysis",
        "Trade Investigation",
        "News Analysis",
    ]
)


def render_trade_news_context(
    trade_frame,
    news_frame,
    spread_frame,
    slider_key_prefix: str,
    heading: str,
    caption: str,
) -> None:
    """Render nearby news and spread context for the currently selected trade."""
    selected_trade_id = st.session_state.get("selected_trade_id")
    if selected_trade_id is None:
        st.info("Select a trade first to inspect the matching news context.")
        return

    trade_details = get_trade_details(trade_frame, selected_trade_id)
    if not trade_details:
        st.info("The selected trade is not available in the current filtered trade set.")
        return

    st.markdown(heading)
    st.caption(caption)

    slider_col1, slider_col2 = st.columns(2)
    with slider_col1:
        before_minutes = st.slider(
            "Minutes before entry",
            min_value=15,
            max_value=1440,
            value=120,
            step=15,
            key=f"{slider_key_prefix}_before",
        )
    with slider_col2:
        after_minutes = st.slider(
            "Minutes after exit",
            min_value=15,
            max_value=1440,
            value=120,
            step=15,
            key=f"{slider_key_prefix}_after",
        )

    entry_time = trade_details["Entry Time"]
    exit_time = trade_details["Exit Time"]

    nearby_news = news_analysis.news_rows_for_trade_window(
        news_frame,
        entry_time=entry_time,
        exit_time=exit_time,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
    )
    nearby_spread = news_analysis.spread_rows_for_trade_window(
        spread_frame,
        entry_time=entry_time,
        exit_time=exit_time,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
    )
    nearby_summary = news_analysis.trade_news_window_summary(nearby_news)

    summary_cols = st.columns(5)
    summary_cols[0].metric("Nearby News", f"{nearby_summary['Nearby News']}")
    summary_cols[1].metric("High Impact", f"{nearby_summary['High Impact']}")
    summary_cols[2].metric("Currencies", f"{nearby_summary['Currencies']}")
    summary_cols[3].metric("Nearest Event", str(nearby_summary["Nearest Event"]))
    summary_cols[4].metric("Nearest Minutes", str(nearby_summary["Nearest Minutes"]))

    st.plotly_chart(
        news_analysis.trade_news_timeline_chart(
            entry_time=entry_time,
            exit_time=exit_time,
            news_rows=nearby_news,
            spread_rows=nearby_spread,
        ),
        use_container_width=True,
    )

    details_col1, details_col2 = st.columns(2)
    with details_col1:
        st.markdown("##### Nearby News Rows")
        if nearby_news.empty:
            if news_frame.empty:
                st.info("No news export file is available for this dashboard.")
            else:
                window_start = entry_time - pd.Timedelta(minutes=before_minutes)
                window_end = exit_time + pd.Timedelta(minutes=after_minutes)
                news_start = news_frame["timestamp"].min()
                news_end = news_frame["timestamp"].max()
                st.info(
                    "No news rows were found for this trade window. "
                    f"Trade window: {window_start:%Y-%m-%d %H:%M} to {window_end:%Y-%m-%d %H:%M}. "
                    f"Available news: {news_start:%Y-%m-%d %H:%M} to {news_end:%Y-%m-%d %H:%M}."
                )
        else:
            st.dataframe(
                nearby_news[
                    [
                        "timestamp",
                        "event",
                        "currency",
                        "impact",
                        "forecast",
                        "result",
                        "minutes_from_entry",
                        "minutes_from_exit",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=320,
            )

    with details_col2:
        st.markdown("##### Nearby Spread Rows")
        if nearby_spread.empty:
            if spread_frame.empty:
                st.info("No spread export file is available for this dashboard.")
            else:
                spread_start = spread_frame["timestamp"].min()
                spread_end = spread_frame["timestamp"].max()
                st.info(
                    "No spread rows were found for this trade window. "
                    f"Available spread data: {spread_start:%Y-%m-%d %H:%M} to {spread_end:%Y-%m-%d %H:%M}."
                )
        else:
            st.dataframe(
                nearby_spread[
                    [
                        "timestamp",
                        "pair",
                        "spread",
                        "price",
                        "tick_volume",
                        "atr",
                        "minutes_from_entry",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=320,
            )


with tab_overview:
    kpis = stats.compute_all(trades)
    dd = stats.max_drawdown(trades)
    advanced = stats.advanced_kpis(trades)

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Total Trades", f"{kpis['Total Trades']:,}")
    with col2:
        st.metric("Win Rate", f"{kpis['Win Rate (%)']:.1f}%")
    with col3:
        st.metric("Total PnL (pips)", f"{kpis['Total PnL (pips)']:+.1f}")
    with col4:
        st.metric("Avg Trade (pips)", f"{kpis['Avg Trade (pips)']:+.2f}")
    with col5:
        st.metric("Avg Duration", f"{kpis['Avg Duration (min)']:.0f} min")
    with col6:
        st.metric("Max Drawdown", f"{dd:.1f} pips")

    st.markdown("---")
    st.markdown("### Strategy Insights")
    insights = stats.strategy_insights(trades)

    if insights:
        i_col1, i_col2, i_col3 = st.columns(3)
        with i_col1:
            if "Best Entry Hour" in insights:
                st.markdown(
                    f"**Best Entry Hour**: {insights['Best Entry Hour']['label']}  \n"
                    f"{insights['Best Entry Hour']['val']:+.1f} pips avg  \n"
                    f"({insights['Best Entry Hour']['count']} trades)"
                )
                st.markdown(
                    f"**Worst Entry Hour**: {insights['Worst Entry Hour']['label']}  \n"
                    f"{insights['Worst Entry Hour']['val']:+.1f} pips avg  \n"
                    f"({insights['Worst Entry Hour']['count']} trades)"
                )
        with i_col2:
            if "Best Session" in insights:
                st.markdown(
                    f"**Best Session**: {insights['Best Session']['label']}  \n"
                    f"{insights['Best Session']['val']:+.1f} pips avg  \n"
                    f"({insights['Best Session']['count']} trades)"
                )
                st.markdown(
                    f"**Worst Session**: {insights['Worst Session']['label']}  \n"
                    f"{insights['Worst Session']['val']:+.1f} pips avg  \n"
                    f"({insights['Worst Session']['count']} trades)"
                )
        with i_col3:
            if "Best Duration" in insights:
                st.markdown(
                    f"**Best Duration**: {insights['Best Duration']['label']}  \n"
                    f"{insights['Best Duration']['val']:+.1f} pips avg  \n"
                    f"({insights['Best Duration']['count']} trades)"
                )
                st.markdown(
                    f"**Worst Duration**: {insights['Worst Duration']['label']}  \n"
                    f"{insights['Worst Duration']['val']:+.1f} pips avg  \n"
                    f"({insights['Worst Duration']['count']} trades)"
                )
    else:
        st.info("Not enough data to generate strategy insights.")

    st.markdown("---")
    st.markdown("### Advanced Statistics")

    adv_row1 = st.columns(4)
    adv_row1[0].metric("Gross Profit", f"{advanced['Gross Profit']:+.1f}")
    adv_row1[1].metric("Gross Loss", f"{advanced['Gross Loss']:+.1f}")
    adv_row1[2].metric("Profit Factor", f"{advanced['Profit Factor']:.2f}")
    adv_row1[3].metric("Expectancy", f"{advanced['Expectancy']:+.2f}")

    adv_row2 = st.columns(4)
    adv_row2[0].metric("Avg Win", f"{advanced['Avg Win']:+.2f}")
    adv_row2[1].metric("Avg Loss", f"{advanced['Avg Loss']:+.2f}")
    adv_row2[2].metric("Reward / Risk", f"{advanced['Reward/Risk']:.2f}")
    adv_row2[3].metric("Median Trade", f"{advanced['Median Trade']:+.2f}")

    adv_row3 = st.columns(4)
    adv_row3[0].metric("Std Dev", f"{advanced['Std Dev']:.2f}")
    adv_row3[1].metric("Best Trade", f"{advanced['Best Trade']:+.1f}")
    adv_row3[2].metric("Worst Trade", f"{advanced['Worst Trade']:+.1f}")
    adv_row3[3].metric(
        "Win / Loss Streak",
        f"{advanced['Max Win Streak']} / {advanced['Max Loss Streak']}",
    )


with tab_equity:
    st.markdown("### Equity Curve")
    st.plotly_chart(charts.equity_curve_chart(trades), use_container_width=True)
    st.markdown("### Drawdown")
    st.plotly_chart(charts.drawdown_chart(trades), use_container_width=True)


with tab_behavior:
    st.markdown("### Performance Charts")

    chart_r1_left, chart_r1_right = st.columns(2)
    with chart_r1_left:
        st.plotly_chart(charts.exit_reason_chart(trades), use_container_width=True)
    with chart_r1_right:
        st.plotly_chart(charts.pnl_distribution_chart(trades), use_container_width=True)

    chart_r2_left, chart_r2_right = st.columns(2)
    with chart_r2_left:
        st.plotly_chart(charts.trades_by_hour_chart(trades), use_container_width=True)
    with chart_r2_right:
        st.plotly_chart(charts.avg_pnl_by_hour_chart(trades), use_container_width=True)

    st.markdown("---")
    st.markdown("### MAE / MFE Analysis")

    mae_col, mfe_col = st.columns(2)
    with mae_col:
        st.plotly_chart(charts.mae_distribution_chart(trades), use_container_width=True)
    with mfe_col:
        st.plotly_chart(charts.mfe_distribution_chart(trades), use_container_width=True)

    dist_col1, dist_col2, dist_col3 = st.columns(3)
    with dist_col1:
        st.plotly_chart(charts.pnl_violin_by_hour_chart(trades), use_container_width=True)
    with dist_col2:
        st.plotly_chart(charts.mae_violin_by_hour_chart(trades), use_container_width=True)
    with dist_col3:
        st.plotly_chart(charts.duration_violin_by_hour_chart(trades), use_container_width=True)

    scatter_fig = charts.mfe_vs_mae_chart(trades)
    st.caption("Click a scatter point to inspect that trade on the candlestick chart below.")

    if plotly_events is not None:
        clicked_points = plotly_events(
            scatter_fig,
            click_event=True,
            hover_event=False,
            select_event=False,
            override_height=520,
            key="behavior_mfe_mae_scatter",
        )
        if clicked_points:
            clicked_point = clicked_points[0]
            curve_index = clicked_point.get("curveNumber", 0)
            point_index = clicked_point.get("pointIndex", clicked_point.get("pointNumber"))
            if point_index is not None and len(scatter_fig.data) > curve_index:
                customdata = scatter_fig.data[curve_index].customdata
                if customdata is not None and len(customdata) > point_index:
                    st.session_state["selected_trade_id"] = int(customdata[point_index][0])
    else:
        st.plotly_chart(scatter_fig, use_container_width=True)
        st.info("Install streamlit-plotly-events to enable scatter click-through.")

    st.markdown("---")
    render_trade_investigation(
        trades,
        prices,
        st.session_state.get("selected_trade_id"),
        key_prefix="behavior",
        heading="### Scatter-Selected Trade",
    )

    st.markdown("---")
    st.markdown("### Exit Optimization")
    st.caption(
        "These optimization charts use observed MAE/MFE as simplified trigger conditions for fixed stop-loss and take-profit levels."
    )
    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        st.plotly_chart(charts.stop_loss_optimization_chart(trades), use_container_width=True)
    with opt_col2:
        st.plotly_chart(charts.take_profit_optimization_chart(trades), use_container_width=True)


with tab_session:
    st.markdown("### Session Analysis")

    sess_col1, sess_col2, sess_col3 = st.columns(3)
    with sess_col1:
        st.plotly_chart(charts.session_count_chart(trades), use_container_width=True)
    with sess_col2:
        st.plotly_chart(charts.session_pnl_chart(trades), use_container_width=True)
    with sess_col3:
        st.plotly_chart(charts.session_winrate_chart(trades), use_container_width=True)

    st.markdown("---")
    heatmap_col1, heatmap_col2 = st.columns(2)
    with heatmap_col1:
        st.plotly_chart(charts.trades_by_weekday_hour_heatmap(trades), use_container_width=True)
    with heatmap_col2:
        st.plotly_chart(charts.avg_pnl_by_weekday_hour_heatmap(trades), use_container_width=True)

    heatmap_col3, heatmap_col4 = st.columns(2)
    with heatmap_col3:
        st.plotly_chart(charts.total_pnl_by_weekday_hour_heatmap(trades), use_container_width=True)
    with heatmap_col4:
        st.plotly_chart(charts.mae_by_weekday_hour_heatmap(trades), use_container_width=True)

    st.markdown("---")
    st.markdown("### Detailed Statistics Tables")
    table_col1, table_col2 = st.columns(2)
    with table_col1:
        st.markdown("#### Hourly")
        st.dataframe(stats.hourly_performance_table(trades), use_container_width=True, hide_index=True)
    with table_col2:
        st.markdown("#### Weekday")
        st.dataframe(stats.weekday_performance_table(trades), use_container_width=True, hide_index=True)


with tab_duration:
    st.markdown("### Duration Analysis")

    dur_col1, dur_col2 = st.columns(2)
    with dur_col1:
        st.plotly_chart(charts.duration_count_chart(trades), use_container_width=True)
    with dur_col2:
        st.plotly_chart(charts.duration_pnl_chart(trades), use_container_width=True)


with tab_investigation:
    st.markdown("### Trades Table")
    st.caption("Use the selector below to investigate a trade in detail.")

    display_df = trades[
        [
            "trade_id",
            "entry_time",
            "exit_time",
            "direction",
            "entry_price",
            "exit_price",
            "pnl_pips",
            "exit_reason",
            "duration_minutes",
        ]
    ].copy()
    display_df.columns = [
        "ID",
        "Entry Time",
        "Exit Time",
        "Direction",
        "Entry Price",
        "Exit Price",
        "PnL (pips)",
        "Exit Reason",
        "Duration (min)",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    trade_ids = display_df["ID"].astype(int).tolist()
    default_trade_id = st.session_state.get("selected_trade_id", trade_ids[0])
    if default_trade_id not in trade_ids:
        default_trade_id = trade_ids[0]

    selected_trade_id = st.selectbox(
        "Trade ID",
        options=trade_ids,
        index=trade_ids.index(default_trade_id),
        key="selected_trade_id",
    )

    st.markdown("---")
    render_trade_investigation(
        trades,
        prices,
        selected_trade_id,
        key_prefix="investigation",
    )

    st.markdown("---")
    render_trade_news_context(
        trade_frame=trades,
        news_frame=all_news,
        spread_frame=all_spread,
        slider_key_prefix="investigation_trade_news",
        heading="#### News Context For Selected Trade",
        caption="This section follows the current trade investigation selection and ignores the News Analysis tab filters.",
    )


with tab_news:
    st.markdown("### News Analysis")

    if all_news.empty:
        st.info("No news export file was found in the configured local data directories.")
    else:
        render_trade_news_context(
            trade_frame=trades,
            news_frame=all_news,
            spread_frame=all_spread,
            slider_key_prefix="news_tab_trade_news",
            heading="#### Selected Trade Context",
            caption="Pick a trade in Trade Investigation or from the scatter drill-down, then inspect the nearby news and spread context here.",
        )

        st.markdown("---")
        news_col1, news_col2, news_col3 = st.columns(3)

        available_currencies = sorted(all_news["currency"].dropna().unique().tolist())
        available_impacts = [
            impact
            for impact in news_analysis.IMPACT_ORDER
            if impact in all_news["impact"].dropna().unique().tolist()
        ]
        date_min = all_news["timestamp"].min().date()
        date_max = all_news["timestamp"].max().date()

        with news_col1:
            selected_currencies = st.multiselect(
                "Currencies",
                options=available_currencies,
                default=available_currencies,
                key="news_currencies",
            )
        with news_col2:
            selected_impacts = st.multiselect(
                "Impact",
                options=available_impacts,
                default=available_impacts,
                key="news_impacts",
            )
        with news_col3:
            event_search = st.text_input(
                "Event Search",
                value="",
                key="news_event_search",
                placeholder="Search event text",
            )

        selected_news_dates = st.date_input(
            "News Date Range",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max,
            key="news_dates",
        )

        filtered_news = news_analysis.filter_news(
            all_news,
            currencies=selected_currencies,
            impacts=selected_impacts,
            event_search=event_search,
            date_range=selected_news_dates,
        )
        filtered_spread = news_analysis.filter_spread(
            all_spread,
            date_range=selected_news_dates,
        )

        summary = news_analysis.news_summary(filtered_news)
        summary_cols = st.columns(5)
        summary_cols[0].metric("Total News", f"{summary['Total News']}")
        summary_cols[1].metric("High Impact", f"{summary['High Impact']}")
        summary_cols[2].metric("Currencies", f"{summary['Currencies']}")
        summary_cols[3].metric("Busiest Hour", summary["Busiest Hour"])
        summary_cols[4].metric("Busiest Day", summary["Busiest Day"])

        st.markdown("---")

        default_month_day = st.session_state.get("news_selected_month_day")
        default_hour = st.session_state.get("news_selected_hour")

        heatmap_fig = news_analysis.news_impact_heatmap(
            filtered_news,
            selected_month_day=default_month_day,
            selected_hour=default_hour,
        )

        if plotly_events is not None:
            clicked_news_points = plotly_events(
                heatmap_fig,
                click_event=True,
                hover_event=False,
                select_event=False,
                override_height=650,
                key="news_heatmap_clicks",
            )
            if clicked_news_points:
                clicked_news = clicked_news_points[0]
                st.session_state["news_selected_month_day"] = clicked_news.get("y")
                st.session_state["news_selected_hour"] = int(clicked_news.get("x"))
        else:
            st.plotly_chart(heatmap_fig, use_container_width=True)

        selected_month_day = st.session_state.get("news_selected_month_day")
        selected_hour = st.session_state.get("news_selected_hour")
        selected_weekday_name = None
        if selected_month_day:
            weekday_short = selected_month_day[:2]
            selected_weekday_name = {
                "mo": "Monday",
                "tu": "Tuesday",
                "we": "Wednesday",
                "th": "Thursday",
                "fr": "Friday",
                "sa": "Saturday",
                "su": "Sunday",
            }.get(weekday_short)

        chart_row1_col1, chart_row1_col2 = st.columns(2)
        with chart_row1_col1:
            st.plotly_chart(
                news_analysis.news_count_by_hour_violin(
                    filtered_news, selected_hour=selected_hour
                ),
                use_container_width=True,
            )
        with chart_row1_col2:
            st.plotly_chart(
                news_analysis.news_count_by_weekday_violin(
                    filtered_news, selected_weekday_name=selected_weekday_name
                ),
                use_container_width=True,
            )

        chart_row2_col1, chart_row2_col2 = st.columns(2)
        with chart_row2_col1:
            st.plotly_chart(
                news_analysis.news_count_by_month_day_violin(
                    filtered_news, selected_month_day=selected_month_day
                ),
                use_container_width=True,
            )
        with chart_row2_col2:
            st.plotly_chart(
                news_analysis.news_impact_distribution_chart(filtered_news),
                use_container_width=True,
            )

        st.plotly_chart(
            news_analysis.news_currency_distribution_chart(filtered_news),
            use_container_width=True,
        )

        st.markdown("---")
        st.markdown("#### Filtered News Table")
        filtered_display = filtered_news[
            ["date", "time", "event", "currency", "impact", "forecast", "result"]
        ].copy()
        st.dataframe(filtered_display, use_container_width=True, hide_index=True, height=320)

        st.markdown("#### Heatmap Cell Details")
        cell_rows = news_analysis.news_rows_for_heatmap_cell(
            filtered_news,
            selected_month_day,
            selected_hour,
        )
        if cell_rows.empty:
            st.info("Click a heatmap cell to inspect the news rows for that month-day / hour bucket.")
        else:
            st.caption(
                f"Selected bucket: {selected_month_day} at {int(selected_hour):02d}:00"
            )
            st.dataframe(cell_rows, use_container_width=True, hide_index=True, height=320)

        st.markdown("---")
        st.markdown("#### Spread Linked To News Timing")

        if filtered_spread.empty:
            st.info("No spread data is available for the currently selected news date range.")
        else:
            spread_col1, spread_col2 = st.columns(2)
            with spread_col1:
                st.plotly_chart(
                    news_analysis.mean_spread_heatmap(
                        filtered_spread,
                        selected_month_day=selected_month_day,
                        selected_hour=selected_hour,
                    ),
                    use_container_width=True,
                )
            with spread_col2:
                st.plotly_chart(
                    news_analysis.max_spread_heatmap(
                        filtered_spread,
                        selected_month_day=selected_month_day,
                        selected_hour=selected_hour,
                    ),
                    use_container_width=True,
                )

            spread_rows = news_analysis.spread_rows_for_heatmap_cell(
                filtered_spread,
                selected_month_day,
                selected_hour,
            )
            if spread_rows.empty:
                st.info("Click a news heatmap cell to inspect the aligned spread rows for that same bucket.")
            else:
                st.caption(
                    f"Spread rows aligned to {selected_month_day} at {int(selected_hour):02d}:00"
                )
                st.dataframe(
                    spread_rows,
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )

        st.markdown("---")
        st.markdown("#### Trade vs News Overlap")
        overlap_window = st.slider(
            "News proximity window (minutes)",
            min_value=5,
            max_value=240,
            value=60,
            step=5,
            key="news_overlap_window",
        )

        overlap_rows, overlap_summary = news_analysis.trade_news_overlap(
            trades,
            filtered_news,
            window_minutes=overlap_window,
        )

        if overlap_rows.empty:
            trade_start = trades["entry_time"].min()
            trade_end = trades["entry_time"].max()
            if filtered_news.empty:
                st.info("No filtered news rows are available for overlap analysis.")
            else:
                news_start = filtered_news["timestamp"].min()
                news_end = filtered_news["timestamp"].max()
                st.info(
                    "No trade/news overlap was found. "
                    f"Trades span {trade_start:%Y-%m-%d %H:%M} to {trade_end:%Y-%m-%d %H:%M}, "
                    f"while filtered news spans {news_start:%Y-%m-%d %H:%M} to {news_end:%Y-%m-%d %H:%M}."
                )
        else:
            overlap_kpi = st.columns(4)
            overlap_kpi[0].metric("Trades Near News", f"{len(overlap_rows)}")
            overlap_kpi[1].metric(
                "Avg PnL Near News",
                f"{overlap_rows['pnl_pips'].mean():+.2f}",
            )
            overlap_kpi[2].metric(
                "Win Rate Near News",
                f"{(overlap_rows['pnl_pips'] > 0).mean() * 100:.1f}%",
            )
            overlap_kpi[3].metric(
                "Avg Minutes To News",
                f"{overlap_rows['minutes_from_entry'].mean():.1f}",
            )

            overlap_table_col1, overlap_table_col2 = st.columns(2)
            with overlap_table_col1:
                st.markdown("##### By Impact")
                st.dataframe(
                    overlap_summary,
                    use_container_width=True,
                    hide_index=True,
                )
            with overlap_table_col2:
                st.markdown("##### Overlap Rows")
                st.dataframe(
                    overlap_rows[
                        [
                            "trade_id",
                            "entry_time",
                            "event",
                            "currency",
                            "impact",
                            "minutes_from_entry",
                            "pnl_pips",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )

            st.markdown("---")
            st.markdown("#### Strategy Impact By News Type")

            strategy_kpis = news_analysis.strategy_news_kpis(trades, overlap_rows)
            strategy_cols = st.columns(4)
            strategy_cols[0].metric(
                "Near-News Share",
                f"{strategy_kpis['near_news_share']:.1f}%",
            )
            strategy_cols[1].metric(
                "Avg PnL Away News",
                f"{strategy_kpis['avg_pnl_away_news']:+.2f}",
                delta=f"{strategy_kpis['avg_pnl_near_news'] - strategy_kpis['avg_pnl_away_news']:+.2f} vs near",
            )
            strategy_cols[2].metric(
                "Win Rate Near News",
                f"{strategy_kpis['win_rate_near_news']:.1f}%",
            )
            strategy_cols[3].metric(
                "Win Rate Away News",
                f"{strategy_kpis['win_rate_away_news']:.1f}%",
                delta=f"{strategy_kpis['win_rate_near_news'] - strategy_kpis['win_rate_away_news']:+.1f} pts near",
            )

            sample_col1, sample_col2 = st.columns(2)
            with sample_col1:
                min_currency_trades = st.slider(
                    "Min trades per currency",
                    min_value=1,
                    max_value=20,
                    value=3,
                    step=1,
                    key="news_currency_min_trades",
                )
            with sample_col2:
                min_event_trades = st.slider(
                    "Min trades per event",
                    min_value=1,
                    max_value=20,
                    value=3,
                    step=1,
                    key="news_event_min_trades",
                )

            impact_perf = news_analysis.impact_strategy_performance(overlap_rows)
            timing_perf = news_analysis.timing_strategy_performance(overlap_rows)
            direction_perf = news_analysis.direction_strategy_performance(overlap_rows)
            currency_perf = news_analysis.currency_strategy_performance(
                overlap_rows,
                min_trades=min_currency_trades,
            )
            event_perf = news_analysis.event_strategy_performance(
                overlap_rows,
                min_trades=min_event_trades,
            )

            impact_chart_col1, impact_chart_col2 = st.columns(2)
            with impact_chart_col1:
                st.plotly_chart(
                    news_analysis.strategy_metric_bar_chart(
                        impact_perf,
                        category_col="impact",
                        metric_col="avg_pnl",
                        title="Average PnL By News Impact",
                    ),
                    use_container_width=True,
                )
            with impact_chart_col2:
                st.plotly_chart(
                    news_analysis.strategy_metric_bar_chart(
                        impact_perf,
                        category_col="impact",
                        metric_col="win_rate",
                        title="Win Rate By News Impact",
                    ),
                    use_container_width=True,
                )

            timing_chart_col1, timing_chart_col2 = st.columns(2)
            with timing_chart_col1:
                st.plotly_chart(
                    news_analysis.strategy_metric_bar_chart(
                        timing_perf,
                        category_col="timing_bucket",
                        metric_col="avg_pnl",
                        title="Average PnL By News Timing",
                    ),
                    use_container_width=True,
                )
            with timing_chart_col2:
                st.plotly_chart(
                    news_analysis.strategy_metric_bar_chart(
                        direction_perf,
                        category_col="direction",
                        metric_col="win_rate",
                        title="Win Rate By Direction Near News",
                    ),
                    use_container_width=True,
                )

            selected_event = st.session_state.get("news_selected_event")
            available_event_options = event_perf["event"].tolist() if not event_perf.empty else []
            if selected_event not in available_event_options:
                selected_event = None
                st.session_state["news_selected_event"] = None

            st.markdown("##### Event Drill-Down")
            event_chart = news_analysis.event_strategy_bar_chart(
                event_perf,
                selected_event=selected_event,
                metric_col="avg_pnl",
            )
            if plotly_events is not None and not event_perf.empty:
                clicked_event_points = plotly_events(
                    event_chart,
                    click_event=True,
                    hover_event=False,
                    select_event=False,
                    override_height=420,
                    key="news_event_ranking_clicks",
                )
                if clicked_event_points:
                    clicked_event = clicked_event_points[0].get("y")
                    if clicked_event:
                        st.session_state["news_selected_event"] = clicked_event
                        st.session_state["news_event_selector"] = clicked_event
                        selected_event = clicked_event
            else:
                st.plotly_chart(event_chart, use_container_width=True)

            selector_options = ["All ranked events"] + available_event_options
            if selected_event:
                st.session_state["news_event_selector"] = selected_event
            elif st.session_state.get("news_event_selector") not in selector_options:
                st.session_state["news_event_selector"] = "All ranked events"

            event_control_col1, event_control_col2 = st.columns([3, 1])
            with event_control_col1:
                selected_event = st.selectbox(
                    "Selected event",
                    options=selector_options,
                    key="news_event_selector",
                )
            with event_control_col2:
                if st.button("Clear event focus", key="news_clear_event_focus"):
                    st.session_state["news_selected_event"] = None
                    st.session_state["news_event_selector"] = "All ranked events"
                    selected_event = "All ranked events"

            if selected_event == "All ranked events":
                selected_event = None
            st.session_state["news_selected_event"] = selected_event

            focused_overlap = news_analysis.filter_overlap_for_event(
                overlap_rows,
                event_name=selected_event,
            )

            if selected_event:
                st.caption(f"Focused event: {selected_event}")
            else:
                st.caption("Focused event: all ranked events")

            st.plotly_chart(
                news_analysis.impact_vs_trade_scatter(focused_overlap),
                use_container_width=True,
            )

            strategy_table_col1, strategy_table_col2 = st.columns(2)
            with strategy_table_col1:
                st.markdown("##### By Currency")
                if currency_perf.empty:
                    st.info("No currency groups meet the current minimum-trades threshold.")
                else:
                    st.dataframe(
                        currency_perf,
                        use_container_width=True,
                        hide_index=True,
                        height=320,
                    )
            with strategy_table_col2:
                st.markdown("##### By Event")
                if event_perf.empty:
                    st.info("No event groups meet the current minimum-trades threshold.")
                else:
                    st.dataframe(
                        event_perf,
                        use_container_width=True,
                        hide_index=True,
                        height=320,
                    )

            focused_col1, focused_col2 = st.columns(2)
            with focused_col1:
                st.markdown("##### By Timing")
                if timing_perf.empty:
                    st.info("No timing groups are available for the current overlap set.")
                else:
                    st.dataframe(
                        timing_perf,
                        use_container_width=True,
                        hide_index=True,
                    )
            with focused_col2:
                st.markdown("##### Focused Overlap Rows")
                st.dataframe(
                    focused_overlap[
                        [
                            "trade_id",
                            "direction",
                            "entry_time",
                            "event",
                            "currency",
                            "impact",
                            "timing_bucket",
                            "signed_minutes_from_entry",
                            "pnl_pips",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )
