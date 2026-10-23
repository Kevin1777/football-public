#!/bin/bash
# ==============================================================================
# 一键修复脚本 - 同时修复 TradingBot 和 Football 环境问题
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   一键环境修复脚本 - TradingBot & Football                ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
# 第一部分：安装 Python 3.12
# ==============================================================================
echo -e "${YELLOW}[1/6] 检查并安装 Python 3.12...${NC}"

if command -v python3.12 &> /dev/null; then
    echo -e "  ${GREEN}✓ Python 3.12 已安装${NC}"
    python3.12 --version
else
    echo -e "  ${YELLOW}正在安装 Python 3.12...${NC}"
    apt update -qq
    apt install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update -qq
    apt install -y python3.12 python3.12-venv python3.12-dev
    echo -e "  ${GREEN}✓ Python 3.12 安装完成${NC}"
fi

echo ""

# ==============================================================================
# 第二部分：修复 TradingBot
# ==============================================================================
echo -e "${YELLOW}[2/6] 修复 TradingBot 环境...${NC}"

TRADINGBOT_DIR="/root/tradingbot"

if [ -d "$TRADINGBOT_DIR" ]; then
    cd "$TRADINGBOT_DIR"
    
    # 停止服务
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "python.*tradingbot.py" 2>/dev/null || true
    
    # 备份并删除旧虚拟环境
    [ -d "venv" ] && rm -rf venv
    [ -d "venv312" ] && rm -rf venv312
    
    # 创建新虚拟环境
    echo "  创建 Python 3.12 虚拟环境..."
    python3.12 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip setuptools wheel -q
    
    # 安装依赖
    echo "  安装核心依赖..."
    pip install ccxt pandas pandas-ta numpy -q
    pip install flask flask-socketio flask-sqlalchemy -q
    pip install sqlalchemy aiohttp eventlet -q
    pip install requests python-dateutil tqdm numba cryptography -q
    
    # 验证
    if python -c "import pandas_ta" 2>/dev/null; then
        echo -e "  ${GREEN}✓ TradingBot 环境修复完成${NC}"
    else
        echo -e "  ${RED}✗ pandas_ta 安装失败${NC}"
    fi
    
    deactivate
else
    echo -e "  ${YELLOW}⚠ TradingBot 目录不存在: $TRADINGBOT_DIR${NC}"
fi

echo ""

# ==============================================================================
# 第三部分：修复 Football
# ==============================================================================
echo -e "${YELLOW}[3/6] 修复 Football 环境...${NC}"

FOOTBALL_DIR="/root/football"

if [ -d "$FOOTBALL_DIR" ]; then
    cd "$FOOTBALL_DIR"
    
    # 停止服务
    pkill -f "python3.*football.*app.py" 2>/dev/null || true
    fuser -k 5001/tcp 2>/dev/null || true
    
    # 备份并删除旧虚拟环境
    [ -d "venv" ] && rm -rf venv
    
    # 创建新虚拟环境
    echo "  创建 Python 3.12 虚拟环境..."
    python3.12 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip setuptools wheel -q
    
    # 安装依赖
    echo "  安装核心依赖..."
    pip install flask flask-cors pandas numpy -q
    pip install selenium webdriver-manager requests beautifulsoup4 lxml -q
    pip install apscheduler psutil python-dateutil -q
    pip install pillow pdfplumber openpyxl -q
    
    # 安装 ddddocr (验证码识别)
    echo "  安装验证码识别库..."
    pip install ddddocr -q 2>/dev/null || echo "  ⚠ ddddocr 安装失败，可能需要手动处理"
    
    # 验证
    if python -c "import selenium; import flask" 2>/dev/null; then
        echo -e "  ${GREEN}✓ Football 环境修复完成${NC}"
    else
        echo -e "  ${RED}✗ 部分依赖安装失败${NC}"
    fi
    
    deactivate
else
    echo -e "  ${YELLOW}⚠ Football 目录不存在: $FOOTBALL_DIR${NC}"
fi

echo ""

# ==============================================================================
# 第四部分：更新 fb.sh 使用虚拟环境
# ==============================================================================
echo -e "${YELLOW}[4/6] 更新启动脚本...${NC}"

