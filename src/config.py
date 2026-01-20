"""Configuration management for PiAlarm."""

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "weather_api_key": "",
    "weather_location": "",
    "timezone": "America/Los_Angeles",
    "snooze_duration_minutes": 9,
    "display_brightness": 100,
    "time_format_24h": False,
    "web_port": 5000,
    "display_type": "auto",  # "auto", "oled", "console"
    "display_interface": "i2c",  # "i2c" or "spi"
    "display_i2c_address": 60,  # 0x3C = 60
}

CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = CONFIG_DIR / "data"
MUSIC_DIR = CONFIG_DIR / "music"


class Config:
    """Application configuration handler."""

    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file, creating with defaults if missing."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = {**DEFAULT_CONFIG, **json.load(f)}
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()

    def save(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        self._config[key] = value
        self.save()

    def update(self, values: dict[str, Any]) -> None:
        """Update multiple configuration values and save."""
        self._config.update(values)
        self.save()

    @property
    def weather_api_key(self) -> str:
        return self._config.get("weather_api_key", "")

    @property
    def weather_location(self) -> str:
        return self._config.get("weather_location", "")

    @property
    def timezone(self) -> str:
        return self._config.get("timezone", "America/Los_Angeles")

    @property
    def snooze_duration_minutes(self) -> int:
        return self._config.get("snooze_duration_minutes", 9)

    @property
    def time_format_24h(self) -> bool:
        return self._config.get("time_format_24h", False)

    @property
    def web_port(self) -> int:
        return self._config.get("web_port", 5000)

    @property
    def display_type(self) -> str:
        return self._config.get("display_type", "auto")

    @property
    def display_interface(self) -> str:
        return self._config.get("display_interface", "i2c")

    @property
    def display_i2c_address(self) -> int:
        return self._config.get("display_i2c_address", 60)

    @property
    def display_brightness(self) -> int:
        return self._config.get("display_brightness", 100)


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
