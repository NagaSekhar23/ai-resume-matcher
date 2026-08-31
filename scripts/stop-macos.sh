#!/bin/zsh
set -u
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="$LOG_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"
LOG_FILE="$LOG_DIR/launcher.log"
LAUNCHD_DOMAIN="gui/$(id -u)"
BACKEND_LABEL="com.local.ai-resume-matcher.backend"
FRONTEND_LABEL="com.local.ai-resume-matcher.frontend"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

stop_launch_agent() {
  local label="$1"
  local display_name="$2"
  if launchctl print "$LAUNCHD_DOMAIN/$label" >/dev/null 2>&1; then
    log "Unloading $display_name launch agent."
    launchctl bootout "$LAUNCHD_DOMAIN/$label" >/dev/null 2>&1 || true
  else
    log "$display_name launch agent is not loaded."
  fi
}

stop_pid_file() {
  local label="$1"
  local file="$2"
  if [[ -f "$file" ]]; then
    local pid="$(cat "$file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      log "Stopping $label PID $pid"
      kill "$pid" >/dev/null 2>&1 || true
    else
      log "$label PID file exists, but process is not running."
    fi
    rm -f "$file"
  else
    log "No launcher-managed $label PID file found."
  fi
}

stop_port_process() {
  local label="$1"
  local port="$2"
  local pid="$(lsof -tiTCP:$port -sTCP:LISTEN 2>/dev/null | head -1)"
  if [[ -n "$pid" ]]; then
    log "Stopping $label on port $port, PID $pid"
    kill "$pid" >/dev/null 2>&1 || true
  else
    log "$label is not listening on port $port."
  fi
}

stop_launch_agent "$BACKEND_LABEL" "backend"
stop_launch_agent "$FRONTEND_LABEL" "frontend"
stop_pid_file "backend" "$PID_DIR/backend.pid"
stop_pid_file "frontend" "$PID_DIR/frontend.pid"
stop_port_process "backend" 8000
stop_port_process "frontend" 3000
log "Application stop requested. Ollama is left running intentionally."
