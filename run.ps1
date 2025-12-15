# HR Job Portal - Bulletproof Startup Script
# Version 3.1 - Enhanced database checking and automatic creation

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
if (-not (Test-Path "$ROOT\parsing-api\node_modules")) {
    Write-Host "  [SETUP] Parsing API dependencies needed..." -ForegroundColor Yellow
    $needsSetup = $true
}
if (-not (Test-Path "$ROOT\parsing-api\dist")) {
    Write-Host "  [SETUP] Parsing API needs to be built..." -ForegroundColor Yellow
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
    
    # Parsing API
    Set-Location "$ROOT\parsing-api"
    if (-not (Test-Path "node_modules")) {
        Write-Host "  Installing Parsing API packages..." -ForegroundColor Gray
        npm install --silent 2>&1 | Out-Null
        Write-Host "  [OK] Parsing API dependencies installed" -ForegroundColor Green
    }
    if (-not (Test-Path "dist")) {
        Write-Host "  Building Parsing API (TypeScript)..." -ForegroundColor Gray
        npm run build --silent 2>&1 | Out-Null
        Write-Host "  [OK] Parsing API built successfully" -ForegroundColor Green
    }
    
    # Frontend
    Set-Location "$ROOT\frontend"
    Write-Host "  Installing Node packages..." -ForegroundColor Gray
    npm install --silent 2>&1 | Out-Null
    Write-Host "  [OK] Frontend setup complete" -ForegroundColor Green
    Write-Host ""
}

Set-Location $ROOT

# Step 2.5: Environment File Setup
Write-Host ""
Write-Host "Step 2.5: Checking Environment Configuration..." -ForegroundColor Cyan

