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
const DEFAULT_OLLAMA_HOST = 'http://192.168.1.200:11434';
/** Pull-only fallback when hardware detection is unavailable. Never written to .env. */
const SAFE_PULL_OLLAMA_MODEL = 'qwen2.5:7b-instruct';

let backendProcess = null;
let frontendProcess = null;
let ollamaProcess = null;

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
  logStep(1, 7, 'Checking environment');
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
    const m = /Python\s+(\d+)\.(\d+)/i.exec(pyVer);
    if (m) {
      const major = Number(m[1]);
      const minor = Number(m[2]);
      if (major < 3 || (major === 3 && minor < 10)) {
        log(
          `Python ${major}.${minor} is below the supported range (3.10–3.12). ` +
            'Type hints like str | None will crash the backend. Install Python 3.10+ ' +
            'and recreate apps/backend/venv, or continue only if all modules use ' +
            '`from __future__ import annotations`.',
          'warn'
        );
      }
    }
  } catch (e) {
    try {
      const py3Ver = nodeExecSync('python3 --version', { encoding: 'utf8' }).trim();
      log(`Python: ${py3Ver}`);
      const m = /Python\s+(\d+)\.(\d+)/i.exec(py3Ver);
      if (m) {
        const major = Number(m[1]);
        const minor = Number(m[2]);
        if (major < 3 || (major === 3 && minor < 10)) {
          log(
            `Python ${major}.${minor} is below the supported range (3.10–3.12). ` +
              'Prefer Python 3.10+ for the backend venv on the VM.',
            'warn'
          );
        }
      }
    } catch (e2) {
      log('Python 3.10+ required for backend.', 'err');
      process.exit(1);
    }
  }
  checkCriticalSource();
  log('Environment check OK');
}

