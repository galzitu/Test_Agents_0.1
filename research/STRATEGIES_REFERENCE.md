# Strategy Reference - מיפוי אסטרטגיות מוכן לקוד

מסמך זה מתרגם את המחקר לכללים מדויקים שהקוד צריך לממש.
כל אסטרטגיה מוגדרת כ-"כרטיס" עם כל המידע שצריך.

---

## Strategy 1: RSI + MACD Momentum

```yaml
name: RSI_MACD_Momentum
file: strategies/rsi_macd.py
timeframe: 5min

params:  # קבועים! Claude Coach לא משנה
  rsi_period: 14
  rsi_oversold: 30
  rsi_overbought: 70
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  min_volume_ratio: 1.5      # volume / avg_volume_20
  stop_loss_atr_mult: 1.5    # stop = entry - ATR*1.5
  take_profit_atr_mult: 3.0  # target = entry + ATR*3.0

entry_long:
  - RSI(14) < 30
  - MACD line crosses ABOVE signal line (bullish crossover)
  - current_volume > avg_volume_20 * 1.5
  - ALL conditions must be true simultaneously

entry_short:
  - RSI(14) > 70
  - MACD line crosses BELOW signal line (bearish crossover)
  - current_volume > avg_volume_20 * 1.5

exit:
  - hit stop_loss (ATR * 1.5 from entry)
  - hit take_profit (ATR * 3.0 from entry)
  - RSI crosses back to neutral zone (40-60)
  - MACD crossover in opposite direction
  - end of day (15:50 ET)

activation_conditions:  # Claude Coach יכול לשנות רק את אלה
  sessions: [opening, power_hour]
  market_conditions: [TRENDING_UP, TRENDING_DOWN, VOLATILE]
  adx_min: 20              # רק כשיש מגמה
  vix_max: 35              # לא בפאניקה

indicators_needed:
  - RSI(14)
  - MACD(12, 26, 9)
  - ATR(14)
  - Volume (current + 20-day average)
  - ADX(14)

risk_reward: "1:2 (stop=1.5×ATR, target=3×ATR)"
expected_win_rate: "55-65%"
avg_hold_time: "15-60 minutes"
```

---

## Strategy 2: Opening Range Breakout (ORB)

```yaml
name: Opening_Range_Breakout
file: strategies/orb.py
timeframe: 1min (setup), 1min (monitoring)

params:
  range_minutes: 15           # 09:30-09:45 ET
  breakout_buffer_pct: 0.002  # 0.2% above/below range
  min_range_pct: 0.005        # range must be > 0.5%
  max_range_pct: 0.03         # range must be < 3%
  min_volume_ratio: 1.5
  stop_loss: "opposite_end_of_range"
  take_profit_mult: 2.0       # 2x range size

setup_phase: "09:30-09:45 ET"
  - record HIGH of first 15 minutes
  - record LOW of first 15 minutes
  - calculate range_size = HIGH - LOW
  - calculate range_pct = range_size / ((HIGH + LOW) / 2)
  - if range_pct < 0.005: SKIP (too narrow)
  - if range_pct > 0.03: SKIP (too wide)

entry_long: "after 09:45 ET"
  - price closes above range_HIGH * (1 + 0.002)
  - volume spike at breakout moment (> 1.5x avg)
  - stop_loss = range_LOW
  - take_profit = range_HIGH + (range_size * 2)

entry_short: "after 09:45 ET"
  - price closes below range_LOW * (1 - 0.002)
  - volume spike at breakout moment
  - stop_loss = range_HIGH
  - take_profit = range_LOW - (range_size * 2)

exit:
  - hit stop_loss (opposite end of range)
  - hit take_profit (2x range size)
  - price re-enters range (false breakout)
  - 11:00 ET (ORB is a morning strategy)
  - end of day (15:50 ET)

activation_conditions:
  sessions: [opening]         # ONLY opening session
  market_conditions: [VOLATILE, TRENDING_UP, TRENDING_DOWN]
  gap_min_pct: 0.005          # better with gap > 0.5%
  pre_market_volume_min: 1.5  # pre-market activity

indicators_needed:
  - Price (1min candles)
  - Volume (current + average)
  - Gap % (open vs previous close)
  - Pre-market volume

risk_reward: "1:2 (stop=range end, target=2x range)"
expected_win_rate: "50-60%"
avg_hold_time: "15-90 minutes"
max_active_until: "11:00 ET"
```

---

## Strategy 3: VWAP Mean Reversion

```yaml
name: VWAP_Mean_Reversion
file: strategies/vwap_reversion.py
timeframe: 5min

params:
  deviation_pct: 0.01          # 1% from VWAP
  # OR use standard deviation bands:
  deviation_std: 2.0            # 2 standard deviations from VWAP
  rsi_confirm_long: 35          # RSI must be below this for long
  rsi_confirm_short: 65         # RSI must be above this for short
  stop_loss_pct: 0.005          # 0.5% beyond entry
  target: "vwap"                # target is return to VWAP
  min_volume_ratio: 1.0

entry_long:
  - price < VWAP * (1 - 0.01)  OR  price below VWAP - 2σ
  - RSI(14) < 35
  - bullish reversal candle (hammer, bullish engulfing)
  - NOT in first 15 minutes (avoid head fakes)
  - stop_loss = recent low - 0.5%
  - take_profit = VWAP

entry_short:
  - price > VWAP * (1 + 0.01)  OR  price above VWAP + 2σ
  - RSI(14) > 65
  - bearish reversal candle (shooting star, bearish engulfing)
  - NOT in first 15 minutes
  - stop_loss = recent high + 0.5%
  - take_profit = VWAP

exit:
  - price reaches VWAP (take profit)
  - hit stop_loss
  - price moves further away (deviation doubles)
  - end of day (15:50 ET)

activation_conditions:
  sessions: [midday]           # BEST in quiet session
  market_conditions: [RANGING] # ONLY when market is ranging!
  adx_max: 25                  # no strong trend
  not_first_15_min: true       # avoid opening noise
  vix_max: 25                  # not too volatile

indicators_needed:
  - VWAP (with standard deviation bands)
  - RSI(14)
  - ADX(14)
  - Candlestick patterns (basic)

risk_reward: "1:2+ (small stop, target=VWAP)"
expected_win_rate: "55-65% (in RANGING market)"
avg_hold_time: "20-60 minutes"

CRITICAL_WARNING: >
  This strategy FAILS in trending markets.
  Claude Coach should ensure it's NEVER active when ADX > 25.
  Historical data shows 25% win rate in trending vs 70%+ in ranging.
```

---

## Strategy 4: Volume Spike Momentum

```yaml
name: Volume_Spike_Momentum
file: strategies/volume_spike.py
timeframe: 1min

params:
  volume_spike_mult: 3.0       # volume > 3x average
  ema_period: 9                # EMA(9) for direction
  stop_loss_pct: 0.01          # 1% stop
  take_profit_pct: 0.02        # 2% target
  max_hold_minutes: 30         # exit after 30 min max
  min_candle_body_pct: 0.003   # candle body > 0.3%

entry_long:
  - current_volume > avg_volume_20 * 3.0 (volume spike!)
  - candle is GREEN (close > open)
  - candle body > 0.3% of price (strong candle)
  - price > EMA(9) (upward momentum)
  - stop_loss = low of spike candle
  - take_profit = entry + 2%

entry_short:
  - current_volume > avg_volume_20 * 3.0
  - candle is RED (close < open)
  - candle body > 0.3%
  - price < EMA(9)
  - stop_loss = high of spike candle
  - take_profit = entry - 2%

exit:
  - hit stop_loss
  - hit take_profit (2%)
  - 30 minutes elapsed (max hold time!)
  - EMA(9) crossover against position
  - end of day (15:50 ET)

special_rules:
  exhaustion_detection: >
    If volume spike occurs AFTER a strong move in same direction
    (price already moved 3%+ in last hour), it may be exhaustion.
    Skip entry or trade in OPPOSITE direction cautiously.

  news_spike: >
    If spike happens at earnings/FOMC time, spreads may be wide.
    Wait 2-3 minutes for stabilization before entry.

activation_conditions:
  sessions: [opening, power_hour]
  market_conditions: [VOLATILE, TRENDING_UP, TRENDING_DOWN]
  not_during_events: [FOMC, earnings_first_5min]

indicators_needed:
  - Volume (current + 20-day average)
  - EMA(9)
  - Price action (candle body size)
  - OBV (confirmation)

risk_reward: "1:2 (stop=1%, target=2%)"
expected_win_rate: "45-55%"
avg_hold_time: "5-30 minutes"
```

