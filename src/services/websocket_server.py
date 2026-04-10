"""WebSocket Server for real-time communication."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

import websockets

from src.agent.intent_agent import get_intent_agent
from src.config import get_settings
from src.models.types import UserIntent

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket server for real-time instruction push and user interaction."""

    def __init__(self) -> None:
        """Initialize WebSocket server."""
        self._settings = get_settings()
        self._host = self._settings.websocket.host
        self._port = self._settings.websocket.port
        self._ping_interval = self._settings.websocket.ping_interval
        self._ping_timeout = self._settings.websocket.ping_timeout

        self._clients: Set[websockets.WebSocketServerProtocol] = set()
        self._running = False
        self._server: Optional[websockets.WebSocketServer] = None
        self._intent_agent = get_intent_agent()

    async def start(self) -> None:
        """Start WebSocket server."""
        if self._running:
            return

        self._running = True
        self._server = await websockets.serve(
            self._handle_client,
            self._host,
            self._port,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
        )

        logger.info(f"WebSocket server started on {self._host}:{self._port}")

    async def stop(self) -> None:
        """Stop WebSocket server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocket server stopped")

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str) -> None:
        """Handle client connection."""
        self._clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}")

        try:
            async for message in websocket:
                await self._process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {websocket.remote_address}")
        finally:
            self._clients.remove(websocket)

    async def _process_message(self, websocket: websockets.WebSocketServerProtocol, message: str) -> None:
        """Process incoming message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "user_query":
                response = await self._handle_user_query(data)
            elif msg_type == "command_result":
                response = await self._handle_command_result(data)
            elif msg_type == "heartbeat":
                response = {"type": "heartbeat_ack", "status": "ok"}
            else:
                response = {"type": "error", "message": f"Unknown message type: {msg_type}"}

            await websocket.send(json.dumps(response))

        except json.JSONDecodeError:
            await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))

    async def _handle_user_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user query with intent recognition."""
        user_input = data.get("content", "")

        # Use intent recognition agent
        result = await self._intent_agent.recognize_intent(user_input)

        intent = result.get("intent")
        missing_slots = result.get("missing_slots", [])
        messages = result.get("messages", [])

        if missing_slots:
            # Need more information
            return {
                "type": "intent_recognition",
                "status": "needs_more_info",
                "missing_slots": missing_slots,
                "messages": messages,
            }
        else:
            # Intent recognized, execute
            return {
                "type": "intent_recognition",
                "status": "ready",
                "intent": intent.model_dump() if intent else None,
                "tools": result.get("confirmed_tools", []),
                "messages": messages,
            }

    async def _handle_command_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command execution result."""
        command_id = data.get("command_id")
        status = data.get("status")
        result = data.get("result", {})

        logger.info(f"Command {command_id} completed with status: {status}")

        return {"type": "command_ack", "command_id": command_id, "status": "received"}

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        if not self._clients:
            return

        msg_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(msg_str) for client in self._clients],
            return_exceptions=True,
        )

    async def send_to_client(self, websocket: websockets.WebSocketServerProtocol, message: Dict[str, Any]) -> None:
        """Send message to a specific client."""
        await websocket.send(json.dumps(message))

    def get_connected_clients_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)


# Global WebSocket server instance
_ws_server: Optional[WebSocketServer] = None


def get_ws_server() -> WebSocketServer:
    """Get global WebSocket server instance."""
    global _ws_server
    if _ws_server is None:
        _ws_server = WebSocketServer()
    return _ws_server