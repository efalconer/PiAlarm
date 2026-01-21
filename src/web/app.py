"""Flask web application for PiAlarm configuration."""

import json
import logging
import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for

from src.config import get_config, MUSIC_DIR
from src.services.alarm_service import get_alarm_service, Alarm
from src.services.audio_service import get_audio_service
from src.services.weather_service import get_weather_service
from src.services.time_service import get_time_service
from src.services.playlist_service import get_playlist_service, Playlist
from src.services.sprite_service import get_sprite_service, Sprite, TimeRange
from src.hardware.buttons import get_button_handler, Button

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload


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


@app.route("/music")
def music():
    """Music library and playlists."""
    audio_service = get_audio_service()
    playlist_service = get_playlist_service()
    return render_template(
        "music.html",
        sounds=audio_service.get_available_sounds(),
        playlists=playlist_service.get_all(),
        has_active_playback=audio_service.has_active_playback(),
        is_playing=audio_service.is_playing(),
        is_paused=audio_service.is_paused,
        current_file=audio_service.current_file,
        is_playlist_mode=audio_service.is_playlist_mode,
        playlist_position=audio_service.playlist_position,
    )


@app.route("/music/now-playing")
def now_playing():
    """Now playing page with full controls."""
    audio_service = get_audio_service()
    return render_template(
        "now_playing.html",
        has_active_playback=audio_service.has_active_playback(),
        is_playing=audio_service.is_playing(),
        is_paused=audio_service.is_paused,
        current_file=audio_service.current_file,
        is_playlist_mode=audio_service.is_playlist_mode,
        playlist_position=audio_service.playlist_position,
        volume=int(audio_service.get_volume() * 100),
    )


@app.route("/music/upload", methods=["POST"])
def upload_music():
    """Upload MP3 files."""
    if "files" not in request.files:
        return redirect(url_for("music"))

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    files = request.files.getlist("files")
    for file in files:
        if file and file.filename and file.filename.lower().endswith((".mp3", ".wav")):
            filename = secure_filename(file.filename)
            file.save(MUSIC_DIR / filename)
            logger.info(f"Uploaded: {filename}")

    return redirect(url_for("music"))


@app.route("/music/<filename>/delete", methods=["POST"])
def delete_music(filename: str):
    """Delete an MP3 file."""
    audio_service = get_audio_service()
    audio_service.delete_file(filename)
    return redirect(url_for("music"))


@app.route("/music/<filename>/play", methods=["POST"])
def play_music(filename: str):
    """Play a single MP3 file."""
    audio_service = get_audio_service()
    audio_service.play(filename, loop=False)
    return redirect(url_for("music"))


@app.route("/music/stop", methods=["POST"])
def stop_music():
    """Stop playback."""
    audio_service = get_audio_service()
    audio_service.stop()
    return redirect(url_for("music"))


@app.route("/music/pause", methods=["POST"])
def pause_music():
    """Pause playback."""
    audio_service = get_audio_service()
    audio_service.pause()
    return redirect(url_for("now_playing"))


@app.route("/music/resume", methods=["POST"])
def resume_music():
    """Resume playback."""
    audio_service = get_audio_service()
    audio_service.unpause()
    return redirect(url_for("now_playing"))


@app.route("/music/next", methods=["POST"])
def next_track():
    """Skip to next track."""
    audio_service = get_audio_service()
    audio_service.next_track()
    return redirect(url_for("music"))


@app.route("/music/previous", methods=["POST"])
def previous_track():
    """Go to previous track."""
    audio_service = get_audio_service()
    audio_service.previous_track()
    return redirect(url_for("music"))


@app.route("/playlists/new", methods=["GET", "POST"])
def new_playlist():
    """Create a new playlist."""
    audio_service = get_audio_service()
    sounds = audio_service.get_available_sounds()

    if request.method == "POST":
        playlist_service = get_playlist_service()
        tracks = request.form.getlist("tracks")
        playlist = Playlist(
            id=None,
            name=request.form.get("name", "New Playlist"),
            tracks=tracks,
        )
        playlist_service.create(playlist)
        return redirect(url_for("music"))

    return render_template("playlist_form.html", playlist=None, sounds=sounds)


@app.route("/playlists/<int:playlist_id>/edit", methods=["GET", "POST"])
def edit_playlist(playlist_id: int):
    """Edit a playlist."""
    playlist_service = get_playlist_service()
    audio_service = get_audio_service()
    playlist = playlist_service.get_by_id(playlist_id)
    sounds = audio_service.get_available_sounds()

    if not playlist:
        return redirect(url_for("music"))

    if request.method == "POST":
        playlist.name = request.form.get("name", playlist.name)
        playlist.tracks = request.form.getlist("tracks")
        playlist_service.update(playlist)
        return redirect(url_for("music"))

    return render_template("playlist_form.html", playlist=playlist, sounds=sounds)


