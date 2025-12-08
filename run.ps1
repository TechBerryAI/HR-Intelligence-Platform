# HR Job Portal - Quick Run Script

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "=== HR Job Portal ===" -ForegroundColor Cyan
Write-Host ""

$ROOT = $PSScriptRoot

# Check if first time setup is needed
$needsSetup = $false

if (-not (Test-Path "$ROOT\backend\venv")) {
    Write-Host "First time setup detected..." -ForegroundColor Yellow
    $needsSetup = $true
}

if (-not (Test-Path "$ROOT\frontend\node_modules")) {
    $needsSetup = $true
}

# First time setup
if ($needsSetup) {
    Write-Host "Setting up environment (this may take a few minutes)..." -ForegroundColor Yellow
    
    # Backend setup
    Write-Host "Setting up backend..." -ForegroundColor Gray
    Set-Location "$ROOT\backend"
    
    if (-not (Test-Path "venv")) {
        python -m venv venv
    }
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
        }
    }
    
    & ".\venv\Scripts\python.exe" -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    & ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet 2>&1 | Out-Null
    
    # Frontend setup
    Write-Host "Setting up frontend..." -ForegroundColor Gray
    Set-Location "$ROOT\frontend"
    
    if (-not (Test-Path ".env")) {
        "VITE_API_URL=http://localhost:3000" | Out-File -FilePath ".env" -Encoding UTF8
        "VITE_API_TIMEOUT_MS=15000" | Add-Content -Path ".env" -Encoding UTF8
    }
    
    npm install --silent 2>&1 | Out-Null
    
    Write-Host "Setup complete!" -ForegroundColor Green
    Write-Host ""
}

Set-Location $ROOT

# Clean up ports
Write-Host "Checking ports..." -ForegroundColor Gray
try {
    Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique | 
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
} catch {}
try {
    Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique | 
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
} catch {}

Start-Sleep -Seconds 1

# Start Backend
Write-Host "Starting backend..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    $env:PYTHONIOENCODING = "utf-8"
    & ".\venv\Scripts\python.exe" app.py 2>&1
} -ArgumentList "$ROOT\backend"

Start-Sleep -Seconds 4

# Start Frontend
Write-Host "Starting frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run dev 2>&1
} -ArgumentList "$ROOT\frontend"

Write-Host "Waiting for servers..." -ForegroundColor Gray
Start-Sleep -Seconds 6

# Check Backend
Write-Host ""
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host "[OK] Backend:  http://localhost:3000" -ForegroundColor Green
    }
} catch {
    Write-Host "[WAIT] Backend: starting..." -ForegroundColor Yellow
}

# Check Frontend
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host "[OK] Frontend: http://localhost:5173" -ForegroundColor Green
    }
} catch {
    Write-Host "[WAIT] Frontend: starting..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Jobs: Backend=$($backendJob.Id) Frontend=$($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""

# Open browser
Start-Sleep -Seconds 2
Write-Host "Opening browser..." -ForegroundColor Cyan
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Application running! Press Ctrl+C to exit." -ForegroundColor Green
Write-Host ""

# Monitor
try {
    while ($true) {
        Start-Sleep -Seconds 10
        $bState = (Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue).State
        $fState = (Get-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue).State
        
        if ($bState -eq "Failed") {
            Write-Host ""
            Write-Host "Backend stopped!" -ForegroundColor Red
            break
        }
        if ($fState -eq "Failed") {
            Write-Host ""
            Write-Host "Frontend stopped!" -ForegroundColor Red
            break
        }
    }
} catch {
    Write-Host ""
    Write-Host "Exiting. Servers still running." -ForegroundColor Yellow
}
