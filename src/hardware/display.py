"""Display abstraction for PiAlarm - interface for display hardware."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Font directory
FONT_DIR = Path(__file__).parent.parent.parent / "fonts"


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
        alarm_text = " [Wake up Claire!]"
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
        self._font_alarm = None
        self._font_alarm_small = None
        self._alarm_blink_state = False

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
                        self._font_time = ImageFont.truetype(str(bold_font), 28)
                        self._font_medium = ImageFont.truetype(str(font_path), 14)
                        self._font_small = ImageFont.truetype(str(font_path), 11)
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

    def _get_weather_icon_type(self, condition: str | None) -> str:
        """Get icon type from weather condition string."""
        if not condition:
            return "sun"
        condition_lower = condition.lower()
        for key, icon in self.WEATHER_ICONS.items():
            if key in condition_lower:
                return icon
        return "sun"  # Default

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
                # Alarm mode - "Wake up Claire!" flashing black/white
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

                # Draw "Wake up" on first line, "Claire!" on second - centered
                text1 = "Wake up"
                text2 = "Claire!"
                bbox1 = draw.textbbox((0, 0), text1, font=self._font_alarm)
                bbox2 = draw.textbbox((0, 0), text2, font=self._font_alarm)
                x1 = (self.WIDTH - (bbox1[2] - bbox1[0])) // 2
                x2 = (self.WIDTH - (bbox2[2] - bbox2[0])) // 2
                draw.text((x1, 12), text1, font=self._font_alarm, fill=text_color)
                draw.text((x2, 36), text2, font=self._font_alarm, fill=text_color)
            else:
                # Normal mode - time, date, weather
                # Time - large, centered, takes up top portion
                time_text = data.time
                # Get text bounding box for centering
                bbox = draw.textbbox((0, 0), time_text, font=self._font_time)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x_pos = (self.WIDTH - text_width) // 2
                draw.text((x_pos, 2), time_text, font=self._font_time, fill="white")

                # Date - small, short format, bottom left
                short_date = self._format_short_date(data.date)
                draw.text((2, 50), short_date, font=self._font_small, fill="white")

                # Weather icon and temp - bottom right
                if data.weather_temp:
                    # Draw weather icon
                    icon_type = self._get_weather_icon_type(data.weather_condition)
                    self._draw_weather_icon(draw, 80, 44, icon_type, size=18)

                    # Temperature next to icon
                    draw.text((100, 50), data.weather_temp, font=self._font_small, fill="white")


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
