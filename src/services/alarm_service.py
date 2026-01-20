"""Alarm service for PiAlarm - manages alarm scheduling and persistence."""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from src.config import DATA_DIR, get_config
from src.services.time_service import get_time_service
from src.services.audio_service import get_audio_service

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "alarms.db"


@dataclass
class Alarm:
    """Represents an alarm."""

    id: int | None
    hour: int
    minute: int
    days: list[int]  # 0=Monday, 6=Sunday
    enabled: bool
    sound_file: str
    label: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "hour": self.hour,
            "minute": self.minute,
            "days": self.days,
            "enabled": self.enabled,
            "sound_file": self.sound_file,
            "label": self.label,
            "time_display": f"{self.hour:02d}:{self.minute:02d}",
        }


class AlarmService:
    """Manages alarms with SQLite persistence."""

    def __init__(self):
        self.config = get_config()
        self.time_service = get_time_service()
        self.audio_service = get_audio_service()
        self._snoozed_until: datetime | None = None
        self._active_alarm: Alarm | None = None
        self._on_alarm_trigger: Callable[[Alarm], None] | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hour INTEGER NOT NULL,
                    minute INTEGER NOT NULL,
                    days TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    sound_file TEXT NOT NULL,
                    label TEXT DEFAULT ''
                )
            """)
            conn.commit()

    def _row_to_alarm(self, row: tuple) -> Alarm:
        """Convert database row to Alarm object."""
        return Alarm(
            id=row[0],
            hour=row[1],
            minute=row[2],
            days=[int(d) for d in row[3].split(",") if d],
            enabled=bool(row[4]),
            sound_file=row[5],
            label=row[6] or "",
        )

    def get_all(self) -> list[Alarm]:
        """Get all alarms."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, hour, minute, days, enabled, sound_file, label FROM alarms ORDER BY hour, minute"
            )
            return [self._row_to_alarm(row) for row in cursor.fetchall()]

    def get_by_id(self, alarm_id: int) -> Alarm | None:
        """Get alarm by ID."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, hour, minute, days, enabled, sound_file, label FROM alarms WHERE id = ?",
                (alarm_id,),
            )
            row = cursor.fetchone()
            return self._row_to_alarm(row) if row else None

    def create(self, alarm: Alarm) -> Alarm:
        """Create a new alarm."""
        days_str = ",".join(str(d) for d in alarm.days)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO alarms (hour, minute, days, enabled, sound_file, label) VALUES (?, ?, ?, ?, ?, ?)",
                (alarm.hour, alarm.minute, days_str, int(alarm.enabled), alarm.sound_file, alarm.label),
            )
            conn.commit()
            alarm.id = cursor.lastrowid
        logger.info(f"Created alarm: {alarm.id}")
        return alarm

    def update(self, alarm: Alarm) -> bool:
        """Update an existing alarm."""
        if alarm.id is None:
            return False
        days_str = ",".join(str(d) for d in alarm.days)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE alarms SET hour=?, minute=?, days=?, enabled=?, sound_file=?, label=? WHERE id=?",
                (alarm.hour, alarm.minute, days_str, int(alarm.enabled), alarm.sound_file, alarm.label, alarm.id),
            )
            conn.commit()
        logger.info(f"Updated alarm: {alarm.id}")
        return True

    def delete(self, alarm_id: int) -> bool:
        """Delete an alarm."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted alarm: {alarm_id}")
        return deleted

    def toggle(self, alarm_id: int) -> bool:
        """Toggle alarm enabled state. Returns new state."""
        alarm = self.get_by_id(alarm_id)
        if alarm:
            alarm.enabled = not alarm.enabled
            self.update(alarm)
            return alarm.enabled
        return False

    def set_trigger_callback(self, callback: Callable[[Alarm], None]) -> None:
        """Set callback for when an alarm triggers."""
        self._on_alarm_trigger = callback

    def check_alarms(self) -> Alarm | None:
        """Check if any alarm should trigger now. Called once per minute."""
        now = self.time_service.now()

        # Check if we're in snooze period
        if self._snoozed_until and now < self._snoozed_until:
            return None

        # Clear snooze if time has passed
        if self._snoozed_until and now >= self._snoozed_until:
            self._snoozed_until = None
            # Resume the snoozed alarm
            if self._active_alarm:
                self._trigger_alarm(self._active_alarm)
                return self._active_alarm

        # Check all enabled alarms
        for alarm in self.get_all():
            if not alarm.enabled:
                continue
            if alarm.hour == now.hour and alarm.minute == now.minute:
                if now.weekday() in alarm.days or not alarm.days:
                    self._trigger_alarm(alarm)
                    return alarm

        return None

    def _trigger_alarm(self, alarm: Alarm) -> None:
        """Trigger an alarm."""
        self._active_alarm = alarm
        logger.info(f"Alarm triggered: {alarm.label or alarm.id}")
        self.audio_service.play(alarm.sound_file, loop=True)
        if self._on_alarm_trigger:
            self._on_alarm_trigger(alarm)

    def snooze(self) -> None:
        """Snooze the current alarm."""
        if self._active_alarm:
            self.audio_service.stop()
            snooze_minutes = self.config.snooze_duration_minutes
            self._snoozed_until = self.time_service.now() + timedelta(minutes=snooze_minutes)
            logger.info(f"Alarm snoozed for {snooze_minutes} minutes")

    def dismiss(self) -> None:
        """Dismiss the current alarm."""
        self.audio_service.stop()
        self._active_alarm = None
        self._snoozed_until = None
        logger.info("Alarm dismissed")

    @property
    def is_alarm_active(self) -> bool:
        """Check if an alarm is currently active (ringing or snoozed)."""
        return self._active_alarm is not None

    @property
    def is_snoozed(self) -> bool:
        """Check if alarm is currently snoozed."""
        return self._snoozed_until is not None

    @property
    def active_alarm(self) -> Alarm | None:
        """Get the currently active alarm."""
        return self._active_alarm


# Global instance
_alarm_service: AlarmService | None = None


def get_alarm_service() -> AlarmService:
    """Get the global alarm service instance."""
    global _alarm_service
    if _alarm_service is None:
        _alarm_service = AlarmService()
    return _alarm_service
