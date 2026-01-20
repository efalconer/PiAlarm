"""Button handler for PiAlarm - GPIO button input with debouncing."""

import logging
from typing import Callable
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import RPi.GPIO, fall back to mock for development
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("RPi.GPIO not available - buttons will be simulated")


class Button(Enum):
    """Available physical buttons."""

    SNOOZE = 17
    DISMISS = 27
    FORECAST = 22


class ButtonHandler:
    """Handles physical button input via GPIO."""

    def __init__(self):
        self._callbacks: dict[Button, Callable[[], None]] = {}
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize GPIO for button input."""
        if not GPIO_AVAILABLE:
            logger.info("Button handler running in simulation mode")
            self._initialized = True
            return True

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            for button in Button:
                GPIO.setup(button.value, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(
                    button.value,
                    GPIO.FALLING,
                    callback=lambda channel, b=button: self._handle_press(b),
                    bouncetime=300,
                )

            self._initialized = True
            logger.info("Button handler initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize buttons: {e}")
            return False

    def shutdown(self) -> None:
        """Clean up GPIO resources."""
        if GPIO_AVAILABLE and self._initialized:
            GPIO.cleanup()
            logger.info("Button handler shutdown")
        self._initialized = False

    def set_callback(self, button: Button, callback: Callable[[], None]) -> None:
        """Set callback for a button press."""
        self._callbacks[button] = callback

    def _handle_press(self, button: Button) -> None:
        """Handle a button press event."""
        logger.debug(f"Button pressed: {button.name}")
        callback = self._callbacks.get(button)
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in button callback: {e}")

    def simulate_press(self, button: Button) -> None:
        """Simulate a button press (for testing/web interface)."""
        self._handle_press(button)


# Global instance
_button_handler: ButtonHandler | None = None


def get_button_handler() -> ButtonHandler:
    """Get the global button handler instance."""
    global _button_handler
    if _button_handler is None:
        _button_handler = ButtonHandler()
    return _button_handler
