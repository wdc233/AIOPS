#!/bin/bash
# AIOPS 离线包打包脚本
# 用法: ./scripts/pack_offline.sh

set -e

echo "=========================================="
echo "AIOPS 离线包打包脚本"
echo "=========================================="

# 目标目录
OUTPUT_FILE="aiops-lib.tar.gz"
PACKAGE_DIR="./lib/site-packages"

# 检查包目录
if [ ! -d "$PACKAGE_DIR" ]; then
    echo "❌ 错误: $PACKAGE_DIR 目录不存在"
    echo "请先运行 pip download 下载离线包"
    exit 1
fi

# 统计文件数量
whl_count=$(find $PACKAGE_DIR -name "*.whl" | wc -l)
echo "📦 找到 $whl_count 个离线包"

# 创建 tar.gz
echo "📦 正在打包..."
tar -czvf $OUTPUT_FILE $PACKAGE_DIR

# 显示大小
size=$(du -h $OUTPUT_FILE | cut -f1)
echo "✅ 打包完成: $OUTPUT_FILE (${size})"

echo ""
echo "=========================================="
echo "下一步:"
echo "=========================================="
echo "1. 将 $OUTPUT_FILE 传输到目标服务器"
echo "2. 在目标服务器解压: tar -xzvf $OUTPUT_FILE"
echo "3. 运行启动脚本: python run_offline.py"
