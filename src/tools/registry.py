"""Tool registry for managing all available tools."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.tools.alert import AlertWebhookTool
from src.tools.base import BaseTool, ToolResult
from src.tools.environment import EnvironmentQueryTool
from src.tools.grafana import GrafanaQueryTool
from src.tools.log_analysis import LogAnalysisTool
from src.tools.prometheus import PrometheusQueryTool
from src.tools.ssh import SSHCommandTool
from src.tools.trend import TrendPredictionTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing all available tools."""

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all tools."""
        if self._initialized:
            return

        # Register all tools
        tools = [
            SSHCommandTool(),
            LogAnalysisTool(),
            PrometheusQueryTool(),
            GrafanaQueryTool(),
            TrendPredictionTool(),
            AlertWebhookTool(),
            EnvironmentQueryTool(),
        ]

        for tool in tools:
            self._tools[tool.name] = tool
            logger.info(f"Registered tool: {tool.name}")

        self._initialized = True

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_tool_schemas(self) -> List[Dict]:
        """Get all tool schemas for LLM function calling."""
        return [tool.get_schema() for tool in self._tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        return tool.execute(**kwargs)


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get global tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        _tool_registry.initialize()
    return _tool_registry


def get_all_tools() -> List[BaseTool]:
    """Get all available tools."""
    return get_tool_registry().get_all_tools()


def get_tool(name: str) -> Optional[BaseTool]:
    """Get tool by name."""
    return get_tool_registry().get_tool(name)