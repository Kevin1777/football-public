#!/bin/bash

# 🚀 足球分析系统 - 服务器快速部署脚本
# 适用于 Linux 服务器（Ubuntu/CentOS）

echo "================================"
echo "🚀 足球分析系统 - 服务器部署"
echo "================================"
echo ""

# 检查Python版本
echo "📋 检查Python版本..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python3未安装，请先安装Python 3.8+"
    exit 1
fi

# 进入项目目录
cd /root/football || exit 1
echo "✅ 当前目录: $(pwd)"
echo ""

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
else
    echo "✅ 虚拟环境已存在"
fi
echo ""

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "📦 升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📦 安装依赖包..."
pip install -r requirements.txt

# 创建必要的目录
echo "📂 创建目录结构..."
mkdir -p data logs progress
echo "✅ 目录创建完成"
echo ""

# 检查环境变量
echo "🔍 检查环境变量..."
if [ -z "$WECOM_WEBHOOK" ]; then
    echo "⚠️  WECOM_WEBHOOK 未设置"
    echo "   请执行: export WECOM_WEBHOOK='your_webhook_url'"
else
    echo "✅ WECOM_WEBHOOK 已设置"
fi
echo ""

# 显示配置信息
echo "================================"
echo "📊 部署配置"
echo "================================"
echo "工作目录: /root/football"
echo "数据目录: /root/football/data"
echo "日志目录: /root/football/logs"
echo "监听地址: 0.0.0.0:5002"
echo "调试模式: False"
echo ""

# 提示下一步
echo "================================"
echo "✅ 部署准备完成！"
echo "================================"
echo ""
echo "下一步操作："
echo "1. 设置环境变量（如果还没设置）："
echo "   export WECOM_WEBHOOK='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY'"
echo ""
echo "2. 启动服务："
echo "   python app.py"
echo ""
echo "3. 或使用systemd管理（推荐）："
echo "   sudo cp football.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl start football"
echo "   sudo systemctl enable football"
echo ""
echo "4. 查看日志："
echo "   tail -f logs/app.log"
echo "   或"
echo "   sudo journalctl -u football -f"
echo ""
