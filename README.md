# PiAlarm

A Raspberry Pi-based alarm clock with weather display and web configuration.

## Hardware

- Raspberry Pi Zero 2
- Adafruit I2S 3W Stereo Speaker Bonnet
- Display: TBD
- 3 momentary push buttons (snooze, dismiss, forecast)

## Features

- Display time with automatic NTP synchronization
- Current weather with hourly refresh (via WeatherAPI.com)
- Weather forecast on button press
- Multiple alarms with per-day scheduling
- MP3 alarm sounds
- Snooze and dismiss via physical buttons or web interface
- Web-based configuration and alarm management

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure I2S audio (on Raspberry Pi)

Follow the [Adafruit Speaker Bonnet guide](https://learn.adafruit.com/adafruit-speaker-bonnet-for-raspberry-pi) to enable I2S audio.

### 3. Wire buttons

Connect momentary push buttons between GPIO and GND:

| Button   | GPIO Pin |
|----------|----------|
| Snooze   | GPIO 17  |
| Dismiss  | GPIO 27  |
| Forecast | GPIO 22  |

### 4. Add alarm sounds

Place MP3 files in the `music/` directory.

### 5. Configure weather

Get a free API key from [weatherapi.com](https://www.weatherapi.com) and configure via the web interface or edit `config.json`:

```json
{
  "weather_api_key": "your_api_key",
  "weather_location": "San Francisco"
}
```

## Running

```bash
# Development (no GPIO)
python -m src.main

# On Raspberry Pi (requires GPIO access)
sudo python -m src.main
```

The web interface is available at `http://<pi-ip>:5000`

## Web Interface

- **Home** - Current time, weather, and active alarms
- **Alarms** - Create, edit, enable/disable, and delete alarms
- **Settings** - Configure weather API, timezone, snooze duration, and time format

## License

MIT
