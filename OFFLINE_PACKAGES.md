# AIOPS 完整依赖包列表

## 下载位置

所有 Python 包可以从以下地址下载：

### PyPI 官方（需要联网）
- https://pypi.org/simple/
- 使用 `pip download` 命令下载

### 镜像站点（内网可能无法访问）
- 阿里云：`https://mirrors.aliyun.com/pypi/simple/`
- 清华：`https://pypi.tuna.tsinghua.edu.cn/simple/`
- 腾讯云：`https://mirrors.cloud.tencent.com/pypi/simple/`

---

## requirements.txt 直接依赖

| 包名 | 最低版本 | 说明 |
|------|---------|------|
| langchain | >=0.2.0 | LangChain 主包 |
| langchain-core | >=0.2.0 | LangChain 核心 |
| langgraph | >=0.2.0 | LangGraph 状态图 |
| langchain-openai | >=0.1.0 | OpenAI LLM 集成 |
| sqlalchemy | >=2.0.0 | ORM 框架 |
| aiomysql | >=0.2.0 | 异步 MySQL 驱动 |
| pymysql | >=1.1.0 | MySQL 驱动 |
| websockets | >=12.0 | WebSocket 库 |
| aiohttp | >=3.9.0 | 异步 HTTP 客户端 |
| paramiko | >=3.4.0 | SSH 客户端 |
| pydantic | >=2.6.0 | 数据验证 |
| pydantic-settings | >=2.2.0 | Pydantic 配置 |
| croniter | >=2.0.0 | Cron 解析 |
| pytest | >=8.0.0 | 测试框架 |
| pytest-asyncio | >=0.23.0 | 异步测试支持 |
| pytest-mock | >=3.12.0 | Mock 支持 |
| python-dotenv | >=1.0.0 | 环境变量加载 |
| openpyxl | >=3.1.0 | Excel 支持 |
| fastapi | >=0.109.0 | Web 框架 |
| uvicorn | >=0.27.0 | ASGI 服务器 |

---

## 完整依赖树（含传递依赖）

### 核心依赖（必须安装）

```
# ===== 核心 Web 框架 =====
fastapi>=0.109.0
    ├── starlette>=0.27.0
    │       └── anyio>=3.0.0
    │               └── idna>=2.5
    ├── pydantic>=2.0.0
    │       ├── pydantic-core>=2.0.0
    │       │       └── typing-extensions>=4.0.0
    │       ├── annotated-types>=0.1.0
    │       └── typing-extensions>=4.0.0
    └── python-multipart>=0.0.5

uvicorn>=0.27.0
    ├── h11>=0.12.0
    └── httptools>=0.5.0

websockets>=12.0

# ===== 数据库 =====
sqlalchemy>=2.0.0
    └── greenlet>=0.4.9

aiomysql>=0.2.0
    └── PyMySQL>=1.0.0

pymysql>=1.1.0

# ===== LangChain 生态 =====
langchain>=0.2.0
    ├── langchain-core>=0.2.0
    │       ├── pydantic>=2.0.0
    │       └── tenacity>=8.0.0
    ├── langgraph>=0.2.0
    │       └── langgraph-checkpoint>=1.0.0
    └── langchain-community>=0.2.0
            ├── sqlalchemy>=1.4.0
            └── aiohttp>=3.8.0

langchain-openai>=0.1.0
    ├── langchain-core>=0.1.0
    └── openai>=1.0.0
            └── httpx>=0.25.0
                    └── httpcore>=0.15.0

langgraph>=0.2.0
    └── langgraph-checkpoint>=1.0.0

# ===== HTTP / 网络 =====
aiohttp>=3.9.0
    ├── aiosignal>=1.0.0
    │       └── frozenlist>=1.0.0
    ├── attrs>=17.3.0
    ├── frozenlist>=1.0.0
    ├── multidict>=4.0.0
    └── yarl>=1.0.0
            └── idna>=2.5

requests>=2.28.0
    ├── charset-normalizer>=2.0.0
    ├── idna>=2.5
    ├── urllib3>=1.21.1,<3
    └── certifi>=2017.4.17

# ===== SSH =====
paramiko>=3.4.0
    ├── cryptography>=3.3.0
    │       └── cffi>=1.0.0
    │               └── pycparser>=2.0.0
    ├── bcrypt>=3.2.0
    └── pynacl>=1.5.0

# ===== 配置 & 日志 =====
pydantic-settings>=2.2.0
    ├── pydantic>=2.0.0
    └── python-dotenv>=0.21.0

croniter>=2.0.0

# ===== 工具库 =====
python-dotenv>=1.0.0

openpyxl>=3.1.0
    └── et-xmlfile>=1.0.0

PyYAML>=6.0.0

tenacity>=8.0.0

rich>=13.0.0
    ├── markdown-it-py>=2.0.0
    │       └── mdurl>=0.1
    └── pygments>=2.13.0

# ===== 测试 =====
pytest>=8.0.0
    ├── iniconfig>=2.0.0
    ├── packaging>=23.0
    ├── pluggy>=0.12.0
    └── colorama>=0.4.0

pytest-asyncio>=0.23.0
    └── pytest>=7.0.0

pytest-mock>=3.12.0
    └── pytest>=6.0.0
```

