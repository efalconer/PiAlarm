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
from src.services.message_service import get_message_service
from src.hardware.buttons import get_button_handler, Button
from src.hardware.display import get_display, set_display, DisplayData, ConsoleDisplay, WaveshareOLED
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
        self.message_service = get_message_service()
        self.button_handler = get_button_handler()
        self.display = self._init_display()

        self._running = False
        self._web_thread: threading.Thread | None = None
        self._last_weather_update = 0
        self._last_alarm_check = -1
        self._showing_forecast = False
        self._showing_message = False
        self._music_mode = False

    def _init_display(self):
        """Initialize the appropriate display based on config."""
        display_type = self.config.display_type

        if display_type == "console":
            logger.info("Using console display")
            display = ConsoleDisplay()
            set_display(display)
            return display

        if display_type == "oled" or display_type == "auto":
            # Try to initialize OLED
            try:
                display = WaveshareOLED(
                    interface=self.config.display_interface,
                    spi_device=self.config.display_spi_device,
                    gpio_dc=self.config.display_gpio_dc,
                    gpio_rst=self.config.display_gpio_rst,
                )
                set_display(display)
                logger.info("Using Waveshare OLED display")
                return display
            except Exception as e:
                if display_type == "oled":
                    logger.error(f"Failed to create OLED display: {e}")
                else:
                    logger.info(f"OLED not available, falling back to console: {e}")

        # Fall back to console
        logger.info("Using console display")
        display = ConsoleDisplay()
        set_display(display)
        return display

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
        else:
            self.display.set_brightness(self.config.display_brightness)

        # Initialize buttons
        if not self.button_handler.initialize():
            logger.warning("Button handler failed to initialize")

        # Set up button callbacks
        self.button_handler.set_callback(Button.SNOOZE, self._on_snooze)
        self.button_handler.set_callback(Button.DISMISS, self._on_dismiss)
        self.button_handler.set_callback(Button.FORECAST, self._on_forecast)
        self.button_handler.set_callback(Button.MESSAGES, self._on_messages)
        self.button_handler.set_callback(Button.MUSIC, self._on_music)

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
        if self._music_mode:
            logger.info("Dismiss pressed — stopping music player")
            self.audio_service.stop()
            self._music_mode = False
        else:
            logger.info("Dismiss button pressed")
            self.alarm_service.dismiss()

    def _on_forecast(self) -> None:
        """Handle forecast button press - toggle forecast, or previous track in music mode."""
        if self._music_mode:
            logger.info("Forecast button pressed — previous track")
            self.audio_service.previous_track()
        else:
            logger.info("Forecast button pressed")
            self._showing_forecast = not self._showing_forecast
            if self._showing_forecast:
                self._show_forecast()

    def _show_forecast(self) -> None:
        """Display the weather forecast."""
        forecast = self.weather_service.get_forecast()
        if forecast:
            high, low = self.weather_service.get_forecast_high_low()
            forecast_data = [
                {
                    "time": h.time.strftime("%I%p").lstrip("0"),
                    "temp": f"{int(h.temp_f)}°",
                    "condition": h.condition,
                    "hour": h.time.hour,
                    "high": f"{int(high)}°" if high is not None else None,
                    "low": f"{int(low)}°" if low is not None else None,
                }
                for h in forecast[:4]
            ]
            self.display.show_forecast(forecast_data)

    def _on_messages(self) -> None:
        """Handle messages button press - next track in music mode, otherwise cycle messages."""
        if self._music_mode:
            logger.info("Messages button pressed — next track")
            self.audio_service.next_track()
        else:
            logger.info("Messages button pressed")
            message = self.message_service.get_next_unread()
            if message:
                self.message_service.mark_as_read(message.id)
                self.display.show_message(message.text)
                self._showing_message = True
                self._showing_forecast = False  # Messages take priority over forecast
            else:
                # No more messages - return to main screen
                self._showing_message = False
                self.display.clear_message()

    def _on_music(self) -> None:
        """Handle music button press - start music player with all uploaded tracks."""
        logger.info("Music button pressed")
        tracks = self.audio_service.get_available_sounds()
        if not tracks:
            logger.warning("No music files found in music directory")
            return
        self._showing_forecast = False
        self._showing_message = False
        self._music_mode = True
        self.audio_service.play_playlist(tracks, start_index=0)
        logger.info(f"Music player started with {len(tracks)} track(s)")

    def _update_music_display(self) -> None:
        """Update display while in music player mode."""
        track_name = self.audio_service.current_file or "Unknown"
        track_num, total_tracks = self.audio_service.playlist_position
        elapsed_ms = self.audio_service.get_position_ms()
        duration_ms = self.audio_service.get_track_duration_ms()
        self.display.show_music_player(track_name, track_num, total_tracks, elapsed_ms, duration_ms)

    def _update_display(self) -> None:
        """Update display with current data."""
        # Alarm takes priority over everything
        if self.alarm_service.is_alarm_active:
            self._showing_forecast = False
            self._showing_message = False
            self._music_mode = False
        elif self._music_mode:
            # Exit music mode automatically when the playlist finishes
            if not self.audio_service.is_playlist_mode and not self.audio_service.has_active_playback():
                self._music_mode = False
            else:
                self._update_music_display()
                return
        elif self._showing_forecast or self._showing_message:
            return  # Don't overwrite forecast/message display

        time_data = self.time_service.get_display_data()
        weather_data = self.weather_service.get_display_data()

        active_alarm = self.alarm_service.active_alarm
        data = DisplayData(
            time=time_data["time"],
            date=time_data["date"],
            hour=time_data["hour"],
            weekday_name=time_data["weekday_name"],
            weather_temp=weather_data["temp"] if weather_data else None,
            weather_condition=weather_data["condition"] if weather_data else None,
            alarm_active=self.alarm_service.is_alarm_active,
            alarm_label=active_alarm.label if active_alarm else None,
            alarm_display_text=active_alarm.display_text if active_alarm else "Wake up Claire!",
            has_unread_messages=self.message_service.has_unread(),
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
