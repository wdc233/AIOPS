# AIOPS 离线部署指南

## 方案一：使用 Docker（推荐）

```bash
# 构建镜像
cd docker
docker build -t aiops-agent:latest ..

# 启动服务
docker-compose up -d
```

## 方案二：直接部署（无需 Docker）

### 前置准备

在有网络的机器上下载以下内容：

#### 1. Python 3.11 预编译版本
```bash
# 下载 Python Standalone (约 80MB)
curl -L -o python-3.11.9-standalone.tar.zst \
  https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-x86_64-unknown-linux-gnu-full.tar.zst

# 解压到 lib 目录
tar -I zstd -xf python-3.11.9-standalone.tar.zst -C lib/
mv lib/python-3.11.7+20240107-x86_64-unknown-linux-gnu-full lib/python3.11
```

#### 2. 本项目所有文件
复制整个 AIOPS 目录到目标服务器。

### 部署步骤

#### 1. 目录结构
```
AIOPS/
├── lib/
│   ├── python3.11/          # Python 解释器
│   ├── *.whl                # 依赖包
├── src/                     # 源代码
├── deploy.sh                # 部署脚本
├── requirements.txt
├── .env                     # 配置文件
└── clusters.json            # 集群配置
```

#### 2. 配置文件
```bash
# 复制并编辑配置
cp .env.example .env
# 编辑 .env 设置数据库、API Key 等
```

#### 3. 安装依赖
```bash
# 使用 pip 安装本地 wheel 包
pip install --no-index --find-links=./lib/ -r requirements.txt

# 或使用 lib 中的 Python
./lib/python3.11/bin/python3 -m pip install --no-index --find-links=./lib/ -r requirements.txt
```

#### 4. 启动
```bash
# 方式一：使用部署脚本
./deploy.sh start

# 方式二：直接运行
PYTHONPATH=. ./lib/python3.11/bin/python3 -m src.main

# 或使用系统 Python（如果已安装 pip 包）
python -m src.main
```

### 快速启动脚本

```bash
# 安装并启动
./deploy.sh install
./deploy.sh start

# 查看日志
tail -f /var/log/aiops.log

# 停止
./deploy.sh stop
```

### 配置文件说明 (.env)

```bash
# 数据库
DATABASE__HOST=localhost
DATABASE__PORT=9030
DATABASE__USER=root
DATABASE__PASSWORD=
DATABASE__DATABASE=aiops

# LLM
LLM__PROVIDER=openai
LLM__API_KEY=your-api-key
LLM__MODEL=gpt-4

# WebSocket
WEBSOCKET__PORT=8765
```

## 依赖包列表

已在 `lib/` 目录中包含以下 72 个包：

| 类别 | 包 |
|------|-----|
| LangChain | langchain, langchain-core, langgraph, langchain-openai |
| 数据库 | sqlalchemy, aiomysql, pymysql |
| Web | aiohttp, websockets, httpx |
| SSH | paramiko, bcrypt, cryptography, pynacl |
| 配置 | pydantic, pydantic-settings |
| 工具 | croniter, python-dotenv |
| 测试 | pytest, pytest-asyncio, pytest-mock |
| 其他 | requests, pyyaml, openai, tiktoken 等 |

## 故障排除

### 问题：找不到 Python
```bash
# 确认 lib 目录结构
ls -la lib/
# 应该有 python3.11/bin/python3
```

### 问题：ImportError
```bash
# 确认依赖已安装
pip list | grep -i pydantic
# 或重新安装
pip install --force-reinstall --no-index --find-links=./lib/ pydantic
```

### 问题：数据库连接失败
```bash
# 检查 StarRocks 是否运行
mysql -h localhost -P 9030 -uroot -e "SELECT 1"
```