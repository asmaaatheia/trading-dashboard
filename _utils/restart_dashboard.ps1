<#
.SYNOPSIS
Stop any running Streamlit process and relaunch the enhanced dashboard.
#>

# === CONFIG ===
$VenvStreamlit = "C:\Users\HP\.gemini\antigravity\.venv\Scripts\streamlit.exe"
$AppTarget     = "C:\Users\HP\.gemini\antigravity\scratch\trading_dashboard\app.py"
$LogFile       = "C:\Users\HP\.gemini\antigravity\_output\restart_dashboard_log.txt"
# ==============

Write-Output "Stopping any existing Streamlit processes..."
Get-Process -Name "streamlit" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Output "Launching enhanced dashboard..."
Start-Process -FilePath $VenvStreamlit -ArgumentList "run", $AppTarget, "--server.headless=true" -NoNewWindow

Start-Sleep -Seconds 3
Write-Output "Dashboard relaunched. Open http://localhost:8501"
Write-Output "Log path: $LogFile"
