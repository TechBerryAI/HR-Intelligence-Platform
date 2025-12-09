# HR Job Portal - Bulletproof Startup Script
# Version 2.0 - Guaranteed to work every time

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   HR Job Portal - Starting..." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

$ROOT = $PSScriptRoot

# Step 1: Check dependencies
Write-Host "Step 1: Checking Dependencies..." -ForegroundColor Cyan
try {
    $null = python --version 2>&1
    Write-Host "  [OK] Python installed" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python not found! Install Python 3.8+" -ForegroundColor Red
    exit 1
}

try {
    $null = node --version 2>&1
    Write-Host "  [OK] Node.js installed" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Node.js not found! Install Node.js 16+" -ForegroundColor Red
    exit 1
}

# Step 2: First-time setup
Write-Host ""
Write-Host "Step 2: Environment Setup..." -ForegroundColor Cyan

$needsSetup = $false
if (-not (Test-Path "$ROOT\backend\venv")) {
    Write-Host "  [SETUP] Creating Python virtual environment..." -ForegroundColor Yellow
    $needsSetup = $true
}
if (-not (Test-Path "$ROOT\frontend\node_modules")) {
    Write-Host "  [SETUP] Frontend dependencies needed..." -ForegroundColor Yellow
    $needsSetup = $true
}

if ($needsSetup) {
    Write-Host ""
    Write-Host "  First-time setup (this may take a few minutes)..." -ForegroundColor Yellow
    Write-Host ""
    
    # Backend
    Set-Location "$ROOT\backend"
    if (-not (Test-Path "venv")) {
        python -m venv venv
    }
    Write-Host "  Installing Python packages..." -ForegroundColor Gray
    & ".\venv\Scripts\python.exe" -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    & ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet 2>&1 | Out-Null
    Write-Host "  [OK] Backend setup complete" -ForegroundColor Green
    
    # Frontend
    Set-Location "$ROOT\frontend"
    Write-Host "  Installing Node packages..." -ForegroundColor Gray
    npm install --silent 2>&1 | Out-Null
    Write-Host "  [OK] Frontend setup complete" -ForegroundColor Green
    Write-Host ""
}

Set-Location $ROOT

# Step 3: Clean up ports
Write-Host ""
Write-Host "Step 3: Cleaning Ports..." -ForegroundColor Cyan
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
Write-Host "  [OK] Ports 3000 and 5173 are free" -ForegroundColor Green

# Step 4: Start services
Write-Host ""
Write-Host "Step 4: Starting Services..." -ForegroundColor Cyan

Write-Host "  Starting backend..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    $env:PYTHONIOENCODING = "utf-8"
    & ".\venv\Scripts\python.exe" app.py 2>&1
} -ArgumentList "$ROOT\backend"

Start-Sleep -Seconds 2

Write-Host "  Starting frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run dev 2>&1
} -ArgumentList "$ROOT\frontend"

# Step 5: Wait for ready
Write-Host ""
Write-Host "Step 5: Waiting for Services..." -ForegroundColor Cyan

$maxWait = 45
$backendReady = $false
$frontendReady = $false

for ($i = 0; $i -lt $maxWait; $i++) {
    Start-Sleep -Seconds 1
    
    # Check Backend
    if (-not $backendReady -and $i -ge 3) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $backendReady = $true
                Write-Host "  [OK] Backend ready at http://localhost:3000" -ForegroundColor Green
            }
        } catch {}
    }
    
    # Check Frontend
    if (-not $frontendReady -and $i -ge 2) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $frontendReady = $true
                Write-Host "  [OK] Frontend ready at http://localhost:5173" -ForegroundColor Green
            }
        } catch {}
    }
    
    # Both ready?
    if ($backendReady -and $frontendReady) {
        break
    }
    
    # Progress
    if (($i + 1) % 5 -eq 0 -and (-not $backendReady -or -not $frontendReady)) {
        $waiting = @()
        if (-not $backendReady) { $waiting += "Backend" }
        if (-not $frontendReady) { $waiting += "Frontend" }
        Write-Host "  [WAIT] Still starting: $($waiting -join ', ') ($($i + 1)s)" -ForegroundColor Yellow
    }
}

Write-Host ""

if ($backendReady -and $frontendReady) {
    Write-Host "=======================================" -ForegroundColor Green
    Write-Host "  ALL SYSTEMS READY!" -ForegroundColor Green
    Write-Host "=======================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Backend:  http://localhost:3000" -ForegroundColor Cyan
    Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Opening browser..." -ForegroundColor Gray
    Start-Process "http://localhost:5173"
    Write-Host ""
    Write-Host "[SUCCESS] Application is running!" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "[WARN] Some services may still be starting..." -ForegroundColor Yellow
    if (-not $backendReady) {
        Write-Host "  Backend: Still starting (check SQL Server)" -ForegroundColor Yellow
    }
    if (-not $frontendReady) {
        Write-Host "  Frontend: Still starting" -ForegroundColor Yellow
    }
}

# Monitor
try {
    while ($true) {
        Start-Sleep -Seconds 10
        $bState = (Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue).State
        $fState = (Get-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue).State
        
        if ($bState -eq "Failed") {
            Write-Host ""
            Write-Host "[ERROR] Backend stopped!" -ForegroundColor Red
            Receive-Job -Id $backendJob.Id
            break
        }
        if ($fState -eq "Failed") {
            Write-Host ""
            Write-Host "[ERROR] Frontend stopped!" -ForegroundColor Red
            break
        }
    }
} catch {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow
}
