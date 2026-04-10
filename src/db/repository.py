"""Repository layer for data access."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.types import (
    AuditLog,
    AuditStatus,
    ClusterInfo,
    CommandAction,
    CommandStatus,
    InspectionCommand,
    OperationType,
    ServerInfo,
)

from .connection import get_db_manager


class CommandRepository:
    """Repository for inspection commands."""

    def __init__(self) -> None:
        """Initialize command repository."""
        self._db = None

    async def _get_db(self):
        """Get database manager."""
        if self._db is None:
            self._db = await get_db_manager()
        return self._db

    async def create(self, command: InspectionCommand) -> InspectionCommand:
        """Create a new command."""
        db = await self._get_db()

        sql = """
        INSERT INTO inspection_commands
        (command_id, action, name, cron, targets, inspection_items, session_type,
         callback_url, priority, created_by, status, created_at, result)
        VALUES
        (:command_id, :action, :name, :cron, :targets, :inspection_items, :session_type,
         :callback_url, :priority, :created_by, :status, :created_at, :result)
        """

        params = {
            "command_id": command.command_id,
            "action": command.action,
            "name": command.name,
            "cron": command.cron,
            "targets": json.dumps(command.targets),
            "inspection_items": json.dumps([item.model_dump() for item in command.inspection_items]),
            "session_type": command.session_type,
            "callback_url": command.callback_url,
            "priority": command.priority,
            "created_by": command.created_by,
            "status": command.status,
            "created_at": command.created_at.isoformat(),
            "result": json.dumps(command.result) if command.result else None,
        }

        await db.execute_sql(sql, params)
        return command

    async def get_by_id(self, command_id: str) -> Optional[InspectionCommand]:
        """Get command by ID."""
        db = await self._get_db()

        sql = "SELECT * FROM inspection_commands WHERE command_id = :command_id"
        row = await db.fetch_one(sql, {"command_id": command_id})

        if row:
            return self._row_to_command(row)
        return None

    async def update(self, command: InspectionCommand) -> InspectionCommand:
        """Update command."""
        db = await self._get_db()

        sql = """
        UPDATE inspection_commands
        SET action = :action, name = :name, cron = :cron, targets = :targets,
            inspection_items = :inspection_items, session_type = :session_type,
            callback_url = :callback_url, priority = :priority, status = :status,
            executed_at = :executed_at, result = :result, updated_at = NOW()
        WHERE command_id = :command_id
        """

        params = {
            "command_id": command.command_id,
            "action": command.action,
            "name": command.name,
            "cron": command.cron,
            "targets": json.dumps(command.targets),
            "inspection_items": json.dumps([item.model_dump() for item in command.inspection_items]),
            "session_type": command.session_type,
            "callback_url": command.callback_url,
            "priority": command.priority,
            "status": command.status,
            "executed_at": command.executed_at.isoformat() if command.executed_at else None,
            "result": json.dumps(command.result) if command.result else None,
        }

        await db.execute_sql(sql, params)
        return command

    async def update_status(self, command_id: str, status: CommandStatus, result: Optional[Dict[str, Any]] = None) -> None:
        """Update command status."""
        db = await self._get_db()

        executed_at = ", executed_at = NOW()" if status in (CommandStatus.COMPLETED, CommandStatus.FAILED) else ""
        result_str = ", result = :result" if result else ""

        sql = f"""
        UPDATE inspection_commands
        SET status = :status{result_str}{executed_at}, updated_at = NOW()
        WHERE command_id = :command_id
        """

        params = {"command_id": command_id, "status": status}
        if result:
            params["result"] = json.dumps(result)

        await db.execute_sql(sql, params)

    async def delete(self, command_id: str) -> bool:
        """Delete command."""
        db = await self._get_db()
        sql = "DELETE FROM inspection_commands WHERE command_id = :command_id"
        await db.execute_sql(sql, {"command_id": command_id})
        return True

    async def list_pending(self, limit: int = 100) -> List[InspectionCommand]:
        """List pending commands."""
        db = await self._get_db()
        sql = "SELECT * FROM inspection_commands WHERE status = 'pending' ORDER BY priority DESC, created_at ASC LIMIT :limit"
        rows = await db.fetch_all(sql, {"limit": limit})
        return [self._row_to_command(row) for row in rows]

    async def list_by_status(self, status: CommandStatus, limit: int = 100) -> List[InspectionCommand]:
        """List commands by status."""
        db = await self._get_db()
        sql = "SELECT * FROM inspection_commands WHERE status = :status ORDER BY created_at DESC LIMIT :limit"
        rows = await db.fetch_all(sql, {"status": status, "limit": limit})
        return [self._row_to_command(row) for row in rows]

    def _row_to_command(self, row: Dict[str, Any]) -> InspectionCommand:
        """Convert database row to InspectionCommand."""
        return InspectionCommand(
            command_id=row["command_id"],
            action=row["action"],
            name=row["name"],
            cron=row["cron"],
            targets=json.loads(row["targets"]) if row["targets"] else [],
            inspection_items=[
                InspectionCommand.model_validate(item)
                for item in (json.loads(row["inspection_items"]) if row["inspection_items"] else [])
            ],
            session_type=row.get("session_type", "isolated"),
            callback_url=row.get("callback_url"),
            priority=row.get("priority", 1),
            created_by=row.get("created_by"),
            status=row.get("status", "pending"),
            created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else datetime.fromisoformat(str(row["created_at"])),
            updated_at=row.get("updated_at") if isinstance(row.get("updated_at"), datetime) else datetime.fromisoformat(str(row["updated_at"])) if row.get("updated_at") else None,
            executed_at=row.get("executed_at") if isinstance(row.get("executed_at"), datetime) else datetime.fromisoformat(str(row["executed_at"])) if row.get("executed_at") else None,
            result=json.loads(row["result"]) if row.get("result") else None,
        )


class AuditRepository:
    """Repository for audit logs."""

    def __init__(self) -> None:
        """Initialize audit repository."""
        self._db = None

    async def _get_db(self):
        """Get database manager."""
        if self._db is None:
            self._db = await get_db_manager()
        return self._db

    async def create(self, audit_log: AuditLog) -> AuditLog:
        """Create a new audit log."""
        db = await self._get_db()

        sql = """
        INSERT INTO audit_logs
        (log_id, timestamp, operation_type, operator, target, input_data,
         output_data, status, error_msg, duration_ms)
        VALUES
        (:log_id, :timestamp, :operation_type, :operator, :target, :input_data,
         :output_data, :status, :error_msg, :duration_ms)
        """

        params = {
            "log_id": audit_log.log_id,
            "timestamp": audit_log.timestamp.isoformat(),
            "operation_type": audit_log.operation_type,
            "operator": audit_log.operator,
            "target": audit_log.target,
            "input_data": json.dumps(audit_log.input_data),
            "output_data": json.dumps(audit_log.output_data),
            "status": audit_log.status,
            "error_msg": audit_log.error_msg,
            "duration_ms": audit_log.duration_ms,
        }

        await db.execute_sql(sql, params)
        return audit_log

    async def get_by_id(self, log_id: str) -> Optional[AuditLog]:
        """Get audit log by ID."""
        db = await self._get_db()
        sql = "SELECT * FROM audit_logs WHERE log_id = :log_id"
        row = await db.fetch_one(sql, {"log_id": log_id})

        if row:
            return self._row_to_audit_log(row)
        return None

    async def list_by_operator(self, operator: str, limit: int = 100) -> List[AuditLog]:
        """List audit logs by operator."""
        db = await self._get_db()
        sql = "SELECT * FROM audit_logs WHERE operator = :operator ORDER BY timestamp DESC LIMIT :limit"
        rows = await db.fetch_all(sql, {"operator": operator, "limit": limit})
        return [self._row_to_audit_log(row) for row in rows]

    async def list_by_operation_type(self, operation_type: OperationType, limit: int = 100) -> List[AuditLog]:
        """List audit logs by operation type."""
        db = await self._get_db()
        sql = "SELECT * FROM audit_logs WHERE operation_type = :operation_type ORDER BY timestamp DESC LIMIT :limit"
        rows = await db.fetch_all(sql, {"operation_type": operation_type, "limit": limit})
        return [self._row_to_audit_log(row) for row in rows]

    def _row_to_audit_log(self, row: Dict[str, Any]) -> AuditLog:
        """Convert database row to AuditLog."""
        return AuditLog(
            log_id=row["log_id"],
            timestamp=row.get("timestamp") if isinstance(row.get("timestamp"), datetime) else datetime.fromisoformat(str(row["timestamp"])),
            operation_type=row["operation_type"],
            operator=row["operator"],
            target=row.get("target"),
            input_data=json.loads(row["input_data"]) if row.get("input_data") else {},
            output_data=json.loads(row["output_data"]) if row.get("output_data") else {},
            status=row["status"],
            error_msg=row.get("error_msg"),
            duration_ms=row.get("duration_ms", 0),
        )


class ClusterRepository:
    """Repository for cluster information."""

    def __init__(self) -> None:
        """Initialize cluster repository."""
        self._db = None

    async def _get_db(self):
        """Get database manager."""
        if self._db is None:
            self._db = await get_db_manager()
        return self._db

    async def create_cluster(self, cluster: ClusterInfo) -> ClusterInfo:
        """Create a new cluster."""
        db = await self._get_db()

        sql = """
        INSERT INTO clusters
        (cluster_name, cluster_type, prometheus_url, grafana_url, labels, description)
        VALUES
        (:cluster_name, :cluster_type, :prometheus_url, :grafana_url, :labels, :description)
        """

        params = {
            "cluster_name": cluster.cluster_name,
            "cluster_type": cluster.cluster_type,
            "prometheus_url": cluster.prometheus_url,
            "grafana_url": cluster.grafana_url,
            "labels": json.dumps(cluster.labels),
            "description": cluster.description,
        }

        await db.execute_sql(sql, params)
        return cluster

    async def get_cluster(self, cluster_name: str) -> Optional[ClusterInfo]:
        """Get cluster by name."""
        db = await self._get_db()
        sql = "SELECT * FROM clusters WHERE cluster_name = :cluster_name"
        row = await db.fetch_one(sql, {"cluster_name": cluster_name})

        if row:
            # Get servers for this cluster
            servers = await self.list_servers(cluster_name)
            return ClusterInfo(
                cluster_name=row["cluster_name"],
                cluster_type=row["cluster_type"],
                prometheus_url=row.get("prometheus_url"),
                grafana_url=row.get("grafana_url"),
                labels=json.loads(row["labels"]) if row.get("labels") else {},
                description=row.get("description"),
                servers=servers,
            )
        return None

    async def list_clusters(self) -> List[ClusterInfo]:
        """List all clusters."""
        db = await self._get_db()
        sql = "SELECT * FROM clusters ORDER BY cluster_name"
        rows = await db.fetch_all(sql)

        clusters = []
        for row in rows:
            servers = await self.list_servers(row["cluster_name"])
            clusters.append(
                ClusterInfo(
                    cluster_name=row["cluster_name"],
                    cluster_type=row["cluster_type"],
                    prometheus_url=row.get("prometheus_url"),
                    grafana_url=row.get("grafana_url"),
                    labels=json.loads(row["labels"]) if row.get("labels") else {},
                    description=row.get("description"),
                    servers=servers,
                )
            )
        return clusters

    async def add_server(self, server: ServerInfo) -> ServerInfo:
        """Add a server to a cluster."""
        db = await self._get_db()

        sql = """
        INSERT INTO servers
        (ip, port, username, password, private_key, os_type, role, cluster_name, labels)
        VALUES
        (:ip, :port, :username, :password, :private_key, :os_type, :role, :cluster_name, :labels)
        """

        params = {
            "ip": server.ip,
            "port": server.port,
            "username": server.username,
            "password": server.password,
            "private_key": server.private_key,
            "os_type": server.os_type,
            "role": json.dumps(server.role),
            "cluster_name": server.cluster_name,
            "labels": json.dumps(server.labels),
        }

        await db.execute_sql(sql, params)
        return server

    async def list_servers(self, cluster_name: str) -> List[ServerInfo]:
        """List servers in a cluster."""
        db = await self._get_db()
        sql = "SELECT * FROM servers WHERE cluster_name = :cluster_name"
        rows = await db.fetch_all(sql, {"cluster_name": cluster_name})

        return [
            ServerInfo(
                ip=row["ip"],
                port=row.get("port", 22),
                username=row["username"],
                password=row.get("password"),
                private_key=row.get("private_key"),
                os_type=row.get("os_type", "linux"),
                role=json.loads(row["role"]) if row.get("role") else [],
                cluster_name=row["cluster_name"],
                labels=json.loads(row["labels"]) if row.get("labels") else {},
            )
            for row in rows
        ]

    async def get_server(self, ip: str) -> Optional[ServerInfo]:
        """Get server by IP."""
        db = await self._get_db()
        sql = "SELECT * FROM servers WHERE ip = :ip"
        row = await db.fetch_one(sql, {"ip": ip})

        if row:
            return ServerInfo(
                ip=row["ip"],
                port=row.get("port", 22),
                username=row["username"],
                password=row.get("password"),
                private_key=row.get("private_key"),
                os_type=row.get("os_type", "linux"),
                role=json.loads(row["role"]) if row.get("role") else [],
                cluster_name=row["cluster_name"],
                labels=json.loads(row["labels"]) if row.get("labels") else {},
            )
        return None