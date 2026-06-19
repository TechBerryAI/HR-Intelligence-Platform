#!/usr/bin/env node
/**
 * Preflight: diagnose PostgreSQL connectivity with specific error reasons.
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

/** TCP probe — returns { ok, errorCode, errorMessage } */
function probeTcp(host, port, ms = 5000) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port });
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(result);
    };
    socket.setTimeout(ms);
    socket.on('connect', () => finish({ ok: true }));
    socket.on('timeout', () =>
      finish({
        ok: false,
        errorCode: 'ETIMEDOUT',
        errorMessage: `TCP connection to ${host}:${port} timed out after ${ms}ms`,
      })
    );
    socket.on('error', (err) =>
      finish({
        ok: false,
        errorCode: err.code || 'ESOCKET',
        errorMessage: err.message || String(err),
      })
    );
  });
}

function testFromWindows(host, port) {
  if (!isWSL) return null;
  const script = [
    `$r = Test-NetConnection -ComputerName '${host}' -Port ${port} -WarningAction SilentlyContinue`,
    `Write-Output "TCP=$($r.TcpTestSucceeded)"`,
    `Write-Output "PING=$($r.PingSucceeded)"`,
  ].join('; ');
  const r = spawnSync('powershell.exe', ['-NoProfile', '-Command', script], {
    encoding: 'utf8',
    timeout: 25000,
  });
  if (r.status !== 0) return null;
  const tcp = /TCP=(True|False)/i.exec(r.stdout || '');
  const ping = /PING=(True|False)/i.exec(r.stdout || '');
  if (!tcp) return null;
  return {
    tcp: tcp[1].toLowerCase() === 'true',
    ping: ping ? ping[1].toLowerCase() === 'true' : null,
  };
}

/** Run psql for PostgreSQL-level errors (auth, pg_hba, wrong db) */
function probePostgres(cfg) {
  const r = spawnSync(
    'psql',
    [
      '-h', cfg.host,
      '-p', String(cfg.port),
      '-U', cfg.user,
      '-d', cfg.db,
      '-c', 'SELECT 1',
    ],
    {
      encoding: 'utf8',
      timeout: 12000,
      env: { ...process.env, PGPASSWORD: cfg.password },
    }
  );
  if (r.status === 0) return { ok: true };
  const err = (r.stderr || r.stdout || '').trim();
  return { ok: false, errorMessage: err || `psql exited with code ${r.status}` };
}

function explainTcp(code, host, port) {
  switch (code) {
    case 'ECONNREFUSED':
      return {
        summary: 'Connection refused — nothing is listening on that host:port',
        causes: [
          `PostgreSQL is not running on ${host}`,
          `PostgreSQL is running but not on port ${port}`,
          `Wrong IP in POSTGRES_HOST (VM may have moved — current .env: ${host})`,
        ],
        fix: `On the VM: sudo ss -tlnp | grep ${port}  and  sudo systemctl status postgresql`,
      };
    case 'EHOSTUNREACH':
    case 'ENETUNREACH':
      return {
        summary: 'No route to host — network cannot reach that IP',
        causes: [
          `Host ${host} is offline or wrong IP`,
          'Your PC is on a different subnet / VPN / Wi‑Fi network',
          'VM IP changed (e.g. was 192.168.1.134, now 192.168.1.120)',
        ],
        fix: `Verify VM IP in pgAdmin or VM console, update POSTGRES_HOST in backend/.env, ping ${host}`,
      };
    case 'ETIMEDOUT':
      return {
        summary: 'Connection timed out — host may be up but port is blocked',
        causes: [
          `Firewall on VM blocking port ${port}`,
          'Firewall on your PC or router blocking outbound',
          'PostgreSQL listening only on localhost inside VM',
        ],
        fix: `On VM: sudo ufw allow ${port}/tcp  and  listen_addresses = '*' in postgresql.conf`,
      };
    default:
      return {
        summary: `TCP failed (${code})`,
        causes: ['See error message below'],
        fix: `Test: psql -h ${host} -p ${port} -U postgres -d hrms -c "SELECT 1"`,
      };
  }
}

