#!/bin/bash
# לחץ פעמיים על הקובץ הזה כדי לפתוח את הדשבורד

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "📊 מפעיל דשבורד..."
echo "פתח בדפדפן: http://localhost:5555"
echo ""

# Open browser automatically
sleep 1
open "http://localhost:5555"

python3 -m agent.dashboard --port 5555
