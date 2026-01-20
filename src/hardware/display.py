"""Display abstraction for PiAlarm - interface for TBD display hardware."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DisplayData:
    """Data to be shown on display."""

    time: str
    date: str
    weather_temp: str | None = None
    weather_condition: str | None = None
    alarm_active: bool = False
    alarm_label: str | None = None
    forecast: list[dict] | None = None


class Display(ABC):
    """Abstract display interface."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the display hardware."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the display."""
        pass

    @abstractmethod
    def show_time(self, time: str, date: str) -> None:
        """Display the current time and date."""
        pass

    @abstractmethod
    def show_weather(self, temp: str, condition: str) -> None:
        """Display current weather."""
        pass

    @abstractmethod
    def show_forecast(self, forecast: list[dict]) -> None:
        """Display weather forecast."""
        pass

    @abstractmethod
    def show_alarm_active(self, label: str | None = None) -> None:
        """Display alarm active indicator."""
        pass

    @abstractmethod
    def clear_alarm_active(self) -> None:
        """Clear alarm active indicator."""
        pass

    @abstractmethod
    def set_brightness(self, level: int) -> None:
        """Set display brightness (0-100)."""
        pass

    @abstractmethod
    def update(self, data: DisplayData) -> None:
        """Update display with all current data."""
        pass


class ConsoleDisplay(Display):
    """Console-based display for development/testing."""

    def __init__(self):
        self._brightness = 100
        self._last_data: DisplayData | None = None

    def initialize(self) -> bool:
        logger.info("Console display initialized")
        return True

    def shutdown(self) -> None:
        logger.info("Console display shutdown")

    def show_time(self, time: str, date: str) -> None:
        print(f"\r[{time}] {date}", end="", flush=True)

    def show_weather(self, temp: str, condition: str) -> None:
        print(f" | {temp} {condition}", end="", flush=True)

    def show_forecast(self, forecast: list[dict]) -> None:
        print("\n--- Forecast ---")
        for hour in forecast[:6]:
            print(f"  {hour.get('time', '')}: {hour.get('temp', '')} - {hour.get('condition', '')}")
        print("----------------")

    def show_alarm_active(self, label: str | None = None) -> None:
        alarm_text = f" [ALARM: {label}]" if label else " [ALARM!]"
        print(alarm_text, end="", flush=True)

    def clear_alarm_active(self) -> None:
        pass  # Will be cleared on next update

    def set_brightness(self, level: int) -> None:
        self._brightness = max(0, min(100, level))

    def update(self, data: DisplayData) -> None:
        self._last_data = data
        self.show_time(data.time, data.date)
        if data.weather_temp:
            self.show_weather(data.weather_temp, data.weather_condition or "")
        if data.alarm_active:
            self.show_alarm_active(data.alarm_label)


# Global instance
_display: Display | None = None


def get_display() -> Display:
    """Get the global display instance."""
    global _display
    if _display is None:
        # Default to console display until hardware is specified
        _display = ConsoleDisplay()
    return _display


def set_display(display: Display) -> None:
    """Set the global display instance."""
    global _display
    _display = display
