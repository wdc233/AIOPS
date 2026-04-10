# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIOPS is an intelligent operations Agent system built on LangChain, supporting dynamic task dispatch via instruction bus, with three scheduling modes: heartbeat self-check, scheduled Cron, and immediate execution. Also supports user interactive input and intelligent intent recognition.

## Common Commands

```bash
# Run the main application
python src/main.py

# Run with custom API port
python src/main.py --api-port 8080

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_specific.py::test_name -v

# Type checking
mypy src/

# Format code
black src/
ruff check src/
```

## FastAPI REST API

AIOPS exposes REST APIs via FastAPI for external integrations (e.g., frontend).

### Configuration

API settings in `.env` or environment variables:
```bash
API__HOST=0.0.0.0
API__PORT=8000
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | User dialogue with multi-round conversation |
| POST | `/api/v1/inspection/run` | Trigger immediate inspection |
| POST | `/api/v1/prediction/risk` | Get trend-based risk prediction |

### API Input Patterns

- **Inspection/Prediction Targets**: Support cluster name, server IPs, or Prometheus metric URL
- **Target Resolution**: If no IP specified, query environment info table to get IP list
- **Metric Resolution**: Query all metrics for target if none specified; return error if metric not found in Prometheus

### WebSocket Coexistence

FastAPI runs in the same process as the existing agent. Uvicorn starts in a subthread, sharing the event loop with heartbeat/scheduler/WebSocket services.

## Architecture

### Four-Layer Architecture

1. **Control Plane**: Instruction bus + task persistence + flow orchestration + audit logs
2. **Agent Runtime**: LangChain ReAct Agent + toolchain + LLM intent recognition sub-agent
3. **Tool Layer**: SSH, command execution, log analysis, Prometheus/Grafana API, LLM trend prediction, alert webhook
4. **Environment Layer**: Global cluster information management

### Key Design Patterns

- **Instruction Bus**: StarRocks persistence + pub/sub with state machine (pending→running→completed/failed)
- **Session Isolation**: Each inspection task has independent session, user interaction maintains context
- **Lane Lock**: Same target server executes serially to prevent concurrent SSH storms
- **Heartbeat**: Lightweight self-check every 30 minutes using low-cost inference
- **Dual-mode Scheduling**: Heartbeat-driven + Cron trigger
- **Intent Recognition Sub-Agent**: Handles natural language input with multi-round dialogue
- **Audit Logging**: Full链路 operation records to StarRocks

### LangChain Implementation

- **Main Agent**: LangGraph StateGraph with nodes: observe → analyze → predict → decide → act → report
- **Intent Recognition Agent**: Independent StateGraph with nodes: intent_parse → slot_check → tool_select → confirm
- **Memory**: ConversationBufferMemory for user sessions, inspection tasks use isolated sessions

## Required Tools

- `SSHCommandTool`: Execute commands on remote servers
- `LogAnalysisTool`: Analyze log files with regex and anomaly detection
- `PrometheusQueryTool`: Query Prometheus metrics with PromQL
- `GrafanaQueryTool`: Query Grafana dashboards and data sources
- `TrendPredictionTool`: Predict trend risks using LLM or statistical models
- `AlertWebhookTool`: Call existing webhook URLs for alerts
- `EnvironmentQueryTool`: Query global environment info, cluster/server metadata

## Data Models

Key Pydantic models defined in requirements:
- `InspectionCommand`: Inspection task command with schedule/run_now/cancel/update actions
- `UserIntent`: User interaction intent with slot filling (target_cluster, target_ip, metric_name, etc.)
- `ClusterInfo` / `ServerInfo`: Global environment information
- `AuditLog`: Full链路 operation records

## Technical Requirements

- **Async**: All code must use async/await, StarRocks uses async connection pool
- **Type Hints**: Full type annotations passing mypy
- **Logging**: Structured logging with structlog or JSON format
- **Config**: Pydantic Settings, support environment variables, hot reload without restart
- **Graceful Shutdown**: SIGTERM handling, complete current task before exit
- **Database**: Connection pool required, parameterized queries to prevent SQL injection

## Prohibited Practices

- Do NOT use deprecated LangChain APIs (e.g., LLMChain)
- Do NOT use blocking `time.sleep()` or sync HTTP requests in Agent
- Do NOT leak database connections to global scope
- Do NOT hardcode secrets; use environment variables or key management service
- Do NOT store passwords in plaintext; must encrypt

## Docker

Project should include:
- `Dockerfile`: Agent container image
- `docker-compose.yml`: Includes StarRocks service

## References

- OpenClaw: SQLite-backed task ledger and lane design
- XXL-JOB: Distributed scheduling with Agent autonomous heartbeat
- Rasa/Dialogflow: Slot filling mechanism for intent recognition