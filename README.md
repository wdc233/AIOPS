# AIOPS - Intelligent Operations Agent

基于 LangChain 的智能运维 Agent 系统，支持通过指令总线动态下发巡检任务，具备心跳自检、定时 Cron、即时执行三种调度模式，同时支持用户交互式指令输入和智能意图识别。

## 核心特性

- **意图识别**：智能识别用户自然语言指令（巡检、查询、预测等）
- **单指标巡检**：支持对 CPU、内存、磁盘、网络等基础指标进行单指标巡检 + LLM 分析
- **风险预测**：基于历史数据的趋势预测，支持单指标和全量指标预测
- **相似指标建议**：当指定指标不存在时，自动推荐相似指标
- **三层调度模式**：心跳自检 (30分钟) + Cron 定时 + 即时执行
- **指令总线**：StarRocks 持久化，支持状态机 (pending→running→completed/failed)
- **会话隔离**：巡检任务独立 Session，用户交互保持上下文
- **车道锁**：同一目标服务器串行执行，防止 SSH 并发风暴
- **LangGraph**：主 Agent (observe→analyze→predict→decide→act→report)

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         User 用户                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Communication Layer 通信层                      │
│         WebSocket (ws://localhost:8765) / REST API             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Control Plane 控制平面                         │
│   Instruction Bus  │ Task Persistence │ Flow Orchestration │ Audit │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Agent Runtime 执行引擎                           │
│  ┌──────────────────┐        ┌──────────────────┐              │
│  │   Main Agent     │        │ Intent Agent    │              │
│  │ (observe→analyze │        │ (意图识别+槽位填充│              │
│  │  →predict→decide │        │  +工具选择+确认)  │              │
│  │  →act→report)    │        └──────────────────┘              │
│  └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Layer 工具层                           │
│  SSHCommand │ LogAnalysis │ Prometheus │ Grafana │ Trend │ Alert │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Environment Layer 环境层                         │
│              Cluster Info │ Server Info │ Prometheus           │
└─────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置要求

- Python 3.10+ (推荐 3.11)
- StarRocks / MySQL (可选，DATABASE__ENABLED=false 可使用本地文件)
- OpenAI API Key (或其他兼容 LLM)

### 安装依赖

**在线安装**
```bash
pip install -r requirements.txt
```

**离线安装（内网环境）**
```bash
# 方式一: pip 离线安装
pip install --no-index --find-links=./lib/site-packages/ -r requirements.txt

# 方式二: 无 pip，直接运行
python run_offline.py
```

### 配置

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env
vim .env
```

**关键配置**
```ini
# LLM 配置（必须）
LLM__PROVIDER=openai
LLM__API_KEY=your-api-key
LLM__BASE_URL=https://api.openai.com/v1  # 内网代理地址

# 数据库配置（可选）
DATABASE__ENABLED=false  # false 时使用本地 clusters.json

# Prometheus 配置（可选）
PROMETHEUS__URL=http://localhost:9090
```

### 启动

```bash
# 直接运行
python src/main.py

# 指定端口
python src/main.py --api-port 8080

# 离线模式（无 pip）
python run_offline.py
```

### Docker 运行

```bash
cd docker
docker-compose up -d
```

---

## 功能说明

### 1. 意图识别

支持以下意图类型：

| 意图类型 | 示例 | 说明 |
|---------|------|------|
| `CHAT` | "你好"、"你是谁" | 闲聊/助手身份 |
| `QUERY_INFO` | "test-cluster有几台服务器" | 查询集群信息 |
| `QUERY_METRIC` | "查看CPU使用率" | **单指标巡检 + LLM分析** |
| `CHECK_STATUS` | "检查192.168.1.1状态" | 状态检查 |
| `RUN_INSPECTION` | "运行巡检" | 全量巡检 |
| `PREDICT_RISK` | "预测磁盘容量风险" | **趋势预测（单指标/全量）** |

### 2. 单指标巡检

用户说"检查 CPU"，系统会：

1. **槽位检查** → 列出所有集群供用户选择
2. **指标获取**：
   - 基础指标 (cpu/memory/disk/network) → **SSH 远程执行命令**
   - 其他指标 → **Prometheus 查询**
3. **LLM 分析** → 生成巡检报告

### 3. 风险预测

**单指标预测**：
```
用户: "预测 prod-cluster 的 CPU 风险"
→ 检查 CPU 指标是否存在
→ 存在 → 执行预测
→ 不存在 → 推荐相似指标（如 cpu_usage）→ 用户确认后执行
```

**全量预测**：
```
用户: "预测 prod-cluster 有无异常风险"
→ 自动对 cpu_usage、memory_usage、disk_usage 执行预测
→ 返回综合风险等级和每指标详细结果
```

### 4. 集群配置

`DATABASE__ENABLED=false` 时使用本地 JSON 配置：

```json
{
  "clusters": [
    {
      "cluster_name": "prod-cluster",
      "cluster_type": "starrocks",
      "env": "prd",
      "prometheus_url": "http://prometheus:9090",
      "servers": [
        {
          "ip": "192.168.1.100",
          "port": 22,
          "username": "root",
          "password": "xxx"
        }
      ]
    }
  ]
}
```

---

## API 接口

### REST API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/chat` | 用户对话 |
| POST | `/api/v1/inspection/run` | 触发即时巡检 |
| POST | `/api/v1/prediction/risk` | 风险预测 |

### WebSocket

连接 `ws://localhost:8000/ws`

```json
// 发送指令
{"type": "command", "action": "run_now", "targets": ["192.168.1.1"], "inspection_items": [...]}

// 用户查询
{"type": "user_query", "content": "查看 CPU"}
```

---

## 工具列表

| 工具 | 说明 |
|------|------|
| `SSHCommandTool` | SSH 远程命令执行 |
| `LogAnalysisTool` | 日志分析，支持正则和异常检测 |
| `PrometheusQueryTool` | Prometheus 指标查询 |
| `GrafanaQueryTool` | Grafana 仪表盘查询 |
| `TrendPredictionTool` | **趋势预测**（统计 + LLM） |
| `AlertWebhookTool` | 告警通知 |
| `EnvironmentQueryTool` | 环境信息查询 |
| `SingleMetricInspector` | **单指标巡检 + LLM 分析** |

---

## 项目结构

```
AIOPS/
├── src/
│   ├── agent/              # Agent 层
│   │   ├── main_agent.py       # 主 Agent (LangGraph)
│   │   ├── intent_agent.py    # 意图识别 Agent
│   │   ├── single_metric_inspector.py  # 单指标巡检
│   │   └── templates.py       # 响应模板
│   ├── api/
│   │   ├── routes/            # API 路由
│   │   │   ├── chat.py        # 对话 API
│   │   │   ├── inspection.py   # 巡检 API
│   │   │   └── prediction.py  # 预测 API
│   │   ├── schemas.py         # Pydantic 模型
│   │   └── dependencies.py   # 依赖注入
│   ├── tools/              # 工具层
│   │   ├── ssh.py           # SSH 命令执行
│   │   ├── prometheus.py    # Prometheus 查询
│   │   ├── trend.py         # 趋势预测
│   │   └── ...
│   ├── config/
│   │   ├── settings.py     # 配置管理
│   │   └── constants.py    # 常量定义
│   ├── models/             # 数据模型
│   ├── environment/       # 环境管理
│   ├── scheduler/          # 调度器
│   └── main.py             # 主入口
├── tests/                  # 测试用例
├── docker/                  # Docker 配置
├── scripts/                 # 部署脚本
│   └── pack_offline.sh     # 离线打包脚本
├── lib/site-packages/       # 离线依赖包
├── DEPLOYMENT.md           # 部署指南
├── OFFLINE_PACKAGES.md     # 离线包列表
├── README_OFFLINE.md        # 离线部署说明
├── run_offline.py          # 离线启动脚本
├── CLAUDE.md               # Claude Code 指南
├── requirements.txt        # 依赖列表
└── .env.example            # 环境变量示例
```

---

## 部署方式

### 1. 在线部署

```bash
pip install -r requirements.txt
python src/main.py
```

### 2. Docker 部署

```bash
cd docker
docker-compose up -d
```

### 3. 离线部署（内网环境）

**Step 1**: 联网机器下载离线包
```bash
pip download --platform manylinux2014_x86_64 --python-version 311 \
  --only-binary=:all: --no-deps -d ./lib/site-packages/ -r requirements.txt
```

**Step 2**: 打包
```bash
./scripts/pack_offline.sh
```

**Step 3**: 目标服务器部署
```bash
# 解压
tar -xzvf aiops-lib.tar.gz

# 启动（无 pip）
python run_offline.py

# 或（有 pip）
pip install --no-index --find-links=./lib/site-packages/ -r requirements.txt
python src/main.py
```

详见 [README_OFFLINE.md](README_OFFLINE.md)

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单个测试
pytest tests/test_aiops.py::TestModels -v

# 跳过需要服务器的集成测试
pytest tests/ -v --ignore=tests/test_chat.py --ignore=tests/test_intent.py
```

---

## License

MIT
