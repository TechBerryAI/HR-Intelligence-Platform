#!/usr/bin/env node
/**
 * HR Portal - Frontend Production Starter
 *
 * Runs React frontend without port using NGINX.
 * Browser → http://localhost
 *
 * Steps:
 * 1. Check environment
 * 2. Install frontend dependencies
 * 3. Build React
 * 4. Configure NGINX
 * 5. Restart NGINX
 * 6. Open browser
 */

const fs = require("fs");
const path = require("path");
const { spawn, execSync } = require("child_process");

const ROOT = path.resolve(__dirname);
const FRONTEND_DIR = path.join(ROOT, "frontend");
const DIST_DIR = path.join(FRONTEND_DIR, "dist");

const NGINX_SITE = "/etc/nginx/sites-available/hr-portal";
const NGINX_ENABLED = "/etc/nginx/sites-enabled/hr-portal";

const URL = "http://localhost";

function timestamp() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

function log(msg, type = "info") {
  const prefix =
    type === "err" ? "[ERROR]" :
    type === "warn" ? "[WARN]" :
    "[start]";
  console.log(`${prefix} [${timestamp()}] ${msg}`);
}

function run(cmd, cwd = ROOT) {
  log(`$ ${cmd}`);
  execSync(cmd, { cwd, stdio: "inherit", shell: true });
}

function checkEnv() {
  log("Checking environment");
  try {
    const nodeVer = execSync("node --version").toString().trim();
    log("Node: " + nodeVer);
  } catch {
    log("Node.js not installed", "err");
    process.exit(1);
  }

  try {
    const nginxVer = execSync("nginx -v 2>&1").toString().trim();
    log(nginxVer);
  } catch {
    log("NGINX not installed", "err");
    process.exit(1);
  }

  log("Environment OK");
}

function installFrontend() {
  log("Installing frontend dependencies");

  const nodeModules = path.join(FRONTEND_DIR, "node_modules");

  if (!fs.existsSync(nodeModules)) {
    run("npm install", FRONTEND_DIR);
  } else {
    log("node_modules already exists");
  }
}

function buildFrontend() {
  log("Building React production build");

  run("npm run build", FRONTEND_DIR);

  if (!fs.existsSync(DIST_DIR)) {
    log("Build failed: dist folder missing", "err");
    process.exit(1);
  }

  log("Frontend build complete");
}

function writeNginxConfig() {
  log("Configuring NGINX");

  const config = `
server {
    listen 80;
    server_name localhost;
    root ${DIST_DIR};
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \\.(js|css|png|jpg|jpeg|gif|svg|ico)$ {
        expires 1y;
        add_header Cache-Control "public";
    }
}
`;

  const tmp = "/tmp/hr-portal-nginx.conf";
  fs.writeFileSync(tmp, config);

  // Ensure NGINX directories exist
  run("sudo mkdir -p /etc/nginx/sites-available");
  run("sudo mkdir -p /etc/nginx/sites-enabled");

  run(`sudo cp ${tmp} ${NGINX_SITE}`);
  run(`sudo ln -sf ${NGINX_SITE} ${NGINX_ENABLED}`);

  run("sudo nginx -t");
}

function restartNginx() {
  log("Restarting NGINX");
  run("sudo systemctl restart nginx");
}

function openBrowser() {
  const cmd =
    process.platform === "win32"
      ? "start"
      : process.platform === "darwin"
      ? "open"
      : "xdg-open";

  spawn(cmd, [URL], { stdio: "ignore", shell: true });
  log("Opening browser: " + URL);
}

function shutdown() {
  log("Shutdown requested");
  // NGINX will keep running; optionally stop it:
  // try { run("sudo systemctl stop nginx"); } catch {}
  process.exit(0);
}

async function main() {
  console.log("\n==================================");
  console.log("   HR Portal Frontend Starter");
  console.log("==================================\n");

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  checkEnv();
  installFrontend();
  buildFrontend();
  writeNginxConfig();
  restartNginx();
  openBrowser();

  console.log("\nFrontend running at:");
  console.log(URL);
  console.log("\nPress Ctrl+C to stop\n");
}

main().catch((err) => {
  log(err.message || err, "err");
  process.exit(1);
});