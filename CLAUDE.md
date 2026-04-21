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

# Run tests excluding integration tests
pytest tests/ -v --ignore=tests/test_chat.py --ignore=tests/test_intent.py

# Type checking
mypy src/

# Format code
black src/
ruff check src/
```

## Project Structure

```
src/
├── agent/
│   ├── main_agent.py           # Main Agent (LangGraph StateGraph)
│   ├── intent_agent.py         # Intent Recognition Agent
│   ├── single_metric_inspector.py  # Single metric inspection with LLM
│   └── templates.py            # Response templates
├── api/
│   ├── routes/
│   │   ├── chat.py            # /api/v1/chat endpoint
│   │   ├── inspection.py       # /api/v1/inspection/run
│   │   └── prediction.py      # /api/v1/prediction/risk
│   ├── schemas.py             # Pydantic request/response models
│   └── dependencies.py         # DI (APIService, SessionManager)
├── config/
│   ├── settings.py            # Pydantic Settings
│   └── constants.py           # BASIC_METRICS, SSH_COMMANDS
├── tools/
│   ├── ssh.py                 # SSHCommandTool
│   ├── prometheus.py          # PrometheusQueryTool
│   ├── trend.py               # TrendPredictionTool
│   └── ...
└── main.py                   # Entry point
```

## FastAPI REST API

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | User dialogue with multi-round conversation |
| POST | `/api/v1/inspection/run` | Trigger immediate inspection |
| POST | `/api/v1/prediction/risk` | Get trend-based risk prediction |

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

### Intent Recognition System

**Intent Types**:
- `CHAT`: User greetings/identity questions - direct LLM response, no tool call
- `QUERY_INFO`: Cluster/server info query - tools: environment_query
- `QUERY_METRIC`: **Single metric inspection with LLM analysis** - tools: ssh_command / prometheus_query + LLM
- `CHECK_STATUS`: Server status check - tools: ssh_command + log_analysis
- `RUN_INSPECTION`: Full cluster inspection - tools: ssh_command + log_analysis + prometheus_query
- `PREDICT_RISK`: **Risk prediction** (single or full metrics) - tools: trend_prediction

**Confidence-Based Execution**:
- ≥ 0.9: Execute directly without confirmation
- 0.7 - 0.9: Execute after user confirmation
- 0.5 - 0.7: Present multiple intent options for user selection
- < 0.5: Fallback response with suggestions

**Slot Filling**:
- User input → cluster.json lookup → follow-up question
- When target not specified: shows ASK_CLUSTER_LIST with all available clusters for user to select
- When metric not found: shows similar metric suggestions

**Strategy Templates** (in `src/agent/templates.py`):
- Pre-defined response templates (not LLM-generated)
- Each intent type has corresponding template for confirmation and result messages

**Fallback Response**:
- "我好像没有理解您的需求。您可以尝试这样说：'检查 prod-cluster 的健康状况'、'查看 CPU 使用率' 或 '预测磁盘容量风险'。"

## Tools

| Tool | File | Description |
|------|------|-------------|
| `SSHCommandTool` | `src/tools/ssh.py` | Execute commands via SSH |
| `LogAnalysisTool` | `src/tools/log_analysis.py` | Log analysis with regex |
| `PrometheusQueryTool` | `src/tools/prometheus.py` | Query Prometheus metrics |
| `GrafanaQueryTool` | `src/tools/grafana.py` | Query Grafana dashboards |
| `TrendPredictionTool` | `src/tools/trend.py` | Trend prediction (stats + LLM) |
| `AlertWebhookTool` | `src/tools/alert.py` | Send alerts via webhook |
| `EnvironmentQueryTool` | `src/tools/env_query.py` | Query cluster/server info |
| `SingleMetricInspector` | `src/agent/single_metric_inspector.py` | Single metric + LLM analysis |

## Data Models

Key Pydantic models in `src/api/schemas.py` and `src/models/types.py`:
- `InspectionCommand`: Inspection task command with schedule/run_now/cancel/update actions
- `UserIntent`: User interaction intent with slot filling (target_cluster, target_ip, metric_name, etc.)
- `ClusterInfo`: Global environment information (cluster_name, cluster_type, env, servers, prometheus_url)
- `ServerInfo`: Server information (ip, port, username, password, cluster_name)

## Constants

**Basic Metrics** (`src/config/constants.py`):
```python
BASIC_METRICS = ["cpu", "memory", "disk", "network"]

SSH_COMMANDS = {
    "cpu": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
    "memory": "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'",
    "disk": "df -h | awk '$NF==\"/\"{print $5}' | cut -d'%' -f1",
    "network": "cat /proc/net/dev | awk 'NR>2{sum+=$10} END{print sum/1024/1024}'",
}
```

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

- `Dockerfile`: Agent container image (python:3.11-slim)
- `docker-compose.yml`: Includes StarRocks, Prometheus, Grafana services

## Deployment

- **Online**: `pip install -r requirements.txt && python src/main.py`
- **Offline**: `python run_offline.py` (extracts whl files to temp dir, no pip needed)
- See `README_OFFLINE.md` for detailed offline deployment guide

## References

- OpenClaw: SQLite-backed task ledger and lane design
- XXL-JOB: Distributed scheduling with Agent autonomous heartbeat
- Rasa/Dialogflow: Slot filling mechanism for intent recognition
