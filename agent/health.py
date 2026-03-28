"""
Operational health monitoring for the trading agent runtime.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.config import LOGS_DIR, MonitoringConfig
from agent.memory import Memory

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Tracks heartbeats and performs lightweight runtime health checks."""

    def __init__(self, memory: Memory, health_file: Optional[Path] = None):
        self.memory = memory
        self.health_file = health_file or (LOGS_DIR / "health_status.json")

    def record_heartbeat(self, component: str, status: str,
                         details: Optional[dict] = None):
        payload = {
            "component": component,
            "status": status,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }
        self.memory.set_heartbeat(component, status, details or {})

        current = self.read_health_file()
        current[component] = payload
        self.health_file.write_text(
            json.dumps(current, indent=2, default=str),
            encoding="utf-8",
        )

    def read_health_file(self) -> dict:
        if not self.health_file.exists():
            return {}
        try:
            return json.loads(self.health_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def run_checks(self, market_hours, client=None) -> dict:
        """Run non-fatal runtime checks used by dashboard and Telegram alerts."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "db_writable": self._check_db_writable(),
            "disk_ok": self._check_disk_space(),
            "agent_heartbeat_fresh": self._check_heartbeat_fresh("agent"),
            "dashboard_heartbeat_fresh": self._check_heartbeat_fresh("dashboard"),
            "alpaca_reachable": self._check_alpaca(client),
            "market_open": market_hours.is_market_open(),
            "systemd": self._check_systemd_services(),
        }
        self.record_heartbeat("health_monitor", "ok", results)
        return results

    def _check_db_writable(self) -> bool:
        try:
            self.memory.set_heartbeat("db_probe", "ok", {"probe": "write"})
            return True
        except Exception as exc:
            logger.warning("DB writability check failed: %s", exc)
            return False

    def _check_disk_space(self) -> bool:
        usage = shutil.disk_usage(LOGS_DIR)
        free_mb = usage.free / (1024 * 1024)
        return free_mb >= MonitoringConfig.MIN_FREE_DISK_MB

    def _check_heartbeat_fresh(self, component: str) -> bool:
        heartbeat = self.memory.get_heartbeat(component)
        if not heartbeat:
            return False
        updated_at = heartbeat.get("updated_at")
        if not updated_at:
            return False
        age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
        return age <= MonitoringConfig.HEARTBEAT_STALE_SECONDS

    def _check_alpaca(self, client) -> bool:
        if client is None:
            return False
        try:
            client.get_account()
            return True
        except Exception as exc:
            logger.warning("Alpaca health check failed: %s", exc)
            return False

    def _check_systemd_services(self) -> dict:
        statuses = {}
        for service in MonitoringConfig.SYSTEMD_SERVICES:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", service],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=2,
                )
                statuses[service] = result.stdout.strip() or "unknown"
            except Exception:
                statuses[service] = "unavailable"
        return statuses
