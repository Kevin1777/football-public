#!/bin/bash
# 设定项目路径 (如果您的路径不同，请修改此处)
PROJECT_DIR="/root/football"
SESSION_NAME="fb"

# 检查目录是否存在
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 错误：找不到项目目录 $PROJECT_DIR"
    echo "   请编辑 /usr/local/bin/fb 修改 PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

case "$1" in
  s)
    # 启动 (Start)
    tmux has-session -t $SESSION_NAME 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "⚠️  服务已在运行 (tmux会话: $SESSION_NAME)"
    else
        echo "🚀 正在启动服务..."
        # 1. 创建会话并启动 Web (Gunicorn)
        # -w 1 -k gthread --threads 4: 1个进程4个线程，适合IO密集型
        tmux new -d -s $SESSION_NAME -n "web" "gunicorn -w 1 -k gthread --threads 4 -b 0.0.0.0:5001 --timeout 120 app:app"
        
        # 2. 分割窗口启动 Scheduler (定时任务)
        tmux split-window -h -t $SESSION_NAME "python3 scheduler_worker.py"
        
        # 3. 分割窗口查看日志
        tmux split-window -v -t $SESSION_NAME "tail -f logs/app_full.log"
        
        # 调整布局
        tmux select-layout tiled
        
        echo "✅ 服务已启动！"
        echo "   Web服务: 0.0.0.0:5001"
        echo "   定时任务: 运行中"
    fi
    ;;
    
  x)
    # 停止 (Stop)
    tmux kill-session -t $SESSION_NAME 2>/dev/null
    pkill -f "gunicorn"
    pkill -f "scheduler_worker.py"
    echo "⏹️ 服务已停止"
    ;;

  k)
    # 强制停止 (Kill)
    tmux kill-session -t $SESSION_NAME 2>/dev/null
    pkill -9 -f "gunicorn"
    pkill -9 -f "scheduler_worker.py"
    echo "💀 服务已强制杀死"
    ;;
    
  r)
    # 重启 (Restart)
    $0 x
    sleep 2
    $0 s
    echo "🔄 服务已重启"
    ;;
    
  p)
    # 状态 (Process)
    echo "--- Tmux Session ---"
    tmux has-session -t $SESSION_NAME 2>/dev/null && echo "✅ 运行中" || echo "❌ 未运行"
    echo ""
    echo "--- Web (Gunicorn) ---"
    ps aux | grep "gunicorn" | grep -v grep || echo "❌ 未运行"
    echo ""
    echo "--- Scheduler ---"
    ps aux | grep "scheduler_worker.py" | grep -v grep || echo "❌ 未运行"
    ;;
    
  l)
    # 查看 (Log/Attach)
    tmux attach -t $SESSION_NAME
    ;;
    
  *)
    echo "⚽️ 足球数据系统管理命令 (fb)"
    echo "--------------------------------"
    echo "  fb s   - 启动 (Start)"
    echo "  fb x   - 停止 (Stop)"
    echo "  fb k   - 强杀 (Kill)"
    echo "  fb r   - 重启 (Restart)"
    echo "  fb p   - 状态 (Process)"
    echo "  fb l   - 查看 (Log/Attach)"
    ;;
esac
