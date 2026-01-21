"""Sprite service for PiAlarm - manages custom dog sprites with JSON persistence."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

SPRITES_FILE = DATA_DIR / "sprites.json"


@dataclass
class TimeRange:
    """Represents a time range when a sprite should be active."""
    start: int  # Hour 0-23, inclusive
    end: int    # Hour 0-24, exclusive (24 allows midnight-crossing ranges)

    def contains(self, hour: int) -> bool:
        """Check if the given hour falls within this time range."""
        if self.start <= self.end:
            return self.start <= hour < self.end
        else:
            # Handles midnight-crossing (e.g., start=22, end=6)
            return hour >= self.start or hour < self.end

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: dict) -> "TimeRange":
        return cls(start=data["start"], end=data["end"])


@dataclass
class Sprite:
    """Represents a dog sprite."""
    id: str
    name: str
    pixels: list[tuple[int, int]]  # List of (x, y) coordinates
    time_ranges: list[TimeRange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pixels": [[x, y] for x, y in self.pixels],
            "time_ranges": [tr.to_dict() for tr in self.time_ranges],
        }

    @classmethod
    def from_dict(cls, sprite_id: str, data: dict) -> "Sprite":
        pixels = [tuple(p) for p in data.get("pixels", [])]
        time_ranges = [TimeRange.from_dict(tr) for tr in data.get("time_ranges", [])]
        return cls(
            id=sprite_id,
            name=data.get("name", sprite_id),
            pixels=pixels,
            time_ranges=time_ranges,
        )

    def is_active_at(self, hour: int) -> bool:
        """Check if this sprite should be active at the given hour."""
        return any(tr.contains(hour) for tr in self.time_ranges)


class SpriteService:
    """Manages sprites with JSON persistence."""

    def __init__(self):
        self._sprites: dict[str, Sprite] = {}
        self._default_activity: str = "sleeping"
        self._version: int = 1
        self._load()

    def _load(self) -> None:
        """Load sprites from JSON file."""
        if not SPRITES_FILE.exists():
            logger.info("No sprites file found, starting with empty sprite set")
            return

        try:
            with open(SPRITES_FILE) as f:
                data = json.load(f)

            self._version = data.get("version", 1)
            self._default_activity = data.get("default_activity", "sleeping")

            sprites_data = data.get("sprites", {})
            for sprite_id, sprite_data in sprites_data.items():
                self._sprites[sprite_id] = Sprite.from_dict(sprite_id, sprite_data)

            logger.info(f"Loaded {len(self._sprites)} sprites")
        except Exception as e:
            logger.error(f"Failed to load sprites: {e}")
            self._sprites = {}

    def _save(self) -> None:
        """Save sprites to JSON file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self._version,
            "default_activity": self._default_activity,
            "sprites": {
                sprite_id: sprite.to_dict()
                for sprite_id, sprite in self._sprites.items()
            },
        }

        try:
            with open(SPRITES_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self._sprites)} sprites")
        except Exception as e:
            logger.error(f"Failed to save sprites: {e}")

    def get_all(self) -> list[Sprite]:
        """Get all sprites."""
        return list(self._sprites.values())

    def get_by_id(self, sprite_id: str) -> Sprite | None:
        """Get a sprite by its ID."""
        return self._sprites.get(sprite_id)

    def create(self, sprite: Sprite) -> Sprite:
        """Create a new sprite."""
        # Generate ID from name if not provided or already exists
        base_id = sprite.id or self._slugify(sprite.name)
        sprite_id = base_id
        counter = 1
        while sprite_id in self._sprites:
            sprite_id = f"{base_id}_{counter}"
            counter += 1

        sprite.id = sprite_id
        self._sprites[sprite_id] = sprite
        self._save()
        logger.info(f"Created sprite: {sprite_id}")
        return sprite

    def update(self, sprite: Sprite) -> bool:
        """Update an existing sprite."""
        if sprite.id not in self._sprites:
            return False

        self._sprites[sprite.id] = sprite
        self._save()
        logger.info(f"Updated sprite: {sprite.id}")
        return True

    def delete(self, sprite_id: str) -> bool:
        """Delete a sprite."""
        if sprite_id not in self._sprites:
            return False

        del self._sprites[sprite_id]
        self._save()
        logger.info(f"Deleted sprite: {sprite_id}")
        return True

    def get_active_sprite(self, hour: int) -> Sprite | None:
        """Get the sprite that should be active at the given hour.

        Returns the first matching sprite based on time ranges.
        """
        for sprite in self._sprites.values():
            if sprite.is_active_at(hour):
                return sprite
        return None

    def get_sprite_pixels(self, sprite_id: str) -> list[tuple[int, int]] | None:
        """Get pixel coordinates for a sprite."""
        sprite = self.get_by_id(sprite_id)
        return sprite.pixels if sprite else None

    @property
    def default_activity(self) -> str:
        """Get the default activity name."""
        return self._default_activity

    @default_activity.setter
    def default_activity(self, value: str) -> None:
        """Set the default activity name."""
        self._default_activity = value
        self._save()

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a name to a URL-safe ID."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '_', slug)
        return slug.strip('_') or "sprite"


# Global instance
_sprite_service: SpriteService | None = None


def get_sprite_service() -> SpriteService:
    """Get the global sprite service instance."""
    global _sprite_service
    if _sprite_service is None:
        _sprite_service = SpriteService()
    return _sprite_service
