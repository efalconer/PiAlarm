"""Weather service for PiAlarm - fetches weather from WeatherAPI.com."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from src.config import get_config

logger = logging.getLogger(__name__)

WEATHER_API_BASE = "https://api.weatherapi.com/v1"


@dataclass
class CurrentWeather:
    """Current weather data."""

    temp_f: float
    temp_c: float
    condition: str
    icon_url: str
    humidity: int
    wind_mph: float
    feels_like_f: float
    last_updated: datetime


@dataclass
class ForecastHour:
    """Hourly forecast data."""

    time: datetime
    temp_f: float
    temp_c: float
    condition: str
    icon_url: str
    chance_of_rain: int


class WeatherService:
    """Fetches and caches weather data from WeatherAPI.com."""

    def __init__(self):
        self.config = get_config()
        self._current_weather: CurrentWeather | None = None
        self._forecast: list[ForecastHour] = []
        self._last_fetch: datetime | None = None
        self._cache_duration = timedelta(hours=1)

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._last_fetch is None:
            return False
        return datetime.now() - self._last_fetch < self._cache_duration

    def _get_api_key(self) -> str | None:
        """Get API key from config."""
        key = self.config.weather_api_key
        if not key:
            logger.warning("Weather API key not configured")
        return key or None

    def _get_location(self) -> str | None:
        """Get location from config."""
        location = self.config.weather_location
        if not location:
            logger.warning("Weather location not configured")
        return location or None

    def fetch_current(self, force: bool = False) -> CurrentWeather | None:
        """Fetch current weather. Uses cache unless force=True."""
        if not force and self._is_cache_valid() and self._current_weather:
            return self._current_weather

        api_key = self._get_api_key()
        location = self._get_location()
        if not api_key or not location:
            return None

        try:
            response = requests.get(
                f"{WEATHER_API_BASE}/current.json",
                params={"key": api_key, "q": location},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            current = data["current"]
            self._current_weather = CurrentWeather(
                temp_f=current["temp_f"],
                temp_c=current["temp_c"],
                condition=current["condition"]["text"],
                icon_url="https:" + current["condition"]["icon"],
                humidity=current["humidity"],
                wind_mph=current["wind_mph"],
                feels_like_f=current["feelslike_f"],
                last_updated=datetime.now(),
            )
            self._last_fetch = datetime.now()
            logger.info(f"Weather updated: {self._current_weather.temp_f}°F, {self._current_weather.condition}")
            return self._current_weather

        except requests.RequestException as e:
            logger.error(f"Failed to fetch weather: {e}")
            return self._current_weather  # Return cached data if available

    def fetch_forecast(self) -> list[ForecastHour]:
        """Fetch hourly forecast for rest of today."""
        api_key = self._get_api_key()
        location = self._get_location()
        if not api_key or not location:
            return []

        try:
            response = requests.get(
                f"{WEATHER_API_BASE}/forecast.json",
                params={"key": api_key, "q": location, "days": 1},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            forecast = []
            now = datetime.now()
            for hour_data in data["forecast"]["forecastday"][0]["hour"]:
                hour_time = datetime.strptime(hour_data["time"], "%Y-%m-%d %H:%M")
                if hour_time > now:
                    forecast.append(
                        ForecastHour(
                            time=hour_time,
                            temp_f=hour_data["temp_f"],
                            temp_c=hour_data["temp_c"],
                            condition=hour_data["condition"]["text"],
                            icon_url="https:" + hour_data["condition"]["icon"],
                            chance_of_rain=hour_data["chance_of_rain"],
                        )
                    )

            self._forecast = forecast
            logger.info(f"Forecast updated: {len(forecast)} hours")
            return forecast

        except requests.RequestException as e:
            logger.error(f"Failed to fetch forecast: {e}")
            return self._forecast  # Return cached data if available

    def get_current(self) -> CurrentWeather | None:
        """Get current weather (from cache or fetch if needed)."""
        if self._is_cache_valid() and self._current_weather:
            return self._current_weather
        return self.fetch_current()

    def get_forecast(self) -> list[ForecastHour]:
        """Get forecast (always fetches fresh data)."""
        return self.fetch_forecast()

    def get_display_data(self) -> dict | None:
        """Get weather data formatted for display."""
        current = self.get_current()
        if not current:
            return None
        return {
            "temp": f"{int(current.temp_f)}°",
            "condition": current.condition,
            "icon_url": current.icon_url,
            "humidity": f"{current.humidity}%",
            "feels_like": f"{int(current.feels_like_f)}°",
        }


# Global instance
_weather_service: WeatherService | None = None


def get_weather_service() -> WeatherService:
    """Get the global weather service instance."""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service
