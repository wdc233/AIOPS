"""Scheduler for Cron and immediate execution."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from croniter import croniter

from src.config import get_settings
from src.db.repository import CommandRepository
from src.models.types import CommandStatus, InspectionCommand

logger = logging.getLogger(__name__)


class Scheduler:
    """Scheduler for Cron tasks and immediate execution."""

    def __init__(self) -> None:
        """Initialize scheduler."""
        self._settings = get_settings()
        self._command_repo = CommandRepository()
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._cron_tasks: Dict[str, InspectionCommand] = {}
        self._max_concurrent = self._settings.scheduler.max_concurrent_tasks

    async def start(self) -> None:
        """Start scheduler."""
        if self._running:
            return

        self._running = True

        # Start cron scheduler
        if self._settings.scheduler.cron_enabled:
            asyncio.create_task(self._cron_loop())

        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop scheduler."""
        self._running = False

        # Cancel all tasks
        for task in self._tasks.values():
            task.cancel()

        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

        logger.info("Scheduler stopped")

    async def schedule_command(self, command: InspectionCommand) -> str:
        """Schedule a command for execution.

        Args:
            command: Inspection command to schedule

        Returns:
            Task ID
        """
        if command.cron:
            # Add to cron tasks
            self._cron_tasks[command.command_id] = command
            logger.info(f"Command {command.command_id} scheduled with cron: {command.cron}")
        else:
            # Execute immediately
            task_id = await self._execute_now(command)
            return task_id

        return command.command_id

    async def _execute_now(self, command: InspectionCommand) -> str:
        """Execute command immediately.

        Args:
            command: Command to execute

        Returns:
            Task ID
        """
        # Check concurrent limit
        if len(self._tasks) >= self._max_concurrent:
            logger.warning("Max concurrent tasks reached, queuing command")
            # Could implement queue here

        task = asyncio.create_task(self._execute_command(command))
        self._tasks[command.command_id] = task

        # Clean up completed tasks
        task.add_done_callback(lambda t: self._tasks.pop(command.command_id, None))

        return command.command_id

    async def _execute_command(self, command: InspectionCommand) -> None:
        """Execute a command."""
        try:
            # Update status to running
            await self._command_repo.update_status(command.command_id, CommandStatus.RUNNING)

            # Execute via instruction bus
            from src.bus import get_instruction_bus
            bus = get_instruction_bus()
            await bus.execute_command(command)

            logger.info(f"Command {command.command_id} executed successfully")

        except Exception as e:
            logger.error(f"Command {command.command_id} execution failed: {e}")
            await self._command_repo.update_status(
                command.command_id,
                CommandStatus.FAILED,
                {"error": str(e)},
            )

    async def _cron_loop(self) -> None:
        """Cron scheduler loop."""
        while self._running:
            try:
                now = datetime.now()

                # Check each cron command
                for command_id, command in list(self._cron_tasks.items()):
                    if not command.cron:
                        continue

                    # Check if cron matches current time
                    cron = croniter(command.cron, now)
                    prev_run = cron.get_prev(datetime)
                    next_run = cron.get_next(datetime)

                    # If previous run was within last minute and not executed
                    if (now - prev_run).total_seconds() < 60:
                        # Check if already executed
                        existing = await self._command_repo.get_by_id(command_id)
                        if existing and existing.status == CommandStatus.PENDING:
                            logger.info(f"Executing cron command {command_id}")
                            await self._execute_now(command)

            except Exception as e:
                logger.error(f"Cron loop error: {e}")

            # Check every minute
            await asyncio.sleep(60)

    async def cancel_task(self, command_id: str) -> bool:
        """Cancel a scheduled task.

        Args:
            command_id: Command ID

        Returns:
            True if cancelled
        """
        # Cancel if running
        if command_id in self._tasks:
            self._tasks[command_id].cancel()
            del self._tasks[command_id]

        # Remove from cron tasks
        if command_id in self._cron_tasks:
            del self._cron_tasks[command_id]

        # Update status
        await self._command_repo.update_status(command_id, CommandStatus.FAILED, {"cancelled": True})

        logger.info(f"Task {command_id} cancelled")
        return True

    def get_scheduled_tasks(self) -> List[str]:
        """Get list of scheduled task IDs."""
        return list(self._cron_tasks.keys())

    def get_running_tasks(self) -> List[str]:
        """Get list of running task IDs."""
        return list(self._tasks.keys())


# Global scheduler instance
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler