"""API dependencies for dependency injection."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from src.agent.intent_agent import IntentRecognitionAgent, get_intent_agent
from src.agent.main_agent import MainAgent, get_main_agent
from src.environment.manager import get_environment_manager
from src.models.types import UserIntent
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
    ) -> None:
        """Update session with new intent or confirmation."""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if intent:
                    session.intent = intent
                session.confirmed = confirmed
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


# Global API service
_api_service: Optional[APIService] = None


def get_api_service() -> APIService:
    """Get global API service instance."""
    global _api_service
    if _api_service is None:
        _api_service = APIService()
    return _api_service