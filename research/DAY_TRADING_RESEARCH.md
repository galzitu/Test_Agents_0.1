# מחקר מעמיק: Day Trading - כל מה שהסוכן צריך לדעת

## 1. מהו Day Trading?

Day Trading הוא סגנון מסחר שבו כל הפוזיציות נפתחות ונסגרות באותו יום מסחר. אין החזקת מניות overnight. המסחר מבוסס על ניתוח טכני בלבד - קריאת גרפים, אינדיקטורים, ו-patterns.

### המציאות הקשה

- 90% מהסוחרים היומיים מפסידים כסף
- רק 1.6% מייצרים רווח אחרי עמלות
- הסיבה העיקרית: חוסר משמעת, לא חוסר ידע
- סוחרים מקצועיים מכוונים ל-10-20% תשואה שנתית, לא חודשית
- **יתרון של סוכן אוטומטי**: אין רגשות, אין revenge trading, משמעת מושלמת

---

## 2. אסטרטגיות טכניות - מדריך מלא

### 2.1 RSI + MACD Momentum Strategy

**מה זה RSI (Relative Strength Index)?**
- מודד את המומנטום של מחיר
- ערך 0-100
- מתחת ל-30 = oversold (המניה ירדה יותר מדי, צפי לעלייה)
- מעל 70 = overbought (המניה עלתה יותר מדי, צפי לירידה)
- Period מומלץ: 14

**מה זה MACD (Moving Average Convergence Divergence)?**
- מראה את הקשר בין שני ממוצעים נעים
- MACD Line = EMA(12) - EMA(26)
- Signal Line = EMA(9) של ה-MACD Line
- Histogram = MACD Line - Signal Line
- Bullish Crossover: MACD חוצה מעל ה-Signal → אות קנייה
- Bearish Crossover: MACD חוצה מתחת ל-Signal → אות מכירה

**הגדרות מהירות יותר (Linda Raschke): MACD(3,10,16)** - מגיב מהר יותר לשינויי מומנטום, מתאים ל-day trading.

**כללי הכניסה:**
```
קנייה כש:
├── RSI < 30 (oversold)
├── MACD Bullish Crossover (MACD חוצה מעל Signal)
├── Volume מעל ממוצע (לפחות 1.5x)
└── הכל קורה ביחד = אות חזק

מכירה כש:
├── RSI > 70 (overbought)
├── MACD Bearish Crossover
├── או: הגעה ל-take profit / stop loss
└── או: סוף יום מסחר (15:50 ET)
```

**Timeframe מומלץ**: 5 דקות
**סשנים מומלצים**: Opening (09:30-10:30) ו-Power Hour (14:30-16:00)

**תוצאות backtesting**: win rate של 60-73% כשמשלבים RSI + MACD ביחד (לעומת 40-50% כל אחד בנפרד). הקונפלואנס (confluence) של שני אינדיקטורים מפחית false signals.

---

### 2.2 Opening Range Breakout (ORB)

**העיקרון**: ב-15 הדקות הראשונות אחרי פתיחת השוק, נקבע "range" (טווח) של high ו-low. כשהמחיר פורץ מעל ה-range → long. כשפורץ מתחת → short.

**למה 15 דקות?** איזון בין מספיק נתונים לבין תפיסת ההזדמנות מוקדם. 5 דקות = רגיש מדי. 30 דקות = מאחר.

**כללי כניסה:**
```
Setup (09:30-09:45 ET):
├── סמן את ה-HIGH של 15 הדקות הראשונות
├── סמן את ה-LOW של 15 הדקות הראשונות
└── חשב range_size = HIGH - LOW

כניסה (09:45+ ET):
├── LONG: מחיר סוגר נר מעל HIGH + 0.2%
│   ├── Volume מעל ממוצע
│   ├── Stop Loss = LOW של ה-range
│   └── Take Profit = HIGH + 2 × range_size
│
├── SHORT: מחיר סוגר נר מתחת LOW - 0.2%
│   ├── Volume מעל ממוצע
│   ├── Stop Loss = HIGH של ה-range
│   └── Take Profit = LOW - 2 × range_size
│
└── סינון:
    ├── Range חייב להיות 0.5%-3% (קטן מדי = false breakout)
    ├── Volume spike ברגע ה-breakout
    └── עדיף עם gap מ-previous close (> 1%)
```

**מתי ORB עובד הכי טוב:**
- ימים עם gap משמעותי (מעל 1%)
- מניות עם pre-market volume גבוה
- ימים עם catalyst (חדשות, דוחות)

