#!/usr/bin/env node
/**
 * HR Job Portal - Single start script (IDE terminal only, no extra windows).
 * Sets up: .env, backend venv + pip install, frontend npm install.
 * Runs backend + frontend, waits until ready, opens browser.
 * Ctrl+C stops both.
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

let backendProcess = null;
let frontendProcess = null;

function log(msg, type = 'info') {
  const prefix = type === 'err' ? '[ERROR]' : type === 'warn' ? '[WARN]' : '[start]';
  console.log(`${prefix} ${msg}`);
}

function runCmd(cmd, args, cwd = ROOT, env = process.env) {
  const c = spawn(cmd, args, { cwd, env, stdio: 'inherit', shell: process.platform === 'win32' });
  return new Promise((resolve, reject) => {
    c.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`Exit ${code}`))));
  });
}

function checkEnv() {
  log('Checking environment...');
  try {
    nodeExecSync('node --version', { stdio: 'pipe' });
  } catch (e) {
    log('Node.js 16+ required. Install from https://nodejs.org', 'err');
    process.exit(1);
  }
  try {
    nodeExecSync('python --version', { stdio: 'pipe' });
  } catch (e) {
    try {
      nodeExecSync('python3 --version', { stdio: 'pipe' });
    } catch (e2) {
      log('Python 3.8+ required for backend.', 'err');
      process.exit(1);
    }
  }
  log('Node and Python OK');
}

function setupEnv() {
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
  const venvDir = path.join(BACKEND_DIR, 'venv');
  if (!fs.existsSync(venvDir)) {
    log('Creating backend virtual environment...');
    await runCmd('python', ['-m', 'venv', 'venv'], BACKEND_DIR);
  }
  log('Installing backend dependencies...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '--upgrade', 'pip', '-q'], BACKEND_DIR);
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Backend deps OK');
}

async function setupFrontend() {
  const nodeModules = path.join(FRONTEND_DIR, 'node_modules');
  if (!fs.existsSync(nodeModules)) {
    log('Installing frontend dependencies...');
    await runCmd('npm', ['install'], FRONTEND_DIR);
  } else {
    log('Frontend node_modules present (run npm install manually to update)');
  }
  log('Frontend deps OK');
}

function startBackend() {
  log('Starting backend...');
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
}

function startFrontend() {
  log('Starting frontend...');
  frontendProcess = spawn('npm', ['run', 'dev'], {
    cwd: FRONTEND_DIR,
    stdio: 'inherit',
    shell: true,
  });
  frontendProcess.on('error', (err) => {
    log('Frontend failed to start: ' + err.message, 'err');
  });
  frontendProcess.on('close', (code) => {
    if (code != null && code !== 0) log('Frontend exited with code ' + code, 'warn');
  });
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
  while (elapsed < maxWaitMs) {
    if (!backendOk) backendOk = await httpGet(backendUrl);
    if (!frontendOk) frontendOk = await httpGet(frontendUrl);
    if (backendOk && frontendOk) {
      log('Backend and frontend ready.');
      return true;
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
  log('Shutting down...');
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
  if (frontendProcess) {
    frontendProcess.kill('SIGTERM');
    frontendProcess = null;
  }
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

  console.log('\nBackend: http://localhost:' + BACKEND_PORT);
  console.log('Frontend: ' + BROWSER_URL);
  console.log('Press Ctrl+C to stop.\n');
}

main().catch((err) => {
  log(err.message || err, 'err');
  process.exit(1);
});
