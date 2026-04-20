"""API dependencies for dependency injection."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.agent.intent_agent import IntentRecognitionAgent, get_intent_agent
from src.agent.main_agent import MainAgent, get_main_agent
from src.environment.manager import get_environment_manager
from src.models.types import CommandAction, InspectionCommand, InspectionItem, UserIntent
from src.tools.prometheus import PrometheusQueryTool

logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Chat session for multi-round conversation."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    intent: Optional[UserIntent] = None
    history: list = field(default_factory=list)
    confirmed: bool = False
    pending_metric_suggestion: Optional[Dict[str, Any]] = field(default=None)  # Store metric suggestion info when user needs to confirm


class SessionManager:
    """Manager for chat sessions."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_session(self, session_id: str) -> ChatSession:
        """Get existing session or create new one."""
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ChatSession(session_id=session_id)
            return self._sessions[session_id]

    async def update_session(
        self,
        session_id: str,
        intent: Optional[UserIntent] = None,
        confirmed: bool = False,
        pending_metric_suggestion: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update session with new intent or confirmation."""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if intent:
                    session.intent = intent
                session.confirmed = confirmed
                if pending_metric_suggestion is not None:
                    session.pending_metric_suggestion = pending_metric_suggestion
                session.updated_at = datetime.now()

    async def add_to_history(self, session_id: str, role: str, content: str) -> None:
        """Add message to session history."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].history.append({
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                })

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def clear_session(self, session_id: str) -> None:
        """Clear a session."""
        async with self._lock:
            self._sessions.pop(session_id, None)


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


class APIService:
    """API service for business logic."""

    def __init__(self) -> None:
        """Initialize API service."""
        self._intent_agent: Optional[IntentRecognitionAgent] = None
        self._main_agent: Optional[MainAgent] = None

    def get_intent_agent(self) -> IntentRecognitionAgent:
        """Get intent recognition agent."""
        if self._intent_agent is None:
            self._intent_agent = get_intent_agent()
        return self._intent_agent

    def get_main_agent(self) -> MainAgent:
        """Get main agent."""
        if self._main_agent is None:
            self._main_agent = get_main_agent()
        return self._main_agent

    def get_environment_manager(self):
        """Get environment manager."""
        return get_environment_manager()

    def get_prometheus_tool(self) -> PrometheusQueryTool:
        """Get Prometheus query tool."""
        return PrometheusQueryTool()

    async def run_inspection(self, targets: List[str], cluster_name: Optional[str] = None) -> Dict[str, Any]:
        """Run inspection on specified targets.

        Args:
            targets: List of target server IPs
            cluster_name: Optional cluster name for reporting

        Returns:
            Inspection result dictionary
        """
        main_agent = self.get_main_agent()
        env_manager = self.get_environment_manager()

        # Build inspection items
        inspection_items = [
            InspectionItem(check_type="cpu", description="CPU usage check"),
            InspectionItem(check_type="memory", description="Memory usage check"),
            InspectionItem(check_type="disk", description="Disk usage check"),
            InspectionItem(check_type="network", description="Network I/O check"),
            InspectionItem(check_type="prometheus", description="Prometheus service metrics check"),
        ]

        # Create inspection command
        command = InspectionCommand(
            command_id=f"chat-inspection-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            action=CommandAction.RUN_NOW,
            name=f"Chat Inspection - {cluster_name or 'direct'}",
            targets=targets,
            inspection_items=inspection_items,
            created_by="user",
        )

        try:
            result = await main_agent.execute_inspection(command)
            logger.info(f"execute_inspection returned: {type(result)} - {result}")
            if result is None:
                logger.error("execute_inspection returned None")
                return {
                    "success": False,
                    "error": "Inspection returned no result",
                    "cluster": cluster_name,
                }
            if not isinstance(result, dict):
                logger.error(f"execute_inspection returned non-dict: {type(result)}")
                return {
                    "success": False,
                    "error": f"Inspection returned unexpected type: {type(result).__name__}",
                    "cluster": cluster_name,
                }
            return {
                "success": True,
                "cluster": cluster_name,
                "inspection_id": command.command_id,
                "results": result.get("results", []),
                "status": result.get("status", "completed"),
            }
        except Exception as e:
            logger.error(f"Inspection execution failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "cluster": cluster_name,
            }


# Global API service
_api_service: Optional[APIService] = None


def get_api_service() -> APIService:
    """Get global API service instance."""
    global _api_service
    if _api_service is None:
        _api_service = APIService()
    return _api_service