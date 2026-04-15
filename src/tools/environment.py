"""Environment Query Tool."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.environment.manager import get_environment_manager
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EnvironmentQueryTool(BaseTool):
    """Tool for querying global environment information."""

    name = "environment_query"
    description = "Query global environment information including cluster and server metadata."

    def __init__(self) -> None:
        """Initialize environment query tool."""
        self._env_manager = get_environment_manager()

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "Type of query: cluster, server, all",
                    "enum": ["cluster", "server", "all"],
                },
                "name": {
                    "type": "string",
                    "description": "Cluster name or server IP",
                },
            },
            "required": ["query_type"],
        }

    async def execute(
        self,
        query_type: str,
        name: Optional[str] = None,
    ) -> ToolResult:
        """Query environment information.

        Args:
            query_type: Type of query (cluster, server, all)
            name: Cluster name or server IP

        Returns:
            ToolResult with query results
        """
        start_time = time.time()

        try:
            result_data = None

            if query_type == "cluster":
                if name:
                    cluster = self._env_manager.get_cluster(name)
                    result_data = cluster.model_dump() if cluster else None
                else:
                    clusters = self._env_manager.get_all_clusters()
                    result_data = [c.model_dump() for c in clusters]

            elif query_type == "server":
                if name:
                    server = self._env_manager.get_server(name)
                    result_data = server.model_dump() if server else None
                else:
                    # Return all servers
                    clusters = self._env_manager.get_all_clusters()
                    servers = []
                    for c in clusters:
                        servers.extend([s.model_dump() for s in c.servers])
                    result_data = servers

            elif query_type == "all":
                clusters = self._env_manager.get_all_clusters()
                result_data = {
                    "clusters": [c.model_dump() for c in clusters],
                    "total_servers": sum(len(c.servers) for c in clusters),
                }

            else:
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    success=False,
                    error=f"Unknown query_type: {query_type}",
                    duration_ms=duration_ms,
                )

            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=True,
                data=result_data,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Environment query failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )