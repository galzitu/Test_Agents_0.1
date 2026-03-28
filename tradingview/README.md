# TradingView Integration

## איך לחבר את הסוכן ל-TradingView

### שלב 1: הפעל את ה-Dashboard
```bash
./start.sh dashboard
```
ה-Dashboard ירוץ על `http://localhost:5555`

### שלב 2: חשוף את ה-API לאינטרנט (כדי ש-TradingView יוכל לגשת)
```bash
# Option A: ngrok (מומלץ)
ngrok http 5555

# Option B: cloudflared tunnel
cloudflared tunnel --url http://localhost:5555
```
תקבל URL כמו: `https://abc123.ngrok.io`

### שלב 3: הוסף את ה-Pine Script ל-TradingView

1. פתח TradingView → Pine Editor
2. העתק את התוכן מ-`agent_signals.pine`
3. שנה את ה-URL בשורה 8 ל-URL שקיבלת מ-ngrok
4. לחץ "Add to Chart"

### מה תראה על הגרף:
- 🟢 חץ ירוק למעלה = BUY signal
- 🔴 חץ אדום למטה = SELL signal
- קו ירוק מקווקו = Stop Loss
- קו כחול מקווקו = Take Profit
- טבלת סטטוס בפינה עם:
  - שם האסטרטגיה
  - Entry price
  - P&L נוכחי
  - ציון האסטרטגיה

### שלב 4 (אופציונלי): התראות TradingView
1. בחרו את האינדיקטור "Trading Agent Signals"
2. לחצו על "Alert" → Set Alert
3. תקבלו התראה בכל פעם שהסוכן פותח/סוגר פוזיציה
