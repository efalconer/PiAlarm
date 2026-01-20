"""Audio service for PiAlarm - handles MP3 playback via I2S."""

import logging
import os
from pathlib import Path

import pygame

from src.config import MUSIC_DIR

logger = logging.getLogger(__name__)


class AudioService:
    """Manages audio playback for alarm sounds and music."""

    def __init__(self):
        self._initialized = False
        self._current_file: str | None = None
        self._volume = 1.0
        self._playlist: list[str] = []
        self._playlist_index = 0
        self._playlist_mode = False

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
        if not tracks:
            return False

        if not self._initialized and not self.initialize():
            return False

        self._playlist = tracks
        self._playlist_index = start_index
        self._playlist_mode = True

        # Set up end event for playlist advancement
        pygame.mixer.music.set_endevent(pygame.USEREVENT)

        return self._play_current_track()

    def _play_current_track(self) -> bool:
        """Play the current track in the playlist."""
        if not self._playlist or self._playlist_index >= len(self._playlist):
            self._playlist_mode = False
            return False

        filename = self._playlist[self._playlist_index]
        filepath = MUSIC_DIR / filename

        if not filepath.exists():
            logger.warning(f"Track not found, skipping: {filename}")
            return self.next_track()

        try:
            pygame.mixer.music.load(str(filepath))
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play()
            self._current_file = filename
            logger.info(f"Playing track {self._playlist_index + 1}/{len(self._playlist)}: {filename}")
            return True
        except pygame.error as e:
            logger.error(f"Failed to play {filename}: {e}")
            return self.next_track()

    def next_track(self) -> bool:
        """Skip to next track in playlist."""
        if not self._playlist_mode or not self._playlist:
            return False

        self._playlist_index += 1
        if self._playlist_index >= len(self._playlist):
            logger.info("Playlist finished")
            self._playlist_mode = False
            self._current_file = None
            return False

        return self._play_current_track()

    def previous_track(self) -> bool:
        """Go to previous track in playlist."""
        if not self._playlist_mode or not self._playlist:
            return False

        self._playlist_index = max(0, self._playlist_index - 1)
        return self._play_current_track()

    def check_playlist_advance(self) -> None:
        """Check if we need to advance to the next track. Call this periodically."""
        if not self._playlist_mode:
            return

        for event in pygame.event.get():
            if event.type == pygame.USEREVENT:
                self.next_track()

    def stop(self) -> None:
        """Stop current playback."""
        if self._initialized and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            logger.info("Playback stopped")
        self._current_file = None
        self._playlist_mode = False
        self._playlist = []

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

    @property
    def is_playlist_mode(self) -> bool:
        """Check if currently playing a playlist."""
        return self._playlist_mode

    @property
    def playlist_position(self) -> tuple[int, int]:
        """Get current playlist position (current_index, total_tracks)."""
        return (self._playlist_index + 1, len(self._playlist))

    def delete_file(self, filename: str) -> bool:
        """Delete an MP3 file."""
        filepath = MUSIC_DIR / filename
        if not filepath.exists():
            return False

        # Stop if currently playing this file
        if self._current_file == filename:
            self.stop()

        try:
            os.remove(filepath)
            logger.info(f"Deleted: {filename}")
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
