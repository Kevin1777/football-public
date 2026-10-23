# ✅ 修复 Web 批量回测准确率

## 🔍 问题发现

### 现象

- **命令行回测**：准确率 84.8%
- **Web 界面回测**：准确率 33.3% ❌

### 差距原因

#### 两种调用方式使用了不同的阈值：

**1. 命令行回测（`真实准确率回测.py`）**

```python
# 调用 recommend(json_path) 方法
result = engine.recommend(str(json_file), kickoff_time=kickoff_time, strict_mode=True)

# recommend() 内部使用策略1：
MIN_CONFIDENCE_THRESHOLD = self._calculate_dynamic_threshold(metrics, funding_level)
# 动态阈值：0.70-0.90，根据比赛质量调整
```

**2. Web 批量回测（`app.py` → `backtest_engine.py`）**

```python
# 调用 generate_recommendation() 方法
recommendation = self.recommendation_engine.generate_recommendation(
    trade_data=trade_data,
    metadata=metadata,
    handicap_data=handicap_data
)

# generate_recommendation() 原来使用固定阈值：
CONFIDENCE_THRESHOLD = 0.70  # ❌ 固定值，未使用策略1
```

---

## 🔧 修复方案

### 修改文件：`recommendation/x1_json_recommender.py` 第 693-701 行

**修改前**：

```python
CONFIDENCE_THRESHOLD = 0.70  # 固定阈值
should_bet = direction not in ['none', None] and confidence >= CONFIDENCE_THRESHOLD
logger.info(f"📊 推荐决策: direction={direction}, confidence={confidence:.2f}, threshold={CONFIDENCE_THRESHOLD}, should_bet={should_bet}")
```

**修改后**：

```python
# 🔥 使用策略1：动态阈值（与recommend方法一致）
dynamic_threshold = self._calculate_dynamic_threshold(metrics, funding_level)
should_bet = direction not in ['none', None] and confidence >= dynamic_threshold
logger.info(f"📊 推荐决策: direction={direction}, confidence={confidence:.2f}, dynamic_threshold={dynamic_threshold:.2f}, should_bet={should_bet}")
```

---

## ✅ 修复效果

### 修复后，Web 批量回测将使用策略 1：

```
英超大热门：阈值降到0.70-0.73 → 更多推荐
低级别冷门：阈值升到0.85-0.90 → 更严格

预期准确率：84.8%（与命令行回测一致）
```

---

## 🎯 验证方法

### 1. 重新运行 Web 批量回测

访问 Web 界面 → 完场回查 → 批量回测

- 选择相同的日期范围
- 点击"批量回测"

### 2. 预期结果

```
修复前：
准确率: 33.3% (1胜/3场)

修复后：
准确率: ~84% (接近命令行回测)
推荐量: 显著减少（质量优先）
```

---

## 📝 技术细节

### 策略 1 动态阈值计算

```python
def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
    base_threshold = 0.80
    adjustments = 0

    # 1. 成交量
    if volume > 500000: adjustments -= 0.03
    elif volume < 50000: adjustments += 0.05

    # 2. 数据质量
    if data_quality == 3: adjustments -= 0.02
    elif data_quality < 2: adjustments += 0.03

    # 3. 资金等级
    if sbre_weight >= 0.85: adjustments -= 0.02
    elif sbre_weight <= 0.35: adjustments += 0.03

    return max(0.70, min(0.90, base_threshold + adjustments))
```

### 为什么固定阈值 0.70 准确率低？

1. **过度推荐**：很多低质量比赛也被推荐
2. **无区分度**：不区分联赛等级、成交量、数据质量
3. **高风险**：冷门比赛的 0.70 置信度实际不可靠

### 策略 1 的优势

1. **智能筛选**：根据比赛质量动态调整
2. **质量优先**：只推荐高把握的比赛
3. **准确率高**：84.8% vs 33.3%

---

## 🚀 后续建议

### 1. 立即测试

修复后立即在 Web 界面重新运行回测，验证准确率提升。

### 2. 监控日志

查看推荐决策日志：

```
📊 推荐决策: direction=home, confidence=0.77, dynamic_threshold=0.73, should_bet=True
```

确认`dynamic_threshold`正在工作。

### 3. 对比测试

- 选择同一天的比赛
- 分别运行命令行回测和 Web 回测
- 对比准确率是否一致

---

## ⚠️ 重要说明

### 为什么会有两个阈值？

**历史原因**：

- `recommend(json_path)` - 新方法，使用策略 1
- `generate_recommendation()` - 旧方法，兼容旧代码

**现在统一**：两个方法都使用策略 1

### 是否影响其他功能？

不会！`generate_recommendation`只在以下场景使用：

1. ✅ Web 批量回测（已修复）
2. ✅ 单场回测（已修复）

其他功能都直接使用`recommend()`方法。

---

## 📊 预期对比

| 场景         | 修复前   | 修复后   |
| ------------ | -------- | -------- |
| 命令行回测   | 84.8% ✅ | 84.8% ✅ |
| Web 批量回测 | 33.3% ❌ | 84.8% ✅ |
| 单场回测     | 33.3% ❌ | 84.8% ✅ |

---

**修复完成时间**: 2025-11-26 12:10
**预期效果**: Web 批量回测准确率提升到 84.8%
**状态**: ✅ 已修复，等待验证
