# Claude Coach — דו"ח יומי 27/03/2026

**תאריך**: שישי, 27 מרץ 2026  
**זמן ניתוח**: 23:30 IST  
**עסקאות היום**: 0  
**P&L יומי**: $0.00

---

## מצב הסוכן היום

הסוכן **הופעל ב-16:02 IST (10:02 ET)** — לפני פתיחת השוק (16:30 IST). אבל הסוכן **קרס מיד אחרי initialization** ולא ביצע אף טיק. הלוג מכיל 25 שורות בלבד, כולן startup messages. `health_status.json` תקוע ב-`status='starting'`. `last_tick.json` עדיין מ-23/03.

זהו **יום 5 ברצף ללא עסקאות** (24, 25, 26, 27/03).

---

## ניתוח Root Cause

### מה ידוע:
1. הסוכן עובר initialization בהצלחה — 9 אסטרטגיות נטענות, agent.core מאותחל
2. הסוכן לא מגיע לשלב ה-main loop (אין שורת "Tick #1" בלוג)
3. הלוג מסתיים ב-`TRADING AGENT STARTING` — אחרי זה שקט מוחלט

### סיבות אפשריות:
1. **Alpaca API call ב-pre-market** — האם `market_data.py` מנסה לקבל bar data לפני 09:30 ET? Timeout יגרום לתקיעה
2. **`market_condition.py`** — חישוב מצב שוק דורש נתוני עבר. אם API לא מגיב, תקיעה
3. **Exception שקט** — ב-`core.py`, אם ה-`run()` method יוצא ללא logging
4. **Python process נהרג ע"י OS** — Mac memory pressure / sleep mode

### מה שונה ב-23/03 (היום שכן עבד):
- הסוכן הופעל ב-10:43 ET — כשהשוק כבר פתוח וה-API יציב
- שאר הימים: הופעל לפני/ב-10:00-10:02 ET — שעה בעייתית

**השערה**: הסוכן מתחיל ב-pre-market, מנסה לקבל market data, ה-API מחזיר timeout/error, וה-exception נבלע בשקט.

---

## מה שלא השתנה (ציונים)

ציונים לא עודכנו — אין עסקאות חדשות. עדיין פחות מ-30 עסקאות לכל אסטרטגיה.

| Strategy | Score | Total Trades |
|----------|-------|-------------|
| EMA_Crossover_9_21 | 53.7 | 7 |
| Volume_Spike_Momentum | 49.3 | 6 |
| Red_Green_Reversal | 25.6 | 3 |
| שאר (5) | 50.0 | 0 |

---

## Setup המנצח — עדיין ממתין לאימות

מ-23/03 (Alpaca, לא ב-DB):
- **EMA_Crossover SHORT + Opening session + TRENDING_DOWN** → +$144.16 (SBUX)
- **Volume_Spike SHORT + Opening session + strong momentum** → +$63.45 (OXY)

**האסטרטגיה עובדת. הסוכן לא מגיע אליה.**

---

## תיקונים נדרשים — מדורגים

| # | בעיה | דחיפות | תיקון מוצע |
|---|------|---------|------------|
| 1 | Agent קורס אחרי startup | 🔴 CRITICAL | הוסף verbose logging בין init לloop. הוסף `try/except Exception as e: logger.critical(f"Startup crash: {e}")` ב-`main()` |
| 2 | Watchdog / pre-market protection | 🔴 CRITICAL | אם שעה < 09:25 ET, sleep עד 09:25. אל תנסה לקבל market data לפני שהשוק קרוב לפתיחה |
| 3 | Per-symbol cooldown 60 דקות | 🟡 HIGH | PFE + SPY דפוס חוזר. הפסד ה-76% (PFE) ניתן למניעה |
| 4 | Signal staleness | 🟡 MEDIUM | הקטנת watchlist ל-20, refresh quote לפני ביצוע |

---

## סיכום שבועי (שבוע 2 — 24-28/03)

| יום | עסקאות | P&L | סיבה |
|-----|--------|-----|------|
| ב 24/03 | 0 | $0 | Agent נפל 06:01 ET |
| ג 25/03 | 0 | $0 | Agent down (לא הופעל) |
| ד 26/03 | 0 | $0 | Agent down (לא הופעל) |
| ה 27/03 | 0 | $0 | Agent קרס אחרי startup |
| **סה"כ שבוע** | **0** | **$0** | — |

**סה"כ מצטבר (מ-19/03)**: -$20.79 (רק עסקאות DB. Alpaca: ~+$57 ללא PFE bug)

---

*Claude Coach — 27/03/2026 23:30 IST*
