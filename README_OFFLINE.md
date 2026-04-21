# AIOPS 离线部署指南

## 快速开始

### Step 1: 下载离线包（联网机器）

```bash
# 下载所有依赖到 lib/site-packages/
pip download --platform manylinux2014_x86_64 --python-version 311 \
  --only-binary=:all: --no-deps -d ./lib/site-packages/ \
  langchain langchain-core langgraph langchain-openai \
  sqlalchemy aiomysql pymysql websockets aiohttp paramiko \
  pydantic pydantic-settings croniter pytest pytest-asyncio pytest-mock \
  python-dotenv openpyxl fastapi uvicorn
```

### Step 2: 打包

**Linux/Mac:**
```bash
./scripts/pack_offline.sh
```

**Windows:**
```cmd
scripts\pack_offline.bat
```

### Step 3: 传输到目标服务器

将 `aiops-lib.tar.gz` 和以下文件传输到目标服务器：
- `run_offline.py` - 启动脚本
- `src/` - 源代码
- `.env` - 配置文件
- `lib/` - 离线包目录

### Step 4: 启动

**方式一：使用离线启动脚本（无 pip）**
```bash
python run_offline.py
```

**方式二：使用 pip 安装后启动**
```bash
# 安装 pip（如果还没有）
python -m ensurepip --upgrade

# 安装离线包
pip install --no-index --find-links=./lib/site-packages/ -r requirements.txt

# 启动
python src/main.py
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `run_offline.py` | 离线启动脚本，无需 pip 直接加载 whl 包 |
| `scripts/pack_offline.sh` | Linux/Mac 打包脚本 |
| `scripts/pack_offline.bat` | Windows 打包脚本 |
| `lib/site-packages/` | 离线包目录（whl 文件） |

---

## run_offline.py 工作原理

1. **查找离线包目录**: `./lib/site-packages/`
2. **解压 whl 文件**: whl 本质是 zip，直接解压到临时目录
3. **设置 sys.path**: 将临时目录添加到 Python 路径
4. **验证依赖**: 检查关键包是否可用
5. **启动应用**: 正常启动 AIOPS

---

## 常见问题

### Q: 提示 "离线包目录不存在"
```
❌ 错误: 离线包目录不存在: lib\site-packages

请确认已将 aiops-lib.tar.gz 解压
```
**解决**: 确保 `lib/site-packages/` 目录存在且有 `.whl` 文件

### Q: 提示 "依赖加载失败"
```
❌ 依赖加载失败: No module named 'xxx'
```
**解决**:
1. 检查 `lib/site-packages/` 是否完整
2. 重新下载缺失的包
3. 尝试使用 pip 安装: `pip install --no-index --find-links=./lib/site-packages/ xxx`

### Q: 目标服务器是 Windows
**解决**: 使用 Docker 部署方式，或者手动解压 whl 到 Python 安装目录

---

## 目标服务器环境要求

- Python >= 3.10
- Linux x86_64（如果下载的是 manylinux 包）

---

## 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 测试对话
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "你好"}'
```
