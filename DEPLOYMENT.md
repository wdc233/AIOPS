# AIOPS 内网部署指南

## 目录
- [方式一：Docker 部署（推荐）](#方式一docker-部署推荐)
- [方式二：本地 Python 环境部署](#方式二本地-python-环境部署)
- [配置说明](#配置说明)
- [依赖离线安装（内网环境）](#依赖离线安装内网环境)
  - [方式 A：使用 pip 离线安装](#方式-a使用-pip-离线安装)
  - [方式 B：无 pip 使用 bootstrap + sys.path](#方式-b无-pip-使用-bootstrap--syspath)
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
- pip >= 21.0（如果使用方式 A）

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

### 方式 A：使用 pip 离线安装

#### Step 1: 联网机器下载依赖

**确认目标服务器信息：**
```bash
# 在目标服务器执行
python --version    # 例如: Python 3.11.9
uname -m             # 例如: x86_64 (Linux), aarch64 (ARM)
```

**下载命令示例（Linux x86_64, Python 3.11）：**
```bash
# 创建离线包目录
mkdir -p aiops-offline-pkgs

# 下载 pip、setuptools、wheel（用于离线安装）
pip download pip setuptools wheel \
  --platform manylinux2014_x86_64 \
  --python-version 311 \
  --only-binary=:all: \
  -d aiops-offline-pkgs/

# 下载所有主依赖
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
  --platform manylinux2014_x86_64 \
  --python-version 311 \
  --only-binary=:all: \
  -d aiops-offline-pkgs/

# 打包
tar -czvf aiops-offline-pkgs.tar.gz aiops-offline-pkgs/
```

**不同架构/版本参数对照表：**

| 目标环境 | `--platform` | `--python-version` |
|----------|--------------|-------------------|
| Linux x86_64 | `manylinux2014_x86_64` | `310`, `311`, `312` |
| Linux ARM64 | `manylinux2014_aarch64` | `310`, `311`, `312` |
| Windows x86_64 | `win_amd64` | `310`, `311`, `312` |
| macOS x86_64 | `macosx_10_16_x86_64` | `310`, `311`, `312` |
| macOS ARM64 | `macosx_11_0_arm64` | `310`, `311`, `312` |

#### Step 2: 目标机器离线安装

```bash
# 解压
tar -xzvf aiops-offline-pkgs.tar.gz

# 离线安装
pip install --no-index --find-links=aiops-offline-pkgs/ -r requirements.txt
```

---

### 方式 B：无 pip 使用 bootstrap + sys.path

如果目标服务器 **没有 pip**，且无法安装，使用此方式。

#### Step 1: 联网机器下载源码包（.tar.gz）

```bash
# 创建离线包目录
mkdir -p aiops-packages

# 下载所有源码包（使用 --no-binary :all: 或直接下载 .tar.gz）
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
  --no-binary :all: \
  -d aiops-packages/

# 打包
tar -czvf aiops-packages.tar.gz aiops-packages/
```

#### Step 2: 目标服务器 bootstrap pip

**方法 1: 使用 ensurepip（Python 内置）**
```bash
# Python 3.x 自带 ensurepip
python -m ensurepip --upgrade

# 或者指定版本
python -m ensurepip --version pip 24.0
```

**方法 2: 使用 get-pip.py**
```bash
# 联网机器下载
curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py

# 传输到目标服务器后安装
python get-pip.py
```

#### Step 3: 使用 sys.path 直接加载包

**创建启动脚本 `run_with_packages.py`：**

```python
#!/usr/bin/env python
"""
AIOPS 启动脚本 - 使用本地包目录
无需 pip install，直接通过 sys.path 加载所有依赖
"""

import sys
import os
from pathlib import Path

# ===== 配置区 =====
# 设置离线包目录（相对于当前目录或绝对路径）
PACKAGES_DIR = Path(__file__).parent / "aiops-packages"

# 添加所有包的路径到 sys.path
def setup_packages_path():
    """将离线包目录中的所有包添加到 sys.path"""
    if not PACKAGES_DIR.exists():
        print(f"Error: Packages directory not found: {PACKAGES_DIR}")
        sys.exit(1)

    # 遍历 packages 目录
    for pkg_path in PACKAGES_DIR.iterdir():
        if pkg_path.is_dir():
            # 检查是否是 Python 包（有 __init__.py 或 .dist-info）
            if any(pkg_path.glob("__init__.py")) or any(pkg_path.glob("*.dist-info")):
                sys.path.insert(0, str(pkg_path.parent))
        elif pkg_path.suffix == ".pth":
            # 处理 .pth 文件
            with open(pkg_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg_dir = PACKAGES_DIR / line
                        if pkg_dir.exists() and str(pkg_dir) not in sys.path:
                            sys.path.insert(0, str(pkg_dir))

    # 也直接把 packages 目录本身加进去
    if str(PACKAGES_DIR) not in sys.path:
        sys.path.insert(0, str(PACKAGES_DIR))

# 执行路径设置
setup_packages_path()

# 现在可以导入所有依赖
import langchain
import langchain_core
import fastapi
import uvicorn
# ... 其他包

# 启动 AIOPS
if __name__ == "__main__":
    from src.main import main
    main()
```

**使用方法：**
```bash
# 1. 传输包和脚本到目标服务器
scp -r aiops-packages aiops-agent/ user@target:/opt/aiops/

# 2. 启动
python run_with_packages.py
```

#### Step 4: 使用 PYTHONPATH 环境变量

```bash
# 解压到指定目录
tar -xzvf aiops-packages.tar.gz -C /opt/aiops/

# 设置 PYTHONPATH
export PYTHONPATH=/opt/aiops/aiops-packages:$PYTHONPATH

# 启动
cd /opt/aiops
python src/main.py
```

**或创建启动脚本 `start.sh`：**
```bash
#!/bin/bash
export PYTHONPATH=/opt/aiops/aiops-packages:$PYTHONPATH
cd /opt/aiops
python src/main.py
```

---

### 方式 C：虚拟环境 + 离线包（混合方案）

**联网机器：**
```bash
# 创建虚拟环境并下载包
python -m venv aiops-venv
source aiops-venv/bin/activate
pip download -r requirements.txt -d aiops-packages/
deactivate

# 打包
tar -czvf aiops-venv-and-packages.tar.gz aiops-venv/ aiops-packages/
```

**目标服务器：**
```bash
# 解压
tar -xzvf aiops-venv-and-packages.tar.gz -C /opt/aiops/

# 激活虚拟环境（虚拟环境内有 pip）
source /opt/aiops/aiops-venv/bin/activate

# 安装包（如果需要）
pip install --no-index --find-links=/opt/aiops/aiops-packages/ -r requirements.txt

# 或直接使用（虚拟环境已包含所有包）
/opt/aiops/aiops-venv/bin/python src/main.py
```

---

## 快速启动脚本模板

### 完整部署脚本 `deploy.sh`

```bash
#!/bin/bash
set -e

# ===== 配置 =====
AIOPS_DIR="/opt/aiops"
PACKAGES_FILE="aiops-packages.tar.gz"
PYTHON_VERSION="3.11"
ARCH="x86_64"  # 或 aarch64

echo "=== AIOPS 部署脚本 ==="

# 1. 检查 Python
if ! command -v python &> /dev/null; then
    echo "Error: Python 未安装"
    exit 1
fi
python --version

# 2. 创建目录
mkdir -p $AIOPS_DIR

# 3. 解压包
if [ -f "$PACKAGES_FILE" ]; then
    echo "解压依赖包..."
    tar -xzvf $PACKAGES_FILE -C $AIOPS_DIR/
else
    echo "Error: $PACKAGES_FILE 不存在"
    exit 1
fi

# 4. 设置 PYTHONPATH
export PYTHONPATH=$AIOPS_DIR/aiops-packages:$PYTHONPATH

# 5. 验证依赖
echo "验证依赖..."
python -c "import langchain; import fastapi; import uvicorn; print('依赖验证通过')"

# 6. 复制配置
if [ ! -f "$AIOPS_DIR/.env" ]; then
    cp $AIOPS_DIR/.env.example $AIOPS_DIR/.env
    echo "请编辑 $AIOPS_DIR/.env 配置"
fi

# 7. 启动
echo "启动 AIOPS..."
cd $AIOPS_DIR
python src/main.py
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
# 检查 sys.path 是否正确
python -c "import sys; print('\n'.join(sys.path))"

# 手动添加路径
export PYTHONPATH=/path/to/packages:$PYTHONPATH
```

### 3. 架构不匹配

**问题**：`not a supported wheel on this platform`

**解决**：
```bash
# 下载时指定正确架构
pip download --platform manylinux2014_x86_64 --python-version 311 --abi cp311 ...

# 或使用源码包
pip download --no-binary :all: ...
```

### 4. LLM API 连接失败

**问题**：`ConnectionError` 或 `AuthenticationError`

**解决**：
1. 检查 `LLM__API_KEY` 是否正确
2. 如果在内网，需要配置代理：
   ```ini
   LLM__BASE_URL=http://your-proxy/v1
   ```
3. 检查代理白名单是否包含 OpenAI API 域名

### 5. SSH 连接失败

**问题**：`AuthenticationError` 或 `Timeout`

**解决**：
```ini
# 检查 SSH 配置
SSH__TIMEOUT=30
SSH__MAX_RETRIES=3
```

### 6. 端口被占用

**问题**：`Port is already in use`

**解决**：
```bash
# 查找占用端口的进程
lsof -i:8000  # Linux
netstat -ano | findstr :8000  # Windows

# 杀掉进程或使用其他端口
python src/main.py --api-port 8080
```

---

## 代码调整指南

### 调整 1：更换 LLM Provider

**文件**：`src/config/settings.py`

```python
# 方式一：修改默认 provider
LLM__PROVIDER=anthropic  # 或 azure, zhipu 等

# 方式二：修改代码
from langchain_anthropic import ChatAnthropic
```

### 调整 2：修改 SSH 命令

**文件**：`src/config/constants.py`

```python
SSH_COMMANDS = {
    "cpu": "your-custom-cpu-command",
    "memory": "your-custom-memory-command",
}
```

### 调整 3：添加新的 Intent 类型

**文件**：`src/models/types.py`

```python
class IntentType(str, Enum):
    CUSTOM_INTENT = "custom_intent"
```

**文件**：`src/agent/intent_agent.py`

```python
if "custom_keyword" in user_input:
    intent_type = IntentType.CUSTOM_INTENT
```

---

## 快速检查清单

部署前确认：

- [ ] Python >= 3.10 已安装
- [ ] 离线包已下载（`.tar.gz` 文件）
- [ ] `.env` 配置文件已创建
- [ ] `LLM__API_KEY` 已配置
- [ ] 集群/服务器 SSH 访问正常
- [ ] Prometheus 可访问（如果使用）
- [ ] 端口 8000（API）和 8765（WebSocket）未被占用

启动后检查：

- [ ] `curl http://localhost:8000/health` 返回正常
- [ ] 日志无报错
- [ ] 可以正常进行对话
