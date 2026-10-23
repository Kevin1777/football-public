#!/bin/bash
# ==============================================================================
# Football 足球数据采集系统 - 安装脚本
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  Football 足球数据采集系统 安装"
echo "========================================"
echo ""

# 1. 删除旧命令
echo "[1/4] 删除旧命令..."
sudo rm -f /usr/local/bin/fb

# 2. 复制脚本
echo "[2/4] 安装 fb 命令..."
sudo cp "$SCRIPT_DIR/fb.sh" /usr/local/bin/fb

# 3. 设置权限
echo "[3/4] 设置执行权限..."
sudo chmod +x /usr/local/bin/fb

# 4. 更新脚本中的路径
echo "[4/4] 配置路径..."
sudo sed -i "s|BOT_DIR=.*|BOT_DIR=\"$BOT_DIR\"|" /usr/local/bin/fb

echo ""
echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "使用方法:"
echo "  fb s      # 启动服务（后台）"
echo "  fb x      # 停止服务"
echo "  fb r      # 重启"
echo "  fb k      # 强制杀死"
echo "  fb p      # 查看状态"
echo "  fb l      # 查看日志"
echo "  fb h      # 帮助"
echo ""
echo "测试: fb p"
echo ""
