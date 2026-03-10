#!/usr/bin/env node

/**
 * HRMS PRODUCTION VM START SCRIPT
 *
 * Production architecture:
 *
 *   Browser
 *      ↓
 *   NGINX (Port 80)
 *      ├── /        → React Build  (frontend/dist)
 *      ├── /api     → Gunicorn     (127.0.0.1:3000)
 *      └── /health  → Gunicorn     (127.0.0.1:3000)
 *                         ↓
 *                   PostgreSQL (192.168.1.53:6567)
 *
 * Usage:
 *   node start-vm.js               — full startup
 *   node start-vm.js --skip-git    — skip git pull  (fast restart)
 *   node start-vm.js --skip-build  — skip npm build (fast restart)
 */

const { execSync, spawn, spawnSync } = require("child_process");
const path  = require("path");
const fs    = require("fs");
const os    = require("os");
const http  = require("http");

// ─── Configuration ────────────────────────────────────────────────────────────

const ROOT          = __dirname;
const FRONTEND_DIR  = path.join(ROOT, "frontend");
const BACKEND_DIR   = path.join(ROOT, "backend");
const LOGS_DIR      = path.join(ROOT, "logs");
const VENV_DIR      = path.join(BACKEND_DIR, "venv");
const PID_FILE      = path.join(ROOT, "gunicorn.pid");

const VM_IP         = "192.168.1.19";
const BACKEND_PORT  = 3000;
const WORKERS       = Math.max(2, Math.min(os.cpus().length * 2 + 1, 8));

const NGINX_SITE    = "/etc/nginx/sites-available/hrms";
const NGINX_ENABLED = "/etc/nginx/sites-enabled/hrms";
const NGINX_DEFAULT = "/etc/nginx/sites-enabled/default";

const ARGS        = process.argv.slice(2);
const SKIP_GIT    = ARGS.includes("--skip-git");
const SKIP_BUILD  = ARGS.includes("--skip-build");

// ─── State ────────────────────────────────────────────────────────────────────

let backendProcess = null;
let restartCount   = 0;
let logStream      = null;

const MAX_RESTARTS     = 5;
const RESTART_DELAY_MS = 3000;

// ─── Logging ──────────────────────────────────────────────────────────────────

function ensureLogsDir() {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
  const logFile = path.join(
    LOGS_DIR,
    `hrms-${new Date().toISOString().slice(0, 10)}.log`
  );
  logStream = fs.createWriteStream(logFile, { flags: "a" });
}

function log(msg, level = "INFO") {
  const t    = new Date().toISOString().replace("T", " ").slice(0, 19);
  const line = `[HRMS ${t}] [${level.padEnd(5)}] ${msg}`;
  console.log(line);
  if (logStream) logStream.write(line + "\n");
}

const logWarn  = (msg) => log(msg, "WARN");
const logError = (msg) => log(msg, "ERROR");

// ─── Shell helpers ────────────────────────────────────────────────────────────

function run(cmd, cwd = ROOT, { allowFail = false } = {}) {
  log(`$ ${cmd}`);
  try {
    execSync(cmd, { cwd, stdio: "inherit", shell: true });
  } catch (err) {
    if (allowFail) {
      logWarn(`Non-fatal failure: ${cmd}`);
      return false;
    }
    logError(`Command failed: ${cmd}`);
    throw err;
  }
  return true;
}

function commandExists(cmd) {
  const result = spawnSync("which", [cmd], { encoding: "utf8" });
  return result.status === 0;
}

// ─── Pre-flight checks ────────────────────────────────────────────────────────

function preflight() {
  log("Running pre-flight checks...");

  if (os.platform() !== "linux") {
    logWarn(`Platform is '${os.platform()}' — this script targets Linux VMs.`);
  }

  const required = ["git", "node", "npm", "nginx", "python3"];
  const missing  = required.filter((c) => !commandExists(c));
  if (missing.length > 0) {
    logError(`Missing required commands: ${missing.join(", ")}`);
    logError("Install them with: sudo apt install -y " + missing.join(" "));
    process.exit(1);
  }

  const envFile = path.join(BACKEND_DIR, ".env");
  if (!fs.existsSync(envFile)) {
    logError("backend/.env not found — copy backend/.env.example and configure it.");
    process.exit(1);
  }

  const envContent = fs.readFileSync(envFile, "utf8");
  if (/FLASK_DEBUG\s*=\s*true/i.test(envContent)) {
    logWarn("FLASK_DEBUG=true detected in backend/.env — set to false for production!");
  }

  try {
    const out = execSync(
      `ss -tlnp 2>/dev/null | grep :${BACKEND_PORT} || true`,
      { encoding: "utf8", shell: true }
    );
    if (out.trim()) {
      logWarn(`Port ${BACKEND_PORT} is in use — killing existing process...`);
      run(`fuser -k ${BACKEND_PORT}/tcp`, ROOT, { allowFail: true });
    }
  } catch (_) {
    // port check is best-effort
  }

  if (fs.existsSync(PID_FILE)) {
    logWarn("Stale PID file found — removing it.");
    fs.unlinkSync(PID_FILE);
  }

  log("Pre-flight checks passed.");
}

