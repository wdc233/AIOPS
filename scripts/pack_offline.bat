@echo off
REM AIOPS 离线包打包脚本 (Windows)
REM 用法: pack_offline.bat

echo ==========================================
echo AIOPS 离线包打包脚本
echo ==========================================

set OUTPUT_FILE=aiops-lib.tar.gz
set PACKAGE_DIR=lib\site-packages

REM 检查包目录
if not exist "%PACKAGE_DIR%" (
    echo ❌ 错误: %PACKAGE_DIR% 目录不存在
    echo 请先运行 pip download 下载离线包
    exit /b 1
)

REM 统计文件数量
echo 📦 正在统计包文件...
dir /b "%PACKAGE_DIR%\*.whl" | find /c /v "" > temp_count.txt
set /p whl_count=<temp_count.txt
del temp_count.txt
echo 📦 找到 %whl_count% 个离线包

REM 创建 tar.gz
echo 📦 正在打包...
powershell -command "Compress-Archive -Path '%PACKAGE_DIR%\*' -DestinationPath '%OUTPUT_FILE%' -Force"

REM 显示大小
for %%A in (%OUTPUT_FILE%) do set size=%%~zA
set /a size_mb=%size% / 1024 / 1024
echo ✅ 打包完成: %OUTPUT_FILE% (!size_mb! MB)

echo.
echo ==========================================
echo 下一步:
echo ==========================================
echo 1. 将 %OUTPUT_FILE% 传输到目标服务器
echo 2. 在目标服务器解压
echo 3. 运行启动脚本: python run_offline.py
