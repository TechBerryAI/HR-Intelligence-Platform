#!/usr/bin/env node
/**
 * HR Job Portal - Single start script.
 * Sets up: backend/.env, backend venv + pip, frontend npm.
 * Starts backend (Flask) + frontend (Vite), waits until ready, opens browser.
 * Ctrl+C stops both. No shell for spawn (avoids Node DEP0190).
 */

const fs = require('fs');
const path = require('path');
const { spawn, execSync: nodeExecSync } = require('child_process');
const http = require('http');

const ROOT = path.resolve(__dirname);
const BACKEND_DIR = path.join(ROOT, 'backend');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const BACKEND_ENV = path.join(BACKEND_DIR, '.env');
const BACKEND_ENV_EXAMPLE = path.join(BACKEND_DIR, '.env.example');
const VENV_PYTHON = path.join(
  BACKEND_DIR,
  process.platform === 'win32' ? 'venv\\Scripts\\python.exe' : 'venv/bin/python'
);
const BACKEND_PORT = 3000;
const FRONTEND_PORT = 5173;
const BROWSER_URL = `http://localhost:${FRONTEND_PORT}`;
const isWin = process.platform === 'win32';

/** On Windows, npm is npm.cmd (batch); spawn needs shell:true to run it. */
let backendProcess = null;
let frontendProcess = null;

// ---- Logging ----
function ts() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function log(msg, type = 'info') {
  const tag = type === 'err' ? 'ERROR' : type === 'warn' ? 'WARN' : 'start';
  console.log(`[${tag}] [${ts()}] ${msg}`);
}

function logStep(step, total, label) {
  console.log(`[start] [${ts()}] Step ${step}/${total}: ${label}`);
}

function logPhase(title) {
  console.log('');
  console.log('  ' + title);
  console.log('  ' + '-'.repeat(Math.min(60, title.length)));
}

/** Run a command. Use shell only when required (e.g. npm.cmd on Windows). */
function runCmd(cmd, args, cwd = ROOT, env = process.env, useShell = false) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, env, stdio: 'inherit', shell: useShell });
    child.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`Exit ${code}`))));
  });
}

/** Open URL in default browser (no shell on Windows: use cmd /c start). */
function openBrowser(url) {
  const args = isWin ? ['/c', 'start', '', url] : [url];
  const cmd = isWin ? 'cmd' : process.platform === 'darwin' ? 'open' : 'xdg-open';
  spawn(cmd, args, { stdio: 'ignore', shell: false }).on('error', () => {});
  log(`Opening browser: ${url}`);
}

// ---- Steps ----
function checkEnv() {
  logStep(1, 6, 'Checking environment');
  try {
    const nodeVer = nodeExecSync('node --version', { encoding: 'utf8' }).trim();
    log(`Node: ${nodeVer}`);
  } catch (e) {
    log('Node.js 16+ required. Install from https://nodejs.org', 'err');
    process.exit(1);
  }
  try {
    const pyVer = nodeExecSync('python --version', { encoding: 'utf8' }).trim();
    log(`Python: ${pyVer}`);
  } catch (e) {
    try {
      const py3Ver = nodeExecSync('python3 --version', { encoding: 'utf8' }).trim();
      log(`Python: ${py3Ver}`);
    } catch (e2) {
      log('Python 3.8+ required for backend.', 'err');
      process.exit(1);
    }
  }
  log('Environment check OK');
}

function setupEnv() {
  logStep(2, 6, 'Checking backend/.env');
  if (!fs.existsSync(BACKEND_ENV)) {
    if (!fs.existsSync(BACKEND_ENV_EXAMPLE)) {
      log('backend/.env.example not found', 'err');
      process.exit(1);
    }
    fs.copyFileSync(BACKEND_ENV_EXAMPLE, BACKEND_ENV);
    log('Created backend/.env from template. Configure MSSQL and MAIL_* in backend/.env');
  } else {
    log('backend/.env found');
  }
}

async function setupBackend() {
  logStep(3, 6, 'Setting up backend (venv + pip)');
  const venvDir = path.join(BACKEND_DIR, 'venv');
  if (!fs.existsSync(venvDir)) {
    log('Creating backend virtual environment...');
    await runCmd('python', ['-m', 'venv', 'venv'], BACKEND_DIR);
    log('Virtual environment created');
  } else {
    log('Backend venv already exists');
  }
  log('Upgrading pip...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '--upgrade', 'pip', '-q'], BACKEND_DIR);
  log('Installing backend dependencies (requirements.txt)...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Backend setup complete');
}

async function setupFrontend() {
  logStep(4, 6, 'Setting up frontend (npm)');
  const nodeModules = path.join(FRONTEND_DIR, 'node_modules');
  if (!fs.existsSync(nodeModules)) {
    log('Installing frontend dependencies (npm install)...');
    await runCmd(isWin ? 'npm.cmd' : 'npm', ['install'], FRONTEND_DIR, process.env, isWin);
    log('Frontend dependencies installed');
  } else {
    log('Frontend node_modules present (run "npm install" in frontend/ to update)');
  }
  log('Frontend setup complete');
}

function startBackend() {
  logStep(5, 6, 'Starting backend (Flask)');
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };
  backendProcess = spawn(VENV_PYTHON, ['app.py'], {
    cwd: BACKEND_DIR,
    stdio: 'inherit',
    shell: false,
    env,
  });
  backendProcess.on('error', (err) => {
    log('Backend failed to start: ' + err.message, 'err');
  });
  backendProcess.on('close', (code) => {
    if (code != null && code !== 0) {
      log('Backend process exited with code ' + code, 'warn');
    }
  });
  log('Backend process started (Flask will bind to port ' + BACKEND_PORT + ')');
}

