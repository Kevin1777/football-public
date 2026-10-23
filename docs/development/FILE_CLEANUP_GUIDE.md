# 📁 老旧文件管理指南

## 📋 概述

随着项目发展，会积累各种老旧文件、备份文件和临时文件，定期清理可以：

- 🗑️ 释放磁盘空间
- 🚀 提升性能
- 🎯 保持项目整洁
- 📊 便于维护

---

## 🔍 识别老旧文件

### 自动识别的文件类型

#### 1. 老旧文件（90 天未修改）

```
logs/                   # 旧日志文件
debug_html/            # 调试HTML
backtest_results/      # 历史回测结果
detail_cache/          # 过期缓存
data/cache/            # 数据缓存
data/results/          # 测试结果
```

#### 2. 备份目录（可删除）

```
analysis_backup/       # 分析备份
config_backup/         # 配置备份
docs_backup/           # 文档备份
logs_backup/           # 日志备份
scripts_backup/        # 脚本备份
tests_backup/          # 测试备份
```

#### 3. 临时文件（可清理）

```
*.pyc                  # Python编译文件
__pycache__/           # Python缓存
*.bak                  # 备份文件
*.tmp, *.temp          # 临时文件
.DS_Store              # macOS文件
Thumbs.db              # Windows缩略图
```

#### 4. 大文件（>10MB）

```
*.log                  # 大日志文件
*.json                 # 大JSON文件
*.db                   # 数据库文件
*.html                 # 调试HTML
```

---

## 🛠️ 使用清理工具

### 安装位置

```
tools/maintenance/cleanup_old_files.py
```

### 基本用法

#### 1. 扫描老旧文件

```bash
# 扫描所有类型的老旧文件
python tools/maintenance/cleanup_old_files.py --mode=scan

# 自定义老化阈值（60天）
python tools/maintenance/cleanup_old_files.py --mode=scan --days=60
```

**输出示例：**

```
🔍 扫描老旧文件...
📁 检查: logs
  发现 45 个老旧文件，总大小 123.45 MB

📊 扫描报告
老旧文件: 45 个
备份目录: 6 个
大文件: 12 个
可清理: 23 个
可释放空间: 456.78 MB
```

#### 2. 归档老旧文件

```bash
# 预览归档操作
python tools/maintenance/cleanup_old_files.py --mode=archive

# 执行归档（文件会移动到 archived/auto_cleanup/）
python tools/maintenance/cleanup_old_files.py --mode=archive --execute
```

#### 3. 清理临时文件

```bash
# 预览清理
python tools/maintenance/cleanup_old_files.py --mode=clean

# 执行清理
python tools/maintenance/cleanup_old_files.py --mode=clean --execute
```

#### 4. 完整清理

```bash
# 扫描所有，预览操作
python tools/maintenance/cleanup_old_files.py --mode=full

# 执行完整清理（需要确认）
python tools/maintenance/cleanup_old_files.py --mode=full --execute
```

---

## 📊 清理策略

### 推荐清理周期

| 文件类型      | 清理周期 | 保留时间   |
| ------------- | -------- | ---------- |
| **日志文件**  | 每周     | 30 天      |
| **调试 HTML** | 每月     | 90 天      |
| **回测结果**  | 每月     | 90 天      |
| **临时文件**  | 每天     | 立即       |
| **备份目录**  | 每季度   | 归档后删除 |
| **缓存文件**  | 每周     | 30 天      |

### 自动化清理

#### 方法 1：Windows 计划任务

```batch
# 创建计划任务脚本: auto_cleanup.bat
@echo off
cd /d D:\MSM\Cursor\football
python tools/maintenance/cleanup_old_files.py --mode=clean --execute
python tools/maintenance/cleanup_old_files.py --mode=archive --execute --days=90
```

在任务计划程序中设置每周运行。

#### 方法 2：Python 定时任务

在 `core/app.py` 中添加定时任务：

```python
from apscheduler.schedulers.background import BackgroundScheduler

# 每周日凌晨3点清理
scheduler.add_job(
    func=lambda: os.system('python tools/maintenance/cleanup_old_files.py --mode=clean --execute'),
    trigger='cron',
    day_of_week='sun',
    hour=3
)
```

---

## 🎯 清理规则详解

### 1. 日志文件清理

**规则：**

- 保留最近 30 天的日志
- 归档 30-90 天的日志
- 删除 90 天以上的日志

**手动清理：**

