#!/usr/bin/env node
/**
 * HR Job Portal - Single start script (IDE terminal only, no extra windows).
 * Sets up: .env, backend venv + pip install, frontend npm install.
 * Runs backend + frontend, waits until ready, opens browser.
 * Ctrl+C stops both.
 */

const fs = require('fs');
const path = require('path');
const { spawn, spawnSync, execSync: nodeExecSync } = require('child_process');
const http = require('http');

const ROOT = path.resolve(__dirname);
const BACKEND_DIR = path.join(ROOT, 'apps', 'backend');
const FRONTEND_DIR = path.join(ROOT, 'apps', 'frontend');
const BACKEND_ENV = path.join(BACKEND_DIR, '.env');
const BACKEND_ENV_EXAMPLE = path.join(BACKEND_DIR, '.env.example');
const VENV_PYTHON = path.join(
  BACKEND_DIR,
  process.platform === 'win32' ? 'venv\\Scripts\\python.exe' : 'venv/bin/python'
);
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

/** Run command. useShell: on Windows set true for npm (npm.cmd). */
function runCmd(cmd, args, cwd = ROOT, env = process.env, useShell = false) {
  return new Promise((resolve, reject) => {
    const c = spawn(cmd, args, { cwd, env, stdio: 'inherit', shell: useShell });
    c.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`Exit ${code}`))));
  });
}

const CRITICAL_SOURCE_FILES = [
  path.join(FRONTEND_DIR, 'src', 'shared', 'lib', 'utils.js'),
  path.join(FRONTEND_DIR, 'src', 'shared', 'lib', 'jobDescription.js'),
  path.join(BACKEND_DIR, 'app', 'domains', 'identity', 'sessions', 'service.py'),
];

function checkCriticalSource() {
  const missing = CRITICAL_SOURCE_FILES.filter((p) => !fs.existsSync(p));
  if (missing.length === 0) return;
  log('Critical source files missing (repo may be incomplete or .gitignore is too broad):', 'err');
  for (const p of missing) {
    log(`  - ${path.relative(ROOT, p)}`, 'err');
  }
  process.exit(1);
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
  checkCriticalSource();
  log('Environment check OK');
}

function setupEnv() {
  logStep(2, 6, 'Checking apps/backend/.env');
  if (!fs.existsSync(BACKEND_ENV)) {
    if (!fs.existsSync(BACKEND_ENV_EXAMPLE)) {
      log('apps/backend/.env.example not found', 'err');
      process.exit(1);
    }
    fs.copyFileSync(BACKEND_ENV_EXAMPLE, BACKEND_ENV);
    log('Created apps/backend/.env from template. Configure POSTGRES_* or DATABASE_URL in apps/backend/.env');
  } else {
    log('apps/backend/.env exists');
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
  log('Installing backend dependencies from requirements.txt...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Backend setup complete');
}

async function setupFrontend() {
  logStep(4, 6, 'Setting up frontend (npm)');
  // Always run npm install so dependencies stay in sync. On Windows, shell: true is required to run npm (avoids spawn EINVAL).
  log('Installing frontend dependencies from package.json...');
  await runCmd('npm', ['install'], FRONTEND_DIR, process.env, process.platform === 'win32');
  log('Frontend setup complete');
}

function startBackend() {
  logStep(5, 6, 'Starting backend (Flask)');
  const env = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: path.join(ROOT, 'ai'),
    AI_RUNTIME_CONFIG: path.join(ROOT, 'ai', 'runtime', 'config', 'runtime.production.yaml'),
  };
  backendProcess = spawn(VENV_PYTHON, ['wsgi.py'], {
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
  // On Windows use shell with single command string to avoid spawn deprecation (args + shell).
  const useShell = process.platform === 'win32';
  const cmd = useShell ? 'npm run dev' : 'npm';
  const args = useShell ? [] : ['run', 'dev'];
  frontendProcess = spawn(cmd, args, {
    cwd: FRONTEND_DIR,
    stdio: 'inherit',
    shell: useShell,
    env: process.env,
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
  const fullCmd = process.platform === 'win32' ? `start "" "${url}"` : `${cmd} "${url}"`;
  spawn(fullCmd, [], { stdio: 'ignore', shell: true }).on('error', () => {});
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

  // After venv/deps so preflight can use psycopg (no local PostgreSQL client needed)
  const preflight = spawnSync('node', [path.join(ROOT, 'scripts', 'db-preflight.js')], {
    encoding: 'utf8',
    stdio: ['inherit', 'pipe', 'inherit'],
  });
  if (preflight.stdout) process.stdout.write(preflight.stdout);
  if (preflight.status !== 0) process.exit(1);

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