function startFrontend() {
  logStep(6, 6, 'Starting frontend (Vite)');
  // Windows: npm is npm.cmd (batch); spawning it without shell causes EINVAL. Use shell on Windows only.
  const opts = {
    cwd: FRONTEND_DIR,
    stdio: 'inherit',
    env: process.env,
    shell: isWin,
  };
  frontendProcess = spawn(isWin ? 'npm.cmd' : 'npm', ['run', 'dev'], opts);
  frontendProcess.on('error', (err) => {
    log('Frontend failed to start: ' + err.message, 'err');
  });
  frontendProcess.on('close', (code) => {
    if (code != null && code !== 0) {
      log('Frontend process exited with code ' + code, 'warn');
    }
  });
  log('Frontend process started (Vite will bind to port ' + FRONTEND_PORT + ')');
}

function httpGet(url) {
  return new Promise((resolve) => {
    const u = new URL(url);
    const req = http.request(
      { hostname: u.hostname, port: u.port || 80, path: u.pathname || '/', method: 'GET' },
      (res) => resolve(res.statusCode === 200)
    );
    req.setTimeout(3000, () => { req.destroy(); resolve(false); });
    req.on('error', () => resolve(false));
    req.end();
  });
}

async function waitForReady(maxWaitMs = 60000) {
  const intervalMs = 1500;
  const backendUrl = `http://localhost:${BACKEND_PORT}/health`;
  const frontendUrl = `http://localhost:${FRONTEND_PORT}`;
  let elapsed = 0;
  let backendOk = false;
  let frontendOk = false;

  logPhase('Waiting for services');
  log('Polling backend (' + backendUrl + ') and frontend (' + frontendUrl + ')...');

  while (elapsed < maxWaitMs) {
    if (!backendOk) backendOk = await httpGet(backendUrl);
    if (!frontendOk) frontendOk = await httpGet(frontendUrl);
    if (backendOk && frontendOk) {
      log('Backend and frontend are ready.');
      return true;
    }
    if (elapsed > 0 && elapsed % 6000 === 0) {
      log(
        `  Backend: ${backendOk ? 'OK' : 'waiting'} | Frontend: ${frontendOk ? 'OK' : 'waiting'} (${elapsed / 1000}s)`
      );
    }
    await new Promise((r) => setTimeout(r, intervalMs));
    elapsed += intervalMs;
  }

  log(
    'Timeout waiting for services. Backend: ' + (backendOk ? 'OK' : 'not ready') + ', Frontend: ' + (frontendOk ? 'OK' : 'not ready'),
    'warn'
  );
  return false;
}

function onExit(signal) {
  logPhase('Shutting down');
  log((signal === 'SIGINT' ? 'Ctrl+C received.' : 'Signal ' + signal + ' received.') + ' Stopping processes...');
  let pending = 0;
  if (backendProcess) pending++;
  if (frontendProcess) pending++;
  const done = () => {
    pending--;
    if (pending <= 0) {
      log('Backend and frontend stopped. Goodbye.');
      process.exit(0);
    }
  };

  if (backendProcess) {
    backendProcess.removeAllListeners('close');
    backendProcess.on('close', done);
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
  if (frontendProcess) {
    frontendProcess.removeAllListeners('close');
    frontendProcess.on('close', done);
    frontendProcess.kill('SIGTERM');
    frontendProcess = null;
  }
  if (pending === 0) process.exit(0);
}

async function main() {
  console.log('\n========================================');
  console.log('   HR Job Portal - Start');
  console.log('========================================\n');

  checkEnv();
  setupEnv();
  await setupBackend();
  await setupFrontend();

  process.on('SIGINT', () => onExit('SIGINT'));
  process.on('SIGTERM', () => onExit('SIGTERM'));

  logPhase('Starting processes');
  startBackend();
  startFrontend();

  const ready = await waitForReady();
  if (ready) {
    openBrowser(BROWSER_URL);
    logPhase('Ready');
    console.log('  Backend:  http://localhost:' + BACKEND_PORT);
    console.log('  Frontend: ' + BROWSER_URL);
    console.log('  Press Ctrl+C to stop.');
    console.log('');
  } else {
    log('Not opening browser because services did not become ready.', 'warn');
    console.log('');
  }
}

main().catch((err) => {
  log(err.message || String(err), 'err');
  process.exit(1);
});