```bash
# 删除旧日志（保留30天）
find logs/ -name "*.log" -mtime +30 -delete

# Windows
forfiles /P logs /S /M *.log /D -30 /C "cmd /c del @path"
```

### 2. 备份目录处理

**规则：**

- `*_backup/` 目录通常是一次性备份
- 确认内容已归档到 `archived/` 后可删除
- 建议先移动到 `archived/` 观察一周

**处理流程：**

```bash
# 1. 检查备份内容
ls -la analysis_backup/

# 2. 移动到归档（如需要）
mv analysis_backup/ archived/old_backups/

# 3. 一周后确认无误，删除
rm -rf archived/old_backups/analysis_backup/
```

### 3. 缓存文件清理

**规则：**

- `__pycache__/` 可安全删除（Python 会自动重建）
- `*.pyc` 可安全删除
- `detail_cache/` 建议保留最近访问的

**清理命令：**

```bash
# Python缓存
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete

# Windows
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
```

### 4. 大文件处理

**规则：**

- > 10MB 的文件需要人工审核
- 日志文件可以压缩后归档
- JSON 结果文件选择性保留

**压缩归档：**

```bash
# 压缩大日志
gzip logs/*.log

# 创建归档
tar -czf archived/logs_$(date +%Y%m).tar.gz logs/
```

---

## 📝 清理报告

### 报告文件

清理工具会生成 `cleanup_report.json`：

```json
{
  "scan_time": "2025-11-26T15:00:00",
  "results": {
    "old_files": [
      {
        "path": "logs/app_2025-08-01.log",
        "size": 1234567,
        "mtime": "2025-08-01T10:00:00",
        "days_old": 117
      }
    ],
    "duplicate_dirs": [...],
    "large_files": [...],
    "cleanup_candidates": [...]
  },
  "total_size_mb": 456.78
}
```

### 查看报告

```bash
# 查看JSON报告
cat cleanup_report.json | jq

# 查看大文件
cat cleanup_report.json | jq '.results.large_files[]'
```

---

## ⚠️ 注意事项

### 安全检查清单

清理前必须检查：

- [ ] 确认文件不再需要
- [ ] 重要文件已备份
- [ ] Git 已提交最新代码
- [ ] 数据库文件谨慎处理
- [ ] 先预览再执行
- [ ] 归档后观察一段时间

### 不要删除

**永远不要删除：**

```
.git/                  # Git仓库
.env                   # 环境变量
*.db                   # 活动数据库（谨慎）
config/                # 配置文件
recommendation/        # 核心模块
```

**谨慎处理：**

```
data/2025/             # 当年数据
logs/football_current.log  # 当前日志
match_data.db          # 主数据库
```

---

## 🔄 恢复文件

### 从归档恢复

```bash
# 归档位置
archived/auto_cleanup/old_files_20251126/

# 恢复文件
cp archived/auto_cleanup/old_files_20251126/logs/old.log logs/
```

### 从 Git 恢复

```bash
# 查看被删除的文件
git log --diff-filter=D --summary

# 恢复文件
git checkout <commit-hash> -- path/to/file
```

---

## 📊 磁盘空间管理

### 检查磁盘使用

```bash
# Linux/Mac
du -sh */ | sort -hr

# Windows
dir /s
```

### 大目录排查

```bash
# 找出最大的10个目录
du -sh */ | sort -hr | head -10

# Windows
diruse /m /s /d:1
```

---

## 🎯 最佳实践

### 1. 定期清理

- ✅ 每周清理临时文件
- ✅ 每月归档旧日志
- ✅ 每季度审查备份目录

### 2. 自动化

- ✅ 使用计划任务自动清理
- ✅ 配置日志轮转
- ✅ 设置磁盘空间告警

### 3. 文档记录

- ✅ 记录清理操作
- ✅ 保存清理报告
- ✅ 标记归档原因

### 4. 版本控制

- ✅ 重要文件提交 Git
- ✅ 使用 `.gitignore` 排除临时文件
- ✅ 定期清理 Git 历史

---

## 📞 故障排查

### 问题：误删文件

**解决：**

1. 检查 `archived/auto_cleanup/` 目录
2. 使用 Git 恢复
3. 从备份恢复

### 问题：清理后程序报错

**解决：**

1. 检查是否删除了必要文件
2. 恢复被删文件
3. 重新生成缓存（`__pycache__`等）

### 问题：空间未释放

**解决：**

1. 确认文件已真正删除
2. 清空回收站
3. 检查是否有进程占用文件

---

**维护者**: 项目团队  
**最后更新**: 2025-11-26  
**工具版本**: 1.0