**מתי ORB נכשל:**
- ימים שקטים עם range קטן (< 0.5%)
- מניות עם volume נמוך
- שוק ranging בלי כיוון

---

### 2.3 VWAP Mean Reversion

**מה זה VWAP (Volume Weighted Average Price)?**
- ממוצע מחיר משוקלל לפי volume
- מחושב מחדש כל יום (מתאפס ב-09:30)
- נחשב ל-"fair value" - המחיר ההוגן של המניה
- אם המחיר מעל VWAP → המניה "יקרה" ביחס לממוצע
- אם מתחת → המניה "זולה" ביחס לממוצע

**העיקרון**: כשהמחיר סוטה משמעותית מה-VWAP, הוא נוטה לחזור אליו (mean reversion).

**כללי כניסה:**
```
LONG (קנייה):
├── מחיר נמצא מתחת VWAP ב-1%+ (או 2 סטיות תקן)
├── RSI מתחת 35 (אישור oversold)
├── נר bullish reversal (hammer, engulfing)
├── Stop Loss: מתחת לנקודת השפל האחרונה
└── Target: חזרה ל-VWAP

SHORT (מכירה בחסר):
├── מחיר מעל VWAP ב-1%+ (או 2 סטיות תקן)
├── RSI מעל 65 (אישור overbought)
├── נר bearish reversal (shooting star, engulfing)
├── Stop Loss: מעל נקודת השיא האחרונה
└── Target: חזרה ל-VWAP
```

**מתי VWAP Reversion עובד:**
- שוק RANGING (שקט, בלי מגמה ברורה)
- ADX מתחת ל-25 (אין מגמה חזקה)
- Mid-day session (10:30-14:30) - הסשן השקט ביותר

**מתי VWAP Reversion נכשל:**
- שוק TRENDING (מגמה חזקה)
- ADX מעל 25
- Opening session (תנודתיות גבוהה מדי)
- ימים עם חדשות/דוחות חשובים

**טיפ קריטי**: לא לסחור VWAP reversion ב-15 הדקות הראשונות - "head fakes" נפוצים בפתיחה.

---

### 2.4 Volume Spike Momentum

**העיקרון**: כשהvolume קופץ פתאום (2-3x מהממוצע), זה סימן שמשהו קורה. אם ה-spike מלווה בתנועת מחיר חזקה - נכנסים לכיוון התנועה.

**כללי כניסה:**
```
LONG:
├── Volume > 3x ממוצע (volume spike)
├── נר ירוק חזק (close > open)
├── מחיר מעל EMA(9)
├── Stop Loss: מתחת ל-low של נר ה-spike
├── Take Profit: 2% או אחרי 30 דקות (מה שמגיע קודם)
└── Hold max: 30 דקות (volume spikes הם אירועים קצרי טווח)

SHORT:
├── Volume > 3x ממוצע
├── נר אדום חזק (close < open)
├── מחיר מתחת EMA(9)
├── Stop Loss: מעל high של נר ה-spike
└── Take Profit: 2%
```

**סוגי volume spikes:**
```
1. Breakout Spike:
   Volume + price breakout מעל resistance
   → נכנסים לכיוון ה-breakout

2. Exhaustion Spike:
   Volume spike אחרי תנועה ארוכה באותו כיוון
   → סימן שהמגמה מתמצית, צפי ל-reversal!
   → זהירות: לא להיכנס לכיוון ה-spike

3. News Spike:
   Volume spike בגלל חדשות / דוחות
   → מסוכן, ספרדים רחבים, חכה להתייצבות
```

**אינדיקטורים משלימים:**
- OBV (On-Balance Volume) - מאשר את כיוון ה-volume
- RSI - מאשר מומנטום
- MACD - מאשר כיוון מגמה

---

### 2.5 EMA Crossover (9/21)

**העיקרון**: כשה-EMA המהיר (9) חוצה מעל ה-EMA האיטי (21) → אות קנייה. כשחוצה מתחת → אות מכירה.

**כללי כניסה:**
```
LONG: EMA(9) חוצה מעל EMA(21)
├── Volume מעל ממוצע
├── RSI בטווח 40-65 (לא overbought)
├── Stop Loss: מתחת EMA(21)
└── Take Profit: 2-3%

SHORT: EMA(9) חוצה מתחת EMA(21)
├── Volume מעל ממוצע
├── RSI בטווח 35-60 (לא oversold)
├── Stop Loss: מעל EMA(21)
└── Take Profit: 2-3%
```

**בעיה מוכרת**: False signal rate של 57-76% בשוק מניות! EMA crossover לבד לא מספיק. חייבים אישור מאינדיקטורים אחרים.

**Timeframe**: 5 דקות
**הערה**: אסטרטגיה זו מתאימה יותר לשוק trending. בשוק ranging היא מייצרת הרבה false signals.

---

### 2.6 Bollinger Band Squeeze

**מה זה?** Bollinger Bands (20 periods, 2 standard deviations) מתכווצות כשהתנודתיות יורדת. הסיקוז (squeeze) מסמן שפיצוץ מחיר קרב.

**כללי כניסה:**
```
זיהוי Squeeze:
├── Bollinger Bands מתקרבות אחת לשנייה
├── ATR יורד (תנודתיות נמוכה)
└── Bandwidth < threshold (למשל 4%)

כניסה:
├── LONG: נר סוגר מעל ה-Upper Band
│   ├── Volume spike (אישור)
│   ├── RSI עולה
│   └── Stop Loss: מתחת ה-Lower Band
│
├── SHORT: נר סוגר מתחת ה-Lower Band
│   ├── Volume spike
│   ├── RSI יורד
│   └── Stop Loss: מעל ה-Upper Band
│
└── Target: הצד הנגדי של ה-band, או 2-3x ה-bandwidth

טיפ: לא לקנות רק כי הבנד צרות - חכה ל-breakout עם volume!
```

**Timeframe**: 5 דקות עד שעה
**סשנים**: עובד בכל סשן, אבל breakouts חזקים יותר בפתיחה וב-power hour

---

## 3. זיהוי מצב שוק (Market Condition)

**זה המפתח לכל הסיפור.** אסטרטגיה לא "טובה" או "רעה" - היא מתאימה למצב שוק מסוים.

### ADX (Average Directional Index) - האינדיקטור הכי חשוב

```
ADX < 20:  שוק RANGING (חלש, בלי מגמה)
           → הפעל: VWAP Reversion, Bollinger Squeeze
           → כבה: Momentum, ORB, EMA Cross

ADX 20-25: תקופת מעבר (לא ברור)
           → הפעל: הכל, אבל position size קטן
           → זהירות: false signals

ADX > 25:  שוק TRENDING (מגמה חזקה)
           → הפעל: RSI_MACD, EMA Cross, Volume Spike
           → כבה: VWAP Reversion!

ADX > 40:  מגמה חזקה מאוד
           → Trend following בלבד
           → אל תנסה mean reversion!
```

### ATR (Average True Range) - מדידת תנודתיות

```
ATR% (ATR / Price):
├── < 1%:  תנודתיות נמוכה → position size גדול יותר
├── 1-2%:  תנודתיות נורמלית → position size רגיל
├── 2-3%:  תנודתיות גבוהה → position size קטן
└── > 3%:  מסוכן! → position size מינימלי או לא לסחור

שימוש ל-Stop Loss:
Stop Loss = Entry Price - (ATR × 1.5)
Take Profit = Entry Price + (ATR × 3.0)
→ Risk:Reward = 1:2
```

### VIX (Fear Index) - מדד הפחד

```
VIX < 15:  שוק רגוע, אופטימי → אסטרטגיות רגילות
VIX 15-20: נורמלי → הכל בסדר
VIX 20-30: מתח → position size קטן, stop loss צמוד
VIX > 30:  פאניקה → מסוכן מאוד, שקול לא לסחור
VIX > 40:  משבר → אל תסחור (אלא אם אתה מומחה)
```

### טבלת התאמה: מצב שוק ↔ אסטרטגיה

```
                │ Trending │ Ranging │ Volatile │ Quiet
════════════════╪══════════╪═════════╪══════════╪═══════
RSI + MACD      │ ✅✅     │ ⚠️      │ ✅       │ ❌
ORB             │ ✅       │ ❌      │ ✅✅     │ ❌
VWAP Reversion  │ ❌❌     │ ✅✅    │ ❌       │ ⚠️
Volume Spike    │ ✅       │ ⚠️      │ ✅✅     │ ❌
EMA Cross       │ ✅       │ ❌❌    │ ⚠️       │ ❌
Bollinger Sq.   │ ⚠️       │ ✅      │ ✅       │ ⚠️
```

---

## 4. ניהול סיכונים - הכי חשוב!

### כלל ה-1%
**לעולם לא לסכן יותר מ-1% מהתיק בעסקה בודדת.**

```
דוגמה:
תיק = $100,000
סיכון מקסימלי = $1,000 (1%)
מחיר מניה = $150
Stop Loss = $148 (הפרש = $2)
Position Size = $1,000 / $2 = 500 מניות
```

### Position Sizing Formula

```python
def calculate_position_size(account_balance, risk_pct, entry_price, stop_loss):
    risk_amount = account_balance * risk_pct      # כמה כסף מוכנים להפסיד
    risk_per_share = abs(entry_price - stop_loss)  # הפסד למניה
    shares = risk_amount / risk_per_share          # כמה מניות
    return int(shares)

# דוגמה:
shares = calculate_position_size(
    account_balance=100_000,
    risk_pct=0.01,           # 1%
    entry_price=150.00,
    stop_loss=148.00
)
# = 500 מניות
```

### כללי Day Trading

```
1. Stop Loss חובה על כל עסקה - בלי יוצא מהכלל!
2. Risk:Reward מינימלי 1:2 (מסכן $1 כדי להרוויח $2)
3. מקסימום 3 פוזיציות פתוחות במקביל
4. מקסימום 3% הפסד יומי → הסוכן נעצר
5. 3 הפסדים ברצף → 30 דקות cooling period
6. סגירת הכל לפני 15:50 ET
7. אין פוזיציות חדשות אחרי 15:45 ET
8. מעולם, אבל מעולם, לא overnight!
9. התחל עם 0.5% risk, עלה ל-1% רק אחרי שמוכח
10. לא לסחור ב-10 דקות לפני/אחרי FOMC / דוחות מרכזיים
```

### Trailing Stop

```
במקום stop loss קבוע, stop loss שעוקב אחרי המחיר:
├── מתחיל ב-ATR × 1.5 מתחת למחיר
├── עולה עם המחיר (לעולם לא יורד!)
├── נועל רווחים תוך כדי תנועה
└── יוצא כשהמחיר מתהפך

דוגמה:
Entry: $150, Initial Stop: $148
מחיר עולה ל-$153 → Stop עולה ל-$151
מחיר עולה ל-$155 → Stop עולה ל-$153
מחיר יורד ל-$153 → נפגע! יוצאים ברווח +$3
```

---

## 5. טעויות נפוצות שהסוכן צריך להימנע מהן

### 5 הטעויות הקטלניות

```
1. Overtrading (מסחר יתר)
   ├── בעיה: 20+ עסקאות ביום = עמלות + טעויות
   ├── פתרון: מקסימום 10-15 עסקאות
   └── הסוכן: מגבלת MAX_DAILY_TRADES

2. No Stop Loss
   ├── בעיה: "זה יחזור" → הפסד 10-20%
   ├── פתרון: MANDATORY_STOP_LOSS = True
   └── הסוכן: לא מבצע עסקה בלי stop loss

3. Revenge Trading
   ├── בעיה: הפסדתי → מכפיל position → מפסיד יותר
   ├── פתרון: cooling period אחרי הפסדים
   └── הסוכן: 3 הפסדים = 30 דקות הפסקה (אין רגשות!)

4. Chasing (רדיפה אחרי מחיר)
   ├── בעיה: המניה כבר עלתה 5%, קונים "כי עולה"
   ├── פתרון: כניסה רק לפי אותות אסטרטגיה
   └── הסוכן: לא נכנס אם המחיר רחוק מ-entry level

5. Position Size גדול מדי
   ├── בעיה: "הפעם אני בטוח" → all-in → disaster
   ├── פתרון: מקסימום 3-5% מהתיק
   └── הסוכן: risk_manager חוסם אוטומטית
```

### יתרון אוטומטי

הדבר הכי חזק בסוכן אוטומטי: **אין רגשות**.
- לא מפחד להפסיד (מבצע stop loss בלי היסוס)
- לא חמדן (לוקח take profit כשצריך)
- לא עושה revenge trading (מכבד cooling period)
- לא מושפע מחדשות / פאניקה
- עוקב אחרי הכללים ב-100%

---

## 6. שעות מסחר - מתי לסחור ומתי לא

### הסשנים (US Eastern Time → Israel Standard Time)

