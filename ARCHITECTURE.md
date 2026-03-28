# Trading Agent - תכנון טכני סופי (v4)

## עקרון מרכזי: טורניר אסטרטגיות

הסוכן מריץ **מספר אסטרטגיות במקביל**, כל אחת עם "חשבון וירטואלי" משלה.
במקום לנחש מראש מה עובד - הוא נותן לתוצאות לדבר.

```
דמיין 5 סוחרים שיושבים באותו חדר:
├── סוחר 1: "אני קונה כש-RSI נמוך + MACD עולה"
├── סוחר 2: "אני קונה breakout מה-range של הבוקר"
├── סוחר 3: "אני קונה חזרה ל-VWAP"
├── סוחר 4: "אני קונה spike בווליום"
└── סוחר 5: "אני קונה EMA crossover"

אחרי חודש:
├── סוחר 1: +$500 (win rate 65%) ← מוצלח!
├── סוחר 2: +$300 (win rate 58%) ← סבבה
├── סוחר 3: -$100 (win rate 40%) ← בעייתי
├── סוחר 4: +$50  (win rate 50%) ← בינוני
└── סוחר 5: -$200 (win rate 35%) ← גרוע

מה עושים?
├── סוחר 1+2: מגדילים להם את התקציב
├── סוחר 3: בודקים למה - אולי עובד רק בשוק שקט?
├── סוחר 4: משאירים, צריך עוד נתונים
└── סוחר 5: מקטינים תקציב או מכבים
```

---

## למה "טורניר" ולא "כיוונון פרמטרים"?

```
הבעיה שזיהינו:
├── יום שני: אסטרטגיה X עובדת מעולה
├── יום שלישי: אותה אסטרטגיה נכשלת
├── Claude משנה פרמטרים → עכשיו נכשלת גם ביום שני
└── הסוכן "רודף את הזנב של עצמו"

הפתרון:
├── הפרמטרים של כל אסטרטגיה נשארים קבועים
├── מה שמשתנה: כמה כסף (%) מקצים לכל אסטרטגיה
├── ומתי כל אסטרטגיה פעילה (באיזה מצב שוק)
└── שינויים רק אחרי מספיק נתונים (מינימום 30 עסקאות)
```

---

## מצבי שוק - הסוד

אסטרטגיה לא "טובה" או "רעה". היא מתאימה למצב שוק מסוים:

```
מצב שוק         │ מה עובד               │ מה נכשל
═════════════════╪═══════════════════════╪══════════════════
Trending Up   ▲  │ Momentum, EMA Cross   │ Mean Reversion
Trending Down ▼  │ Short Momentum        │ Buy-the-dip
Ranging ↔        │ VWAP Reversion, RSI   │ Breakout, Momentum
Volatile ⚡      │ Volume Spike, ORB     │ VWAP, Range trading
Low Volume 😴    │ כלום (לא לסחור!)      │ הכל
```

### איך הסוכן מזהה מצב שוק?

```python
class MarketCondition:
    """מזהה את מצב השוק הנוכחי - בלי AI, רק מתמטיקה"""

    def detect(self, data):
        atr = data.atr_14                    # תנודתיות
        adx = data.adx_14                    # חוזק מגמה
        volume_ratio = data.volume / data.avg_volume_20

        if adx > 25 and data.trend == "up":
            return "TRENDING_UP"
        elif adx > 25 and data.trend == "down":
            return "TRENDING_DOWN"
        elif atr > data.atr_avg * 1.5:
            return "VOLATILE"
        elif volume_ratio < 0.5:
            return "LOW_VOLUME"             # סכנה! לא לסחור
        else:
            return "RANGING"
```

---

## הארכיטקטורה המלאה

