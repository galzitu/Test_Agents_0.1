#!/bin/bash
# לחץ פעמיים על הקובץ הזה כדי לעצור את הסוכן + דשבורד

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

STOPPED=false

# Stop agent
if [ -f "logs/agent.pid" ]; then
    PID=$(cat logs/agent.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "⏹️ סוכן נעצר (PID: $PID)"
        STOPPED=true
    fi
    rm -f logs/agent.pid
fi

# Stop dashboard
if [ -f "logs/dashboard.pid" ]; then
    PID=$(cat logs/dashboard.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "⏹️ דשבורד נעצר (PID: $PID)"
        STOPPED=true
    fi
    rm -f logs/dashboard.pid
fi

# Stop caffeinate (allow sleep again)
if [ -f "logs/caffeinate.pid" ]; then
    kill $(cat logs/caffeinate.pid) 2>/dev/null
    rm -f logs/caffeinate.pid
    echo "😴 מניעת שינה בוטלה — המחשב יכול לישון שוב"
fi

if ! $STOPPED; then
    echo "⚠️ לא נמצאו תהליכים רצים"
fi

echo ""
read -p "לחץ Enter לסגירה..."
