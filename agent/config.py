"""
Configuration - All settings loaded from .env + hardcoded defaults.
Risk management rules are IMMUTABLE - not even Claude Coach can change them.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# Alpaca API
# ============================================================
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# ============================================================
# Telegram
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# Agent Settings
# ============================================================
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "100000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SHADOW_MODE = os.getenv("SHADOW_MODE", "false").lower() == "true"

# ============================================================
# Paths
# ============================================================
STRATEGIES_CONFIG_DIR = PROJECT_ROOT / "strategies_config"
MEMORY_DIR = PROJECT_ROOT / "memory"
LOGS_DIR = PROJECT_ROOT / "logs"
DB_PATH = MEMORY_DIR / "trading.db"

# ============================================================
# RISK MANAGEMENT - HARDCODED, IMMUTABLE
# Nobody changes these. Not Claude Coach, not the code.
# ============================================================
class RiskLimits:
    """Hardcoded risk management rules."""

    # Position limits
    MAX_POSITION_PCT = 0.05            # 5% of portfolio per trade
    OPENING_MAX_POSITION_PCT = 0.03    # 3% during opening session (volatile)
    MAX_OPEN_POSITIONS = 3

    # Stop loss
    MANDATORY_STOP_LOSS = True         # NO TRADE without stop loss
    MAX_STOP_LOSS_PCT = 0.02           # max 2% loss per trade

    # Daily limits
    MAX_DAILY_LOSS_PCT = 0.03          # 3% daily loss → agent STOPS
    MAX_DAILY_TRADES = 20
    COOLING_AFTER_CONSECUTIVE_LOSSES = 3   # 3 losses in a row → pause
    COOLING_DURATION_MINUTES = 30

    # Day trading rules
    CLOSE_ALL_BY = "15:50"             # ET - close all positions
    NO_NEW_POSITIONS_AFTER = "15:45"   # ET - stop opening new ones
    NO_OVERNIGHT = True                # NEVER hold overnight

    # Extended hours
    ALLOW_PREMARKET = False
    ALLOW_AFTERHOURS = False

    # Volume safety
    MIN_VOLUME_RATIO = 0.5             # Don't trade if volume < 50% of avg
    MIN_SPREAD_CHECK = True            # Alert if spread > 0.5%


class ExecutionConfig:
    """Execution hygiene and market microstructure safeguards."""

    SIGNAL_COOLDOWN_MINUTES = 5
    STALE_SIGNAL_OPENING_PCT = 0.006
    STALE_SIGNAL_MIDDAY_PCT = 0.003
    STALE_SIGNAL_POWER_HOUR_PCT = 0.004
    STALE_SIGNAL_ATR_MULTIPLIER = 0.35
    MAX_SPREAD_PCT = 0.005
    MIN_DOLLAR_VOLUME = 500_000
    MAX_SLIPPAGE_PCT = 0.003


class AuditConfig:
    """Retention and schema metadata for audit/event logging."""

    SCHEMA_VERSION = 2
    SIGNAL_AUDIT_RETENTION_DAYS = 30


class MonitoringConfig:
    """Operational health monitoring thresholds."""

    HEARTBEAT_STALE_SECONDS = 600
    MIN_FREE_DISK_MB = 512
    SYSTEMD_SERVICES = ["trading-agent", "trading-dashboard"]

# ============================================================
# Scoring System
# ============================================================
class ScoringConfig:
    """Strategy scoring configuration (v2.0 GT-Score inspired)."""

    MIN_TRADES_FOR_SCORE = 30          # Need 30 trades before score is reliable
    MIN_TRADES_FOR_DISABLE = 50        # Need 50 trades before disabling
    DEFAULT_SCORE = 50                 # New strategies start at 50

    # Score weights (GT-Score inspired — total = 100)
    WIN_RATE_WEIGHT = 30               # 30% weight
    PROFIT_FACTOR_WEIGHT = 25          # 25% weight
    RISK_REWARD_WEIGHT = 20            # 20% weight
    CONSISTENCY_WEIGHT = 15            # 15% weight (NEW — penalizes outlier-dependent)
    MAX_DRAWDOWN_WEIGHT = 10           # 10% weight (NEW — survivability measure)

    # Allocation limits
    MAX_ALLOCATION_PCT = 0.35          # No single strategy > 35%
    MIN_ALLOCATION_PCT = 0.05          # Minimum 5% (unless disabled)

# ============================================================
# Trading Sessions (ET timezone)
# ============================================================
class SessionConfig:
    """Trading session definitions and check intervals."""

    SESSIONS = {
        "premarket": {
            "start": "04:00",
            "end": "09:30",
            "check_interval_seconds": 300,  # 5 min - scan only
            "trading_allowed": False,
        },
        "opening": {
            "start": "09:30",
            "end": "10:30",
            "check_interval_seconds": 30,  # aggressive - every 30 sec
            "trading_allowed": True,
        },
        "midday": {
            "start": "10:30",
            "end": "14:30",
            "check_interval_seconds": 300,  # conservative - every 5 min
            "trading_allowed": True,
        },
        "power_hour": {
            "start": "14:30",
            "end": "16:00",
            "check_interval_seconds": 120,  # aggressive - every 2 min
            "trading_allowed": True,
        },
    }

    # Special times
    CLOSE_ALL_TIME = "15:50"
    NO_NEW_AFTER = "15:45"

# ============================================================
# Market Condition Thresholds
# ============================================================
class MarketConditionConfig:
    """Thresholds for market condition detection."""

    ADX_TREND_THRESHOLD = 25           # ADX > 25 = trending
    ADX_RANGING_THRESHOLD = 20         # ADX < 20 = ranging
    ATR_VOLATILE_RATIO = 1.5           # ATR > 1.5x avg = volatile
    ATR_QUIET_RATIO = 0.7              # ATR < 0.7x avg = quiet
    VOLUME_LOW_RATIO = 0.3             # Volume < 0.3x avg = low volume (don't trade!)
    VOLUME_HIGH_RATIO = 2.0            # Volume > 2x avg = high activity


def ensure_directories():
    """Create all necessary directories."""
    for dir_path in [STRATEGIES_CONFIG_DIR, MEMORY_DIR, LOGS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
