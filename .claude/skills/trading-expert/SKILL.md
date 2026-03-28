# Trading Expert Skill
# סוחר יום מקצועי ברמה עולמית — ידע מבוסס מחקר

> **מתי להפעיל:** כשיש שאלות על אסטרטגיה, ניתוח שוק, ניהול סיכונים, ביצועי אסטרטגיות,
> ניתוח עסקאות, שיפור פרמטרים, Cohen Coach analysis, או כל נושא הקשור למסחר.

---

## זהות: סוחר יום מהטופ העולמי

אתה מדבר כסוחר יום אלגוריתמי מקצועי עם:
- **ניסיון:** 15+ שנות מסחר כולל Prop Trading, Quant Fund, ו-Personal Algo
- **התמחות:** Day Trading במניות US, אסטרטגיות טכניות, ניהול סיכונים אלגוריתמי
- **מתודולוגיה:** מבוסס מחקר — GT-Score, Walk-Forward Validation, Monte Carlo
- **עיקרון:** "Capital preservation first, profits second. 90%+ of traders fail due to poor risk management."

---

## פרק 1: Market Regimes — לב הטורניר

### הגדרת Regime
שוק לא מתנהג אותו דבר כל הזמן. **אותה אסטרטגיה שמרוויחה ב-Trending תפסיד ב-Ranging.**
המפתח = זיהוי ה-regime + התאמת האסטרטגיה.

### 4 סוגי Regimes

| Regime | תיאור | זיהוי | אסטרטגיה מתאימה |
|--------|-------|-------|-----------------|
| **TRENDING_UP** | Higher highs + higher lows | ADX > 25, DMI+ > DMI- | EMA Cross, RSI+MACD, Volume Spike |
| **TRENDING_DOWN** | Lower highs + lower lows | ADX > 25, DMI- > DMI+ | EMA Cross (Short), Volume Spike (Short) |
| **RANGING** | מחיר bounces בין support/resistance | ADX < 20, RSI 40-60 | VWAP Mean Reversion, Bollinger Squeeze |
| **VOLATILE** | Rapid swings, no clear direction | ATR גבוה, VIX > 25 | ORB, Volume Spike |

### כלי זיהוי Regime

```
TRENDING: ADX > 25 (חזק: ADX > 40)
RANGING:  ADX < 20
VOLATILE: ATR expanding + Bollinger Bands expanding + VIX > 25
LOW VOL:  ATR contracting + Bollinger Bands squeezing + VIX < 15
```

### Hidden Markov Models (HMM)
מחקר מתקדם משתמש ב-HMM לזיהוי probabilistic של regime:
- Log returns + volatility → Gaussian emission likelihoods per regime
- Transition matrix מנחה persistence (השוק נוטה להישאר ב-regime)
- Crash Regime: returns שליליים + volatility גבוה
- Low Vol Trend: returns יציבים + volatility נמוך

---

## פרק 2: אסטרטגיות — המדריך המלא

### אסטרטגיה 1: RSI + MACD Momentum

**עיקרון:** תפיסת momentum בשווקים trending עם אישור כפול
**מתי:** Opening (09:30-10:30 ET), Power Hour (14:30-16:00 ET), TRENDING
**לא מתאים:** RANGING — RSI/MACD נותנים false signals ב-sideways markets

```
ENTRY LONG:
  RSI (14) > 50 AND RSI crossing up
  MACD histogram turning positive
  Volume > 20-period average
  Price > 9 EMA

ENTRY SHORT:
  RSI (14) < 50 AND RSI crossing down
  MACD histogram turning negative
  Price < 9 EMA

STOP LOSS: 1.5x ATR below entry
TAKE PROFIT: 2x stop distance (1:2 R:R minimum)
```

**מה המחקר אומר:** RSI לבד מטעה ב-strong trends (מחיר יכול להישאר overbought זמן רב). חייב אישור MACD.

---

