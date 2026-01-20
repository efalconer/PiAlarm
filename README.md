# PiAlarm

A Raspberry Pi-based alarm clock with weather display and web configuration.

## Hardware

- Raspberry Pi Zero 2
- Adafruit I2S 3W Stereo Speaker Bonnet
- Waveshare 2.42" OLED display (SSD1309, 128x64)
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

### 2. Install fonts

The OLED display requires the DejaVu font family for proper text rendering:

```bash
sudo apt install fonts-dejavu
```

### 3. Configure I2S audio (on Raspberry Pi)

Follow the [Adafruit Speaker Bonnet guide](https://learn.adafruit.com/adafruit-speaker-bonnet-for-raspberry-pi) to enable I2S audio.

### 4. Connect the OLED display

Enable SPI on your Pi:
```bash
sudo raspi-config
# Navigate to: Interface Options → SPI → Enable
```

Wire the Waveshare 2.42" OLED:

| OLED Pin | Pi Pin | Description |
|----------|--------|-------------|
| VCC | 3.3V (Pin 1) | Power |
| GND | GND (Pin 6) | Ground |
| DIN | GPIO 10 (Pin 19) | SPI MOSI |
| CLK | GPIO 11 (Pin 23) | SPI SCLK |
| CS | GPIO 8 (Pin 24) | SPI CE0 |
| DC | GPIO 24 (Pin 18) | Data/Command |
| RST | GPIO 25 (Pin 22) | Reset |

### 5. Wire buttons

Connect momentary push buttons between GPIO and GND:

| Button   | GPIO Pin |
|----------|----------|
| Snooze   | GPIO 17  |
| Dismiss  | GPIO 27  |
| Forecast | GPIO 22  |

### 6. Add alarm sounds

Place MP3 or WAV files in the `music/` directory.

### 7. Configure weather

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

## Auto-Start on Boot

Create a systemd service to start PiAlarm automatically and restart it if it crashes.

Create `/etc/systemd/system/pialarm.service`:

```ini
[Unit]
Description=PiAlarm Clock
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/PiAlarm
ExecStart=/usr/bin/python3 -m src.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pialarm
sudo systemctl start pialarm
```

Useful commands:

```bash
sudo systemctl status pialarm    # Check status
sudo systemctl stop pialarm      # Stop the service
sudo systemctl restart pialarm   # Restart the service
journalctl -u pialarm -f         # View live logs
```

## License

MIT
