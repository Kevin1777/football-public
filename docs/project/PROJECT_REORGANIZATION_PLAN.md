# 🗂️ 项目文件重组方案

## 📋 当前问题

- ✅ 根目录有 **100+ 个文件**（Python、Markdown、配置等混杂）
- ✅ 测试文件、工具脚本、文档散落各处
- ✅ 难以快速找到所需文件
- ✅ 不利于项目维护和协作

---

## 🎯 重组目标

### 新目录结构

```
football/
├── 📦 core/                    # 核心应用代码
│   ├── app.py                  # 主应用
│   ├── version_config.py       # 版本配置
│   └── config.py              # 配置管理
│
├── 🧪 tests/                   # 测试文件（统一）
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   ├── accuracy/               # 准确率测试
│   └── validation/             # 验证测试
│
├── 🛠️ tools/                   # 工具脚本
│   ├── analysis/               # 分析工具
│   ├── optimization/           # 优化工具
│   ├── quick_scripts/          # 快速脚本
│   └── debugging/              # 调试工具
│
├── 📚 docs/                    # 文档（重组）
│   ├── user_guides/            # 用户指南
│   ├── development/            # 开发文档
│   ├── deployment/             # 部署文档
│   ├── changelogs/             # 变更日志
│   └── reports/                # 测试报告
│
├── ⚙️ config/                  # 配置文件
│   ├── .env.example            # 环境变量示例
│   ├── requirements.txt        # 依赖
│   └── settings/               # 各种配置
│
├── 📜 scripts/                 # Shell/Bat脚本
│   ├── deployment/             # 部署脚本
│   ├── automation/             # 自动化脚本
│   └── utilities/              # 实用工具
│
├── 📊 data/                    # 数据目录（保持）
├── 📝 logs/                    # 日志目录（保持）
├── 🎨 static/                  # 静态文件（保持）
├── 📄 templates/               # 模板文件（保持）
├── 🔧 utils/                   # 工具模块（保持）
├── 🎯 recommendation/          # 推荐引擎（保持）
├── 🔙 backtest/                # 回测模块（保持）
├── 📡 notification/            # 通知模块（保持）
├── 🔍 parser/                  # 解析模块（保持）
├── 💾 services/                # 服务模块（保持）
│
├── 📦 archived/                # 归档（已存在）
│   ├── old_scripts/            # 旧脚本
│   ├── old_docs/               # 旧文档
│   └── deprecated/             # 废弃代码
│
└── README.md                   # 主文档
```

---

## 📂 详细文件分类

### 1. 核心应用 (core/)

```
core/
├── app.py                      # ✅ 主Flask应用
├── version_config.py           # ✅ 版本配置
├── main_automation.py          # ✅ 自动化主程序
├── auto_recommend_push.py      # ✅ 推荐推送
├── recommendation_tracker.py   # ✅ 推荐追踪
├── schedule_manager.py         # ✅ 调度管理
└── daily_review_scheduler.py   # ✅ 每日审查
```

### 2. 测试文件 (tests/)

```
tests/
├── unit/                       # 单元测试
│   ├── test_recommender.py
│   └── test_parser.py
│
├── integration/                # 集成测试
│   ├── test_x1_integration.py
│   ├── test_api_v2.py
│   └── integration_example.py
│
├── accuracy/                   # 准确率测试
│   ├── test_accuracy.py
│   ├── quick_accuracy_test.py
│   ├── final_accuracy_test.py
│   ├── backtest_x1_accuracy.py
│   └── 真实准确率回测.py
│
└── validation/                 # 验证测试
    ├── validate_model.py
    ├── verify_v2.py
    ├── test_current_v2.py
    └── 严格验证无未来函数.py
```

### 3. 工具脚本 (tools/)

```
tools/
├── analysis/                   # 分析工具
│   ├── analyze_failures.py
│   ├── analyze_winners.py
│   ├── 分析回测结果.py
│   ├── 分析最近回测.py
│   ├── 成交额深度分析.py
│   ├── 实时交易明细分析.py
│   └── 高级特征挖掘.py
│
├── optimization/               # 优化工具
│   ├── optimize_model.py
│   ├── build_new_model.py
│   ├── 优化推荐引擎.py
│   ├── V5深度优化分析.py
│   ├── 实施分级阈值.py
│   └── test_optimization.py
│
├── quick_scripts/              # 快速脚本
│   ├── quick_collect_today.py
│   ├── quick_batch_test.py
│   ├── 快速测试真实准确率.py
│   └── 快速验证修复.py
│
├── debugging/                  # 调试工具
│   ├── debug_v2.py
│   ├── debug_missing_handicap.py
│   ├── 调试公司ID.py
│   └── 诊断批量回测问题.py
│
├── visualization/              # 可视化工具
│   ├── visualize_x1_accuracy.py
│   ├── generate_x1_report.py
│   └── daily_review_visualizer.py
│
└── data_collection/            # 数据采集
    ├── auto_capture_links.py
    └── 测试采集盘口.py
```

### 4. 文档 (docs/)

