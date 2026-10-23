# 📁 根目录文件说明

## ✅ 根目录应该只包含

### 核心文件（3 个）

```
app.py              # Flask主应用
version_config.py   # 版本配置管理
README.md          # 项目说明文档
```

### 配置文件（2 个）

```
.env               # 环境变量（私密，不提交）
.gitignore         # Git忽略配置
```

### 核心目录

```
core/              # 核心功能模块
tests/             # 测试文件
tools/             # 工具脚本
docs/              # 文档
config/            # 配置文件
scripts/           # Shell/Bat脚本
data/              # 数据文件
logs/              # 日志文件
recommendation/    # 推荐引擎
backtest/          # 回测模块
utils/             # 工具模块
notification/      # 通知模块
parser/            # 解析模块
services/          # 服务模块
static/            # 静态文件
templates/         # 模板文件
archived/          # 归档文件
```

---

## 🗑️ 已清理的内容

### 移动到 `archived/old_backups/`

- analysis_backup/
- config_backup/
- docs_backup/
- logs_backup/
- scripts_backup/
- tests_backup/

### 移动到 `archived/temp_files/`

- auto_recommend_push.log
- captcha.png
- cookies.json
- cleanup_report.json
- reorganize_log.json
- X1\_可视化报告.html

### 移动到 `data/databases/`

- match_data.db
- recommendation_tracker.db

### 移动到 `docs/project/`

- PROJECT_REORGANIZATION_PLAN.md
- README_REORGANIZATION.md
- REORGANIZATION_SUMMARY.md
- REORGANIZATION_UPDATE.md

### 移动到其他位置

- reorganize_project.py → tools/maintenance/
- deep_cleanup.py → tools/maintenance/
- PDF/ → docs/pdf/

### 已删除空目录

- downloads/
- temp_files/
- visualization_output/
- analysis_charts/
- **pycache**/

---

## 📝 目录结构

```
football/
├── app.py                  ✅ 主应用
├── version_config.py       ✅ 版本配置
├── README.md              ✅ 项目文档
├── .env                   ✅ 环境变量
├── .gitignore             ✅ Git配置
│
├── core/                   📦 核心模块
├── tests/                  🧪 测试文件
├── tools/                  🛠️ 工具脚本
├── docs/                   📚 文档
├── config/                 ⚙️ 配置
├── scripts/                📜 脚本
├── data/                   📊 数据
├── logs/                   📝 日志
│
├── recommendation/         🎯 推荐引擎
├── backtest/              🔙 回测模块
├── utils/                 🔧 工具
├── notification/          📡 通知
├── parser/                🔍 解析
├── services/              💾 服务
├── static/                🎨 静态文件
├── templates/             📄 模板
│
└── archived/              📦 归档
    ├── old_backups/       # 旧备份
    ├── temp_files/        # 临时文件
    └── ...
```

---

## 🎯 保持整洁的原则

### 1. 根目录最小化

只保留：

- 必要的入口文件（app.py）
- 配置文件（.env, .gitignore）
- 主文档（README.md）
- 核心配置（version_config.py）

### 2. 分类存放

- 工具脚本 → `tools/`
- 测试文件 → `tests/`
- 文档文件 → `docs/`
- 临时文件 → `archived/temp_files/`
- 备份文件 → `archived/old_backups/`

### 3. 定期清理

```bash
# 每周运行
python tools/maintenance/cleanup_old_files.py --mode=clean --execute

# 深度清理（需要时）
python tools/maintenance/deep_cleanup.py
```

---

**创建时间**: 2025-11-26  
**维护**: 使用 `deep_cleanup.py` 保持根目录整洁
