# Learnings - מה הסוכן למד

*עדכון אחרון: 2026-03-28 (Coach v2 — שדרוג מקיף: GT-Score scoring, ATR position sizing, bug fixes, strategy upgrades)*

---

## 🔴 Agent_Stability (URGENT — המפתח לכל השאר)

- **[28/03/2026] תוקן! Agent startup crash — root cause ותיקון:** `_log_startup_info()` ו-`notify_daily_start()` היו מחוץ ל-try/except ב-`run()`. אם Alpaca API לא זמין (timeout, pre-market) — הסוכן קרס בשקט ללא שום log. **תיקון:** עטיפה ב-try/except נפרד (non-fatal), הוספת CRITICAL logging ב-main.py, heartbeat "running" לפני כניסה ל-loop.

- **[28/03/2026] תוקן! Watchdog auto-restart:** נוצר `watchdog.sh` שבודק כל 5 דקות אם הסוכן חי ומפעיל מחדש + שולח Telegram notification. הגדרת cron: `*/5 9-16 * * 1-5 /path/to/watchdog.sh`.

- **[28/03/2026] תוקן! Watchlist מותאם ל-35 סמלים (8 tiers):** 45 סמלים גרמו ל-signal staleness. צומצם ל-35 ב-8 tiers לפי liquidity: Mega-cap tech, Semiconductors, High-beta, Consumer (SBUX מוכח), Energy (OXY מוכח), Financials, Healthcare, ETFs. מספיק רחב לטורניר אסטרטגיות.

- **[28/03/2026] שדרוג! GT-Score inspired scoring (v2.0):** הציון השתנה מ-40/35/25 (win rate/PF/RR) ל-30/25/20/15/10 — הוספו 2 מטריקות חדשות: **Consistency** (15%, מעניש אסטרטגיות שתלויות ב-outliers) ו-**Max Drawdown** (10%, survivability). מבוסס על מחקר GT-Score שהראה 98% שיפור ב-generalization.

- **[28/03/2026] שדרוג! ATR-based position sizing:** במקום fixed percentage בלבד, הסוכן עכשיו מגביל position size לפי `Risk_Amount / Risk_Per_Share`. Risk per share = מרחק ל-stop loss, או ATR × 1.5 כ-fallback. מבטיח שפוזיציות במניות תנודתיות יהיו קטנות יותר אוטומטית.

- **[28/03/2026] שדרוג! ATR מועבר בכל האסטרטגיות:** כל 9 האסטרטגיות עכשיו כוללות ATR ב-indicators dict, מה שמאפשר ל-risk_manager לבצע ATR-based sizing. EMA Cross שודרג ל-ATR-based stops.

- **[28/03/2026] תוקן! SQL injection ב-memory.py:** LIMIT clause היה מוזרק ישירות ל-SQL. תוקן עם `int()` sanitization.

- **[28/03/2026] תוקן! ET timezone ב-memory.py:** כל 5 קריאות `date.today()` הוחלפו ב-`_today_et()` שמשתמש ב-pytz עם התאמה ל-pre-4AM.

- **[27/03/2026] יום 5 ברצף ללא עסקאות — Agent קורס אחרי startup:** הסוכן הופעל ב-16:02 IST (10:02 ET) אבל קרס מיד אחרי initialization — 25 שורות לוג בלבד, אף טיק לא בוצע. `health_status.json` תקוע ב-`status='starting'`. `last_tick` עדיין מ-23/03. **Root cause חדש שנחשף:** הסוכן עובר initialization אבל לא מגיע ל-main loop — ייתכן Alpaca connection timeout ב-pre-market, כשל ב-`market_data.py` בשעות לא-מסחר, או exception שקט. **תוקן ב-28/03.**

- **[26/03/2026] 3 ימי מסחר מבוזבזים ברצף (24-26/03):** הסוכן נפל ב-24/03 ב-06:01 ET ולא הופעל מחדש. באגים תוקנו ב-26/03 ב-09:59 ET אבל הסוכן לא הופעל. **זהו הבלוקר הראשי:** הסוכן לא יכול ללמוד בלי להיות חי. תיקון קריטי: watchdog process + cron job ב-09:25 ET מדי יום.

---

## 🟢 Bug_Fix (תוקן!)

- **[26/03/2026] תוקן: עסקאות לא נשמרות ל-DB (4 באגים):**
  1. **save_trade() ללא try/except** — הזמנה נשלחה ל-Alpaca לפני השמירה ל-DB, ואם השמירה נכשלה העסקה אבדה. תוקן: עטיפה ב-try/except עם CRITICAL logging.
  2. **Exception swallowing בסגירת עסקאות** — catch-all גנרי בלע שגיאות DB. תוקן: הפרדה בין שגיאות Alpaca ל-DB.
  3. **get_consecutive_losses() סופר כל הזמן** — קרא 10 עסקאות אחרונות ללא סינון תאריך → cooling period אינסופי אחרי יום הפסד. **זה הסיבה ש-24/03 חסם את כל העסקאות!** תוקן: סינון לפי תאריך היום בלבד.
  4. **SQLite connection ללא timeout** — WAL lock contention גרם ל-hang. תוקן: timeout=10s + busy_timeout=10000ms.