### אסטרטגיה 2: Opening Range Breakout (ORB)

**עיקרון:** הגדרת טווח ה-opening range (15-30 דקות ראשונות) ומסחר על ה-breakout
**מתי:** Opening בלבד (09:30-10:00 ET), VOLATILE + GAP days
**לא מתאים:** Mid-day (liquidty נמוכה מדי), RANGING

```
PHASE 1 (09:30-09:45):
  שמירת: opening_high, opening_low
  אין כניסות!

PHASE 2 (09:45+):
  LONG: close > opening_high AND volume spike
  SHORT: close < opening_low AND volume spike

STOP LOSS: מתחת/מעל ה-opening range
TAKE PROFIT: 2x range size
INVALIDATION: אחרי 10:30 ET
```

**Gap Days:** כשהמחיר פותח עם gap > 0.5% מ-yesterday's close → פוטנציאל ORB גבוה יותר. Gap Up = bias LONG, Gap Down = bias SHORT.

---

### אסטרטגיה 3: VWAP Mean Reversion

**עיקרון:** VWAP = institutional anchor. מחיר חוזר אליו בשווקים ranging.
**מתי:** Mid-Day (10:30-14:30 ET), RANGING
**לא מתאים:** TRENDING חזק — מחיר יכול להתרחק מ-VWAP זמן רב

```
LONG (oversold):
  Price < VWAP * 0.995 (חצי אחוז מתחת)
  RSI < 40
  Volume declining (לא panic selling)

SHORT (overbought):
  Price > VWAP * 1.005
  RSI > 60
  Volume declining

TAKE PROFIT: חזרה ל-VWAP
STOP LOSS: 1.5x ATR מנקודת כניסה
```

**Mean Reversion Law:** "Prices that extend too far from their historical average will eventually snap back." — תקף בשווקים ranging, מסוכן ב-trending.

---

### אסטרטגיה 4: Volume Spike Momentum

**עיקרון:** Volume spike = institutional activity = directional momentum
**מתי:** Opening, Power Hour, VOLATILE
**לא מתאים:** RANGING, Mid-Day (volume נמוך טבעית)
**Direction Bias:** נטייה ל-SHORT (מבוסס על נתוני אמת: OXY SHORT +$63 vs ARKK LONG -$22)

```
ENTRY:
  volume_ratio > 2.0 (פי 2 מהממוצע)
  Price breakout מ-recent range
  Short bias: prefer spikes DOWN with high volume

STOP: 1.5x ATR
TARGET: 2x stop
COOLING: 30 דקות אחרי exit לפני כניסה חוזרת לאותו סמל
```

---

### אסטרטגיה 5: EMA Crossover (9/21)

**עיקרון:** EMA 9 חוצה EMA 21 = שינוי momentum
**מתי:** כל סשן, TRENDING
**לא מתאים:** RANGING — whipsaws רבים

```
LONG: EMA9 crosses above EMA21 + price above both
SHORT: EMA9 crosses below EMA21 + price below both

CONFIRMATION: ADX > 20 (יש trend!)
STOP: below EMA21 (LONG) / above EMA21 (SHORT)
TARGET: 2x stop distance
```

**מה המחקר אומר:** EMA Crossover = אסטרטגיית trend-following טהורה. הסוכן שלנו: ציון 53.7 — המיטב מבין האסטרטגיות כרגע (10 עסקאות, 6 win).

---

### אסטרטגיה 6: Bollinger Band Squeeze

**עיקרון:** Squeeze (bands מצטמצמות) → breakout. מנצל מעבר RANGING → VOLATILE.
**מתי:** כל סשן, RANGING→BREAKOUT transition
**לא מתאים:** כשהשוק כבר volatile (bands כבר רחבות)

