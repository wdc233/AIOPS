# AIOPS 内网部署指南

## 目录
- [方式一：Docker 部署（推荐）](#方式一docker-部署推荐)
- [方式二：本地 Python 环境部署](#方式二本地-python-环境部署)
- [配置说明](#配置说明)
- [依赖离线安装（内网环境）](#依赖离线安装内网环境)
- [常见问题与解决方案](#常见问题与解决方案)

---

## 方式一：Docker 部署（推荐）

### 前提条件
- Docker >= 20.10
- Docker Compose >= 2.0

### 部署步骤

```bash
# 1. 进入 docker 目录
cd docker

# 2. 复制并编辑环境配置
cp ../.env.example ../.env
# 编辑 .env 文件，配置必要的环境变量

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f aiops-agent
```

### 验证服务
```bash
# 检查 API 是否正常
curl http://localhost:8000/health

# 测试 WebSocket 连接
ws://localhost:8000/ws
```

---

## 方式二：本地 Python 环境部署

### 前提条件
- Python >= 3.10
- pip >= 21.0

### 1. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 2. 在线安装依赖

```bash
pip install -r requirements.txt
```

### 3. 离线安装依赖（内网环境）

**步骤 A：打包依赖（需要联网机器）**

```bash
# 创建依赖目录
mkdir -p lib

# 下载所有依赖到 lib 目录
pip download -r requirements.txt -d lib/

# 打包 lib 目录
tar -czvf aiops-deps.tar.gz lib/
```

**步骤 B：离线安装（在目标机器）**

```bash
# 解压依赖包
tar -xzvf aiops-deps.tar.gz

# 离线安装
pip install --no-index --find-links=lib/ -r requirements.txt
```

或者逐个安装：
```bash
pip install langchain/langchain-*.whl
pip install langchain-core/langchain_core-*.whl
# ... 继续安装其他包
```

### 4. 配置文件

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件
vim .env
```

**关键配置项**：
```ini
# LLM 配置（必须）
LLM__PROVIDER=openai
LLM__API_KEY=your-api-key
LLM__BASE_URL=https://api.openai.com/v1  # 如果使用代理
LLM__MODEL=gpt-4

# 数据库配置（可选，无数据库也可运行）
DATABASE__ENABLED=false

# Prometheus 配置（可选）
PROMETHEUS__URL=http://localhost:9090

# SSH 配置
SSH__TIMEOUT=30
SSH__COMMAND_TIMEOUT=300
```

### 5. 启动服务

```bash
# 方式一：直接运行
python src/main.py

# 方式二：指定端口
python src/main.py --api-port 8080

# 方式三：带日志运行
python -u src/main.py
```

### 6. 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 测试对话 API
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "你好"}'
```

---

## 配置说明

### 环境变量映射

AIOPS 使用 Pydantic Settings，所有配置通过环境变量注入：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `LLM__API_KEY` | LLM API 密钥 | `sk-xxx` |
| `LLM__BASE_URL` | LLM API 地址（内网代理） | `http://proxy.internal/v1` |
| `LLM__MODEL` | 使用的模型 | `gpt-4` |
| `DATABASE__ENABLED` | 是否启用数据库 | `true` / `false` |
| `PROMETHEUS__URL` | Prometheus 地址 | `http://prom:9090` |
| `SSH__*` | SSH 连接参数 | - |

### 集群配置

如果 `DATABASE__ENABLED=false`，使用本地 JSON 文件配置集群：

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

## 依赖离线安装（内网环境）

### 完整离线安装步骤

**在联网机器执行：**

```bash
# 1. 创建依赖目录
mkdir -p aiops-offline
cd aiops-offline

# 2. 下载 Python 和 pip（如果目标机器没有）
# 下载 requirements.txt 中的所有包
pip download pip setuptools wheel -d deps/

# 3. 下载主依赖
pip download \
  langchain \
  langchain-core \
  langgraph \
  langchain-openai \
  sqlalchemy \
  aiomysql \
  pymysql \
  websockets \
  aiohttp \
  paramiko \
  pydantic \
  pydantic-settings \
  croniter \
  pytest \
  pytest-asyncio \
  pytest-mock \
  python-dotenv \
  openpyxl \
  fastapi \
  uvicorn \
  -d deps/ \
  --platform linux_x86_64 \
  --only-binary=:all: \
  --python-version 3.11

# 4. 打包
tar -czvf aiops-deps.tar.gz deps/
```

**在目标机器执行：**

```bash
# 1. 解压
tar -xzvf aiops-deps.tar.gz

# 2. 安装
pip install --no-index --find-links=deps/ -r requirements.txt

# 3. 如果有二进制包安装失败，尝试源码安装
pip install --no-binary :all: --find-links=deps/ some-package
```

### pip 离线镜像（如果内网有镜像服务器）

```ini
# pip.conf (Linux: ~/.pip/pip.conf, Windows: %HOME%\pip\pip.ini)
[global]
index-url = http://mirror.internal/simple/
trusted-host = mirror.internal
```

---

## 常见问题与解决方案

### 1. 依赖安装失败

**问题**：`pip install` 报 `Connection Error`

**解决**：
```bash
# 使用内网镜像
pip install -r requirements.txt -i http://mirror.internal/simple --trusted-host mirror.internal

# 或者先下载 wheel 文件离线安装
pip install --no-index --find-links=/path/to/wheels/ package-name
```

### 2. 导入错误 (ImportError)

**问题**：`ModuleNotFoundError: No module named 'xxx'`

**解决**：
```bash
# 确认已安装
pip list | grep xxx

# 如果没有，重新安装
pip install xxx

# 如果是内网环境，检查是否有多个 Python 版本
which python
python --version
```

### 3. LLM API 连接失败

**问题**：`ConnectionError` 或 `AuthenticationError`

**解决**：
1. 检查 `LLM__API_KEY` 是否正确
2. 如果在内网，需要配置代理：
   ```ini
   LLM__BASE_URL=http://your-proxy/v1
   ```
3. 检查代理白名单是否包含 OpenAI API 域名

### 4. SSH 连接失败

**问题**：`AuthenticationError` 或 `Timeout`

**解决**：
```ini
# 检查 SSH 配置
SSH__TIMEOUT=30
SSH__MAX_RETRIES=3
```

目标机器 SSH 配置检查：
```bash
# 测试 SSH 连接
ssh -v -o ConnectTimeout=30 user@host

# 检查 SSH 服务
systemctl status sshd  # Linux
```

### 5. Prometheus 查询无数据

**问题**：`No data found`

**解决**：
1. 确认 Prometheus 配置了目标机器的 node_exporter
2. 检查 Prometheus UI：`http://prometheus:9090`
3. 查询可用指标：`{__name__=~".+"}`

### 6. 数据库连接失败

**问题**：`Can't connect to MySQL`

**解决**：
```ini
# 确认数据库启用
DATABASE__ENABLED=true

# 或禁用使用本地文件
DATABASE__ENABLED=false
```

### 7. 端口被占用

**问题**：`Port is already in use`

**解决**：
```bash
# 查找占用端口的进程
lsof -i:8000  # Linux
netstat -ano | findstr :8000  # Windows

# 杀掉进程或使用其他端口
python src/main.py --api-port 8080
```

### 8. Docker 部署问题

**问题**：容器内无法连接宿主机服务

**解决**：
```yaml
# docker-compose.yml 已配置 extra_hosts
extra_hosts:
  - "host.docker.internal:host-gateway"
```

在容器内访问宿主机：`http://host.docker.internal:8000`

---

## 代码调整指南

### 调整 1：更换 LLM Provider

如果需要使用其他 LLM（如内网模型）：

**文件**：`src/config/settings.py`

```python
# 方式一：修改默认 provider
LLM__PROVIDER=anthropic  # 或 azure, zhipu 等

# 方式二：修改代码
# src/tools/llm.py 或相关文件
from langchain_anthropic import ChatAnthropic

# 修改 LLM 初始化逻辑
```

### 调整 2：添加新指标采集方式

**文件**：`src/tools/` 下新增工具类

```python
# src/tools/custom_metric.py
from src.tools.base import BaseTool, ToolResult

class CustomMetricTool(BaseTool):
    name = "custom_metric"
    description = "Custom metric collector"

    async def execute(self, **kwargs) -> ToolResult:
        # 实现自定义采集逻辑
        ...
```

### 调整 3：修改 SSH 命令

**文件**：`src/config/constants.py`

```python
# 修改 SSH 命令定义
SSH_COMMANDS = {
    "cpu": "your-custom-cpu-command",
    "memory": "your-custom-memory-command",
    ...
}
```

### 调整 4：添加新的 Intent 类型

**文件**：`src/models/types.py`

```python
class IntentType(str, Enum):
    # 新增意图类型
    CUSTOM_INTENT = "custom_intent"
```

**文件**：`src/agent/intent_agent.py`

```python
# 在 intent_parse 方法中添加处理逻辑
if "custom_keyword" in user_input:
    intent_type = IntentType.CUSTOM_INTENT
```

### 调整 5：修改端口或地址

**方式一：环境变量**
```bash
export API__PORT=8080
export WEBSOCKET__PORT=8766
```

**方式二：.env 文件**
```ini
API__PORT=8080
WEBSOCKET__PORT=8766
```

---

## 快速检查清单

部署前确认：

- [ ] Python >= 3.10 已安装
- [ ] 所有依赖已安装（`pip list` 检查）
- [ ] `.env` 配置文件已创建
- [ ] `LLM__API_KEY` 已配置
- [ ] 集群/服务器 SSH 访问正常
- [ ] Prometheus 可访问（如果使用）
- [ ] 端口 8000（API）和 8765（WebSocket）未被占用

启动后检查：

- [ ] `curl http://localhost:8000/health` 返回正常
- [ ] 日志无报错
- [ ] 可以正常进行对话
