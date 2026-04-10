"""Heartbeat Service for agent self-check."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.config import get_settings
from src.models.types import AgentState, HeartbeatInfo
from src.agent.main_agent import get_main_agent

logger = logging.getLogger(__name__)


class HeartbeatService:
    """Heartbeat service for lightweight self-check every 30 minutes."""

    def __init__(self) -> None:
        """Initialize heartbeat service."""
        self._settings = get_settings()
        self._agent = get_main_agent()
        self._heartbeat_interval = self._settings.scheduler.heartbeat_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_info = HeartbeatInfo(
            agent_id=self._settings.agent.agent_id,
            status=AgentState.IDLE,
        )

    async def start(self) -> None:
        """Start heartbeat service."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Heartbeat service started (interval: {self._heartbeat_interval}s)")

    async def stop(self) -> None:
        """Stop heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat service stopped")

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop running every 30 minutes."""
        while self._running:
            try:
                await self._perform_heartbeat()
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

            # Wait for next heartbeat interval
            try:
                await asyncio.sleep(self._heartbeat_interval)
            except asyncio.CancelledError:
                break

    async def _perform_heartbeat(self) -> None:
        """Perform heartbeat self-check."""
        logger.debug("Performing heartbeat...")

        self._heartbeat_info.status = AgentState.HEARTBEAT
        self._heartbeat_info.last_heartbeat = datetime.now()

        try:
            # Perform lightweight checks
            checks = await self._run_health_checks()

            # Update heartbeat info
            self._heartbeat_info.status = AgentState.IDLE

            logger.debug(f"Heartbeat completed: {checks}")

        except Exception as e:
            logger.error(f"Heartbeat check failed: {e}")
            self._heartbeat_info.status = AgentState.IDLE

    async def _run_health_checks(self) -> Dict[str, Any]:
        """Run health checks during heartbeat."""
        checks = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self._settings.agent.agent_id,
            "status": "healthy",
            "checks": {},
        }

        # Check database connectivity
        try:
            from src.db import get_db_manager
            db = await get_db_manager()
            await db.execute_sql("SELECT 1")
            checks["checks"]["database"] = "ok"
        except Exception as e:
            checks["checks"]["database"] = f"error: {str(e)}"
            checks["status"] = "degraded"

        # Check environment manager
        try:
            from src.environment import get_environment_manager
            env_mgr = get_environment_manager()
            clusters = env_mgr.get_all_clusters()
            checks["checks"]["environment"] = f"ok ({len(clusters)} clusters)"
        except Exception as e:
            checks["checks"]["environment"] = f"error: {str(e)}"

        # Check tool registry
        try:
            from src.tools import get_tool_registry
            tools = get_tool_registry().get_all_tools()
            checks["checks"]["tools"] = f"ok ({len(tools)} tools)"
        except Exception as e:
            checks["checks"]["tools"] = f"error: {str(e)}"

        return checks

    def get_heartbeat_info(self) -> HeartbeatInfo:
        """Get current heartbeat information."""
        return self._heartbeat_info

    async def report_status(self, status: AgentState, current_task: Optional[str] = None) -> None:
        """Report agent status."""
        self._heartbeat_info.status = status
        self._heartbeat_info.current_task = current_task

    def is_running(self) -> bool:
        """Check if heartbeat service is running."""
        return self._running


# Global heartbeat service instance
_heartbeat_service: Optional[HeartbeatService] = None


def get_heartbeat_service() -> HeartbeatService:
    """Get global heartbeat service instance."""
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = HeartbeatService()
    return _heartbeat_service