@echo off
chcp 65001 >nul
echo ================================================================================
echo 🔧 批量回测问题快速修复
echo ================================================================================
echo.

echo 步骤1: 停止所有Python进程...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 >nul
echo    ✅ 已停止
echo.

echo 步骤2: 清理Python缓存...
for /r %%i in (*.pyc) do del "%%i" >nul 2>&1
for /d /r %%i in (__pycache__) do rd /s /q "%%i" >nul 2>&1
echo    ✅ 已清理
echo.

echo 步骤3: 启动Flask应用（前台运行）...
echo    请等待看到 "Running on http://0.0.0.0:5000" 才算成功！
echo.
echo ================================================================================
echo.

python app.py

pause
