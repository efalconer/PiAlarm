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


class WaveshareOLED(Display):
    """Waveshare 2.42" OLED display (SSD1309, 128x64, I2C/SPI)."""

    # Display dimensions
    WIDTH = 128
    HEIGHT = 64

    def __init__(self, interface: str = "i2c", i2c_address: int = 0x3C,
                 spi_device: int = 0, spi_port: int = 0,
                 gpio_dc: int = 24, gpio_rst: int = 25):
        """
        Initialize Waveshare OLED display.

        Args:
            interface: "i2c" or "spi"
            i2c_address: I2C address (default 0x3C)
            spi_device: SPI device number (default 0)
            spi_port: SPI port number (default 0)
            gpio_dc: GPIO pin for DC (SPI only)
            gpio_rst: GPIO pin for reset (SPI only)
        """
        self._interface = interface
        self._i2c_address = i2c_address
        self._spi_device = spi_device
        self._spi_port = spi_port
        self._gpio_dc = gpio_dc
        self._gpio_rst = gpio_rst

        self._device = None
        self._brightness = 100
        self._last_data: DisplayData | None = None
        self._font_large = None
        self._font_medium = None
        self._font_small = None
        self._alarm_blink_state = False

    def initialize(self) -> bool:
        """Initialize the OLED display."""
        try:
            from luma.core.interface.serial import i2c, spi
            from luma.oled.device import ssd1309
            from PIL import ImageFont

            # Set up serial interface
            if self._interface == "i2c":
                serial = i2c(port=1, address=self._i2c_address)
            else:
                serial = spi(device=self._spi_device, port=self._spi_port,
                            gpio_DC=self._gpio_dc, gpio_RST=self._gpio_rst)

            # Create device
            self._device = ssd1309(serial, width=self.WIDTH, height=self.HEIGHT)

            # Load fonts - try custom fonts first, fall back to default
            try:
                font_path = FONT_DIR / "DejaVuSans.ttf"
                if font_path.exists():
                    self._font_large = ImageFont.truetype(str(font_path), 32)
                    self._font_medium = ImageFont.truetype(str(font_path), 14)
                    self._font_small = ImageFont.truetype(str(font_path), 10)
                else:
                    raise FileNotFoundError("Custom font not found")
            except Exception:
                # Fall back to default font
                self._font_large = ImageFont.load_default()
                self._font_medium = ImageFont.load_default()
                self._font_small = ImageFont.load_default()
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
                # Alarm mode - large blinking display
                self._alarm_blink_state = not self._alarm_blink_state
                if self._alarm_blink_state:
                    # Draw inverted (white background, black text)
                    draw.rectangle([(0, 0), (self.WIDTH, self.HEIGHT)], fill="white")
                    draw.text((10, 5), "ALARM!", font=self._font_large, fill="black")
                    if data.alarm_label:
                        draw.text((10, 42), data.alarm_label[:15], font=self._font_medium, fill="black")
                else:
                    # Normal colors
                    draw.text((10, 5), "ALARM!", font=self._font_large, fill="white")
                    if data.alarm_label:
                        draw.text((10, 42), data.alarm_label[:15], font=self._font_medium, fill="white")
            else:
                # Normal mode - time, date, weather
                # Time - large, centered at top
                time_text = data.time
                draw.text((4, 0), time_text, font=self._font_large, fill="white")

                # Date - medium, below time
                draw.text((4, 36), data.date[:20], font=self._font_small, fill="white")

                # Weather - bottom right
                if data.weather_temp:
                    weather_text = f"{data.weather_temp}"
                    draw.text((90, 0), weather_text, font=self._font_medium, fill="white")

                    if data.weather_condition:
                        # Truncate condition to fit
                        cond = data.weather_condition[:12]
                        draw.text((4, 50), cond, font=self._font_small, fill="white")


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
