"""Display abstraction for PiAlarm - interface for display hardware."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.sprite_service import SpriteService

logger = logging.getLogger(__name__)

# Font directory
FONT_DIR = Path(__file__).parent.parent.parent / "fonts"


@dataclass
class DisplayData:
    """Data to be shown on display."""

    time: str
    date: str
    hour: int = 0
    weekday_name: str = ""
    weather_temp: str | None = None
    weather_condition: str | None = None
    alarm_active: bool = False
    alarm_label: str | None = None
    alarm_display_text: str = "Wake up Claire!"
    forecast: list[dict] | None = None
    has_unread_messages: bool = False


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

    @abstractmethod
    def show_message(self, text: str, is_last: bool = False) -> None:
        """Display a message on screen."""
        pass

    @abstractmethod
    def clear_message(self) -> None:
        """Clear message display and return to normal mode."""
        pass

    @abstractmethod
    def show_music_player(
        self,
        track_name: str,
        track_num: int,
        total_tracks: int,
        elapsed_ms: int,
        duration_ms: int | None = None,
    ) -> None:
        """Display music player screen with track info and progress."""
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
        print(f" [{label or 'Wake up Claire!'}]", end="", flush=True)

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
        if data.has_unread_messages:
            print(" [*]", end="", flush=True)

    def show_message(self, text: str, is_last: bool = False) -> None:
        if is_last:
            print(f"\n--- End of messages ---")
        else:
            print(f"\n--- Message: {text} ---")

    def clear_message(self) -> None:
        pass  # Console doesn't need explicit clearing

    def show_music_player(
        self,
        track_name: str,
        track_num: int,
        total_tracks: int,
        elapsed_ms: int,
        duration_ms: int | None = None,
    ) -> None:
        elapsed_s = elapsed_ms // 1000
        elapsed_str = f"{elapsed_s // 60}:{elapsed_s % 60:02d}"
        suffix = f" / {duration_ms // 1000 // 60}:{(duration_ms // 1000) % 60:02d}" if duration_ms else ""
        print(f"\r[Music] {track_name} ({track_num}/{total_tracks}) {elapsed_str}{suffix}", end="", flush=True)


class WaveshareOLED(Display):
    """Waveshare 2.42" OLED display (SSD1309, 128x64, I2C/SPI)."""

    # Display dimensions
    WIDTH = 128
    HEIGHT = 64

    # Weather condition to icon mapping
    WEATHER_ICONS = {
        "sunny": "sun",
        "clear": "sun",
        "partly cloudy": "partial",
        "cloudy": "cloud",
        "overcast": "cloud",
        "mist": "cloud",
        "fog": "cloud",
        "rain": "rain",
        "drizzle": "rain",
        "light rain": "rain",
        "heavy rain": "rain",
        "showers": "rain",
        "thunderstorm": "storm",
        "thunder": "storm",
        "snow": "snow",
        "sleet": "snow",
        "blizzard": "snow",
    }

    def __init__(self, interface: str = "spi", spi_device: int = 0, spi_port: int = 0,
                 gpio_dc: int = 24, gpio_rst: int = 25):
        """
        Initialize Waveshare OLED display.

        Args:
            interface: "spi" (default) or "i2c"
            spi_device: SPI device number (default 0)
            spi_port: SPI port number (default 0)
            gpio_dc: GPIO pin for DC
            gpio_rst: GPIO pin for reset
        """
        self._interface = interface
        self._spi_device = spi_device
        self._spi_port = spi_port
        self._gpio_dc = gpio_dc
        self._gpio_rst = gpio_rst

        self._device = None
        self._brightness = 100
        self._last_data: DisplayData | None = None
        self._font_time = None
        self._font_medium = None
        self._font_small = None
        self._font_tiny = None
        self._font_alarm = None
        self._font_alarm_small = None
        self._alarm_blink_state = False
        self._showing_message = False
        self._message_text: str | None = None
        self._message_is_last = False

    def initialize(self) -> bool:
        """Initialize the OLED display."""
        try:
            from luma.core.interface.serial import i2c, spi
            from luma.oled.device import ssd1309
            from PIL import ImageFont

            # Set up serial interface (SPI is default for Waveshare 2.42")
            if self._interface == "spi":
                serial = spi(device=self._spi_device, port=self._spi_port,
                            gpio_DC=self._gpio_dc, gpio_RST=self._gpio_rst)
            else:
                serial = i2c(port=1, address=0x3C)

            # Create device
            self._device = ssd1309(serial, width=self.WIDTH, height=self.HEIGHT)

            # Load fonts - try multiple locations
            font_loaded = False
            font_search_paths = [
                # Local fonts directory
                (FONT_DIR / "DejaVuSans.ttf", FONT_DIR / "DejaVuSans-Bold.ttf"),
                # System fonts (Raspberry Pi / Debian)
                (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                 Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
                # macOS system fonts
                (Path("/System/Library/Fonts/Helvetica.ttc"),
                 Path("/System/Library/Fonts/Helvetica.ttc")),
            ]

            for font_path, bold_path in font_search_paths:
                if font_path.exists():
                    try:
                        bold_font = bold_path if bold_path.exists() else font_path
                        self._font_time = ImageFont.truetype(str(bold_font), 24)
                        self._font_medium = ImageFont.truetype(str(font_path), 14)
                        self._font_small = ImageFont.truetype(str(font_path), 11)
                        self._font_tiny = ImageFont.truetype(str(font_path), 9)
                        self._font_alarm = ImageFont.truetype(str(bold_font), 18)
                        self._font_alarm_small = ImageFont.truetype(str(font_path), 14)
                        font_loaded = True
                        logger.info(f"Loaded fonts from {font_path.parent}")
                        break
                    except Exception as e:
                        logger.debug(f"Failed to load font from {font_path}: {e}")
                        continue

            if not font_loaded:
                # Fall back to default font
                self._font_time = ImageFont.load_default()
                self._font_medium = ImageFont.load_default()
                self._font_small = ImageFont.load_default()
                self._font_tiny = ImageFont.load_default()
                self._font_alarm = ImageFont.load_default()
                self._font_alarm_small = ImageFont.load_default()
                logger.warning("Using default font - install fonts for better display")

            logger.info(f"Waveshare OLED initialized ({self._interface})")
            return True

        except ImportError as e:
            logger.error(f"Failed to import luma.oled: {e}")
            logger.error("Install with: pip install luma.oled")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize OLED: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown the display."""
        if self._device:
            self._device.clear()
            self._device.hide()
            logger.info("Waveshare OLED shutdown")

    def set_brightness(self, level: int) -> None:
        """Set display brightness (0-100)."""
        self._brightness = max(0, min(100, level))
        if self._device:
            # Convert 0-100 to 0-255
            contrast = int(self._brightness * 255 / 100)
            self._device.contrast(contrast)

    def _is_nighttime(self, hour: int) -> bool:
        """Determine if it's nighttime (for moon icons)."""
        return hour >= 20 or hour < 6

    def _get_weather_icon_type(self, condition: str | None, hour: int = 12) -> str:
        """Get icon type from weather condition string, with night variants."""
        is_night = self._is_nighttime(hour)

        if not condition:
            return "moon" if is_night else "sun"

        condition_lower = condition.lower()
        for key, icon in self.WEATHER_ICONS.items():
            if key in condition_lower:
                # Convert day icons to night variants
                if is_night:
                    if icon == "sun":
                        return "moon"
                    elif icon == "partial":
                        return "partial_moon"
                return icon

        return "moon" if is_night else "sun"  # Default

    def _draw_weather_icon(self, draw, x: int, y: int, icon_type: str, size: int = 20):
        """Draw a weather icon at the specified position."""
        cx, cy = x + size // 2, y + size // 2

        if icon_type == "sun":
            # Sun: circle with rays
            r = size // 3
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white")
            # Rays
            for i in range(8):
                import math
                angle = i * math.pi / 4
                x1 = cx + int((r + 2) * math.cos(angle))
                y1 = cy + int((r + 2) * math.sin(angle))
                x2 = cx + int((r + 5) * math.cos(angle))
                y2 = cy + int((r + 5) * math.sin(angle))
                draw.line([x1, y1, x2, y2], fill="white", width=1)

        elif icon_type == "moon":
            # Moon: crescent shape
            r = size // 3
            # Draw full circle
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white")
            # Cut out a smaller circle offset to the right to create crescent
            cut_offset = r // 2
            cut_r = r - 1
            draw.ellipse([cx - cut_r + cut_offset, cy - cut_r, cx + cut_r + cut_offset, cy + cut_r], fill="black")

        elif icon_type == "partial_moon":
            # Partial cloud with moon: small moon with cloud
            r = 4
            # Draw crescent moon
            draw.ellipse([x + 12 - r, y + 4 - r + 4, x + 12 + r, y + 4 + r + 4], fill="white")
            # Cut out for crescent effect
            draw.ellipse([x + 12 - r + 3, y + 4 - r + 3, x + 12 + r + 3, y + 4 + r + 3], fill="black")
            # Cloud in front
            draw.ellipse([x, y + 10, x + 8, y + 18], fill="white")
            draw.ellipse([x + 5, y + 6, x + 15, y + 16], fill="white")
            draw.ellipse([x + 10, y + 10, x + 20, y + 18], fill="white")

        elif icon_type == "cloud":
            # Cloud: overlapping circles
            draw.ellipse([x + 2, y + 8, x + 12, y + 18], fill="white")
            draw.ellipse([x + 8, y + 4, x + 20, y + 16], fill="white")
            draw.ellipse([x + 14, y + 8, x + 24, y + 18], fill="white")

        elif icon_type == "partial":
            # Partial cloud: small sun with cloud
            r = 4
            draw.ellipse([x + 12 - r, y + 4 - r + 4, x + 12 + r, y + 4 + r + 4], fill="white")
            draw.ellipse([x, y + 10, x + 8, y + 18], fill="white")
            draw.ellipse([x + 5, y + 6, x + 15, y + 16], fill="white")
            draw.ellipse([x + 10, y + 10, x + 20, y + 18], fill="white")

        elif icon_type == "rain":
            # Rain: cloud with drops
            draw.ellipse([x + 2, y + 4, x + 10, y + 12], fill="white")
            draw.ellipse([x + 6, y + 2, x + 16, y + 10], fill="white")
            draw.ellipse([x + 12, y + 4, x + 20, y + 12], fill="white")
            # Rain drops
            draw.line([x + 5, y + 14, x + 3, y + 19], fill="white", width=1)
            draw.line([x + 11, y + 14, x + 9, y + 19], fill="white", width=1)
            draw.line([x + 17, y + 14, x + 15, y + 19], fill="white", width=1)

        elif icon_type == "storm":
            # Storm: cloud with lightning
            draw.ellipse([x + 2, y + 2, x + 10, y + 10], fill="white")
            draw.ellipse([x + 6, y, x + 16, y + 8], fill="white")
            draw.ellipse([x + 12, y + 2, x + 20, y + 10], fill="white")
            # Lightning bolt
            draw.polygon([
                (x + 12, y + 10), (x + 8, y + 14), (x + 11, y + 14),
                (x + 9, y + 20), (x + 15, y + 13), (x + 12, y + 13)
            ], fill="white")

        elif icon_type == "snow":
            # Snow: cloud with snowflakes
            draw.ellipse([x + 2, y + 4, x + 10, y + 12], fill="white")
            draw.ellipse([x + 6, y + 2, x + 16, y + 10], fill="white")
            draw.ellipse([x + 12, y + 4, x + 20, y + 12], fill="white")
            # Snowflakes (dots)
            draw.ellipse([x + 4, y + 15, x + 6, y + 17], fill="white")
            draw.ellipse([x + 10, y + 17, x + 12, y + 19], fill="white")
            draw.ellipse([x + 16, y + 15, x + 18, y + 17], fill="white")

    def _draw_envelope_icon(self, draw, x: int, y: int):
        """Draw a small envelope icon (8x6 pixels) at the specified position."""
        # Envelope outline (rectangle)
        draw.rectangle([x, y, x + 7, y + 5], outline="white", fill=None)
        # Envelope flap (V shape inside)
        draw.line([x, y, x + 3, y + 2], fill="white")
        draw.line([x + 7, y, x + 4, y + 2], fill="white")

    def _get_sprite_service(self) -> "SpriteService | None":
        """Get sprite service lazily to avoid circular imports."""
        try:
            from src.services.sprite_service import get_sprite_service
            return get_sprite_service()
        except Exception as e:
            logger.debug(f"Could not load sprite service: {e}")
            return None

    def _get_dog_activity(self, hour: int) -> str:
        """Get dog activity based on hour of day.

        Uses sprite service for all sprites (default and custom).
        Falls back to hardcoded activity names only if sprite service fails.
        """
        sprite_service = self._get_sprite_service()
        if sprite_service:
            active_sprite = sprite_service.get_active_sprite(hour)
            if active_sprite:
                return active_sprite.id

        # Fall back to hardcoded activity names if sprite service unavailable
        if hour >= 20 or hour < 6:
            return "sleeping"
        elif 6 <= hour < 8:
            return "coffee"
        elif 8 <= hour < 10:
            return "walking"
        elif 10 <= hour < 14:
            return "school"
        elif 14 <= hour < 17:
            return "homework"
        elif 17 <= hour < 18:
            return "dinner"
        else:  # 18 <= hour < 20
            return "gaming"

    def _get_hardcoded_sprite(self, activity: str) -> list[tuple[int, int]]:
        """Get hardcoded sprite pixel coordinates for a given activity."""
        if activity == "sleeping":
            # Sleeping dog - curled up with Zzz
            pixels = [
                # Curled body outline
                *[(i, 14) for i in range(8, 20)],
                *[(i, 15) for i in range(7, 21)],
                (6, 16), (21, 16),
                (5, 17), (22, 17),
                (5, 18), (22, 18),
                (5, 19), (22, 19),
                *[(i, 20) for i in range(5, 23)],
                *[(i, 21) for i in range(6, 22)],
                # Head tucked in
                *[(i, 16) for i in range(8, 14)],
                *[(i, 17) for i in range(8, 13)],
                *[(i, 18) for i in range(9, 12)],
                # Ear
                (7, 13), (8, 13), (7, 14), (8, 14),
                # Tail curl
                (20, 17), (21, 16), (22, 15), (23, 14),
                # Closed eye (line)
                (9, 16), (10, 16), (11, 16),
                # Zzz
                *[(i, 5) for i in range(22, 27)],
                (26, 6), (25, 7), (24, 8),
                *[(i, 9) for i in range(22, 27)],
            ]

        elif activity == "coffee":
            # Dog sitting with coffee mug
            pixels = [
                # Left ear
                (5, 2), (6, 2), (7, 2), (5, 3), (6, 3), (7, 3), (6, 4), (7, 4),
                # Right ear
                (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (16, 3), (14, 4), (15, 4),
                # Head
                *[(i, 5) for i in range(6, 16)],
                *[(i, 6) for i in range(5, 17)],
                *[(i, 7) for i in range(5, 17)],
                (5, 8), (6, 8), (15, 8), (16, 8),
                *[(i, 9) for i in range(6, 16)],
                *[(i, 10) for i in range(7, 15)],
                # Eyes
                (8, 7), (9, 7), (12, 7), (13, 7),
                # Nose
                (10, 8), (11, 8), (10, 9), (11, 9),
                # Body
                *[(i, 11) for i in range(7, 15)],
                *[(i, 12) for i in range(6, 16)],
                *[(i, 13) for i in range(6, 16)],
                *[(i, 14) for i in range(6, 16)],
                # Legs
                (6, 15), (7, 15), (8, 15), (13, 15), (14, 15), (15, 15),
                (6, 16), (7, 16), (8, 16), (13, 16), (14, 16), (15, 16),
                (6, 17), (7, 17), (14, 17), (15, 17),
                # Coffee mug
                *[(i, 11) for i in range(18, 24)],
                (18, 12), (23, 12), (25, 12), (26, 12),
                (18, 13), (23, 13), (26, 13),
                (18, 14), (23, 14), (26, 14),
                (18, 15), (23, 15), (25, 15), (26, 15),
                *[(i, 16) for i in range(18, 24)],
                # Steam
                (20, 7), (21, 8), (20, 9), (22, 8), (21, 9),
            ]

        elif activity == "walking":
            # Dog walking with backpack
            pixels = [
                # Left ear
                (3, 3), (4, 3), (5, 3), (4, 4), (5, 4), (5, 5),
                # Right ear
                (13, 3), (14, 3), (15, 3), (13, 4), (14, 4), (13, 5),
                # Head
                *[(i, 6) for i in range(5, 14)],
                *[(i, 7) for i in range(4, 15)],
                *[(i, 8) for i in range(4, 15)],
                (4, 9), (5, 9), (13, 9), (14, 9),
                *[(i, 10) for i in range(5, 14)],
                # Eyes
                (6, 8), (7, 8), (11, 8), (12, 8),
                # Nose
                (9, 9), (10, 9),
                # Body
                *[(i, 11) for i in range(6, 18)],
                *[(i, 12) for i in range(6, 18)],
                *[(i, 13) for i in range(6, 18)],
                *[(i, 14) for i in range(6, 18)],
                # Backpack
                *[(i, 10) for i in range(16, 22)],
                (16, 11), (21, 11),
                (16, 12), (21, 12),
                (16, 13), (21, 13),
                *[(i, 14) for i in range(16, 22)],
                # Walking legs
                (5, 15), (6, 15), (15, 15), (16, 15),
                (4, 16), (5, 16), (16, 16), (17, 16),
                (3, 17), (4, 17), (17, 17), (18, 17),
                (3, 18), (18, 18),
                # Tail up
                (17, 9), (18, 8), (19, 7), (20, 6),
            ]

        elif activity == "school":
            # Dog at desk with book
            pixels = [
                # Left ear
                (5, 1), (6, 1), (7, 1), (6, 2), (7, 2), (7, 3),
                # Right ear
                (14, 1), (15, 1), (16, 1), (14, 2), (15, 2), (14, 3),
                # Head
                *[(i, 4) for i in range(6, 16)],
                *[(i, 5) for i in range(5, 17)],
                *[(i, 6) for i in range(5, 17)],
                (5, 7), (6, 7), (15, 7), (16, 7),
                *[(i, 8) for i in range(6, 16)],
                # Eyes (looking down)
                (8, 7), (9, 7), (12, 7), (13, 7),
                # Nose
                (10, 7), (11, 7),
                # Body at desk
                *[(i, 9) for i in range(6, 16)],
                *[(i, 10) for i in range(6, 16)],
                *[(i, 11) for i in range(6, 16)],
                # Desk surface
                *[(i, 12) for i in range(2, 26)],
                *[(i, 13) for i in range(2, 26)],
                # Desk legs
                (2, 14), (3, 14), (24, 14), (25, 14),
                (2, 15), (3, 15), (24, 15), (25, 15),
                (2, 16), (3, 16), (24, 16), (25, 16),
                (2, 17), (3, 17), (24, 17), (25, 17),
                # Book on desk
                *[(i, 11) for i in range(8, 14)],
                # Paws on desk
                (6, 11), (7, 11), (14, 11), (15, 11),
            ]

        elif activity == "homework":
            # Dog writing with pencil
            pixels = [
                # Left ear
                (5, 2), (6, 2), (7, 2), (6, 3), (7, 3), (7, 4),
                # Right ear
                (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (14, 4),
                # Head (looking down)
                *[(i, 5) for i in range(6, 16)],
                *[(i, 6) for i in range(5, 17)],
                *[(i, 7) for i in range(5, 17)],
                (5, 8), (6, 8), (15, 8), (16, 8),
                *[(i, 9) for i in range(6, 16)],
                # Eyes
                (8, 7), (9, 7), (12, 7), (13, 7),
                # Nose
                (10, 8), (11, 8),
                # Body
                *[(i, 10) for i in range(7, 15)],
                *[(i, 11) for i in range(6, 16)],
                *[(i, 12) for i in range(6, 16)],
                *[(i, 13) for i in range(6, 16)],
                # Sitting legs
                (6, 14), (7, 14), (8, 14), (13, 14), (14, 14), (15, 14),
                (6, 15), (7, 15), (14, 15), (15, 15),
                (6, 16), (7, 16), (14, 16), (15, 16),
                # Paper
                *[(i, 10) for i in range(18, 27)],
                (18, 11), (26, 11),
                (18, 12), (26, 12),
                (18, 13), (26, 13),
                (18, 14), (26, 14),
                *[(i, 15) for i in range(18, 27)],
                # Pencil in paw
                (15, 11), (16, 10), (17, 9), (18, 8), (19, 7),
                # Writing lines
                (20, 11), (21, 11), (22, 11), (23, 11),
                (20, 13), (21, 13), (22, 13),
            ]

        elif activity == "dinner":
            # Dog eating from bowl
            pixels = [
                # Left ear (flopped)
                (4, 5), (5, 5), (6, 5), (5, 6), (6, 6), (6, 7),
                # Right ear (flopped)
                (16, 5), (17, 5), (18, 5), (16, 6), (17, 6), (16, 7),
                # Head (down eating)
                *[(i, 7) for i in range(7, 16)],
                *[(i, 8) for i in range(6, 17)],
                *[(i, 9) for i in range(6, 17)],
                (6, 10), (7, 10), (15, 10), (16, 10),
                *[(i, 11) for i in range(7, 16)],
                *[(i, 12) for i in range(8, 15)],
                # Eyes closed (happy)
                (8, 9), (9, 9), (13, 9), (14, 9),
                # Nose near bowl
                (10, 11), (11, 11), (12, 11),
                # Body
                *[(i, 13) for i in range(9, 20)],
                *[(i, 14) for i in range(9, 20)],
                *[(i, 15) for i in range(9, 20)],
                # Legs
                (9, 16), (10, 16), (17, 16), (18, 16),
                (9, 17), (10, 17), (17, 17), (18, 17),
                # Tail wagging
                (19, 13), (20, 12), (21, 13), (22, 12),
                # Food bowl
                *[(i, 13) for i in range(3, 10)],
                (2, 14), (10, 14),
                (2, 15), (10, 15),
                *[(i, 16) for i in range(2, 11)],
                # Food in bowl
                *[(i, 14) for i in range(4, 9)],
            ]

        else:  # gaming
            # Dog with game controller
            pixels = [
                # Left ear
                (5, 2), (6, 2), (7, 2), (6, 3), (7, 3), (7, 4),
                # Right ear
                (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (14, 4),
                # Head
                *[(i, 5) for i in range(6, 16)],
                *[(i, 6) for i in range(5, 17)],
                *[(i, 7) for i in range(5, 17)],
                (5, 8), (6, 8), (15, 8), (16, 8),
                *[(i, 9) for i in range(6, 16)],
                # Eyes (focused)
                (8, 7), (9, 7), (12, 7), (13, 7),
                # Nose
                (10, 8), (11, 8),
                # Tongue out
                (10, 10), (11, 10), (10, 11), (11, 11),
                # Body
                *[(i, 12) for i in range(7, 15)],
                *[(i, 13) for i in range(6, 16)],
                *[(i, 14) for i in range(6, 16)],
                # Sitting legs
                (6, 15), (7, 15), (8, 15), (13, 15), (14, 15), (15, 15),
                (6, 16), (7, 16), (14, 16), (15, 16),
                (6, 17), (7, 17), (14, 17), (15, 17),
                # Game controller
                *[(i, 13) for i in range(17, 25)],
                *[(i, 14) for i in range(17, 25)],
                *[(i, 15) for i in range(18, 24)],
                # Controller buttons
                (18, 13), (19, 13), (22, 13), (23, 13),
                # Paws holding controller
                (15, 13), (16, 13), (15, 14), (16, 14),
                # TV/Screen
                *[(i, 3) for i in range(20, 29)],
                (20, 4), (28, 4),
                (20, 5), (28, 5),
                (20, 6), (28, 6),
                (20, 7), (28, 7),
                *[(i, 8) for i in range(20, 29)],
            ]

        return pixels

    def _draw_dog(self, draw, x: int, y: int, activity: str):
        """Draw a 30x30 pixel dog based on activity.

        Uses sprite service for all sprites, falls back to hardcoded only if unavailable.
        """
        pixels = []

        # Try to get pixels from sprite service (handles both default and custom)
        sprite_service = self._get_sprite_service()
        if sprite_service:
            sprite_pixels = sprite_service.get_sprite_pixels(activity)
            if sprite_pixels:
                pixels = sprite_pixels

        # Fall back to hardcoded sprites if sprite service unavailable
        if not pixels:
            pixels = self._get_hardcoded_sprite(activity)

        # Draw all pixels
        for dx, dy in pixels:
            draw.point((x + dx, y + dy), fill="white")

    def _format_short_date(self, date_str: str) -> str:
        """Convert date to short format (e.g., 'Jan 15')."""
        # Try to parse common date formats
        months = {
            "january": "Jan", "february": "Feb", "march": "Mar",
            "april": "Apr", "may": "May", "june": "Jun",
            "july": "Jul", "august": "Aug", "september": "Sep",
            "october": "Oct", "november": "Nov", "december": "Dec"
        }
        date_lower = date_str.lower()
        for full, short in months.items():
            if full in date_lower:
                # Extract day number
                import re
                day_match = re.search(r'\d+', date_str)
                if day_match:
                    return f"{short} {day_match.group()}"
        return date_str[:10]  # Fallback

    def show_time(self, time: str, date: str) -> None:
        """Display the current time and date."""
        # This is handled by update() for efficiency
        pass

    def show_weather(self, temp: str, condition: str) -> None:
        """Display current weather."""
        # This is handled by update() for efficiency
        pass

    def show_forecast(self, forecast: list[dict]) -> None:
        """Display weather forecast (temporarily replaces main display)."""
        if not self._device:
            return

        from luma.core.render import canvas

        with canvas(self._device) as draw:
            draw.text((0, 0), "Forecast:", font=self._font_medium, fill="white")
            y = 14
            for hour in forecast[:4]:
                text = f"{hour.get('time', '')}: {hour.get('temp', '')} {hour.get('condition', '')[:10]}"
                draw.text((0, y), text, font=self._font_small, fill="white")
                y += 12

    def show_alarm_active(self, label: str | None = None) -> None:
        """Display alarm active indicator."""
        # Handled by update() with blinking
        pass

    def clear_alarm_active(self) -> None:
        """Clear alarm active indicator."""
        pass

    def update(self, data: DisplayData) -> None:
        """Update display with all current data."""
        if not self._device:
            return

        self._last_data = data

        from luma.core.render import canvas

        with canvas(self._device) as draw:
            if data.alarm_active:
                # Alarm mode - custom text flashing black/white
                self._alarm_blink_state = not self._alarm_blink_state

                if self._alarm_blink_state:
                    # White background, black text
                    bg_color = "white"
                    text_color = "black"
                else:
                    # Black background, white text
                    bg_color = "black"
                    text_color = "white"

                draw.rectangle([(0, 0), (self.WIDTH, self.HEIGHT)], fill=bg_color)

                # Split display text into two lines for better display
                display_text = data.alarm_display_text or "Wake up Claire!"
                words = display_text.split()
                if len(words) >= 2:
                    # Split roughly in half
                    mid = len(words) // 2
                    text1 = " ".join(words[:mid])
                    text2 = " ".join(words[mid:])
                else:
                    text1 = display_text
                    text2 = ""

                bbox1 = draw.textbbox((0, 0), text1, font=self._font_alarm)
                x1 = (self.WIDTH - (bbox1[2] - bbox1[0])) // 2
                if text2:
                    bbox2 = draw.textbbox((0, 0), text2, font=self._font_alarm)
                    x2 = (self.WIDTH - (bbox2[2] - bbox2[0])) // 2
                    draw.text((x1, 12), text1, font=self._font_alarm, fill=text_color)
                    draw.text((x2, 36), text2, font=self._font_alarm, fill=text_color)
                else:
                    # Single line, center vertically
                    draw.text((x1, 24), text1, font=self._font_alarm, fill=text_color)
            else:
                # Normal mode - time, date, weather, dog
                # Time - large, centered, takes up top portion
                time_text = data.time
                # Get text bounding box for centering
                bbox = draw.textbbox((0, 0), time_text, font=self._font_time)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x_pos = (self.WIDTH - text_width) // 2
                draw.text((x_pos, 2), time_text, font=self._font_time, fill="white")

                # Dog character - bottom left (30x30)
                activity = self._get_dog_activity(data.hour)
                self._draw_dog(draw, 0, 32, activity)

                # Date - small, short format, right of dog
                short_date = self._format_short_date(data.date)
                draw.text((32, 36), short_date, font=self._font_small, fill="white")

                # Day of week - tiny, below date
                if data.weekday_name:
                    draw.text((32, 48), data.weekday_name, font=self._font_tiny, fill="white")

                # Weather icon and temp - bottom right
                if data.weather_temp:
                    # Draw weather icon (uses hour to show moon at night)
                    icon_type = self._get_weather_icon_type(data.weather_condition, data.hour)
                    icon_x = 78
                    icon_size = 18
                    self._draw_weather_icon(draw, icon_x, 32, icon_type, size=icon_size)

                    # Temperature next to icon with 10px gap
                    temp_x = icon_x + icon_size + 10
                    draw.text((temp_x, 38), data.weather_temp, font=self._font_small, fill="white")

                # Envelope icon in lower-right corner when messages pending
                if data.has_unread_messages:
                    self._draw_envelope_icon(draw, 118, 56)

    def show_message(self, text: str, is_last: bool = False) -> None:
        """Display a message on screen (full screen with word-wrapped text)."""
        if not self._device:
            return

        self._showing_message = True
        self._message_text = text
        self._message_is_last = is_last

        from luma.core.render import canvas

        with canvas(self._device) as draw:
            if is_last:
                # Show "End of messages" centered
                msg = "End of messages"
                bbox = draw.textbbox((0, 0), msg, font=self._font_medium)
                text_width = bbox[2] - bbox[0]
                x = (self.WIDTH - text_width) // 2
                draw.text((x, 26), msg, font=self._font_medium, fill="white")
            else:
                # Word-wrap and display message text
                self._draw_wrapped_text(draw, text, 4, 4, self.WIDTH - 8, self._font_small)

    def _draw_wrapped_text(self, draw, text: str, x: int, y: int, max_width: int, font) -> None:
        """Draw word-wrapped text within a maximum width."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # Draw each line
        line_height = 12
        for i, line in enumerate(lines[:5]):  # Max 5 lines
            draw.text((x, y + i * line_height), line, font=font, fill="white")

    def show_music_player(
        self,
        track_name: str,
        track_num: int,
        total_tracks: int,
        elapsed_ms: int,
        duration_ms: int | None = None,
    ) -> None:
        """Display music player screen with track info and progress."""
        if not self._device:
            return

        from luma.core.render import canvas

        # Strip file extension for display
        display_name = track_name.rsplit(".", 1)[0] if "." in track_name else track_name

        # Elapsed time string
        elapsed_s = elapsed_ms // 1000
        elapsed_str = f"{elapsed_s // 60}:{elapsed_s % 60:02d}"
        if duration_ms is not None:
            duration_s = duration_ms // 1000
            time_str = f"{elapsed_str} / {duration_s // 60}:{duration_s % 60:02d}"
        else:
            time_str = elapsed_str

        with canvas(self._device) as draw:
            # Header row
            draw.text((0, 0), "Now Playing", font=self._font_tiny, fill="white")

            # Track name — truncate to fit 128px width using the small font
            # Measure and shorten until it fits
            name = display_name
            while name:
                bbox = draw.textbbox((0, 0), name, font=self._font_small)
                if bbox[2] - bbox[0] <= self.WIDTH:
                    break
                name = name[:-1]
            if name != display_name:
                name = name[:-1] + "\u2026"  # ellipsis
            draw.text((0, 11), name, font=self._font_small, fill="white")

            # Track position
            draw.text((0, 24), f"Track {track_num} of {total_tracks}", font=self._font_tiny, fill="white")

            # Progress bar outline
            bar_x, bar_y, bar_w, bar_h = 4, 35, 120, 6
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline="white")

            inner_w = bar_w - 2
            if duration_ms and duration_ms > 0:
                fill_w = int(min(elapsed_ms / duration_ms, 1.0) * inner_w)
                if fill_w > 0:
                    draw.rectangle(
                        [bar_x + 1, bar_y + 1, bar_x + 1 + fill_w, bar_y + bar_h - 1],
                        fill="white",
                    )
            else:
                # Bouncing indicator when duration unknown
                block_w = 20
                period = inner_w - block_w
                tick = (elapsed_ms // 300) % (period * 2)
                pos = tick if tick <= period else period * 2 - tick
                draw.rectangle(
                    [bar_x + 1 + pos, bar_y + 1, bar_x + 1 + pos + block_w, bar_y + bar_h - 1],
                    fill="white",
                )

            # Time display
            draw.text((0, 44), time_str, font=self._font_tiny, fill="white")

            # Button hints
            draw.text((0, 55), "< Prev", font=self._font_tiny, fill="white")
            draw.text((88, 55), "Next >", font=self._font_tiny, fill="white")

    def clear_message(self) -> None:
        """Clear message display and return to normal mode."""
        self._showing_message = False
        self._message_text = None
        self._message_is_last = False


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
