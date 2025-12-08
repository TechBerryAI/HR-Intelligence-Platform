# How to Fix CORS Error - Server Restart Instructions

## IMPORTANT: You MUST restart your backend server for the CORS changes to take effect!

### Steps to Fix:

1. **Stop the current backend server:**
   - Find the terminal/command prompt where your Flask server is running
   - Press `Ctrl+C` to stop it

2. **Restart the backend server:**
   ```bash
   cd backend
   python app.py
   ```
   
   You should see:
   - `CORS allowed origins: ['http://127.0.0.1:5173', 'http://localhost:5173']`
   - Server starting on port 3000

3. **Verify the server is running:**
   - Check that you see the CORS origins printed in the console
   - The server should be listening on `http://localhost:3000`

4. **Test CORS in browser:**
   - Open browser console
   - Try the signup form again
   - Check the backend console for CORS debug messages like:
     - `[CORS] Request: OPTIONS /api/candidate/signup, Origin: http://localhost:5173`
     - `[CORS] Headers set for origin: http://localhost:5173`

5. **If still not working:**
   - Check the backend console for CORS debug messages
   - Verify the Origin header matches the allowed origins
   - Make sure both servers are running (frontend on 5173, backend on 3000)

### Test Endpoint:
You can test CORS by visiting: `http://localhost:3000/api/test-cors` in your browser

