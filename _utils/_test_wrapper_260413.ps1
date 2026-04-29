# === CONFIG ===
$Log = ".\_output\explore_python.log"
# ==============

New-Item -ItemType Directory -Force -Path ".\_output" | Out-Null

python test.py | Out-File -FilePath $Log -Encoding utf8
Write-Host $Log
