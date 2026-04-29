<#
.SYNOPSIS
Launch the Streamlit Trading Dashboard within the isolated workspace venv.
#>

# === CONFIG ===
$VenvPython   = "C:\Users\HP\.gemini\antigravity\.venv\Scripts\python.exe"
$VenvStreamlit = "C:\Users\HP\.gemini\antigravity\.venv\Scripts\streamlit.exe"
$AppTarget    = "C:\Users\HP\.gemini\antigravity\scratch\trading_dashboard\app.py"
$LogFile      = "C:\Users\HP\.gemini\antigravity\_output\start_dashboard_log.txt"
# ==============

Write-Output "Starting Trading Dashboard..."
Write-Output "Streamlit: $VenvStreamlit"
Write-Output "App: $AppTarget"
Write-Output "Log: $LogFile"

# Install requirements first (pip install into venv)
$ReqFile = "C:\Users\HP\.gemini\antigravity\scratch\trading_dashboard\requirements.txt"
if (Test-Path $ReqFile) {
    Write-Output "Installing requirements..."
    & $VenvPython -m pip install -r $ReqFile --quiet 2>&1 | Out-File -FilePath $LogFile -Encoding utf8
    Write-Output "Requirements installed."
}

# Launch streamlit (non-blocking background)
Write-Output "Launching streamlit run..."
Start-Process -FilePath $VenvStreamlit -ArgumentList "run", $AppTarget, "--server.headless=true" -NoNewWindow
Write-Output "Dashboard launched. Open http://localhost:8501 in your browser."
Write-Output "Log path: $LogFile"
