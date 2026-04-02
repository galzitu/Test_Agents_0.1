"""
Dashboard - Web-based monitoring for the trading agent.

Provides:
  - REST API for agent status, trades, positions
  - Real-time updates via Server-Sent Events (SSE)
  - Serves the frontend (HTML + TradingView charts)
  - TradingView webhook endpoint for Pine Script integration

Usage:
    python -m agent.dashboard          # Start dashboard on port 5555
    python -m agent.dashboard --port 8080
"""

import json
import logging
import time
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from threading import Thread

from flask import Flask, jsonify, request, Response, send_from_directory

from agent.config import STRATEGIES_CONFIG_DIR, INITIAL_CAPITAL, MEMORY_DIR, SHADOW_MODE
from agent.memory import Memory
from agent.market_hours import MarketHours
from agent.market_data import AlpacaClient, IndicatorCalculator
from agent.health import HealthMonitor
from agent.strategies.selector import StrategySelector
from agent.scorer import StrategyScorer
from agent.allocator import CapitalAllocator

logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__,
            static_folder=str(Path(__file__).parent / "static"),
            static_url_path="/static")

# Shared state (initialized on startup)
_memory: Optional[Memory] = None
_market_hours: Optional[MarketHours] = None
_client: Optional[AlpacaClient] = None
_indicator_calc: Optional[IndicatorCalculator] = None
_selector: Optional[StrategySelector] = None
_scorer: Optional[StrategyScorer] = None
_allocator: Optional[CapitalAllocator] = None
_health: Optional[HealthMonitor] = None


def init_components():
    """Initialize all components for the dashboard."""
    global _memory, _market_hours, _client, _indicator_calc
    global _selector, _scorer, _allocator, _health

    logger.info("Initializing dashboard components...")

    _memory = Memory()
    logger.info("✓ Memory")
    _health = HealthMonitor(_memory)
    _health.record_heartbeat("dashboard", "running", {"phase": "init"})

    _market_hours = MarketHours()
    logger.info("✓ MarketHours")

    _client = AlpacaClient()
    logger.info("✓ AlpacaClient")

    _indicator_calc = IndicatorCalculator()
    logger.info("✓ IndicatorCalculator")

    try:
        _selector = StrategySelector()
        logger.info(f"✓ StrategySelector ({len(_selector.all_strategies)} strategies)")
    except Exception as e:
        logger.error(f"✗ StrategySelector failed: {e}")
        _selector = None

    try:
        _scorer = StrategyScorer(_memory)
        logger.info("✓ StrategyScorer")
    except Exception as e:
        logger.error(f"✗ StrategyScorer failed: {e}")
        _scorer = None

    try:
        _allocator = CapitalAllocator()
        logger.info("✓ CapitalAllocator")
    except Exception as e:
        logger.error(f"✗ CapitalAllocator failed: {e}")
        _allocator = None

    logger.info("Dashboard components ready.")


@app.after_request
def add_no_cache_headers(response):
    """Prevent browser from caching API responses — ensures live data."""
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ============================================================
# Frontend
# ============================================================