@app.route("/playlists/<int:playlist_id>/delete", methods=["POST"])
def delete_playlist(playlist_id: int):
    """Delete a playlist."""
    playlist_service = get_playlist_service()
    playlist_service.delete(playlist_id)
    return redirect(url_for("music"))


@app.route("/playlists/<int:playlist_id>/play", methods=["POST"])
def play_playlist(playlist_id: int):
    """Play a playlist."""
    playlist_service = get_playlist_service()
    audio_service = get_audio_service()
    playlist = playlist_service.get_by_id(playlist_id)

    if playlist and playlist.tracks:
        audio_service.play_playlist(playlist.tracks)

    return redirect(url_for("music"))


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


@app.route("/sprites")
def list_sprites():
    """List all sprites."""
    sprite_service = get_sprite_service()
    return render_template("sprites.html", sprites=sprite_service.get_all())


@app.route("/sprites/new", methods=["GET", "POST"])
def new_sprite():
    """Create a new sprite."""
    if request.method == "POST":
        sprite_service = get_sprite_service()

        # Parse pixels from JSON string
        pixels_json = request.form.get("pixels", "[]")
        try:
            pixels_list = json.loads(pixels_json)
            pixels = [tuple(p) for p in pixels_list]
        except json.JSONDecodeError:
            pixels = []

        # Parse time ranges from JSON string
        time_ranges_json = request.form.get("time_ranges", "[]")
        try:
            time_ranges_list = json.loads(time_ranges_json)
            time_ranges = [TimeRange(tr["start"], tr["end"]) for tr in time_ranges_list]
        except (json.JSONDecodeError, KeyError):
            time_ranges = []

        sprite = Sprite(
            id="",  # Will be generated
            name=request.form.get("name", "New Sprite"),
            pixels=pixels,
            time_ranges=time_ranges,
        )
        sprite_service.create(sprite)
        return redirect(url_for("list_sprites"))

    return render_template("sprite_editor.html", sprite=None)


@app.route("/sprites/<sprite_id>/edit", methods=["GET", "POST"])
def edit_sprite(sprite_id: str):
    """Edit an existing sprite."""
    sprite_service = get_sprite_service()
    sprite = sprite_service.get_by_id(sprite_id)

    if not sprite:
        return redirect(url_for("list_sprites"))

    if request.method == "POST":
        # Parse pixels from JSON string
        pixels_json = request.form.get("pixels", "[]")
        try:
            pixels_list = json.loads(pixels_json)
            pixels = [tuple(p) for p in pixels_list]
        except json.JSONDecodeError:
            pixels = sprite.pixels

        # Parse time ranges from JSON string
        time_ranges_json = request.form.get("time_ranges", "[]")
        try:
            time_ranges_list = json.loads(time_ranges_json)
            time_ranges = [TimeRange(tr["start"], tr["end"]) for tr in time_ranges_list]
        except (json.JSONDecodeError, KeyError):
            time_ranges = sprite.time_ranges

        sprite.name = request.form.get("name", sprite.name)
        sprite.pixels = pixels
        sprite.time_ranges = time_ranges
        sprite_service.update(sprite)
        return redirect(url_for("list_sprites"))

    # Prepare serializable data for template
    sprite_data = {
        "pixels": [[x, y] for x, y in sprite.pixels],
        "time_ranges": [tr.to_dict() for tr in sprite.time_ranges],
    }
    return render_template("sprite_editor.html", sprite=sprite, sprite_data=sprite_data)


@app.route("/sprites/<sprite_id>/delete", methods=["POST"])
def delete_sprite(sprite_id: str):
    """Delete a sprite."""
    sprite_service = get_sprite_service()
    sprite_service.delete(sprite_id)
    return redirect(url_for("list_sprites"))


@app.route("/api/sprites/<sprite_id>")
def api_sprite(sprite_id: str):
    """Get sprite data as JSON."""
    sprite_service = get_sprite_service()
    sprite = sprite_service.get_by_id(sprite_id)
    if sprite:
        return jsonify({
            "id": sprite.id,
            "name": sprite.name,
            "pixels": [[x, y] for x, y in sprite.pixels],
            "time_ranges": [tr.to_dict() for tr in sprite.time_ranges],
        })
    return jsonify({"error": "Sprite not found"}), 404


@app.route("/api/status")
def api_status():
    """API endpoint for current status."""
    alarm_service = get_alarm_service()
    time_service = get_time_service()
    weather_service = get_weather_service()
    audio_service = get_audio_service()

    return jsonify({
        "time": time_service.get_display_data(),
        "weather": weather_service.get_display_data(),
        "alarm_active": alarm_service.is_alarm_active,
        "is_snoozed": alarm_service.is_snoozed,
        "music": {
            "has_active_playback": audio_service.has_active_playback(),
            "is_playing": audio_service.is_playing(),
            "is_paused": audio_service.is_paused,
            "current_file": audio_service.current_file,
            "is_playlist_mode": audio_service.is_playlist_mode,
            "playlist_position": audio_service.playlist_position,
        },
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
