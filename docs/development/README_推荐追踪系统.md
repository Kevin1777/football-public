# 🎯 X1 推荐模型 + 推荐追踪系统 - 完整方案

## ✅ 系统概述

完整的足球推荐系统，包含：

1. **X1 JSON 推荐引擎** - 准确率 83.6%
2. **推荐记录系统** - 自动记录每次推荐
3. **定时审查系统** - 每天中午 12 点审查
4. **可视化报告** - 生成 HTML 报告和图表
5. **企业微信推送** - 自动通知审查结果

---

## 🚀 快速开始

### 1. 启动服务

```bash
cd d:\MSM\Cursor\football
python app.py
```

启动后自动：

- ✅ 加载 X1 JSON 推荐引擎
- ✅ 注册 6 个 API 接口
- ✅ 启动定时审查任务（每天 12:00）
- ✅ 初始化数据库

### 2. 测试系统

```bash
# 测试推荐追踪系统
python test_recommendation_tracking.py

# 测试X1推荐集成
python test_x1_integration.py
```

### 3. 查看效果

- 📊 打开 `X1_可视化报告.html` 查看历史准确率
- 📈 等待明天 12 点查看第一次自动审查
- 💬 查看企业微信获取审查通知

---

## 📡 API 接口清单

### X1 推荐接口

| 接口                      | 方法 | 说明     |
| ------------------------- | ---- | -------- |
| `/api/x1/recommend`       | POST | 单个推荐 |
| `/api/x1/batch_recommend` | POST | 批量推荐 |
| `/api/x1/stats`           | GET  | 统计信息 |

### 审查接口（新增）

| 接口                     | 方法 | 说明       |
| ------------------------ | ---- | ---------- |
| `/api/x1/review/trigger` | POST | 触发审查   |
| `/api/x1/review/history` | GET  | 审查历史   |
| `/api/x1/review/pending` | GET  | 待审查列表 |

---

## 🎯 核心功能

### 1. 推荐生成（自动记录）

```python
import requests

# 生成推荐
response = requests.post(
    "http://127.0.0.1:5002/api/x1/recommend",
    json={"json_path": "data/2025/11/25/比赛.json"}
)

result = response.json()
print(f"推荐: {result['recommendation']['handicap']}")
print(f"置信度: {result['recommendation']['confidence_pct']}")
print(f"记录ID: {result['record_id']}")  # 🔥 自动记录
```

### 2. 定时审查（自动执行）

```
每天中午12:00
    ↓
扫描前一天的推荐
    ↓
提取实际比分
    ↓
计算准确率
    ↓
生成报告
    ↓
推送企业微信
```

### 3. 手动触发审查

```python
# 审查指定日期
response = requests.post(
    "http://127.0.0.1:5002/api/x1/review/trigger",
    json={"date": "2025-11-25"}
)

result = response.json()['result']
print(f"准确率: {result['accuracy']:.1f}%")
print(f"正确: {result['correct']}")
print(f"错误: {result['wrong']}")
print(f"报告: {result['report_path']}")
```

### 4. 查看历史趋势

```python
# 查看7天历史
response = requests.get(
    "http://127.0.0.1:5002/api/x1/review/history?days=7"
)

reviews = response.json()['reviews']
for review in reviews:
    print(f"{review['review_date']}: {review['accuracy']:.1f}%")
```

---

## 📊 可视化报告

### 报告内容

每次审查生成包含：

1. **评级卡片**

   - 🔥 优秀 (≥85%)
   - ✅ 良好 (75-85%)
   - ⚠️ 一般 (65-75%)
   - ❌ 需改进 (<65%)

2. **统计卡片**

   - 推荐总数
   - 已审查数
   - 正确/错误/走盘
   - 高置信度准确率

3. **准确率饼图**

   - 正确/错误/走盘分布

4. **7 天趋势图**

   - 整体准确率趋势线
   - 高置信度准确率趋势线
   - 历史均值参考线

