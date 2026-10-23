# Linux 服务器部署指南

## 路径配置说明

本系统已经过路径适配，支持在 Windows 和 Linux 上无缝运行。

### 目录结构

```
/root/football/                 # 项目根目录
├── app.py                      # 主应用
├── data/                       # 数据目录（自动创建）
│   ├── 2025/
│   │   ├── 11/
│   │   │   ├── 23/
│   │   │   │   ├── 盘口数据.json
│   │   │   │   ├── 盘口数据.html
│   │   │   │   ├── 标盘指数_*.json
│   │   │   │   └── *.csv (交易明细)
│   ├── handicaps/              # 盘口数据备份
│   ├── details/                # 详细数据
│   └── cache/                  # 缓存数据
├── logs/                       # 日志目录（自动创建）
└── progress/                   # 进度管理（自动创建）
```

### 自动路径处理

系统会自动检测运行环境：

- **Windows**: `d:\MSM\Cursor\football\data`
- **Linux**: `/root/football/data`

所有路径都使用 `pathlib.Path` 处理，自动适配操作系统。

### 验证路径配置

启动应用时会显示路径信息：

```
================================================================================
📂 工作目录配置
================================================================================
  项目根目录: /root/football
  数据目录: /root/football/data
  日志目录: /root/football/logs
  缓存管理器目录: /root/football/data
  500彩票数据目录: /root/football/data
================================================================================
```

## 部署步骤

### 1. 上传代码到服务器

```bash
# 使用 git 克隆或 scp 上传
cd /root
git clone <repository_url> football
# 或
scp -r ./football root@server:/root/
```

### 2. 安装依赖

```bash
cd /root/football
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）

```bash
# 创建 .env 文件
cp .env.example .env
nano .env
```

### 4. 启动应用

```bash
# 开发模式
python app.py

# 生产模式（推荐使用 supervisor 或 systemd）
nohup python app.py > app.log 2>&1 &
```

### 5. 使用 systemd 管理服务（推荐）

创建服务文件 `/etc/systemd/system/football.service`：

```ini
[Unit]
Description=Football Data Collection Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/football
ExecStart=/usr/bin/python3 /root/football/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable football
sudo systemctl start football
sudo systemctl status football
```

## 数据目录权限

确保应用有权限读写数据目录：

```bash
# 检查权限
ls -la /root/football/data

# 如果需要，修改权限
chmod -R 755 /root/football/data
chown -R root:root /root/football/data
```

## 常见问题

### Q1: 无法读取 data 目录

**解决方案**：

1. 检查路径是否存在：`ls -la /root/football/data`
2. 检查权限：`chmod -R 755 /root/football/data`
3. 查看启动日志中的路径配置信息

### Q2: Windows 和 Linux 路径不一致

**解决方案**：
本系统已经自动处理跨平台路径，无需手动配置。系统使用 `pathlib.Path` 自动适配操作系统。

### Q3: 数据文件找不到

**解决方案**：

1. 确认数据已正确采集到 `/root/football/data/YYYY/MM/DD/` 目录
2. 检查文件名格式是否正确
3. 查看应用日志：`tail -f /root/football/logs/*.log`

## 监控和维护

### 查看日志

```bash
# 实时查看应用日志
tail -f /root/football/logs/session_*.log

# 查看系统服务日志
journalctl -u football -f
```

### 数据备份

```bash
# 备份数据目录
tar -czf football_data_$(date +%Y%m%d).tar.gz /root/football/data

# 定期备份（添加到 crontab）
0 3 * * * tar -czf /root/backups/football_data_$(date +\%Y\%m\%d).tar.gz /root/football/data
```

### 清理旧数据

```bash
# 清理 30 天前的数据
find /root/football/data -name "*.csv" -mtime +30 -delete
find /root/football/logs -name "*.log" -mtime +30 -delete
```

## 性能优化

### 1. 使用 Redis 缓存（可选）

如果并发量大，可以使用 Redis 代替文件缓存。

### 2. 数据库优化

考虑使用 PostgreSQL 或 MySQL 存储历史数据，而不是 CSV 文件。

### 3. 定期清理

设置定时任务清理过期数据和日志。

## 安全建议

1. **限制访问**: 配置防火墙只允许特定 IP 访问
2. **使用 HTTPS**: 配置 nginx 反向代理，启用 SSL
3. **定期备份**: 每天自动备份数据目录
4. **监控日志**: 使用 logrotate 管理日志文件大小

## 联系支持

如有问题，请查看：

- 应用日志：`/root/football/logs/`
- 系统日志：`journalctl -u football`
- GitHub Issues: <repository_url>/issues
