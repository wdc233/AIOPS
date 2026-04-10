"""Core data models for AIOPS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CommandAction(str, Enum):
    """Inspection command action types."""

    SCHEDULE = "schedule"
    RUN_NOW = "run_now"
    CANCEL = "cancel"
    UPDATE = "update"


class CommandStatus(str, Enum):
    """Inspection command status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionType(str, Enum):
    """Session type for inspection tasks."""

    ISOLATED = "isolated"
    PERSISTENT = "persistent"


class ClusterType(str, Enum):
    """Cluster type."""

    K8S = "k8s"
    VM = "vm"
    BARE_METAL = "baremetal"


class OSType(str, Enum):
    """Operating system type."""

    LINUX = "linux"
    WINDOWS = "windows"


class IntentType(str, Enum):
    """User intent types."""

    QUERY_METRIC = "query_metric"
    CHECK_STATUS = "check_status"
    RUN_INSPECTION = "run_inspection"
    UNKNOWN = "unknown"


class OperationType(str, Enum):
    """Audit log operation types."""

    COMMAND_PUBLISH = "command_publish"
    INSPECTION_RUN = "inspection_run"
    USER_QUERY = "user_query"
    TOOL_CALL = "tool_call"
    ALERT_SEND = "alert_send"


class AuditStatus(str, Enum):
    """Audit log status."""

    SUCCESS = "success"
    FAILURE = "failure"


# --- Inspection Models ---


class InspectionItem(BaseModel):
    """Individual inspection item."""

    check_type: str = Field(..., description="Type of check: cpu, memory, disk, network, etc.")
    target_metric: Optional[str] = Field(None, description="Target metric name")
    threshold: Optional[str] = Field(None, description="Threshold value or expression")
    description: Optional[str] = Field(None, description="Description of this check")


class InspectionCommand(BaseModel):
    """Inspection command model."""

    command_id: str = Field(..., description="Unique command ID")
    action: CommandAction = Field(..., description="Command action: schedule, run_now, cancel, update")
    name: str = Field(..., description="Command name")
    cron: Optional[str] = Field(None, description="Cron expression for scheduled tasks")
    targets: List[str] = Field(..., description="Target server IPs")
    inspection_items: List[InspectionItem] = Field(default_factory=list, description="Items to inspect")
    session_type: SessionType = Field(default=SessionType.ISOLATED, description="Session type")
    callback_url: Optional[str] = Field(None, description="Callback URL for result notification")
    priority: int = Field(default=1, description="Priority level")
    created_by: Optional[str] = Field(None, description="Creator: user or system")
    status: CommandStatus = Field(default=CommandStatus.PENDING, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    executed_at: Optional[datetime] = Field(None, description="Execution timestamp")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution result")

    model_config = {"use_enum_values": True}


# --- User Intent Models ---


class UserIntent(BaseModel):
    """User interaction intent model."""

    intent_type: IntentType = Field(default=IntentType.UNKNOWN, description="Intent type")
    target_cluster: Optional[str] = Field(None, description="Target cluster name")
    target_ip: Optional[str] = Field(None, description="Target server IP")
    metric_name: Optional[str] = Field(None, description="Metric name")
    time_range: Optional[str] = Field(None, description="Time range: 1h, 24h, 7d, etc.")
    missing_slots: List[str] = Field(default_factory=list, description="Missing information slots")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Intent confidence score")
    raw_input: Optional[str] = Field(None, description="Raw user input")

    model_config = {"use_enum_values": True}


# --- Environment Models ---


class ServerInfo(BaseModel):
    """Server information model."""

    ip: str = Field(..., description="Server IP address")
    port: int = Field(default=22, description="SSH port")
    username: str = Field(..., description="SSH username")
    password: Optional[str] = Field(None, description="SSH password (encrypted)")
    private_key: Optional[str] = Field(None, description="SSH private key path")
    os_type: OSType = Field(default=OSType.LINUX, description="Operating system type")
    role: List[str] = Field(default_factory=list, description="Server roles: web, db, cache, etc.")
    cluster_name: str = Field(..., description="Cluster name this server belongs to")
    labels: Dict[str, str] = Field(default_factory=dict, description="Custom labels")

    model_config = {"use_enum_values": True}


class ClusterInfo(BaseModel):
    """Cluster information model."""

    cluster_name: str = Field(..., description="Cluster name")
    cluster_type: ClusterType = Field(..., description="Cluster type")
    servers: List[ServerInfo] = Field(default_factory=list, description="Servers in this cluster")
    prometheus_url: Optional[str] = Field(None, description="Prometheus URL")
    grafana_url: Optional[str] = Field(None, description="Grafana URL")
    labels: Dict[str, str] = Field(default_factory=dict, description="Custom labels")
    description: Optional[str] = Field(None, description="Cluster description")

    model_config = {"use_enum_values": True}


# --- Audit Models ---


class AuditLog(BaseModel):
    """Audit log model."""

    log_id: str = Field(..., description="Unique log ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Operation timestamp")
    operation_type: OperationType = Field(..., description="Operation type")
    operator: str = Field(..., description="Operator: user_id or agent_id")
    target: Optional[str] = Field(None, description="Target resource")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Output data")
    status: AuditStatus = Field(..., description="Operation status")
    error_msg: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: int = Field(default=0, description="Duration in milliseconds")

    model_config = {"use_enum_values": True}


# --- Agent State Models ---


class AgentState(str, Enum):
    """Agent running state."""

    IDLE = "idle"
    RUNNING = "running"
    HEARTBEAT = "heartbeat"
    STOPPING = "stopping"


class HeartbeatInfo(BaseModel):
    """Heartbeat information."""

    agent_id: str = Field(..., description="Agent ID")
    status: AgentState = Field(default=AgentState.IDLE, description="Current status")
    current_task: Optional[str] = Field(None, description="Current task ID")
    last_heartbeat: datetime = Field(default_factory=datetime.now, description="Last heartbeat time")
    tasks_completed: int = Field(default=0, description="Tasks completed count")
    tasks_failed: int = Field(default=0, description="Tasks failed count")

    model_config = {"use_enum_values": True}


# --- Tool Result Models ---


class ToolResult(BaseModel):
    """Base tool execution result."""

    success: bool = Field(..., description="Execution success")
    data: Any = Field(None, description="Result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: int = Field(default=0, description="Execution duration")