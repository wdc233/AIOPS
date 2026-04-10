"""Base tool class and result type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Base tool execution result."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = "base_tool"
    description: str = "Base tool"

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult: Execution result
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM function calling.

        Returns:
            Tool schema in OpenAI function calling format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._get_parameters_schema(),
            },
        }

    @abstractmethod
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for this tool.

        Returns:
            JSON schema for parameters
        """
        pass

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate tool parameters.

        Args:
            params: Parameters to validate

        Returns:
            True if valid
        """
        return True