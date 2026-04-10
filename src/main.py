"""Main entry point for AIOPS Agent."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
from typing import Optional

import uvicorn

from src.config import get_settings
from src.models.types import AgentState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AIOPSAgent:
    """Main AIOPS Agent application."""

    def __init__(self) -> None:
        """Initialize AIOPS Agent."""
        self._settings = get_settings()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._api_server_thread: Optional[threading.Thread] = None

    def _start_api_server(self) -> None:
        """Start FastAPI server in a background thread."""
        from src.api.main import get_app

        app = get_app()

        def run_server():
            uvicorn.run(
                app,
                host=self._settings.api.host,
                port=self._settings.api.port,
                log_level=self._settings.agent.log_level.lower(),
            )

        self._api_server_thread = threading.Thread(target=run_server, daemon=True)
        self._api_server_thread.start()

    async def start(self) -> None:
        """Start the AIOPS Agent."""
        if self._running:
            logger.warning("Agent already running")
            return

        logger.info("Starting AIOPS Agent...")
        self._running = True

        # Initialize database (optional, can be disabled for local API-only testing)
        if self._settings.database.enabled:
            from src.db import get_db_manager
            db = await get_db_manager()
            logger.info("Database initialized")
        else:
            logger.info("Database disabled, skipping initialization")

        # Initialize environment
        from src.environment import initialize_environment
        config_path = self._settings.cluster_config_path
        await initialize_environment(config_path)
        logger.info("Environment initialized")

        # Initialize tools
        from src.tools import get_tool_registry
        get_tool_registry().initialize()
        logger.info("Tools initialized")

        # Start heartbeat service
        from src.services.heartbeat import get_heartbeat_service
        heartbeat = get_heartbeat_service()
        await heartbeat.start()
        logger.info("Heartbeat service started")

        # Start scheduler
        from src.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.start()
        logger.info("Scheduler started")

        # Start WebSocket server
        from src.services.websocket_server import get_ws_server
        ws_server = get_ws_server()
        await ws_server.start()
        logger.info("WebSocket server started")

        # Start FastAPI server in background thread
        self._start_api_server()
        logger.info(f"API server started on {self._settings.api.host}:{self._settings.api.port}")

        logger.info(f"AIOPS Agent started successfully (agent_id: {self._settings.agent.agent_id})")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the AIOPS Agent."""
        if not self._running:
            return

        logger.info("Stopping AIOPS Agent...")

        # Stop heartbeat
        from src.services.heartbeat import get_heartbeat_service
        heartbeat = get_heartbeat_service()
        await heartbeat.stop()

        # Stop scheduler
        from src.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.stop()

        # Stop WebSocket
        from src.services.websocket_server import get_ws_server
        ws_server = get_ws_server()
        await ws_server.stop()

        # Stop API server (trigger uvicorn shutdown)
        from src.api.main import get_app
        app = get_app()
        # Uvicorn doesn't have a clean shutdown from external, but the daemon thread will exit with the process
        logger.info("API server will stop with the process")

        # Close database (only if enabled)
        if self._settings.database.enabled:
            from src.db import close_db_manager
            await close_db_manager()

        self._running = False
        logger.info("AIOPS Agent stopped")

        # Signal shutdown complete
        self._shutdown_event.set()

    def signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.stop())


async def main() -> None:
    """Main entry point."""
    agent = AIOPSAgent()

    # Register signal handlers
    signal.signal(signal.SIGINT, agent.signal_handler)
    signal.signal(signal.SIGTERM, agent.signal_handler)

    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await agent.stop()
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        await agent.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())