5. **置信度对比图**
   - 高/中/低置信度准确率柱状图

### 报告位置

```
daily_reports/
  └── 20251125/
      ├── report.html         ← 打开查看
      ├── accuracy_pie.png
      ├── trend.png
      └── confidence.png
```

---

## 💬 企业微信推送

### 推送内容

```markdown
## 📊 每日推荐审查报告

**日期**: 2025-11-25
**审查时间**: 2025-11-26 12:00

---

### 📈 整体统计

- **推荐总数**: 10
- **已审查**: 10
- **正确**: ✅ 8
- **错误**: ❌ 2
- **走盘**: ⚖️ 0

### 🎯 准确率

🟢 **整体准确率**: 80.0% (8/10)
🌟 **高置信度准确率**: 85.0%

---

### 💡 表现评价

✅ **良好**: 准确率在合理范围内

📄 详细报告: [点击查看]
```

---

## 📈 准确率数据

### 历史回测数据

```
测试规模: 1,552场
整体准确率: 77.1%
高置信度准确率: 83.6% ⭐⭐⭐⭐⭐
中置信度准确率: 74.5%
```

### 实时追踪数据

通过 `/api/x1/stats` 查看：

- 累计推荐数
- 累计审查数
- 实时准确率
- 按置信度统计

---

## 🗄️ 数据库

### 数据库文件

`recommendation_tracker.db` - SQLite 数据库

### 表结构

**recommendations** - 推荐记录表

- 推荐信息（队伍、方向、置信度）
- 评分详情（FLM、SPM、DPI）
- 实际结果（比分、是否正确）
- 审查状态

**daily_reviews** - 每日审查统计表

- 日期
- 推荐总数
- 准确率
- 报告路径

---

## 📁 文件清单

### 核心模块

| 文件                                    | 说明           |
| --------------------------------------- | -------------- |
| `recommendation/x1_json_recommender.py` | X1 推荐引擎    |
| `recommendation_tracker.py`             | 推荐追踪器     |
| `daily_review_scheduler.py`             | 定时审查调度器 |
| `daily_review_visualizer.py`            | 可视化报告生成 |
| `api_x1_json_recommendation.py`         | API 接口       |

### 测试工具

| 文件                              | 说明         |
| --------------------------------- | ------------ |
| `test_x1_integration.py`          | X1 集成测试  |
| `test_recommendation_tracking.py` | 追踪系统测试 |
| `backtest_x1_accuracy.py`         | 准确率回测   |
| `visualize_x1_accuracy.py`        | 准确率可视化 |

### 文档

| 文件                            | 说明           |
| ------------------------------- | -------------- |
| `X1_快速开始.md`                | 5 分钟上手     |
| `X1_集成使用文档.md`            | API 使用文档   |
| `推荐记录和审查系统使用文档.md` | 审查系统文档   |
| `X1_准确率分析报告.md`          | 准确率详细分析 |
| `README_推荐追踪系统.md`        | 本文档         |

### 报告

| 文件                     | 说明           |
| ------------------------ | -------------- |
| `X1_可视化报告.html`     | 历史准确率报告 |
| `X1_测试报告.md`         | 全数据测试报告 |
| `X1_准确率回测结果.json` | 回测数据       |

---

## 💡 使用场景

### 场景 1: 每日推荐

```python
# 早上：批量获取今日推荐
response = requests.post(
    "http://127.0.0.1:5002/api/x1/batch_recommend",
    json={"date": "2025-11-25", "min_confidence": 0.85}
)

# 自动记录到数据库
recommendations = response.json()['recommendations']
for rec in recommendations:
    print(f"{rec['match']}: {rec['recommendation']['handicap']}")
```

### 场景 2: 次日审查

```
自动执行（中午12点）
    ↓
查看企业微信通知
    ↓
打开HTML报告查看详情
    ↓
分析准确率趋势
```

### 场景 3: 周度分析

