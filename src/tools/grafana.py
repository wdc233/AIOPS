"""Grafana Query Tool."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.config import get_settings
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class GrafanaQueryTool(BaseTool):
    """Tool for querying Grafana dashboards and data sources."""

    name = "grafana_query"
    description = "Query Grafana dashboards and retrieve panel data."

    def __init__(self) -> None:
        """Initialize Grafana query tool."""
        self._settings = get_settings()
        self._url = self._settings.grafana.url
        self._api_key = self._settings.grafana.api_key
        self._timeout = self._settings.grafana.timeout

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "dashboard_uid": {
                    "type": "string",
                    "description": "Grafana dashboard UID",
                },
                "panel_id": {
                    "type": "integer",
                    "description": "Panel ID",
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range (e.g., '1h', '24h', '7d')",
                },
            },
            "required": ["dashboard_uid"],
        }

    async def execute(
        self,
        dashboard_uid: str,
        panel_id: Optional[int] = None,
        time_range: str = "1h",
    ) -> ToolResult:
        """Query Grafana panel data.

        Args:
            dashboard_uid: Dashboard UID
            panel_id: Panel ID (optional)
            time_range: Time range

        Returns:
            ToolResult with panel data
        """
        start_time = time.time()

        try:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            # Get dashboard
            async with aiohttp.ClientSession() as session:
                # First get the dashboard
                async with session.get(
                    f"{self._url}/api/dashboards/uid/{dashboard_uid}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        duration_ms = int((time.time() - start_time) * 1000)
                        return ToolResult(
                            success=False,
                            error=f"Failed to get dashboard: {response.status} - {error_text}",
                            duration_ms=duration_ms,
                        )

                    dashboard_data = await response.json()

            dashboard = dashboard_data.get("dashboard", {})
            panels = dashboard.get("panels", [])

            # Filter by panel_id if specified
            if panel_id:
                panels = [p for p in panels if p.get("id") == panel_id]

            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=True,
                data={
                    "dashboard_uid": dashboard_uid,
                    "dashboard_title": dashboard.get("title"),
                    "panels": [
                        {
                            "id": p.get("id"),
                            "title": p.get("title"),
                            "type": p.get("type"),
                        }
                        for p in panels
                    ],
                },
                duration_ms=duration_ms,
            )

        except aiohttp.ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Grafana query failed: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to connect to Grafana: {str(e)}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Grafana query error: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def get_dashboards(self) -> ToolResult:
        """Get all dashboards."""
        start_time = time.time()

        try:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/search",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    data = await response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            dashboards = [
                {"uid": d.get("uid"), "title": d.get("title"), "type": d.get("type")}
                for d in data
                if d.get("type") == "dash-db"
            ]

            return ToolResult(
                success=True,
                data=dashboards,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def get_datasource(self, datasource_id: int) -> ToolResult:
        """Get datasource by ID."""
        start_time = time.time()

        try:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/datasources/{datasource_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    data = await response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                success=True,
                data=data,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )