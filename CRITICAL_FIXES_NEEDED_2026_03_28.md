# CRITICAL BUGS REQUIRING IMMEDIATE FIXES

## Overview
Three CRITICAL bugs must be fixed before the agent can trade safely. These can cause crashes, data loss, or trading violations.

---

## CRITICAL BUG #1: SQL Injection Vulnerability

**File:** `/sessions/intelligent-bold-cray/mnt/trading-agent/agent/memory.py`, line 388

**Current Code:**
```python
def get_trades_by_strategy(self, strategy: str, last_n: int = None) -> list[dict]:
    conn = self._get_conn()
    try:
        query = """SELECT * FROM trades
                   WHERE strategy = ? AND status = 'closed'
                   ORDER BY timestamp DESC"""
        if last_n:
            query += f" LIMIT {last_n}"  # ❌ VULNERABLE - not parameterized!
        rows = conn.execute(query, (strategy,)).fetchall()
        return [dict(r) for r in rows]
```

**Problem:**
- `last_n` value is concatenated directly into SQL string
- Attacker could pass `last_n="99; DELETE FROM trades; --"` to drop tables
- SQLite doesn't support parameterized LIMIT, but Python can apply it locally

**Fix (Recommended):**
```python
def get_trades_by_strategy(self, strategy: str, last_n: int = None) -> list[dict]:
    conn = self._get_conn()
    try:
        query = """SELECT * FROM trades
                   WHERE strategy = ? AND status = 'closed'
                   ORDER BY timestamp DESC"""
        rows = conn.execute(query, (strategy,)).fetchall()
        
        # Apply LIMIT in Python, not SQL
        if last_n:
            rows = rows[:last_n]
        return [dict(r) for r in rows]
```

**Alternative Fix (Validate Input):**
```python
if last_n:
    if not isinstance(last_n, int) or last_n < 1 or last_n > 10000:
        raise ValueError(f"Invalid last_n: {last_n}")
    query += f" LIMIT {last_n}"
```

**Severity:** CRITICAL - Data corruption, exfiltration, or deletion possible

---

## CRITICAL BUG #2: Risk Check Not Actually Blocking Trades

**File:** `/sessions/intelligent-bold-cray/mnt/trading-agent/agent/trader.py`, lines 133-135

**Current Code:**
```python
risk_result = self.risk_manager.check_if_can_trade(
    signal, portfolio_value, open_positions, session
)

if not risk_result:  # ❌ BUG - risk_result is always truthy (object, not bool/None)
    logger.info(f"Trade blocked by risk manager: {risk_result.reason}")
    return self._blocked(signal, risk_result.reason, "risk")

# Trade proceeds here regardless!
```

**Problem:**
- `risk_manager.check_if_can_trade()` returns a `RiskCheckResult` object
- Object is always truthy, so `if not risk_result` is always False
- Risk check effectively never blocks trades
- Even if daily loss limit exceeded, agent still trades

**Fix:**
```python
risk_result = self.risk_manager.check_if_can_trade(
    signal, portfolio_value, open_positions, session
)

if not risk_result.can_trade:  # ✅ Check the boolean property
    logger.info(f"Trade blocked by risk manager: {risk_result.reason}")
    return self._blocked(signal, risk_result.reason, "risk")

# Trade proceeds only if risk_result.can_trade == True
```

**Verify RiskCheckResult class has:**
```python
@dataclass
class RiskCheckResult:
    can_trade: bool  # Must exist!
    reason: str
```

**Severity:** CRITICAL - Bypasses all risk limits, can lose entire portfolio

---

## CRITICAL BUG #3: Division by Zero in Position Sizing

**File:** `/sessions/intelligent-bold-cray/mnt/trading-agent/agent/risk_manager.py`, line 306

**Current Code:**
```python
def calculate_position_size(self, signal, portfolio_value, alloc_pct, session):
    # ... calculation of trade_budget ...
    
    # Calculate shares (whole shares only)
    shares = int(trade_budget / signal.entry_price)  # ❌ ZeroDivisionError if entry_price=0
    
    if shares <= 0:
        return {"shares": 0, "dollar_amount": 0, "position_pct": 0}
```

**Problem:**
- No check that `signal.entry_price > 0` before division
- Can crash agent if:
  - Signal has entry_price = 0 (corrupted data)
  - Quote API returns null/zero price
  - Data type conversion error

**Fix:**
```python
def calculate_position_size(self, signal, portfolio_value, alloc_pct, session):
    # ... calculation of trade_budget ...
    
    # Validate entry price
    if signal.entry_price <= 0:
        logger.error(f"CRITICAL: Invalid entry_price={signal.entry_price} for {signal.symbol}")
        return {"shares": 0, "dollar_amount": 0, "position_pct": 0}
    
    # Calculate shares (whole shares only)
    shares = int(trade_budget / signal.entry_price)
    
    if shares <= 0:
        return {"shares": 0, "dollar_amount": 0, "position_pct": 0}
```

**Severity:** CRITICAL - Agent crashes during trade execution, no graceful recovery

---

## Testing the Fixes

After applying fixes, run:

```bash
cd /sessions/intelligent-bold-cray/mnt/trading-agent

# 1. Test SQL injection fix
python3 -c "
from agent.memory import TradeMemory
from pathlib import Path
db = TradeMemory(Path('memory/trading.db'))

# This should work safely now
trades = db.get_trades_by_strategy('EMA_Crossover_9_21', last_n=10)
print(f'✅ Got {len(trades)} trades')

# Try with invalid input (should not crash)
trades = db.get_trades_by_strategy('EMA_Crossover_9_21', last_n=99999)
print(f'✅ Invalid limit handled safely')
"

# 2. Test risk check fix
python3 -c "
from agent.risk_manager import RiskManager
from agent.config import RiskLimits
from agent.strategies.base import Signal, SignalType

rm = RiskManager()
# Create a signal
signal = Signal(
    strategy='TEST', symbol='AAPL', type=SignalType.BUY,
    entry_price=150, stop_loss=145, take_profit=155,
    confidence=0.8, reason='test'
)

# Check that can_trade is actually checked
result = rm.check_if_can_trade(signal, 100000, [], 'opening')
print(f'✅ Risk check returns: can_trade={result.can_trade}, reason={result.reason}')
"

# 3. Test zero division fix
python3 -c "
from agent.risk_manager import RiskManager
from agent.strategies.base import Signal, SignalType

rm = RiskManager()
signal = Signal(
    strategy='TEST', symbol='AAPL', type=SignalType.BUY,
    entry_price=0,  # Invalid!
    stop_loss=-10, take_profit=10,
    confidence=0.8, reason='test'
)

# Should not crash
try:
    result = rm.calculate_position_size(signal, 100000, 0.05, 'opening')
    print(f'✅ Zero division handled: {result}')
except Exception as e:
    print(f'❌ FAILED: {e}')
"
```

---

## Summary

| Bug | Fix Type | File | Line | Impact if Not Fixed |
|-----|----------|------|------|-------------------|
| SQL Injection | Python-level LIMIT | memory.py | 388 | Data corruption/deletion |
| Risk Check | Check boolean property | trader.py | 133 | Trades despite daily loss limit |
| Division by Zero | Input validation | risk_manager.py | 306 | Agent crash during trade |

**Recommendation:** Fix all three before next market open (Monday 30/03 at 09:30 ET).

