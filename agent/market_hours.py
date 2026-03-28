"""
Market Hours - Sessions, holidays, timezone handling.
All times are in US Eastern Time (ET).
"""

from datetime import datetime, time, date, timedelta
from typing import Optional
import pytz

# US Eastern timezone
ET = pytz.timezone("US/Eastern")
IST = pytz.timezone("Asia/Jerusalem")


# ============================================================
# Market Holidays 2026 (NYSE/NASDAQ)
# ============================================================
MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
}

# Early close days (market closes at 13:00 ET)
EARLY_CLOSE_DAYS_2026 = {
    date(2026, 11, 27),  # Day after Thanksgiving
    date(2026, 12, 24),  # Christmas Eve
}


class MarketSession:
    """Represents a trading session with its characteristics."""

    def __init__(self, name: str, start: time, end: time,
                 check_interval: int, trading_allowed: bool):
        self.name = name
        self.start = start
        self.end = end
        self.check_interval = check_interval  # seconds
        self.trading_allowed = trading_allowed

    def is_active(self, current_time: time) -> bool:
        """Check if this session is currently active."""
        return self.start <= current_time < self.end

    def __repr__(self):
        return f"<Session {self.name} {self.start}-{self.end}>"


# Define all sessions
SESSIONS = {
    "premarket": MarketSession(
        name="premarket",
        start=time(4, 0),
        end=time(9, 30),
        check_interval=300,    # 5 min - scan only
        trading_allowed=False,
    ),
    "opening": MarketSession(
        name="opening",
        start=time(9, 30),
        end=time(10, 30),
        check_interval=30,     # every 30 sec - aggressive
        trading_allowed=True,
    ),
    "midday": MarketSession(
        name="midday",
        start=time(10, 30),
        end=time(14, 30),
        check_interval=300,    # every 5 min - conservative
        trading_allowed=True,
    ),
    "power_hour": MarketSession(
        name="power_hour",
        start=time(14, 30),
        end=time(16, 0),
        check_interval=120,    # every 2 min - aggressive
        trading_allowed=True,
    ),
}


