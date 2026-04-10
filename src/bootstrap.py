#!/usr/bin/env python3
"""
AIOPS 离线启动器
直接使用 lib 目录中的包，无需 pip install
"""

import sys
import os
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LIB_DIR = PROJECT_ROOT / "lib"
SRC_DIR = PROJECT_ROOT / "src"

def setup_environment():
    """设置离线运行环境"""

    # 添加 lib 目录到 sys.path
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))

    # 添加 src 目录到 sys.path
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    # 设置环境变量
    os.environ['PYTHONPATH'] = str(PROJECT_ROOT)
    os.environ['PYTHONUNBUFFERED'] = '1'

    # 设置工作目录
    os.chdir(PROJECT_ROOT)

    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Lib Dir: {LIB_DIR}")
    print(f"Src Dir: {SRC_DIR}")
    print(f"Python: {sys.executable}")
    print(f"Python Version: {sys.version}")

    # 检查必需的目录
    if not LIB_DIR.exists():
        raise RuntimeError(f"lib directory not found: {LIB_DIR}")

    if not SRC_DIR.exists():
        raise RuntimeError(f"src directory not found: {SRC_DIR}")

def import_vendored_modules():
    """预加载 vendored 模块"""
    # 这些模块需要特殊处理
    vendored_modules = [
        'pydantic',
        'pydantic_settings',
        'sqlalchemy',
        'aiohttp',
        'yarl',
        'multidict',
    ]

    # 确保所有 wheel 包可以被导入
    lib_wheels = list(LIB_DIR.glob("*.whl"))
    print(f"Found {len(lib_wheels)} wheel packages in lib/")

def main():
    """主函数"""
    try:
        # 设置环境
        setup_environment()

        # 预加载模块
        import_vendored_modules()

        # 启动应用
        from src.main import main as app_main

        import asyncio
        asyncio.run(app_main())

    except KeyboardInterrupt:
        print("\nShutdown requested...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()