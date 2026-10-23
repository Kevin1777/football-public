#!/bin/bash
# ============================================================================
# 服务器部署脚本 - Linux/Ubuntu
# ============================================================================

set -e  # 遇到错误立即停止

echo "=========================================="
echo "  必发网足球数据采集系统 - 服务器部署"
echo "=========================================="

# 检查Python版本
echo ""
echo "1️⃣  检查Python版本..."
python3 --version || { echo "❌ Python3未安装"; exit 1; }

# 创建虚拟环境（推荐）
echo ""
echo "2️⃣  创建Python虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "3️⃣  激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo ""
echo "4️⃣  升级pip..."
pip install --upgrade pip

# 安装依赖
echo ""
echo "5️⃣  安装Python依赖包..."
pip install -r requirements.txt

# 检查关键包
echo ""
echo "6️⃣  验证关键包安装..."
python3 -c "import flask; print('✅ Flask:', flask.__version__)" || echo "❌ Flask安装失败"
python3 -c "import pandas; print('✅ Pandas:', pandas.__version__)" || echo "❌ Pandas安装失败"
python3 -c "import selenium; print('✅ Selenium:', selenium.__version__)" || echo "❌ Selenium安装失败"
python3 -c "import apscheduler; print('✅ APScheduler:', apscheduler.__version__)" || echo "❌ APScheduler安装失败"

# 安装Chrome和ChromeDriver
echo ""
echo "7️⃣  检查Chrome浏览器..."
if command -v google-chrome &> /dev/null; then
    echo "✅ Chrome已安装: $(google-chrome --version)"
else
    echo "⚠️  Chrome未安装，正在安装..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
    echo "✅ Chrome安装完成"
fi

# 创建必要的目录
echo ""
echo "8️⃣  创建数据目录..."
mkdir -p data/cache data/details data/handicaps debug_html PDF
echo "✅ 目录结构已创建"

# 设置权限
echo ""
echo "9️⃣  设置文件权限..."
chmod +x app.py
chmod 755 data debug_html PDF
echo "✅ 权限设置完成"

# 检查配置文件
echo ""
echo "🔟  检查配置文件..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "⚠️  已从.env.example创建.env文件，请编辑配置"
    else
        echo "⚠️  .env文件不存在，请手动创建"
    fi
else
    echo "✅ .env文件已存在"
fi

if [ ! -f "config.json" ]; then
    echo "⚠️  config.json不存在，请创建并配置账号密码"
else
    echo "✅ config.json已存在"
fi

echo ""
echo "=========================================="
echo "  ✅ 部署完成！"
echo "=========================================="
echo ""
echo "📝 下一步操作："
echo "   1. 编辑 .env 文件，配置百度OCR等参数"
echo "   2. 编辑 config.json 文件，配置必发网账号"
echo "   3. 运行服务：python3 app.py"
echo ""
echo "🔗 访问地址："
echo "   本地：http://127.0.0.1:5001"
echo "   外网：http://服务器IP:5001"
echo ""
