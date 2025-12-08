# 🚨 CRITICAL: FIX CORS ERROR - FOLLOW THESE STEPS EXACTLY

## The Problem
You have **MULTIPLE Flask servers running** on port 3000 with OLD code. This is why CORS isn't working.

## Solution - Do This NOW:

### Step 1: Kill ALL Python processes on port 3000
Open PowerShell and run:
```powershell
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```

Or double-click: `backend/KILL_AND_RESTART.bat`

### Step 2: Verify port 3000 is free
```powershell
netstat -ano | findstr :3000
```
Should show NOTHING (no LISTENING processes)

### Step 3: Start the server with NEW code
```bash
cd backend
python app.py
```

### Step 4: Verify it's working
When server starts, you MUST see:
```
[CORS] Allowed origins: ['http://localhost:5173', 'http://127.0.0.1:5173']
```

When you try to sign up, you MUST see in backend console:
```
[CORS] OPTIONS preflight: /api/candidate/signup from http://localhost:5173
[CORS] Preflight response sent
[CORS] ✓ Headers added to POST /api/candidate/signup for http://localhost:5173
```

## If you still see errors:

1. **Check backend console** - Do you see the `[CORS]` messages?
   - NO = Server not restarted with new code
   - YES = Check what origin is being blocked

2. **Check browser console** - What exact error?
   - "No Access-Control-Allow-Origin" = Server not sending headers (not restarted)
   - "Origin not allowed" = Origin mismatch (check allowed origins)

3. **Verify frontend URL** - Make sure frontend is on `http://localhost:5173` (not 5174 or other port)

## The Fix is Complete
The code in `backend/app.py` now has:
- ✅ Manual OPTIONS handler (runs FIRST)
- ✅ Flask-CORS as backup
- ✅ after_request that FORCES headers on all responses
- ✅ Debug logging to see what's happening

**YOU MUST RESTART THE SERVER FOR IT TO WORK!**