---

## 完整包列表（按字母排序）

### 必须安装（直接依赖 + 传递依赖）

```
aiofiles>=23.0.0
aiohttp>=3.9.0
aiosignal>=1.0.0
annotated-types>=0.1.0
anyio>=3.0.0
async-timeout>=4.0.0
attrs>=17.3.0
bcrypt>=3.2.0
certifi>=2017.4.17
cffi>=1.0.0
charset-normalizer>=2.0.0
click>=8.0.0
colorama>=0.4.0
cryptography>=3.3.0
distro>=1.5.0
et-xmlfile>=1.0.0
fastapi>=0.109.0
frozendict>=2.0.0
frozenlist>=1.0.0
greenlet>=0.4.9
h11>=0.12.0
httpcore>=0.15.0
httptools>=0.5.0
httpx>=0.25.0
idna>=2.5
iniconfig>=2.0.0
jsonpatch>=1.0.0
jsonpointer>=1.9.0
langchain>=0.2.0
langchain-community>=0.2.0
langchain-core>=0.2.0
langchain-openai>=0.1.0
langgraph>=0.2.0
langgraph-checkpoint>=1.0.0
langsmith>=0.1.0
markdown>=2.6.0
markdown-it-py>=2.0.0
mdurl>=0.1
multidict>=4.0.0
numpy>=1.20.0
openai>=1.0.0
openpyxl>=3.1.0
packaging>=23.0
paramiko>=3.4.0
pluggy>=0.12.0
pydantic>=2.6.0
pydantic-core>=2.0.0
pydantic-settings>=2.2.0
pygments>=2.13.0
pynacl>=1.5.0
pycparser>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
pytz>=2020.0
pyyaml>=6.0.0
requests>=2.28.0
rich>=13.0.0
six>=1.5.0
soupsieve>=2.0.0
sqlalchemy>=2.0.0
starlette>=0.27.0
tenacity>=8.0.0
typing-extensions>=4.0.0
typing-inspection>=0.4.0
ujson>=5.0.0
urllib3>=1.21.1,<3
uvicorn>=0.27.0
uvloop>=0.17.0
watchfiles>=0.21.0
websockets>=12.0
wheel>=0.40.0
yarl>=1.0.0
```

---

## 推荐下载命令

### 联网机器执行：下载所有包

```bash
#!/bin/bash
# download_all_packages.sh

TARGET_DIR="aiops-all-packages"
PLATFORM="manylinux2014_x86_64"  # 修改为你的目标平台
PYTHON_VERSION="311"              # 修改为你的 Python 版本

mkdir -p $TARGET_DIR

# 核心包
pip download \
    fastapi uvicorn starlette pydantic pydantic-core pydantic-settings \
    sqlalchemy aiomysql pymysql \
    langchain langchain-core langchain-openai langgraph \
    aiohttp requests httpx \
    paramiko cryptography bcrypt pynacl \
    python-dotenv python-multipart \
    websockets \
    croniter tenacity \
    openpyxl PyYAML \
    pytest pytest-asyncio pytest-mock \
    rich markdown-it-py pygments \
    annotated-types typing-extensions \
    -d $TARGET_DIR/ \
    --platform $PLATFORM \
    --python-version $PYTHON_VERSION \
    --only-binary=:all: \
    --no-deps

# 传递依赖（不使用 --no-deps 让 pip 自动下载）
pip download \
    anyio idna certifi charset-normalizer urllib3 \
    httptools uvloop h11 \
    greenlet \
    aiosignal frozenlist attrs multidict yarl \
    jsonpatch jsonpointer \
    iniconfig packaging pluggy colorama \
    -d $TARGET_DIR/ \
    --platform $PLATFORM \
    --python-version $PYTHON_VERSION \
    --only-binary=:all: \
    --no-deps

echo "下载完成，包保存在: $TARGET_DIR/"
ls -la $TARGET_DIR/
```

