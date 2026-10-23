#!/bin/bash
# Football 服务管理脚本（改进版）
# 用法: fb s(启动) x(停止) k(强杀) r(重启) p(状态) l(日志)

PROJECT_DIR="/root/football"
SESSION_NAME="fb"
LOG_FILE="$PROJECT_DIR/logs/app_full.log"

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 错误：找不到项目目录 $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/logs"

check_process() {
    local name=$1
    pgrep -f "$name" > /dev/null 2>&1
    return $?
}

start_service() {
    # 检查是否已在运行
    if check_process "gunicorn.*app:app"; then
        echo "⚠️  Web服务已在运行"
    else
        echo "🚀 启动 Web 服务..."
        # 🔥 启用定时任务调度器（自动恢复采集、自动登录等）
        export DISABLE_SCHEDULER=false
        nohup gunicorn -w 1 -k gthread --threads 4 -b 0.0.0.0:5001 --timeout 120 app:app >> "$LOG_FILE" 2>&1 &
        sleep 2
        if check_process "gunicorn.*app:app"; then
            echo "✅ Web 服务已启动"
        else
            echo "❌ Web 服务启动失败"
        fi
    fi
    
    if check_process "scheduler_worker.py"; then
        echo "⚠️  定时任务已在运行"
    else
        echo "🚀 启动定时任务..."
        nohup python3 scheduler_worker.py >> "$PROJECT_DIR/logs/scheduler_worker.log" 2>&1 &
        sleep 2
        if check_process "scheduler_worker.py"; then
            echo "✅ 定时任务已启动"
        else
            echo "❌ 定时任务启动失败"
        fi
    fi
}

stop_service() {
    echo "⏹️  停止服务..."
    
    # 停止 gunicorn
    pkill -f "gunicorn.*app:app" 2>/dev/null
    
    # 停止 scheduler_worker
    pkill -f "scheduler_worker.py" 2>/dev/null
    
    # 等待进程退出
    sleep 2
    
    # 检查是否停止成功
    if check_process "gunicorn.*app:app" || check_process "scheduler_worker.py"; then
        echo "⚠️  部分进程未停止，尝试强制杀死..."
        pkill -9 -f "gunicorn.*app:app" 2>/dev/null
        pkill -9 -f "scheduler_worker.py" 2>/dev/null
        sleep 1
    fi
    
    echo "✅ 服务已停止"
}

kill_service() {
    echo "💀 强制杀死所有进程..."
    pkill -9 -f "gunicorn" 2>/dev/null
    pkill -9 -f "scheduler_worker.py" 2>/dev/null
    
    # 杀死 tmux 会话（如果存在）
    tmux kill-session -t $SESSION_NAME 2>/dev/null
    
    echo "✅ 已强制杀死所有进程"
}

show_status() {
    echo "========== 服务状态 =========="
    echo ""
    
    echo "--- Web 服务 ---"
    if check_process "gunicorn.*app:app"; then
        echo "✅ 运行中"
        ps aux | grep "gunicorn" | grep -v grep | head -1
    else
        echo "❌ 未运行"
    fi
    echo ""
    
    echo "--- 定时任务 ---"
    if check_process "scheduler_worker.py"; then
        echo "✅ 运行中"
        ps aux | grep "scheduler_worker.py" | grep -v grep | head -1
    else
        echo "❌ 未运行"
    fi
    echo ""
    
    echo "--- 端口监听 ---"
    netstat -tlnp 2>/dev/null | grep ":5001" || ss -tlnp 2>/dev/null | grep ":5001" || echo "❌ 5001端口未监听"
    echo ""
    
    echo "=============================="
}

show_logs() {
    echo "📋 显示最近日志..."
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "❌ 日志文件不存在: $LOG_FILE"
    fi
}

# 使用 tmux 启动（可选）
start_with_tmux() {
    tmux has-session -t $SESSION_NAME 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "⚠️  tmux 会话已存在"
        tmux attach -t $SESSION_NAME
    else
        echo "🚀 创建 tmux 会话..."
        
        # 创建新会话并启动 Web 服务
        tmux new-session -d -s $SESSION_NAME -n "web" "cd $PROJECT_DIR && gunicorn -w 1 -k gthread --threads 4 -b 0.0.0.0:5001 --timeout 120 app:app 2>&1 | tee -a $LOG_FILE"
        
        # 等待窗口创建
        sleep 1
        
        # 分割窗口并启动定时任务
        tmux split-window -h -t $SESSION_NAME "cd $PROJECT_DIR && python3 scheduler_worker.py 2>&1 | tee -a $PROJECT_DIR/logs/scheduler_worker.log"
        
        # 再分割一个窗口显示日志
        tmux split-window -v -t $SESSION_NAME "tail -f $LOG_FILE"
        
        # 调整布局
        tmux select-layout -t $SESSION_NAME tiled
        
        echo "✅ tmux 会话已创建"
        echo "   使用 'fb l' 或 'tmux attach -t fb' 查看"
    fi
}

# 主逻辑
case "$1" in
    s|start)
        start_service
        ;;
    t|tmux)
        start_with_tmux
        ;;
    x|stop)
        stop_service
        ;;
    k|kill)
        kill_service
        ;;
    r|restart)
        stop_service
        sleep 2
        start_service
        echo "🔄 已重启"
        ;;
    p|status)
        show_status
        ;;
    l|log|logs)
        show_logs
        ;;
    *)
        echo "Football 服务管理脚本"
        echo ""
        echo "用法: $0 <命令>"
        echo ""
        echo "命令:"
        echo "  s, start   - 启动服务（后台运行）"
        echo "  t, tmux    - 使用 tmux 启动（可查看实时输出）"
        echo "  x, stop    - 停止服务"
        echo "  k, kill    - 强制杀死所有进程"
        echo "  r, restart - 重启服务"
        echo "  p, status  - 查看状态"
        echo "  l, logs    - 查看日志"
        ;;
esac