---

## Strategy 5: EMA Crossover (9/21)

```yaml
name: EMA_Crossover_9_21
file: strategies/ema_cross.py
timeframe: 5min

params:
  ema_fast: 9
  ema_slow: 21
  rsi_filter_low: 40           # don't buy if RSI > 65
  rsi_filter_high: 65          # don't short if RSI < 35
  min_volume_ratio: 1.2
  stop_loss: "below_ema_slow"  # stop at EMA(21)
  take_profit_pct: 0.025       # 2.5%

entry_long:
  - EMA(9) crosses ABOVE EMA(21)
  - RSI(14) between 40 and 65 (not overbought)
  - current_volume > avg_volume * 1.2
  - stop_loss = EMA(21) current value
  - take_profit = entry + 2.5%

entry_short:
  - EMA(9) crosses BELOW EMA(21)
  - RSI(14) between 35 and 60 (not oversold)
  - current_volume > avg_volume * 1.2
  - stop_loss = EMA(21) current value
  - take_profit = entry - 2.5%

exit:
  - hit stop_loss (price crosses EMA(21) against position)
  - hit take_profit (2.5%)
  - opposite EMA crossover
  - end of day (15:50 ET)

activation_conditions:
  sessions: [opening, midday, power_hour]
  market_conditions: [TRENDING_UP, TRENDING_DOWN]
  adx_min: 22                  # needs trend

WARNING: >
  EMA crossover alone has 57-76% false signal rate on stocks!
  Must be combined with RSI filter and volume confirmation.
  This strategy starts with LOW score and must prove itself.

initial_score: 40  # starts skeptical, must earn trust

indicators_needed:
  - EMA(9)
  - EMA(21)
  - RSI(14)
  - ADX(14)
  - Volume

risk_reward: "1:2.5"
expected_win_rate: "40-55% (with filters)"
avg_hold_time: "30-120 minutes"
```

---

## Strategy 6: Bollinger Band Squeeze

```yaml
name: Bollinger_Squeeze
file: strategies/bollinger_squeeze.py
timeframe: 5min

params:
  bb_period: 20
  bb_std: 2.0
  squeeze_bandwidth_threshold: 0.04  # 4% = squeeze
  rsi_confirm: true
  min_volume_spike: 2.0              # volume > 2x at breakout
  stop_loss: "opposite_band"
  take_profit: "2x_bandwidth"

setup_phase: "detect squeeze"
  - calculate Bollinger Bandwidth = (upper - lower) / middle
  - if bandwidth < 0.04 → SQUEEZE detected
  - wait for breakout...

entry_long:
  - squeeze detected (bandwidth < 4%)
  - price closes ABOVE upper Bollinger Band
  - volume spike > 2x average (confirmation!)
  - RSI rising (momentum confirmation)
  - stop_loss = lower Bollinger Band
  - take_profit = entry + 2x current bandwidth

entry_short:
  - squeeze detected (bandwidth < 4%)
  - price closes BELOW lower Bollinger Band
  - volume spike > 2x average
  - RSI falling
  - stop_loss = upper Bollinger Band
  - take_profit = entry - 2x current bandwidth

exit:
  - hit stop_loss (opposite band)
  - hit take_profit (2x bandwidth)
  - price re-enters bands (false breakout)
  - end of day (15:50 ET)

activation_conditions:
  sessions: [opening, midday, power_hour]
  market_conditions: [RANGING, VOLATILE]  # squeeze happens in ranging→volatile transition

indicators_needed:
  - Bollinger Bands(20, 2)
  - Bollinger Bandwidth
  - RSI(14)
  - Volume
  - ATR(14)

risk_reward: "1:2 (stop=opposite band, target=2x bandwidth)"
expected_win_rate: "50-60%"
avg_hold_time: "15-60 minutes"
```

