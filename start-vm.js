#!/usr/bin/env node

/**
 * HRMS VM START SCRIPT
 * Starts backend + frontend for VM testing environment
 */

const { spawn } = require("child_process");
const path = require("path");

const ROOT = __dirname;
const BACKEND_DIR = path.join(ROOT, "backend");
const FRONTEND_DIR = path.join(ROOT, "frontend");

const PYTHON = path.join(BACKEND_DIR, "venv/bin/python");

let backendProcess = null;
let frontendProcess = null;

function log(msg) {
  const t = new Date().toISOString().replace("T", " ").slice(0, 19);
  console.log(`[HRMS ${t}] ${msg}`);
}

function startBackend() {
  log("Starting backend server...");

  backendProcess = spawn(PYTHON, ["app.py"], {
    cwd: BACKEND_DIR,
    stdio: "inherit",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });

  backendProcess.on("close", (code) => {
    log(`Backend stopped with code ${code}`);
  });
}

function startFrontend() {
  log("Starting frontend (Vite)...");

  frontendProcess = spawn("npm", ["run", "dev", "--", "--host", "0.0.0.0"], {
    cwd: FRONTEND_DIR,
    stdio: "inherit",
    shell: true,
  });

  frontendProcess.on("close", (code) => {
    log(`Frontend stopped with code ${code}`);
  });
}

function shutdown() {
  log("Stopping services...");

  if (backendProcess) backendProcess.kill("SIGTERM");
  if (frontendProcess) frontendProcess.kill("SIGTERM");

  process.exit();
}

function main() {
  console.log("\n======================================");
  console.log("        HRMS VM START SCRIPT");
  console.log("======================================\n");

  startBackend();
  startFrontend();

  console.log("\nServices started:");
  console.log("Backend:  http://192.168.1.19:3000");
  console.log("Frontend: http://192.168.1.19:5173\n");

  console.log("Press Ctrl+C to stop.\n");

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main();