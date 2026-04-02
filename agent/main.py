"""
Main - Entry point for the Trading Agent.

Usage:
    python -m agent.main              # Run the agent
    python -m agent.main --status     # Show current status
    python -m agent.main --test       # Test Alpaca connection
"""

import argparse
import logging
import sys
from pathlib import Path

from agent.config import LOG_LEVEL, LOGS_DIR, ensure_directories


def setup_logging():
    """Configure logging to both console and file."""
    ensure_directories()

    from datetime import date, datetime, timedelta
    try:
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        # If before 4 AM ET, use yesterday's date for log file
        trading_date = now_et.date() if now_et.hour >= 4 else (now_et.date() - timedelta(days=1))
    except Exception:
        trading_date = date.today()
    log_file = LOGS_DIR / f"agent_{trading_date.isoformat()}.log"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)

    # File handler (more detail)
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("alpaca").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


def cmd_run():
    """Run the trading agent."""
    logger = setup_logging()
    logger.info("Starting Trading Agent...")

    try:
        from agent.core import TradingAgent
        agent = TradingAgent()
    except Exception as e:
        logger.critical(f"FATAL: Failed to initialize TradingAgent: {e}", exc_info=True)
        sys.exit(1)

    try:
        agent.run()
    except Exception as e:
        logger.critical(f"FATAL: Agent run() crashed unexpectedly: {e}", exc_info=True)
        sys.exit(1)


def cmd_status():
    """Show current status without running the agent."""
    setup_logging()

    from agent.core import TradingAgent

    agent = TradingAgent()
    status = agent.get_full_status()

    print("\n" + "=" * 50)
    print("    TRADING AGENT STATUS")
    print("=" * 50)

    # Market
    m = status["market"]
    print(f"\n📊 Market:")
    print(f"  Time:     {m['time_et']} ({m['time_ist']})")
    print(f"  Open:     {'Yes' if m['is_market_open'] else 'No'}")
    print(f"  Session:  {m['current_session']}")
    if m.get("time_until_open"):
        print(f"  Opens in: {m['time_until_open']}")

    # Trading
    t = status["trading"]
    print(f"\n💰 Portfolio:")
    print(f"  Value:    ${t['portfolio_value']:,.2f}")
    print(f"  Cash:     ${t['cash']:,.2f}")
    print(f"  Open:     {t['open_positions']} positions")
    print(f"  Today:    {t['today_trade_count']} trades, P&L: ${t['today_pnl']:+,.2f}")

    # Risk
    r = status["risk"]
    print(f"\n🛡 Risk:")
    print(f"  Can trade:   {'Yes' if r['can_trade'] else 'NO'}")
    print(f"  Daily loss:  ${r['today_pnl']:+,.2f} / -${r['max_daily_loss']:,.2f}")
    print(f"  Trades:      {r['today_trades']}/{r['max_daily_trades']}")
    print(f"  Consec loss: {r['consecutive_losses']}")
    if r["cooling_active"]:
        print(f"  COOLING:     Until {r['cooling_until']}")

    # Strategies
    print(f"\n🎯 Strategies:")
    for name, info in status["strategies"].items():
        emoji = "✅" if info["enabled"] else "❌"
        alloc = status["allocation"].get(name, 0)
        print(f"  {emoji} {name}: alloc={alloc:.0%}")

    print("\n" + "=" * 50)


def cmd_test():
    """Test Alpaca connection."""
    setup_logging()

    from agent.market_data import AlpacaClient

    print("\n🔗 Testing Alpaca connection...")

    try:
        client = AlpacaClient()
        account = client.get_account()

        print(f"\n✅ Connection successful!")
        print(f"  Equity:        ${account['equity']:,.2f}")
        print(f"  Buying Power:  ${account['buying_power']:,.2f}")
        print(f"  Cash:          ${account['cash']:,.2f}")
        print(f"  Day Trades:    {account['day_trade_count']}")

        # Test market data
        print(f"\n📈 Testing market data (SPY)...")
        df = client.get_bars("SPY", "5Min", limit=5)
        print(f"  Got {len(df)} bars")
        if not df.empty:
            latest = df.iloc[-1]
            print(f"  Latest close: ${float(latest['close']):.2f}")

        print(f"\n✅ All tests passed!")

    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
        print(f"   Make sure .env file has ALPACA_API_KEY and ALPACA_SECRET_KEY")
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Day Trading Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main              Run the trading agent
  python -m agent.main --status     Show current status
  python -m agent.main --test       Test Alpaca connection
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true",
                       help="Show current status")
    group.add_argument("--test", action="store_true",
                       help="Test Alpaca connection")

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.test:
        cmd_test()
    else:
        cmd_run()


if __name__ == "__main__":
    main()
