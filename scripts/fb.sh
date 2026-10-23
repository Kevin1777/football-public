#!/bin/bash
# ==============================================================================
# Football 足球数据采集系统 - 服务管理脚本
# 用法: fb [命令]
# ==============================================================================

# 配置
BOT_DIR="/root/football"  # 项目目录（固定路径）
TMUX_SESSION="football"
WEB_PORT=5001
CONDA_ENV="football"  # Conda环境名称

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$BOT_DIR"

# 显示帮助
show_help() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Football 足球数据采集 管理脚本          ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    echo "用法: fb [命令]"
    echo ""
    echo "命令:"
    echo "  s, start    启动服务 (后台运行)"
    echo "  x, stop     停止服务"
    echo "  r, restart  重启服务"
    echo "  k, kill     强制杀死所有进程"
    echo "  p, status   查看运行状态"
    echo "  l, logs     实时查看日志"
    echo "  d, daemon   启动守护进程模式（崩溃自动重启）"
    echo "  xd          停止守护进程"
    echo "  h, help     显示帮助"
    echo ""
}

# 启动服务
start_service() {
    echo -e "${GREEN}[FB] 启动服务...${NC}"
    
    # 检查是否已运行
    if pgrep -f "python3.*app.py.*5001" > /dev/null || pgrep -f "python3 $BOT_DIR/app.py" > /dev/null; then
        echo -e "${YELLOW}[FB] 服务已在运行中${NC}"
        return
    fi
    
    # 确保logs目录存在
    mkdir -p "$BOT_DIR/logs"
    
    cd "$BOT_DIR"
    
    # 激活conda环境
    source /root/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source /root/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
    conda activate $CONDA_ENV 2>/dev/null || true
    
    # 启动Web服务器
    nohup bash -c "source /root/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source /root/anaconda3/etc/profile.d/conda.sh 2>/dev/null; conda activate $CONDA_ENV; python3 app.py" > logs/football.log 2>&1 &
    WEB_PID=$!
    echo -e "${GREEN}[FB] 服务已启动 (PID: $WEB_PID)${NC}"
    
    sleep 3
    
    # 检查是否成功
    if netstat -tlnp 2>/dev/null | grep -q ":$WEB_PORT" || ss -tlnp 2>/dev/null | grep -q ":$WEB_PORT"; then
        echo -e "${GREEN}[FB] 服务启动成功！${NC}"
        echo -e "${GREEN}[FB] Web: http://$(hostname -I | awk '{print $1}'):$WEB_PORT${NC}"
    else
        echo -e "${RED}[FB] 启动可能失败，请检查 logs/football.log${NC}"
        tail -20 "$BOT_DIR/logs/football.log"
    fi
}

# 停止服务
stop_service() {
    echo -e "${YELLOW}[FB] 停止服务...${NC}"
    pkill -f "python3 $BOT_DIR/app.py" 2>/dev/null
    pkill -f "python3.*football.*app.py" 2>/dev/null
    # 杀死占用5001端口的进程
    fuser -k 5001/tcp 2>/dev/null
    echo -e "${GREEN}[FB] 服务已停止${NC}"
}

# 重启服务
restart_service() {
    echo -e "${YELLOW}[FB] 重启服务...${NC}"
    stop_service
    sleep 2
    start_service
}

# 强制杀死
kill_all() {
    echo -e "${RED}[FB] 强制杀死所有进程...${NC}"
    pkill -9 -f "python3 $BOT_DIR/app.py" 2>/dev/null
    pkill -9 -f "python3.*football.*app.py" 2>/dev/null
    fuser -k 5001/tcp 2>/dev/null
    echo -e "${GREEN}[FB] 已杀死${NC}"
}

# 查看状态
show_status() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Football 运行状态                       ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}[进程]${NC}"
    FB_PID=$(pgrep -f "python3.*football.*app.py" 2>/dev/null | head -1)
    if [ -n "$FB_PID" ]; then
        echo -e "  Football服务: ${GREEN}运行中${NC} (PID: $FB_PID)"
    else
        echo -e "  Football服务: ${RED}未运行${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}[端口]${NC}"
    if netstat -tlnp 2>/dev/null | grep -q ":$WEB_PORT" || ss -tlnp 2>/dev/null | grep -q ":$WEB_PORT"; then
        echo -e "  $WEB_PORT: ${GREEN}监听中${NC}"
    else
        echo -e "  $WEB_PORT: ${RED}未监听${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}[日志]${NC}"
    echo "  查看日志: tail -f $BOT_DIR/logs/football.log"
    echo ""
    
    echo -e "${YELLOW}[最近日志]${NC}"
    if [ -f "$BOT_DIR/logs/football.log" ]; then
        tail -5 "$BOT_DIR/logs/football.log"
    fi
    echo ""
}

# 查看日志
show_logs() {
    echo -e "${GREEN}[FB] 实时日志 (Ctrl+C 退出)${NC}"
    tail -f "$BOT_DIR/logs/football.log"
}

# 启动守护进程（自动重启）
start_daemon() {
    echo -e "${GREEN}[FB] 启动守护进程模式（自动重启）...${NC}"
    
    # 先停止旧进程
    stop_service
    sleep 2
    
    # 启动守护进程
    cd "$BOT_DIR"
    nohup bash -c "source /root/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source /root/anaconda3/etc/profile.d/conda.sh 2>/dev/null; conda activate $CONDA_ENV; bash scripts/fb_daemon.sh" > logs/daemon.log 2>&1 &
    
    echo -e "${GREEN}[FB] 守护进程已启动，服务会自动重启${NC}"
    echo -e "${GREEN}[FB] 查看守护日志: tail -f $BOT_DIR/logs/daemon.log${NC}"
}

# 停止守护进程
stop_daemon() {
    echo -e "${YELLOW}[FB] 停止守护进程...${NC}"
    pkill -f "fb_daemon.sh" 2>/dev/null
    stop_service
    echo -e "${GREEN}[FB] 守护进程已停止${NC}"
}

# 主逻辑
case "$1" in
    s|start)    start_service ;;
    x|stop)     stop_service ;;
    r|restart)  restart_service ;;
    k|kill)     kill_all ;;
    p|status)   show_status ;;
    l|logs)     show_logs ;;
    d|daemon)   start_daemon ;;
    xd|stopdaemon) stop_daemon ;;
    h|help|"")  show_help ;;
    *)          echo -e "${RED}未知命令: $1${NC}"; show_help ;;
esac