```
docs/
├── README.md                   # 主文档（保留在根目录）
│
├── user_guides/                # 用户指南
│   ├── QUICK_START.md
│   ├── X1_快速开始.md
│   ├── 快速开始_优化版.md
│   ├── X1_JSON推荐模型使用说明.md
│   ├── X1_集成使用文档.md
│   └── 推荐记录和审查系统使用文档.md
│
├── development/                # 开发文档
│   ├── VERSION_UPDATE_GUIDE.md
│   ├── VERSION_QUICK_GUIDE.md
│   ├── README_系统优化总结.md
│   ├── README_日志系统.md
│   ├── README_推荐追踪系统.md
│   └── 操作日志使用说明.md
│
├── deployment/                 # 部署文档
│   ├── DEPLOYMENT.md
│   ├── ✅服务器部署总结.md
│   ├── 服务器部署检查报告.md
│   └── 无人值守功能检查报告.md
│
├── changelogs/                 # 变更日志
│   ├── V2_MODEL_INTEGRATION.md
│   ├── X1_集成完成总结.md
│   ├── ✅全系统统一引擎完成.md
│   ├── ✅统一推荐引擎替换完成.md
│   └── 推荐引擎替换完成.md
│
├── reports/                    # 测试报告
│   ├── X1_准确率分析报告.md
│   ├── X1_测试报告.md
│   ├── X1_测试结果总结.md
│   ├── FINAL_V2_VERIFICATION.md
│   ├── 回测真实性验证报告.md
│   ├── ✅真实准确率测试结论.md
│   └── 全盘检查报告.md
│
└── archived_docs/              # 归档文档
    ├── ✅修复Web回测准确率.md
    ├── ✅完整修复总结.md
    └── ...（其他已完成的任务文档）
```

### 5. 配置文件 (config/)

```
config/
├── .env.example                # 环境变量示例
├── requirements.txt            # Python依赖
├── requirements_full.txt       # 完整依赖
├── wecom_config.json           # 企微配置
├── config.json                 # 应用配置
└── settings/                   # 其他配置
    └── ...
```

### 6. Shell/Bat 脚本 (scripts/)

```
scripts/
├── deployment/                 # 部署脚本
│   ├── deploy_server.sh
│   ├── 服务器快速部署.sh
│   └── football.service
│
├── automation/                 # 自动化脚本
│   ├── 启动服务器.bat
│   ├── 启动自动推送.bat
│   └── quick_start.bat
│
└── utilities/                  # 实用脚本
    ├── quick_test.bat
    ├── 立即测试准确率.sh
    └── 快速修复脚本.bat
```

### 7. 数据文件 (data/)

```
data/
├── models/                     # 模型数据
│   ├── V5增强特征.csv
│   └── ...
│
├── results/                    # 测试结果
│   ├── X1_准确率回测结果.json
│   ├── X1_测试详细结果.json
│   ├── x1_test_results.json
│   ├── 真实准确率回测结果.json
│   └── 全方案对比结果.json
│
└── cache/                      # 缓存数据
    ├── pre_match_history.json
    └── ...
```

---

## 🚀 执行计划

### 阶段 1：创建新目录结构（安全）

1. 创建所有新目录
2. 不删除任何文件
3. 验证目录结构

### 阶段 2：移动文件（可回滚）

1. 先复制文件到新位置
2. 验证功能正常
3. 删除旧文件

### 阶段 3：更新引用

1. 更新 import 路径
2. 更新配置文件
3. 更新文档链接

### 阶段 4：清理验证

1. 删除空目录
2. 更新.gitignore
3. 完整测试

---

## ⚠️ 注意事项

1. **备份优先**

   - 执行前完整备份项目
   - 使用 Git 提交当前状态

2. **分批执行**

   - 不要一次性移动所有文件
   - 每移动一批就测试一次

3. **保持运行**

   - 移动过程中不影响运行中的服务
   - 关键文件最后处理

4. **更新配置**
   - 更新所有硬编码路径
   - 更新环境变量
   - 更新文档链接

---

## 📝 重组检查清单

- [ ] 备份当前项目
- [ ] Git 提交当前状态
- [ ] 创建新目录结构
- [ ] 移动核心应用文件
- [ ] 移动测试文件
- [ ] 移动工具脚本
- [ ] 移动文档
- [ ] 移动配置文件
- [ ] 移动 Shell 脚本
- [ ] 更新 import 路径
- [ ] 更新配置路径
- [ ] 测试核心功能
- [ ] 测试推荐引擎
- [ ] 测试 API
- [ ] 更新 README
- [ ] 删除空目录
- [ ] 提交变更

---

## 🎯 预期效果

### 之前

```
❌ 100+ 文件在根目录
❌ 难以找到需要的文件
❌ 测试、工具、文档混杂
❌ 不利于团队协作
```

### 之后

```
✅ 清晰的目录结构
✅ 文件分类明确
✅ 易于查找和维护
✅ 专业的项目组织
```

---

**创建时间**: 2025-11-26  
**状态**: 待执行  
**预计时间**: 2-3 小时
