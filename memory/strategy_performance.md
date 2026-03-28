# Strategy Performance - ביצועי אסטרטגיות

*עדכון אחרון: 2026-03-28 (Coach — תיקוני תשתית: startup crash fix, watchdog, watchlist 45→19)*

## ציונים נוכחיים

| Strategy | Score | Trades | Win Rate | Profit Factor | P&L כולל | הערות |
|----------|-------|--------|----------|---------------|----------|-------|
| EMA_Crossover_9_21 | 53.7 | 7 | 14% | 41.6 | +$127.16* | ניצחון ענק SBUX +$144. הפסדות קטנות. עובד! |
| Volume_Spike_Momentum | 49.3 | 6 | 17% | 1.84 | -$108.99 | OXY +$63 אבל PFE הרג הכל. direction_bias=SHORT עודכן ✅ |
| Red_Green_Reversal | 25.6 | 3 | 33% | 0.08 | -$68.28 | MARA הפסד גדול. עדיין מוקדם לקבוע |
| RSI_MACD_Momentum | 50 | 0 | — | — | $0 | לא פעיל ב-RANGING |
| Opening_Range_Breakout | 50 | 0 | — | — | $0 | לא פעיל ב-RANGING |
| VWAP_Mean_Reversion | 50 | 0 | — | — | $0 | סיגנלים נחסמו ע"י staleness |
| Bollinger_Squeeze | 50 | 0 | — | — | $0 | לא מצא squeeze |
| Gap_And_Go | 50 | 0 | — | — | $0 | חדש |
| Price_Action_Scalp | 50 | 0 | — | — | $0 | סיגנלים נחסמו ע"י staleness |

*EMA כולל 6 הפסדים קטנים מ-19/03 + ניצחון +$144 ב-23/03

## סיכום כולל (כל הזמן)

| מדד | ערך |
|-----|-----|
| סה"כ עסקאות | 20 |
| ניצחונות | 4 |
| הפסדים | 16 |
| Win Rate | 20% |
| P&L כולל | **-$53.90** |
| P&L בלי PFE | **+$96.70** |

## הערת Coach — 28/03/2026 (תיקוני תשתית קריטיים)

### מה תוקן היום (28/03) — 5 תיקונים

| # | בעיה | סטטוס | מה נעשה |
|---|------|--------|---------|
| 1 | **Agent קורס אחרי startup** | ✅ תוקן | `_log_startup_info()` ו-`notify_daily_start()` עטופים ב-try/except (non-fatal). הוספת CRITICAL logging ב-main.py. |
| 2 | **Per-symbol cooldown** | ✅ קיים | כבר מיושם ב-`risk_manager.py._check_symbol_cooldown()` — 60 דקות cooldown. |
| 3 | **Signal staleness** | ✅ תוקן | Watchlist מוקטן מ-45 ל-19 סמלים. Focus על proven winners + high liquidity. |
| 4 | **Agent watchdog** | ✅ תוקן | `watchdog.sh` חדש — בודק כל 5 דקות, מפעיל מחדש אוטומטית + Telegram alert. |
| 5 | **Log filename timezone** | ✅ תוקן | `main.py` משתמש ב-ET timezone לשם קובץ הלוג (במקום שעון מקומי). |

### פעולות נדרשות מגל:

1. **הגדרת cron ל-watchdog** (על ה-Mac):
```bash
crontab -e
# הוסף שורה:
*/5 9-16 * * 1-5 /Users/galzituni/trading-agent/watchdog.sh >> /Users/galzituni/trading-agent/logs/watchdog.log 2>&1
```

2. **הרצת reconciliation** לסנכרון עסקאות חסרות מ-23/03:
```bash
cd ~/trading-agent
source venv/bin/activate
python scripts/reconcile_trades.py --date 2026-03-23
```

3. **הפעלת הסוכן ביום ראשון** (29/03 = שישי ET, 30/03 = שבת — מתחילים 31/03):
```bash
./start.sh
```

---

## הערת Coach — 27/03/2026 (ניתוח יומי — 23:30 IST)

### מה קרה היום (27/03)

הסוכן **הופעל ב-16:02 IST (10:02 ET)** אבל **קרס מיד אחרי initialization** — 25 שורות לוג בלבד. **תוקן ב-28/03.**

| מדד | ערך |
|-----|-----|
| עסקאות היום | 0 |
| P&L היום | $0.00 |
| ימי מסחר אבודים ברצף | 5 (24-28/03, שבת) |

---

## הערת Coach — 26/03/2026 (ניתוח יומי — 23:05 IST)

### מה קרה היום (26/03)

הסוכן **לא רץ היום**. אין לוג ל-26/03. heartbeat אחרון: 24/03 06:17 ET. הסוכן down 59+ שעות. 3 ימי מסחר מבוזבזים ברצף: 24/03, 25/03, 26/03.

הבאגים תוקנו היום ב-09:59 ET (19:29 IST) אבל הסוכן לא הופעל לאחר התיקונים. שוק סגור ב-16:00 ET (02:00 IST 27/03).

**הבעיה הראשית: agent stability. לא ניתן ללמוד ולהשתפר כשהסוכן לא רץ.**

### 4 באגים שתוקנו ב-26/03

| # | באג | השפעה | תיקון |
|---|-----|-------|-------|
| 1 | save_trade() ללא try/except | עסקאות אובדות | try/except + CRITICAL log |
| 2 | Exception swallowing בסגירה | שגיאות DB נבלעות | הפרדת שגיאות |
| 3 | consecutive_losses ללא סינון תאריך | cooling period אינסופי | סינון TODAY בלבד |
| 4 | SQLite ללא timeout | WAL lock hang | timeout=10s |