```
┌──────────────────────────────────────────────────────────────┐
│                        Mac של המשתמש                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  RULE ENGINE (real-time)                │  │
│  │                                                        │  │
│  │  Market Data ──→ Market Condition ──→ Strategy Selector│  │
│  │  (Alpaca)        Detector              "מי פעיל היום?" │  │
│  │                  (trending/ranging/                     │  │
│  │                   volatile/quiet)                       │  │
│  │                                                        │  │
│  │  Active Strategies (run in parallel):                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│  │  │ RSI+MACD │ │   ORB    │ │   VWAP   │ │ Vol Spike│ │  │
│  │  │ score:72 │ │ score:65 │ │ score:45 │ │ score:55 │ │  │
│  │  │ alloc:30%│ │ alloc:25%│ │ alloc:15%│ │ alloc:20%│ │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │  │
│  │       └─────────────┴─────────────┴─────────────┘      │  │
│  │                         │ signals                      │  │
│  │                         ▼                              │  │
│  │              ┌─────────────────────┐                   │  │
│  │              │    Risk Manager     │                   │  │
│  │              │  position size      │                   │  │
│  │              │  stop loss          │                   │  │
│  │              │  daily limits       │                   │  │
│  │              └──────────┬──────────┘                   │  │
│  │                         ▼                              │  │
│  │              ┌─────────────────────┐                   │  │
│  │              │   Alpaca Trader     │                   │  │
│  │              │   execute orders    │                   │  │
│  │              └─────────────────────┘                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │ saves everything                   │
│                         ▼                                    │
│  ┌─────────────────────────────────────┐                    │
│  │          SQLite Memory              │                    │
│  │  trades │ strategy_scores │ lessons │                    │
│  └─────────────────┬───────────────────┘                    │
│                     │ read by                                │
│                     ▼                                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │         CLAUDE COACH (Scheduled Task / On-Demand)      │  │
│  │                                                        │  │
│  │  Daily: קורא תוצאות → מנתח → מעדכן scores + תנאים    │  │
│  │  Weekly: סקירה רחבה → הפעלה/כיבוי אסטרטגיות          │  │
│  │  On-Demand: אתה שואל "למה הפסדתי היום?"              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Telegram Bot                         │  │
│  │  Real-time: 📈BUY 📉SELL 🛑STOP ✅PROFIT              │  │
│  │  Commands: /status /pnl /scores /coach /pause          │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## מנגנון הציון (Scoring System)

כל אסטרטגיה מקבלת **ציון** שמבוסס על ביצועים אמיתיים, לא על דעה:

```python
class StrategyScorer:
    """מחשב ציון לכל אסטרטגיה - רק על בסיס נתונים"""

    # מינימום עסקאות לפני שהציון נחשב אמין
    MIN_TRADES_FOR_SCORE = 30

    def calculate_score(self, strategy_name, trades):
        if len(trades) < self.MIN_TRADES_FOR_SCORE:
            return 50  # ציון ניטרלי - עוד לא מספיק נתונים

        win_rate = wins / total                    # 0-1
        profit_factor = gross_profit / gross_loss  # >1 = רווחי
        avg_rr = avg_win / avg_loss                # risk/reward

        # ציון משוקלל 0-100
        score = (
            win_rate * 40 +              # 40% משקל ל-win rate
            min(profit_factor / 3, 1) * 35 +  # 35% ל-profit factor
            min(avg_rr / 3, 1) * 25      # 25% ל-risk/reward
        )

        return round(score)
```

### מה הציון קובע?

```
ציון 70-100: "אסטרטגיה חזקה"
├── מקבלת 25-35% מהתקציב
├── פעילה בכל סשן מתאים
└── פרמטרים לא נוגעים!

ציון 50-70: "אסטרטגיה סבירה"
├── מקבלת 10-20% מהתקציב
├── פעילה, ממשיכים לעקוב
└── אם יורדת מ-50 → לבדיקה

ציון 30-50: "אסטרטגיה בעייתית"
├── מקבלת 5-10% מהתקציב (מקטינים חשיפה)
├── Claude בודק: אולי עובדת רק במצב שוק מסוים?
│   ├── כן → מגבילים אותה לאותו מצב (ציון עולה)
│   └── לא → מכבים אחרי 50 עסקאות
└── לא משנים פרמטרים!

ציון 0-30: "אסטרטגיה כושלת"
├── מכובה אוטומטית
├── Claude מנתח: מה הבעיה? (post-mortem)
└── אפשר להדליק מחדש ידנית אם השוק השתנה

ציון "?" (פחות מ-30 עסקאות):
├── "תקופת מבחן" - allocation קטן (5%)
├── לא מכבים, לא מגדילים
└── ממתינים ל-30 עסקאות לפני שיפוט
```

---

## הקצאת תקציב דינמית (Capital Allocation)

```python
class CapitalAllocator:
    """מחלק את הכסף בין אסטרטגיות לפי ציון"""

    TOTAL_BUDGET = 1.0  # 100% מהתיק הזמין

    def allocate(self, strategy_scores):
        """
        דוגמה:
        RSI_MACD:  score=72 → weight=72
        ORB:       score=65 → weight=65
        VWAP:      score=45 → weight=45
        VolSpike:  score=55 → weight=55
        EMA_Cross: score=? (new) → weight=50 (default)

        total_weight = 72+65+45+55+50 = 287
        RSI_MACD:  72/287 = 25.1% מהתקציב
        ORB:       65/287 = 22.6%
        VWAP:      45/287 = 15.7%
        VolSpike:  55/287 = 19.2%
        EMA_Cross: 50/287 = 17.4%
        """
        total_weight = sum(scores.values())
        return {
            name: score / total_weight
            for name, score in scores.items()
        }
```

**מה קורה עם הזמן:**

```
חודש 1 (הכל חדש):
├── RSI_MACD:  50 (?) → 20% │ כל האסטרטגיות
├── ORB:       50 (?) → 20% │ מקבלות
├── VWAP:      50 (?) → 20% │ חלק
├── VolSpike:  50 (?) → 20% │ שווה
└── EMA_Cross: 50 (?) → 20% │

חודש 2 (מתחילים לראות):
├── RSI_MACD:  68 → 26% ▲  │ עובדת טוב
├── ORB:       61 → 23% ▲  │ סבבה
├── VWAP:      42 → 16% ▼  │ בעייתית
├── VolSpike:  54 → 20%    │ ממוצעת
└── EMA_Cross: 38 → 15% ▼  │ גרועה

חודש 3 (ציונים מתייצבים):
├── RSI_MACD:  72 → 30% ▲  │ אלופה!
├── ORB:       65 → 27% ▲  │ חזקה
├── VWAP:      52 → 18%    │ Claude גילה: עובדת רק ב-RANGING
├── VolSpike:  55 → 19%    │ יציבה
└── EMA_Cross: 28 → 6%  ▼  │ כמעט כבויה, Claude בודק

חודש 6:
├── RSI_MACD:  75 → 28%    │ אסטרטגיית דגל
├── ORB:       70 → 26%    │ חזקה
├── VWAP:      64 → 18%    │ מצוינת - רק כש-RANGING
├── VolSpike:  58 → 16%    │ OK
├── EMA_Cross: כבויה       │ Claude כיבה, לא שווה
└── Bollinger: 55 (?) → 12%│ ← Claude הוסיף אסטרטגיה חדשה!
```

---

## מנגנון הלמידה - Step by Step

### שלב 1: כל עסקה נשמרת עם כל הפרטים

```sql
INSERT INTO trades VALUES (
    strategy = "RSI_MACD",
    symbol = "AAPL",
    session = "opening",
    market_condition = "TRENDING_UP",
    entry_price = 178.50,
    exit_price = 180.10,
    pnl = +80.00,
    pnl_pct = +0.9%,
    hold_minutes = 33,
    exit_reason = "take_profit",
    -- אינדיקטורים ברגע הכניסה:
    rsi_at_entry = 28,
    macd_at_entry = "bullish_cross",
    atr_at_entry = 1.8,
    volume_ratio = 2.3,
    vix_at_entry = 18.5
);
```

### שלב 2: ציונים מתעדכנים אוטומטית (אחרי כל עסקה)

```python
# אחרי כל עסקה שנסגרת:
def on_trade_closed(trade):
    # 1. שמור ב-database
    db.save_trade(trade)

    # 2. חשב מחדש את הציון של האסטרטגיה
    all_trades = db.get_trades(strategy=trade.strategy, last_n=50)
    new_score = scorer.calculate_score(all_trades)
    db.update_score(trade.strategy, new_score)

    # 3. עדכן allocation
    allocator.recalculate()

    # 4. שלח Telegram
    telegram.send(f"{'✅' if trade.pnl > 0 else '❌'} "
                  f"{trade.strategy} {trade.symbol} "
                  f"P&L: ${trade.pnl:.2f} | "
                  f"Score: {new_score}")
```

### שלב 3: Claude Coach - ניתוח יומי (Scheduled Task)

Claude רץ פעם ביום דרך Cowork Scheduled Task, **$0 עלות**:

```
Prompt ל-Claude (סוף יום):
═══════════════════════════

"אתה מנתח ביצועי מסחר. הנה תוצאות היום:

📊 סיכום:
- תאריך: 2026-03-15
- מצב שוק: TRENDING_UP בבוקר, RANGING אחה"צ
- עסקאות: 12 (7 wins, 5 losses)
- P&L: +$215

📈 לפי אסטרטגיה:
RSI_MACD: 4 trades (3W/1L) +$180 | score: 72→74
ORB:      3 trades (2W/1L) +$95  | score: 65→66
VWAP:     3 trades (1W/2L) -$45  | score: 45→43
VolSpike: 2 trades (1W/1L) -$15  | score: 55→54

❌ הפסדים:
1. VWAP TSLA -$65 | condition=TRENDING_UP ← !!!
2. VWAP AMD -$30  | condition=TRENDING_UP ← !!!
3. ORB NVDA -$25  | range=0.3% (small)
4. RSI META -$15  | volume_ratio=0.8 (low)
5. VolSpike GOOG -$20 | condition=RANGING

שאלות:
1. יש pattern בהפסדים?
2. האם צריך לשנות activation conditions?
3. האם להוסיף/להוריד אסטרטגיה?"
```

```
תשובה מ-Claude:
═══════════════

{
  "analysis": "VWAP נכשל פעמיים כי השוק היה TRENDING.
    Mean reversion לא עובד בשוק עם מגמה ברורה.
    זה לא בעיה של פרמטרים - זה בעיה של TIMING.",

  "pattern_found": "VWAP: 5 מתוך 6 הפסדים בשבוע האחרון
    היו בשוק TRENDING. בשוק RANGING: 4W/1L.",

  "condition_changes": [
    {
      "strategy": "VWAP_Reversion",
      "change": "add_condition",
      "condition": "market_condition == RANGING",
      "reason": "VWAP עובד מצוין ב-RANGING, נכשל ב-TRENDING.
                 6 הפסדים מיותרים בשבועיים.
                 data: RANGING=80% win, TRENDING=25% win"
    }
  ],

  "parameter_changes": [],  // ← לא משנים פרמטרים!

  "new_lessons": [
    "VWAP Mean Reversion: להפעיל רק כש-ADX < 25 (ranging)"
  ],

  "strategy_recommendations": {
    "consider_adding": "Bollinger Band Squeeze -
      יכול לעבוד טוב ב-ranging→breakout transitions",
    "consider_disabling": null
  }
}
```

### שלב 4: הפרויקט מבצע את השינויים

```python
# coach_executor.py - מבצע את ההמלצות של Claude

def apply_coach_recommendations(recommendations):
    for change in recommendations["condition_changes"]:
        # 1. טוען את config של האסטרטגיה
        config = load_json(f"strategies_config/{change['strategy']}.json")

        # 2. מוסיף תנאי הפעלה
        config["activation_conditions"].update(
            change["condition"]
        )

        # 3. שומר (עם changelog)
        config["changelog"].append({
            "date": today(),
            "change": change["change"],
            "reason": change["reason"],
            "data_points": 30  # כמה עסקאות בססו את ההחלטה
        })

        save_json(config)

    # 4. שומר לקחים
    for lesson in recommendations["new_lessons"]:
        db.save_learning(lesson)

    # 5. מעדכן learnings.md (קריא לאדם)
    update_learnings_md()
```

---

## דוגמה: 3 חודשים של למידה

```
══════════════════════════════════════════════════════
שבוע 1-2: "תקופת מבחן"
══════════════════════════════════════════════════════
- כל 5 האסטרטגיות רצות עם allocation שווה (20% כל אחת)
- הסוכן אוסף נתונים
- Claude עדיין לא משנה כלום (אין מספיק data)
- הרבה הפסדים - צפוי ונורמלי!
- Telegram שולח כל עסקה, אתה רואה מה קורה

══════════════════════════════════════════════════════
שבוע 3-4: "התמונה מתבהרת"
══════════════════════════════════════════════════════
- RSI_MACD ו-ORB מובילות (score 60+)
- EMA_Cross בפיגור (score 38)
- Claude מזהה:
  ├── "VWAP נכשל ב-trending days → הגבל ל-RANGING"
  ├── "ORB מצוין כשיש gap > 1%"
  └── "EMA_Cross: 2 מתוך 15 wins. עוד 15 עסקאות לפני החלטה"
- Allocation מתחיל להשתנות (RSI_MACD מקבל 28%)

