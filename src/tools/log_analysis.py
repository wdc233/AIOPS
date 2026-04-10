"""Log Analysis Tool."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Pattern

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class LogAnalysisTool(BaseTool):
    """Tool for analyzing log files with regex and anomaly detection."""

    name = "log_analysis"
    description = "Analyze log files on remote servers, support regex matching and anomaly detection."

    def __init__(self) -> None:
        """Initialize log analysis tool."""
        self._anomaly_patterns = [
            (r"ERROR|FATAL|EXCEPTION", "error"),
            (r"WARNING|WARN", "warning"),
            (r"timeout|timed out", "timeout"),
            (r"connection refused|connection reset", "connection_error"),
            (r"out of memory|OOM", "memory_error"),
            (r"disk full|no space left", "disk_error"),
        ]

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target server IP address",
                },
                "log_path": {
                    "type": "string",
                    "description": "Path to log file on remote server",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "lines": {
                    "type": "integer",
                    "description": "Number of lines to read from end (tail)",
                    "default": 100,
                },
                "detect_anomalies": {
                    "type": "boolean",
                    "description": "Enable anomaly detection",
                    "default": True,
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range filter (e.g., '1h', '24h', '7d')",
                },
            },
            "required": ["host", "log_path"],
        }

    async def execute(
        self,
        host: str,
        log_path: str,
        pattern: Optional[str] = None,
        lines: int = 100,
        detect_anomalies: bool = True,
        time_range: Optional[str] = None,
    ) -> ToolResult:
        """Analyze log file.

        Args:
            host: Target server IP
            log_path: Path to log file
            pattern: Regex pattern to search
            lines: Number of lines to read
            detect_anomalies: Enable anomaly detection
            time_range: Time range filter

        Returns:
            ToolResult with log analysis
        """
        start_time = time.time()

        try:
            # Build command based on parameters
            cmd = f"tail -n {lines} {log_path}"

            if time_range:
                # Use find with -mmin for time filtering
                cmd = f"find {log_path} -mmin -{self._parse_time_range(time_range)} -exec tail -n {lines} {{}} \\;"

            # Import here to avoid circular dependency
            from src.tools.ssh import SSHCommandTool

            ssh_tool = SSHCommandTool()
            result = await ssh_tool.execute(host=host, command=cmd)

            if not result.success:
                return result

            log_content = result.data.get("stdout", "") if result.data else ""

            # Analyze logs
            analysis = self._analyze_content(log_content, pattern, detect_anomalies)

            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=True,
                data=analysis,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Log analysis failed for {host}:{log_path}: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def _analyze_content(
        self,
        content: str,
        pattern: Optional[str] = None,
        detect_anomalies: bool = True,
    ) -> Dict[str, Any]:
        """Analyze log content."""
        lines = content.strip().split("\n")
        total_lines = len(lines)

        result = {
            "total_lines": total_lines,
            "matched_lines": 0,
            "matches": [],
            "anomalies": [],
            "summary": {},
        }

        # Pattern matching
        compiled_pattern: Optional[Pattern] = None
        if pattern:
            try:
                compiled_pattern = re.compile(pattern)
            except re.error as e:
                return {"error": f"Invalid regex pattern: {e}"}

        matched_lines = []
        for i, line in enumerate(lines):
            if compiled_pattern and compiled_pattern.search(line):
                matched_lines.append({"line_number": i + 1, "content": line})

            # Anomaly detection
            if detect_anomalies:
                for anomaly_pattern, anomaly_type in self._anomaly_patterns:
                    if re.search(anomaly_pattern, line, re.IGNORECASE):
                        result["anomalies"].append(
                            {
                                "line_number": i + 1,
                                "type": anomaly_type,
                                "content": line[:200],  # Truncate long lines
                            }
                        )
                        break

        result["matched_lines"] = len(matched_lines)
        result["matches"] = matched_lines[:50]  # Limit to 50 matches
        result["anomalies"] = result["anomalies"][:50]  # Limit anomalies

        # Summary
        result["summary"] = {
            "total_lines": total_lines,
            "error_count": sum(1 for a in result["anomalies"] if a["type"] == "error"),
            "warning_count": sum(1 for a in result["anomalies"] if a["type"] == "warning"),
            "anomaly_count": len(result["anomalies"]),
        }

        return result

    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range to minutes."""
        match = re.match(r"(\d+)([smhd])", time_range.lower())
        if not match:
            return 60  # Default 1 hour

        value, unit = match.groups()
        value = int(value)

        multipliers = {"s": 1, "m": 1, "h": 60, "d": 1440}
        return value * multipliers.get(unit, 60)