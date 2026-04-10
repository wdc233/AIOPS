"""Alert Webhook Tool."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class AlertWebhookTool(BaseTool):
    """Tool for sending alert notifications via webhook."""

    name = "alert_webhook"
    description = "Send alert notifications to webhook URLs."

    def __init__(self) -> None:
        """Initialize alert webhook tool."""
        self._timeout = 10

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "webhook_url": {
                    "type": "string",
                    "description": "Webhook URL to send alert",
                },
                "title": {
                    "type": "string",
                    "description": "Alert title",
                },
                "message": {
                    "type": "string",
                    "description": "Alert message",
                },
                "severity": {
                    "type": "string",
                    "description": "Alert severity: critical, warning, info",
                    "enum": ["critical", "warning", "info"],
                    "default": "warning",
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata",
                },
            },
            "required": ["webhook_url", "title", "message"],
        }

    async def execute(
        self,
        webhook_url: str,
        title: str,
        message: str,
        severity: str = "warning",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """Send alert via webhook.

        Args:
            webhook_url: Webhook URL
            title: Alert title
            message: Alert message
            severity: Alert severity
            metadata: Additional metadata

        Returns:
            ToolResult with webhook response
        """
        start_time = time.time()

        try:
            payload = {
                "title": title,
                "message": message,
                "severity": severity,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    response_text = await response.text()

            duration_ms = int((time.time() - start_time) * 1000)

            if response.status < 400:
                return ToolResult(
                    success=True,
                    data={
                        "status_code": response.status,
                        "response": response_text,
                    },
                    duration_ms=duration_ms,
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Webhook returned {response.status}: {response_text}",
                    duration_ms=duration_ms,
                )

        except aiohttp.ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Alert webhook failed: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to send alert: {str(e)}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Alert webhook error: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def send_batch(
        self,
        webhook_urls: List[str],
        title: str,
        message: str,
        severity: str = "warning",
    ) -> Dict[str, ToolResult]:
        """Send alert to multiple webhooks.

        Args:
            webhook_urls: List of webhook URLs
            title: Alert title
            message: Alert message
            severity: Alert severity

        Returns:
            Dictionary of url -> ToolResult
        """
        tasks = [
            self.execute(
                webhook_url=url,
                title=title,
                message=message,
                severity=severity,
            )
            for url in webhook_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            url: result if isinstance(result, ToolResult) else ToolResult(success=False, error=str(result))
            for url, result in zip(webhook_urls, results)
        }