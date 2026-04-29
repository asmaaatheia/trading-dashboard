<#
.SYNOPSIS
Exploratory script to check strategy insights dict.
#>
# === CONFIG ===
$Log = ".\_output\explore_strategy_insights.log"
# ==============

New-Item -ItemType Directory -Force -Path ".\_output" | Out-Null

$pythonCode = @"
import sys
import pandas as pd
from modules.data_loader import load_trades, load_prices
from modules import statistics as stats

try:
    all_trades = load_trades()
    # Mock filters (no filters)
    insights = stats.strategy_insights(all_trades)
    print(insights)
except Exception as e:
    import traceback
    traceback.print_exc()
"@

$pythonCode | python -c "import sys; exec(sys.stdin.read())" | Out-File -FilePath $Log -Encoding utf8
Write-Host $Log
