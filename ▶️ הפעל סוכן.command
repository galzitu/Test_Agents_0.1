#!/bin/bash
# לחץ פעמיים על הקובץ הזה כדי להפעיל את הסוכן + דשבורד

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs dir
mkdir -p logs

# Check if agent already running
AGENT_RUNNING=false
if [ -f "logs/agent.pid" ]; then
    PID=$(cat logs/agent.pid)
    if kill -0 "$PID" 2>/dev/null; then
        AGENT_RUNNING=true
        echo "✅ הסוכן כבר רץ (PID: $PID)"
    fi
fi

# Check if dashboard already running
DASH_RUNNING=false
if [ -f "logs/dashboard.pid" ]; then
    PID=$(cat logs/dashboard.pid)
    if kill -0 "$PID" 2>/dev/null; then
        DASH_RUNNING=true
        echo "✅ הדשבורד כבר רץ (PID: $PID)"
    fi
fi

# If both running, just show status
if $AGENT_RUNNING && $DASH_RUNNING; then
    echo ""
    echo "🟢 הכל רץ! פתח http://localhost:5555 בדפדפן."
    echo ""
    echo "כדי לעצור: לחץ פעמיים על '⏹️ עצור סוכן.command'"
    read -p "לחץ Enter לסגירה..."
    exit 0
fi

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Prevent Mac from sleeping while agent runs
caffeinate -i -w $$ &
CAFFEINATE_PID=$!
echo $CAFFEINATE_PID > logs/caffeinate.pid

# Start agent in background (if not already running)
if ! $AGENT_RUNNING; then
    echo "🚀 מפעיל סוכן מסחר..."
    nohup python3 -m agent.main > logs/agent.log 2>&1 &
    echo $! > logs/agent.pid
    echo "   סוכן PID: $(cat logs/agent.pid)"
fi

# Start dashboard in background (if not already running)
if ! $DASH_RUNNING; then
    echo "📊 מפעיל דשבורד..."
    nohup python3 -m agent.dashboard --port 5555 > logs/dashboard.log 2>&1 &
    echo $! > logs/dashboard.pid
    echo "   דשבורד PID: $(cat logs/dashboard.pid)"
fi

# Wait a moment for dashboard to start
sleep 3

# Open browser
open "http://localhost:5555"

echo ""
echo "✅ הכל רץ!"
echo "🖥  דשבורד: http://localhost:5555"
echo "☕ מניעת שינה פעילה — המחשב לא ילך לישון"
echo ""
echo "📋 לוגים:"
echo "   סוכן:   $SCRIPT_DIR/logs/agent.log"
echo "   דשבורד: $SCRIPT_DIR/logs/dashboard.log"
echo ""
echo "אפשר לסגור את החלון הזה - הכל ימשיך לרוץ ברקע."
echo ""
read -p "לחץ Enter לסגירה..."
