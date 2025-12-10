<#
.SYNOPSIS
    Database Setup Script for HR Job Portal

.DESCRIPTION
    This script helps set up the SQL Server database for the HR Job Portal.

.EXAMPLE
    .\setup-database.ps1 -LocalSqlServer
    Creates the database on local SQL Server (prompts for password)

.EXAMPLE
    .\setup-database.ps1 -LocalSqlServer -Server myserver -User myuser
    Creates the database on a specific server with a specific user
#>

param(
    [switch]$LocalSqlServer,
    [string]$Server = "localhost",
    [string]$Database = "JobPortal",
    [string]$User = "sa",
    [string]$Password
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Text)
    Write-Host "`n$("=" * 60)" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor White
    Write-Host "$("=" * 60)`n" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Text)
    Write-Host "➡️  $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "⚠️  $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor Red
}

Write-Header "HR Job Portal - Database Setup"

# Local SQL Server Setup
if ($LocalSqlServer) {
    Write-Step "Setting up database on local SQL Server..."
    
    if (-not $Password) {
        $SecurePassword = Read-Host "Enter SQL Server password for user '$User'" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
        $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }
    
    # Try to run the init script
    $scriptPath = Join-Path $PSScriptRoot "init-db.sql"
    
    Write-Step "Running database initialization script..."
    try {
        sqlcmd -S $Server -U $User -P $Password -i $scriptPath
        Write-Host "✅ Database created successfully!" -ForegroundColor Green
    } catch {
        Write-Error "Failed to run SQL script. Error: $_"
        Write-Host "`nMake sure:" -ForegroundColor Yellow
        Write-Host "  1. SQL Server is running" -ForegroundColor White
        Write-Host "  2. Credentials are correct" -ForegroundColor White
        Write-Host "  3. sqlcmd is installed and in PATH" -ForegroundColor White
        exit 1
    }
    
    # Check for available ODBC drivers
    $odbcDriver = "{SQL Server}"
    try {
        $drivers = Get-OdbcDriver | Where-Object { $_.Name -like '*SQL*' }
        if ($drivers) {
            $odbcDriver = "{" + $drivers[0].Name + "}"
            Write-Host "`nDetected ODBC driver: $odbcDriver" -ForegroundColor Gray
        }
    } catch {
        # Use default
    }
    
    Write-Host "`nUpdate your backend/.env with:" -ForegroundColor Yellow
    Write-Host @"

MSSQL_SERVER=$Server
MSSQL_PORT=1433
MSSQL_DATABASE=$Database
MSSQL_USER=$User
MSSQL_PASSWORD=<your-password>
MSSQL_ODBC_DRIVER=$odbcDriver

"@ -ForegroundColor White
}
# No option selected - show help
else {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\setup-database.ps1 -LocalSqlServer [-Server hostname] [-User username]`n"
    
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  .\setup-database.ps1 -LocalSqlServer"
    Write-Host "    Uses localhost with 'sa' user (prompts for password)`n"
    
    Write-Host "  .\setup-database.ps1 -LocalSqlServer -Server myserver -User myuser"
    Write-Host "    Uses specific server and username`n"
    
    Write-Host "Prerequisites:" -ForegroundColor Yellow
    Write-Host "  - SQL Server installed and running"
    Write-Host "  - sqlcmd in PATH (comes with SQL Server)`n"
    
    Write-Host "Check SQL Server status:" -ForegroundColor Gray
    Write-Host "  Get-Service MSSQLSERVER`n"
    
    Write-Host "ODBC Driver:" -ForegroundColor Yellow
    Write-Host "  Make sure you have an ODBC driver for SQL Server installed."
    Write-Host "  Check with: Get-OdbcDriver | Where-Object { `$_.Name -like '*SQL*' }"
    Write-Host "  Download from: https://aka.ms/downloadmsodbcsql`n"
}

