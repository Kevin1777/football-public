@echo off
chcp 65001 >nul

REM Add Git to PATH
set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo ========================================
echo   Football Data Service 启动脚本
echo ========================================
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo ❌ 虚拟环境不存在
    echo.
    echo 请先运行: 用Python312重建.bat
    echo.
    pause
    exit /b 1
)

echo ✅ 使用虚拟环境: venv
echo.

REM 测试 ddddocr
echo 测试依赖...
venv\Scripts\python.exe -c "import ddddocr; print('✓ ddddocr 已安装')" 2>nul
if %errorlevel% neq 0 (
    echo ❌ ddddocr 未安装！
    echo.
    echo 请运行: 用Python312重建.bat
    pause
    exit /b 1
)

echo.
echo 启动程序...
echo.

REM 直接使用虚拟环境的 Python（不需要 activate）
venv\Scripts\python.exe app.py

pause
