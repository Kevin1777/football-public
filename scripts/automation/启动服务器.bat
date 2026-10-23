@echo off
chcp 65001 >nul
cls
echo ========================================
echo 📡 必发采集控制台
echo ========================================
echo.
echo 正在启动服务器...
echo.
echo 访问地址：
echo   本地: http://localhost:5001
echo   域名: http://fb.kevinsun7.dpdns.org
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.
python app.py
pause