function readEnvFile(filePath) {
  const out = {};
  if (!fs.existsSync(filePath)) return out;
  const text = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

function upsertEnvKeys(filePath, updates) {
  let content = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : '';
  for (const [key, value] of Object.entries(updates)) {
    const re = new RegExp(`^${key}=.*$`, 'm');
    if (re.test(content)) {
      content = content.replace(re, `${key}=${value}`);
    } else {
      if (content && !content.endsWith('\n')) content += '\n';
      content += `${key}=${value}\n`;
    }
  }
  fs.writeFileSync(filePath, content, 'utf8');
}

/** Non-empty OLLAMA_MODEL in .env or process env is an operator pin. */
function explicitOllamaModel(envMap = {}, processEnv = process.env) {
  const fromProcess = String((processEnv && processEnv.OLLAMA_MODEL) || '').trim();
  if (fromProcess) return fromProcess;
  return String((envMap && envMap.OLLAMA_MODEL) || '').trim();
}

function ollamaModelIsExplicit(envMap = {}, processEnv = process.env) {
  return Boolean(explicitOllamaModel(envMap, processEnv));
}

/** True only for 127.0.0.1 / localhost (optional scheme and port). */
function isOllamaLoopbackHost(host) {
  const raw = String(host || '').trim().toLowerCase().replace(/\/$/, '');
  if (!raw) return false;
  let hostname = raw;
  try {
    const url = new URL(raw.includes('://') ? raw : `http://${raw}`);
    hostname = url.hostname;
  } catch {
    hostname = raw.replace(/^https?:\/\//, '').split('/')[0].split(':')[0];
  }
  return hostname === '127.0.0.1' || hostname === 'localhost';
}

/** Host/base-url normalization only — never persist OLLAMA_MODEL. */
function ollamaHostUpdates(envMap = {}, defaultHost = DEFAULT_OLLAMA_HOST) {
  const host =
    (envMap.OLLAMA_HOST || '').trim() ||
    (envMap.OLLAMA_BASE_URL || '').trim() ||
    defaultHost;
  const updates = {};
  if ((envMap.OLLAMA_HOST || '').trim() !== host) updates.OLLAMA_HOST = host;
  if (!(envMap.OLLAMA_BASE_URL || '').trim()) updates.OLLAMA_BASE_URL = host;
  return { host, updates };
}

/** Keys that must match between start.js Ollama pull and Flask hardware selection. */
const MODEL_SELECTION_KEYS = ['OLLAMA_MODEL', 'HCIP_HARDWARE_PROFILE', 'HCIP_VRAM_MB'];

/**
 * Child env for `python -m app.ai.parser.engine.hardware`.
 * Process env wins; .env fills only unset/blank model-selection keys.
 * Never copies unrelated .env secrets.
 */
function hardwareHelperEnv(envMap = {}, processEnv = process.env) {
  const env = { ...processEnv };
  for (const key of MODEL_SELECTION_KEYS) {
    const fromProcess = String((processEnv && processEnv[key]) || '').trim();
    if (fromProcess) {
      env[key] = fromProcess;
      continue;
    }
    const fromFile = String((envMap && envMap[key]) || '').trim();
    if (fromFile) {
      env[key] = fromFile;
    } else {
      delete env[key];
    }
  }
  return env;
}

function setupEnv() {
  logStep(2, 7, 'Checking apps/backend/.env');
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

  // Runtime YAML reads OLLAMA_HOST; accept legacy OLLAMA_BASE_URL and normalize.
  // Do NOT persist OLLAMA_MODEL — unset means hardware-adaptive selection in Python.
  const envMap = readEnvFile(BACKEND_ENV);
  const { host, updates } = ollamaHostUpdates(envMap);
  const pinned = explicitOllamaModel(envMap);
  if (Object.keys(updates).length) {
    upsertEnvKeys(BACKEND_ENV, updates);
    log(
      pinned
        ? `Normalized Ollama env: host=${host}, model=${pinned} (operator pin)`
        : `Normalized Ollama env: host=${host}, model=unset (hardware-adaptive)`
    );
  } else {
    log(
      pinned
        ? `Ollama config: host=${host}, model=${pinned} (operator pin)`
        : `Ollama config: host=${host}, model=unset (hardware-adaptive)`
    );
  }

  setupFrontendEnv(envMap);
}

/**
 * Keep apps/frontend/.env VM/LAN-compatible with backend FRONTEND_URL.
 * Empty VITE_API_URL → same-origin /api via Vite proxy (works on LAN IPs).
 */
function setupFrontendEnv(backendEnvMap = null) {
  const FRONTEND_ENV = path.join(FRONTEND_DIR, '.env');
  const FRONTEND_ENV_EXAMPLE = path.join(FRONTEND_DIR, '.env.example');
  const be = backendEnvMap || readEnvFile(BACKEND_ENV);

  if (!fs.existsSync(FRONTEND_ENV)) {
    if (fs.existsSync(FRONTEND_ENV_EXAMPLE)) {
      fs.copyFileSync(FRONTEND_ENV_EXAMPLE, FRONTEND_ENV);
      log('Created apps/frontend/.env from .env.example');
    } else {
      fs.writeFileSync(
        FRONTEND_ENV,
        [
          '# Auto-created by start.js / start-vm.js',
          'VITE_API_URL=',
          'VITE_API_TIMEOUT_MS=30000',
          '',
        ].join('\n'),
        'utf8'
      );
      log('Created apps/frontend/.env');
    }
  }

  const fe = readEnvFile(FRONTEND_ENV);
  const updates = {};

  // localhost absolute API breaks LAN (UI on 192.168.x.x → API hits client's localhost)
  const apiUrl = (fe.VITE_API_URL || '').trim();
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/?$/i.test(apiUrl)) {
    updates.VITE_API_URL = '';
    log(
      'Cleared VITE_API_URL localhost — using same-origin /api (VM/LAN safe via Vite proxy)',
      'warn'
    );
  } else if (!('VITE_API_URL' in fe)) {
    updates.VITE_API_URL = '';
  }

  if (!(fe.VITE_API_TIMEOUT_MS || '').trim()) {
    updates.VITE_API_TIMEOUT_MS = '30000';
  }

  const publicOrigin = (be.FRONTEND_URL || '').trim();
  if (publicOrigin && (fe.VITE_PUBLIC_ORIGIN || '').trim() !== publicOrigin) {
    updates.VITE_PUBLIC_ORIGIN = publicOrigin;
    log(`Synced VITE_PUBLIC_ORIGIN ← backend FRONTEND_URL (${publicOrigin})`);
  }

  if (Object.keys(updates).length) {
    upsertEnvKeys(FRONTEND_ENV, updates);
  } else {
    log(
      `Frontend .env OK (VITE_API_URL=${apiUrl ? apiUrl : '(same-origin)'}, ` +
        `VITE_PUBLIC_ORIGIN=${(fe.VITE_PUBLIC_ORIGIN || publicOrigin || '').trim() || 'unset'})`
    );
  }
}

async function setupBackend() {
  logStep(3, 7, 'Setting up backend (venv + pip)');
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
  log('Installing backend dependencies from requirements.txt (includes OCR: pymupdf, Pillow; RapidOCR on Python <3.13)...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Verifying OCR packages import...');
  const verifyCore = spawnSync(
    VENV_PYTHON,
    ['-c', "import fitz, PIL; print('OCR core packages OK (pymupdf, Pillow)')"],
    { cwd: BACKEND_DIR, encoding: 'utf8' }
  );
  if (verifyCore.status !== 0) {
    log('OCR core package verification failed. Re-run pip install -r requirements.txt', 'err');
    if (verifyCore.stderr) process.stderr.write(verifyCore.stderr);
    process.exit(1);
  }
  if (verifyCore.stdout) process.stdout.write(verifyCore.stdout.trim() + '\n');

  const verifyRapid = spawnSync(
    VENV_PYTHON,
    ['-c', "import rapidocr_onnxruntime; print('RapidOCR OK')"],
    { cwd: BACKEND_DIR, encoding: 'utf8' }
  );
  if (verifyRapid.status === 0) {
    if (verifyRapid.stdout) process.stdout.write(verifyRapid.stdout.trim() + '\n');
  } else {
    const pyVer = spawnSync(VENV_PYTHON, ['-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], {
      cwd: BACKEND_DIR,
      encoding: 'utf8',
    });
    const version = (pyVer.stdout || '').trim() || 'unknown';
    log(
      `RapidOCR not available on this Python (${version}). ` +
        'Scanned-image OCR needs Python 3.12 (recommended) or system Tesseract. Continuing setup...',
      'warn'
    );
  }
  log('Backend setup complete');
}

function httpGetJson(url, timeoutMs = 3000) {
  return new Promise((resolve) => {
    try {
      const u = new URL(url);
      const lib = u.protocol === 'https:' ? require('https') : http;
      const req = lib.request(
        {
          hostname: u.hostname,
          port: u.port || (u.protocol === 'https:' ? 443 : 80),
          path: `${u.pathname || '/'}${u.search || ''}`,
          method: 'GET',
        },
        (res) => {
          let body = '';
          res.on('data', (chunk) => {
            body += chunk;
          });
          res.on('end', () => {
            if (res.statusCode !== 200) {
              resolve(null);
              return;
            }
            try {
              resolve(JSON.parse(body));
            } catch {
              resolve(null);
            }
          });
        }
      );
      req.setTimeout(timeoutMs, () => {
        req.destroy();
        resolve(null);
      });
      req.on('error', () => resolve(null));
      req.end();
    } catch {
      resolve(null);
    }
  });
}

function commandExists(cmd) {
  try {
    if (process.platform === 'win32') {
      nodeExecSync(`where ${cmd}`, { stdio: 'ignore' });
    } else {
      nodeExecSync(`command -v ${cmd}`, { stdio: 'ignore', shell: true });
    }
    return true;
  } catch {
    return false;
  }
}

async function waitForOllama(host, maxWaitMs = 45000) {
  const step = 1500;
  let elapsed = 0;
  while (elapsed < maxWaitMs) {
    const tags = await httpGetJson(`${host.replace(/\/$/, '')}/api/tags`);
    if (tags && Array.isArray(tags.models)) return tags;
    await new Promise((r) => setTimeout(r, step));
    elapsed += step;
  }
  return null;
}

function modelIsPresent(tags, modelName) {
  const wanted = String(modelName || '').toLowerCase().trim();
  if (!wanted) return false;
  const models = (tags && tags.models) || [];
  return models.some((m) => {
    const name = String((m && (m.name || m.model)) || '').toLowerCase().trim();
    if (!name) return false;
    // Exact tag match only (e.g. qwen2.5:14b-instruct). Fuzzy base matches
    // falsely skip pull when a different size/tag of the same family exists.
    if (name === wanted) return true;
    // Bare base name (no tag) may appear as name:latest in Ollama tags.
    if (!wanted.includes(':') && (name === `${wanted}:latest` || name === wanted)) return true;
    return false;
  });
}

function resolveAdaptiveOllamaModel(envMap = {}) {
  const pinned = explicitOllamaModel(envMap);
  if (pinned) {
    return { model: pinned, source: 'operator' };
  }
  try {
    const env = hardwareHelperEnv(envMap, process.env);
    env.PYTHONPATH = BACKEND_DIR;
    const result = spawnSync(
      VENV_PYTHON,
      ['-m', 'app.ai.parser.engine.hardware'],
      { cwd: BACKEND_DIR, encoding: 'utf8', env }
    );
    const lines = String(result.stdout || '')
      .trim()
      .split(/\r?\n/)
      .filter(Boolean);
    const model = lines.length ? lines[lines.length - 1].trim() : '';
    if (result.status === 0 && model) {
      return { model, source: 'hardware' };
    }
    if (result.stderr) {
      log(`Hardware model helper: ${String(result.stderr).trim()}`, 'warn');
    }
  } catch (err) {
    log(`Hardware model helper failed: ${err.message || err}`, 'warn');
  }
  log(
    `Hardware detection unavailable — pulling ${SAFE_PULL_OLLAMA_MODEL} (not written to .env)`,
    'warn'
  );
  return { model: SAFE_PULL_OLLAMA_MODEL, source: 'pull-fallback' };
}

async function setupOllama() {
  logStep(4, 7, 'Checking Ollama');
  const envMap = readEnvFile(BACKEND_ENV);
  const host = (envMap.OLLAMA_HOST || envMap.OLLAMA_BASE_URL || DEFAULT_OLLAMA_HOST).replace(/\/$/, '');
  const resolved = resolveAdaptiveOllamaModel(envMap);
  const model = resolved.model;
  log(`Using Ollama model: ${model} (${resolved.source})`);
  log(`Using Ollama host: ${host}`);

  if (!isOllamaLoopbackHost(host)) {
    log('Remote Ollama host — health-check only (no local serve or model pull)');
    const tags = await httpGetJson(`${host}/api/tags`);
    if (!tags) {
      log(
        `Ollama did not become ready at ${host}. Parsing may fail until the central server is reachable.`,
        'warn'
      );
      return { host, model, ready: false };
    }
    log('Ollama API is reachable');
    const ready = modelIsPresent(tags, model);
    if (ready) {
      log(`Ollama setup complete (model ${model} listed)`);
    } else {
      log(
        `Ollama is reachable but model ${model} is not listed. Pull it on the central server.`,
        'warn'
      );
    }
    return { host, model, ready };
  }

  if (!commandExists('ollama')) {
    log(
      'Ollama CLI not found. Install from https://ollama.com/download then re-run start.js. ' +
        'Parsing requires Ollama (Grok cloud fallback is disabled).',
      'warn'
    );
    return { host, model, ready: false };
  }

  let tags = await httpGetJson(`${host}/api/tags`);
  if (!tags) {
    log('Ollama not responding — starting `ollama serve` in background...');
    ollamaProcess = spawn('ollama', ['serve'], {
      cwd: ROOT,
      stdio: 'ignore',
      shell: process.platform === 'win32',
      detached: true,
      env: process.env,
    });
    ollamaProcess.unref();
    tags = await waitForOllama(host);
  }

  if (!tags) {
    log(
      `Ollama did not become ready at ${host}. Parsing may fail until Ollama is running.`,
      'warn'
    );
    return { host, model, ready: false };
  }
  log('Ollama API is reachable');

  if (!modelIsPresent(tags, model)) {
    log(`Pulling Ollama model ${model} (this can take several minutes on first run)...`);
    try {
      await runCmd('ollama', ['pull', model], ROOT, process.env, process.platform === 'win32');
      log(`Model ${model} pulled successfully`);
    } catch (err) {
      log(`Failed to pull model ${model}: ${err.message || err}`, 'err');
      return { host, model, ready: false };
    }
  } else {
    log(`Model already available: ${model}`);
  }

  tags = await httpGetJson(`${host}/api/tags`);
  const ready = modelIsPresent(tags, model);
  if (ready) log('Ollama setup complete');
  else log(`Model ${model} still not listed after pull`, 'warn');
  return { host, model, ready };
}

async function setupFrontend() {
  logStep(5, 7, 'Setting up frontend (npm)');
  // Always run npm install so dependencies stay in sync. On Windows, shell: true is required to run npm (avoids spawn EINVAL).
  log('Installing frontend dependencies from package.json...');
  await runCmd('npm', ['install'], FRONTEND_DIR, process.env, process.platform === 'win32');
  log('Frontend setup complete');
}

/** Kill any leftover process still bound to a port (prevents stale Flask serving old code). */
function freePort(port) {
  try {
    if (process.platform === 'win32') {
      const out = nodeExecSync(`netstat -ano | findstr :${port}`, { encoding: 'utf8' });
      const pids = new Set();
      for (const line of out.split(/\r?\n/)) {
        if (!/LISTENING/i.test(line)) continue;
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && /^\d+$/.test(pid) && pid !== '0') pids.add(pid);
      }
      for (const pid of pids) {
        try {
          nodeExecSync(`taskkill /PID ${pid} /F`, { stdio: 'ignore' });
          log(`Freed port ${port} (killed PID ${pid})`);
        } catch {
          /* already gone */
        }
      }
    } else {
      try {
        const out = nodeExecSync(`lsof -ti :${port}`, { encoding: 'utf8' }).trim();
        for (const pid of out.split(/\s+/).filter(Boolean)) {
          try {
            process.kill(Number(pid), 'SIGTERM');
            log(`Freed port ${port} (killed PID ${pid})`);
          } catch {
            /* already gone */
          }
        }
      } catch {
        /* nothing listening */
      }
    }
  } catch {
    /* nothing listening / netstat empty */
  }
}

