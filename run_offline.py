#!/usr/bin/env python
"""
AIOPS 离线启动脚本 - 无需 pip 安装，直接加载离线包

使用方法:
    1. 解压离线包: tar -xzvf aiops-lib.tar.gz
    2. 运行本脚本: python run_offline.py

如果目标服务器有 pip:
    pip install --no-index --find-links=./lib/site-packages/ -r requirements.txt
    python src/main.py
"""

import sys
import os
import zipfile
import tempfile
import shutil
from pathlib import Path


def get_package_dir() -> Path:
    """获取离线包目录"""
    # 优先使用相对路径
    script_dir = Path(__file__).parent.resolve()
    package_dir = script_dir / "lib" / "site-packages"

    # 如果不存在，尝试当前目录
    if not package_dir.exists():
        package_dir = Path(".") / "lib" / "site-packages"

    return package_dir


def extract_wheels(package_dir: Path) -> str:
    """解压所有 whl 到临时目录

    Args:
        package_dir: whl 文件所在目录

    Returns:
        临时目录路径
    """
    temp_dir = tempfile.mkdtemp(prefix="aiops_packages_")
    print(f"📦 解压离线包到临时目录: {temp_dir}")

    if not package_dir.exists():
        print(f"❌ 错误: 离线包目录不存在: {package_dir}")
        print(f"   请确认已将 aiops-lib.tar.gz 解压到项目目录")
        sys.exit(1)

    whl_files = list(package_dir.glob("*.whl"))
    if not whl_files:
        print(f"❌ 错误: 目录下没有找到 .whl 文件: {package_dir}")
        sys.exit(1)

    extracted = 0
    for whl in whl_files:
        try:
            with zipfile.ZipFile(whl, 'r') as z:
                z.extractall(temp_dir)
            extracted += 1
        except Exception as e:
            print(f"⚠️  警告: 解压失败 {whl.name}: {e}")

    print(f"✅ 成功解压 {extracted}/{len(whl_files)} 个包")
    return temp_dir


def setup_python_path(temp_dir: str) -> None:
    """设置 sys.path

    Args:
        temp_dir: 临时目录路径
    """
    # 优先添加临时解压目录
    if temp_dir not in sys.path:
        sys.path.insert(0, temp_dir)

    # 添加 packages 目录本身（处理 .pth 文件）
    package_dir = get_package_dir()
    if str(package_dir) not in sys.path:
        sys.path.insert(0, str(package_dir))

    print(f"📍 PYTHONPATH 已设置")


def verify_packages() -> bool:
    """验证关键依赖是否可用"""
    critical_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("langchain", "LangChain"),
        ("langchain_core", "LangChain Core"),
        ("langgraph", "LangGraph"),
        ("paramiko", "Paramiko"),
        ("aiohttp", "aiohttp"),
        ("sqlalchemy", "SQLAlchemy"),
    ]

    print("\n🔍 验证依赖...")
    all_ok = True

    for module_name, display_name in critical_packages:
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "unknown")
            print(f"   ✅ {display_name}: {version}")
        except ImportError as e:
            print(f"   ❌ {display_name}: 未找到 ({e})")
            all_ok = False

    return all_ok


def check_environment() -> None:
    """检查运行环境"""
    print(f"\n🐍 Python 信息:")
    print(f"   版本: {sys.version}")
    print(f"   路径: {sys.executable}")
    print(f"   平台: {sys.platform}")


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 AIOPS 离线启动脚本")
    print("=" * 60)

    # 检查环境
    check_environment()

    # 获取离线包目录
    package_dir = get_package_dir()
    print(f"\n📂 离线包目录: {package_dir}")

    if not package_dir.exists():
        print(f"\n❌ 错误: 离线包目录不存在")
        print(f"\n请执行以下步骤:")
        print(f"   1. 解压离线包: tar -xzvf aiops-lib.tar.gz")
        print(f"   2. 确认 lib/site-packages/ 目录下有 .whl 文件")
        print(f"   3. 重新运行: python run_offline.py")
        sys.exit(1)

    # 解压 whl 文件
    temp_dir = extract_wheels(package_dir)

    # 设置 PYTHONPATH
    setup_python_path(temp_dir)

    # 验证依赖
    if not verify_packages():
        print("\n❌ 依赖验证失败，请检查离线包是否完整")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ 所有依赖验证通过！")
    print("=" * 60)

    # 启动应用
    print("\n🚀 启动 AIOPS...")
    try:
        # 确保 src 目录在 path 中
        src_dir = Path(__file__).parent.resolve() / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from src.main import main as app_main
        app_main()
    except KeyboardInterrupt:
        print("\n\n👋 应用已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
