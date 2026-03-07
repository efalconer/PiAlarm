"""Audio service for PiAlarm - handles MP3 playback via I2S."""

import json
import logging
import os
import threading
import time
from pathlib import Path

import pygame

from src.config import MUSIC_DIR

logger = logging.getLogger(__name__)


class AudioService:
    """Manages audio playback for alarm sounds and music."""

    def __init__(self):
        self._lock = threading.Lock()
        self._initialized = False
        self._current_file: str | None = None
        self._volume = 1.0
        self._playlist: list[str] = []
        self._playlist_index = 0
        self._playlist_mode = False
        self._paused = False
        self._duration_cache: dict[str, int | None] = {}
        self._track_started_at: float = 0
        self._metadata: dict[str, dict] = {}
        self._metadata_loaded = False

    def initialize(self) -> bool:
        """Initialize pygame mixer for audio playback."""
        if self._initialized:
            return True

        # Force SDL to use ALSA so it routes through the dmix chain in
        # /etc/asound.conf rather than falling back to a dummy driver.
        os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
            self._initialized = True
            logger.info("Audio service initialized")
            return True
        except pygame.error as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown audio service."""
        with self._lock:
            if self._initialized:
                self._stop_locked()
                pygame.mixer.quit()
                self._initialized = False
                logger.info("Audio service shutdown")

    def _metadata_path(self) -> Path:
        return MUSIC_DIR / "metadata.json"

    def _load_metadata(self) -> None:
        """Load per-file metadata from disk (idempotent)."""
        if self._metadata_loaded:
            return
        path = self._metadata_path()
        if path.exists():
            try:
                self._metadata = json.loads(path.read_text())
            except Exception:
                self._metadata = {}
        self._metadata_loaded = True

    def _save_metadata(self) -> None:
        """Persist per-file metadata to disk."""
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        self._metadata_path().write_text(json.dumps(self._metadata, indent=2))

    def is_alarm_only(self, filename: str) -> bool:
        """Return True if the file is flagged as alarm-only."""
        self._load_metadata()
        return bool(self._metadata.get(filename, {}).get("alarm_only", False))

    def set_alarm_only(self, filename: str, value: bool) -> None:
        """Set or clear the alarm-only flag for a file."""
        with self._lock:
            self._load_metadata()
            if value:
                self._metadata.setdefault(filename, {})["alarm_only"] = True
            else:
                entry = self._metadata.get(filename, {})
                entry.pop("alarm_only", None)
                if not entry:
                    self._metadata.pop(filename, None)
                else:
                    self._metadata[filename] = entry
            self._save_metadata()

    def get_available_sounds(self, exclude_alarm_only: bool = False) -> list[str]:
        """Get list of available audio files (MP3 and WAV).

        Args:
            exclude_alarm_only: When True, omit files flagged as alarm-only.
        """
        if not MUSIC_DIR.exists():
            return []
        files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))
        names = sorted([f.name for f in files])
        if exclude_alarm_only:
            self._load_metadata()
            names = [n for n in names if not self._metadata.get(n, {}).get("alarm_only", False)]
        return names

    def play(self, filename: str, loop: bool = True) -> bool:
        """Play an MP3 file. Returns True if successful."""
        with self._lock:
            if not self._initialized and not self.initialize():
                return False

            filepath = MUSIC_DIR / filename
            if not filepath.exists():
                logger.error(f"Audio file not found: {filepath}")
                return False

            try:
                self._playlist_mode = False
                pygame.mixer.music.load(str(filepath))
                pygame.mixer.music.set_volume(self._volume)
                loops = -1 if loop else 0
                pygame.mixer.music.play(loops=loops)
                self._current_file = filename
                logger.info(f"Playing: {filename}")
                return True
            except pygame.error as e:
                logger.error(f"Failed to play {filename}: {e}")
                return False

    def play_playlist(self, tracks: list[str], start_index: int = 0) -> bool:
        """Play a playlist of tracks."""
        with self._lock:
            if not tracks:
                return False

            if not self._initialized and not self.initialize():
                return False

            self._playlist = tracks
            self._playlist_index = start_index
            self._playlist_mode = True

            return self._play_current_track()

    def _play_current_track(self) -> bool:
        """Play the current track in the playlist, skipping unplayable tracks."""
        while self._playlist and self._playlist_index < len(self._playlist):
            filename = self._playlist[self._playlist_index]
            filepath = MUSIC_DIR / filename

            if not filepath.exists():
                logger.warning(f"Track not found, skipping: {filename}")
                self._playlist_index += 1
                continue

            try:
                pygame.mixer.music.load(str(filepath))
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play()
                self._current_file = filename
                self._track_started_at = time.time()
                logger.info(f"Playing track {self._playlist_index + 1}/{len(self._playlist)}: {filename}")
                return True
            except pygame.error as e:
                logger.error(f"Failed to play {filename}: {e}")
                self._playlist_index += 1

        logger.info("Playlist finished (no playable tracks remaining)")
        self._playlist_mode = False
        self._current_file = None
        return False

    def next_track(self) -> bool:
        """Skip to next track in playlist."""
        with self._lock:
            if not self._playlist_mode or not self._playlist:
                return False

            self._playlist_index += 1
            return self._play_current_track()

    def previous_track(self) -> bool:
        """Go to previous track in playlist."""
        with self._lock:
            if not self._playlist_mode or not self._playlist:
                return False

            self._playlist_index = max(0, self._playlist_index - 1)
            return self._play_current_track()

    def check_playlist_advance(self) -> None:
        """Check if we need to advance to the next track. Call this periodically."""
        if not self._playlist_mode or not self._initialized:
            return

        if not pygame.mixer.music.get_busy() and not self._paused and time.time() - self._track_started_at > 3:
            with self._lock:
                if not self._playlist_mode or not self._playlist:
                    return
                self._playlist_index += 1
                self._play_current_track()

    def stop(self) -> None:
        """Stop current playback."""
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        """Stop current playback (must be called with _lock held)."""
        if self._initialized:
            pygame.mixer.music.stop()
            logger.info("Playback stopped")
        self._current_file = None
        self._playlist_mode = False
        self._playlist = []
        self._paused = False

    def pause(self) -> None:
        """Pause current playback."""
        with self._lock:
            self._pause_locked()

    def _pause_locked(self) -> None:
        """Pause current playback (must be called with _lock held)."""
        if self._initialized and self.is_playing():
            pygame.mixer.music.pause()
            self._paused = True
            logger.info("Playback paused")

    def unpause(self) -> None:
        """Resume paused playback."""
        with self._lock:
            self._unpause_locked()

    def _unpause_locked(self) -> None:
        """Resume paused playback (must be called with _lock held)."""
        if self._initialized and self._paused:
            pygame.mixer.music.unpause()
            self._paused = False
            logger.info("Playback resumed")

    def toggle_pause(self) -> bool:
        """Toggle pause state. Returns new paused state."""
        with self._lock:
            if self._paused:
                self._unpause_locked()
            else:
                self._pause_locked()
            return self._paused

    @property
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._paused

    def is_playing(self) -> bool:
        """Check if audio is currently playing (not paused)."""
        if not self._initialized:
            return False
        return pygame.mixer.music.get_busy()

    def has_active_playback(self) -> bool:
        """Check if there's active playback (playing or paused)."""
        return self._current_file is not None

    def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        if self._initialized:
            pygame.mixer.music.set_volume(self._volume)

    def get_volume(self) -> float:
        """Get current volume level."""
        return self._volume

    @property
    def current_file(self) -> str | None:
        """Get currently playing file name."""
        return self._current_file

    @property
    def is_playlist_mode(self) -> bool:
        """Check if currently playing a playlist."""
        return self._playlist_mode

    @property
    def playlist_position(self) -> tuple[int, int]:
        """Get current playlist position (current_index, total_tracks)."""
        return (self._playlist_index + 1, len(self._playlist))

    def get_position_ms(self) -> int:
        """Get current playback position in milliseconds."""
        if not self._initialized:
            return 0
        return max(0, pygame.mixer.music.get_pos())

    def get_track_duration_ms(self, filename: str | None = None) -> int | None:
        """Get duration of a track in milliseconds using mutagen (if available)."""
        target = filename or self._current_file
        if not target:
            return None

        if target in self._duration_cache:
            return self._duration_cache[target]

        filepath = MUSIC_DIR / target
        if not filepath.exists():
            return None

        duration_ms = None
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(filepath))
            if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length"):
                duration_ms = int(audio.info.length * 1000)
        except Exception as e:
            logger.debug(f"Could not read duration for {target}: {e}")

        self._duration_cache[target] = duration_ms
        return duration_ms

    def delete_file(self, filename: str) -> bool:
        """Delete an MP3 file."""
        filepath = MUSIC_DIR / filename
        if not filepath.exists():
            return False

        with self._lock:
            # Stop if currently playing this file
            if self._current_file == filename:
                self._stop_locked()

        try:
            os.remove(filepath)
            logger.info(f"Deleted: {filename}")
            self._load_metadata()
            if filename in self._metadata:
                del self._metadata[filename]
                self._save_metadata()
            return True
        except OSError as e:
            logger.error(f"Failed to delete {filename}: {e}")
            return False


# Global instance
_audio_service: AudioService | None = None


def get_audio_service() -> AudioService:
    """Get the global audio service instance."""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
