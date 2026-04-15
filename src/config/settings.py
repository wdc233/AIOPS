"""Application settings with Pydantic Settings."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    enabled: bool = Field(default=True, description="Enable database connection")
    host: str = Field(default="localhost", description="StarRocks host")
    port: int = Field(default=9030, description="StarRocks port")
    user: str = Field(default="root", description="StarRocks user")
    password: str = Field(default="", description="StarRocks password")
    database: str = Field(default="aiops", description="Database name")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout seconds")
    echo: bool = Field(default=False, description="Echo SQL queries")

    @property
    def connection_string(self) -> str:
        """Get MySQL compatible connection string for StarRocks."""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class LLMSettings(BaseSettings):
    """LLM configuration."""

    provider: str = Field(default="openai", description="LLM provider: openai, anthropic, local")
    api_key: Optional[str] = Field(None, description="API key for LLM")
    base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible API")
    model: str = Field(default="gpt-4", description="Model name")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    max_tokens: int = Field(default=2048, description="Max tokens to generate")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    # For low-cost heartbeat
    heartbeat_model: str = Field(default="gpt-3.5-turbo", description="Model for heartbeat tasks")
    heartbeat_temperature: float = Field(default=0.3, description="Temperature for heartbeat")


class SSHSettings(BaseSettings):
    """SSH configuration."""

    timeout: int = Field(default=30, description="SSH connection timeout")
    command_timeout: int = Field(default=300, description="Command execution timeout")
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, description="Retry delay seconds")


class PrometheusSettings(BaseSettings):
    """Prometheus configuration."""

    url: str = Field(default="http://localhost:9090", description="Prometheus URL")
    timeout: int = Field(default=10, description="Request timeout")


class GrafanaSettings(BaseSettings):
    """Grafana configuration."""

    url: str = Field(default="http://localhost:3000", description="Grafana URL")
    api_key: Optional[str] = Field(None, description="Grafana API key")
    timeout: int = Field(default=10, description="Request timeout")


class WebSocketSettings(BaseSettings):
    """WebSocket server configuration."""

    host: str = Field(default="0.0.0.0", description="WebSocket host")
    port: int = Field(default=8765, description="WebSocket port")
    ping_interval: int = Field(default=30, description="Ping interval seconds")
    ping_timeout: int = Field(default=10, description="Ping timeout seconds")


class SchedulerSettings(BaseSettings):
    """Scheduler configuration."""

    heartbeat_interval: int = Field(default=1800, description="Heartbeat interval in seconds (30 min)")
    cron_enabled: bool = Field(default=True, description="Enable cron scheduler")
    max_concurrent_tasks: int = Field(default=10, description="Max concurrent tasks")


class APISettings(BaseSettings):
    """FastAPI server configuration."""

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, description="API port")
    workers: int = Field(default=1, description="Number of worker processes")
    reload: bool = Field(default=False, description="Enable auto-reload for development")


class AgentSettings(BaseSettings):
    """Agent configuration."""

    agent_id: str = Field(default="aiops-agent-001", description="Unique agent ID")
    name: str = Field(default="AIOPS Agent", description="Agent name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    prometheus: PrometheusSettings = Field(default_factory=PrometheusSettings)
    grafana: GrafanaSettings = Field(default_factory=GrafanaSettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    api: APISettings = Field(default_factory=APISettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)

    # Environment file path
    env_file_path: Optional[str] = Field(None, description="Custom env file path")

    # Cluster config file path (for loading cluster/server info without database)
    cluster_config_path: Optional[str] = Field(
        None,
        description="Path to cluster config JSON file",
    )

    def __init__(self, **data: Any) -> None:
        # Support custom env file path before base init reads it
        env_file_path = data.get("env_file_path")
        if env_file_path and os.path.exists(env_file_path):
            data["env_file"] = env_file_path
        super().__init__(**data)

    def reload(self) -> None:
        """Reload settings from environment variables."""
        # Clear cached settings
        get_settings.cache_clear()


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def load_clusters_from_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load cluster configuration from JSON/YAML file."""
    path = Path(file_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                return json.load(f)
            return {}
    except FileNotFoundError:
        return {}


def save_clusters_to_file(file_path: Union[str, Path], data: Dict[str, Any]) -> None:
    """Save cluster configuration to JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)