// ─── Git ──────────────────────────────────────────────────────────────────────

function ensureBranch() {
  if (SKIP_GIT) {
    logWarn("Skipping git pull (--skip-git flag).");
    return;
  }
  log("Syncing with development branch...");
  run("git fetch origin");
  run("git checkout development");
  run("git pull origin development");
}

// ─── Python venv ─────────────────────────────────────────────────────────────

function ensureVenv() {
  const venvPython = path.join(VENV_DIR, "bin", "python");
  if (!fs.existsSync(venvPython)) {
    log("Creating Python virtual environment...");
    run(`python3 -m venv ${VENV_DIR}`, BACKEND_DIR);
  } else {
    log("Python venv already exists.");
  }
}

// ─── Frontend ─────────────────────────────────────────────────────────────────

function installFrontendDeps() {
  log("Installing frontend dependencies...");
  run("npm install --legacy-peer-deps", FRONTEND_DIR);
}

function buildFrontend() {
  if (SKIP_BUILD) {
    logWarn("Skipping frontend build (--skip-build flag).");
    const distDir = path.join(FRONTEND_DIR, "dist");
    if (!fs.existsSync(distDir)) {
      logError("frontend/dist does not exist. Cannot skip build on first run.");
      process.exit(1);
    }
    return;
  }
  log("Building production frontend...");
  run("npm run build", FRONTEND_DIR);
  const distDir = path.join(FRONTEND_DIR, "dist");
  if (!fs.existsSync(distDir)) {
    logError("Frontend build failed — frontend/dist was not created.");
    process.exit(1);
  }
  log("Frontend build complete.");
}

// ─── Backend dependencies ─────────────────────────────────────────────────────

function installBackendDeps() {
  log("Installing backend dependencies...");
  const pip = path.join(VENV_DIR, "bin", "pip");
  run(`${pip} install --upgrade pip`, BACKEND_DIR, { allowFail: true });
  run(`${pip} install -r requirements.txt`, BACKEND_DIR);
  run(`${pip} install gunicorn`, BACKEND_DIR);
}

// ─── Nginx ────────────────────────────────────────────────────────────────────

function writeNginxConfig() {
  const distDir = path.join(FRONTEND_DIR, "dist");

  const config = `# HRMS — auto-generated by start-vm.js — do not edit manually
server {
    listen 80;
    server_name ${VM_IP} localhost;

    root ${distDir};
    index index.html;

    # React client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to Gunicorn
    location /api {
        proxy_pass            http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header      Host              $host;
        proxy_set_header      X-Real-IP         $remote_addr;
        proxy_set_header      X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header      X-Forwarded-Proto $scheme;
        proxy_read_timeout    120s;
        proxy_connect_timeout 10s;
        proxy_send_timeout    120s;
        client_max_body_size  50M;
    }

    # Health endpoint
    location /health {
        proxy_pass         http://127.0.0.1:${BACKEND_PORT}/health;
        proxy_set_header   Host        $host;
        proxy_set_header   X-Real-IP   $remote_addr;
        access_log         off;
    }

    # Static asset caching
    location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # Gzip compression
    gzip            on;
    gzip_vary       on;
    gzip_proxied    any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types
        text/plain text/css text/xml text/javascript
        application/json application/javascript application/xml
        application/rss+xml font/truetype font/opentype
        application/vnd.ms-fontobject image/svg+xml;

    # Security headers
    add_header X-Frame-Options        "SAMEORIGIN"                   always;
    add_header X-Content-Type-Options "nosniff"                      always;
    add_header X-XSS-Protection       "1; mode=block"                always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
}
`;

  log(`Writing nginx config → ${NGINX_SITE}`);
  const tmpFile = path.join(os.tmpdir(), "hrms-nginx.conf");
  fs.writeFileSync(tmpFile, config, "utf8");

  run(`sudo cp ${tmpFile} ${NGINX_SITE}`);
  run(`sudo ln -sf ${NGINX_SITE} ${NGINX_ENABLED}`, ROOT, { allowFail: true });

  // Remove default site to avoid conflicts
  run(`sudo rm -f ${NGINX_DEFAULT}`, ROOT, { allowFail: true });

  run("sudo nginx -t");
  log("Nginx config validated successfully.");
}

function restartNginx() {
  log("Restarting Nginx...");
  run("sudo systemctl restart nginx");
  run("sudo systemctl enable nginx", ROOT, { allowFail: true });
}

// ─── Backend process ──────────────────────────────────────────────────────────

