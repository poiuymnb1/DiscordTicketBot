"""Утилиты безопасности и rate limiting."""
import asyncio
import time
import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory rate limiter с автоматической очисткой устаревших записей."""

    CLEANUP_THRESHOLD = 5000  # Запускать очистку каждые N проверок

    def __init__(self, max_actions: int = 5, window_seconds: int = 10):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self._user_actions: dict[int, list[float]] = defaultdict(list)
        self._check_counter = 0  # Счётчик для периодической очистки

    def _cleanup_old_entries(self) -> None:
        """Очищает записи старше window_seconds для всех пользователей."""
        now = time.time()
        window_start = now - self.window_seconds

        # Фильтруем все записи
        cutoff = now - self.window_seconds * 2  # Удаляем даже чуть раньше окна
        keys_to_delete = []

        for user_id, timestamps in self._user_actions.items():
            self._user_actions[user_id] = [t for t in timestamps if t > cutoff]
            if not self._user_actions[user_id]:
                keys_to_delete.append(user_id)

        # Удаляем пустые ключи
        for user_id in keys_to_delete:
            del self._user_actions[user_id]

        logger.debug(f"RateLimiter cleanup: removed {len(keys_to_delete)} stale entries")

    def is_allowed(self, user_id: int) -> bool:
        """Проверяет, может ли пользователь совершить действие."""
        now = time.time()
        window_start = now - self.window_seconds

        # Периодическая очистка
        self._check_counter += 1
        if self._check_counter >= self.CLEANUP_THRESHOLD:
            self._cleanup_old_entries()
            self._check_counter = 0

        # Очищаем старые записи для конкретного пользователя
        self._user_actions[user_id] = [
            t for t in self._user_actions[user_id] if t > window_start
        ]

        if len(self._user_actions[user_id]) >= self.max_actions:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False

        self._user_actions[user_id].append(now)
        return True

    def get_remaining(self, user_id: int) -> int:
        """Сколько действий осталось у пользователя."""
        now = time.time()
        window_start = now - self.window_seconds
        self._user_actions[user_id] = [
            t for t in self._user_actions[user_id] if t > window_start
        ]
        return max(0, self.max_actions - len(self._user_actions[user_id]))


# Глобальный rate limiter для создания тикетов
# 5 тикетов за 10 секунд с одного аккаунта
ticket_rate_limiter = RateLimiter(max_actions=5, window_seconds=10)


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Очищает текст от потенциально опасных символов."""
    if not text:
        return ""

    # Discord сам экранирует HTML в embeds, но ограничим длину
    result = text[:max_length]

    # Убираем нуль-символы и другие проблемные символы
    result = result.replace("\x00", "")

    return result.strip()


def truncate_text(text: str, max_length: int = 1024) -> str:
    """Обрезает текст с многоточием."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."