# 更新 fb.sh
if [ -f "$FOOTBALL_DIR/scripts/fb.sh" ]; then
    cat > /usr/local/bin/fb << 'FBEOF'
#!/bin/bash
# Football 服务管理脚本 (使用venv)

BOT_DIR="/root/football"
VENV_DIR="$BOT_DIR/venv"
WEB_PORT=5001

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$BOT_DIR"

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
fi

case "$1" in
    s|start)
        echo -e "${GREEN}[FB] 启动服务...${NC}"
        mkdir -p "$BOT_DIR/logs"
        nohup python app.py > logs/football.log 2>&1 &
        sleep 2
        echo -e "${GREEN}[FB] 服务已启动 (PID: $!)${NC}"
        echo -e "${GREEN}[FB] Web: http://$(hostname -I | awk '{print $1}'):$WEB_PORT${NC}"
        ;;
    x|stop)
        echo -e "${YELLOW}[FB] 停止服务...${NC}"
        pkill -f "python.*football.*app.py" 2>/dev/null
        fuser -k 5001/tcp 2>/dev/null
        echo -e "${GREEN}[FB] 服务已停止${NC}"
        ;;
    r|restart)
        $0 x; sleep 2; $0 s
        ;;
    k|kill)
        pkill -9 -f "python.*football.*app.py" 2>/dev/null
        fuser -k 5001/tcp 2>/dev/null
        echo -e "${GREEN}[FB] 已杀死${NC}"
        ;;
    p|status)
        echo -e "${BLUE}[FB] 状态:${NC}"
        pgrep -f "python.*football.*app.py" && echo "  运行中" || echo "  未运行"
        ;;
    l|logs)
        tail -f "$BOT_DIR/logs/football.log"
        ;;
    *)
        echo "用法: fb [s|x|r|k|p|l]"
        echo "  s=启动 x=停止 r=重启 k=杀死 p=状态 l=日志"
        ;;
esac
FBEOF
    chmod +x /usr/local/bin/fb
    echo -e "  ${GREEN}✓ fb 命令已更新${NC}"
fi

# 更新 tb 命令
if [ -f "$TRADINGBOT_DIR/scripts/tb.sh" ]; then
    cp "$TRADINGBOT_DIR/scripts/tb.sh" /usr/local/bin/tb
    chmod +x /usr/local/bin/tb
    echo -e "  ${GREEN}✓ tb 命令已更新${NC}"
fi

echo ""

# ==============================================================================
# 第五部分：检查 Chrome/Chromium
# ==============================================================================
echo -e "${YELLOW}[5/6] 检查浏览器环境...${NC}"

if command -v google-chrome &> /dev/null; then
    echo -e "  ${GREEN}✓ Google Chrome 已安装${NC}"
elif command -v chromium-browser &> /dev/null; then
    echo -e "  ${GREEN}✓ Chromium 已安装${NC}"
elif command -v chromium &> /dev/null; then
    echo -e "  ${GREEN}✓ Chromium 已安装${NC}"
else
    echo -e "  ${YELLOW}⚠ Chrome/Chromium 未安装，正在安装...${NC}"
    apt install -y chromium-browser 2>/dev/null || apt install -y chromium 2>/dev/null || echo "  请手动安装Chrome"
fi

echo ""

# ==============================================================================
# 第六部分：启动服务
# ==============================================================================
echo -e "${YELLOW}[6/6] 启动服务...${NC}"

# 启动 TradingBot
if [ -d "$TRADINGBOT_DIR" ]; then
    echo "  启动 TradingBot..."
    tb s 2>/dev/null || echo "  ⚠ TradingBot 启动失败，请手动执行: tb s"
fi

# 启动 Football
if [ -d "$FOOTBALL_DIR" ]; then
    echo "  启动 Football..."
    fb s 2>/dev/null || echo "  ⚠ Football 启动失败，请手动执行: fb s"
fi

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ${GREEN}修复完成！${BLUE}                                              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "服务状态:"
echo "  TradingBot: http://$(hostname -I | awk '{print $1}'):5000"
echo "  Football:   http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo -e "${YELLOW}注意: Football 登录问题需要访问Web界面手动触发验证码登录${NC}"
echo ""
