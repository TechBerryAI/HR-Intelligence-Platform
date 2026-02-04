#!/usr/bin/env node
/**
 * HR Job Portal - Single start script (IDE terminal only, no extra windows).
 * Sets up: .env, backend venv + pip install, frontend npm install.
 * Runs backend + frontend, waits until ready, opens browser.
 * Ctrl+C stops both.
 */

const fs = require('fs');
const path = require('path');
const { spawn, execSync: nodeExecSync, spawnSync } = require('child_process');
const http = require('http');

const ROOT = path.resolve(__dirname);
const BACKEND_DIR = path.join(ROOT, 'backend');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const BACKEND_ENV = path.join(BACKEND_DIR, '.env');
const BACKEND_ENV_EXAMPLE = path.join(BACKEND_DIR, '.env.example');
const VENV_DIR = path.join(BACKEND_DIR, 'venv');
const VENV_PYTHON = path.join(
  BACKEND_DIR,
  process.platform === 'win32' ? 'venv\\Scripts\\python.exe' : 'venv/bin/python'
);

// pyodbc does not support Python 3.14+ (C API changes). Backend needs 3.8–3.12.
const PY_MIN_MINOR = 8;
const PY_MAX_MINOR = 12;

// Python prints --version to stderr; use -c to get version on stdout.
const PY_VERSION_SCRIPT = '-c', PY_VERSION_CODE = 'import sys; print(sys.version_info.major, sys.version_info.minor)';

function parsePythonVersion(output) {
  const parts = (output || '').trim().split(/\s+/);
  if (parts.length >= 2) {
    const major = parseInt(parts[0], 10), minor = parseInt(parts[1], 10);
    if (!isNaN(major) && !isNaN(minor)) return { major, minor };
  }
  return null;
}

function isPythonVersionCompatible(ver) {
  return ver && ver.major === 3 && ver.minor >= PY_MIN_MINOR && ver.minor <= PY_MAX_MINOR;
}

/** Get { cmd, venvArgs } to run Python 3.8–3.12 for venv creation (pyodbc requires < 3.14). */
function getCompatiblePythonForVenv() {
  const tryCommands = [];
  if (process.platform === 'win32') {
    for (let minor = PY_MAX_MINOR; minor >= PY_MIN_MINOR; minor--) {
      tryCommands.push({ cmd: 'py', args: [`-3.${minor}`, PY_VERSION_SCRIPT, PY_VERSION_CODE], usePy: true, pyLabel: `-3.${minor}` });
    }
  }
  tryCommands.push({ cmd: 'python', args: [PY_VERSION_SCRIPT, PY_VERSION_CODE], usePy: false });
  tryCommands.push({ cmd: 'python3', args: [PY_VERSION_SCRIPT, PY_VERSION_CODE], usePy: false });

  for (const t of tryCommands) {
    try {
      const r = spawnSync(t.cmd, t.args, { encoding: 'utf8', shell: false });
      if (r.status !== 0) continue;
      const ver = parsePythonVersion(r.stdout || r.stderr || '');
      if (isPythonVersionCompatible(ver)) {
        if (t.usePy) {
          return { cmd: 'py', venvArgs: [t.pyLabel, '-m', 'venv', 'venv'] };
        }
        return { cmd: t.cmd, venvArgs: ['-m', 'venv', 'venv'] };
      }
    } catch (_) {
      // ignore and try next
    }
  }
  return null;
}

function getVenvPythonVersion() {
  if (!fs.existsSync(VENV_PYTHON)) return null;
  try {
    const r = spawnSync(VENV_PYTHON, [PY_VERSION_SCRIPT, PY_VERSION_CODE], { encoding: 'utf8', cwd: BACKEND_DIR });
    if (r.status !== 0) return null;
    return parsePythonVersion(r.stdout || r.stderr || '');
  } catch (_) {
    return null;
  }
}
const BACKEND_PORT = 3000;
const FRONTEND_PORT = 5173;
const BROWSER_URL = `http://localhost:${FRONTEND_PORT}`;

let backendProcess = null;
let frontendProcess = null;

function timestamp() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function log(msg, type = 'info') {
  const prefix = type === 'err' ? '[ERROR]' : type === 'warn' ? '[WARN]' : '[start]';
  console.log(`${prefix} [${timestamp()}] ${msg}`);
}

function logStep(step, total, label) {
  console.log(`[start] [${timestamp()}] Step ${step}/${total}: ${label}`);
}

/** Run command without shell to avoid Node DEP0190 (args not escaped with shell). */
function runCmd(cmd, args, cwd = ROOT, env = process.env) {
  return new Promise((resolve, reject) => {
    const c = spawn(cmd, args, { cwd, env, stdio: 'inherit', shell: false });
    c.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`Exit ${code}`))));
  });
}

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
    log('Created backend/.env from template. Configure MSSQL_USER and MSSQL_PASSWORD in backend/.env');
  } else {
    log('backend/.env exists');
  }
}

