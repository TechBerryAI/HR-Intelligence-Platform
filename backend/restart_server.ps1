# PowerShell script to restart Flask server
Write-Host "Stopping any existing Flask server on port 3000..." -ForegroundColor Yellow
$processes = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $processes) {
    Write-Host "Killing process $pid" -ForegroundColor Red
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Write-Host "Starting Flask server..." -ForegroundColor Green
python app.py