function startBackend() {
  logStep(6, 7, 'Starting backend (Flask)');
  freePort(BACKEND_PORT);
  const envMap = readEnvFile(BACKEND_ENV);
  const ollamaHost = (envMap.OLLAMA_HOST || envMap.OLLAMA_BASE_URL || DEFAULT_OLLAMA_HOST).trim();
  const env = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: path.join(ROOT, 'ai'),
    AI_RUNTIME_CONFIG: path.join(ROOT, 'ai', 'runtime', 'config', 'runtime.production.yaml'),
    OLLAMA_HOST: ollamaHost,
    OLLAMA_BASE_URL: ollamaHost,
    FLASK_USE_RELOADER: 'false',
  };
  const pinned = explicitOllamaModel(envMap);
  if (pinned) {
    env.OLLAMA_MODEL = pinned;
  } else {
    delete env.OLLAMA_MODEL;
  }
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
  logStep(7, 7, 'Starting frontend (Vite)');
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
  // Do not kill ollamaProcess — it may be a system-wide daemon started detached.
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

  const ollama = await setupOllama();
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
  console.log('Ollama:   ' + ollama.host + '  model=' + ollama.model + (ollama.ready ? ' (ready)' : ' (not ready — check host/model)'));
  console.log('Press Ctrl+C to stop.\n');
}

module.exports = {
  main,
  ROOT,
  BACKEND_DIR,
  FRONTEND_DIR,
  BACKEND_ENV,
  readEnvFile,
  upsertEnvKeys,
  DEFAULT_OLLAMA_HOST,
  explicitOllamaModel,
  ollamaModelIsExplicit,
  isOllamaLoopbackHost,
  ollamaHostUpdates,
  hardwareHelperEnv,
  MODEL_SELECTION_KEYS,
  resolveAdaptiveOllamaModel,
  log,
  logStep,
  checkEnv,
  setupEnv,
  setupFrontendEnv,
  setupBackend,
  setupOllama,
  setupFrontend,
  startBackend,
  startFrontend,
  waitForReady,
  openBrowser,
  onExit,
  BACKEND_PORT,
  FRONTEND_PORT,
  BROWSER_URL,
};

if (require.main === module) {
  main().catch((err) => {
    log(err.message || err, 'err');
    process.exit(1);
  });
}