async function setupBackend() {
  logStep(3, 6, 'Setting up backend (venv + pip)');
  const venvDir = path.join(BACKEND_DIR, 'venv');
  const venvVer = getVenvPythonVersion();
  if (venvVer && venvVer.major === 3 && venvVer.minor >= 14) {
    log('Removing existing venv (Python 3.14+ not supported by pyodbc; need 3.8–3.12)...');
    fs.rmSync(venvDir, { recursive: true, force: true });
  }
  if (!fs.existsSync(venvDir)) {
    const compatible = getCompatiblePythonForVenv();
    if (!compatible) {
      log('Python 3.8–3.12 required for backend (pyodbc does not support 3.14+).', 'err');
      if (process.platform === 'win32') {
        log('Install Python 3.12 from https://www.python.org/downloads/ then run "node start.js" again.', 'err');
      } else {
        log('Install Python 3.11 or 3.12 and ensure "python3" or "python" points to it.', 'err');
      }
      process.exit(1);
    }
    log('Creating backend virtual environment (Python 3.8–3.12 for pyodbc)...');
    await runCmd(compatible.cmd, compatible.venvArgs, BACKEND_DIR);
    log('Virtual environment created');
  } else {
    log('Backend venv already exists');
  }
  log('Upgrading pip...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '--upgrade', 'pip', '-q'], BACKEND_DIR);
  log('Installing backend dependencies from requirements.txt...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Backend setup complete');
}

async function setupFrontend() {
  logStep(4, 6, 'Setting up frontend (npm)');
  const nodeModules = path.join(FRONTEND_DIR, 'node_modules');
  if (!fs.existsSync(nodeModules)) {
    log('Installing frontend dependencies (npm install)...');
    await runCmd('npm', ['install'], FRONTEND_DIR);
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
    if (code != null && code !== 0) log('Backend exited with code ' + code, 'warn');
  });
  log('Backend process started (port ' + BACKEND_PORT + ')');
}

function startFrontend() {
  logStep(6, 6, 'Starting frontend (Vite)');
  // On Windows, spawn('npm', ...) needs shell so the system finds npm.cmd (otherwise EINVAL or ENOENT).
  const useShell = process.platform === 'win32';
  frontendProcess = spawn('npm', ['run', 'dev'], {
    cwd: FRONTEND_DIR,
    stdio: 'inherit',
    shell: useShell,
  });
  frontendProcess.on('error', (err) => {
    log('Frontend failed to start: ' + err.message, 'err');
  });
  frontendProcess.on('close', (code) => {
    if (code != null && code !== 0) log('Frontend exited with code ' + code, 'warn');
  });
  log('Frontend process started (port ' + FRONTEND_PORT + ')');
}

function httpGet(url) {
  return new Promise((resolve) => {
    const u = new URL(url);
    const req = http.request(
      { hostname: u.hostname, port: u.port || 80, path: u.pathname || '/', method: 'GET' },
      (res) => resolve(res.statusCode === 200)
    );
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
    req.on('error', () => resolve(false));
    req.end();
  });
}

async function waitForReady(maxWaitMs = 60000) {
  const step = 1500;
  const backendUrl = `http://localhost:${BACKEND_PORT}/health`;
  const frontendUrl = `http://localhost:${FRONTEND_PORT}`;
  let elapsed = 0;
  let backendOk = false;
  let frontendOk = false;
  log('Waiting for backend and frontend to be ready...');
  while (elapsed < maxWaitMs) {
    if (!backendOk) backendOk = await httpGet(backendUrl);
    if (!frontendOk) frontendOk = await httpGet(frontendUrl);
    if (backendOk && frontendOk) {
      log('Backend and frontend are ready');
      return true;
    }
    if (elapsed > 0 && elapsed % 5000 === 0) {
      log(`Still waiting... Backend: ${backendOk ? 'OK' : 'pending'}, Frontend: ${frontendOk ? 'OK' : 'pending'} (${elapsed / 1000}s)`);
    }
    await new Promise((r) => setTimeout(r, step));
    elapsed += step;
  }
  log('Timeout waiting for services. Backend: ' + (backendOk ? 'OK' : 'not ready') + ', Frontend: ' + (frontendOk ? 'OK' : 'not ready'), 'warn');
  return false;
}

function openBrowser() {
  const url = BROWSER_URL;
  const cmd = process.platform === 'win32' ? 'start' : process.platform === 'darwin' ? 'open' : 'xdg-open';
  spawn(cmd, [url], { stdio: 'ignore', shell: true }).on('error', () => {});
  log('Opening browser: ' + url);
}

function onExit() {
  log('Shutting down (Ctrl+C received)...');
  if (backendProcess) {
    log('Stopping backend process...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
  if (frontendProcess) {
    log('Stopping frontend process...');
    frontendProcess.kill('SIGTERM');
    frontendProcess = null;
  }
  log('Goodbye.');
  process.exit(0);
}

async function main() {
  console.log('\n========================================');
  console.log('   HR Job Portal - Start');
  console.log('========================================\n');

  checkEnv();
  setupEnv();
  await setupBackend();
  await setupFrontend();

  process.on('SIGINT', onExit);
  process.on('SIGTERM', onExit);

  startBackend();
  startFrontend();

  const ready = await waitForReady();
  if (ready) openBrowser();

  console.log('\n--- Ready ---');
  console.log('Backend:  http://localhost:' + BACKEND_PORT);
  console.log('Frontend: ' + BROWSER_URL);
  console.log('Press Ctrl+C to stop.\n');
}

main().catch((err) => {
  log(err.message || err, 'err');
  process.exit(1);
});