@app.route("/")
def index():
    """Serve the main dashboard page — always fresh, no browser cache."""
    response = send_from_directory(app.static_folder, "dashboard.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ============================================================
# API - Status
# ============================================================

@app.route("/api/status")
def api_status():
    """Get complete agent status."""
    try:
        market = _market_hours.get_status()

        try:
            account = _client.get_account()
            alpaca_connected = True
            alpaca_error = None
        except Exception:
            account = {
                "equity": INITIAL_CAPITAL, "buying_power": INITIAL_CAPITAL,
                "cash": INITIAL_CAPITAL, "portfolio_value": INITIAL_CAPITAL,
                "day_trade_count": 0,
            }
            alpaca_connected = False
            alpaca_error = "Unable to reach Alpaca live account data"

        today_pnl = _memory.get_today_pnl()
        today_trades = _memory.get_today_trade_count()
        open_trades = _memory.get_open_trades()
        consecutive_losses = _memory.get_consecutive_losses()
        closed_trade_count = sum(
            1 for trade in _memory.get_today_trades() if trade.get("status") == "closed"
        )

        return jsonify({
            "market": market,
            "account": account,
            "today_pnl": round(today_pnl, 2),
            "today_trades": today_trades,
            "open_positions": len(open_trades),
            "consecutive_losses": consecutive_losses,
            "system": {
                "alpaca_connected": alpaca_connected,
                "alpaca_error": alpaca_error,
                "mode": "shadow" if SHADOW_MODE else "paper",
            },
            "learning": {
                "today_closed_trades": closed_trade_count,
                "today_total_trades": today_trades,
                "total_closed_trades": _memory._count_all_closed_trades(),
            },
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    """Operational health snapshot for agent + dashboard runtime."""
    try:
        data = _health.run_checks(_market_hours, _client) if _health else {}
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Tick Diagnostics
# ============================================================

@app.route("/api/tick")
def api_tick():
    """Get last tick diagnostics from the agent (reads logs/last_tick.json)."""
    try:
        from agent.config import LOGS_DIR
        tick_file = LOGS_DIR / "last_tick.json"
        if tick_file.exists():
            with open(tick_file) as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({"reason_no_trade": "Agent hasn't run a tick yet"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Trades
# ============================================================

@app.route("/api/trades/today")
def api_trades_today():
    """Get today's trades."""
    try:
        trades = _memory.get_today_trades()
        return jsonify({"trades": trades, "count": len(trades)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trades/open")
def api_trades_open():
    """Get currently open trades."""
    try:
        trades = _memory.get_open_trades()

        # Add current prices
        for trade in trades:
            try:
                quote = _client.get_latest_quote(trade["symbol"])
                mid = (quote["bid"] + quote["ask"]) / 2
                entry = trade["entry_price"]
                qty = trade["quantity"]
                side = trade.get("side", "long")

                if side == "long":
                    unrealized = (mid - entry) * qty
                else:
                    unrealized = (entry - mid) * qty

                trade["current_price"] = round(mid, 2)
                trade["unrealized_pnl"] = round(unrealized, 2)
                trade["unrealized_pnl_pct"] = round(unrealized / (entry * qty), 4)
            except Exception:
                trade["current_price"] = None
                trade["unrealized_pnl"] = None

        return jsonify({"trades": trades, "count": len(trades)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Manual Close
# ============================================================

@app.route("/api/trades/<int:trade_id>/close", methods=["POST"])
def api_close_trade(trade_id):
    """Manually close an open trade from the dashboard."""
    try:
        # Find the open trade
        open_trades = _memory.get_open_trades()
        trade = next((t for t in open_trades if t["id"] == trade_id), None)
        if not trade:
            return jsonify({"error": "Trade not found or already closed"}), 404

        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade.get("side", "long")

        # Get current price
        quote = _client.get_latest_quote(symbol)
        exit_price = round((quote["bid"] + quote["ask"]) / 2, 2)

        # Submit close order via Alpaca
        from alpaca.trading.requests import MarketOrderRequest, OrderSide, TimeInForce

        close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=int(abs(qty)),
            side=close_side,
            time_in_force=TimeInForce.DAY,
        )
        _client.trading.submit_order(order_data)

        # Calculate P&L
        entry_price = trade["entry_price"]
        if side == "long":
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty
        pnl_pct = pnl / (entry_price * qty) if entry_price * qty > 0 else 0

        # Hold time
        entry_time = datetime.fromisoformat(trade["timestamp"])
        hold_minutes = (datetime.now() - entry_time).total_seconds() / 60

        # Update DB
        _memory.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_reason="manual",
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            hold_minutes=round(hold_minutes, 1),
        )

        emoji = "✅" if pnl > 0 else "❌"
        logger.info(f"{emoji} Manual close: {symbol} | P&L: ${pnl:.2f} ({pnl_pct:.1%})")

        return jsonify({
            "success": True,
            "symbol": symbol,
            "exit_price": exit_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 4),
        })

    except Exception as e:
        logger.error(f"Manual close error for trade {trade_id}: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Strategies
# ============================================================

@app.route("/api/strategies")
def api_strategies():
    """Get strategy scores and allocation."""
    try:
        if _selector is None:
            return jsonify({"strategies": {}, "error": "StrategySelector not initialized"})

        # Load scores
        scores_path = STRATEGIES_CONFIG_DIR / "scores.json"
        if scores_path.exists():
            with open(scores_path) as f:
                scores = json.load(f)
        else:
            scores = {}

        # Load allocation
        alloc_path = STRATEGIES_CONFIG_DIR / "allocation.json"
        if alloc_path.exists():
            with open(alloc_path) as f:
                allocation = json.load(f)
        else:
            allocation = {}

        # Strategy details
        strategies = {}
        for name, strategy in _selector.all_strategies.items():
            strategies[name] = {
                "name": name,
                "enabled": strategy.enabled,
                "score": scores.get("scores", {}).get(name, 50),
                "allocation": allocation.get("allocation", {}).get(name, 0),
                "activation_conditions": strategy.activation_conditions,
                "timeframe": strategy.timeframe,
            }

        return jsonify({"strategies": strategies})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies/<strategy_name>/performance")
def api_strategy_performance(strategy_name):
    """Get detailed performance for a strategy."""
    try:
        perf = _memory.get_strategy_performance(strategy_name)
        return jsonify(perf)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Chart Data (for TradingView Lightweight Charts)
# ============================================================

@app.route("/api/chart/<symbol>")
def api_chart(symbol):
    """
    Get OHLCV + indicators for charting.
    Query params: timeframe (default 5Min), limit (default 100)
    """
    try:
        timeframe = request.args.get("timeframe", "5Min")
        limit = int(request.args.get("limit", "100"))

        df = _client.get_bars(symbol.upper(), timeframe, limit)
        df = _indicator_calc.add_all_indicators(df)

        # Format for TradingView Lightweight Charts
        candles = []
        for _, row in df.iterrows():
            ts = row.get("timestamp")
            if hasattr(ts, "timestamp"):
                t = int(ts.timestamp())
            else:
                t = int(datetime.now().timestamp())

            candles.append({
                "time": t,
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            })

        # Indicator series
        indicators = {}
        for col in ["ema_9", "ema_21", "vwap", "bb_upper", "bb_lower"]:
            if col in df.columns:
                series = []
                for _, row in df.iterrows():
                    val = row.get(col)
                    ts = row.get("timestamp")
                    if val is not None and not (isinstance(val, float) and val != val):
                        t = int(ts.timestamp()) if hasattr(ts, "timestamp") else 0
                        series.append({"time": t, "value": round(float(val), 2)})
                indicators[col] = series

        # Trade markers for this symbol
        today_trades = _memory.get_today_trades()
        markers = []
        for trade in today_trades:
            if trade["symbol"] == symbol.upper():
                is_buy = trade.get("side") == "long"
                ts_str = trade.get("timestamp", "")
                try:
                    t = int(datetime.fromisoformat(ts_str).timestamp())
                except Exception:
                    t = 0

                markers.append({
                    "time": t,
                    "position": "belowBar" if is_buy else "aboveBar",
                    "color": "#22c55e" if is_buy else "#ef4444",
                    "shape": "arrowUp" if is_buy else "arrowDown",
                    "text": f"{trade.get('strategy', '')} {'BUY' if is_buy else 'SELL'}",
                })

                # Add exit marker
                if trade.get("exit_timestamp") and trade.get("status") == "closed":
                    try:
                        exit_t = int(datetime.fromisoformat(trade["exit_timestamp"]).timestamp())
                    except Exception:
                        exit_t = 0

                    pnl = trade.get("pnl", 0)
                    markers.append({
                        "time": exit_t,
                        "position": "aboveBar" if is_buy else "belowBar",
                        "color": "#22c55e" if pnl > 0 else "#ef4444",
                        "shape": "circle",
                        "text": f"EXIT ${pnl:+.2f}" if pnl else "EXIT",
                    })

        return jsonify({
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "candles": candles,
            "indicators": indicators,
            "markers": markers,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - TradingView Webhook (for Pine Script)
# ============================================================

@app.route("/api/tradingview/signals")
def api_tv_signals():
    """
    Endpoint for TradingView Pine Script to poll.
    Returns current open trades and recent signals.
    """
    try:
        open_trades = _memory.get_open_trades()
        today_trades = _memory.get_today_trades()

        signals = []
        for trade in today_trades:
            signals.append({
                "symbol": trade["symbol"],
                "side": trade.get("side", "long"),
                "strategy": trade.get("strategy", ""),
                "entry_price": trade.get("entry_price", 0),
                "stop_loss": trade.get("stop_loss_price", 0),
                "take_profit": trade.get("take_profit_price", 0),
                "status": trade.get("status", ""),
                "pnl": trade.get("pnl"),
                "timestamp": trade.get("timestamp", ""),
                "exit_reason": trade.get("exit_reason"),
            })

        return jsonify({
            "open_positions": [t["symbol"] for t in open_trades],
            "signals": signals,
            "updated": datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Daily Summary + History
# ============================================================

@app.route("/api/daily")
def api_daily():
    """Get daily summaries."""
    try:
        days = int(request.args.get("days", "30"))
        summaries = _memory.get_daily_summaries(last_n=days)
        return jsonify({"summaries": summaries})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/learnings")
def api_learnings():
    """Get active learnings."""
    try:
        learnings = _memory.get_active_learnings()
        return jsonify({"learnings": learnings})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API - Claude Coach
# ============================================================

@app.route("/api/coach")
def api_coach():
    """
    Full Claude Coach data for the dashboard tab.
    Returns learnings, score history, daily summaries, last run info.
    """
    try:
        # Active learnings from DB
        learnings = _memory.get_active_learnings()

        # Daily summaries (last 30 days) for P&L chart
        daily = _memory.get_daily_summaries(last_n=30)

        # Strategy score history (last 100 updates)
        conn = _memory._get_conn()
        try:
            score_rows = conn.execute(
                """SELECT timestamp, strategy, score, win_rate, profit_factor,
                          total_trades, allocation_pct, reason
                   FROM strategy_scores
                   ORDER BY timestamp DESC LIMIT 200"""
            ).fetchall()
            score_history = [dict(r) for r in score_rows]

            # Last coach run (latest learning timestamp)
            last_run_row = conn.execute(
                "SELECT MAX(timestamp) as ts FROM learnings WHERE source = 'claude_coach'"
            ).fetchone()
            last_run = last_run_row["ts"] if last_run_row and last_run_row["ts"] else None

            # Coach change log (score changes with reason)
            changes = conn.execute(
                """SELECT timestamp, strategy, score, reason
                   FROM strategy_scores
                   WHERE reason != '' AND reason IS NOT NULL
                   ORDER BY timestamp DESC LIMIT 50"""
            ).fetchall()
            changes = [dict(r) for r in changes]

            recs = conn.execute(
                """SELECT timestamp, change_type, target, before_state, after_state,
                          evidence_count, confidence, review_date, status
                   FROM coach_recommendations
                   ORDER BY timestamp DESC LIMIT 50"""
            ).fetchall()
            recommendations = [dict(r) for r in recs]

            # Overall stats
            total_trades_row = conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE status='closed'"
            ).fetchone()
            total_trades = total_trades_row["c"] if total_trades_row else 0

            total_pnl_row = conn.execute(
                "SELECT COALESCE(SUM(pnl),0) as s FROM trades WHERE status='closed'"
            ).fetchone()
            total_pnl = total_pnl_row["s"] if total_pnl_row else 0

            win_row = conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE status='closed' AND pnl > 0"
            ).fetchone()
            total_wins = win_row["c"] if win_row else 0

        finally:
            conn.close()

        # Read learnings.md for human-readable summary
        learnings_md = ""
        md_path = MEMORY_DIR / "learnings.md"
        if md_path.exists():
            learnings_md = md_path.read_text(encoding="utf-8")

        # Read strategy_performance.md
        perf_md = ""
        perf_path = MEMORY_DIR / "strategy_performance.md"
        if perf_path.exists():
            perf_md = perf_path.read_text(encoding="utf-8")

        return jsonify({
            "last_run": last_run,
            "learnings": learnings,
            "learnings_md": learnings_md,
            "score_history": score_history,
            "changes": changes,
            "recommendations": recommendations,
            "daily_summaries": daily,
            "overall": {
                "total_trades": total_trades,
                "total_pnl": round(total_pnl, 2),
                "total_wins": total_wins,
                "win_rate": round(total_wins / total_trades, 3) if total_trades > 0 else 0,
            },
        })
    except Exception as e:
        logger.exception("Coach API error")
        return jsonify({"error": str(e)}), 500


# ============================================================
# Server-Sent Events (real-time updates)
# ============================================================

@app.route("/api/stream")
def api_stream():
    """SSE endpoint for real-time updates."""
    def generate():
        while True:
            try:
                data = {
                    "today_pnl": round(_memory.get_today_pnl(), 2),
                    "today_trades": _memory.get_today_trade_count(),
                    "open_positions": len(_memory.get_open_trades()),
                    "market_open": _market_hours.is_market_open(),
                    "session": _market_hours.get_current_session().name
                        if _market_hours.get_current_session() else "closed",
                    "timestamp": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(5)

    return Response(generate(), mimetype="text/event-stream")


# ============================================================
# Run
# ============================================================

def run_dashboard(port: int = 5555, debug: bool = False):
    """Start the dashboard server."""
    init_components()
    logger.info(f"Dashboard starting on http://localhost:{port}")
    print(f"\n🖥  Dashboard: http://localhost:{port}")
    print(f"📊 API:       http://localhost:{port}/api/status")
    print(f"📈 Charts:    http://localhost:{port}/api/chart/AAPL")
    print(f"🔗 TV Signals: http://localhost:{port}/api/tradingview/signals\n")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trading Agent Dashboard")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_dashboard(port=args.port, debug=args.debug)
