"""
Telegram Bot - Real-time alerts and commands for the trading agent.

Sends:
  - Trade opened/closed notifications
  - Daily summary
  - Error alerts
  - Status updates

Commands:
  /status  - Current agent status
  /pnl     - Today's P&L
  /scores  - Strategy scores
  /trades  - Today's trades
  /pause   - Pause trading
  /resume  - Resume trading
"""

import logging
import json
from datetime import datetime
from typing import Optional

import requests

from agent.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends notifications to Telegram.
    Uses the HTTP API directly (no async dependency needed).
    """

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        if not self.enabled:
            logger.warning(
                "Telegram not configured. Set TELEGRAM_BOT_TOKEN and "
                "TELEGRAM_CHAT_ID in .env"
            )

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        if not self.enabled:
            logger.debug(f"Telegram disabled, would send: {text[:100]}...")
            return False

        logger.info(f"Telegram: sending message ({len(text)} chars) to chat_id={self.chat_id}")
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f"Telegram: message sent OK")
            else:
                logger.error(f"Telegram: HTTP {response.status_code} - {response.text[:200]}")
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Telegram connection and send a test message. Call this to diagnose issues."""
        if not self.enabled:
            logger.warning("Telegram not enabled (no token/chat_id)")
            return False
        try:
            # First check if bot token is valid
            resp = requests.get(f"{self.base_url}/getMe", timeout=10)
            if resp.status_code == 200:
                bot_info = resp.json()
                logger.info(f"Telegram bot OK: @{bot_info['result'].get('username', '?')}")
            else:
                logger.error(f"Telegram bot token invalid: {resp.status_code} {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False
        # Now send a test message
        return self.send_message("🤖 <b>Trading Agent</b> — Telegram test message. Working!")

    # ============================================================
    # Trade Notifications
    # ============================================================

    def notify_trade_opened(self, trade: dict):
        """Notify about a new trade."""
        side_emoji = "📈" if trade.get("side") == "long" else "📉"
        msg = (
            f"{side_emoji} <b>TRADE OPENED</b>\n"
            f"Strategy: {trade.get('strategy', '?')}\n"
            f"Symbol: <b>{trade.get('symbol', '?')}</b>\n"
            f"Side: {trade.get('side', '?').upper()}\n"
            f"Shares: {trade.get('quantity', 0)}\n"
            f"Entry: ${trade.get('entry_price', 0):.2f}\n"
            f"Stop Loss: ${trade.get('stop_loss_price', 0):.2f}\n"
            f"Take Profit: ${trade.get('take_profit_price', 0):.2f}\n"
            f"Position: {trade.get('position_pct', 0):.1%}\n"
            f"Reason: {trade.get('entry_reason', '?')}"
        )
        self.send_message(msg)

    def notify_trade_closed(self, result: dict):
        """Notify about a closed trade."""
        pnl = result.get("pnl", 0)
        emoji = "✅" if pnl > 0 else "❌"
        pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"

        msg = (
            f"{emoji} <b>TRADE CLOSED</b>\n"
            f"Symbol: <b>{result.get('symbol', '?')}</b>\n"
            f"P&L: <b>{pnl_str}</b> ({result.get('pnl_pct', 0):.2%})\n"
            f"Reason: {result.get('exit_reason', '?')}\n"
            f"Hold: {result.get('hold_minutes', 0):.0f} min"
        )
        self.send_message(msg)

    def notify_all_closed(self, results: list, reason: str):
        """Notify that all positions were closed."""
        total_pnl = sum(r.get("pnl", 0) for r in results)
        emoji = "🛑" if reason == "daily_loss_limit" else "🔔"

        msg = (
            f"{emoji} <b>ALL POSITIONS CLOSED</b>\n"
            f"Reason: {reason}\n"
            f"Positions: {len(results)}\n"
            f"Total P&L: <b>${total_pnl:+,.2f}</b>"
        )
        self.send_message(msg)

    # ============================================================
    # Status Notifications
    # ============================================================

    def notify_daily_start(self, status: dict):
        """Send morning status when agent starts trading."""
        market = status.get("market", {})
        trading = status.get("trading", {})

        msg = (
            f"🌅 <b>AGENT STARTED</b>\n"
            f"Time: {market.get('time_et', '?')}\n"
            f"Session: {market.get('current_session', '?')}\n"
            f"Portfolio: ${trading.get('portfolio_value', 0):,.2f}\n"
            f"Cash: ${trading.get('cash', 0):,.2f}"
        )
        self.send_message(msg)

    def notify_daily_summary(self, summary: dict):
        """Send end-of-day summary."""
        total_pnl = summary.get("total_pnl", 0)
        emoji = "🟢" if total_pnl >= 0 else "🔴"
        wins = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        total = summary.get("total_trades", 0)
        win_rate = (wins / total * 100) if total > 0 else 0

        msg = (
            f"{emoji} <b>DAILY SUMMARY</b>\n"
            f"{'=' * 25}\n"
            f"Trades: {total} ({wins}W / {losses}L)\n"
            f"Win Rate: {win_rate:.0f}%\n"
            f"P&L: <b>${total_pnl:+,.2f}</b>\n"
            f"Best: ${summary.get('best_trade_pnl', 0):+,.2f}\n"
            f"Worst: ${summary.get('worst_trade_pnl', 0):+,.2f}\n"
            f"Strategies: {', '.join(summary.get('strategies_used', []))}"
        )
        self.send_message(msg)

    def notify_error(self, error: str):
        """Send error alert."""
        msg = f"🚨 <b>ERROR</b>\n{error}"
        self.send_message(msg)

    def notify_risk_alert(self, alert: str):
        """Send risk management alert."""
        msg = f"⚠️ <b>RISK ALERT</b>\n{alert}"
        self.send_message(msg)

    def notify_system_alert(self, title: str, details: str):
        """Send operational health alert."""
        msg = (
            f"🛠️ <b>{title}</b>\n"
            f"{details}"
        )
        self.send_message(msg)

    def notify_cooling(self, consecutive_losses: int, minutes: int):
        """Notify about cooling period."""
        msg = (
            f"❄️ <b>COOLING PERIOD</b>\n"
            f"{consecutive_losses} consecutive losses\n"
            f"Pausing for {minutes} minutes"
        )
        self.send_message(msg)

    # ============================================================
    # Command Responses (for future interactive bot)
    # ============================================================

    def format_status(self, status: dict) -> str:
        """Format status dict as readable message."""
        market = status.get("market", {})
        trading = status.get("trading", {})
        risk = status.get("risk", {})

        lines = [
            "<b>📊 AGENT STATUS</b>",
            f"Time: {market.get('time_et', '?')}",
            f"Market: {'Open' if market.get('is_market_open') else 'Closed'}",
            f"Session: {market.get('current_session', '?')}",
            "",
            f"💰 Portfolio: ${trading.get('portfolio_value', 0):,.2f}",
            f"Open: {trading.get('open_positions', 0)} positions",
            f"Today: {trading.get('today_trade_count', 0)} trades",
            f"P&L: ${trading.get('today_pnl', 0):+,.2f}",
            "",
            f"🛡 Can Trade: {'Yes' if risk.get('can_trade') else 'NO'}",
            f"Loss Remaining: ${risk.get('daily_loss_remaining', 0):,.2f}",
        ]

        if risk.get("cooling_active"):
            lines.append(f"❄️ Cooling until: {risk.get('cooling_until')}")

        return "\n".join(lines)

    def format_scores(self, scores: dict, allocation: dict) -> str:
        """Format strategy scores as readable message."""
        lines = ["<b>🎯 STRATEGY SCORES</b>", ""]

        for name, data in sorted(
            scores.items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True,
        ):
            score = data.get("score", "?")
            trades = data.get("total_trades", 0)
            wr = data.get("win_rate", 0)
            alloc = allocation.get(name, 0)

            if isinstance(score, (int, float)) and score >= 70:
                emoji = "🟢"
            elif isinstance(score, (int, float)) and score >= 50:
                emoji = "🟡"
            else:
                emoji = "🔴"

            lines.append(
                f"{emoji} <b>{name}</b>: {score} "
                f"({trades} trades, {wr:.0%} WR, {alloc:.0%} alloc)"
            )

        return "\n".join(lines)


# Convenience instance
notifier = TelegramNotifier()
