#!/usr/bin/env node

/**
 * HRMS PRODUCTION VM START SCRIPT
 *
 * Production architecture:
 *
 * Browser
 *    ↓
 * NGINX (Port 80)
 *    ↓
 * React Build (frontend/dist)
 *    ↓
 * Flask Backend (Gunicorn :3000)
 *    ↓
 * PostgreSQL (192.168.1.53)
 *
 * Usage:
 *    node start-vm.js
 */

const { execSync, spawn } = require("child_process");
const path = require("path");

const ROOT = __dirname;
const FRONTEND_DIR = path.join(ROOT, "frontend");
const BACKEND_DIR = path.join(ROOT, "backend");

const VM_IP = "192.168.1.19";
const BACKEND_PORT = 3000;

let backendProcess = null;

function log(msg) {
  const t = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`[HRMS ${t}] ${msg}`);
}

function run(cmd, cwd = ROOT) {
  log(`$ ${cmd}`);
  execSync(cmd, { cwd, stdio: "inherit" });
}

function ensureBranch() {
  log("Switching to development branch...");
  run("git fetch origin");
  run("git checkout development");
  run("git pull origin development");
}

function installFrontendDeps() {
  log("Checking frontend dependencies...");

  try {
    run("npm install", FRONTEND_DIR);
  } catch (err) {
    log("Frontend dependency install failed");
  }
}

function buildFrontend() {
  log("Building production frontend...");
  run("npm run build", FRONTEND_DIR);
}

function installBackendDeps() {
  log("Installing backend dependencies...");

  const pip = path.join(BACKEND_DIR, "venv", "bin", "pip");

  try {
    run(`${pip} install -r requirements.txt`, BACKEND_DIR);
  } catch (err) {
    log("Backend dependency install failed");
  }
}

function ensureGunicorn() {
  const pip = path.join(BACKEND_DIR, "venv", "bin", "pip");

  log("Ensuring gunicorn installed...");

  try {
    run(`${pip} install gunicorn`, BACKEND_DIR);
  } catch (err) {
    log("Gunicorn installation failed");
  }
}

function startBackend() {
  log("Starting backend with Gunicorn...");

  const gunicorn = path.join(
    BACKEND_DIR,
    "venv",
    "bin",
    "gunicorn"
  );

  backendProcess = spawn(
    gunicorn,
    [
      "-w",
      "4",
      "-b",
      `127.0.0.1:${BACKEND_PORT}`,
      "app:app"
    ],
    {
      cwd: BACKEND_DIR,
      stdio: "inherit"
    }
  );

  backendProcess.on("close", (code) => {
    log(`Backend stopped with code ${code}`);
  });
}

function restartNginx() {
  log("Reloading Nginx...");
  run("sudo systemctl restart nginx");
}

function printStatus() {
  console.log("\n======================================");
  console.log("        HRMS PRODUCTION SERVER");
  console.log("======================================\n");

  console.log(`Frontend : http://${VM_IP}`);
  console.log(`Backend  : http://${VM_IP}/api`);
  console.log(`Health   : http://${VM_IP}/health\n`);
}

function shutdown() {
  log("Stopping backend...");
  if (backendProcess) backendProcess.kill("SIGTERM");
  process.exit();
}

function main() {
  ensureBranch();
  installFrontendDeps();
  installBackendDeps();
  ensureGunicorn();
  buildFrontend();
  startBackend();
  restartNginx();
  printStatus();

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main();