"""SSH Command Tool for remote server execution."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import paramiko

from src.config import get_settings
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class SSHCommandTool(BaseTool):
    """Tool for executing commands on remote servers via SSH."""

    name = "ssh_command"
    description = "Execute commands on remote Linux servers via SSH. Returns structured command output."

    def __init__(self) -> None:
        """Initialize SSH command tool."""
        self._settings = get_settings()
        self._timeout = self._settings.ssh.timeout
        self._command_timeout = self._settings.ssh.command_timeout
        self._max_retries = self._settings.ssh.max_retries

    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target server IP address or hostname",
                },
                "port": {
                    "type": "integer",
                    "description": "SSH port (default: 22)",
                    "default": 22,
                },
                "username": {
                    "type": "string",
                    "description": "SSH username",
                },
                "password": {
                    "type": "string",
                    "description": "SSH password (optional if using private_key)",
                },
                "private_key": {
                    "type": "string",
                    "description": "Path to private key file (optional)",
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute",
                },
                "sudo": {
                    "type": "boolean",
                    "description": "Execute command with sudo",
                    "default": False,
                },
            },
            "required": ["host", "command"],
        }

    async def execute(
        self,
        host: str,
        command: str,
        port: int = 22,
        username: str = "root",
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        sudo: bool = False,
    ) -> ToolResult:
        """Execute command on remote server.

        Args:
            host: Target server IP or hostname
            port: SSH port
            username: SSH username
            password: SSH password
            private_key: Path to private key
            command: Command to execute
            sudo: Execute with sudo

        Returns:
            ToolResult with execution output
        """
        start_time = time.time()

        if sudo and not password:
            command = f"sudo {command}"

        for attempt in range(self._max_retries):
            try:
                result = await self._execute_ssh(
                    host, port, username, password, private_key, command
                )
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    success=True,
                    data=result,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                logger.warning(f"SSH attempt {attempt + 1} failed for {host}: {e}")
                if attempt == self._max_retries - 1:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ToolResult(
                        success=False,
                        error=str(e),
                        duration_ms=duration_ms,
                    )
                await asyncio.sleep(self._settings.ssh.retry_delay)

        duration_ms = int((time.time() - start_time) * 1000)
        return ToolResult(success=False, error="Max retries exceeded", duration_ms=duration_ms)

    async def _execute_ssh(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str],
        private_key: Optional[str],
        command: str,
    ) -> Dict[str, Any]:
        """Execute SSH command."""
        loop = asyncio.get_event_loop()

        async def run_ssh():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Connect
                connect_kwargs = {
                    "hostname": host,
                    "port": port,
                    "username": username,
                    "timeout": self._timeout,
                }

                if password:
                    connect_kwargs["password"] = password
                elif private_key:
                    connect_kwargs["key_filename"] = private_key

                await loop.run_in_executor(None, client.connect, **connect_kwargs)

                # Execute command
                stdin, stdout, stderr = await loop.run_in_executor(
                    None,
                    client.exec_command,
                    command,
                    timeout=self._command_timeout,
                )

                # Read output
                stdout_data = await loop.run_in_executor(None, stdout.read)
                stderr_data = await loop.run_in_executor(None, stderr.read)

                exit_code = stdout.channel.recv_exit_status()

                return {
                    "host": host,
                    "command": command,
                    "exit_code": exit_code,
                    "stdout": stdout_data.decode("utf-8", errors="replace"),
                    "stderr": stderr_data.decode("utf-8", errors="replace"),
                }
            finally:
                await loop.run_in_executor(None, client.close)

        return await run_ssh()

    async def execute_batch(
        self,
        hosts: List[str],
        command: str,
        port: int = 22,
        username: str = "root",
        password: Optional[str] = None,
    ) -> Dict[str, ToolResult]:
        """Execute command on multiple hosts.

        Args:
            hosts: List of target server IPs
            command: Command to execute
            port: SSH port
            username: SSH username
            password: SSH password

        Returns:
            Dictionary of host -> ToolResult
        """
        tasks = [
            self.execute(
                host=host,
                command=command,
                port=port,
                username=username,
                password=password,
            )
            for host in hosts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            host: result if isinstance(result, ToolResult) else ToolResult(success=False, error=str(result))
            for host, result in zip(hosts, results)
        }