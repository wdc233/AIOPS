"""Lane Lock for serial execution on same target server."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)


class LaneLock:
    """Lane lock to prevent concurrent SSH storms on the same target server."""

    def __init__(self) -> None:
        """Initialize lane lock."""
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()

    async def acquire(self, target: str) -> asyncio.Lock:
        """Acquire lock for a target server.

        Args:
            target: Target server IP or identifier

        Returns:
            asyncio.Lock for the target
        """
        async with self._lock_creation_lock:
            if target not in self._locks:
                self._locks[target] = asyncio.Lock()
            return self._locks[target]

    @asynccontextmanager
    async def lock(self, target: str) -> AsyncGenerator[None, None]:
        """Context manager for locking a target server.

        Args:
            target: Target server IP or identifier

        Yields:
            None
        """
        lock = await self.acquire(target)
        async with lock:
            logger.debug(f"Acquired lock for target: {target}")
            try:
                yield
            finally:
                logger.debug(f"Released lock for target: {target}")

    async def execute_with_lock(
        self,
        target: str,
        coro: Any,
    ) -> Any:
        """Execute a coroutine with lane lock.

        Args:
            target: Target server IP or identifier
            coro: Coroutine to execute

        Returns:
            Result of coroutine
        """
        async with self.lock(target):
            return await coro

    def get_locked_targets(self) -> list[str]:
        """Get list of currently locked targets."""
        return [target for target, lock in self._locks.items() if lock.locked()]

    async def unlock_all(self) -> None:
        """Force unlock all targets (for emergency use)."""
        for target, lock in self._locks.items():
            if lock.locked():
                try:
                    # Note: This is a workaround - can't truly unlock from outside
                    # but we clear the reference
                    logger.warning(f"Force clearing lock for target: {target}")
                except Exception as e:
                    logger.error(f"Failed to clear lock for {target}: {e}")
        self._locks.clear()


# Global lane lock instance
_lane_lock: Optional[LaneLock] = None


def get_lane_lock() -> LaneLock:
    """Get global lane lock instance."""
    global _lane_lock
    if _lane_lock is None:
        _lane_lock = LaneLock()
    return _lane_lock