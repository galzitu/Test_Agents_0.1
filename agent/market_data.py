"""
Market Data - Alpaca API connection + technical indicators.
Fetches price data and computes all indicators needed by strategies.
Uses the `ta` library for technical analysis.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from agent.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
)
from agent.market_condition import MarketSnapshot

logger = logging.getLogger(__name__)


# ============================================================
# Alpaca Client Wrapper
# ============================================================

class AlpacaClient:
    """
    Wrapper for Alpaca API.
    Handles: account info, market data, order execution.
    """

    def __init__(self):
        self._client = None
        self._data_client = None
        self._trading_client = None

    def _ensure_connected(self):
        """Lazy-initialize Alpaca clients."""
        if self._trading_client is not None:
            return

        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise ValueError(
                "Alpaca API keys not configured. "
                "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )

        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient

            self._trading_client = TradingClient(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
                paper=True,
            )
            self._data_client = StockHistoricalDataClient(
                ALPACA_API_KEY,
                ALPACA_SECRET_KEY,
            )
            logger.info("Connected to Alpaca (paper trading)")
        except ImportError:
            raise ImportError(
                "alpaca-py not installed. Run: pip install alpaca-py"
            )

    @property
    def trading(self):
        self._ensure_connected()
        return self._trading_client

    @property
    def data(self):
        self._ensure_connected()
        return self._data_client

    def get_account(self) -> dict:
        """Get account info (balance, buying power, etc.)."""
        account = self.trading.get_account()
        return {
            "equity": float(account.equity),
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "day_trade_count": account.daytrade_count,
            "pattern_day_trader": account.pattern_day_trader,
        }

    def get_bars(self, symbol: str, timeframe: str = "5Min",
                 limit: int = 100) -> pd.DataFrame:
        """
        Get historical bars for a symbol.

        Args:
            symbol: Stock ticker (e.g., "AAPL")
            timeframe: "1Min", "5Min", "15Min", "1Hour", "1Day"
            limit: Number of bars to fetch

        Returns:
            DataFrame with columns: open, high, low, close, volume, vwap
        """
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        # Map timeframe strings to Alpaca TimeFrame
        tf_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }

        if timeframe not in tf_map:
            raise ValueError(f"Unknown timeframe: {timeframe}")

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf_map[timeframe],
            limit=limit,
        )

        # Retry logic for transient connection errors
        import time as _time
        last_error = None
        for attempt in range(3):
            try:
                bars = self.data.get_stock_bars(request)
                df = bars.df

                if isinstance(df.index, pd.MultiIndex):
                    df = df.droplevel("symbol")

                df = df.reset_index()
                df.columns = [c.lower() for c in df.columns]
                return df
            except Exception as e:
                last_error = e
                if attempt < 2:
                    logger.warning(
                        f"Retry {attempt+1}/3 for {symbol} bars: {e}"
                    )
                    _time.sleep(1 + attempt)
        raise last_error

    def get_latest_quote(self, symbol: str) -> dict:
        """Get latest bid/ask quote for a symbol."""
        from alpaca.data.requests import StockLatestQuoteRequest

        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = self.data.get_stock_latest_quote(request)

        q = quote[symbol]
        return {
            "bid": float(q.bid_price),
            "ask": float(q.ask_price),
            "bid_size": q.bid_size,
            "ask_size": q.ask_size,
            "spread": float(q.ask_price - q.bid_price),
            "spread_pct": float((q.ask_price - q.bid_price) / q.ask_price),
        }

    def get_positions(self) -> list[dict]:
        """Get all current positions."""
        positions = self.trading.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": p.side,
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "market_value": float(p.market_value),
            }
            for p in positions
        ]


# ============================================================
# Technical Indicator Calculator
# ============================================================

class IndicatorCalculator:
    """
    Computes all technical indicators needed by strategies.
    Uses the `ta` library built on top of pandas.
    """

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all technical indicators to a price DataFrame.

        Input DataFrame must have columns: open, high, low, close, volume

        Returns DataFrame with added indicator columns.
        """
        import ta

        if df.empty or len(df) < 26:  # Need at least 26 bars for MACD
            logger.warning("Not enough data for indicators")
            return df

        df = df.copy()

        # --- Trend Indicators ---
        # RSI(14)
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

        # MACD(12, 26, 9)
        macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # EMA(9) and EMA(21)
        df["ema_9"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
        df["ema_21"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()

        # ADX(14)
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
        df["adx"] = adx.adx()

        # --- Volatility Indicators ---
        # ATR(14)
        df["atr"] = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()

        # Bollinger Bands(20, 2)
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_bandwidth"] = bb.bollinger_wband()

        # --- Volume Indicators ---
        # OBV
        df["obv"] = ta.volume.OnBalanceVolumeIndicator(
            df["close"], df["volume"]
        ).on_balance_volume()

        # Volume moving average (20 period)
        df["volume_avg_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_avg_20"]

        # --- VWAP ---
        # VWAP is typically calculated from start of day
        # Using ta library's VWAP if available, otherwise manual calc
        if "vwap" not in df.columns:
            try:
                df["vwap"] = ta.volume.VolumeWeightedAveragePrice(
                    high=df["high"], low=df["low"], close=df["close"],
                    volume=df["volume"], window=14,
                ).volume_weighted_average_price()
            except Exception:
                # Manual VWAP calculation
                typical_price = (df["high"] + df["low"] + df["close"]) / 3
                df["vwap"] = (
                    (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
                )

        # --- ATR average (for market condition detection) ---
        df["atr_avg_20"] = df["atr"].rolling(window=20).mean()

        # --- Crossover helpers ---
        df["macd_crossover_up"] = (
            (df["macd"] > df["macd_signal"]) &
            (df["macd"].shift(1) <= df["macd_signal"].shift(1))
        )
        df["macd_crossover_down"] = (
            (df["macd"] < df["macd_signal"]) &
            (df["macd"].shift(1) >= df["macd_signal"].shift(1))
        )
        df["ema_crossover_up"] = (
            (df["ema_9"] > df["ema_21"]) &
            (df["ema_9"].shift(1) <= df["ema_21"].shift(1))
        )
        df["ema_crossover_down"] = (
            (df["ema_9"] < df["ema_21"]) &
            (df["ema_9"].shift(1) >= df["ema_21"].shift(1))
        )

        return df

    @staticmethod
    def get_market_snapshot(df: pd.DataFrame) -> MarketSnapshot:
        """
        Extract a MarketSnapshot from the latest indicator values.
        Used by MarketConditionDetector.
        """
        if df.empty:
            raise ValueError("Empty DataFrame, cannot create snapshot")

        latest = df.iloc[-1]

        return MarketSnapshot(
            adx=float(latest.get("adx", 0) or 0),
            ema_9=float(latest.get("ema_9", 0) or 0),
            ema_21=float(latest.get("ema_21", 0) or 0),
            current_price=float(latest["close"]),
            atr=float(latest.get("atr", 0) or 0),
            atr_avg_20=float(latest.get("atr_avg_20", latest.get("atr", 1)) or 1),
            current_volume=float(latest["volume"]),
            avg_volume_20=float(latest.get("volume_avg_20", latest["volume"]) or 1),
        )

    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> dict:
        """
        Get a dict of latest indicator values.
        Useful for saving to trade records and logging.
        """
        if df.empty:
            return {}

        latest = df.iloc[-1]

        indicator_cols = [
            "rsi", "macd", "macd_signal", "macd_hist",
            "ema_9", "ema_21", "adx", "atr", "atr_avg_20",
            "bb_upper", "bb_middle", "bb_lower", "bb_bandwidth",
            "obv", "volume_ratio", "vwap",
        ]

        result = {}
        for col in indicator_cols:
            val = latest.get(col)
            if val is not None and not pd.isna(val):
                result[col] = round(float(val), 4)

        result["price"] = round(float(latest["close"]), 2)
        result["volume"] = int(latest["volume"])

        return result


# ============================================================
# Screener - Find tradeable stocks
# ============================================================

class Screener:
    """
    Pre-market screener to find stocks worth watching.
    Looks for: gaps, volume spikes, high ATR.
    """

    # Default watchlist — structured universe for strategy tournament learning
    # Research basis: GT-Score paper used top 50 S&P500 for broad strategy scoring.
    # Tournament system MUST score strategies across many symbols to discover
    # which strategy works on which instrument — core to self-improvement loop.
    #
    # Tier ordering = scan priority (high-liquidity first = freshest quotes)
    DEFAULT_WATCHLIST = [
        # ── Tier 1: Mega-cap tech (tightest spreads, EMA/VWAP/RSI+MACD)
        "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
        # ── Tier 2: Semiconductors (volatile, Momentum + Breakout)
        "AMD", "MU", "AVGO", "ARM",
        # ── Tier 3: High-beta / crypto-adjacent (ORB + Volume Spike)
        "COIN", "MARA", "PLTR", "RBLX",
        # ── Tier 4: Consumer / retail (proven: SBUX +$144; trend + mean-rev)
        "SBUX", "NFLX", "NKE",
        # ── Tier 5: Energy (proven: OXY +$63; trend following)
        "OXY", "XOM", "CVX",
        # ── Tier 6: Financials (JPM steady; EMA + mean-rev)
        "JPM", "BAC",
        # ── Tier 7: Healthcare (gap plays, earnings catalysts)
        "MRNA", "ABBV",
        # ── Tier 8: ETFs (broad market reference + high-beta sectors)
        "SPY", "QQQ", "IWM", "SOXL", "ARKK",
    ]
    # REMOVED vs original watchlist (reason):
    # PFE  → -$151 loss, death spiral risk (per-symbol cooldown protects but edge is weak)
    # NIO/JD/BABA/PDD → China ADR halt risk, regulatory overhang, low edge
    # SOFI/HOOD → low volume, wide spreads unfavorable for algos
    # INTC/QCOM → lower volatility, weak momentum edge vs AMD/NVDA
    # GS → lower retail participation, harder for momentum signals
    # DIS/MCD → too slow for day trading, better for swing

    def __init__(self, client: AlpacaClient):
        self.client = client
        self.calc = IndicatorCalculator()

    def scan_for_gaps(self, symbols: Optional[list[str]] = None,
                      min_gap_pct: float = 0.005) -> list[dict]:
        """
        Find stocks with gaps > min_gap_pct.
        Gap = (today's open - yesterday's close) / yesterday's close
        """
        symbols = symbols or self.DEFAULT_WATCHLIST
        results = []

        for symbol in symbols:
            try:
                df = self.client.get_bars(symbol, "1Day", limit=2)
                if len(df) < 2:
                    continue

                prev_close = float(df.iloc[-2]["close"])
                today_open = float(df.iloc[-1]["open"])
                gap_pct = (today_open - prev_close) / prev_close

                if abs(gap_pct) >= min_gap_pct:
                    results.append({
                        "symbol": symbol,
                        "gap_pct": gap_pct,
                        "direction": "up" if gap_pct > 0 else "down",
                        "prev_close": prev_close,
                        "today_open": today_open,
                    })
            except Exception as e:
                logger.warning(f"Failed to scan {symbol}: {e}")

        return sorted(results, key=lambda x: abs(x["gap_pct"]), reverse=True)

    def scan_volume_spikes(self, symbols: Optional[list[str]] = None,
                           min_volume_ratio: float = 2.0) -> list[dict]:
        """Find stocks with volume spikes."""
        symbols = symbols or self.DEFAULT_WATCHLIST
        results = []

        for symbol in symbols:
            try:
                df = self.client.get_bars(symbol, "5Min", limit=100)
                if len(df) < 20:
                    continue

                df = self.calc.add_all_indicators(df)
                latest = df.iloc[-1]

                vol_ratio = latest.get("volume_ratio", 0)
                if vol_ratio and vol_ratio >= min_volume_ratio:
                    results.append({
                        "symbol": symbol,
                        "volume_ratio": round(float(vol_ratio), 2),
                        "price": round(float(latest["close"]), 2),
                    })
            except Exception as e:
                logger.warning(f"Failed to scan {symbol}: {e}")

        return sorted(results, key=lambda x: x["volume_ratio"], reverse=True)


# Convenience instances
alpaca_client = AlpacaClient()
indicator_calc = IndicatorCalculator()
screener = Screener(alpaca_client)


if __name__ == "__main__":
    """Quick connection test."""
    try:
        client = AlpacaClient()
        account = client.get_account()
        print("=== Alpaca Account ===")
        for key, value in account.items():
            print(f"  {key}: {value}")

        # Test getting bars
        df = client.get_bars("AAPL", "5Min", limit=50)
        print(f"\n=== AAPL 5min bars: {len(df)} rows ===")

        # Add indicators
        df = IndicatorCalculator.add_all_indicators(df)
        indicators = IndicatorCalculator.get_latest_indicators(df)
        print("\n=== Latest Indicators ===")
        for key, value in indicators.items():
            print(f"  {key}: {value}")

        # Get market snapshot
        snapshot = IndicatorCalculator.get_market_snapshot(df)
        print(f"\n=== Market Snapshot ===")
        print(f"  ADX: {snapshot.adx:.1f}")
        print(f"  ATR ratio: {snapshot.atr_ratio:.2f}")
        print(f"  Volume ratio: {snapshot.volume_ratio:.2f}")

    except ValueError as e:
        print(f"Setup needed: {e}")
    except Exception as e:
        print(f"Error: {e}")
