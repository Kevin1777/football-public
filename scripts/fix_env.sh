#!/bin/bash
# ==============================================================================
# 环境修复脚本 - 修复交易机器人和Football的依赖问题
# ==============================================================================

echo "========================================"
echo "  环境诊断与修复脚本"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==============================================================================
# 1. 修复交易机器人 (tradingbot)
# ==============================================================================
echo -e "${YELLOW}[1/3] 检查交易机器人环境...${NC}"

TRADINGBOT_DIR="/root/tradingbot"
if [ -d "$TRADINGBOT_DIR" ]; then
    cd "$TRADINGBOT_DIR"
    
    # 检查虚拟环境
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "  已激活虚拟环境: venv"
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "  已激活虚拟环境: .venv"
    fi
    
    # 检查 pandas_ta
    if python -c "import pandas_ta" 2>/dev/null; then
        echo -e "  ${GREEN}✓ pandas_ta 已安装${NC}"
    else
        echo -e "  ${RED}✗ pandas_ta 缺失，正在安装...${NC}"
        pip install pandas-ta
        if [ $? -eq 0 ]; then
            echo -e "  ${GREEN}✓ pandas_ta 安装成功${NC}"
        else
            echo -e "  ${RED}✗ pandas_ta 安装失败${NC}"
        fi
    fi
    
    # 检查其他关键依赖
    echo ""
    echo "  检查其他关键依赖:"
    for pkg in ccxt flask pandas numpy; do
        if python -c "import $pkg" 2>/dev/null; then
            echo -e "    ${GREEN}✓ $pkg${NC}"
        else
            echo -e "    ${RED}✗ $pkg 缺失${NC}"
            pip install $pkg
        fi
    done
else
    echo -e "  ${YELLOW}⚠ 交易机器人目录不存在: $TRADINGBOT_DIR${NC}"
fi

echo ""

# ==============================================================================
# 2. 修复 Football 数据工作台
# ==============================================================================
echo -e "${YELLOW}[2/3] 检查 Football 环境...${NC}"

FOOTBALL_DIR="/root/football"
if [ ! -d "$FOOTBALL_DIR" ]; then
    FOOTBALL_DIR="$HOME/football"
fi

if [ -d "$FOOTBALL_DIR" ]; then
    cd "$FOOTBALL_DIR"
    
    # 检查虚拟环境
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "  已激活虚拟环境: venv"
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "  已激活虚拟环境: .venv"
    fi
    
    # 检查关键依赖
    echo ""
    echo "  检查关键依赖:"
    
    MISSING_PKGS=""
    
    # selenium
    if python -c "import selenium" 2>/dev/null; then
        echo -e "    ${GREEN}✓ selenium${NC}"
    else
        echo -e "    ${RED}✗ selenium 缺失${NC}"
        MISSING_PKGS="$MISSING_PKGS selenium"
    fi
    
    # ddddocr (验证码识别)
    if python -c "import ddddocr" 2>/dev/null; then
        echo -e "    ${GREEN}✓ ddddocr${NC}"
    else
        echo -e "    ${RED}✗ ddddocr 缺失${NC}"
        MISSING_PKGS="$MISSING_PKGS ddddocr"
    fi
    
    # requests
    if python -c "import requests" 2>/dev/null; then
        echo -e "    ${GREEN}✓ requests${NC}"
    else
        echo -e "    ${RED}✗ requests 缺失${NC}"
        MISSING_PKGS="$MISSING_PKGS requests"
    fi
    
    # flask
    if python -c "import flask" 2>/dev/null; then
        echo -e "    ${GREEN}✓ flask${NC}"
    else
        echo -e "    ${RED}✗ flask 缺失${NC}"
        MISSING_PKGS="$MISSING_PKGS flask"
    fi
    
    # 安装缺失的包
    if [ -n "$MISSING_PKGS" ]; then
        echo ""
        echo -e "  ${YELLOW}正在安装缺失的包:$MISSING_PKGS${NC}"
        pip install $MISSING_PKGS
    fi
    
    # 检查Chrome/Chromium
    echo ""
    echo "  检查浏览器环境:"
    if command -v google-chrome &> /dev/null; then
        echo -e "    ${GREEN}✓ Google Chrome 已安装${NC}"
    elif command -v chromium-browser &> /dev/null; then
        echo -e "    ${GREEN}✓ Chromium 已安装${NC}"
    elif command -v chromium &> /dev/null; then
        echo -e "    ${GREEN}✓ Chromium 已安装${NC}"
    else
        echo -e "    ${RED}✗ Chrome/Chromium 未安装${NC}"
        echo "      运行: apt install chromium-browser"
    fi
    
    # 检查ChromeDriver
    if command -v chromedriver &> /dev/null; then
        echo -e "    ${GREEN}✓ ChromeDriver 已安装${NC}"
    else
        echo -e "    ${YELLOW}⚠ ChromeDriver 可能需要安装${NC}"
    fi
    
    # 检查cookies文件
    echo ""
    echo "  检查登录状态:"
    COOKIES_FILE="$FOOTBALL_DIR/config/bifaw_cookies.json"
    if [ -f "$COOKIES_FILE" ]; then
        COOKIE_AGE=$(( ($(date +%s) - $(stat -c %Y "$COOKIES_FILE")) / 3600 ))
        echo -e "    Cookies文件存在，${COOKIE_AGE}小时前更新"
        if [ $COOKIE_AGE -gt 24 ]; then
            echo -e "    ${YELLOW}⚠ Cookies可能已过期，需要重新登录${NC}"
        fi
    else
        echo -e "    ${RED}✗ Cookies文件不存在，需要登录${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ Football目录不存在${NC}"
fi

echo ""

# ==============================================================================
# 3. 重启服务
# ==============================================================================
echo -e "${YELLOW}[3/3] 是否重启服务？${NC}"
echo ""
echo "  输入 'y' 重启所有服务，其他键跳过"
read -r -p "  > " response

if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    echo ""
    echo "  重启交易机器人..."
    if [ -f "/usr/local/bin/tb" ]; then
        tb r
    else
        echo "    tb 命令不存在，请手动重启"
    fi
    
    echo ""
    echo "  重启 Football..."
    if [ -f "/usr/local/bin/fb" ]; then
        fb r
    else
        echo "    fb 命令不存在，请手动重启"
    fi
fi

echo ""
echo "========================================"
echo -e "  ${GREEN}诊断完成！${NC}"
echo "========================================"
echo ""
echo "如果 Football 登录失败，请手动触发登录:"
echo "  1. 访问 Web 界面"
echo "  2. 点击登录/验证按钮"
echo "  3. 等待 OCR 自动识别验证码"
echo ""