class MarketHours:
    """
    Handles all market hours logic:
    - Is market open?
    - What session are we in?
    - How long until next check?
    - Holiday/early close detection
    """

    def __init__(self):
        self.holidays = MARKET_HOLIDAYS_2026
        self.early_close_days = EARLY_CLOSE_DAYS_2026
        self.sessions = SESSIONS

    def now_et(self) -> datetime:
        """Get current time in ET."""
        return datetime.now(ET)

    def now_ist(self) -> datetime:
        """Get current time in Israel time."""
        return datetime.now(IST)

    def today_et(self) -> date:
        """Get today's date in ET."""
        return self.now_et().date()

    def is_holiday(self, check_date: Optional[date] = None) -> bool:
        """Check if a given date is a market holiday."""
        check_date = check_date or self.today_et()
        return check_date in self.holidays

    def is_weekend(self, check_date: Optional[date] = None) -> bool:
        """Check if it's a weekend (Sat=5, Sun=6)."""
        check_date = check_date or self.today_et()
        return check_date.weekday() >= 5

    def is_early_close(self, check_date: Optional[date] = None) -> bool:
        """Check if today is an early close day (closes at 13:00 ET)."""
        check_date = check_date or self.today_et()
        return check_date in self.early_close_days

    def is_market_open(self) -> bool:
        """Is the market currently open for regular trading?"""
        now = self.now_et()
        today = now.date()

        # Weekend or holiday
        if self.is_weekend(today) or self.is_holiday(today):
            return False

        current_time = now.time()

        # Early close day
        if self.is_early_close(today):
            return time(9, 30) <= current_time < time(13, 0)

        # Regular day
        return time(9, 30) <= current_time < time(16, 0)

    def get_current_session(self) -> Optional[MarketSession]:
        """Get the current trading session, or None if outside sessions."""
        now = self.now_et()
        today = now.date()

        # No sessions on weekends/holidays
        if self.is_weekend(today) or self.is_holiday(today):
            return None

        current_time = now.time()

        # Early close day - adjust power_hour end
        if self.is_early_close(today):
            # Power hour doesn't exist on early close days
            # Midday ends at 13:00
            if time(10, 30) <= current_time < time(13, 0):
                return self.sessions["midday"]
            elif time(9, 30) <= current_time < time(10, 30):
                return self.sessions["opening"]
            elif time(4, 0) <= current_time < time(9, 30):
                return self.sessions["premarket"]
            return None

        # Regular day - check all sessions
        for session in self.sessions.values():
            if session.is_active(current_time):
                return session

        return None

    def get_check_interval(self) -> int:
        """
        Get the current check interval in seconds.
        Returns the session's check interval, or 60 if outside sessions.
        """
        session = self.get_current_session()
        if session:
            return session.check_interval
        return 60  # Default: check every minute when outside sessions

    def should_close_all(self) -> bool:
        """Is it time to close all positions? (15:50 ET)"""
        now = self.now_et()
        today = now.date()

        if self.is_weekend(today) or self.is_holiday(today):
            return False

        current_time = now.time()

        if self.is_early_close(today):
            return current_time >= time(12, 50)  # Close by 12:50 on early days

        return current_time >= time(15, 50)

    def can_open_new_positions(self) -> bool:
        """Can we open new positions? (before 15:45 ET)"""
        now = self.now_et()
        today = now.date()

        if self.is_weekend(today) or self.is_holiday(today):
            return False

        if not self.is_market_open():
            return False

        current_time = now.time()

        if self.is_early_close(today):
            return current_time < time(12, 45)

        return current_time < time(15, 45)

    def time_until_market_open(self) -> Optional[timedelta]:
        """How long until market opens? None if already open."""
        if self.is_market_open():
            return None

        now = self.now_et()
        today = now.date()

        # Find next trading day
        next_day = today
        if now.time() >= time(16, 0):
            next_day += timedelta(days=1)

        # Skip weekends and holidays
        while self.is_weekend(next_day) or self.is_holiday(next_day):
            next_day += timedelta(days=1)

        # Market opens at 9:30 ET
        market_open = ET.localize(datetime.combine(next_day, time(9, 30)))
        return market_open - now

    def get_next_trading_session_info(self) -> dict:
        """
        Returns info about the next session that allows trading.
        Used for log messages when market is closed or in premarket.
        Returns dict with: name, start_et, end_et, start_ist, end_ist, day_label
        """
        now = self.now_et()
        today = now.date()
        current_time = now.time()

        # Sessions with trading, in order
        trading_sessions = [
            ("opening",    time(9, 30),  time(10, 30)),
            ("midday",     time(10, 30), time(14, 30)),
            ("power_hour", time(14, 30), time(16, 0)),
        ]

        def _fmt_et_ist(d: date, t: time) -> tuple[str, str]:
            dt_et = ET.localize(datetime.combine(d, t))
            dt_ist = dt_et.astimezone(IST)
            return dt_et.strftime("%H:%M"), dt_ist.strftime("%H:%M")

        def _next_trading_day(from_date: date) -> date:
            d = from_date + timedelta(days=1)
            while self.is_weekend(d) or self.is_holiday(d):
                d += timedelta(days=1)
            return d

        # If it's a trading day, look for the next session still ahead today
        if not self.is_weekend(today) and not self.is_holiday(today):
            for name, start, end in trading_sessions:
                if current_time < start:
                    start_et, start_ist = _fmt_et_ist(today, start)
                    end_et, end_ist = _fmt_et_ist(today, end)
                    return {
                        "name": name,
                        "day_label": "היום",
                        "start_et": start_et, "end_et": end_et,
                        "start_ist": start_ist, "end_ist": end_ist,
                    }

        # No more sessions today → find next trading day opening
        next_day = _next_trading_day(today)
        start_et, start_ist = _fmt_et_ist(next_day, time(9, 30))
        end_et, end_ist     = _fmt_et_ist(next_day, time(10, 30))
        day_names = {0: "ב׳", 1: "ג׳", 2: "ד׳", 3: "ה׳", 4: "ו׳", 5: "ש׳", 6: "א׳"}
        day_label = f"יום {day_names.get(next_day.weekday(), '')} {next_day.strftime('%d/%m')}"
        return {
            "name": "opening",
            "day_label": day_label,
            "start_et": start_et, "end_et": end_et,
            "start_ist": start_ist, "end_ist": end_ist,
        }

    def get_status(self) -> dict:
        """Get a complete market status summary."""
        now = self.now_et()
        session = self.get_current_session()
        is_open = self.is_market_open()

        status = {
            "time_et": now.strftime("%H:%M:%S ET"),
            "time_ist": self.now_ist().strftime("%H:%M:%S IST"),
            "date": now.strftime("%Y-%m-%d"),
            "day": now.strftime("%A"),
            "is_market_open": is_open,
            "is_holiday": self.is_holiday(),
            "is_early_close": self.is_early_close(),
            "current_session": session.name if session else "closed",
            "check_interval": self.get_check_interval(),
            "can_open_positions": self.can_open_new_positions(),
            "should_close_all": self.should_close_all(),
        }

        if not is_open:
            until = self.time_until_market_open()
            if until:
                hours = int(until.total_seconds() // 3600)
                minutes = int((until.total_seconds() % 3600) // 60)
                status["time_until_open"] = f"{hours}h {minutes}m"

        # Always include next trading session info
        status["next_session"] = self.get_next_trading_session_info()

        return status


# Convenience instance
market_hours = MarketHours()


if __name__ == "__main__":
    """Quick test."""
    mh = MarketHours()
    status = mh.get_status()
    print("=== Market Status ===")
    for key, value in status.items():
        print(f"  {key}: {value}")
