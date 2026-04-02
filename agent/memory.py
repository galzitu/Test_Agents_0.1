"""
Memory - SQLite database for trades, strategy scores, and learnings.
Every trade is saved with full context (indicators, market condition, session).
This is the data source for the Scoring System and Claude Coach.
"""

import sqlite3
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

try:
    import pytz
    _ET = pytz.timezone('US/Eastern')
except ImportError:
    _ET = None

from agent.config import DB_PATH, MEMORY_DIR, ScoringConfig, AuditConfig


def _today_et() -> date:
    """Get today's date in ET timezone (market time). Falls back to local."""
    if _ET:
        now_et = datetime.now(_ET)
        # Before 4 AM ET, consider it the previous trading day
        if now_et.hour < 4:
            return (now_et - timedelta(days=1)).date()
        return now_et.date()
    return date.today()

logger = logging.getLogger(__name__)


class Memory:
    """
    SQLite-based memory system.

    Tables:
      - trades: Every trade with full context
      - strategy_scores: Current scores + history
      - learnings: Lessons learned by Claude Coach
      - daily_summary: Daily P&L summary
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)  # 10 second timeout for locks
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")  # 10 second timeout in milliseconds
        return conn

    def _init_db(self):
        """Create all tables if they don't exist and run safe migrations."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Every trade with full context
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,           -- ISO format
                    strategy TEXT NOT NULL,             -- strategy name
                    symbol TEXT NOT NULL,               -- ticker
                    side TEXT NOT NULL,                 -- 'long' or 'short'
                    entry_price REAL NOT NULL,
                    exit_price REAL,                    -- NULL if still open
                    quantity REAL NOT NULL,
                    pnl REAL,                           -- profit/loss in dollars
                    pnl_pct REAL,                       -- profit/loss percentage
                    status TEXT NOT NULL DEFAULT 'open', -- open/closed/cancelled

                    -- Context at entry
                    session TEXT,                       -- opening/midday/power_hour
                    market_condition TEXT,              -- TRENDING_UP/RANGING/etc
                    entry_reason TEXT,                  -- why we entered

                    -- Indicators at entry (JSON)
                    indicators_at_entry TEXT,           -- JSON blob

                    -- Exit info
                    exit_reason TEXT,                   -- stop_loss/take_profit/signal/eod
                    exit_timestamp TEXT,
                    hold_minutes REAL,

                    -- Risk
                    stop_loss_price REAL,
                    take_profit_price REAL,
                    position_pct REAL,                  -- % of portfolio used

                    -- Metadata
                    alpaca_order_id TEXT,
                    notes TEXT
                );

                -- Strategy scores over time
                CREATE TABLE IF NOT EXISTS strategy_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    score REAL NOT NULL,                -- 0-100
                    total_trades INTEGER NOT NULL,
                    win_rate REAL,
                    profit_factor REAL,
                    avg_risk_reward REAL,
                    allocation_pct REAL,               -- current capital allocation
                    reason TEXT                         -- why score changed
                );

                -- Learnings from Claude Coach
                CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT,                     -- strategy/risk/market/general
                    lesson TEXT NOT NULL,
                    data_points INTEGER,               -- how many trades supported this
                    source TEXT DEFAULT 'claude_coach', -- who added it
                    active INTEGER DEFAULT 1           -- still relevant?
                );

                -- Daily summary
                CREATE TABLE IF NOT EXISTS daily_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    total_trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    total_pnl REAL,
                    total_pnl_pct REAL,
                    best_trade_pnl REAL,
                    worst_trade_pnl REAL,
                    strategies_used TEXT,               -- JSON list
                    market_conditions TEXT,              -- JSON list of conditions seen
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS signal_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tick_id TEXT,
                    signal_id TEXT,
                    strategy TEXT,
                    symbol TEXT,
                    stage TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    confidence REAL,
                    market_context TEXT,
                    payload TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS coach_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    before_state TEXT,
                    after_state TEXT,
                    evidence_count INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0,
                    review_date TEXT,
                    status TEXT DEFAULT 'proposed'
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_trades_strategy
                    ON trades(strategy);
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp
                    ON trades(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trades_status
                    ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_symbol
                    ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_scores_strategy
                    ON strategy_scores(strategy);
                CREATE INDEX IF NOT EXISTS idx_daily_date
                    ON daily_summary(date);
                CREATE INDEX IF NOT EXISTS idx_signal_audit_created
                    ON signal_audit(created_at);
                CREATE INDEX IF NOT EXISTS idx_signal_audit_tick
                    ON signal_audit(tick_id);
                CREATE INDEX IF NOT EXISTS idx_signal_audit_strategy_symbol
                    ON signal_audit(strategy, symbol);
            """)
            self._run_migrations(conn)
            self._set_metadata(conn, "schema_version", str(AuditConfig.SCHEMA_VERSION))
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            conn.close()

    def _run_migrations(self, conn: sqlite3.Connection):
        """Apply backwards-safe SQLite migrations on existing databases."""
        migrations = [
            (
                1,
                "baseline metadata and audit tables",
                self._migration_v1_baseline,
            ),
            (
                2,
                "add reconciliation-safe trade lifecycle fields",
                self._migration_v2_trade_lifecycle,
            ),
        ]

        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for version, description, migration in migrations:
            if version in applied:
                continue
            migration(conn)
            conn.execute(
                """INSERT INTO schema_migrations (version, applied_at, description)
                   VALUES (?, ?, ?)""",
                (version, datetime.now().isoformat(), description),
            )
            logger.info("Applied DB migration v%s: %s", version, description)

    def _migration_v1_baseline(self, conn: sqlite3.Connection):
        """Baseline migration kept explicit for old DBs."""
        self._set_metadata(conn, "schema_version", "1")

    def _migration_v2_trade_lifecycle(self, conn: sqlite3.Connection):
        """Add fields used by new trade/audit lifecycle without breaking old data."""
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        if "signal_id" not in existing:
            conn.execute("ALTER TABLE trades ADD COLUMN signal_id TEXT")
        if "tick_id" not in existing:
            conn.execute("ALTER TABLE trades ADD COLUMN tick_id TEXT")
        if "status_detail" not in existing:
            conn.execute("ALTER TABLE trades ADD COLUMN status_detail TEXT")
        if "last_updated_at" not in existing:
            conn.execute("ALTER TABLE trades ADD COLUMN last_updated_at TEXT")
        self._set_metadata(conn, "schema_version", "2")

    def _set_metadata(self, conn: sqlite3.Connection, key: str, value: str):
        conn.execute(
            """INSERT INTO system_metadata (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
            (key, value, datetime.now().isoformat()),
        )

    # ============================================================
    # TRADES
    # ============================================================

    def save_trade(self, trade_data: dict) -> int:
        """
        Save a trade to the database.

        Args:
            trade_data: Dict with trade fields (see schema above)

        Returns:
            trade id
        """
        conn = self._get_conn()
        try:
            # Serialize indicators dict to JSON
            if "indicators_at_entry" in trade_data and isinstance(
                trade_data["indicators_at_entry"], dict
            ):
                trade_data["indicators_at_entry"] = json.dumps(
                    trade_data["indicators_at_entry"]
                )

            fields = [
                "timestamp", "strategy", "symbol", "side", "entry_price",
                "exit_price", "quantity", "pnl", "pnl_pct", "status",
                "session", "market_condition", "entry_reason",
                "indicators_at_entry", "exit_reason", "exit_timestamp",
                "hold_minutes", "stop_loss_price", "take_profit_price",
                "position_pct", "alpaca_order_id", "notes", "signal_id",
                "tick_id", "status_detail", "last_updated_at",
            ]

            # Only include fields that are in trade_data
            present_fields = [f for f in fields if f in trade_data]
            placeholders = ", ".join(["?"] * len(present_fields))
            columns = ", ".join(present_fields)
            values = [trade_data[f] for f in present_fields]

            cursor = conn.execute(
                f"INSERT INTO trades ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            trade_id = cursor.lastrowid
            logger.info(
                f"Saved trade #{trade_id}: {trade_data.get('strategy')} "
                f"{trade_data.get('side')} {trade_data.get('symbol')}"
            )
            return trade_id
        finally:
            conn.close()

    def close_trade(self, trade_id: int, exit_price: float,
                    exit_reason: str, pnl: float, pnl_pct: float,
                    hold_minutes: float):
        """Close an open trade with exit details."""
        conn = self._get_conn()
        try:
            conn.execute(
                """UPDATE trades SET
                    exit_price = ?, exit_reason = ?, pnl = ?, pnl_pct = ?,
                    hold_minutes = ?, exit_timestamp = ?, status = 'closed',
                    status_detail = ?, last_updated_at = ?
                WHERE id = ?""",
                (exit_price, exit_reason, pnl, pnl_pct, hold_minutes,
                 datetime.now().isoformat(), exit_reason,
                 datetime.now().isoformat(), trade_id),
            )
            conn.commit()
            logger.info(
                f"Closed trade #{trade_id}: {exit_reason}, "
                f"P&L=${pnl:.2f} ({pnl_pct:.2%})"
            )
        finally:
            conn.close()

    def update_trade_status(self, trade_id: int, status: str,
                            status_detail: str = "",
                            notes: str = ""):
        """Update lifecycle state for an existing trade without deleting history."""
        conn = self._get_conn()
        try:
            conn.execute(
                """UPDATE trades SET
                    status = ?,
                    status_detail = ?,
                    notes = COALESCE(NULLIF(?, ''), notes),
                    last_updated_at = ?
                WHERE id = ?""",
                (status, status_detail, notes, datetime.now().isoformat(), trade_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_open_trades(self) -> list[dict]:
        """Get all currently open trades."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status = 'open' ORDER BY timestamp"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_recent_trades(self, strategy: str, symbol: str,
                          since_minutes: int = 5) -> list[dict]:
        """Return recent trades for cooldown/dedupe checks."""
        cutoff = (datetime.now() - timedelta(minutes=since_minutes)).isoformat()
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM trades
                   WHERE strategy = ? AND symbol = ? AND timestamp >= ?
                   ORDER BY timestamp DESC""",
                (strategy, symbol, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trades_by_strategy(self, strategy: str,
                               last_n: Optional[int] = None) -> list[dict]:
        """Get trades for a specific strategy."""
        conn = self._get_conn()
        try:
            query = """SELECT * FROM trades
                       WHERE strategy = ? AND status = 'closed'
                       ORDER BY timestamp DESC"""
            if last_n:
                last_n = int(last_n)  # Sanitize: ensure integer
                query += f" LIMIT {last_n}"
            rows = conn.execute(query, (strategy,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_today_trades(self) -> list[dict]:
        """Get all trades from today (ET timezone)."""
        conn = self._get_conn()
        try:
            today_str = _today_et().isoformat()
            rows = conn.execute(
                "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY timestamp",
                (f"{today_str}%",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_today_pnl(self) -> float:
        """Get total P&L for today."""
        conn = self._get_conn()
        try:
            today_str = _today_et().isoformat()
            result = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades "
                "WHERE timestamp LIKE ? AND status = 'closed'",
                (f"{today_str}%",),
            ).fetchone()
            return result[0]
        finally:
            conn.close()

    def get_today_trade_count(self) -> int:
        """Get number of trades today."""
        conn = self._get_conn()
        try:
            today_str = _today_et().isoformat()
            result = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE timestamp LIKE ?",
                (f"{today_str}%",),
            ).fetchone()
            return result[0]
        finally:
            conn.close()

    def _count_all_closed_trades(self) -> int:
        """Count total closed trades across all time."""
        conn = self._get_conn()
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status = 'closed'"
            ).fetchone()
            return result[0]
        finally:
            conn.close()

    def get_consecutive_losses(self) -> int:
        """Get number of consecutive losses today (most recent trades first)."""
        conn = self._get_conn()
        try:
            today_str = _today_et().isoformat()
            rows = conn.execute(
                """SELECT pnl FROM trades
                   WHERE status = 'closed'
                     AND timestamp LIKE ?
                   ORDER BY exit_timestamp DESC LIMIT 10""",
                (f"{today_str}%",)
            ).fetchall()

            count = 0
            for row in rows:
                if row["pnl"] is not None and row["pnl"] < 0:
                    count += 1
                else:
                    break
            return count
        finally:
            conn.close()

    # ============================================================
    # STRATEGY SCORES
    # ============================================================

    def save_score(self, strategy: str, score: float, total_trades: int,
                   win_rate: float, profit_factor: float,
                   avg_risk_reward: float, allocation_pct: float,
                   reason: str = ""):
        """Save a strategy score update."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO strategy_scores
                   (timestamp, strategy, score, total_trades, win_rate,
                    profit_factor, avg_risk_reward, allocation_pct, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), strategy, score, total_trades,
                 win_rate, profit_factor, avg_risk_reward, allocation_pct,
                 reason),
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_scores(self) -> dict[str, dict]:
        """Get the most recent score for each strategy."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT s.* FROM strategy_scores s
                   INNER JOIN (
                       SELECT strategy, MAX(timestamp) as max_ts
                       FROM strategy_scores GROUP BY strategy
                   ) latest ON s.strategy = latest.strategy
                              AND s.timestamp = latest.max_ts"""
            ).fetchall()
            return {row["strategy"]: dict(row) for row in rows}
        finally:
            conn.close()

    # ============================================================
    # LEARNINGS
    # ============================================================

    def save_learning(self, lesson: str, category: str = "general",
                      data_points: int = 0, source: str = "claude_coach"):
        """Save a new learning."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO learnings
                   (timestamp, category, lesson, data_points, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), category, lesson,
                 data_points, source),
            )
            conn.commit()
            logger.info(f"New learning: {lesson}")
        finally:
            conn.close()

    def get_active_learnings(self) -> list[dict]:
        """Get all active learnings."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM learnings WHERE active = 1 ORDER BY timestamp DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def save_coach_recommendation(self, change_type: str, target: str,
                                  before_state: dict | str,
                                  after_state: dict | str,
                                  evidence_count: int,
                                  confidence: float,
                                  review_date: Optional[str] = None,
                                  status: str = "proposed"):
        """Persist evidence-based coach recommendations."""
        before_json = (
            json.dumps(before_state) if isinstance(before_state, dict) else str(before_state)
        )
        after_json = (
            json.dumps(after_state) if isinstance(after_state, dict) else str(after_state)
        )
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO coach_recommendations
                   (timestamp, change_type, target, before_state, after_state,
                    evidence_count, confidence, review_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    change_type,
                    target,
                    before_json,
                    after_json,
                    evidence_count,
                    confidence,
                    review_date,
                    status,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # AUDIT / HEALTH
    # ============================================================

    def save_signal_audit(self, tick_id: str, signal_id: str,
                          strategy: str, symbol: str, stage: str,
                          decision: str, reason: str = "",
                          confidence: Optional[float] = None,
                          market_context: Optional[dict] = None,
                          payload: Optional[dict] = None):
        """Save signal/tick decisions for explainability and offline coaching."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO signal_audit
                   (tick_id, signal_id, strategy, symbol, stage, decision, reason,
                    confidence, market_context, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tick_id,
                    signal_id,
                    strategy,
                    symbol,
                    stage,
                    decision,
                    reason,
                    confidence,
                    json.dumps(market_context or {}),
                    json.dumps(payload or {}),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def prune_signal_audit(self, retention_days: int = AuditConfig.SIGNAL_AUDIT_RETENTION_DAYS) -> int:
        """Delete detailed audit rows older than retention window."""
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM signal_audit WHERE created_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def set_heartbeat(self, component: str, status: str, details: Optional[dict] = None):
        """Persist the latest heartbeat for each component in metadata."""
        payload = {
            "status": status,
            "details": details or {},
            "updated_at": datetime.now().isoformat(),
        }
        conn = self._get_conn()
        try:
            self._set_metadata(conn, f"heartbeat:{component}", json.dumps(payload))
            conn.commit()
        finally:
            conn.close()

    def get_heartbeat(self, component: str) -> Optional[dict]:
        """Fetch the latest heartbeat for a component."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT value FROM system_metadata WHERE key = ?",
                (f"heartbeat:{component}",),
            ).fetchone()
            return json.loads(row["value"]) if row else None
        finally:
            conn.close()

    # ============================================================
    # DAILY SUMMARY
    # ============================================================

    def save_daily_summary(self, summary: dict):
        """Save or update today's daily summary."""
        conn = self._get_conn()
        try:
            # Serialize lists to JSON
            if "strategies_used" in summary and isinstance(
                summary["strategies_used"], list
            ):
                summary["strategies_used"] = json.dumps(summary["strategies_used"])
            if "market_conditions" in summary and isinstance(
                summary["market_conditions"], list
            ):
                summary["market_conditions"] = json.dumps(summary["market_conditions"])

            conn.execute(
                """INSERT OR REPLACE INTO daily_summary
                   (date, total_trades, wins, losses, total_pnl, total_pnl_pct,
                    best_trade_pnl, worst_trade_pnl, strategies_used,
                    market_conditions, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (summary.get("date", _today_et().isoformat()),
                 summary.get("total_trades", 0),
                 summary.get("wins", 0),
                 summary.get("losses", 0),
                 summary.get("total_pnl", 0),
                 summary.get("total_pnl_pct", 0),
                 summary.get("best_trade_pnl", 0),
                 summary.get("worst_trade_pnl", 0),
                 summary.get("strategies_used", "[]"),
                 summary.get("market_conditions", "[]"),
                 summary.get("notes", "")),
            )
            conn.commit()
        finally:
            conn.close()

    def get_daily_summaries(self, last_n: int = 30) -> list[dict]:
        """Get recent daily summaries."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?",
                (last_n,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ============================================================
    # COACH HELPERS
    # ============================================================

    def get_strategy_performance(self, strategy: str,
                                  market_condition: Optional[str] = None
                                  ) -> dict:
        """
        Get performance stats for a strategy, optionally filtered
        by market condition. Used by Claude Coach for analysis.
        """
        conn = self._get_conn()
        try:
            query = """SELECT * FROM trades
                       WHERE strategy = ? AND status = 'closed'"""
            params = [strategy]

            if market_condition:
                query += " AND market_condition = ?"
                params.append(market_condition)

            rows = conn.execute(query, params).fetchall()
            trades = [dict(r) for r in rows]

            if not trades:
                return {
                    "strategy": strategy,
                    "total_trades": 0,
                    "message": "No closed trades yet",
                }

            wins = [t for t in trades if t["pnl"] and t["pnl"] > 0]
            losses = [t for t in trades if t["pnl"] and t["pnl"] <= 0]
            total_pnl = sum(t["pnl"] for t in trades if t["pnl"])

            gross_profit = sum(t["pnl"] for t in wins) if wins else 0
            gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 1

            avg_win = (gross_profit / len(wins)) if wins else 0
            avg_loss = (gross_loss / len(losses)) if losses else 1

            return {
                "strategy": strategy,
                "market_condition": market_condition or "all",
                "total_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) if trades else 0,
                "total_pnl": total_pnl,
                "profit_factor": gross_profit / gross_loss if gross_loss > 0 else 0,
                "avg_risk_reward": avg_win / avg_loss if avg_loss > 0 else 0,
                "avg_hold_minutes": (
                    sum(t["hold_minutes"] for t in trades if t["hold_minutes"])
                    / len(trades)
                ) if trades else 0,
                "has_enough_data": len(trades) >= ScoringConfig.MIN_TRADES_FOR_SCORE,
            }
        finally:
            conn.close()

    def get_coach_report(self, day: Optional[str] = None) -> dict:
        """
        Generate a full report for Claude Coach analysis.
        Includes today's trades, strategy performance, recent learnings.
        """
        day = day or _today_et().isoformat()
        conn = self._get_conn()
        try:
            # Today's trades
            trades = conn.execute(
                "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY timestamp",
                (f"{day}%",),
            ).fetchall()
            trades = [dict(r) for r in trades]

            # Strategy performance
            strategies = set(t["strategy"] for t in trades)
            performance = {}
            for strat in strategies:
                performance[strat] = self.get_strategy_performance(strat)

            # Recent learnings
            learnings = self.get_active_learnings()

            # Latest scores
            scores = self.get_latest_scores()

            recommendations = conn.execute(
                """SELECT timestamp, change_type, target, before_state, after_state,
                          evidence_count, confidence, review_date, status
                   FROM coach_recommendations
                   ORDER BY timestamp DESC LIMIT 50"""
            ).fetchall()

            return {
                "date": day,
                "total_trades": len(trades),
                "trades": trades,
                "performance_by_strategy": performance,
                "current_scores": scores,
                "active_learnings": learnings,
                "coach_recommendations": [dict(r) for r in recommendations],
            }
        finally:
            conn.close()

    # ============================================================
    # MARKDOWN EXPORT (for human readability)
    # ============================================================

    def export_learnings_md(self):
        """Export learnings to memory/learnings.md for human reading."""
        learnings = self.get_active_learnings()
        md_path = MEMORY_DIR / "learnings.md"

        lines = ["# Learnings - מה הסוכן למד\n"]
        lines.append(f"*עדכון אחרון: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        if not learnings:
            lines.append("\nעדיין לא נלמדו לקחים. הסוכן צריך לצבור עסקאות.\n")
        else:
            categories = {}
            for l in learnings:
                cat = l.get("category", "general")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(l)

            for cat, items in categories.items():
                lines.append(f"\n## {cat.title()}\n")
                for item in items:
                    lines.append(
                        f"- {item['lesson']} "
                        f"({item.get('data_points', '?')} trades, "
                        f"{item['timestamp'][:10]})"
                    )

        md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Exported learnings to {md_path}")

    def export_strategy_performance_md(self):
        """Export strategy performance to memory/strategy_performance.md."""
        scores = self.get_latest_scores()
        md_path = MEMORY_DIR / "strategy_performance.md"

        lines = ["# Strategy Performance - ביצועי אסטרטגיות\n"]
        lines.append(f"*עדכון אחרון: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        if not scores:
            lines.append("\nאין עדיין נתוני ביצועים.\n")
        else:
            lines.append("| Strategy | Score | Trades | Win Rate | PF | Alloc |")
            lines.append("|----------|-------|--------|----------|-----|-------|")
            for name, data in sorted(scores.items(),
                                      key=lambda x: x[1].get("score", 0),
                                      reverse=True):
                lines.append(
                    f"| {name} | {data.get('score', '?'):.0f} | "
                    f"{data.get('total_trades', 0)} | "
                    f"{data.get('win_rate', 0):.0%} | "
                    f"{data.get('profit_factor', 0):.1f} | "
                    f"{data.get('allocation_pct', 0):.0%} |"
                )

        md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Exported performance to {md_path}")


# Lazy convenience instance - only initialized when first used
_memory_instance = None

def get_memory() -> Memory:
    """Get or create the global Memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = Memory()
    return _memory_instance


if __name__ == "__main__":
    """Quick test."""
    m = Memory()
    print(f"Database at: {m.db_path}")
    print(f"Open trades: {len(m.get_open_trades())}")
    print(f"Today's trades: {len(m.get_today_trades())}")
    print(f"Today's P&L: ${m.get_today_pnl():.2f}")
    print(f"Consecutive losses: {m.get_consecutive_losses()}")
    print("Database initialized successfully!")
