"""Time service for PiAlarm - handles NTP sync and time display."""

import subprocess
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import get_config

logger = logging.getLogger(__name__)


class TimeService:
    """Manages time synchronization and formatting."""

    def __init__(self):
        self.config = get_config()
        self._timezone: ZoneInfo | None = None

    @property
    def timezone(self) -> ZoneInfo:
        """Get the configured timezone."""
        if self._timezone is None:
            self._timezone = ZoneInfo(self.config.timezone)
        return self._timezone

    def sync_time(self) -> bool:
        """Sync system time via NTP. Returns True if successful."""
        try:
            # Check if NTP is already enabled (avoids password prompt)
            result = subprocess.run(
                ["timedatectl", "show", "--property=NTP", "--value"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip().lower() == "yes":
                logger.info("NTP time sync already enabled")
                return True

            # NTP not enabled, try to enable it
            result = subprocess.run(
                ["timedatectl", "set-ntp", "true"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info("NTP time sync enabled")
                return True
            else:
                logger.warning(f"NTP sync failed: {result.stderr}")
                return False
        except FileNotFoundError:
            # timedatectl not available (not on systemd system)
            logger.warning("timedatectl not available, skipping NTP sync")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("NTP sync timed out")
            return False
        except Exception as e:
            logger.error(f"NTP sync error: {e}")
            return False

    def now(self) -> datetime:
        """Get current time in configured timezone."""
        return datetime.now(self.timezone)

    def format_time(self, dt: datetime | None = None) -> str:
        """Format time for display."""
        if dt is None:
            dt = self.now()
        if self.config.time_format_24h:
            return dt.strftime("%H:%M")
        else:
            return dt.strftime("%I:%M %p").lstrip("0")

    def format_time_with_seconds(self, dt: datetime | None = None) -> str:
        """Format time with seconds for display."""
        if dt is None:
            dt = self.now()
        if self.config.time_format_24h:
            return dt.strftime("%H:%M:%S")
        else:
            return dt.strftime("%I:%M:%S %p").lstrip("0")

    def format_date(self, dt: datetime | None = None) -> str:
        """Format date for display."""
        if dt is None:
            dt = self.now()
        return dt.strftime("%A, %B %d")

    def get_display_data(self) -> dict:
        """Get all time data for display."""
        now = self.now()
        return {
            "time": self.format_time(now),
            "time_with_seconds": self.format_time_with_seconds(now),
            "date": self.format_date(now),
            "hour": now.hour,
            "minute": now.minute,
            "weekday": now.weekday(),
        }


# Global instance
_time_service: TimeService | None = None


def get_time_service() -> TimeService:
    """Get the global time service instance."""
    global _time_service
    if _time_service is None:
        _time_service = TimeService()
    return _time_service