```
PRE-MARKET (04:00-09:30 ET = 11:00-16:30 IST):
├── נזילות נמוכה מאוד
├── ספרדים רחבים
├── רק Limit Orders!
├── שימוש: סריקת gaps, בניית watchlist
└── מסחר: לא מומלץ לסוכן (בשלב ראשון)

OPENING BELL (09:30-10:30 ET = 16:30-17:30 IST):
├── "The Money Session" - הכי הרבה הזדמנויות
├── תנודתיות מקסימלית
├── Volume הגבוה ביותר ביום
├── Gap fills, breakouts, momentum plays
├── סיכון: false breakouts נפוצים ב-5 דקות ראשונות
└── מומלץ: ORB, RSI_MACD, Volume Spike

MID-DAY (10:30-14:30 ET = 17:30-21:30 IST):
├── "The Chop Zone" - השוק הכי שקט
├── הרבה false signals
├── Mean reversion עובד הכי טוב פה
├── Momentum לא עובד!
└── מומלץ: VWAP Reversion, Bollinger (או לא לסחור)

POWER HOUR (14:30-16:00 ET = 21:30-23:00 IST):
├── תנודתיות עולה שוב
├── סוחרים מוסדיים סוגרים פוזיציות
├── Momentum חוזר לעבוד
├── החלטה: לסגור הכל או לנסות עוד עסקה?
└── מומלץ: RSI_MACD, Volume Spike

CLOSE (15:50-16:00 ET):
├── סוגרים הכל! Day Trading = לא overnight
└── הסוכן סוגר כל פוזיציה פתוחה אוטומטית
```

---

## 7. Screener - איך למצוא מניות לסחור

### Pre-Market Scan (08:00 ET)

```
סינון מניות מעניינות ליום:
├── Gap Up > 2%: מניות שפתחו גבוה מאתמול
│   → פוטנציאל ל-ORB, Momentum
│
├── Gap Down > 2%: מניות שפתחו נמוך
│   → פוטנציאל ל-gap fill, reversal
│
├── Pre-market Volume > 2x average
│   → משהו קורה, כדאי לעקוב
│
├── Earnings Today: מניות עם דוחות כספיים
│   → תנודתיות גבוהה צפויה
│
└── News Catalyst: חדשות חשובות
    → FDA approval, partnership, lawsuit...
```

### Criteria ל-Day Trading

```
מניות שמתאימות:
├── מחיר: $10-$300 (לא penny stocks, לא יקרות מדי)
├── Volume יומי ממוצע: > 500K (נזילות מספיקה)
├── Spread: < 0.1% (ספרד צר)
├── ATR: 1-3% (מספיק תנועה, לא מסוכן מדי)
└── Float: > 10M shares (לא מניות "דלות")

מניות להימנע מהן:
├── Penny stocks (< $5) - מניפולציות, spread רחב
├── Low volume (< 100K) - לא נזילות
├── Bio/pharma לפני FDA - binary events
├── IPO ביום הראשון - לא predictable
└── מניות בהליך פשיטת רגל
```

---

## 8. אינדיקטורים טכניים - מדריך מהיר

| אינדיקטור | מה מודד | איך לקרוא | Timeframe |
|-----------|---------|-----------|-----------|
| **RSI(14)** | מומנטום | < 30 = oversold, > 70 = overbought | 5min, 15min |
| **MACD(12,26,9)** | מגמה + מומנטום | Crossovers = שינוי כיוון | 5min |
| **VWAP** | מחיר הוגן | מעל = יקר, מתחת = זול | Intraday only |
| **EMA(9)** | מגמה קצרה | מחיר מעל = bullish | 1min, 5min |
| **EMA(21)** | מגמה בינונית | מחיר מעל = bullish | 5min |
| **Bollinger(20,2)** | תנודתיות | Squeeze = breakout צפוי | 5min, 15min |
| **ATR(14)** | תנודתיות | גבוה = מסוכן, נמוך = שקט | 5min, daily |
| **ADX(14)** | חוזק מגמה | > 25 = trending, < 20 = ranging | 15min, daily |
| **OBV** | Volume flow | עולה = buying pressure | 5min |
| **Stochastic RSI** | RSI של RSI | 0-20 = oversold extreme | 5min |

**כלל זהב**: **לעולם לא לסמוך על אינדיקטור אחד.** חפש confluence - כשלפחות 2-3 אינדיקטורים מסכימים.

---

## 9. סיכום: מה הסוכן שלנו צריך לדעת

```
1. יש לו 5-6 אסטרטגיות מוגדרות עם כללים ברורים
2. הוא מזהה מצב שוק (trending/ranging/volatile) ובוחר אסטרטגיה מתאימה
3. הוא לא משנה פרמטרים - רק לומד מתי להשתמש בכל אסטרטגיה
4. ניהול סיכונים קשיח - stop loss חובה, 1% risk, daily limit
5. סוגר הכל לפני סוף היום - אף פעם overnight
6. Claude Coach מנתח בסוף היום ומשפר activation conditions
7. אין רגשות = היתרון הגדול שלו
```