# Check if backend .env exists
if (-not (Test-Path "$ROOT\backend\.env")) {
    if (Test-Path "$ROOT\backend\.env.example") {
        Write-Host "  [SETUP] Creating backend/.env from template..." -ForegroundColor Yellow
        Copy-Item "$ROOT\backend\.env.example" "$ROOT\backend\.env"
        Write-Host "  [INFO] Created backend/.env - please configure MSSQL_USER and MSSQL_PASSWORD" -ForegroundColor Yellow
        Write-Host "  [INFO] Opening backend/.env for editing..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
        notepad "$ROOT\backend\.env"
        Write-Host "  [WAIT] Press Enter after configuring your SQL Server credentials..." -ForegroundColor Yellow
        Read-Host
    } else {
        Write-Host "  [ERROR] backend/.env.example not found!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [OK] backend/.env exists" -ForegroundColor Green
}

# Load environment variables from .env to check database config
$envLines = Get-Content "$ROOT\backend\.env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' }
$mssqlUser = ($envLines | Where-Object { $_ -match '^\s*MSSQL_USER\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
$mssqlPassword = ($envLines | Where-Object { $_ -match '^\s*MSSQL_PASSWORD\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
$mssqlServer = ($envLines | Where-Object { $_ -match '^\s*MSSQL_SERVER\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($mssqlServer)) { $mssqlServer = "localhost" }
$mssqlDatabase = ($envLines | Where-Object { $_ -match '^\s*MSSQL_DATABASE\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($mssqlDatabase)) { $mssqlDatabase = "JobPortal" }
$mssqlPort = ($envLines | Where-Object { $_ -match '^\s*MSSQL_PORT\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($mssqlPort)) { $mssqlPort = "1433" }

# Check if credentials are configured
if ($mssqlUser -eq "YOUR_SQL_USERNAME" -or $mssqlPassword -eq "YOUR_SQL_PASSWORD" -or [string]::IsNullOrWhiteSpace($mssqlUser) -or [string]::IsNullOrWhiteSpace($mssqlPassword)) {
    Write-Host "  [WARN] SQL Server credentials not configured in backend/.env" -ForegroundColor Yellow
    Write-Host "  [INFO] Please set MSSQL_USER and MSSQL_PASSWORD in backend/.env" -ForegroundColor Yellow
    Write-Host "  [INFO] Opening backend/.env for editing..." -ForegroundColor Gray
    Start-Sleep -Seconds 1
    notepad "$ROOT\backend\.env"
        Write-Host "  [WAIT] Press Enter after configuring your SQL Server credentials..." -ForegroundColor Yellow
        Read-Host
        # Reload after user edits
        $envLines = Get-Content "$ROOT\backend\.env" | Where-Object { $_ -notmatch '^\s*#' -and $_ -match '=' }
        $mssqlUser = ($envLines | Where-Object { $_ -match '^\s*MSSQL_USER\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
        $mssqlPassword = ($envLines | Where-Object { $_ -match '^\s*MSSQL_PASSWORD\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() }) | Select-Object -First 1
}

# Step 2.6: SQL Server Check
Write-Host ""
Write-Host "Step 2.6: Checking SQL Server..." -ForegroundColor Cyan

# Check if SQL Server service is running
$sqlService = Get-Service -Name "MSSQLSERVER" -ErrorAction SilentlyContinue
if ($sqlService) {
    if ($sqlService.Status -eq "Running") {
        Write-Host "  [OK] SQL Server service is running" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] SQL Server service is not running" -ForegroundColor Yellow
        Write-Host "  [INFO] Attempting to start SQL Server service..." -ForegroundColor Gray
        try {
            Start-Service -Name "MSSQLSERVER" -ErrorAction Stop
            Start-Sleep -Seconds 3
            Write-Host "  [OK] SQL Server service started" -ForegroundColor Green
        } catch {
            Write-Host "  [ERROR] Could not start SQL Server service. Please start it manually." -ForegroundColor Red
            Write-Host "  [INFO] Run: Start-Service -Name MSSQLSERVER" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [WARN] SQL Server service not found (might be named differently or remote server)" -ForegroundColor Yellow
    Write-Host "  [INFO] Continuing with connection test..." -ForegroundColor Gray
}

# Test SQL Server connection
Write-Host "  Testing SQL Server connection..." -ForegroundColor Gray
$connectionTest = $false
try {
    # Try to connect using sqlcmd
    $testQuery = "SELECT 1"
    $result = sqlcmd -S "$mssqlServer,$mssqlPort" -U $mssqlUser -P $mssqlPassword -Q $testQuery -W -h -1 -b 2>&1
    if ($LASTEXITCODE -eq 0) {
        $connectionTest = $true
        Write-Host "  [OK] SQL Server connection successful" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] SQL Server connection test failed" -ForegroundColor Yellow
        Write-Host "  [INFO] Will attempt database creation anyway..." -ForegroundColor Gray
    }
} catch {
    Write-Host "  [WARN] Could not test SQL Server connection (sqlcmd may not be in PATH)" -ForegroundColor Yellow
    Write-Host "  [INFO] Will attempt database creation anyway..." -ForegroundColor Gray
}

# Step 2.7: Database Initialization
Write-Host ""
Write-Host "Step 2.7: Database Initialization..." -ForegroundColor Cyan

# Function to check if database exists
function Test-DatabaseExists {
    param(
        [string]$Server,
        [string]$Port,
        [string]$User,
        [string]$Password,
        [string]$Database
    )
    
    try {
        $checkQuery = "SELECT CASE WHEN DB_ID('$Database') IS NOT NULL THEN 1 ELSE 0 END AS db_exists"
        $result = sqlcmd -S "$Server,$Port" -U $User -P $Password -Q $checkQuery -W -h -1 -b 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            # Check if result contains "1" (database exists)
            $resultString = $result -join " "
            if ($resultString -match '\b1\b') {
                return $true
            }
        }
        return $false
    } catch {
        return $false
    }
}

# Check if database exists
$dbExists = $false
Write-Host "  Checking if database '$mssqlDatabase' exists..." -ForegroundColor Gray

try {
    $null = Get-Command sqlcmd -ErrorAction Stop
    $dbExists = Test-DatabaseExists -Server $mssqlServer -Port $mssqlPort -User $mssqlUser -Password $mssqlPassword -Database $mssqlDatabase
    
    if ($dbExists) {
        Write-Host "  [OK] Database '$mssqlDatabase' exists" -ForegroundColor Green
        
        # Verify we can connect to the database
        Write-Host "  Verifying database connection..." -ForegroundColor Gray
        $verifyQuery = "USE [$mssqlDatabase]; SELECT 1"
        $verifyResult = sqlcmd -S "$mssqlServer,$mssqlPort" -U $mssqlUser -P $mssqlPassword -Q $verifyQuery -b 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Database connection verified" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] Could not verify database connection" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [SETUP] Database '$mssqlDatabase' not found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] sqlcmd not found - will attempt database creation via application" -ForegroundColor Yellow
    $dbExists = $false
}

# Create database if it doesn't exist
if (-not $dbExists) {
    Write-Host "  [SETUP] Creating database '$mssqlDatabase'..." -ForegroundColor Yellow
    $initScript = "$ROOT\backend\scripts\init-db.sql"
    
    if (-not (Test-Path $initScript)) {
        Write-Host "  [ERROR] Database init script not found at $initScript" -ForegroundColor Red
        Write-Host "  [INFO] Please ensure the init-db.sql file exists" -ForegroundColor Yellow
        exit 1
    }
    
    try {
        $null = Get-Command sqlcmd -ErrorAction Stop
        
        # Create a temporary SQL script with the correct database name
        $tempScript = "$env:TEMP\init-db-$([System.Guid]::NewGuid().ToString('N')).sql"
        $sqlContent = Get-Content $initScript -Raw
        # Replace hardcoded 'JobPortal' with the actual database name from .env
        $sqlContent = $sqlContent -replace "'JobPortal'", "'$mssqlDatabase'"
        $sqlContent = $sqlContent -replace "JobPortal;", "$mssqlDatabase;"
        $sqlContent = $sqlContent -replace "USE JobPortal", "USE [$mssqlDatabase]"
        Set-Content -Path $tempScript -Value $sqlContent -Encoding UTF8
        
        Write-Host "  Running database initialization script..." -ForegroundColor Gray
        $sqlResult = sqlcmd -S "$mssqlServer,$mssqlPort" -U $mssqlUser -P $mssqlPassword -i $tempScript -b 2>&1
        
        # Clean up temporary script
        Remove-Item $tempScript -ErrorAction SilentlyContinue
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Database '$mssqlDatabase' created successfully" -ForegroundColor Green
            
            # Verify the database was created
            Start-Sleep -Seconds 1
            $verifyExists = Test-DatabaseExists -Server $mssqlServer -Port $mssqlPort -User $mssqlUser -Password $mssqlPassword -Database $mssqlDatabase
            if ($verifyExists) {
                Write-Host "  [OK] Database creation verified" -ForegroundColor Green
                Write-Host "  [INFO] Tables will be created automatically by the backend on startup" -ForegroundColor Gray
            } else {
                Write-Host "  [WARN] Database creation may have failed - backend will attempt to create it" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  [ERROR] Database creation failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
            Write-Host "  [INFO] Error output:" -ForegroundColor Yellow
            $sqlResult | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            Write-Host "  [INFO] Backend will attempt to create the database on startup" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [WARN] sqlcmd not available - database will be created by the application on first run" -ForegroundColor Yellow
        Write-Host "  [INFO] To manually create: sqlcmd -S $mssqlServer,$mssqlPort -U $mssqlUser -P <password> -i $initScript" -ForegroundColor Gray
    }
} else {
    Write-Host "  [OK] Database '$mssqlDatabase' is ready" -ForegroundColor Green
    Write-Host "  [INFO] Tables will be verified/created by the backend on startup" -ForegroundColor Gray
}

# Step 3: Clean up ports
Write-Host ""
Write-Host "Step 3: Cleaning Ports..." -ForegroundColor Cyan
try {
    Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique | 
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
} catch {}
try {
    Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique | 
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
} catch {}
try {
    Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | 
        Select-Object -ExpandProperty OwningProcess -Unique | 
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
} catch {}
Start-Sleep -Seconds 1
Write-Host "  [OK] Ports 3000, 4000, and 5173 are free" -ForegroundColor Green

# Step 4: Start services
Write-Host ""
Write-Host "Step 4: Starting Services..." -ForegroundColor Cyan

Write-Host "  Starting parsing API..." -ForegroundColor Yellow
$parsingJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm start 2>&1
} -ArgumentList "$ROOT\parsing-api"

Start-Sleep -Seconds 2

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
$parsingReady = $false
$backendReady = $false
$frontendReady = $false

for ($i = 0; $i -lt $maxWait; $i++) {
    Start-Sleep -Seconds 1
    
    # Check Parsing API
    if (-not $parsingReady -and $i -ge 2) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:4000/health" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $parsingReady = $true
                Write-Host "  [OK] Parsing API ready at http://localhost:4000" -ForegroundColor Green
            }
        } catch {}
    }
    
    # Check Backend
    if (-not $backendReady -and $i -ge 4) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $backendReady = $true
                Write-Host "  [OK] Backend ready at http://localhost:3000" -ForegroundColor Green
            }
        } catch {}
    }
    
    # Check Frontend
    if (-not $frontendReady -and $i -ge 3) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $frontendReady = $true
                Write-Host "  [OK] Frontend ready at http://localhost:5173" -ForegroundColor Green
            }
        } catch {}
    }
    
    # All ready?
    if ($parsingReady -and $backendReady -and $frontendReady) {
        break
    }
    
    # Progress
    if (($i + 1) % 5 -eq 0 -and (-not $parsingReady -or -not $backendReady -or -not $frontendReady)) {
        $waiting = @()
        if (-not $parsingReady) { $waiting += "Parsing API" }
        if (-not $backendReady) { $waiting += "Backend" }
        if (-not $frontendReady) { $waiting += "Frontend" }
        Write-Host "  [WAIT] Still starting: $($waiting -join ', ') ($($i + 1)s)" -ForegroundColor Yellow
    }
}

Write-Host ""

if ($parsingReady -and $backendReady -and $frontendReady) {
    Write-Host "=======================================" -ForegroundColor Green
    Write-Host "  ALL SYSTEMS READY!" -ForegroundColor Green
    Write-Host "=======================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Parsing API: http://localhost:4000" -ForegroundColor Cyan
    Write-Host "Backend:     http://localhost:3000" -ForegroundColor Cyan
    Write-Host "Frontend:    http://localhost:5173" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Opening browser..." -ForegroundColor Gray
    Start-Process "http://localhost:5173"
    Write-Host ""
    Write-Host "[SUCCESS] Application is running!" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "[WARN] Some services may still be starting..." -ForegroundColor Yellow
    if (-not $parsingReady) {
        Write-Host "  Parsing API: Still starting (check LLM API keys in .env)" -ForegroundColor Yellow
    }
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
        $pState = (Get-Job -Id $parsingJob.Id -ErrorAction SilentlyContinue).State
        $bState = (Get-Job -Id $backendJob.Id -ErrorAction SilentlyContinue).State
        $fState = (Get-Job -Id $frontendJob.Id -ErrorAction SilentlyContinue).State
        
        if ($pState -eq "Failed") {
            Write-Host ""
            Write-Host "[ERROR] Parsing API stopped!" -ForegroundColor Red
            Receive-Job -Id $parsingJob.Id
            break
        }
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
