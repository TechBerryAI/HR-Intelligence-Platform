#!/usr/bin/env node
/**
 * HCIP full-stack start for VM / LAN setups.
 *
 * Brings up (in order):
 *   1. Database VM (Hyper-V, optional) or local Docker Postgres
 *   2. Waits until PostgreSQL from apps/backend/.env is reachable
 *   3. Backend (Flask :3000) + Frontend (Vite :5173) + Ollama
 *   4. Opens the browser
 *
 * Usage (repo root):
 *   node start-vm.js
 *
 * Optional env / .env keys (apps/backend/.env or process env):
 *   HCIP_VM_NAME=MyDbVm          Hyper-V VM name to Start-VM
 *   HCIP_VM_PROVIDER=hyperv|docker|auto   (default: auto)
 *   HCIP_START_DOCKER_DB=true    Force docker compose postgres
 *   HCIP_SKIP_OLLAMA=true        Skip Ollama setup
 *   HCIP_OPEN_BROWSER=false      Do not open browser
 *
 * Ctrl+C stops backend + frontend (same as start.js).
 */

const fs = require('fs');
const path = require('path');
const net = require('net');
const { spawn, spawnSync } = require('child_process');

const start = require('./start.js');
const {
  ROOT,
  BACKEND_ENV,
  readEnvFile,
  log,
  checkEnv,
  setupEnv,
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
} = start;

const COMPOSE_FILE = path.join(ROOT, 'infrastructure', 'docker', 'docker-compose.yml');
const isWSL = !!(process.env.WSL_DISTRO_NAME || process.env.WSLENV);
const isWin = process.platform === 'win32' || isWSL;

function envFlag(map, key, fallback = false) {
  const raw = (process.env[key] || map[key] || '').toString().trim().toLowerCase();
  if (!raw) return fallback;
  return raw === '1' || raw === 'true' || raw === 'yes';
}

function isLocalHost(host) {
  return (
    !host ||
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '::1' ||
    host.startsWith('172.22.')
  );
}

function probeTcp(host, port, ms = 4000) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    let settled = false;
    const done = (ok) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(ok);
    };
    socket.setTimeout(ms);
    socket.on('connect', () => done(true));
    socket.on('timeout', () => done(false));
    socket.on('error', () => done(false));
  });
}

async function waitForTcp(host, port, label, maxWaitMs = 120000) {
  const step = 2000;
  let elapsed = 0;
  log(`Waiting for ${label} at ${host}:${port}...`);
  while (elapsed < maxWaitMs) {
    if (await probeTcp(host, port)) {
      log(`${label} is reachable (${host}:${port})`);
      return true;
    }
    if (elapsed > 0 && elapsed % 10000 === 0) {
      log(`Still waiting for ${label}... (${elapsed / 1000}s)`, 'warn');
    }
    await new Promise((r) => setTimeout(r, step));
    elapsed += step;
  }
  return false;
}

function runPs(command, { timeout = 60000 } = {}) {
  const exe = isWSL ? 'powershell.exe' : 'powershell';
  return spawnSync(
    exe,
    ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
    { encoding: 'utf8', timeout, windowsHide: true }
  );
}

