#!/bin/bash
#
# AIOPS 离线部署脚本
# 支持多种 Python 来源：lib/python3.11、系统 Python、pip install
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"
PYTHON_DIR="$LIB_DIR/python3.11"
APP_DIR="$SCRIPT_DIR"
LOG_FILE="/var/log/aiops.log"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[AIOPS]${NC} $1"; }
warn() { echo -e "${YELLOW}[AIOPS]${NC} $1"; }
error() { echo -e "${RED}[AIOPS]${NC} $1"; }

# 查找 Python
find_python() {
    # 1. lib/python3.11
    if [ -x "$PYTHON_DIR/bin/python3" ]; then
        echo "$PYTHON_DIR/bin/python3"
        return 0
    fi
    # 2. lib/python3.11/bin/python
    if [ -x "$PYTHON_DIR/bin/python" ]; then
        echo "$PYTHON_DIR/bin/python"
        return 0
    fi
    # 3. 系统 python3
    if command -v python3 &>/dev/null; then
        echo "python3"
        return 0
    fi
    # 4. 系统 python
    if command -v python &>/dev/null; then
        echo "python"
        return 0
    fi
    return 1
}

# 安装依赖
install_deps() {
    local PYTHON="$1"

    log "安装依赖包..."

    # 检查 lib 目录
    if [ ! -d "$LIB_DIR" ]; then
        error "lib 目录不存在: $LIB_DIR"
        return 1
    fi

    local WHEEL_COUNT=$(ls -1 "$LIB_DIR"/*.whl 2>/dev/null | wc -l)
    log "发现 $WHEEL_COUNT 个 wheel 包"

    # 优先使用本地 lib 安装
    if [ -d "$LIB_DIR" ] && [ "$WHEEL_COUNT" -gt 0 ]; then
        log "从 lib 目录安装依赖..."

        # 安装主包
        $PYTHON -m pip install --no-index --find-links="$LIB_DIR" \
            langchain langchain-core langgraph langchain-openai \
            sqlalchemy aiomysql pymysql websockets aiohttp paramiko \
            pydantic pydantic-settings croniter python-dotenv \
            pytest pytest-asyncio pytest-mock 2>/dev/null || true

        # 强制重装所有 wheel
        for whl in "$LIB_DIR"/*.whl; do
            [ -f "$whl" ] && $PYTHON -m pip install --force-reinstall --no-deps "$whl" 2>/dev/null || true
        done
    else
        warn "lib 目录为空，使用系统 pip 安装"
        $PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" --user
    fi

    log "依赖安装完成"
}

# 启动
start_aiops() {
    local PYTHON=$(find_python) || {
        error "未找到 Python 解释器"
        error "请确保已安装 Python 3.11，或将 Python 解压到 lib/python3.11"
        return 1
    }

    log "使用 Python: $PYTHON ($($PYTHON --version))"

    # 检查配置
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            warn "创建 .env 配置文件..."
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        fi
    fi

    # 检查 lib 目录
    if [ ! -d "$LIB_DIR" ]; then
        error "lib 目录不存在"
        return 1
    fi

    # 设置环境
    export PYTHONPATH="$APP_DIR:$LIB_DIR"
    export PYTHONUNBUFFERED=1
    export PYTHONHOME="$PYTHON_DIR"

    # 切换到应用目录
    cd "$APP_DIR"

    # 后台启动
    log "启动 AIOPS 服务..."
    nohup $PYTHON -m src.main > "$LOG_FILE" 2>&1 &
    local PID=$!

    sleep 2

    if ps -p $PID > /dev/null 2>&1; then
        log "AIOPS 已启动 (PID: $PID)"
        log "WebSocket: ws://localhost:8765"
        log "日志: $LOG_FILE"
    else
        error "启动失败，查看日志: $LOG_FILE"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

# 停止
stop_aiops() {
    log "停止 AIOPS..."

    local PIDS=$(pgrep -f "python.*src\.main" 2>/dev/null || true)

    if [ -z "$PIDS" ]; then
        warn "未找到运行中的进程"
        return 0
    fi

    for pid in $PIDS; do
        log "终止进程: $pid"
        kill $pid 2>/dev/null || true
    done

    # 等待结束
    sleep 1

    # 强制终止
    pkill -f "python.*src\.main" 2>/dev/null || true

    log "已停止"
}

# 状态
status_aiops() {
    local PIDS=$(pgrep -f "python.*src\.main" 2>/dev/null || true)

    if [ -n "$PIDS" ]; then
        log "运行中 (PIDs: $PIDS)"
        return 0
    else
        warn "未运行"
        return 1
    fi
}

# 状态
case "${1:-status}" in
    install)
        PYTHON=$(find_python) || {
            error "未找到 Python"
            exit 1
        }
        install_deps "$PYTHON"
        ;;
    start)
        start_aiops
        ;;
    stop)
        stop_aiops
        ;;
    restart)
        stop_aiops
        sleep 2
        start_aiops
        ;;
    status)
        status_aiops
        ;;
    log)
        tail -50 "$LOG_FILE"
        ;;
    *)
        echo "用法: $0 {install|start|stop|restart|status|log}"
        echo ""
        echo "命令说明:"
        echo "  install - 安装依赖包"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看状态"
        echo "  log     - 查看日志"
        exit 1
        ;;
esac