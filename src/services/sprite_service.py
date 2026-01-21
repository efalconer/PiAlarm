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
        """Load sprites from JSON file, initializing with defaults if needed."""
        if not SPRITES_FILE.exists():
            logger.info("No sprites file found, initializing with default sprites")
            self._initialize_defaults()
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

    def _initialize_defaults(self) -> None:
        """Initialize with default sprites."""
        defaults = self._get_default_sprites()
        for sprite in defaults:
            self._sprites[sprite.id] = sprite
        self._save()
        logger.info(f"Initialized {len(defaults)} default sprites")

    def _get_default_sprites(self) -> list[Sprite]:
        """Get the default hardcoded sprites with their time ranges."""
        return [
            Sprite(
                id="sleeping",
                name="Sleeping",
                time_ranges=[TimeRange(20, 24), TimeRange(0, 6)],
                pixels=[
                    # Curled body outline
                    *[(i, 14) for i in range(8, 20)],
                    *[(i, 15) for i in range(7, 21)],
                    (6, 16), (21, 16),
                    (5, 17), (22, 17),
                    (5, 18), (22, 18),
                    (5, 19), (22, 19),
                    *[(i, 20) for i in range(5, 23)],
                    *[(i, 21) for i in range(6, 22)],
                    # Head tucked in
                    *[(i, 16) for i in range(8, 14)],
                    *[(i, 17) for i in range(8, 13)],
                    *[(i, 18) for i in range(9, 12)],
                    # Ear
                    (7, 13), (8, 13), (7, 14), (8, 14),
                    # Tail curl
                    (20, 17), (21, 16), (22, 15), (23, 14),
                    # Closed eye (line)
                    (9, 16), (10, 16), (11, 16),
                    # Zzz
                    *[(i, 5) for i in range(22, 27)],
                    (26, 6), (25, 7), (24, 8),
                    *[(i, 9) for i in range(22, 27)],
                ],
            ),
            Sprite(
                id="coffee",
                name="Coffee",
                time_ranges=[TimeRange(6, 8)],
                pixels=[
                    # Left ear
                    (5, 2), (6, 2), (7, 2), (5, 3), (6, 3), (7, 3), (6, 4), (7, 4),
                    # Right ear
                    (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (16, 3), (14, 4), (15, 4),
                    # Head
                    *[(i, 5) for i in range(6, 16)],
                    *[(i, 6) for i in range(5, 17)],
                    *[(i, 7) for i in range(5, 17)],
                    (5, 8), (6, 8), (15, 8), (16, 8),
                    *[(i, 9) for i in range(6, 16)],
                    *[(i, 10) for i in range(7, 15)],
                    # Eyes
                    (8, 7), (9, 7), (12, 7), (13, 7),
                    # Nose
                    (10, 8), (11, 8), (10, 9), (11, 9),
                    # Body
                    *[(i, 11) for i in range(7, 15)],
                    *[(i, 12) for i in range(6, 16)],
                    *[(i, 13) for i in range(6, 16)],
                    *[(i, 14) for i in range(6, 16)],
                    # Legs
                    (6, 15), (7, 15), (8, 15), (13, 15), (14, 15), (15, 15),
                    (6, 16), (7, 16), (8, 16), (13, 16), (14, 16), (15, 16),
                    (6, 17), (7, 17), (14, 17), (15, 17),
                    # Coffee mug
                    *[(i, 11) for i in range(18, 24)],
                    (18, 12), (23, 12), (25, 12), (26, 12),
                    (18, 13), (23, 13), (26, 13),
                    (18, 14), (23, 14), (26, 14),
                    (18, 15), (23, 15), (25, 15), (26, 15),
                    *[(i, 16) for i in range(18, 24)],
                    # Steam
                    (20, 7), (21, 8), (20, 9), (22, 8), (21, 9),
                ],
            ),
            Sprite(
                id="walking",
                name="Walking",
                time_ranges=[TimeRange(8, 10)],
                pixels=[
                    # Left ear
                    (3, 3), (4, 3), (5, 3), (4, 4), (5, 4), (5, 5),
                    # Right ear
                    (13, 3), (14, 3), (15, 3), (13, 4), (14, 4), (13, 5),
                    # Head
                    *[(i, 6) for i in range(5, 14)],
                    *[(i, 7) for i in range(4, 15)],
                    *[(i, 8) for i in range(4, 15)],
                    (4, 9), (5, 9), (13, 9), (14, 9),
                    *[(i, 10) for i in range(5, 14)],
                    # Eyes
                    (6, 8), (7, 8), (11, 8), (12, 8),
                    # Nose
                    (9, 9), (10, 9),
                    # Body
                    *[(i, 11) for i in range(6, 18)],
                    *[(i, 12) for i in range(6, 18)],
                    *[(i, 13) for i in range(6, 18)],
                    *[(i, 14) for i in range(6, 18)],
                    # Backpack
                    *[(i, 10) for i in range(16, 22)],
                    (16, 11), (21, 11),
                    (16, 12), (21, 12),
                    (16, 13), (21, 13),
                    *[(i, 14) for i in range(16, 22)],
                    # Walking legs
                    (5, 15), (6, 15), (15, 15), (16, 15),
                    (4, 16), (5, 16), (16, 16), (17, 16),
                    (3, 17), (4, 17), (17, 17), (18, 17),
                    (3, 18), (18, 18),
                    # Tail up
                    (17, 9), (18, 8), (19, 7), (20, 6),
                ],
            ),
            Sprite(
                id="school",
                name="School",
                time_ranges=[TimeRange(10, 14)],
                pixels=[
                    # Left ear
                    (5, 1), (6, 1), (7, 1), (6, 2), (7, 2), (7, 3),
                    # Right ear
                    (14, 1), (15, 1), (16, 1), (14, 2), (15, 2), (14, 3),
                    # Head
                    *[(i, 4) for i in range(6, 16)],
                    *[(i, 5) for i in range(5, 17)],
                    *[(i, 6) for i in range(5, 17)],
                    (5, 7), (6, 7), (15, 7), (16, 7),
                    *[(i, 8) for i in range(6, 16)],
                    # Eyes (looking down)
                    (8, 7), (9, 7), (12, 7), (13, 7),
                    # Nose
                    (10, 7), (11, 7),
                    # Body at desk
                    *[(i, 9) for i in range(6, 16)],
                    *[(i, 10) for i in range(6, 16)],
                    *[(i, 11) for i in range(6, 16)],
                    # Desk surface
                    *[(i, 12) for i in range(2, 26)],
                    *[(i, 13) for i in range(2, 26)],
                    # Desk legs
                    (2, 14), (3, 14), (24, 14), (25, 14),
                    (2, 15), (3, 15), (24, 15), (25, 15),
                    (2, 16), (3, 16), (24, 16), (25, 16),
                    (2, 17), (3, 17), (24, 17), (25, 17),
                    # Book on desk
                    *[(i, 11) for i in range(8, 14)],
                    # Paws on desk
                    (6, 11), (7, 11), (14, 11), (15, 11),
                ],
            ),
            Sprite(
                id="homework",
                name="Homework",
                time_ranges=[TimeRange(14, 17)],
                pixels=[
                    # Left ear
                    (5, 2), (6, 2), (7, 2), (6, 3), (7, 3), (7, 4),
                    # Right ear
                    (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (14, 4),
                    # Head (looking down)
                    *[(i, 5) for i in range(6, 16)],
                    *[(i, 6) for i in range(5, 17)],
                    *[(i, 7) for i in range(5, 17)],
                    (5, 8), (6, 8), (15, 8), (16, 8),
                    *[(i, 9) for i in range(6, 16)],
                    # Eyes
                    (8, 7), (9, 7), (12, 7), (13, 7),
                    # Nose
                    (10, 8), (11, 8),
                    # Body
                    *[(i, 10) for i in range(7, 15)],
                    *[(i, 11) for i in range(6, 16)],
                    *[(i, 12) for i in range(6, 16)],
                    *[(i, 13) for i in range(6, 16)],
                    # Sitting legs
                    (6, 14), (7, 14), (8, 14), (13, 14), (14, 14), (15, 14),
                    (6, 15), (7, 15), (14, 15), (15, 15),
                    (6, 16), (7, 16), (14, 16), (15, 16),
                    # Paper
                    *[(i, 10) for i in range(18, 27)],
                    (18, 11), (26, 11),
                    (18, 12), (26, 12),
                    (18, 13), (26, 13),
                    (18, 14), (26, 14),
                    *[(i, 15) for i in range(18, 27)],
                    # Pencil in paw
                    (15, 11), (16, 10), (17, 9), (18, 8), (19, 7),
                    # Writing lines
                    (20, 11), (21, 11), (22, 11), (23, 11),
                    (20, 13), (21, 13), (22, 13),
                ],
            ),
            Sprite(
                id="dinner",
                name="Dinner",
                time_ranges=[TimeRange(17, 18)],
                pixels=[
                    # Left ear (flopped)
                    (4, 5), (5, 5), (6, 5), (5, 6), (6, 6), (6, 7),
                    # Right ear (flopped)
                    (16, 5), (17, 5), (18, 5), (16, 6), (17, 6), (16, 7),
                    # Head (down eating)
                    *[(i, 7) for i in range(7, 16)],
                    *[(i, 8) for i in range(6, 17)],
                    *[(i, 9) for i in range(6, 17)],
                    (6, 10), (7, 10), (15, 10), (16, 10),
                    *[(i, 11) for i in range(7, 16)],
                    *[(i, 12) for i in range(8, 15)],
                    # Eyes closed (happy)
                    (8, 9), (9, 9), (13, 9), (14, 9),
                    # Nose near bowl
                    (10, 11), (11, 11), (12, 11),
                    # Body
                    *[(i, 13) for i in range(9, 20)],
                    *[(i, 14) for i in range(9, 20)],
                    *[(i, 15) for i in range(9, 20)],
                    # Legs
                    (9, 16), (10, 16), (17, 16), (18, 16),
                    (9, 17), (10, 17), (17, 17), (18, 17),
                    # Tail wagging
                    (19, 13), (20, 12), (21, 13), (22, 12),
                    # Food bowl
                    *[(i, 13) for i in range(3, 10)],
                    (2, 14), (10, 14),
                    (2, 15), (10, 15),
                    *[(i, 16) for i in range(2, 11)],
                    # Food in bowl
                    *[(i, 14) for i in range(4, 9)],
                ],
            ),
            Sprite(
                id="gaming",
                name="Gaming",
                time_ranges=[TimeRange(18, 20)],
                pixels=[
                    # Left ear
                    (5, 2), (6, 2), (7, 2), (6, 3), (7, 3), (7, 4),
                    # Right ear
                    (14, 2), (15, 2), (16, 2), (14, 3), (15, 3), (14, 4),
                    # Head
                    *[(i, 5) for i in range(6, 16)],
                    *[(i, 6) for i in range(5, 17)],
                    *[(i, 7) for i in range(5, 17)],
                    (5, 8), (6, 8), (15, 8), (16, 8),
                    *[(i, 9) for i in range(6, 16)],
                    # Eyes (focused)
                    (8, 7), (9, 7), (12, 7), (13, 7),
                    # Nose
                    (10, 8), (11, 8),
                    # Tongue out
                    (10, 10), (11, 10), (10, 11), (11, 11),
                    # Body
                    *[(i, 12) for i in range(7, 15)],
                    *[(i, 13) for i in range(6, 16)],
                    *[(i, 14) for i in range(6, 16)],
                    # Sitting legs
                    (6, 15), (7, 15), (8, 15), (13, 15), (14, 15), (15, 15),
                    (6, 16), (7, 16), (14, 16), (15, 16),
                    (6, 17), (7, 17), (14, 17), (15, 17),
                    # Game controller
                    *[(i, 13) for i in range(17, 25)],
                    *[(i, 14) for i in range(17, 25)],
                    *[(i, 15) for i in range(18, 24)],
                    # Controller buttons
                    (18, 13), (19, 13), (22, 13), (23, 13),
                    # Paws holding controller
                    (15, 13), (16, 13), (15, 14), (16, 14),
                    # TV/Screen
                    *[(i, 3) for i in range(20, 29)],
                    (20, 4), (28, 4),
                    (20, 5), (28, 5),
                    (20, 6), (28, 6),
                    (20, 7), (28, 7),
                    *[(i, 8) for i in range(20, 29)],
                ],
            ),
        ]

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