══════════════════════════════════════════════════════
חודש 2: "אופטימיזציה"
══════════════════════════════════════════════════════
- RSI_MACD: score 72, alloc 30%
- ORB: score 67, alloc 25%
- VWAP: score 60, alloc 18% (רק ב-RANGING - עובד!)
- VolSpike: score 55, alloc 17%
- EMA_Cross: כבויה (score 25 אחרי 45 עסקאות)
- Claude מציע: "נסה Bollinger Band Squeeze"
  └── נוספת עם alloc 10%, תקופת מבחן

══════════════════════════════════════════════════════
חודש 3: "סוכן בוגר"
══════════════════════════════════════════════════════
- RSI_MACD: score 75, alloc 28% ← אסטרטגיית דגל
- ORB: score 70, alloc 25% ← חזקה
- VWAP: score 64, alloc 16% ← RANGING only, מושלם
- Bollinger: score 58, alloc 14% ← מבטיחה
- VolSpike: score 56, alloc 17% ← יציבה
-
- לקחים מצטברים:
  ├── "לא לסחור כש-volume_ratio < 0.5"
  ├── "ORB עובד הכי טוב עם gap 1-3%"
  ├── "RSI_MACD: oversold=30 מושלם ל-large caps"
  ├── "VWAP רק ב-RANGING (ADX < 25)"
  ├── "לא לסחור 10 דקות לפני/אחרי FOMC"
  └── "Power Hour: RSI_MACD ו-VolSpike הכי טובות"
```

---

## מה Claude Coach באמת יכול לשנות (ומה לא)

```
✅ מותר לשנות:
├── Activation Conditions (מתי אסטרטגיה פעילה)
│   "הפעל VWAP רק כש-ADX < 25"
│
├── Allocation (כמה כסף לכל אסטרטגיה)
│   "RSI_MACD מקבל 30% במקום 20%"
│
├── הוספת אסטרטגיה חדשה (בתקופת מבחן)
│   "נסה Bollinger Squeeze עם 5% allocation"
│
├── כיבוי אסטרטגיה (אחרי 50+ עסקאות עם score < 30)
│   "EMA_Cross כבויה - win rate 25% אחרי 50 עסקאות"
│
├── Watchlist
│   "הוסף NVDA ל-watchlist - earnings השבוע"
│
└── לקחים (learnings)
    "לא לסחור ב-10 דקות הראשונות של FOMC day"

❌ אסור לשנות:
├── פרמטרים של אסטרטגיות (RSI period, thresholds)
│   (רק אחרי 100+ עסקאות ובאישור המשתמש)
│
├── כללי ניהול סיכונים (max position, stop loss חובה)
│   (hardcoded, אף אחד לא משנה)
│
├── קוד (Claude לא נוגע ב-Python)
│
└── Daily loss limit, max positions
```

---

## שעות מסחר

### סשנים

| סשן | שעות (ET) | שעות (ישראל) | מאפיינים |
|------|-----------|---------------|----------|
| **Pre-Market** | 04:00-09:30 | 11:00-16:30 | סריקה בלבד, לא סוחר |
| **Opening** | 09:30-10:30 | 16:30-17:30 | תנודתיות מקסימלית |
| **Mid-Day** | 10:30-14:30 | 17:30-21:30 | שוק שקט, ranging |
| **Power Hour** | 14:30-16:00 | 21:30-23:00 | תנודתיות עולה |
| **Close** | 15:50-16:00 | 22:50-23:00 | סגירת כל הפוזיציות |

### התנהגות לפי סשן

```
Pre-Market: סורק gaps, volume → בונה watchlist
Opening:    ORB + RSI_MACD + VolSpike (כל 30-60 שניות)
Mid-Day:    VWAP + Bollinger (כל 5 דקות)
Power Hour: RSI_MACD + VolSpike (כל 2 דקות)
15:50:      סוגר הכל - Day Trading = לא overnight!
ערב:        Claude Coach scheduled task → ניתוח + עדכון
```

### חגים

```python
MARKET_HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25"
]
EARLY_CLOSE_DAYS_2026 = ["2026-11-27", "2026-12-24"]
```

---

## מבנה קבצים סופי

```
trading-agent/
├── CLAUDE.md
├── ARCHITECTURE.md
├── requirements.txt
├── .env / .env.example / .gitignore
│
├── agent/
│   ├── __init__.py
│   ├── main.py                # נקודת כניסה
│   ├── core.py                # Main loop
│   │
│   ├── # --- Data & Market ---
│   ├── market_data.py         # Alpaca + technical indicators
│   ├── market_hours.py        # סשנים, חגים, timezones
│   ├── market_condition.py    # זיהוי: trending/ranging/volatile
│   │
│   ├── # --- Strategies ---
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseStrategy class
│   │   ├── rsi_macd.py
│   │   ├── orb.py
│   │   ├── vwap_reversion.py
│   │   ├── volume_spike.py
│   │   ├── ema_cross.py
│   │   └── selector.py       # בחירה לפי סשן + מצב שוק
│   │
│   ├── # --- Scoring & Allocation ---
│   ├── scorer.py              # ציון אסטרטגיות
│   ├── allocator.py           # הקצאת תקציב
│   │
│   ├── # --- Execution ---
│   ├── trader.py              # ביצוע עסקאות Alpaca
│   ├── risk_manager.py        # כללים קשיחים
│   │
│   ├── # --- Memory ---
│   ├── memory.py              # SQLite
│   │
│   ├── # --- Communication ---
│   ├── telegram_bot.py        # התראות + פקודות
│   └── config.py              # הגדרות
│
├── strategies_config/         # JSON - מה Claude Coach משנה
│   ├── rsi_macd.json
│   ├── orb.json
│   ├── vwap_reversion.json
│   ├── volume_spike.json
│   ├── ema_cross.json
│   ├── scores.json            # ציונים נוכחיים
│   └── allocation.json        # הקצאה נוכחית
│
├── memory/
│   ├── learnings.md           # לקחים (קריא לאדם)
│   ├── strategy_performance.md
│   ├── trades_summary.md
│   └── trading.db             # SQLite
│
├── logs/
│   └── agent_YYYY-MM-DD.log
│
└── tests/
    └── ...
