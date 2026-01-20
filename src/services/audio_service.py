"""Audio service for PiAlarm - handles MP3 playback via I2S."""

import logging
from pathlib import Path

import pygame

from src.config import MUSIC_DIR

logger = logging.getLogger(__name__)


class AudioService:
    """Manages audio playback for alarm sounds."""

    def __init__(self):
        self._initialized = False
        self._current_file: str | None = None
        self._volume = 1.0

    def initialize(self) -> bool:
        """Initialize pygame mixer for audio playback."""
        if self._initialized:
            return True

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
        if self._initialized:
            self.stop()
            pygame.mixer.quit()
            self._initialized = False
            logger.info("Audio service shutdown")

    def get_available_sounds(self) -> list[str]:
        """Get list of available MP3 files."""
        if not MUSIC_DIR.exists():
            return []
        return sorted([f.name for f in MUSIC_DIR.glob("*.mp3")])

    def play(self, filename: str, loop: bool = True) -> bool:
        """Play an MP3 file. Returns True if successful."""
        if not self._initialized and not self.initialize():
            return False

        filepath = MUSIC_DIR / filename
        if not filepath.exists():
            logger.error(f"Audio file not found: {filepath}")
            return False

        try:
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

    def stop(self) -> None:
        """Stop current playback."""
        if self._initialized and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            logger.info("Playback stopped")
        self._current_file = None

    def pause(self) -> None:
        """Pause current playback."""
        if self._initialized:
            pygame.mixer.music.pause()
            logger.info("Playback paused")

    def unpause(self) -> None:
        """Resume paused playback."""
        if self._initialized:
            pygame.mixer.music.unpause()
            logger.info("Playback resumed")

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        if not self._initialized:
            return False
        return pygame.mixer.music.get_busy()

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


# Global instance
_audio_service: AudioService | None = None


def get_audio_service() -> AudioService:
    """Get the global audio service instance."""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService()
    return _audio_service
