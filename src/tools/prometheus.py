"""Prometheus Query Tool."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.config import get_settings
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class PrometheusQueryTool(BaseTool):
    """Tool for querying Prometheus metrics with PromQL."""

    name = "prometheus_query"
    description = "Query Prometheus metrics using PromQL. Returns time series data."

    def __init__(self) -> None:
        """Initialize Prometheus query tool."""
        self._settings = get_settings()
        self._url = self._settings.prometheus.url
        self._timeout = self._settings.prometheus.timeout

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PromQL query string",
                },
                "time": {
                    "type": "string",
                    "description": "Unix timestamp or relative time (e.g., 'now', '1h ago')",
                },
                "step": {
                    "type": "string",
                    "description": "Query resolution step (e.g., '15s', '1m', '5m')",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        time: Optional[str] = None,
        step: Optional[str] = None,
    ) -> ToolResult:
        """Query Prometheus.

        Args:
            query: PromQL query
            time: Time (unix timestamp or relative)
            step: Resolution step

        Returns:
            ToolResult with query results
        """
        start_time = time.time()

        try:
            params: Dict[str, str] = {"query": query}

            if time:
                params["time"] = time
            if step:
                params["step"] = step

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/v1/query",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        duration_ms = int((time.time() - start_time) * 1000)
                        return ToolResult(
                            success=False,
                            error=f"Prometheus query failed: {response.status} - {error_text}",
                            duration_ms=duration_ms,
                        )

                    data = await response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            if data.get("status") == "success":
                return ToolResult(
                    success=True,
                    data=data.get("data", {}),
                    duration_ms=duration_ms,
                )
            else:
                return ToolResult(
                    success=False,
                    error=data.get("error", "Unknown error"),
                    duration_ms=duration_ms,
                )

        except aiohttp.ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Prometheus query failed: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to connect to Prometheus: {str(e)}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Prometheus query error: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def query_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "1m",
    ) -> ToolResult:
        """Query Prometheus with time range.

        Args:
            query: PromQL query
            start: Start time (unix timestamp or relative)
            end: End time (unix timestamp or relative)
            step: Resolution step

        Returns:
            ToolResult with query results
        """
        start_time = time.time()

        try:
            params: Dict[str, str] = {
                "query": query,
                "start": start,
                "end": end,
                "step": step,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/v1/query_range",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self._timeout * 10),  # Longer for range queries
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        duration_ms = int((time.time() - start_time) * 1000)
                        return ToolResult(
                            success=False,
                            error=f"Prometheus query failed: {response.status} - {error_text}",
                            duration_ms=duration_ms,
                        )

                    data = await response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            if data.get("status") == "success":
                return ToolResult(
                    success=True,
                    data=data.get("data", {}),
                    duration_ms=duration_ms,
                )
            else:
                return ToolResult(
                    success=False,
                    error=data.get("error", "Unknown error"),
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Prometheus query_range failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def get_metric_names(self) -> ToolResult:
        """Get all available metric names."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/v1/label/__name__/values",
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    data = await response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            if data.get("status") == "success":
                return ToolResult(
                    success=True,
                    data=data.get("data", []),
                    duration_ms=duration_ms,
                )
            else:
                return ToolResult(
                    success=False,
                    error=data.get("error", "Unknown error"),
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )