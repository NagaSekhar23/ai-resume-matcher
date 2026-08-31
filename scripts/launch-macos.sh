#!/bin/zsh
set -u

APP_NAME="AI Resume Matcher"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="$LOG_DIR/pids"
BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:3000"
OLLAMA_URL="http://localhost:11434"
OLLAMA_MODEL="mistral:latest"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
OLLAMA_LOG="$LOG_DIR/ollama.log"
LAUNCHER_LOG="$LOG_DIR/launcher.log"
LAUNCHD_DOMAIN="gui/$(id -u)"
BACKEND_LABEL="com.local.ai-resume-matcher.backend"
FRONTEND_LABEL="com.local.ai-resume-matcher.frontend"
LAUNCHD_PLIST_DIR="$LOG_DIR/launchd"
BACKEND_PLIST="$LAUNCHD_PLIST_DIR/$BACKEND_LABEL.plist"
FRONTEND_PLIST="$LAUNCHD_PLIST_DIR/$FRONTEND_LABEL.plist"

mkdir -p "$LOG_DIR" "$PID_DIR" "$LAUNCHD_PLIST_DIR" "$ROOT_DIR/data/db" "$ROOT_DIR/data/uploads" "$ROOT_DIR/data/cache" "$ROOT_DIR/data/embeddings"
touch "$BACKEND_LOG" "$FRONTEND_LOG" "$OLLAMA_LOG" "$LAUNCHER_LOG"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd "$ROOT_DIR" || exit 1

log() {
  local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
  echo "$message" | tee -a "$LAUNCHER_LOG"
}

fail() {
  log "ERROR: $1"
  osascript -e "display alert \"$APP_NAME startup failed\" message \"$1\n\nSee logs in $LOG_DIR.\" as critical" >/dev/null 2>&1 || true
  exit 1
}

is_http_ok() {
  /usr/bin/curl -fsS --max-time 2 "$1" >/dev/null 2>&1
}

listener_pid_for_port() {
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

clear_stale_next_dev_cache() {
  local next_dev_dir="$FRONTEND_DIR/.next/dev"
  if [[ -d "$next_dev_dir" ]]; then
    log "Clearing stale Next.js dev cache at $next_dev_dir."
    rm -rf "$next_dev_dir"
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local timeout_seconds="$3"
  local started_at=$(date +%s)
  while true; do
    if is_http_ok "$url"; then
      log "$label is healthy at $url"
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_seconds )); then
      return 1
    fi
    sleep 1
  done
}

require_file() {
  [[ -e "$1" ]] || fail "$2"
}

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g' -e "s/'/\&apos;/g"
}

write_launch_agent_plists() {
  local backend_script="$(xml_escape "$ROOT_DIR/scripts/start-backend-macos.sh")"
  local frontend_script="$(xml_escape "$ROOT_DIR/scripts/start-frontend-macos.sh")"
  local root_dir="$(xml_escape "$ROOT_DIR")"
  local frontend_dir="$(xml_escape "$FRONTEND_DIR")"
  local backend_log="$(xml_escape "$BACKEND_LOG")"
  local frontend_log="$(xml_escape "$FRONTEND_LOG")"
  cat > "$BACKEND_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$BACKEND_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$backend_script</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$root_dir</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$backend_log</string>
  <key>StandardErrorPath</key>
  <string>$backend_log</string>
</dict>
</plist>
PLIST
  cat > "$FRONTEND_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$FRONTEND_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$frontend_script</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$frontend_dir</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$frontend_log</string>
  <key>StandardErrorPath</key>
  <string>$frontend_log</string>
</dict>
</plist>
PLIST
}

start_launch_agent() {
  local label="$1"
  local plist="$2"
  local display_name="$3"
  require_file "$plist" "$display_name launch agent plist is missing."
  if launchctl print "$LAUNCHD_DOMAIN/$label" >/dev/null 2>&1; then
    log "$display_name launch agent is loaded but service is not healthy; unloading stale agent."
    launchctl bootout "$LAUNCHD_DOMAIN/$label" >/dev/null 2>&1 || true
    sleep 1
  fi
  log "Loading $display_name launch agent."
  launchctl bootstrap "$LAUNCHD_DOMAIN" "$plist" >/dev/null 2>&1 || fail "Could not load $display_name launch agent. Check $LAUNCHER_LOG."
}

