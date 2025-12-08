# HR Job Portal

Full-stack HR Job Portal with candidate management, job posting, and AI-powered matching.

## Quick Start

```powershell
.\run.ps1
```

Opens automatically in your browser at http://localhost:5173

## Prerequisites

- Python 3.8+
- Node.js 16+
- Microsoft SQL Server
- ODBC Driver for SQL Server

## Configuration

### Backend Environment

Edit `backend/.env`:

```env
PORT=3000
FLASK_DEBUG=true
FRONTEND_URL=http://localhost:5173
JWT_SECRET=your-secret-key

# Database
MSSQL_SERVER=localhost
MSSQL_DATABASE=JobPortal
MSSQL_USER=Test
MSSQL_PASSWORD=Root@123
MSSQL_ODBC_DRIVER={SQL Server}

# Email (Gmail for OTP)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

**Gmail App Password**: Google Account → Security → 2-Step Verification → App passwords

### Frontend Environment

`frontend/.env` (created automatically):

```env
VITE_API_URL=http://localhost:3000
VITE_API_TIMEOUT_MS=15000
```

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

### Port in Use

```powershell
Get-NetTCPConnection -LocalPort 3000 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force
Get-NetTCPConnection -LocalPort 5173 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force
```

### Database Connection

1. Check SQL Server is running: `Get-Service MSSQLSERVER`
2. Start if needed: `Start-Service MSSQLSERVER`
3. Verify credentials in `backend/.env`

### Email Not Sending

For testing, disable emails: `MAIL_SUPPRESS_SEND=true` in `backend/.env`

## Manual Setup

If needed:

**Backend:**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

**Frontend:**
```powershell
cd frontend
npm install
npm run dev
```

## Stopping

```powershell
# Get process IDs from run.ps1 output, then:
Stop-Job <backend-id>, <frontend-id>
Remove-Job <backend-id>, <frontend-id>
```

## License

MIT License