### 不同平台的 --platform 参数

| 目标平台 | --platform 参数 |
|---------|----------------|
| Linux x86_64 | `manylinux2014_x86_64` |
| Linux aarch64 (ARM64) | `manylinux2014_aarch64` |
| Windows x86_64 | `win_amd64` |
| macOS Intel | `macosx_10_15_x86_64` |
| macOS Apple Silicon | `macosx_11_0_arm64` |

### 完整下载命令（包含所有传递依赖）

```bash
# 创建目录
mkdir -p aiops-complete-packages
cd aiops-complete-packages

# 下载核心依赖（自动包含传递依赖）
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
    -d ./packages/

# 打包
cd ..
tar -czvf aiops-complete-packages.tar.gz aiops-complete-packages/
```

---

## 内网目标服务器安装步骤

### 方式 1：使用 pip 安装（推荐）

```bash
# 1. 解压
tar -xzvf aiops-complete-packages.tar.gz

# 2. 安装（pip 会自动处理依赖顺序）
pip install --no-index --find-links=aiops-complete-packages/packages/ -r requirements.txt

# 3. 验证
python -c "import fastapi; import langchain; import pydantic; print('OK')"
```

### 方式 2：无 pip 使用 bootstrap

```bash
# 1. 安装 pip（如果还没有）
python -m ensurepip --upgrade

# 2. 解压包
tar -xzvf aiops-complete-packages.tar.gz

# 3. 设置离线镜像源
pip install --no-index --find-links=aiops-complete-packages/packages/ -r requirements.txt
```

### 方式 3：直接 sys.path 加载

```python
# run_aiops.py
import sys
import os
from pathlib import Path

# 添加包目录到 sys.path
PACKAGES_DIR = Path(__file__).parent / "aiops-complete-packages" / "packages"
sys.path.insert(0, str(PACKAGES_DIR))

# 验证导入
import fastapi
import langchain
import pydantic
import uvicorn

print("所有依赖加载成功！")

# 启动应用
from src.main import main
main()
```

---

## 验证安装完整性

```bash
# 逐个检查关键包
python -c "
import fastapi; print(f'fastapi: {fastapi.__version__}')
import uvicorn; print(f'uvicorn: {uvicorn.__version__}')
import langchain; print(f'langchain: {langchain.__version__}')
import langchain_core; print(f'langchain-core: {langchain_core.__version__}')
import langgraph; print(f'langgraph: {langgraph.__version__}')
import pydantic; print(f'pydantic: {pydantic.__version__}')
import pydantic_settings; print(f'pydantic-settings: OK')
import sqlalchemy; print(f'sqlalchemy: {sqlalchemy.__version__}')
import paramiko; print(f'paramiko: {paramiko.__version__}')
import aiohttp; print(f'aiohttp: {aiohttp.__version__}')
import pytest; print(f'pytest: {pytest.__version__}')
print('\\n所有依赖验证通过！')
"
```

---

## 常见问题

### Q: 有些包下载失败？

```bash
# 使用 --no-deps 单独下载
pip download package-name --no-deps -d ./packages/

# 或使用源码包
pip download package-name --no-binary :all: -d ./packages/
```

### Q: 架构不匹配？

```bash
# 查看目标机器架构
uname -m
python --version

# 重新下载时指定正确参数
pip download ... --platform linux_x86_64 --python-version 311 ...
```

### Q: 如何确认下载完整？

```bash
# 在目标机器执行
python -c "import pkg_resources; [print(p.project_name) for p in pkg_resources.working_set]"
```

### Q: 某些包版本冲突？

```bash
# 强制安装特定版本
pip install package==1.2.3 --force-reinstall
```
