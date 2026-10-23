# 📝 项目重组更新说明

## 调整说明

根据实际使用需求，对重组方案进行了调整：

### ✅ 保留在根目录的核心文件

以下文件**保留在根目录**，不移入 `core/`：

```
football/
├── app.py                  # ✅ 主应用（保留根目录）
├── version_config.py       # ✅ 版本配置（保留根目录）
├── README.md              # ✅ 主文档
├── .env                   # ✅ 环境变量
├── .gitignore             # ✅ Git配置
└── ...
```

### 📦 core/ 目录调整

`core/` 目录现在只包含：

```
core/
├── main_automation.py      # 自动化主程序
├── auto_recommend_push.py  # 推荐推送
├── recommendation_tracker.py  # 推荐追踪
├── schedule_manager.py     # 调度管理
└── daily_review_scheduler.py  # 每日审查
```

### 🎯 调整原因

1. **app.py 是项目入口** - 保留在根目录更直观
2. **version_config.py 被多处引用** - 根目录便于导入
3. **符合惯例** - 主应用通常在根目录

### 🚀 使用方式

**启动应用（更简单）：**

```bash
# 直接运行
python app.py

# 或使用脚本
scripts/automation/启动服务器.bat
```

**导入版本配置（更简洁）：**

```python
# 之前（已修正）
from core.version_config import MODEL_FULL_NAME

# 现在
from version_config import MODEL_FULL_NAME
```

---

## 📂 最终目录结构

```
football/
├── app.py                  # 主应用（根目录）
├── version_config.py       # 版本配置（根目录）
├── README.md              # 主文档
│
├── core/                   # 核心功能模块（5个文件）
├── tests/                  # 测试文件（26个文件）
├── tools/                  # 工具脚本（33个文件）
├── docs/                   # 文档（68个文件）
├── config/                 # 配置文件（5个文件）
├── scripts/                # 脚本文件（9个文件）
├── data/                   # 数据文件
│
├── recommendation/         # 推荐引擎
├── backtest/              # 回测模块
├── utils/                 # 工具模块
├── notification/          # 通知模块
├── parser/                # 解析模块
├── services/              # 服务模块
├── static/                # 静态文件
├── templates/             # 模板文件
└── logs/                  # 日志目录
```

---

## ✅ 验证测试

```bash
# 1. 测试应用启动
python app.py

# 2. 测试版本配置
python version_config.py

# 3. 测试V2模型
python tests/validation/test_current_v2.py
```

---

**更新时间**: 2025-11-26  
**状态**: ✅ 已调整完成
