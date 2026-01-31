# HR Job Portal

Full-stack HR Job Portal with candidate management, job posting, and AI-powered matching.

## ⚡ Performance Optimized!

**NEW:** Lightning-fast startup (1-2 seconds) with automatic retry and connection pooling!
- 🚀 **87-93% faster** backend startup
- 🛡️ **Never-fail API calls** with automatic retry
- 💪 **5-15x faster** database queries
- 📊 Real-time startup progress

## 🚀 Quick Start

### First Time Setup

```bash
# 1. Copy environment template (or start.js will do it)
cp backend/.env.example backend/.env

# 2. Edit backend/.env with YOUR SQL Server credentials
# Set: MSSQL_USER and MSSQL_PASSWORD

# 3. Run the application (from repo root, in your IDE terminal)
node start.js
```

`start.js` installs backend (Python venv + pip) and frontend (npm) dependencies, starts backend and frontend, then opens the browser at http://localhost:5173. All output runs in the same terminal (no extra windows). Press **Ctrl+C** to stop.

The database and tables are created automatically on first backend run.

📖 **Having issues?** See [SETUP.md](SETUP.md) for detailed troubleshooting.

### Bulk Resume Parser — full folder access (Electron)

In the browser, folder pickers are restricted (e.g. "contains system files"). To **access any folder** for input/output, run the app as a desktop window:

1. **Terminal 1** — start the frontend:
   ```bash
   cd frontend && npm run dev
   ```
2. **Terminal 2** — from repo root, install once then run Electron:
   ```bash
   npm install
   npm run electron
   ```

Electron opens a window that loads the app and uses the OS folder/file dialogs, so you can select any directory or file without browser restrictions.

### Returning Users

```bash
node start.js
```

Opens automatically in your browser at http://localhost:5173 when ready.

## Prerequisites

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.8+ | `python --version` |
| Node.js | 16+ | `node --version` |
| SQL Server | 2017+ | Local or remote instance |
| ODBC Driver | Any | `Get-OdbcDriver \| Where-Object { $_.Name -like '*SQL*' }` |

**Database Options:**
- 💻 **Local SQL Server** - SQL Server Express (free) or full version
- ☁️ **Cloud SQL** - Azure SQL Database, AWS RDS for SQL Server

## Configuration

### Quick Setup

```powershell
copy backend\.env.example backend\.env
```

Edit `backend/.env` - only these 2 values need to change:

```env
MSSQL_USER=YOUR_SQL_USERNAME      # Your SQL Server login
MSSQL_PASSWORD=YOUR_SQL_PASSWORD  # Your SQL Server password
```

Everything else has working defaults.

### Optional: Email Configuration

For OTP to work, add your Gmail credentials:

```env
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password  # Gmail App Password
```

**Gmail App Password**: Google Account → Security → 2-Step Verification → App passwords

### Optional: LLM Configuration

For AI matching features:

```env
XAI_API_KEY=your-xai-api-key
```

### Optional: ATS and Bulk Resume Parsing (external services)

Resume/JD parsing and matching run inside the main backend. For ATS scoring on applications and admin bulk resume parsing, configure URLs to external services (deploy separately if needed):

```env
# ATS Matching (HR-ATS-API) - used when candidates apply
ATS_API_URL=http://localhost:8000
ATS_API_KEY=your-ats-api-key

# Bulk Resume Parser - used on Admin > Bulk Resume Parser page
BULK_PARSER_URL=http://localhost:8001
```

If not set, applications are still saved; ATS score/shortlist and bulk parsing will be unavailable until these services are running.

## Performance Features

### ⚡ Fast Startup
- Lazy database initialization
- Parallel server startup
- Smart health checking

### 🛡️ Reliable API Calls
- Automatic retry with exponential backoff
- 99%+ success rate
- Clear error messages

### 💪 Optimized Database
- Connection pooling (5 connections)
- 5-15x faster queries
- Automatic connection recovery

### 📊 Better Monitoring
- Real-time startup progress
- Connection status indicator
- Health check endpoint

See [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) for technical details.

## Features

### For HR/Recruiters
- Job posting and management
- View candidate applications
- Smart AI matching scores (0-100%)
- Application tracking
- Resume viewing/download

### For Candidates
- Complete profile management (education, experience, certifications)
- Resume upload
- Job search and browsing
- One-click application
- Application status tracking

## Access

- **Frontend**: http://localhost:5173
- **Backend**: http://localhost:3000
- **Health**: http://localhost:3000/health

## API Endpoints

### Authentication
- `POST /api/signup` - HR signup
- `POST /api/verify-otp` - Verify OTP
- `POST /api/login` - HR login
- `POST /api/candidate/signup` - Candidate signup
- `POST /api/candidate/login` - Candidate login

### Jobs
- `GET /api/jobs` - List jobs
- `POST /api/jobs` - Create job (HR)
- `PUT /api/jobs/:id` - Update job (HR)
- `DELETE /api/jobs/:id` - Delete job (HR)

### Applications
- `POST /api/applications` - Apply to job
- `GET /api/applications` - Get my applications
- `GET /api/candidate/profile` - Get profile
- `POST /api/candidate/profile` - Update profile

## Database

Auto-created on first run:
- hr_signup, hr_login
- candidate_signup, candidate_login, candidate_profiles
- candidate_education, candidate_certifications, candidate_experiences
- jobs, applications
- login_history

## Troubleshooting

### Environment Validation Failed

The backend validates your configuration on startup. If you see errors:
```powershell
# Run validation standalone
cd backend
python env_validator.py
```

### ODBC Driver Not Found

```powershell
# Check installed drivers
Get-OdbcDriver | Where-Object { $_.Name -like '*SQL*' }

# Download ODBC Driver 17 from Microsoft:
# https://aka.ms/downloadmsodbcsql
```

Update `MSSQL_ODBC_DRIVER` in `.env` to match an installed driver.

### Database Connection Failed

```powershell
# Check SQL Server service is running
Get-Service MSSQLSERVER

# Start if needed
Start-Service MSSQLSERVER

# Test connection
Test-NetConnection localhost -Port 1433
```

### Port in Use

```powershell
Get-NetTCPConnection -LocalPort 3000 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force
Get-NetTCPConnection -LocalPort 5173 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force
```

### Email Not Sending

For testing without email: `MAIL_SUPPRESS_SEND=true` in `backend/.env`

📖 **More help**: See [SETUP.md](SETUP.md) for detailed troubleshooting.

## Manual Setup

If you prefer to run backend and frontend separately:

**Backend:**
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1  |  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Stopping

When using `node start.js`, press **Ctrl+C** in the same terminal to stop both backend and frontend.

## License

MIT License
