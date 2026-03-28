#!/bin/bash
# ============================================================
# Trading Agent Watchdog
# ============================================================
# Ensures the agent is running during market hours.
# Restarts it if crashed. Run via cron:
#
#   crontab -e
#   # Check every 5 min, Mon-Fri, 09:25-16:05 ET
#   */5 9-16 * * 1-5 /path/to/trading-agent/watchdog.sh >> /path/to/trading-agent/logs/watchdog.log 2>&1
#
# Or for IST (ET+7):
#   */5 16-23 * * 1-5 /path/to/trading-agent/watchdog.sh >> /path/to/trading-agent/logs/watchdog.log 2>&1
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PIDFILE="$SCRIPT_DIR/logs/agent.pid"
LOGDIR="$SCRIPT_DIR/logs"

mkdir -p "$LOGDIR"

echo "[$TIMESTAMP] Watchdog check..."

# Check if agent process is running
is_running() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            return 0  # Running
        fi
    fi
    # Also check by process name
    if pgrep -f "python3 -m agent.main" > /dev/null 2>&1; then
        return 0  # Running
    fi
    return 1  # Not running
}

# Check if we're in market hours (ET)
is_market_hours() {
    # Get current hour in ET
    ET_HOUR=$(TZ='US/Eastern' date '+%H' | sed 's/^0//')
    ET_MIN=$(TZ='US/Eastern' date '+%M' | sed 's/^0//')
    ET_DOW=$(TZ='US/Eastern' date '+%u')  # 1=Mon, 7=Sun

    # Skip weekends
    if [ "$ET_DOW" -ge 6 ]; then
        echo "[$TIMESTAMP] Weekend — skipping"
        return 1
    fi

    # Market hours: 09:25 ET to 16:05 ET (start 5 min early, end 5 min late)
    ET_MINUTES=$((ET_HOUR * 60 + ET_MIN))
    MARKET_START=$((9 * 60 + 25))   # 09:25 ET
    MARKET_END=$((16 * 60 + 5))     # 16:05 ET

    if [ "$ET_MINUTES" -ge "$MARKET_START" ] && [ "$ET_MINUTES" -le "$MARKET_END" ]; then
        return 0  # In market hours
    fi

    echo "[$TIMESTAMP] Outside market hours (ET: ${ET_HOUR}:${ET_MIN}) — skipping"
    return 1
}

# Main logic
if ! is_market_hours; then
    exit 0
fi

if is_running; then
    echo "[$TIMESTAMP] Agent is running — OK"
    exit 0
fi

echo "[$TIMESTAMP] ⚠️ Agent NOT running! Restarting..."

# Activate venv if exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Start agent in background
nohup python3 -m agent.main >> "$LOGDIR/agent_$(TZ='US/Eastern' date '+%Y-%m-%d').log" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PIDFILE"

echo "[$TIMESTAMP] ✅ Agent restarted with PID $NEW_PID"

# Send Telegram notification about restart
if [ -f "$SCRIPT_DIR/.env" ]; then
    source <(grep -E '^(TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)=' "$SCRIPT_DIR/.env")
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        MSG="🔄 <b>WATCHDOG RESTART</b>%0A%0AAgent was down and has been restarted.%0APID: $NEW_PID%0ATime: $TIMESTAMP"
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${TELEGRAM_CHAT_ID}&text=${MSG}&parse_mode=HTML" > /dev/null 2>&1
    fi
fi
