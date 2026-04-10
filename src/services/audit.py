"""Audit Service for logging all operations."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.db.repository import AuditRepository
from src.models.types import AuditLog, AuditStatus, OperationType

logger = logging.getLogger(__name__)


class AuditService:
    """Audit service for full链路 operation logging."""

    def __init__(self) -> None:
        """Initialize audit service."""
        self._repo = AuditRepository()

    async def log_command_publish(
        self,
        command_id: str,
        operator: str,
        targets: list,
        inspection_items: list,
        created_by: Optional[str] = None,
    ) -> AuditLog:
        """Log command publish operation."""
        return await self._create_log(
            operation_type=OperationType.COMMAND_PUBLISH,
            operator=operator,
            target=command_id,
            input_data={
                "targets": targets,
                "inspection_items": [item.model_dump() for item in inspection_items],
                "created_by": created_by,
            },
            output_data={"status": "published"},
        )

    async def log_inspection_run(
        self,
        command_id: str,
        operator: str,
        target: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: AuditStatus = AuditStatus.SUCCESS,
        error_msg: Optional[str] = None,
        duration_ms: int = 0,
    ) -> AuditLog:
        """Log inspection run operation."""
        return await self._create_log(
            operation_type=OperationType.INSPECTION_RUN,
            operator=operator,
            target=f"{command_id}:{target}",
            input_data=input_data,
            output_data=output_data,
            status=status,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )

    async def log_user_query(
        self,
        operator: str,
        user_input: str,
        intent_type: str,
        missing_slots: list,
    ) -> AuditLog:
        """Log user query operation."""
        return await self._create_log(
            operation_type=OperationType.USER_QUERY,
            operator=operator,
            input_data={"user_input": user_input},
            output_data={
                "intent_type": intent_type,
                "missing_slots": missing_slots,
            },
        )

    async def log_tool_call(
        self,
        operator: str,
        tool_name: str,
        target: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: AuditStatus = AuditStatus.SUCCESS,
        error_msg: Optional[str] = None,
        duration_ms: int = 0,
    ) -> AuditLog:
        """Log tool call operation."""
        return await self._create_log(
            operation_type=OperationType.TOOL_CALL,
            operator=operator,
            target=f"{tool_name}:{target}",
            input_data=input_data,
            output_data=output_data,
            status=status,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )

    async def log_alert_send(
        self,
        operator: str,
        alert_title: str,
        target: str,
        severity: str,
        webhook_url: str,
        status: AuditStatus = AuditStatus.SUCCESS,
        error_msg: Optional[str] = None,
        duration_ms: int = 0,
    ) -> AuditLog:
        """Log alert send operation."""
        return await self._create_log(
            operation_type=OperationType.ALERT_SEND,
            operator=operator,
            target=target,
            input_data={
                "alert_title": alert_title,
                "severity": severity,
                "webhook_url": webhook_url,
            },
            output_data={"status": "sent" if status == AuditStatus.SUCCESS else "failed"},
            status=status,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )

    async def _create_log(
        self,
        operation_type: OperationType,
        operator: str,
        target: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        error_msg: Optional[str] = None,
        duration_ms: int = 0,
    ) -> AuditLog:
        """Create and save audit log."""
        log = AuditLog(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            operation_type=operation_type,
            operator=operator,
            target=target,
            input_data=input_data or {},
            output_data=output_data or {},
            status=status,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )

        try:
            await self._repo.create(log)
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

        return log

    async def get_logs_by_operator(self, operator: str, limit: int = 100) -> list[AuditLog]:
        """Get audit logs by operator."""
        return await self._repo.list_by_operator(operator, limit)

    async def get_logs_by_operation(self, operation_type: OperationType, limit: int = 100) -> list[AuditLog]:
        """Get audit logs by operation type."""
        return await self._repo.list_by_operation_type(operation_type, limit)


# Global audit service instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get global audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service