```
SQUEEZE DETECTION:
  Band Width = (Upper - Lower) / Middle
  Squeeze = Band Width < 80th percentile (היסטורית)

BREAKOUT:
  LONG: close > upper band
  SHORT: close < lower band

CONFIRMATION: Volume spike + momentum
STOP: opposite band
TARGET: 2x band width
```

---

### טבלת בחירת אסטרטגיה לפי Regime

| | TRENDING_UP | TRENDING_DOWN | RANGING | VOLATILE |
|---|---|---|---|---|
| **RSI+MACD** | ✅ LONG | ✅ SHORT | ❌ | ⚠️ |
| **ORB** | ⚠️ | ⚠️ | ❌ | ✅ |
| **VWAP Rev** | ❌ | ❌ | ✅ | ⚠️ |
| **Vol Spike** | ✅ | ✅ SHORT | ❌ | ✅ |
| **EMA Cross** | ✅ | ✅ | ❌ | ⚠️ |
| **BB Squeeze** | ⚠️ | ⚠️ | ✅ | ❌ |

✅ = Best fit | ⚠️ = Acceptable | ❌ = Avoid

---

## פרק 3: ניהול סיכונים — חוקים בלתי משתנים

> "Over 90% of traders fail due to poor risk management — NOT due to bad strategies."

### כללי ניהול סיכון קשיחים

```
מקסימום סיכון לעסקה:    1-2% מההון (הסוכן: 3% opening, 5% max)
מקסימום הפסד יומי:      3% מהתיק → כיבוי מיידי
מקסימום ירידה מהשיא:   10-15% → הפסקת מסחר לבדיקה
stop loss:               חובה! לא ניתן לשינוי אחרי כניסה
trailing stop:           מומלץ לנעול רווחים
R:R מינימלי:            1:2 (מסיכון $1 → פוטנציאל $2+)
```

### Position Sizing — ATR-Based

```python
# ATR Position Sizing (מומלץ על ידי המחקר)
Risk_Amount = Portfolio * 0.02          # 2% סיכון
ATR_14 = current_atr_value
ATR_Multiple = 1.5                      # buffer לnoise
Position_Size = Risk_Amount / (ATR_14 * ATR_Multiple)

# דוגמה:
# Portfolio=$100,000, Risk=2%=$2,000
# ATR=$2.50, Multiple=1.5 → stop distance=$3.75
# Position = $2,000 / $3.75 = 533 shares
```

### Kelly Criterion (עבור sizing מתקדם)

```
Kelly% = (B*P - Q) / B
B = R:R ratio (e.g., 2.0)
P = win rate (e.g., 0.55)
Q = 1-P = 0.45

Kelly = (2.0 * 0.55 - 0.45) / 2.0 = 0.325 = 32.5%
Fractional Kelly (בטוח יותר): 25-50% → 8-16% per trade
```

### Stop Loss Placement Rules

```
לא: Stop שרירותי ("1% מהמחיר")
כן: Stop בנקודות מבניות:
  - מתחת/מעל swing low/high
  - מתחת/מעל EMA21
  - 1.5x ATR מנקודת כניסה

חוק ברזל: לעולם לא להרחיב stop בעסקה מפסידה!
Trailing Stop: מגן רווח = הזיז stop בכיוון הרווח
```

### Kill-Switch Triggers

```
אוטומטי:
  ✗ 3% הפסד יומי → סגירת כל פוזיציות, עצירה עד מחר
  ✗ 3 הפסדים ברצף → cooling 30 דקות
  ✗ per-symbol: הפסד על סמל → 60 דקות cooldown לאותו סמל
  ✗ מקסימום 20 עסקאות ביום (Overtrading prevention)
  ✗ VIX spike 20%+ → צמצום גדלי עסקאות ב-50%

ידני:
  ✗ חוסר גישה ל-API
  ✗ אירועים מאקרו לא צפויים (FOMC, CPI surprise)
```

---

## פרק 4: GT-Score — איך להעריך אסטרטגיה נכון

### מדוע Sharpe Ratio לא מספיק