```

---

## ניהול סיכונים - Day Trading

```python
class DayTradingRiskManager:
    """כללים קשיחים - אף אחד לא משנה, כולל Claude"""

    MAX_POSITION_PCT = 0.05          # מקסימום 5% בעסקה
    OPENING_MAX_POSITION_PCT = 0.03  # 3% בפתיחה
    MAX_OPEN_POSITIONS = 3
    MANDATORY_STOP_LOSS = True
    MAX_STOP_LOSS_PCT = 0.02
    MAX_DAILY_LOSS_PCT = 0.03        # 3% הפסד → סוכן נעצר
    MAX_DAILY_TRADES = 20
    COOLING_AFTER_LOSSES = 3         # 3 הפסדים ברצף → 30 דקות
    CLOSE_ALL_BY = "15:50"           # ET
    NO_NEW_AFTER = "15:45"
    NO_OVERNIGHT = True
```

---

## עלויות

| שירות | עלות חודשית |
|--------|------------|
| Alpaca Paper Trading | $0 |
| Claude (Cowork Scheduled Task) | $0 (חלק מהמנוי) |
| Telegram Bot | $0 |
| Python + Libraries | $0 |
| TradingView (אופציונלי, בהמשך) | $0-$12.95 |
| **סה"כ** | **$0** |

---

## שלבי פיתוח

### שלב 1: תשתית (Day 1-2)
- [ ] venv + requirements + config + .env
- [ ] market_hours.py + market_condition.py
- [ ] memory.py (SQLite schema)
- [ ] חיבור Alpaca בסיסי

### שלב 2: נתוני שוק (Day 3)
- [ ] market_data.py (כל האינדיקטורים)
- [ ] screener (gaps, volume spikes)

### שלב 3: אסטרטגיות (Day 4-5)
- [ ] BaseStrategy + כל האסטרטגיות
- [ ] selector.py + scorer.py + allocator.py
- [ ] strategies_config/*.json

### שלב 4: מסחר (Day 6)
- [ ] trader.py + risk_manager.py
- [ ] core.py + main.py
- [ ] ריצה ראשונה!

### שלב 5: Telegram + Coach (Day 7-8)
- [ ] telegram_bot.py
- [ ] Cowork Scheduled Task ל-Claude Coach
- [ ] cron job ל-Rule Engine

### שלב 6: שיפורים (Day 9+)
- [ ] TradingView webhooks
- [ ] אסטרטגיות נוספות
- [ ] Dashboard
- [ ] Backtesting
