#!/usr/bin/env node
/**
 * Preflight: verify configured PostgreSQL host:port is reachable before startup.
 */
const net = require('net');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const isWSL = !!(process.env.WSL_DISTRO_NAME || process.env.WSLENV);
const envPath = path.join(__dirname, '..', 'backend', '.env');

function readEnv() {
  const text = fs.readFileSync(envPath, 'utf8');
  const get = (key, fallback = '') =>
    (text.match(new RegExp(`^${key}=(.+)$`, 'm')) || [])[1]?.trim() || fallback;
  return {
    host: get('POSTGRES_HOST', 'localhost'),
    port: Number(get('POSTGRES_PORT', '5432')),
    db: get('POSTGRES_DB', 'postgres'),
    user: get('POSTGRES_USER', 'postgres'),
    password: get('POSTGRES_PASSWORD', ''),
  };
}

function isLocalHost(host) {
  return ['localhost', '127.0.0.1', '::1'].includes(host) || host.startsWith('172.22.');
}

function getWslGateway() {
  try {
    const out = spawnSync('ip', ['route', 'show', 'default'], { encoding: 'utf8' });
    const m = out.stdout.match(/\s(\d+\.\d+\.\d+\.\d+)\s/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}

function probe(host, port, ms = 4000) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    const done = (ok) => {
      socket.destroy();
      resolve(ok);
    };
    socket.setTimeout(ms);
    socket.on('connect', () => done(true));
    socket.on('timeout', () => done(false));
    socket.on('error', () => done(false));
  });
}

function testFromWindows(host, port) {
  if (!isWSL) return null;
  const script = `Test-NetConnection -ComputerName '${host}' -Port ${port} -WarningAction SilentlyContinue | Select-Object -ExpandProperty TcpTestSucceeded`;
  const r = spawnSync('powershell.exe', ['-NoProfile', '-Command', script], {
    encoding: 'utf8',
    timeout: 20000,
  });
  if (r.status !== 0) return null;
  const val = (r.stdout || '').trim().toLowerCase();
  if (val === 'true') return true;
  if (val === 'false') return false;
  return null;
}

function printLocalWslHelp(gateway) {
  console.error('PostgreSQL appears to run on this Windows machine, but WSL cannot reach it.\n');
  console.error('FIX (pick ONE):\n');
  console.error('  Option A — recommended (no admin):');
  console.error('    1. Open Windows PowerShell (not WSL)');
  console.error('    2. Run:  wsl --shutdown');
  console.error('    3. Reopen terminal and run:  node start.js\n');
  console.error('  Option B — firewall (Admin PowerShell):');
  if (gateway) {
    console.error(`    1. Set POSTGRES_HOST=${gateway} in backend/.env`);
  }
  console.error('    2. Run:  D:\\Projects\\HR-Job-Portal-App\\scripts\\fix-windows-postgres.ps1\n');
}

function printRemoteHelp(cfg) {
  const win = testFromWindows(cfg.host, cfg.port);
  console.error(`Target: ${cfg.host}:${cfg.port}  database=${cfg.db}\n`);

  if (win === false) {
    console.error('Windows also cannot open a TCP connection to this host:port.');
    console.error('The .env values look fine — the VM/network must allow inbound PostgreSQL.\n');
  } else if (win === true) {
    console.error('Windows CAN reach this port, but WSL cannot (WSL LAN routing).');
    console.error('Run `wsl --shutdown` in Windows PowerShell, then reopen this terminal.\n');
  } else {
    console.error('Could not reach the database server from this environment.\n');
  }

  console.error('On the VM (192.168.1.134), verify:\n');
  console.error('  1. PostgreSQL is running:  sudo systemctl status postgresql');
  console.error('  2. postgresql.conf:  listen_addresses = \'*\'  and  port = 6567');
  console.error('  3. pg_hba.conf allows your PC, e.g.:');
  console.error('       host  all  all  192.168.0.0/24  scram-sha-256');
  console.error('       host  all  all  192.168.1.0/24  scram-sha-256');
  console.error('  4. Firewall allows port 6567:  sudo ufw allow 6567/tcp');
  console.error('  5. Reload:  sudo systemctl reload postgresql\n');
  console.error('Then test from WSL:');
  console.error(`  PGPASSWORD='***' psql -h ${cfg.host} -p ${cfg.port} -U ${cfg.user} -d ${cfg.db} -c "SELECT 1"`);
}

(async () => {
  const cfg = readEnv();
  const gateway = isWSL ? getWslGateway() : null;
  const local = isLocalHost(cfg.host);

  if (await probe(cfg.host, cfg.port)) process.exit(0);

  if (local && isWSL) {
    for (const h of ['localhost', '127.0.0.1', gateway].filter(Boolean)) {
      if (h !== cfg.host && (await probe(h, cfg.port))) process.exit(0);
    }
  }

  console.error('\n========================================');
  console.error('  DATABASE UNREACHABLE');
  console.error('========================================\n');

  if (local && isWSL) printLocalWslHelp(gateway);
  else printRemoteHelp(cfg);

  process.exit(1);
})();
