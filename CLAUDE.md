# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PiAlarm is a Raspberry Pi Zero 2-based alarm clock with I2S audio output, weather display, and web-based configuration.

**Hardware:**
- Raspberry Pi Zero 2
- Adafruit I2S 3W Stereo Speaker Bonnet
- Waveshare 2.42" OLED (SSD1309, 128x64, I2C/SPI)

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python -m src.main

# Run on Pi (with GPIO access)
sudo python -m src.main
```

The web interface runs on port 5000 by default.

## Architecture

```
src/
├── main.py           # Application entry point and main loop
├── config.py         # Configuration management (config.json)
├── services/         # Core business logic
│   ├── time_service.py    # NTP sync, time formatting
│   ├── weather_service.py # WeatherAPI.com integration
│   ├── alarm_service.py   # Alarm scheduling, SQLite persistence
│   └── audio_service.py   # MP3 playback via pygame
├── hardware/         # Hardware abstractions
│   ├── buttons.py    # GPIO button input (snooze/dismiss/forecast)
│   └── display.py    # Display interface (abstract, console fallback)
└── web/              # Flask web interface
    ├── app.py        # Routes and API endpoints
    └── templates/    # Jinja2 HTML templates
```

**Key patterns:**
- Each service uses a singleton pattern via `get_*_service()` functions
- Hardware modules gracefully degrade when not on Pi (simulation mode)
- Display uses abstract base class for future hardware implementations
- Web server runs in a daemon thread alongside main loop

**Data storage:**
- `config.json` - Application settings (weather API key, timezone, etc.)
- `data/alarms.db` - SQLite database for alarm persistence
- `music/` - Directory for alarm sound MP3 files

## Configuration

Weather requires a WeatherAPI.com API key. Configure via web interface at `/settings` or edit `config.json`:

```json
{
  "weather_api_key": "your_key",
  "weather_location": "San Francisco"
}
```

## GPIO Pin Assignments

- GPIO 17: Snooze button
- GPIO 27: Dismiss button
- GPIO 22: Forecast button

Buttons use pull-up resistors (connect button between GPIO and GND).

## Display Configuration

The Waveshare 2.42" OLED uses the SSD1309 controller. Configure in `config.json`:

```json
{
  "display_type": "auto",
  "display_interface": "i2c",
  "display_i2c_address": 60,
  "display_brightness": 100
}
```

- `display_type`: "auto" (detect), "oled", or "console"
- `display_interface`: "i2c" or "spi"
- `display_i2c_address`: I2C address (60 = 0x3C, 61 = 0x3D)
- `display_brightness`: 0-100

**I2C Wiring:**
| OLED Pin | Pi Pin |
|----------|--------|
| VCC | 3.3V (Pin 1) |
| GND | GND (Pin 6) |
| SDA | GPIO 2 (Pin 3) |
| SCL | GPIO 3 (Pin 5) |

Enable I2C on Pi: `sudo raspi-config` → Interface Options → I2C
