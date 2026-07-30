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
const DEFAULT_OLLAMA_HOST = 'http://127.0.0.1:11434';
const DEFAULT_OLLAMA_MODEL = 'qwen2.5:7b-instruct';

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
  const envMap = readEnvFile(BACKEND_ENV);
  const host =
    (envMap.OLLAMA_HOST || '').trim() ||
    (envMap.OLLAMA_BASE_URL || '').trim() ||
    DEFAULT_OLLAMA_HOST;
  const model = (envMap.OLLAMA_MODEL || '').trim() || DEFAULT_OLLAMA_MODEL;
  const updates = {};
  if ((envMap.OLLAMA_HOST || '').trim() !== host) updates.OLLAMA_HOST = host;
  if (!(envMap.OLLAMA_MODEL || '').trim()) updates.OLLAMA_MODEL = model;
  if (!(envMap.OLLAMA_BASE_URL || '').trim()) updates.OLLAMA_BASE_URL = host;
  if (Object.keys(updates).length) {
    upsertEnvKeys(BACKEND_ENV, updates);
    log(`Normalized Ollama env: host=${host}, model=${model}`);
  } else {
    log(`Ollama config: host=${host}, model=${model}`);
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
  log('Installing backend dependencies from requirements.txt (includes OCR: pymupdf, rapidocr-onnxruntime, Pillow)...');
  await runCmd(VENV_PYTHON, ['-m', 'pip', 'install', '-r', 'requirements.txt', '-q'], BACKEND_DIR);
  log('Verifying OCR packages import...');
  const verify = spawnSync(
    VENV_PYTHON,
    [
      '-c',
      "import fitz, PIL, rapidocr_onnxruntime; print('OCR packages OK')",
    ],
    { cwd: BACKEND_DIR, encoding: 'utf8' }
  );
  if (verify.status !== 0) {
    log('OCR package verification failed. Re-run pip install -r requirements.txt', 'err');
    if (verify.stderr) process.stderr.write(verify.stderr);
    process.exit(1);
  }
  if (verify.stdout) process.stdout.write(verify.stdout.trim() + '\n');
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
  const wanted = String(modelName || '').toLowerCase();
  const wantedBase = wanted.split(':')[0];
  const models = (tags && tags.models) || [];
  return models.some((m) => {
    const name = String((m && (m.name || m.model)) || '').toLowerCase();
    return name === wanted || name.startsWith(`${wantedBase}:`) || name === wantedBase;
  });
}

async function setupOllama() {
  logStep(4, 7, 'Setting up Ollama (serve + model pull)');
  const envMap = readEnvFile(BACKEND_ENV);
  const host = (envMap.OLLAMA_HOST || envMap.OLLAMA_BASE_URL || DEFAULT_OLLAMA_HOST).replace(/\/$/, '');
  const model = envMap.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL;
  log(`Using Ollama model: ${model}`);
  log(`Using Ollama host: ${host}`);

  if (!commandExists('ollama')) {
    log(
      'Ollama CLI not found. Install from https://ollama.com/download then re-run start.js. ' +
        'Resume/JD parsing will fall back to Grok only if XAI_API_KEY is set.',
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

  // Re-check after pull
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

function startBackend() {
  logStep(6, 7, 'Starting backend (Flask)');
  const envMap = readEnvFile(BACKEND_ENV);
  const ollamaHost = (envMap.OLLAMA_HOST || envMap.OLLAMA_BASE_URL || DEFAULT_OLLAMA_HOST).trim();
  const ollamaModel = (envMap.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim();
  const env = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: path.join(ROOT, 'ai'),
    AI_RUNTIME_CONFIG: path.join(ROOT, 'ai', 'runtime', 'config', 'runtime.production.yaml'),
    OLLAMA_HOST: ollamaHost,
    OLLAMA_BASE_URL: ollamaHost,
    OLLAMA_MODEL: ollamaModel,
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
  console.log('Ollama:   ' + ollama.host + '  model=' + ollama.model + (ollama.ready ? ' (ready)' : ' (not ready — check install/pull)'));
  console.log('Press Ctrl+C to stop.\n');
}

main().catch((err) => {
  log(err.message || err, 'err');
  process.exit(1);
});
