"""Instruction Bus for command dispatch and state management."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.db.repository import CommandRepository
from src.models.types import (
    CommandAction,
    CommandStatus,
    InspectionCommand,
    InspectionItem,
)

logger = logging.getLogger(__name__)


class InstructionBus:
    """Instruction bus for command management with state machine."""

    def __init__(self) -> None:
        """Initialize instruction bus."""
        self._command_repo = CommandRepository()
        self._subscribers: Dict[str, List[Callable]] = {
            "pending": [],
            "running": [],
            "completed": [],
            "failed": [],
        }
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def publish_command(
        self,
        action: CommandAction,
        name: str,
        targets: List[str],
        inspection_items: Optional[List[InspectionItem]] = None,
        cron: Optional[str] = None,
        session_type: str = "isolated",
        callback_url: Optional[str] = None,
        priority: int = 1,
        created_by: Optional[str] = None,
    ) -> InspectionCommand:
        """Publish a new inspection command.

        Args:
            action: Command action
            name: Command name
            targets: Target server IPs
            inspection_items: Items to inspect
            cron: Cron expression
            session_type: Session type
            callback_url: Callback URL
            priority: Priority
            created_by: Creator

        Returns:
            Created InspectionCommand
        """
        command_id = str(uuid.uuid4())

        command = InspectionCommand(
            command_id=command_id,
            action=action,
            name=name,
            cron=cron,
            targets=targets,
            inspection_items=inspection_items or [],
            session_type=session_type,
            callback_url=callback_url,
            priority=priority,
            created_by=created_by,
            status=CommandStatus.PENDING,
        )

        # Save to database
        await self._command_repo.create(command)

        # Notify subscribers
        await self._notify_subscribers("pending", command)

        logger.info(f"Published command {command_id}: {name} with action {action}")

        # If action is run_now, execute immediately
        if action == CommandAction.RUN_NOW:
            asyncio.create_task(self._execute_command(command))

        return command

    async def update_command_status(
        self,
        command_id: str,
        status: CommandStatus,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update command status.

        Args:
            command_id: Command ID
            status: New status
            result: Execution result
        """
        async with self._lock:
            await self._command_repo.update_status(command_id, status, result)
            command = await self._command_repo.get_by_id(command_id)

            if command:
                await self._notify_subscribers(status.value, command)

            logger.info(f"Updated command {command_id} status to {status}")

    async def cancel_command(self, command_id: str) -> bool:
        """Cancel a running command.

        Args:
            command_id: Command ID

        Returns:
            True if cancelled
        """
        async with self._lock:
            # Check if command is running
            if command_id in self._active_tasks:
                task = self._active_tasks[command_id]
                task.cancel()
                del self._active_tasks[command_id]

            await self._command_repo.update_status(command_id, CommandStatus.FAILED, {"cancelled": True})
            logger.info(f"Cancelled command {command_id}")
            return True

    async def get_command(self, command_id: str) -> Optional[InspectionCommand]:
        """Get command by ID."""
        return await self._command_repo.get_by_id(command_id)

    async def list_pending_commands(self) -> List[InspectionCommand]:
        """List all pending commands."""
        return await self._command_repo.list_pending()

    async def subscribe(self, status: str, callback: Callable) -> None:
        """Subscribe to command status changes.

        Args:
            status: Status to subscribe to
            callback: Callback function
        """
        if status in self._subscribers:
            self._subscribers[status].append(callback)

    async def unsubscribe(self, status: str, callback: Callable) -> None:
        """Unsubscribe from command status changes.

        Args:
            status: Status to unsubscribe from
            callback: Callback function
        """
        if status in self._subscribers and callback in self._subscribers[status]:
            self._subscribers[status].remove(callback)

    async def _notify_subscribers(self, status: str, command: InspectionCommand) -> None:
        """Notify subscribers of status change."""
        if status in self._subscribers:
            for callback in self._subscribers[status]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(command)
                    else:
                        callback(command)
                except Exception as e:
                    logger.error(f"Subscriber callback failed: {e}")

    async def _execute_command(self, command: InspectionCommand) -> None:
        """Execute a command (internal)."""
        command_id = command.command_id

        try:
            # Update status to running
            await self.update_command_status(command_id, CommandStatus.RUNNING)

            # Add to active tasks
            self._active_tasks[command_id] = asyncio.current_task()

            # Execute inspection logic here
            # This will be called from the Agent
            logger.info(f"Executing command {command_id}")

            # Mark as completed (actual execution done by Agent)
            await self.update_command_status(command_id, CommandStatus.COMPLETED, {"status": "executed"})

        except asyncio.CancelledError:
            logger.info(f"Command {command_id} was cancelled")
            await self.update_command_status(command_id, CommandStatus.FAILED, {"cancelled": True})
        except Exception as e:
            logger.error(f"Command {command_id} failed: {e}")
            await self.update_command_status(command_id, CommandStatus.FAILED, {"error": str(e)})
        finally:
            self._active_tasks.pop(command_id, None)

    async def execute_command(self, command: InspectionCommand) -> Dict[str, Any]:
        """Execute a command with full inspection logic.

        Args:
            command: Command to execute

        Returns:
            Execution result
        """
        command_id = command.command_id

        try:
            await self.update_command_status(command_id, CommandStatus.RUNNING)

            results = []
            for target in command.targets:
                target_result = {
                    "target": target,
                    "items": [],
                    "success": True,
                }

                for item in command.inspection_items:
                    # Placeholder for actual inspection logic
                    # This will be replaced by Agent execution
                    target_result["items"].append(
                        {
                            "check_type": item.check_type,
                            "result": "pending",
                        }
                    )

                results.append(target_result)

            await self.update_command_status(
                command_id,
                CommandStatus.COMPLETED,
                {"results": results},
            )

            return {"command_id": command_id, "status": "completed", "results": results}

        except Exception as e:
            logger.error(f"Command {command_id} execution failed: {e}")
            await self.update_command_status(
                command_id,
                CommandStatus.FAILED,
                {"error": str(e)},
            )
            raise


# Global instruction bus instance
_instruction_bus: Optional[InstructionBus] = None


def get_instruction_bus() -> InstructionBus:
    """Get global instruction bus instance."""
    global _instruction_bus
    if _instruction_bus is None:
        _instruction_bus = InstructionBus()
    return _instruction_bus