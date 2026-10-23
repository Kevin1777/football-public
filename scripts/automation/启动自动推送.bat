@echo off
chcp 65001 >nul
title 足球自动推荐推送系统

echo ============================================================
echo    ⚽ 足球比赛自动推荐推送系统
echo ============================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未检测到Python环境
    echo 请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

REM 检查依赖
echo 检查依赖包...
python -c "import schedule, requests, pandas" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ⚠️  检测到缺少依赖包，正在安装...
    pip install schedule requests pandas
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请手动运行：pip install schedule requests pandas
        pause
        exit /b 1
    )
    echo ✅ 依赖安装完成
    echo.
)

REM 启动系统
echo 启动自动推送系统...
echo.
python auto_recommend_push.py

if errorlevel 1 (
    echo.
    echo ❌ 程序异常退出
    pause
)