function startBackend() {
  const gunicorn  = path.join(VENV_DIR, "bin", "gunicorn");
  const accessLog = path.join(LOGS_DIR, "gunicorn-access.log");
  const errorLog  = path.join(LOGS_DIR, "gunicorn-error.log");

  if (!fs.existsSync(gunicorn)) {
    logError(`Gunicorn not found at ${gunicorn}. Run installBackendDeps first.`);
    process.exit(1);
  }

  log(`Starting Gunicorn — ${WORKERS} workers on 127.0.0.1:${BACKEND_PORT}...`);

  backendProcess = spawn(
    gunicorn,
    [
      "--workers",        String(WORKERS),
      "--bind",           `127.0.0.1:${BACKEND_PORT}`,
      "--timeout",        "120",
      "--keep-alive",     "5",
      "--max-requests",   "1000",
      "--max-requests-jitter", "50",
      "--access-logfile", accessLog,
      "--error-logfile",  errorLog,
      "--capture-output",
      "--pid",            PID_FILE,
      "--log-level",      "info",
      "app:app",
    ],
    {
      cwd:   BACKEND_DIR,
      stdio: "inherit",
    }
  );

  backendProcess.on("error", (err) => {
    logError(`Failed to start Gunicorn: ${err.message}`);
    process.exit(1);
  });

  backendProcess.on("close", (code) => {
    log(`Gunicorn exited with code ${code}.`);
    if (code !== 0 && restartCount < MAX_RESTARTS) {
      restartCount++;
      logWarn(`Auto-restarting backend (attempt ${restartCount}/${MAX_RESTARTS})...`);
      setTimeout(startBackend, RESTART_DELAY_MS);
    } else if (code !== 0) {
      logError(`Backend failed ${MAX_RESTARTS} times consecutively. Exiting.`);
      cleanup();
      process.exit(1);
    }
  });
}

// ─── Health check ─────────────────────────────────────────────────────────────

function waitForBackend(retries = 20, intervalMs = 2000) {
  return new Promise((resolve, reject) => {
    let attempt = 0;

    function check() {
      attempt++;
      log(`Health check ${attempt}/${retries}...`);

      const req = http.get(
        {
          hostname: "127.0.0.1",
          port:     BACKEND_PORT,
          path:     "/health",
          timeout:  3000,
        },
        (res) => {
          if (res.statusCode === 200) {
            log("Backend is healthy ✓");
            resolve();
          } else {
            retry(`HTTP ${res.statusCode}`);
          }
        }
      );

      req.on("error",   () => retry("connection refused"));
      req.on("timeout", () => { req.destroy(); retry("timeout"); });
    }

    function retry(reason) {
      if (attempt >= retries) {
        reject(
          new Error(
            `Backend did not become healthy after ${retries} attempts (last: ${reason}).`
          )
        );
        return;
      }
      setTimeout(check, intervalMs);
    }

    check();
  });
}

// ─── Status banner ────────────────────────────────────────────────────────────

function printStatus() {
  const bar = "═".repeat(50);
  console.log(`\n${bar}`);
  console.log("         HRMS PRODUCTION SERVER — ONLINE");
  console.log(`${bar}\n`);
  console.log(`  Frontend  →  http://${VM_IP}`);
  console.log(`  API       →  http://${VM_IP}/api`);
  console.log(`  Health    →  http://${VM_IP}/health`);
  console.log(`  Logs      →  ${LOGS_DIR}`);
  console.log(`  Workers   →  ${WORKERS} Gunicorn workers`);
  console.log(`\n${bar}\n`);
}

// ─── Graceful shutdown ────────────────────────────────────────────────────────

function cleanup() {
  if (backendProcess) {
    log("Sending SIGTERM to Gunicorn...");
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
  if (fs.existsSync(PID_FILE)) {
    fs.unlinkSync(PID_FILE);
  }
  if (logStream) {
    logStream.end();
  }
}

function shutdown(signal) {
  log(`Received ${signal} — graceful shutdown...`);
  cleanup();
  process.exit(0);
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  process.on("SIGINT",  () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("uncaughtException", (err) => {
    logError(`Uncaught exception: ${err.message}`);
    logError(err.stack || "");
    cleanup();
    process.exit(1);
  });
  process.on("unhandledRejection", (reason) => {
    logError(`Unhandled promise rejection: ${reason}`);
    cleanup();
    process.exit(1);
  });

  try {
    ensureLogsDir();
    log("=== HRMS VM Production Startup ===");
    log(`Node ${process.version} | ${os.platform()} ${os.arch()} | CPUs: ${os.cpus().length}`);

    preflight();
    ensureBranch();
    ensureVenv();
    installFrontendDeps();
    installBackendDeps();
    buildFrontend();
    writeNginxConfig();
    startBackend();

    log("Waiting for backend to become healthy...");
    await waitForBackend();

    restartNginx();
    printStatus();
  } catch (err) {
    logError(`Startup failed: ${err.message}`);
    cleanup();
    process.exit(1);
  }
}

main();