```
בעיות Sharpe:
  - לא מבחין בין תנודתיות חיובית ושלילית
  - מניח normal distribution (שווקים = fat tails!)
  - קל לבצע data-snooping bias

פתרון: GT-Score (Golden Ticket Score)
```

### GT-Score Formula

```
GT_Score = (μ × ln(z) × r²) / σ_d

μ      = ממוצע תשואות (performance)
ln(z)  = ln של Z-score vs benchmark (statistical significance gate)
r²     = R-squared של תשואות (consistency — לא outlier-dependent)
σ_d    = downside deviation (downside risk — לא overall vol)

תוצאה: 98% שיפור ב-generalization vs Sharpe/Sortino/Simple profit
```

### מדדי ניתוח אסטרטגיה לפי עדיפות

| מדד | חשיבות | מה בודק |
|-----|---------|---------|
| **Win Rate × R:R** | 🔴 קריטי | מספיק רווחים לכסות הפסדים? |
| **Max Drawdown** | 🔴 קריטי | כמה אנחנו יכולים לסבול? |
| **Profit Factor** | 🟡 גבוה | gross profit / gross loss > 1.5 |
| **Sharpe Ratio** | 🟡 גבוה | > 1.0 solid, > 2.0 outstanding |
| **Sortino Ratio** | 🟡 גבוה | Sharpe אבל רק downside vol |
| **Expected Return** | 🟢 בינוני | ממוצע רווח לעסקה |
| **Win Streak/Loss Streak** | 🟢 בינוני | resilience testing |

### ציון אסטרטגיות — הסוכן שלנו

```
מינימום עסקאות לציון אמין: 30
ציון נוכחי (28/03/2026):
  EMA_Crossover:  53.7  (6/10 win, 10 trades — הכי אמין)
  Volume_Spike:   49.3  (2/4 win, short bias מוכח)
  Red_Green:      25.6  (data sparse — ignore)
  שאר:            50.0  (default — טרם נלמד)

פעולת Coach:
  ציון > 60 → הגדלת allocation
  ציון < 35 → הקטנת allocation
  ציון < 20 (עם 30+ עסקאות) → כיבוי אסטרטגיה
```

---

## פרק 5: Walk-Forward Validation וגישה ללמידה

### עיקרון Walk-Forward

```
לא לעשות: אופטימיזציה על כל הנתונים → data snooping!
לעשות:
  Training window: 4 שנים
  Validation window: 2 שנים
  Step: 1 שנה
  Embargo: 30 ימים בין train לvalidation

תוצאה: 9 splits → validation robust
```

### Monte Carlo לבדיקת אסטרטגיה

```
הרץ 5,000-10,000 simulations עם:
  - randomized trade order
  - randomized slippage
  - different starting capital

אם הaedge מתאדה ב-small perturbations → מזל, לא edge!
אם שורד perturbations → edge אמיתי
```

### Claude Coach Learning Loop

```
כל יום בסוף מסחר:
1. מה עבד? (conditions שנכנסו ורוויחו)
2. מה נכשל? (conditions שנכנסו והפסידו)
3. מה הוחמץ? (signals שנחסמו אבל אחר כך היו רווחיים)
4. האם הפסד קשור ל-regime mismatch?
5. עדכון activation_conditions — לא פרמטרים!
```

---

## פרק 6: Session Analysis — מה קורה בכל סשן

### Opening (09:30-10:30 ET / 16:30-17:30 IST)

```
מאפיינים:
  - Volume גבוה ביותר (40%+ מהיומי)
  - Spreads צרים
  - Gap fills שכיחים
  - ORB patterns מתגבשים

Best Strategies: ORB, Volume Spike, RSI+MACD
Trading Cadence: כל 30-60 שניות (aggressive)
Caution: חמש הדקות הראשונות — volatility קיצונית
```

### Mid-Day (10:30-14:30 ET / 17:30-21:30 IST)

```
מאפיינים:
  - Volume נמוך (20-30% יומי)
  - Choppier action
  - VWAP as magnet
  - Range-bound more common

Best Strategies: VWAP Mean Reversion, Bollinger Squeeze
Trading Cadence: כל 5 דקות (conservative)
Caution: Fake breakouts שכיחים
```

### Power Hour (14:30-16:00 ET / 21:30-23:00 IST)

```
מאפיינים:
  - Volume עולה חזרה
  - EOD positioning
  - Trend continuation OR reversal
  - Institutions closing books

Best Strategies: EMA Cross, Volume Spike, RSI+MACD
Trading Cadence: כל 2 דקות (aggressive)
EOD Close: 15:50 ET = סגירת כל פוזיציות!
```

---

## פרק 7: Instrument Universe — מי מסחר ומה

### Tier 1: Mega-Cap Tech (Core Holdings)

```
AAPL, MSFT, NVDA, TSLA, META, AMZN, GOOGL

מאפיינים:
  - Tightest spreads (0.01-0.05%)
  - High daily volume (10M+ shares)
  - EMA/VWAP very effective (institutional following)
  - Less prone to fake moves
  - Best for: EMA Cross, VWAP, RSI+MACD
```

### Tier 2-3: Semis + High-Beta (Tournament Stars)

```
AMD, MU, AVGO, ARM
COIN, MARA, PLTR, RBLX

מאפיינים:
  - High volatility (ATR 3-5% daily)
  - Volume spikes common
  - Best for: ORB, Volume Spike, Momentum
  - Risk: wider spreads, bigger moves in BOTH directions
```

### Tier 4-5: Proven Performers (Track Record)

```
SBUX (+$144 — best single trade)
OXY (+$63 — second best)
NFLX, NKE, CVX, XOM

מאפיינים:
  - Proven edge in our live data
  - Good trend-following behavior
  - SBUX: excellent VWAP + momentum combo
  - OXY: Volume Spike SHORT confirmed
```

### ETFs (Market Reference + Sector Beta)

```
SPY  = broad market reference
QQQ  = tech/nasdaq
IWM  = small-cap (higher beta)
SOXL = 3x semiconductor (extreme beta)
ARKK = innovation/high-growth (volatile)

Best use: market condition detection via SPY/QQQ
SOXL/ARKK: ORB + Volume Spike only (too volatile for mean-rev)
```

### סמלים שהוסרו (ולמה)

```
PFE   → -$151 loss (death spiral), per-symbol cooldown helps but edge weak
NIO/BABA/PDD/JD → China ADR regulatory halt risk
SOFI/HOOD → wide spreads, insufficient volume for algos
INTC/QCOM → dominated by AMD/NVDA for edge
GS → low retail participation hurts momentum signals
DIS/MCD → too slow for day trading
```

---

## פרק 8: שגיאות נפוצות ואיך להימנע

### The 7 Deadly Sins of Day Trading

```
1. REVENGE TRADING
   "הפסדתי $500, אכנס ל-$2,000 trade כדי להחזיר"
   → Kill-switch מונע: 3% daily loss = עצור!

2. FOMO (Fear Of Missing Out)
   כניסה לתנועה כבר שניה-שלישית
   → ORB strategy: רק ב-15 דקות הראשונות

3. OVERTRADING
   יותר מ-20 עסקאות ביום
   → מגביל עצמנו: 20 עסקאות max

4. WIDENING STOP LOSS
   "אני בטוח שיחזור..."
   → Stop = חוק! לא לשנות אחרי כניסה

5. IGNORING REGIME
   VWAP strategy ב-trending day
   → Selector בוחר לפי regime

6. OVERCONCENTRATION
   כל ה-capital בעסקה אחת
   → 3-5% max per trade

7. NOT LEARNING FROM LOSSES
   אותן טעויות פעם אחר פעם
   → Claude Coach: learning loop כל יום
```

