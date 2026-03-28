#!/bin/bash
# ============================================================
# restart.sh — Nightly restart after Claude Coach review
#
# Called by crontab every night at 00:05 IST (after the
# 23:30 IST daily review).  Stops dashboard + agent cleanly
# and brings them back fresh for the next trading day.
#
# Cron entry (auto-set):
#   5 0 * * * /Users/galzituni/trading-agent/restart.sh
# ============================================================

BASE="/Users/galzituni/trading-agent"
PYTHON="$BASE/venv/bin/python3"
LOGS="$BASE/logs"
LOG="$LOGS/restart.log"

# ── Helpers ─────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

stop_by_pid_file() {
    local name=$1
    local pid_file="$LOGS/${name}.pid"

    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            log "Stopped $name (PID $pid)"
        else
            log "$name PID $pid was not running"
        fi
        rm -f "$pid_file"
    else
        log "No PID file for $name"
    fi
}

# ── Start ────────────────────────────────────────────────────
log "═══════════════════════════════════════════"
log "  Nightly restart — $(date '+%A %Y-%m-%d')"
log "═══════════════════════════════════════════"

# ── Stop dashboard + agent (via PID files) ──────────────────
stop_by_pid_file "dashboard"
stop_by_pid_file "agent"

# ── Fallback: kill by port / process name ───────────────────
DASH_LEFTOVER=$(lsof -ti :5555 2>/dev/null)
if [ -n "$DASH_LEFTOVER" ]; then
    kill $DASH_LEFTOVER 2>/dev/null
    log "Killed leftover dashboard (PID $DASH_LEFTOVER)"
fi

AGENT_LEFTOVER=$(pgrep -f "python.*agent\.main" 2>/dev/null)
if [ -n "$AGENT_LEFTOVER" ]; then
    kill $AGENT_LEFTOVER 2>/dev/null
    log "Killed leftover agent (PIDs $AGENT_LEFTOVER)"
fi

sleep 3  # clean shutdown window

# ── Restart dashboard ────────────────────────────────────────
cd "$BASE" || { log "ERROR: cannot cd to $BASE"; exit 1; }

nohup "$PYTHON" -m agent.dashboard --port 5555 \
    >> "$LOGS/dashboard.log" 2>&1 &
DASH_PID=$!
echo "$DASH_PID" > "$LOGS/dashboard.pid"
log "Dashboard restarted (PID $DASH_PID)"

# ── Restart trading agent ────────────────────────────────────
nohup "$PYTHON" -m agent.main \
    >> "$LOGS/agent.log" 2>&1 &
AGENT_PID=$!
echo "$AGENT_PID" > "$LOGS/agent.pid"
log "Trading agent restarted (PID $AGENT_PID)"

# ── caffeinate: keep Mac awake ───────────────────────────────
CAF_FILE="$LOGS/caffeinate.pid"
CAF_RUNNING=false
if [ -f "$CAF_FILE" ]; then
    CAF_PID=$(cat "$CAF_FILE")
    kill -0 "$CAF_PID" 2>/dev/null && CAF_RUNNING=true
fi

if [ "$CAF_RUNNING" = false ]; then
    nohup caffeinate -i >> "$LOGS/restart.log" 2>&1 &
    echo $! > "$CAF_FILE"
    log "caffeinate restarted (PID $!)"
else
    log "caffeinate already running (PID $CAF_PID)"
fi

log "═══ Restart complete ═══"
