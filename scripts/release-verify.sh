#!/usr/bin/env bash
# Release verification — no secrets. Run from the repository root.
#   scripts/release-verify.sh pre-deploy   # processes gone + alembic current == heads
#   scripts/release-verify.sh post-start   # /health /ready + alembic current == heads
#   scripts/release-verify.sh processes    # fail if old writers still running
#   scripts/release-verify.sh db-sessions  # read-only pg_stat_activity report; fail on unknown writers
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/apps/backend"
PHASE="${1:-all}"
HEALTH_URL="${HCIP_HEALTH_URL:-http://127.0.0.1:3000/health}"
READY_URL="${HCIP_READY_URL:-http://127.0.0.1:3000/ready}"

fail() {
  echo "release-verify FAIL: $*" >&2
  exit 1
}

ok() {
  echo "release-verify OK: $*"
}

process_matches() {
  # Match real app processes only. Ignore this script, pgrep, and command-line wrappers
  # whose argv merely mentions these tokens.
  ps -eo pid,comm,args --no-headers 2>/dev/null | awk -v self="$$" -v parent="$PPID" '
    $1 == self || $1 == parent { next }
    $2 ~ /^(gunicorn|gunicorn3)$/ { print; next }
    $3 ~ /(release-verify|cursorsandbox|cursor-server)/ { next }
    $0 ~ /python[0-9.]* -m app\.domains\.integrations\.(scheduler|worker)/ { print; next }
    $0 ~ /python[0-9.]* wsgi\.py/ { print; next }
    $0 ~ /gunicorn[0-9.]* .*-c gunicorn\.conf\.py/ { print; next }
  '
}

check_processes_stopped() {
  local hits
  hits="$(process_matches)"
  if [[ -n "${hits//[[:space:]]/}" ]]; then
    echo "$hits" >&2
    fail "stale processes still running (gunicorn / scheduler / outbox / wsgi.py)"
  fi
  ok "no gunicorn/scheduler/outbox/wsgi.py processes"
}

alembic_bin() {
  if [[ -x "$BACKEND/venv/bin/alembic" ]]; then
    echo "$BACKEND/venv/bin/alembic"
    return
  fi
  command -v alembic || fail "alembic not found (apps/backend/venv or PATH)"
}

parse_alembic_revision() {
  # Skip SQLAlchemy chatter; take the last revision-like token.
  grep -Eo '20[0-9]{6}_[A-Za-z0-9_]+|[0-9a-f]{12}' | tail -1
}

check_alembic_at_head() {
  local current heads alembic
  [[ -d "$BACKEND" ]] || fail "backend directory missing: $BACKEND"
  alembic="$(alembic_bin)"
  cd "$BACKEND"
  current="$("$alembic" current 2>/dev/null | parse_alembic_revision)"
  heads="$("$alembic" heads 2>/dev/null | parse_alembic_revision)"
  [[ -n "$current" ]] || fail "alembic current returned empty"
  [[ -n "$heads" ]] || fail "alembic heads returned empty"
  if [[ "$current" != "$heads" ]]; then
    fail "alembic current ($current) != heads ($heads)"
  fi
  ok "alembic current == heads ($current)"
}

python_bin() {
  if [[ -x "$BACKEND/venv/bin/python" ]]; then
    echo "$BACKEND/venv/bin/python"
    return
  fi
  command -v python3 || fail "python3 not found (apps/backend/venv or PATH)"
}

check_db_sessions() {
  local py
  py="$(python_bin)"
  "$py" "$ROOT/scripts/inspect_db_sessions.py" "$@"
}

check_health_ready() {
  local health_code ready_code
  health_code="$(curl -sS -o /tmp/hcip-health.json -w '%{http_code}' --max-time 5 "$HEALTH_URL" || true)"
  ready_code="$(curl -sS -o /tmp/hcip-ready.json -w '%{http_code}' --max-time 5 "$READY_URL" || true)"
  [[ "$health_code" == "200" ]] || fail "/health returned ${health_code:-none}"
  [[ "$ready_code" == "200" ]] || fail "/ready returned ${ready_code:-none}"
  ok "/health and /ready are 200"
}

case "$PHASE" in
  processes)
    check_processes_stopped
    ;;
  pre-deploy)
    check_processes_stopped
    check_alembic_at_head
    ;;
  post-start)
    check_alembic_at_head
    check_health_ready
    ;;
  db-sessions)
    shift || true
    check_db_sessions "$@"
    ;;
  all)
    echo "usage: $0 {pre-deploy|post-start|processes|db-sessions}" >&2
    echo "Running alembic current == heads only." >&2
    check_alembic_at_head
    ;;
  *)
    fail "unknown phase '$PHASE' (use pre-deploy | post-start | processes | db-sessions)"
    ;;
esac
