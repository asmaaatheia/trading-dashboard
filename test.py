import sys
import pandas as pd
from modules.data_loader import load_trades, load_prices
from modules import statistics as stats

try:
    all_trades = load_trades()
    insights = stats.strategy_insights(all_trades)
    with open('_output/explore_python_utf8.log', 'w', encoding='utf-8') as f:
        f.write(str(insights))
except Exception as e:
    import traceback
    with open('_output/explore_python_utf8.log', 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