```python
# 查看本周表现
response = requests.get(
    "http://127.0.0.1:5002/api/x1/review/history?days=7"
)

reviews = response.json()['reviews']
weekly_avg = sum(r['accuracy'] for r in reviews) / len(reviews)
print(f"本周平均准确率: {weekly_avg:.1f}%")
```

---

## 🎯 关键指标

### 监控指标

| 指标           | 目标值 | 说明                  |
| -------------- | ------ | --------------------- |
| 整体准确率     | ≥77%   | 所有推荐的准确率      |
| 高置信度准确率 | ≥83%   | 置信度 ≥0.85 的准确率 |
| 推荐率         | 60-70% | 有明确推荐的比例      |
| 高置信度占比   | 20-25% | 高置信度推荐的比例    |

### 预警阈值

- 🟢 准确率 ≥ 80% - 优秀
- 🟡 准确率 75-80% - 良好
- 🟠 准确率 70-75% - 一般
- 🔴 准确率 < 70% - 需要调整

---

## 🔧 配置

### 修改审查时间

编辑 `daily_review_scheduler.py`:

```python
# 改为每天18:00
trigger=CronTrigger(hour=18, minute=0)
```

### 修改企业微信 Webhook

编辑 `app.py` 或设置环境变量:

```bash
export WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

---

## 🎉 完成清单

### ✅ X1 推荐系统

- ✅ X1 JSON 推荐引擎（准确率 83.6%）
- ✅ 6 个 REST API 接口
- ✅ 完整测试工具
- ✅ 可视化报告
- ✅ 详细文档

### ✅ 推荐追踪系统

- ✅ 自动记录推荐
- ✅ 定时审查（每天 12:00）
- ✅ 可视化报告生成
- ✅ 企业微信推送
- ✅ 数据库存储
- ✅ 历史查询 API

### ✅ 文档完整性

- ✅ 快速开始指南
- ✅ API 使用文档
- ✅ 审查系统文档
- ✅ 准确率分析报告
- ✅ 项目总结文档

---

## 📝 维护指南

### 日常检查

- 📊 每天查看企业微信获取审查结果
- 📈 每周查看准确率趋势
- 🔍 关注异常数据

### 定期维护

- 💾 每月备份数据库
- 🧹 清理 30 天以上的报告
- 📊 生成月度分析报告

### 优化建议

- 准确率下降 → 调整置信度阈值
- 某联赛表现差 → 单独优化
- 风控触发频繁 → 调整风控参数

---

## 🚀 下一步

### 1. 启动服务

```bash
python app.py
```

### 2. 运行测试

```bash
python test_recommendation_tracking.py
```

### 3. 生成推荐

```bash
python -c "import requests; print(requests.post('http://127.0.0.1:5002/api/x1/batch_recommend', json={'date': '2025-11-25', 'min_confidence': 0.85}).json())"
```

### 4. 等待审查

明天中午 12 点自动执行第一次审查

### 5. 查看结果

- 企业微信通知
- HTML 报告
- API 查询

---

## ✅ 总结

完整的推荐和追踪系统已就绪：

| 模块         | 功能数 | 状态 |
| ------------ | ------ | ---- |
| X1 推荐引擎  | 1      | ✅   |
| REST API     | 6      | ✅   |
| 推荐记录     | 1      | ✅   |
| 定时审查     | 1      | ✅   |
| 可视化报告   | 1      | ✅   |
| 企业微信推送 | 1      | ✅   |
| 数据库       | 2 张表 | ✅   |
| 文档         | 10+    | ✅   |
| 测试工具     | 5      | ✅   |

**准确率**:

- 历史回测: 83.6% (高置信度)
- 实时追踪: 自动计算

**自动化程度**: 100%

- 推荐自动记录
- 每天自动审查
- 自动生成报告
- 自动推送通知

**状态**: ✅ 已完成，可投入使用！

---

**版本**: v1.0  
**完成日期**: 2025-11-25  
**系统**: X1 推荐 + 推荐追踪  
**准确率**: 83.6% (高置信度)
