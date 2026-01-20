"""PiAlarm - Main application entry point."""

import logging
import signal
import sys
import threading
import time

from src.config import get_config
from src.services.time_service import get_time_service
from src.services.weather_service import get_weather_service
from src.services.alarm_service import get_alarm_service
from src.services.audio_service import get_audio_service
from src.hardware.buttons import get_button_handler, Button
from src.hardware.display import get_display, DisplayData
from src.web.app import run_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PiAlarm:
    """Main application controller."""

    def __init__(self):
        self.config = get_config()
        self.time_service = get_time_service()
        self.weather_service = get_weather_service()
        self.alarm_service = get_alarm_service()
        self.audio_service = get_audio_service()
        self.button_handler = get_button_handler()
        self.display = get_display()

        self._running = False
        self._web_thread: threading.Thread | None = None
        self._last_weather_update = 0
        self._last_alarm_check = -1

    def initialize(self) -> bool:
        """Initialize all services."""
        logger.info("Initializing PiAlarm...")

        # Sync time
        self.time_service.sync_time()

        # Initialize audio
        if not self.audio_service.initialize():
            logger.warning("Audio service failed to initialize")

        # Initialize display
        if not self.display.initialize():
            logger.warning("Display failed to initialize")

        # Initialize buttons
        if not self.button_handler.initialize():
            logger.warning("Button handler failed to initialize")

        # Set up button callbacks
        self.button_handler.set_callback(Button.SNOOZE, self._on_snooze)
        self.button_handler.set_callback(Button.DISMISS, self._on_dismiss)
        self.button_handler.set_callback(Button.FORECAST, self._on_forecast)

        # Fetch initial weather
        self.weather_service.fetch_current()

        logger.info("PiAlarm initialized")
        return True

    def shutdown(self) -> None:
        """Shutdown all services."""
        logger.info("Shutting down PiAlarm...")
        self._running = False

        self.audio_service.shutdown()
        self.button_handler.shutdown()
        self.display.shutdown()

        logger.info("PiAlarm shutdown complete")

    def _on_snooze(self) -> None:
        """Handle snooze button press."""
        logger.info("Snooze button pressed")
        self.alarm_service.snooze()

    def _on_dismiss(self) -> None:
        """Handle dismiss button press."""
        logger.info("Dismiss button pressed")
        self.alarm_service.dismiss()

    def _on_forecast(self) -> None:
        """Handle forecast button press."""
        logger.info("Forecast button pressed")
        forecast = self.weather_service.get_forecast()
        if forecast:
            forecast_data = [
                {
                    "time": h.time.strftime("%I %p"),
                    "temp": f"{int(h.temp_f)}°",
                    "condition": h.condition,
                }
                for h in forecast[:6]
            ]
            self.display.show_forecast(forecast_data)

    def _update_display(self) -> None:
        """Update display with current data."""
        time_data = self.time_service.get_display_data()
        weather_data = self.weather_service.get_display_data()

        data = DisplayData(
            time=time_data["time"],
            date=time_data["date"],
            weather_temp=weather_data["temp"] if weather_data else None,
            weather_condition=weather_data["condition"] if weather_data else None,
            alarm_active=self.alarm_service.is_alarm_active,
            alarm_label=self.alarm_service.active_alarm.label if self.alarm_service.active_alarm else None,
        )
        self.display.update(data)

    def _check_weather_refresh(self) -> None:
        """Check if weather should be refreshed (hourly)."""
        current_hour = self.time_service.now().hour
        if current_hour != self._last_weather_update:
            self._last_weather_update = current_hour
            self.weather_service.fetch_current(force=True)

    def _check_alarms(self) -> None:
        """Check for triggered alarms (once per minute)."""
        current_minute = self.time_service.now().minute
        if current_minute != self._last_alarm_check:
            self._last_alarm_check = current_minute
            self.alarm_service.check_alarms()

    def _start_web_server(self) -> None:
        """Start web server in background thread."""
        self._web_thread = threading.Thread(target=run_web_server, daemon=True)
        self._web_thread.start()
        logger.info(f"Web server started on port {self.config.web_port}")

    def run(self) -> None:
        """Main application loop."""
        if not self.initialize():
            logger.error("Failed to initialize, exiting")
            return

        self._running = True
        self._start_web_server()

        logger.info("PiAlarm running. Press Ctrl+C to exit.")

        try:
            while self._running:
                self._check_weather_refresh()
                self._check_alarms()
                self._update_display()
                self.audio_service.check_playlist_advance()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.shutdown()


def main():
    """Entry point."""
    app = PiAlarm()

    # Handle signals for clean shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.run()


if __name__ == "__main__":
    main()