---

## 🔴 System_Bug (עדיין פתוח)

- **[24/03/2026] Cooling period אינסופי חסם את כל העסקאות:** הסוכן רץ ב-24/03 אבל כל סיגנל נחסם ע"י "6 consecutive losses! Cooling for 30 minutes" — כי get_consecutive_losses() ספר את 6 ההפסדים מ-19/03 (ללא סינון תאריך). **תוקן ב-26/03** — עכשיו סופר רק הפסדים של היום הנוכחי.

- **[24/03/2026] עסקאות ב-Alpaca לא נשמרו ל-DB:** אותו באג כמו 23/03. **תוקן ב-26/03.**

- **[23/03/2026] עסקאות לא נשמרות ל-DB:** 10 עסקאות ב-Alpaca, 0 ב-SQLite. **תוקן ב-26/03.**

---

## 🏆 Winning_Setup (setup מנצח)

- **[23/03/2026] EMA_Crossover SBUX SHORT +$144.16:** Opening session, entry=$94.33, exit=$91.61 (ירידה 2.88%), take_profit. הניצחון הגדול ביותר עד כה. EMA crossover SHORT עם מומנטום ברור — עובד! נדרשות יותר דוגמאות לזיהוי ה-setup המדויק. (1 עסקה, 23/03)

- **[23/03/2026] Volume_Spike OXY SHORT +$63.45:** take_profit, entry=$60.40 exit=$59.11 (ירידה 2.14%). Volume_Spike עובד טוב ב-SHORT על מניות עם מומנטום ברור. (1 עסקה, 23/03)

---

## 🔴 Risk_Management

- **[23/03/2026] PFE Death Spiral — 4 פעמים:** PFE SHORT נסחר 4 פעמים (13:31, 13:37, 18:40, 18:43) כולן מ-$26.66, כולן הפסד. **סה"כ הפסד מ-PFE: $-150.60 (76% מכלל ההפסדות!).** ללא PFE — P&L היום היה +$117.49. אותו דפוס כמו SPY ב-19/03. כלל ה-cooldown לא מיושם. תיקון: per-symbol cooldown מינימום 60 דקות אחרי הפסד. (4 עסקאות, 23/03)

- 5 עסקאות זהות על SPY תוך 3 דקות (16:15-16:18), כולן stop_loss, -$16. צריך cooldown של 5 דקות בין כניסות לאותו סמל. (5 עסקאות, 2026-03-19)

---

## Strategy_Activation

- **[23/03/2026] Volume_Spike — SHORT בלבד בינתיים:** ARKK LONG נכשל (-$21.84), OXY SHORT הצליח (+$63.45). שקול להגביל Volume_Spike ל-SHORT עד שיהיו יותר דוגמאות LONG מנצחות. (6 עסקאות, 23/03)

- EMA_Crossover_9_21 ירה 6 פעמים בשוק RANGING (ADX=15) — 100% הפסד. אסור להפעיל בשוק RANGING. תוקן: הוסר RANGING, adx_min הועלה מ-15 ל-25. (6 עסקאות, 2026-03-19)

---

## Market_Timing

- **[26/03/2026] 4 Opening sessions מוחמצות ברצף (23-26/03):** Opening session (09:30-10:30 ET) הוא ה-session הרווחי ביותר — 100% מהניצחונות הגיעו משם (SBUX +$144, OXY +$63). שני ה-setups המנצחים המוכחים הם Opening-only. לאבד 4 openings ברצף = לאבד את ה-best opportunity כל יום. **Watchdog auto-restart = השיפור הגדול ביותר שניתן לעשות, לא שיפור אסטרטגי.**

- **[26/03/2026] 3 ימי מסחר מבוזבזים ברצף:** ראה Agent_Stability למעלה.

- **[24/03/2026] יום מסחר מבוזבז עקב cooling bug:** הסוכן רץ כל היום (agent.log מראה ticks ב-17:45, 18:08, 19:15, 21:43) אבל 100% נחסם ע"י cooling period. סיגנלים טובים נוצרו (3-6 per tick above threshold) אבל אף אחד לא בוצע. **Root cause תוקן.**

- **[23/03/2026] Opening session הכי רווחי:** 7 מתוך 10 עסקאות היו ב-Opening (13:31-16:33 IST). כולל שני הניצחונות הגדולים (SBUX +$144, OXY +$63). Midday הביא רק 2 עסקאות PFE כושלות.

- No trades on 2026-03-20 (Friday). Pattern: RANGING Friday after a losing day = no-trade day. (0 trades, 2026-03-20)

---

## Signal_Quality

- **[23/03/2026] PFE — סיגנל פנטום חוזר:** Price_Action_Scalp + Volume_Spike ממשיכים לייצר סיגנלים על PFE בכל טיק. entry_price תמיד $26.66. מציע שהמניה נשארת מתחת ל-VWAP/EMA לאורך כל היום. Cooldown לפי סמל יפתור זאת.

- EMA(9)-EMA(21) spread של $0.03 על SPY (~0.005%) — רעש סטטיסטי, לא מגמה אמיתית. יש להוסיף min_ema_spread_pct=0.05%. (6 עסקאות, 2026-03-19)