function explainPsql(msg) {
  const m = msg.toLowerCase();
  if (m.includes('no pg_hba.conf entry')) {
    const hostMatch = msg.match(/host "([^"]+)"/);
    const clientIp = hostMatch ? hostMatch[1] : 'your PC IP';
    return {
      summary: 'PostgreSQL rejected client — pg_hba.conf missing your IP',
      causes: [`VM allows other IPs but not ${clientIp}`],
      fix: `On VM add: host all all ${clientIp}/32 scram-sha-256  then  sudo systemctl reload postgresql`,
    };
  }
  if (m.includes('password authentication failed')) {
    return {
      summary: 'Wrong password — TCP works but credentials failed',
      causes: ['POSTGRES_PASSWORD in backend/.env does not match VM postgres password'],
      fix: 'Update POSTGRES_PASSWORD to match pgAdmin / VM postgres user password',
    };
  }
  if (m.includes('does not exist') && m.includes('database')) {
    return {
      summary: 'Database name not found on server',
      causes: ['POSTGRES_DB in .env does not exist on this PostgreSQL instance'],
      fix: 'Create the database on VM or fix POSTGRES_DB in backend/.env',
    };
  }
  return {
    summary: 'PostgreSQL handshake failed after TCP connected',
    causes: [msg],
    fix: 'Check PostgreSQL logs on the VM: sudo journalctl -u postgresql -n 50',
  };
}

function printDiagnosis(cfg, diagnosis) {
  console.error('\n========================================');
  console.error('  DATABASE CONNECTION FAILED');
  console.error('========================================\n');
  console.error(`Target:  ${cfg.host}:${cfg.port}`);
  console.error(`Database: ${cfg.db}`);
  console.error(`User:     ${cfg.user}`);
  console.error(`Source:   ${isWSL ? 'WSL2' : process.platform}\n`);
  console.error(`Issue:    ${diagnosis.summary}\n`);

  if (diagnosis.tcp) {
    console.error(`TCP:      ${diagnosis.tcp.ok ? 'OK' : 'FAILED'}`);
    if (!diagnosis.tcp.ok) {
      console.error(`          ${diagnosis.tcp.errorCode}: ${diagnosis.tcp.errorMessage}`);
    }
  }

  if (diagnosis.windows) {
    console.error(`Windows:  ping=${diagnosis.windows.ping}  tcp:${cfg.port}=${diagnosis.windows.tcp}`);
  }

  if (diagnosis.psql && !diagnosis.psql.ok) {
    console.error(`PostgreSQL: ${diagnosis.psql.errorMessage.split('\n')[0]}`);
  }

  console.error('\nLikely causes:');
  diagnosis.causes.forEach((c) => console.error(`  • ${c}`));

  console.error('\nFix:');
  console.error(`  ${diagnosis.fix}\n`);

  if (isWSL && diagnosis.windows?.tcp && !diagnosis.tcp?.ok) {
    console.error('Note: Windows can reach the VM but WSL cannot — run `wsl --shutdown` in Windows PowerShell, reopen terminal.\n');
  }
}

(async () => {
  const cfg = readEnv();
  const target = `${cfg.host}:${cfg.port}`;

  // Step 1: TCP
  const tcp = await probeTcp(cfg.host, cfg.port);
  if (tcp.ok) {
    // Step 2: PostgreSQL auth / pg_hba / db name
    const psql = probePostgres(cfg);
    if (psql.ok) process.exit(0);

    const explained = explainPsql(psql.errorMessage);
    printDiagnosis(cfg, {
      summary: explained.summary,
      tcp,
      psql,
      causes: explained.causes,
      fix: explained.fix,
    });
    process.exit(1);
  }

  // TCP failed — gather more context
  const windows = isWSL ? testFromWindows(cfg.host, cfg.port) : null;
  const explained = explainTcp(tcp.errorCode, cfg.host, cfg.port);

  const causes = [...explained.causes];
  if (windows?.ping === false) causes.push(`Windows cannot ping ${cfg.host} — IP may be wrong or VM is down`);
  if (windows?.ping === true && windows?.tcp === false)
    causes.push(`Windows can ping ${cfg.host} but port ${cfg.port} is closed on the VM firewall`);
  if (windows?.tcp === true && !tcp.ok)
    causes.push('Windows can open the port but WSL cannot — WSL networking issue');

  if (isLocalHost(cfg.host) && isWSL) {
    causes.push('POSTGRES_HOST is localhost but PostgreSQL runs on Windows — WSL localhost ≠ Windows localhost');
  }

  printDiagnosis(cfg, {
    summary: explained.summary,
    tcp,
    windows,
    causes,
    fix: explained.fix,
  });
  process.exit(1);
})();
