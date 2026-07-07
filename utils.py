"""Security utilities and rate limiting."""
import asyncio
import time
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory rate limiter with automatic cleanup of stale entries."""

    CLEANUP_THRESHOLD = 5000  # Run cleanup every N checks

    def __init__(self, max_actions: int = 5, window_seconds: int = 10):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._user_actions: dict[int, list[float]] = defaultdict(list)
        self._check_counter = 0  # Counter for periodic cleanup

    def _cleanup_old_entries(self) -> None:
        """Clean up entries older than window_seconds for all users."""
        now = time.time()
        window_start = now - self.window_seconds

        # Filter all entries
        cutoff = now - self.window_seconds * 2  # Remove even slightly before window
        keys_to_delete = []

        for user_id, timestamps in self._user_actions.items():
            self._user_actions[user_id] = [t for t in timestamps if t > cutoff]
            if not self._user_actions[user_id]:
                keys_to_delete.append(user_id)

        # Delete empty keys
        for user_id in keys_to_delete:
            del self._user_actions[user_id]

        logger.debug(f"RateLimiter cleanup: removed {len(keys_to_delete)} stale entries")

    def is_allowed(self, user_id: int) -> bool:
        """Check if user can perform an action."""
        now = time.time()
        window_start = now - self.window_seconds

        # Periodic cleanup
        self._check_counter += 1
        if self._check_counter >= self.CLEANUP_THRESHOLD:
            self._cleanup_old_entries()
            self._check_counter = 0

        # Clean old records for specific user
        self._user_actions[user_id] = [
            t for t in self._user_actions[user_id] if t > window_start
        ]

        if len(self._user_actions[user_id]) >= self.max_actions:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False

        self._user_actions[user_id].append(now)
        return True

    def get_remaining(self, user_id: int) -> int:
        """How many actions user has left."""
        now = time.time()
        window_start = now - self.window_seconds
        self._user_actions[user_id] = [
            t for t in self._user_actions[user_id] if t > window_start
        ]
        return max(0, self.max_actions - len(self._user_actions[user_id]))


# Global rate limiter for ticket creation
# 5 tickets per 10 seconds per account
ticket_rate_limiter = RateLimiter(max_actions=5, window_seconds=10)


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Sanitize text from potentially dangerous characters."""
    if not text:
        return ""

    # Discord escapes HTML in embeds itself, but let's limit length
    result = text[:max_length]

    # Remove null-characters and other problematic characters
    result = result.replace("\x00", "")

    return result.strip()


def truncate_text(text: str, max_length: int = 1024) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."