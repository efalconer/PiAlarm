"""Button handler for PiAlarm - GPIO button input with debouncing."""

import logging
from typing import Callable
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import gpiozero, fall back to mock for development
try:
    from gpiozero import Button as GPIOButton
    from gpiozero.exc import BadPinFactory
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("gpiozero not available - buttons will be simulated")


class Button(Enum):
    """Available physical buttons."""

    SNOOZE = 17
    DISMISS = 27
    FORECAST = 22
    MESSAGES = 23
    MUSIC = 5


class ButtonHandler:
    """Handles physical button input via GPIO."""

    def __init__(self):
        self._callbacks: dict[Button, Callable[[], None]] = {}
        self._buttons: dict[Button, "GPIOButton"] = {}
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize GPIO for button input."""
        if not GPIO_AVAILABLE:
            logger.info("Button handler running in simulation mode")
            self._initialized = True
            return True

        try:
            for button in Button:
                gpio_button = GPIOButton(
                    button.value,
                    pull_up=True,
                    bounce_time=0.1,
                )
                gpio_button.when_pressed = lambda b=button: self._handle_press(b)
                self._buttons[button] = gpio_button

            self._initialized = True
            logger.info("Button handler initialized")
            return True
        except BadPinFactory as e:
            logger.info("Button handler running in simulation mode (no GPIO available)")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize buttons: {e}")
            return False

    def shutdown(self) -> None:
        """Clean up GPIO resources."""
        if self._buttons:
            for gpio_button in self._buttons.values():
                gpio_button.close()
            self._buttons.clear()
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
