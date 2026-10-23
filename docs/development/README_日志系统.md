# 操作日志系统 - 快速开始

## 🎯 功能概述

已为系统添加完整的操作日志管理功能：

✅ **自动记录**：所有模块的日志自动写入文件  
✅ **定期轮转**：每 48 小时自动轮转  
✅ **自动压缩**：归档日志自动压缩节省空间  
✅ **自动清理**：保留最近 7 天，超期自动删除  
✅ **API 查询**：提供完整的 API 接口查看和搜索

---

## 🚀 快速开始

### 1. 启动服务

```bash
cd d:\MSM\Cursor\football
python app.py
```

启动后会看到：

```
================================================================================
🚀 Football Analysis System - 启动中
================================================================================
📝 操作日志已启用
   日志目录: logs
   轮转周期: 48小时
   保留天数: 7天
================================================================================
```

### 2. 查看日志文件

日志文件自动创建在 `logs/` 目录：

```
logs/
├── football_current.log           # 当前日志（实时写入）
└── archive/                        # 归档目录
    ├── football_20251125_220000.log.gz
    └── ...
```

### 3. 使用 API 查看日志

#### 查看最近 500 行日志

```bash
curl http://localhost:5000/api/logs/view?lines=500
```

#### 获取日志统计

```bash
curl http://localhost:5000/api/logs/stats
```

#### 搜索日志内容

```bash
curl -X POST http://localhost:5000/api/logs/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "推送", "max_results": 100}'
```

### 4. 运行测试脚本

```bash
python test_logs.py
```

---

## 📋 API 接口列表

| 接口               | 方法 | 功能               |
| ------------------ | ---- | ------------------ |
| `/api/logs/view`   | GET  | 查看最近的日志内容 |
| `/api/logs/stats`  | GET  | 获取日志统计信息   |
| `/api/logs/search` | POST | 搜索日志内容       |
| `/api/logs/rotate` | POST | 手动触发日志轮转   |

---

## 🔍 常用操作

### 排查推送问题

1. **搜索推送相关日志**

```bash
curl -X POST http://localhost:5000/api/logs/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "赛前推送", "max_results": 50}'
```

2. **查看最近日志**

```bash
curl http://localhost:5000/api/logs/view?lines=1000
```

### 查看调度任务

```bash
curl http://localhost:5000/api/push/scheduled_tasks
```

### 监控日志大小

```bash
curl http://localhost:5000/api/logs/stats
```

如果当前日志过大（>100MB），可以手动轮转：

```bash
curl -X POST http://localhost:5000/api/logs/rotate
```

---

## 📚 详细文档

- **完整使用说明**：`操作日志使用说明.md`
- **调度系统说明**：`推送调度说明.md`

---

## 🎉 优势

### 问题排查更容易

**以前**：

- ❌ 日志只在控制台，关闭就丢失
- ❌ 无法查看历史日志
- ❌ 难以定位具体问题

**现在**：

- ✅ 日志自动保存到文件
- ✅ 保留 7 天历史，随时可查
- ✅ 支持关键字搜索，快速定位
- ✅ 压缩存储，节省空间

### 系统监控更方便

- 📊 日志统计一目了然
- 🔍 全文搜索快速查找
- 📅 历史追溯最多 7 天
- 🤖 自动管理无需干预

---

## ⚠️ 注意事项

1. **日志目录**：确保 `logs/` 目录有写入权限
2. **磁盘空间**：日志会占用磁盘空间，但会自动清理
3. **搜索性能**：归档很多时搜索会慢，建议限制结果数

---

## 🛠️ 配置修改

如需修改轮转周期或保留天数，编辑 `utils/operation_logger.py`：

```python
class OperationLogger:
    def __init__(self, log_dir: str = "logs", app_name: str = "football"):
        self.rotation_hours = 48  # 改为24则每天轮转
        self.keep_days = 7        # 改为14则保留14天
```

---

## 📞 问题反馈

如果遇到问题，可以：

1. 查看 `logs/football_current.log` 文件
2. 使用搜索 API 查找错误信息
3. 运行 `test_logs.py` 测试各项功能

祝使用愉快！🎉
