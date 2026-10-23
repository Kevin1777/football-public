#!/bin/bash
# ==============================================================================
# Football 守护进程 - 自动重启崩溃的服务
# 用法: nohup ./fb_daemon.sh &
# ==============================================================================

BOT_DIR="/root/football"
CONDA_ENV="football"
WEB_PORT=5001
LOG_FILE="$BOT_DIR/logs/football.log"
DAEMON_LOG="$BOT_DIR/logs/daemon.log"
CHECK_INTERVAL=30  # 每30秒检查一次

# 初始化conda
init_conda() {
    if [ -f "/root/miniconda3/etc/profile.d/conda.sh" ]; then
        source /root/miniconda3/etc/profile.d/conda.sh
    elif [ -f "/root/anaconda3/etc/profile.d/conda.sh" ]; then
        source /root/anaconda3/etc/profile.d/conda.sh
    fi
}

# 日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$DAEMON_LOG"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查端口是否监听（更准确的检测方式）
is_running() {
    netstat -tlnp 2>/dev/null | grep -q ":$WEB_PORT " || \
    ss -tlnp 2>/dev/null | grep -q ":$WEB_PORT "
}

# 启动服务
start_service() {
    log "🚀 启动Football服务..."
    
    # 先杀死可能残留的进程
    pkill -f "python3.*app.py" 2>/dev/null
    sleep 2
    
    cd "$BOT_DIR"
    
    # 初始化并激活conda
    init_conda
    conda activate $CONDA_ENV 2>/dev/null || log "⚠️ conda环境激活失败，使用系统Python"
    
    # 启动服务
    nohup python3 app.py >> "$LOG_FILE" 2>&1 &
    local PID=$!
    log "📝 启动PID: $PID"
    
    sleep 8
    
    if is_running; then
        log "✅ 服务启动成功，端口 $WEB_PORT 已监听"
    else
        log "❌ 服务启动失败，查看日志: $LOG_FILE"
        tail -20 "$LOG_FILE" >> "$DAEMON_LOG"
    fi
}

# 主循环
main() {
    log "=========================================="
    log "🔄 Football守护进程启动"
    log "=========================================="
    
    # 初始化conda（在主进程中）
    init_conda
    
    # 初始启动
    if ! is_running; then
        start_service
    else
        log "✅ 服务已在运行中 (端口 $WEB_PORT)"
    fi
    
    # 监控循环
    while true; do
        sleep $CHECK_INTERVAL
        
        if ! is_running; then
            log "⚠️ 检测到服务停止（端口 $WEB_PORT 未监听），正在重启..."
            start_service
        fi
    done
}

# 运行
main
