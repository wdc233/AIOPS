"""Async database connection manager for StarRocks."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool

from src.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async database manager for StarRocks."""

    def __init__(self, connection_string: str, pool_size: int = 10, max_overflow: int = 20, pool_timeout: int = 30, echo: bool = False) -> None:
        """Initialize database manager.

        Args:
            connection_string: MySQL connection string
            pool_size: Connection pool size
            max_overflow: Max overflow connections
            pool_timeout: Pool timeout seconds
            echo: Echo SQL queries
        """
        # Convert mysql+pymysql to mysql+aiomysql for async
        async_connection_string = connection_string.replace("mysql+pymysql", "mysql+aiomysql")

        self._engine: Optional[AsyncEngine] = None
        self._sync_engine = None
        self._connection_string = connection_string
        self._async_connection_string = async_connection_string
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_timeout = pool_timeout
        self._echo = echo
        self._session_factory: Optional[sessionmaker] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        if self._initialized:
            return

        try:
            # Try aiomysql first for async support
            # Use NullPool for async engine (QueuePool not compatible)
            self._engine = create_async_engine(
                self._async_connection_string,
                poolclass=NullPool,
                echo=self._echo,
            )
            self._session_factory = sessionmaker(
                self._engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info("Async database engine initialized")
        except ImportError:
            # Fallback to sync engine if aiomysql not available
            logger.warning("aiomysql not available, using sync engine")
            self._sync_engine = create_engine(
                self._connection_string,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_timeout=self._pool_timeout,
                echo=self._echo,
                poolclass=QueuePool,
            )
            self._session_factory = sessionmaker(
                self._sync_engine, class_=Session, expire_on_commit=False
            )

        self._initialized = True
        await self._create_tables()

    async def _create_tables(self) -> None:
        """Create required tables if not exist."""
        await self.execute_sql(COMMANDS_TABLE_SQL)
        await self.execute_sql(AUDIT_LOGS_TABLE_SQL)
        await self.execute_sql(CLUSTERS_TABLE_SQL)
        await self.execute_sql(SERVERS_TABLE_SQL)
        logger.info("Database tables initialized")

    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
        if self._sync_engine:
            self._sync_engine.dispose()
        self._initialized = False
        logger.info("Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context manager."""
        if not self._initialized:
            await self.initialize()

        if self._session_factory is None:
            raise RuntimeError("Database not initialized")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute raw SQL."""
        if not self._initialized:
            await self.initialize()

        if self._engine:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})
                await conn.commit()
                return result
        elif self._sync_engine:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                conn.commit()
                return result
        else:
            raise RuntimeError("No database engine available")

    async def fetch_one(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch one row."""
        if not self._initialized:
            await self.initialize()

        if self._engine:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})
                row = result.fetchone()
                if row:
                    return dict(result._metadata._keys, **row._mapping)
                return None
        elif self._sync_engine:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                row = result.fetchone()
                if row:
                    return dict(result._metadata._keys, **row._mapping)
                return None
        return None

    async def fetch_all(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        if not self._initialized:
            await self.initialize()

        if self._engine:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})
                rows = result.fetchall()
                return [dict(result._metadata._keys, **row._mapping) for row in rows]
        elif self._sync_engine:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                rows = result.fetchall()
                return [dict(result._metadata._keys, **row._mapping) for row in rows]
        return []

    async def execute_many(self, sql: str, params_list: List[Dict[str, Any]]) -> None:
        """Execute batch SQL."""
        if not self._initialized:
            await self.initialize()

        if self._engine:
            async with self._engine.connect() as conn:
                for params in params_list:
                    await conn.execute(text(sql), params)
                await conn.commit()
        elif self._sync_engine:
            with self._sync_engine.connect() as conn:
                for params in params_list:
                    conn.execute(text(sql), params)
                conn.commit()


# Table creation SQL
COMMANDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS inspection_commands (
    command_id VARCHAR(64) PRIMARY KEY,
    action VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    cron VARCHAR(64),
    targets JSON,
    inspection_items JSON,
    session_type VARCHAR(32) DEFAULT 'isolated',
    callback_url VARCHAR(512),
    priority INT DEFAULT 1,
    created_by VARCHAR(128),
    status VARCHAR(32) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    executed_at DATETIME,
    result JSON,
    INDEX idx_status (status),
    INDEX idx_cron (cron),
    INDEX idx_created_at (created_at)
) ENGINE=OLAP
DUPLICATE KEY(command_id)
COMMENT='Inspection commands table'
DISTRIBUTED BY HASH(command_id) BUCKETS 10;
"""

AUDIT_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    operation_type VARCHAR(32) NOT NULL,
    operator VARCHAR(128) NOT NULL,
    target VARCHAR(512),
    input_data JSON,
    output_data JSON,
    status VARCHAR(16) NOT NULL,
    error_msg TEXT,
    duration_ms INT DEFAULT 0,
    INDEX idx_operation_type (operation_type),
    INDEX idx_operator (operator),
    INDEX idx_timestamp (timestamp)
) ENGINE=OLAP
DUPLICATE KEY(log_id)
COMMENT='Audit logs table'
DISTRIBUTED BY HASH(log_id) BUCKETS 10;
"""

CLUSTERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS clusters (
    cluster_name VARCHAR(128) PRIMARY KEY,
    cluster_type VARCHAR(32) NOT NULL,
    prometheus_url VARCHAR(512),
    grafana_url VARCHAR(512),
    labels JSON,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=OLAP
DUPLICATE KEY(cluster_name)
COMMENT='Cluster information table'
DISTRIBUTED BY HASH(cluster_name) BUCKETS 10;
"""

SERVERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS servers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ip VARCHAR(64) NOT NULL,
    port INT DEFAULT 22,
    username VARCHAR(128) NOT NULL,
    password VARCHAR(512),
    private_key TEXT,
    os_type VARCHAR(16) DEFAULT 'linux',
    role JSON,
    cluster_name VARCHAR(128) NOT NULL,
    labels JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cluster (cluster_name),
    INDEX idx_ip (ip)
) ENGINE=OLAP
DUPLICATE KEY(id)
COMMENT='Server information table'
DISTRIBUTED BY HASH(cluster_name) BUCKETS 10;
"""

# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_db_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        _db_manager = DatabaseManager(
            connection_string=settings.database.connection_string,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            echo=settings.database.echo,
        )
        await _db_manager.initialize()
    return _db_manager


async def close_db_manager() -> None:
    """Close global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None