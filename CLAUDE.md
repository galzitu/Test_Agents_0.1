# Trading Agent - סוכן Day Trading אוטונומי

## מה הפרויקט הזה
סוכן Day Trading אוטונומי שרץ על Mac. מבוסס Rule Engine (בלי AI בזמן אמת).
לומד מטעויות בעזרת Claude Coach (Cowork Scheduled Task בסוף יום).
Paper trading בלבד עד שמוכח רווחי.

## ארכיטקטורה - שתי שכבות

```
שכבה 1: RULE ENGINE (real-time, $0)
├── Python script שרץ בשעות מסחר
├── 5-6 אסטרטגיות טכניות רצות במקביל (טורניר)
├── זיהוי מצב שוק (trending/ranging/volatile)
├── בחירת אסטרטגיה מתאימה אוטומטית
├── Alpaca API - ביצוע עסקאות (paper trading)
├── SQLite - שמירת כל עסקה + ציונים
└── Telegram - התראות real-time

שכבה 2: CLAUDE COACH (סוף יום, $0)
├── Cowork Scheduled Task (חלק מהמנוי)
├── מנתח ביצועים יומיים/שבועיים
├── לא משנה פרמטרים - משנה activation conditions
├── לומד: מתי כל אסטרטגיה עובדת/נכשלת
└── מעדכן scores, allocation, learnings
```

## עקרונות מרכזיים

### Day Trading
- כל הפוזיציות נסגרות לפני 15:50 ET (22:50 IST)
- אף פעם overnight!
- נטו טכני - גרפים, אינדיקטורים, patterns

### טורניר אסטרטגיות
- כל אסטרטגיה מקבלת ציון (0-100) על סמך ביצועים אמיתיים
- מינימום 30 עסקאות לפני שציון נחשב אמין
- ציון גבוה = יותר תקציב (capital allocation)
- ציון נמוך = פחות תקציב או כיבוי
- פרמטרים קבועים! מה שמשתנה = מתי להפעיל כל אסטרטגיה

### ניהול סיכונים (קשיח - לא ניתן לשינוי!)
- מקסימום 5% מהתיק בעסקה (3% בפתיחה)
- Stop Loss חובה על כל עסקה
- מקסימום 3% הפסד יומי → הסוכן נעצר
- 3 הפסדים ברצף → 30 דקות cooling
- מקסימום 3 פוזיציות פתוחות
- מקסימום 20 עסקאות ביום

## מסמכי הפרויקט

| מסמך | תוכן |
|------|-------|
| `CLAUDE.md` | הקובץ הזה - סקירה והוראות |
| `ARCHITECTURE.md` | תכנון טכני מפורט (v4) |
| `research/DAY_TRADING_RESEARCH.md` | מחקר מעמיק על day trading |
| `research/STRATEGIES_REFERENCE.md` | מיפוי אסטרטגיות מוכן לקוד |
| `memory/learnings.md` | לקחים שהסוכן למד |
| `memory/strategy_performance.md` | ביצועי אסטרטגיות |

## אסטרטגיות

| # | אסטרטגיה | סשן מתאים | מצב שוק |
|---|----------|-----------|---------|
| 1 | RSI + MACD Momentum | Opening, Power Hour | Trending |
| 2 | Opening Range Breakout (ORB) | Opening | Volatile, Gap |
| 3 | VWAP Mean Reversion | Mid-Day | Ranging |
| 4 | Volume Spike Momentum | Opening, Power Hour | Volatile |
| 5 | EMA Crossover (9/21) | Any | Trending |
| 6 | Bollinger Band Squeeze | Any | Ranging→Breakout |

## שעות מסחר (ET → IST)

| סשן | ET | IST | הסוכן עושה |
|------|-----|-----|-----------|
| Pre-Market | 04:00-09:30 | 11:00-16:30 | סריקה + watchlist |
| Opening | 09:30-10:30 | 16:30-17:30 | מסחר אגרסיבי (כל 30-60 שניות) |
| Mid-Day | 10:30-14:30 | 17:30-21:30 | מסחר שמרני (כל 5 דקות) |
| Power Hour | 14:30-16:00 | 21:30-23:00 | מסחר אגרסיבי (כל 2 דקות) |
| Close | 15:50 | 22:50 | סוגר הכל! |
| Review | 16:15+ | 23:15+ | Claude Coach מנתח |

## סטטוס נוכחי

### שלב 0: תכנון ✅
- [x] CLAUDE.md
- [x] ARCHITECTURE.md (v4 - טורניר אסטרטגיות)
- [x] מחקר Day Trading מעמיק
- [x] מיפוי אסטרטגיות

### שלב 1: תשתית ✅
- [ ] הגדרת Alpaca paper trading account (צריך מהמשתמש)
- [ ] הגדרת Telegram Bot (צריך מהמשתמש)
- [x] requirements.txt + config.py + .env.example + .gitignore
- [x] market_hours.py (sessions, holidays, timezone ET/IST)
- [x] market_condition.py (trending/ranging/volatile/low_volume)
- [x] memory.py (SQLite schema - trades, scores, learnings)
- [x] market_data.py (Alpaca client + indicators + screener)
- [x] strategies_config/*.json (כל 6 אסטרטגיות + scores + allocation)

### שלב 2: נתוני שוק ✅ (חלק מ-market_data.py)
- [x] market_data.py (Alpaca + ta library + all indicators)
- [x] screener (gaps, volume spikes)

### שלב 3: אסטרטגיות ✅
- [x] BaseStrategy + Signal classes
- [x] RSI+MACD Momentum, ORB, VWAP Reversion, Volume Spike, EMA Cross, Bollinger Squeeze
- [x] selector.py (בוחר אסטרטגיות לפי סשן + מצב שוק)
- [x] scorer.py (ציון 0-100 לפי ביצועים)
- [x] allocator.py (הקצאת תקציב לפי ציון)

### שלב 4: מסחר ✅
- [x] risk_manager.py (כללי סיכון קשיחים - stop loss, position size, daily limits, cooling)
- [x] trader.py (ביצוע עסקאות Alpaca - פתיחה, סגירה, ניהול פוזיציות)
- [x] core.py (לולאה ראשית - market condition → strategies → signals → execute)
- [x] main.py (נקודת כניסה - run/status/test)
- [ ] ריצה ראשונה! (צריך להתקין dependencies על ה-Mac)

### שלב 5: Telegram + Coach ✅
- [x] telegram_bot.py (התראות real-time + פורמט הודעות)
- [x] Cowork Scheduled Task (Claude Coach - כל יום 23:30 IST, ימי חול)
- [x] start.sh (סקריפט הפעלה ל-Mac)
- [ ] הגדרת Telegram Bot (צריך מהמשתמש)

### שלב 6: שיפורים ⬅️ פה אנחנו
- [ ] TradingView webhooks (אופציונלי)
- [ ] Dashboard
- [ ] Backtesting

## הוראות לפתיחת פרויקט
כשפותחים את הפרויקט הזה ב-Claude Desktop:
1. קרא את CLAUDE.md (הקובץ הזה)
2. קרא את ARCHITECTURE.md
3. קרא את `memory/learnings.md` אם קיים
4. קרא את `memory/strategy_performance.md` אם קיים
5. המשך מהסטטוס הנוכחי

## עלויות: $0
- Alpaca Paper Trading: חינמי
- Claude Coach (Cowork Scheduled Task): חלק מהמנוי
- Telegram Bot: חינמי
- Python + Libraries: חינמי
