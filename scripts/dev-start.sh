#!/usr/bin/env bash
#
# Start the app with the Node version this repo pins in .nvmrc.
#
# Why this exists: a non-interactive shell (IDE task runner, `wsl -- bash -lc`,
# CI step) never reaches the nvm block in ~/.bashrc — Ubuntu's .bashrc returns
# early when the shell is not interactive. Such a shell resolves /usr/bin/node,
# which may be an older apt-installed Node than .nvmrc requires, and start.js
# then refuses to run. Loading nvm here makes the pinned version apply the same
# way it does in a developer's terminal.
#
# Falls through harmlessly when nvm is not installed: start.js still checks the
# Node major and reports what to do.
set -u

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

if command -v nvm >/dev/null 2>&1; then
  # `nvm use` with no argument reads .nvmrc. Install it on first run if missing.
  nvm use >/dev/null 2>&1 || nvm install >/dev/null 2>&1 || true
fi

echo "[dev-start] node: $(node -v 2>/dev/null || echo 'not found')"
exec npm run start
