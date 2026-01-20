"""Flask web application for PiAlarm configuration."""

import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for

from src.config import get_config, MUSIC_DIR
from src.services.alarm_service import get_alarm_service, Alarm
from src.services.audio_service import get_audio_service
from src.services.weather_service import get_weather_service
from src.services.time_service import get_time_service
from src.hardware.buttons import get_button_handler, Button

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    """Dashboard - show current status and alarms."""
    alarm_service = get_alarm_service()
    time_service = get_time_service()
    weather_service = get_weather_service()

    return render_template(
        "index.html",
        alarms=alarm_service.get_all(),
        time_data=time_service.get_display_data(),
        weather=weather_service.get_display_data(),
        is_alarm_active=alarm_service.is_alarm_active,
    )


@app.route("/alarms")
def list_alarms():
    """List all alarms."""
    alarm_service = get_alarm_service()
    return render_template("alarms.html", alarms=alarm_service.get_all())


@app.route("/alarms/new", methods=["GET", "POST"])
def new_alarm():
    """Create a new alarm."""
    audio_service = get_audio_service()
    sounds = audio_service.get_available_sounds()

    if request.method == "POST":
        alarm_service = get_alarm_service()
        time_parts = request.form.get("time", "07:00").split(":")
        days = request.form.getlist("days")

        alarm = Alarm(
            id=None,
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            days=[int(d) for d in days],
            enabled=True,
            sound_file=request.form.get("sound", sounds[0] if sounds else ""),
            label=request.form.get("label", ""),
        )
        alarm_service.create(alarm)
        return redirect(url_for("list_alarms"))

    return render_template("alarm_form.html", alarm=None, sounds=sounds)


@app.route("/alarms/<int:alarm_id>/edit", methods=["GET", "POST"])
def edit_alarm(alarm_id: int):
    """Edit an existing alarm."""
    alarm_service = get_alarm_service()
    audio_service = get_audio_service()
    alarm = alarm_service.get_by_id(alarm_id)
    sounds = audio_service.get_available_sounds()

    if not alarm:
        return redirect(url_for("list_alarms"))

    if request.method == "POST":
        time_parts = request.form.get("time", "07:00").split(":")
        days = request.form.getlist("days")

        alarm.hour = int(time_parts[0])
        alarm.minute = int(time_parts[1])
        alarm.days = [int(d) for d in days]
        alarm.sound_file = request.form.get("sound", alarm.sound_file)
        alarm.label = request.form.get("label", "")
        alarm_service.update(alarm)
        return redirect(url_for("list_alarms"))

    return render_template("alarm_form.html", alarm=alarm, sounds=sounds)


@app.route("/alarms/<int:alarm_id>/delete", methods=["POST"])
def delete_alarm(alarm_id: int):
    """Delete an alarm."""
    alarm_service = get_alarm_service()
    alarm_service.delete(alarm_id)
    return redirect(url_for("list_alarms"))


@app.route("/alarms/<int:alarm_id>/toggle", methods=["POST"])
def toggle_alarm(alarm_id: int):
    """Toggle alarm enabled state."""
    alarm_service = get_alarm_service()
    new_state = alarm_service.toggle(alarm_id)
    return jsonify({"enabled": new_state})


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Application settings."""
    config = get_config()

    if request.method == "POST":
        config.update({
            "weather_api_key": request.form.get("weather_api_key", ""),
            "weather_location": request.form.get("weather_location", ""),
            "timezone": request.form.get("timezone", "America/Los_Angeles"),
            "snooze_duration_minutes": int(request.form.get("snooze_duration", 9)),
            "time_format_24h": request.form.get("time_format_24h") == "on",
        })
        return redirect(url_for("settings"))

    return render_template("settings.html", config=config)


@app.route("/api/status")
def api_status():
    """API endpoint for current status."""
    alarm_service = get_alarm_service()
    time_service = get_time_service()
    weather_service = get_weather_service()

    return jsonify({
        "time": time_service.get_display_data(),
        "weather": weather_service.get_display_data(),
        "alarm_active": alarm_service.is_alarm_active,
        "is_snoozed": alarm_service.is_snoozed,
    })


@app.route("/api/snooze", methods=["POST"])
def api_snooze():
    """Snooze the current alarm."""
    button_handler = get_button_handler()
    button_handler.simulate_press(Button.SNOOZE)
    return jsonify({"success": True})


@app.route("/api/dismiss", methods=["POST"])
def api_dismiss():
    """Dismiss the current alarm."""
    button_handler = get_button_handler()
    button_handler.simulate_press(Button.DISMISS)
    return jsonify({"success": True})


@app.route("/api/forecast")
def api_forecast():
    """Get weather forecast."""
    weather_service = get_weather_service()
    forecast = weather_service.get_forecast()
    return jsonify([{
        "time": h.time.strftime("%I %p"),
        "temp": f"{int(h.temp_f)}°",
        "condition": h.condition,
        "rain_chance": h.chance_of_rain,
    } for h in forecast])


def run_web_server():
    """Run the Flask web server."""
    config = get_config()
    app.run(host="0.0.0.0", port=config.web_port, debug=False, threaded=True)
