"""Playlist service for PiAlarm - manages music playlists."""

import sqlite3
import logging
from dataclasses import dataclass
from pathlib import Path

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "alarms.db"


@dataclass
class Playlist:
    """Represents a playlist."""

    id: int | None
    name: str
    tracks: list[str]  # List of MP3 filenames

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "tracks": self.tracks,
            "track_count": len(self.tracks),
        }


class PlaylistService:
    """Manages playlists with SQLite persistence."""

    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    track_filename TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def _get_tracks(self, conn: sqlite3.Connection, playlist_id: int) -> list[str]:
        """Get tracks for a playlist."""
        cursor = conn.execute(
            "SELECT track_filename FROM playlist_tracks WHERE playlist_id = ? ORDER BY position",
            (playlist_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def _row_to_playlist(self, conn: sqlite3.Connection, row: tuple) -> Playlist:
        """Convert database row to Playlist object."""
        playlist_id = row[0]
        return Playlist(
            id=playlist_id,
            name=row[1],
            tracks=self._get_tracks(conn, playlist_id),
        )

    def get_all(self) -> list[Playlist]:
        """Get all playlists."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT id, name FROM playlists ORDER BY name")
            return [self._row_to_playlist(conn, row) for row in cursor.fetchall()]

    def get_by_id(self, playlist_id: int) -> Playlist | None:
        """Get playlist by ID."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT id, name FROM playlists WHERE id = ?",
                (playlist_id,),
            )
            row = cursor.fetchone()
            return self._row_to_playlist(conn, row) if row else None

    def create(self, playlist: Playlist) -> Playlist:
        """Create a new playlist."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO playlists (name) VALUES (?)",
                (playlist.name,),
            )
            playlist.id = cursor.lastrowid
            self._save_tracks(conn, playlist.id, playlist.tracks)
            conn.commit()
        logger.info(f"Created playlist: {playlist.name}")
        return playlist

    def update(self, playlist: Playlist) -> bool:
        """Update an existing playlist."""
        if playlist.id is None:
            return False
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE playlists SET name = ? WHERE id = ?",
                (playlist.name, playlist.id),
            )
            # Delete existing tracks and re-add
            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist.id,))
            self._save_tracks(conn, playlist.id, playlist.tracks)
            conn.commit()
        logger.info(f"Updated playlist: {playlist.name}")
        return True

    def _save_tracks(self, conn: sqlite3.Connection, playlist_id: int, tracks: list[str]) -> None:
        """Save tracks for a playlist."""
        for position, filename in enumerate(tracks):
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_filename, position) VALUES (?, ?, ?)",
                (playlist_id, filename, position),
            )

    def delete(self, playlist_id: int) -> bool:
        """Delete a playlist."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
            cursor = conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted playlist: {playlist_id}")
        return deleted

    def add_track(self, playlist_id: int, filename: str) -> bool:
        """Add a track to the end of a playlist."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT MAX(position) FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            )
            max_pos = cursor.fetchone()[0]
            next_pos = (max_pos or 0) + 1
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_filename, position) VALUES (?, ?, ?)",
                (playlist_id, filename, next_pos),
            )
            conn.commit()
        return True

    def remove_track(self, playlist_id: int, filename: str) -> bool:
        """Remove a track from a playlist."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_filename = ?",
                (playlist_id, filename),
            )
            conn.commit()
            return cursor.rowcount > 0


# Global instance
_playlist_service: PlaylistService | None = None


def get_playlist_service() -> PlaylistService:
    """Get the global playlist service instance."""
    global _playlist_service
    if _playlist_service is None:
        _playlist_service = PlaylistService()
    return _playlist_service
