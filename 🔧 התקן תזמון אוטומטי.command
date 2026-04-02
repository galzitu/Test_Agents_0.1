#!/bin/bash
# ============================================================
# התקנת תזמון אוטומטי — הסוכן יידלק כל יום ב-16:00 IST
# לחץ פעמיים על הקובץ הזה פעם אחת כדי להתקין
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
USERNAME=$(whoami)
PLIST_NAME="com.trading-agent.autostart"
PLIST_SRC="$SCRIPT_DIR/com.trading-agent.autostart.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo "╔════════════════════════════════════════╗"
echo "║   התקנת תזמון אוטומטי לסוכן מסחר     ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 1. Replace YOUR_USERNAME with actual username in the plist
echo "🔧 מגדיר נתיב עבור המשתמש: $USERNAME..."
sed "s|YOUR_USERNAME|$USERNAME|g" "$PLIST_SRC" > /tmp/$PLIST_NAME.plist
sed -i '' "s|/Documents/trading-agent|${SCRIPT_DIR#$HOME}|g" /tmp/$PLIST_NAME.plist

# Show what path was set
AGENT_PATH=$(grep -A1 "bash -c" /tmp/$PLIST_NAME.plist | grep "cd " | sed 's/.*cd "//' | sed 's/".*//')
echo "   נתיב סוכן: $AGENT_PATH"
echo ""

# 2. Create LaunchAgents folder if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# 3. Unload if already installed
if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
    echo "🔄 מסיר גרסה קודמת..."
    launchctl unload "$PLIST_DST" 2>/dev/null
fi

# 4. Copy plist to LaunchAgents
cp /tmp/$PLIST_NAME.plist "$PLIST_DST"
echo "✅ קובץ הגדרה הועתק"

# 5. Load the launch agent
launchctl load "$PLIST_DST"

if [ $? -eq 0 ]; then
    echo "✅ תזמון הותקן בהצלחה!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📅 הסוכן ייפתח אוטומטית כל יום ב-16:00"
    echo "   (ראשון-חמישי, שעות מסחר אמריקאיות)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  חשוב: המחשב חייב להיות דלוק ולא בשינה ב-16:00"
    echo ""
    echo "כדי להסיר את התזמון בעתיד, הרץ:"
    echo "  launchctl unload ~/Library/LaunchAgents/$PLIST_NAME.plist"
    echo ""
else
    echo "❌ שגיאה בהתקנת התזמון"
    echo "נסה להריץ את הפקודה הבאה ב-Terminal:"
    echo "  launchctl load $PLIST_DST"
fi

echo ""
read -p "לחץ Enter לסגירה..."