ensure_ollama() {
  if is_http_ok "$OLLAMA_URL/api/tags"; then
    log "Ollama is already running."
  else
    command -v ollama >/dev/null 2>&1 || fail "Ollama was not found in PATH. Install Ollama or start it manually."
    log "Starting Ollama..."
    nohup ollama serve >> "$OLLAMA_LOG" 2>&1 &!
    echo $! > "$PID_DIR/ollama.pid"
    wait_for_http "$OLLAMA_URL/api/tags" "Ollama" 30 || fail "Ollama did not become reachable at $OLLAMA_URL."
  fi

  if ! /usr/bin/curl -fsS --max-time 5 "$OLLAMA_URL/api/tags" | /usr/bin/grep -q '"name":"mistral:latest"'; then
    fail "Ollama is running, but model mistral:latest was not detected."
  fi
  log "Ollama model detected: $OLLAMA_MODEL"
}

ensure_backend() {
  if is_http_ok "$BACKEND_URL/api/health"; then
    log "Backend is already running."
    return 0
  fi
  require_file "$ROOT_DIR/.venv/bin/python" "Python virtual environment is missing. Run backend setup from README first."
  log "Starting backend..."
  start_launch_agent "$BACKEND_LABEL" "$BACKEND_PLIST" "Backend"
  wait_for_http "$BACKEND_URL/api/health" "Backend" 45 || fail "Backend did not become healthy. Check $BACKEND_LOG."
  local listener_pid="$(listener_pid_for_port 8000)"
  [[ -n "$listener_pid" ]] || fail "Backend health passed but no process is listening on port 8000. Check $BACKEND_LOG."
  echo "$listener_pid" > "$PID_DIR/backend.pid"
}

configure_backend() {
  /usr/bin/curl -fsS --max-time 5 -X PUT "$BACKEND_URL/api/settings" \
    -H 'Content-Type: application/json' \
    -d '{"ollama_url":"http://localhost:11434","ollama_model":"mistral:latest"}' >/dev/null \
    || fail "Backend is healthy, but saving Ollama settings failed."
  log "Backend configured for $OLLAMA_URL with $OLLAMA_MODEL."
}

ensure_frontend() {
  if is_http_ok "$FRONTEND_URL/"; then
    sleep 2
    is_http_ok "$FRONTEND_URL/" || fail "Frontend responded once but did not remain healthy. Check $FRONTEND_LOG."
    local listener_pid="$(listener_pid_for_port 3000)"
    [[ -n "$listener_pid" ]] || fail "Frontend responded but no process is listening on port 3000."
    echo "$listener_pid" > "$PID_DIR/frontend.pid"
    log "Frontend is already running."
    return 0
  fi
  require_file "$FRONTEND_DIR/package.json" "Frontend package.json is missing."
  require_file "$FRONTEND_DIR/node_modules/.package-lock.json" "Frontend dependencies are missing. Run npm install in frontend first."
  clear_stale_next_dev_cache
  log "Starting frontend..."
  start_launch_agent "$FRONTEND_LABEL" "$FRONTEND_PLIST" "Frontend"
  wait_for_http "$FRONTEND_URL/" "Frontend" 60 || fail "Frontend did not become reachable. Check $FRONTEND_LOG."
  sleep 5
  is_http_ok "$FRONTEND_URL/" || fail "Frontend became unhealthy after initial startup. Check $FRONTEND_LOG."
  local listener_pid="$(listener_pid_for_port 3000)"
  [[ -n "$listener_pid" ]] || fail "Frontend health passed but no process is listening on port 3000. Check $FRONTEND_LOG."
  echo "$listener_pid" > "$PID_DIR/frontend.pid"
  log "Frontend remained healthy on port 3000."
}

main() {
  log "Launching $APP_NAME from $ROOT_DIR"
  write_launch_agent_plists
  ensure_ollama
  ensure_backend
  configure_backend
  ensure_frontend
  if [[ "${OPEN_BROWSER:-1}" == "1" ]]; then
    local brave_app="/Applications/Brave Browser.app"
    if [[ ! -d "$brave_app" ]]; then
      brave_app="$(mdfind 'kMDItemCFBundleIdentifier == "com.brave.Browser"' 2>/dev/null | head -1)"
    fi
    [[ -n "$brave_app" && -d "$brave_app" ]] || fail "Brave Browser was not found. Install Brave Browser or place it in /Applications/Brave Browser.app."
    log "Opening $FRONTEND_URL in Brave at $brave_app"
    open -a "$brave_app" "$FRONTEND_URL" >/dev/null 2>&1 || fail "Could not open Brave Browser automatically. Open $FRONTEND_URL in Brave manually."
  else
    log "OPEN_BROWSER=0; browser open skipped after successful health checks."
  fi
  log "$APP_NAME is ready."
  osascript -e "display notification \"Ready at $FRONTEND_URL\" with title \"$APP_NAME\"" >/dev/null 2>&1 || true
}

main "$@"
