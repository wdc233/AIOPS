"""Tests for AIOPS."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.types import (
    CommandAction,
    CommandStatus,
    InspectionCommand,
    InspectionItem,
    IntentType,
    UserIntent,
    ClusterInfo,
    ServerInfo,
    ClusterType,
    OSType,
)


class TestModels:
    """Test data models."""

    def test_inspection_command_creation(self):
        """Test creating an inspection command."""
        command = InspectionCommand(
            command_id="test-001",
            action=CommandAction.SCHEDULE,
            name="Test Inspection",
            targets=["192.168.1.1", "192.168.1.2"],
            inspection_items=[
                InspectionItem(check_type="cpu", target_metric="cpu_usage", threshold="80"),
                InspectionItem(check_type="memory", target_metric="memory_usage", threshold="90"),
            ],
            cron="0 */6 * * *",
            priority=1,
        )

        assert command.command_id == "test-001"
        assert command.action == CommandAction.SCHEDULE
        assert len(command.targets) == 2
        assert len(command.inspection_items) == 2
        assert command.status == CommandStatus.PENDING

    def test_user_intent_creation(self):
        """Test creating a user intent."""
        intent = UserIntent(
            intent_type=IntentType.QUERY_METRIC,
            target_ip="192.168.1.1",
            metric_name="cpu",
            time_range="1h",
            confidence=0.95,
        )

        assert intent.intent_type == IntentType.QUERY_METRIC
        assert intent.target_ip == "192.168.1.1"
        assert intent.metric_name == "cpu"
        assert intent.confidence == 0.95

    def test_cluster_info_creation(self):
        """Test creating cluster info."""
        cluster = ClusterInfo(
            cluster_name="prod-cluster",
            cluster_type=ClusterType.K8S,
            servers=[
                ServerInfo(
                    ip="192.168.1.1",
                    port=22,
                    username="admin",
                    password="password",
                    os_type=OSType.LINUX,
                    role=["web", "api"],
                    cluster_name="prod-cluster",
                ),
            ],
            prometheus_url="http://prometheus:9090",
            grafana_url="http://grafana:3000",
        )

        assert cluster.cluster_name == "prod-cluster"
        assert cluster.cluster_type == ClusterType.K8S
        assert len(cluster.servers) == 1
        assert cluster.servers[0].ip == "192.168.1.1"


class TestInstructionBus:
    """Test instruction bus."""

    @pytest.mark.asyncio
    async def test_publish_command(self):
        """Test publishing a command."""
        with patch("src.bus.bus.CommandRepository") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.create = AsyncMock()
            mock_repo.return_value = mock_instance

            from src.bus.bus import InstructionBus

            bus = InstructionBus()
            bus._command_repo = mock_instance

            command = await bus.publish_command(
                action=CommandAction.RUN_NOW,
                name="Test Command",
                targets=["192.168.1.1"],
                created_by="test_user",
            )

            assert command.name == "Test Command"
            mock_instance.create.assert_called_once()


class TestLaneLock:
    """Test lane lock."""

    @pytest.mark.asyncio
    async def test_lock_acquire_release(self):
        """Test acquiring and releasing lock."""
        from src.bus.lane_lock import LaneLock

        lock = LaneLock()

        # Acquire lock
        lock1 = await lock.acquire("192.168.1.1")
        assert lock1 is not None

        # Same target should return same lock
        lock2 = await lock.acquire("192.168.1.1")
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test lock context manager."""
        from src.bus.lane_lock import LaneLock

        lock = LaneLock()
        executed = False

        async with lock.lock("192.168.1.1"):
            executed = True

        assert executed is True


class TestIntentRecognition:
    """Test intent recognition."""

    @pytest.mark.asyncio
    async def test_intent_creation(self):
        """Test creating user intent with missing slots."""
        intent = UserIntent(
            intent_type=IntentType.QUERY_METRIC,
            raw_input="查看 CPU",
            missing_slots=["target_ip"],
            confidence=0.8,
        )

        assert intent.intent_type == IntentType.QUERY_METRIC
        assert "target_ip" in intent.missing_slots
        assert intent.confidence == 0.8


class TestTools:
    """Test tools."""

    @pytest.mark.asyncio
    async def test_tool_result(self):
        """Test tool result."""
        from src.tools.base import ToolResult

        result = ToolResult(
            success=True,
            data={"key": "value"},
            duration_ms=100,
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.duration_ms == 100

        # Test to_dict
        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_ssh_command_schema(self):
        """Test SSH command tool schema."""
        from src.tools.ssh import SSHCommandTool

        tool = SSHCommandTool()
        schema = tool.get_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "ssh_command"
        assert "host" in schema["function"]["parameters"]["required"]


class TestScheduler:
    """Test scheduler."""

    @pytest.mark.asyncio
    async def test_cron_validation(self):
        """Test cron expression validation."""
        # Valid cron expressions
        valid_crons = [
            "0 * * * *",  # Every hour
            "*/5 * * * *",  # Every 5 minutes
            "0 0 * * *",  # Daily at midnight
        ]

        for cron in valid_crons:
            from croniter import croniter
            from datetime import datetime

            assert croniter.is_valid(cron) is True


class TestAgentState:
    """Test agent state transitions."""

    def test_command_status_transitions(self):
        """Test command status transitions."""
        command = InspectionCommand(
            command_id="test-001",
            action=CommandAction.RUN_NOW,
            name="Test",
            targets=["192.168.1.1"],
        )

        assert command.status == CommandStatus.PENDING

        # Simulate status change
        command.status = CommandStatus.RUNNING
        assert command.status == CommandStatus.RUNNING

        command.status = CommandStatus.COMPLETED
        assert command.status == CommandStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])