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

# Start Backend (with integrated Python LLM parsing)
Write-Host "Starting backend..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    $env:PYTHONIOENCODING = "utf-8"
    & ".\venv\Scripts\python.exe" app.py 2>&1
} -ArgumentList "$ROOT\backend"

# Give backend a moment to start binding to port
Start-Sleep -Seconds 2

# Start Frontend immediately
Write-Host "Starting frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run dev 2>&1
} -ArgumentList "$ROOT\frontend"

Write-Host "Waiting for servers to start..." -ForegroundColor Gray

# Smart waiting with progressive checks
$maxWait = 45  # Increased from 30 to 45 seconds
$backendReady = $false
$frontendReady = $false
$backendChecked = $false
$frontendChecked = $false

for ($i = 0; $i -lt $maxWait; $i++) {
    Start-Sleep -Seconds 1
    
    # Check Backend (start checking after 3 seconds to give it time to start)
    if (-not $backendReady -and $i -ge 3) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $backendReady = $true
                if (-not $backendChecked) {
                    Write-Host "[OK] Backend:     http://localhost:3000" -ForegroundColor Green
                    $backendChecked = $true
                }
            }
        } catch {
            # Still waiting - check job state
            $jobState = (Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue).State
            if ($jobState -eq "Failed" -or $jobState -eq "Stopped") {
                Write-Host "[ERROR] Backend job failed! Check logs:" -ForegroundColor Red
                Receive-Job -Id $backendJob.Id | Write-Host -ForegroundColor Yellow
                break
            }
        }
    }
    
    # Check Frontend (start checking after 2 seconds)
    if (-not $frontendReady -and $i -ge 2) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $frontendReady = $true
                if (-not $frontendChecked) {
                    Write-Host "[OK] Frontend:    http://localhost:5173" -ForegroundColor Green
                    $frontendChecked = $true
                }
            }
        } catch {
            # Still waiting
        }
    }
    
    # Both ready? Break early!
    if ($backendReady -and $frontendReady) {
        break
    }
    
    # Progress indicator every 3 seconds
    if (($i + 1) % 3 -eq 0 -and (-not $backendReady -or -not $frontendReady)) {
        $elapsed = $i + 1
        $status = @()
        if (-not $backendReady) { $status += "Backend" }
        if (-not $frontendReady) { $status += "Frontend" }
        Write-Host "[WAIT] Starting $(($status -join ', '))... ($elapsed`s)" -ForegroundColor Yellow
    }
}

Write-Host ""

# Final status check
if (-not $backendReady) {
    Write-Host "[WARN] Backend is still starting (this is normal, it will be ready soon)" -ForegroundColor Yellow
    Write-Host "       Check logs if it doesn't become available within 1 minute" -ForegroundColor Gray
}

if (-not $frontendReady) {
    Write-Host "[WARN] Frontend is still starting..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Jobs: Backend=$($backendJob.Id) Frontend=$($frontendJob.Id)" -ForegroundColor Gray
Write-Host "Note: AI Parsing integrated in Backend (Python LLM)" -ForegroundColor Cyan
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
            Receive-Job -Id $backendJob.Id
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