---

## Market Condition Detection

```yaml
file: agent/market_condition.py

indicators_used:
  - ADX(14): trend strength
  - ATR(14): volatility
  - ATR_ratio: ATR / avg_ATR_20
  - Volume_ratio: volume / avg_volume_20

conditions:
  TRENDING_UP:
    - ADX > 25
    - price > EMA(21)
    - EMA(9) > EMA(21)

  TRENDING_DOWN:
    - ADX > 25
    - price < EMA(21)
    - EMA(9) < EMA(21)

  RANGING:
    - ADX < 20
    - ATR_ratio < 1.2 (normal volatility)
    - price oscillating around VWAP

  VOLATILE:
    - ATR_ratio > 1.5 (high volatility)
    - large candles
    - volume > 2x average

  LOW_VOLUME:
    - volume_ratio < 0.5
    - ATR_ratio < 0.7
    - ACTION: DO NOT TRADE!

detection_interval: every run (before strategy selection)
```

---

## Scoring System

```yaml
file: agent/scorer.py

formula:
  # Only calculated after MIN_TRADES (30) trades
  win_rate_score = (wins / total) * 40        # 40% weight
  profit_factor_score = min(PF / 3, 1) * 35   # 35% weight
  risk_reward_score = min(avg_RR / 3, 1) * 25 # 25% weight

  final_score = win_rate_score + profit_factor_score + risk_reward_score
  # Scale: 0-100

thresholds:
  70-100: "strong"    → allocation 25-35%
  50-70:  "decent"    → allocation 10-20%
  30-50:  "weak"      → allocation 5-10%, Claude investigates
  0-30:   "failing"   → disabled after 50+ trades
  "?":    "new"       → 50 (neutral), allocation 5%, trial period

min_trades_for_score: 30
min_trades_for_disable: 50
recalculate_after: every_closed_trade
```

---

## Capital Allocation

```yaml
file: agent/allocator.py

method: score-weighted proportional
  # Each strategy gets: its_score / sum_of_all_scores

example:
  RSI_MACD:  score=72 → 72/287 = 25.1%
  ORB:       score=65 → 65/287 = 22.6%
  VWAP:      score=45 → 45/287 = 15.7%
  VolSpike:  score=55 → 55/287 = 19.2%
  EMA_Cross: score=50 → 50/287 = 17.4%
  Total:           287         100%

constraints:
  max_per_strategy: 35%    # no single strategy > 35%
  min_per_strategy: 5%     # keep at least 5% (unless disabled)

recalculate: after every score change
```

---

## Risk Manager Rules (HARDCODED)

```yaml
file: agent/risk_manager.py
IMMUTABLE: true  # Nobody changes these. Not Claude, not the code.

position_limits:
  max_position_pct: 0.05         # 5% of portfolio per trade
  opening_max_position_pct: 0.03 # 3% during opening (volatile)
  max_open_positions: 3

stop_loss:
  mandatory: true                # NO TRADE without stop loss
  max_stop_loss_pct: 0.02        # max 2% loss per trade

daily_limits:
  max_daily_loss_pct: 0.03       # 3% daily loss → agent stops
  max_daily_trades: 20
  cooling_after_consecutive_losses: 3  # 3 losses → 30 min pause
  cooling_duration_minutes: 30

day_trading_rules:
  close_all_by: "15:50 ET"
  no_new_positions_after: "15:45 ET"
  no_overnight: true

extended_hours:
  allow_premarket: false         # default off
  allow_afterhours: false        # default off

order_types:
  regular_hours: [market, limit, stop, stop_limit]
  extended_hours: [limit]        # ONLY limit orders!

volume_check:
  min_volume_ratio: 0.5          # don't trade if volume < 50% avg
  min_spread_check: true         # alert if spread > 0.5%
```
