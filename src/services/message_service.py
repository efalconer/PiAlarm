"""Message service for PiAlarm - manages user messages with JSON persistence."""

import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.config import DATA_DIR
from src.services.time_service import get_time_service

logger = logging.getLogger(__name__)

MESSAGES_FILE = DATA_DIR / "messages.json"


@dataclass
class Message:
    """Represents a user message."""

    id: str
    text: str
    created_at: str
    read: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Message":
        """Create Message from dictionary."""
        return Message(
            id=data["id"],
            text=data["text"],
            created_at=data["created_at"],
            read=data["read"],
        )


class MessageService:
    """Manages messages with JSON file persistence."""

    def __init__(self):
        self.time_service = get_time_service()
        self._messages: list[Message] = []
        self._load()

    def _load(self) -> None:
        """Load messages from JSON file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if MESSAGES_FILE.exists():
            try:
                with open(MESSAGES_FILE) as f:
                    data = json.load(f)
                    self._messages = [Message.from_dict(m) for m in data]
                logger.info(f"Loaded {len(self._messages)} messages")
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to load messages: {e}")
                self._messages = []
        else:
            self._messages = []

    def _save(self) -> None:
        """Save messages to JSON file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MESSAGES_FILE, "w") as f:
            json.dump([m.to_dict() for m in self._messages], f, indent=2)

    def get_all_messages(self) -> list[Message]:
        """Get all messages (for web UI)."""
        return sorted(self._messages, key=lambda m: m.created_at, reverse=True)

    def get_unread_messages(self) -> list[Message]:
        """Get all unread messages."""
        return [m for m in self._messages if not m.read]

    def has_unread(self) -> bool:
        """Quick check if there are any unread messages."""
        return any(not m.read for m in self._messages)

    def get_next_unread(self) -> Optional[Message]:
        """Get the next unread message (oldest first)."""
        unread = [m for m in self._messages if not m.read]
        if not unread:
            return None
        # Return oldest unread message
        return sorted(unread, key=lambda m: m.created_at)[0]

    def get_recent_messages(self, days: int = 2) -> list[Message]:
        """Get all messages created within the last N days, oldest first."""
        cutoff = self.time_service.now().replace(tzinfo=None) - timedelta(days=days)
        recent = [
            m for m in self._messages
            if datetime.fromisoformat(m.created_at).replace(tzinfo=None) >= cutoff
        ]
        return sorted(recent, key=lambda m: m.created_at)

    def create_message(self, text: str) -> Message:
        """Create a new message."""
        message = Message(
            id=str(uuid.uuid4()),
            text=text.strip(),
            created_at=self.time_service.now().isoformat(),
            read=False,
        )
        self._messages.append(message)
        self._save()
        logger.info(f"Created message: {message.id}")
        return message

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        for message in self._messages:
            if message.id == message_id:
                message.read = True
                self._save()
                logger.info(f"Marked message as read: {message_id}")
                return True
        return False

    def delete_message(self, message_id: str) -> bool:
        """Delete a message."""
        for i, message in enumerate(self._messages):
            if message.id == message_id:
                del self._messages[i]
                self._save()
                logger.info(f"Deleted message: {message_id}")
                return True
        return False

    def get_by_id(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        for message in self._messages:
            if message.id == message_id:
                return message
        return None


# Global instance
_message_service: MessageService | None = None


def get_message_service() -> MessageService:
    """Get the global message service instance."""
    global _message_service
    if _message_service is None:
        _message_service = MessageService()
    return _message_service