function dockerBin() {
  if (commandExists('docker')) return 'docker';
  const candidates = [
    '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe',
    'C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

function commandExists(cmd) {
  try {
    if (process.platform === 'win32' && !isWSL) {
      const r = spawnSync('where', [cmd], { encoding: 'utf8' });
      return r.status === 0;
    }
    const r = spawnSync('bash', ['-lc', `command -v ${cmd}`], { encoding: 'utf8' });
    return r.status === 0 && !!(r.stdout || '').trim();
  } catch {
    return false;
  }
}

function ensureDockerDesktop() {
  const docker = dockerBin();
  if (!docker) {
    log('Docker CLI not found — skipping Docker Desktop start', 'warn');
    return false;
  }

  const info = spawnSync(docker, ['info'], { encoding: 'utf8', timeout: 15000 });
  if (info.status === 0) {
    log('Docker engine is running');
    return true;
  }

  log('Docker engine not running — starting Docker Desktop...');
  let desktopWin = 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe';
  const desktopWsl = '/mnt/c/Program Files/Docker/Docker/Docker Desktop.exe';
  if (isWSL && fs.existsSync(desktopWsl)) {
    runPs(`Start-Process '${desktopWin}'`);
  } else if (fs.existsSync(desktopWin) || fs.existsSync(desktopWsl)) {
    const exe = fs.existsSync(desktopWin) ? desktopWin : desktopWsl;
    spawn(exe, [], { detached: true, stdio: 'ignore' }).unref();
  } else {
    log('Docker Desktop executable not found', 'warn');
    return false;
  }

  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const check = spawnSync(docker, ['info'], { encoding: 'utf8', timeout: 10000 });
    if (check.status === 0) {
      log('Docker engine is ready');
      return true;
    }
    spawnSync(process.platform === 'win32' ? 'timeout' : 'sleep', process.platform === 'win32' ? ['/t', '3'] : ['3'], {
      shell: true,
      stdio: 'ignore',
    });
  }
  log('Docker Desktop did not become ready in time', 'warn');
  return false;
}

function startDockerPostgres(envMap) {
  if (!fs.existsSync(COMPOSE_FILE)) {
    log(`Compose file missing: ${COMPOSE_FILE}`, 'err');
    return false;
  }
  if (!ensureDockerDesktop()) return false;

  const docker = dockerBin();
  log('Starting PostgreSQL via docker compose...');
  const up = spawnSync(
    docker,
    ['compose', '-f', COMPOSE_FILE, 'up', '-d'],
    { cwd: ROOT, encoding: 'utf8', timeout: 120000 }
  );
  if (up.stdout) process.stdout.write(up.stdout);
  if (up.stderr) process.stderr.write(up.stderr);
  if (up.status !== 0) {
    log('docker compose up failed', 'err');
    return false;
  }

  // Align .env to local compose defaults when forcing docker DB and host is remote
  if (envFlag(envMap, 'HCIP_START_DOCKER_DB') && !isLocalHost(envMap.POSTGRES_HOST)) {
    log(
      'HCIP_START_DOCKER_DB=true but POSTGRES_HOST points at a remote VM. ' +
        'Compose maps 5432 locally — set POSTGRES_HOST=localhost and POSTGRES_PORT=5432 to use it.',
      'warn'
    );
  }
  return true;
}

function startHyperVVm(vmName) {
  if (!vmName) return { attempted: false, ok: false };
  if (!isWin) {
    log('Hyper-V start is only available on Windows/WSL', 'warn');
    return { attempted: true, ok: false };
  }

  log(`Starting Hyper-V VM "${vmName}" (if Off/Saved)...`);
  const script = `
$ErrorActionPreference = 'Stop'
$name = '${vmName.replace(/'/g, "''")}'
try {
  $vm = Get-VM -Name $name
} catch {
  Write-Output "MISSING"
  exit 2
}
Write-Output ("STATE=" + $vm.State)
if ($vm.State -eq 'Running') { exit 0 }
Start-VM -Name $name
Start-Sleep -Seconds 2
$vm2 = Get-VM -Name $name
Write-Output ("STATE=" + $vm2.State)
if ($vm2.State -ne 'Running') { exit 1 }
exit 0
`.trim();

  const r = runPs(script, { timeout: 120000 });
  const out = `${r.stdout || ''}${r.stderr || ''}`.trim();
  if (out) console.log(out);

  if (r.status === 2 || /MISSING/i.test(out)) {
    log(`Hyper-V VM "${vmName}" not found (or no permission to query VMs)`, 'warn');
    return { attempted: true, ok: false };
  }
  if (r.status !== 0) {
    log(`Failed to start Hyper-V VM "${vmName}" (exit ${r.status}). Start it manually in Hyper-V Manager.`, 'warn');
    return { attempted: true, ok: false };
  }
  log(`Hyper-V VM "${vmName}" is Running`);
  return { attempted: true, ok: true };
}

async function ensureDatabase(envMap) {
  const host = (envMap.POSTGRES_HOST || 'localhost').trim();
  const port = Number(envMap.POSTGRES_PORT || 5432);
  const provider = (process.env.HCIP_VM_PROVIDER || envMap.HCIP_VM_PROVIDER || 'auto')
    .toString()
    .trim()
    .toLowerCase();
  const vmName = (process.env.HCIP_VM_NAME || envMap.HCIP_VM_NAME || '').trim();
  const forceDocker = envFlag(envMap, 'HCIP_START_DOCKER_DB');

  log(`Database target: ${host}:${port} (db=${envMap.POSTGRES_DB || '?'})`);

  // Already up?
  if (await probeTcp(host, port)) {
    log('PostgreSQL already reachable — skipping VM/docker start');
    return true;
  }

  log('PostgreSQL not reachable yet — bringing up database...');

  if (provider === 'hyperv' || (provider === 'auto' && vmName)) {
    startHyperVVm(vmName);
    if (await waitForTcp(host, port, 'PostgreSQL (VM)', 180000)) return true;
  }

  if (provider === 'docker' || forceDocker || (provider === 'auto' && isLocalHost(host))) {
    if (startDockerPostgres(envMap)) {
      const waitHost = isLocalHost(host) ? host : '127.0.0.1';
      const waitPort = isLocalHost(host) ? port : 5432;
      if (await waitForTcp(waitHost, waitPort, 'PostgreSQL (Docker)', 120000)) {
        if (!isLocalHost(host)) {
          log(
            `Docker Postgres is up on ${waitHost}:${waitPort}, but .env still points to ${host}:${port}. Update POSTGRES_* or set HCIP_START_DOCKER_DB with matching host.`,
            'err'
          );
          return false;
        }
        return true;
      }
    }
  }

  // Last chance: wait longer for a manually started remote VM
  if (await waitForTcp(host, port, 'PostgreSQL', 60000)) return true;

  log(
    `Could not reach PostgreSQL at ${host}:${port}.\n` +
      `  • Start your DB VM (Hyper-V), or set HCIP_VM_NAME=<vm-name>\n` +
      `  • Or run local DB: HCIP_START_DOCKER_DB=true with POSTGRES_HOST=localhost POSTGRES_PORT=5432\n` +
      `  • Then: node scripts/db-preflight.js`,
    'err'
  );
  return false;
}

async function main() {
  console.log('\n========================================');
  console.log('   HCIP — Start VM / Full Stack');
  console.log('========================================\n');

  checkEnv();
  setupEnv(); // also syncs apps/frontend/.env from backend FRONTEND_URL (VM/LAN)

  const envMap = {
    ...readEnvFile(BACKEND_ENV),
    HCIP_VM_NAME: process.env.HCIP_VM_NAME,
    HCIP_VM_PROVIDER: process.env.HCIP_VM_PROVIDER,
    HCIP_START_DOCKER_DB: process.env.HCIP_START_DOCKER_DB,
  };

  const dbOk = await ensureDatabase(envMap);
  if (!dbOk) process.exit(1);

  await setupBackend();

  const preflight = spawnSync('node', [path.join(ROOT, 'scripts', 'db-preflight.js')], {
    encoding: 'utf8',
    stdio: ['inherit', 'pipe', 'inherit'],
  });
  if (preflight.stdout) process.stdout.write(preflight.stdout);
  if (preflight.status !== 0) {
    log('Database preflight failed', 'err');
    process.exit(1);
  }

  let ollama = { host: 'skipped', model: 'skipped', ready: false };
  if (!envFlag(envMap, 'HCIP_SKIP_OLLAMA')) {
    ollama = await setupOllama();
  } else {
    log('Skipping Ollama setup (HCIP_SKIP_OLLAMA=true)');
  }

  await setupFrontend();

  process.on('SIGINT', onExit);
  process.on('SIGTERM', onExit);

  startBackend();
  startFrontend();

  const ready = await waitForReady();
  const shouldOpen =
    String(process.env.HCIP_OPEN_BROWSER || envMap.HCIP_OPEN_BROWSER || 'true')
      .toLowerCase()
      .trim() !== 'false';
  if (ready && shouldOpen) openBrowser();

  console.log('\n--- Ready (VM stack) ---');
  console.log(`Database: ${envMap.POSTGRES_HOST}:${envMap.POSTGRES_PORT}/${envMap.POSTGRES_DB}`);
  console.log(`Backend:  http://localhost:${BACKEND_PORT}  (also 0.0.0.0:${BACKEND_PORT})`);
  console.log(`Frontend: ${BROWSER_URL}  (Vite binds 0.0.0.0 — LAN OK)`);
  const feOrigin = (readEnvFile(path.join(ROOT, 'apps', 'frontend', '.env')).VITE_PUBLIC_ORIGIN || '').trim();
  if (feOrigin) console.log(`LAN UI:   ${feOrigin}`);
  console.log('API mode: same-origin /api (VITE_API_URL empty — VM/LAN safe)');
  console.log(
    `Ollama:   ${ollama.host}  model=${ollama.model}` +
      (ollama.ready ? ' (ready)' : ' (not ready / skipped)')
  );
  console.log('Press Ctrl+C to stop backend + frontend.\n');
}

if (require.main === module) {
  main().catch((err) => {
    log(err.message || err, 'err');
    process.exit(1);
  });
}

module.exports = { main, ensureDatabase, startHyperVVm, startDockerPostgres };