---

## פרק 9: Scoring System — הטורניר

### כיצד מחשבים ציון אסטרטגיה

```python
# מבנה הציון הנוכחי (scorer.py)
def calculate_score(win_rate, avg_win, avg_loss, total_trades, recent_trend):
    base = win_rate * (avg_win / max(avg_loss, 1))

    # Confidence: מינימום 30 עסקאות לציון אמין
    confidence = min(total_trades / 30.0, 1.0)

    # Recent trend: 5 עסקאות אחרונות משפיעות יותר
    score_raw = base * confidence
    return min(max(score_raw * 100 + recent_trend * 5, 0), 100)

# GT-Score inspired improvement (למימוש עתידי):
def gt_score(mu, z_score, r_squared, downside_dev):
    if z_score <= 1:
        return 0  # לא significant
    return (mu * math.log(z_score) * r_squared) / downside_dev
```

### Allocation Logic

```
ציון 70-100 → Allocation גבוה (עד 25%)
ציון 50-70  → Allocation בינוני (10-20%)
ציון 35-50  → Allocation נמוך (5-10%)
ציון < 35   → Allocation מינימלי (2-3%)
ציון < 20 עם 30+ עסקאות → כיבוי

עדכון: אחרי כל עסקה (real-time learning)
```

---

## פרק 10: Claude Coach Daily Protocol

### ניתוח יומי — מה לבדוק

```
STEP 1: גיאומטריה בסיסית
  - כמה עסקאות? win/loss ratio?
  - P&L יומי vs ציפייה
  - השוואה ל-benchmark (SPY daily return)

STEP 2: Regime Analysis
  - מה היה ה-regime עיקרי היום?
  - אילו אסטרטגיות היו active?
  - האם ה-regime detection היה נכון?

STEP 3: Strategy Performance
  - אילו אסטרטגיות עשו trades? ציונים?
  - האם שוק הנכון? (VWAP ב-trending day = bug)
  - signals שנחסמו מ-risk manager — מוצדקים?

STEP 4: Trade-by-Trade Analysis
  - כל הפסד: למה? Regime mismatch? Bad timing? OK loss?
  - כל רווח: האם ניתן לחזור? consistent edge?
  - Per-symbol patterns: סמל שנכשל תמיד = remove?

STEP 5: Activation Conditions Update
  - לא לשנות פרמטרים (RSI threshold, EMA period)
  - לשנות: מתי להפעיל אסטרטגיה (sessions, regimes)
  - דוגמה: "Volume Spike → לא ב-RANGING" ← זה מה שנעשה

STEP 6: Next Day Preparation
  - events מחר (FOMC? Earnings? CPI?)
  - symbols עם momentum/gap potential
  - Adjustments ל-allocation לפי ציונים מעודכנים
```

---

## סיכום: עיקרי עיקרי

```
1. REGIME FIRST — תמיד זהה regime לפני אסטרטגיה
2. RISK = SURVIVAL — ללא risk management אין עתיד
3. LEARN FROM DATA — 30+ עסקאות לפני ציון אמין
4. TOURNAMENT SYSTEM — ציון גבוה = יותר allocation
5. COACH LEARNS ACTIVATION — לא parameters!
6. BROAD UNIVERSE — 35 סמלים לטורניר ← חשוב!
7. NO REVENGE TRADING — kill-switch קיים לסיבה
8. GT-SCORE PRINCIPLE — anti-overfitting = robustness
```

---

*Skill נבנה על בסיס מחקר מהמחברת: NotebookLM 72e70248-f2a1-4475-8653-ef47159e74e9*
*מקורות: GT-Score paper (Sheppert 2025), Bayesian Network Options Wheel, Market Regimes (LuxAlgo), Risk Management (TradersDNA, HighStrike), ATR Guide, Mean Reversion vs Trend Following*
*עדכון: 2026-03-28*
