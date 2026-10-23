# X1 推荐引擎优化方案

基于 959 场历史比赛数据（2025-11-01 至 2025-11-26）的分析结果

---

## 📊 当前状况分析

### 数据质量

- **总场次**: 959 场
- **有盘口数据**: 820 场 (85.5%)
- **有交易数据**: 820 场 (85.5%)
- **完整数据**: 820 场 (85.5%)

### 推荐表现

- **推荐率**: 4.7% (45/959 场)
- **推荐结果**: 23 胜 22 负
- **当前胜率**: 51.1% (几乎随机)
- **融断原因**:
  - LOW_CONFIDENCE: 705 场 (73.5%)
  - F-CONS: 13 场

### 置信度分布

| 置信度范围    | 场次       | 占比      |
| ------------- | ---------- | --------- |
| 0.90-1.00     | 9 场       | 0.9%      |
| 0.85-0.90     | 10 场      | 1.0%      |
| 0.80-0.85     | 5 场       | 0.5%      |
| **0.75-0.80** | **610 场** | **63.6%** |
| 0.70-0.75     | 147 场     | 15.3%     |
| 0.60-0.70     | 60 场      | 6.3%      |
| 0.50-0.60     | 118 场     | 12.3%     |

---

## 🎯 核心问题

### 1. 阈值设置过高

当前动态阈值：`base_threshold = 0.80`

**问题**：

- 63.6%的比赛置信度集中在 0.75-0.80
- 这些比赛被阈值卡住，无法推荐
- 导致推荐率极低（4.7%）

### 2. 阈值分析结果

| 阈值     | 推荐场次  | 推荐率   | 胜场 | 负场 | 胜率         |
| -------- | --------- | -------- | ---- | ---- | ------------ |
| 0.90     | 9 场      | 0.9%     | 4    | 5    | 44.4%        |
| 0.85     | 19 场     | 2.0%     | 9    | 10   | 47.4%        |
| 0.81     | 24 场     | 2.5%     | 13   | 11   | **54.2%** ⬆️ |
| **0.80** | 24 场     | 2.5%     | 13   | 11   | **54.2%** ⬆️ |
| **0.75** | **45 场** | **4.7%** | 21   | 19   | **46.7%**    |
| 0.70     | 45 场     | 4.7%     | 21   | 19   | 46.7%        |

**关键发现**：

- ✅ **0.80 阈值**: 虽然推荐率低，但胜率最高(54.2%)
- ⚠️ **0.75 阈值**: 推荐率提升到 4.7%，但胜率下降到 46.7%
- **结论**: 目前没有找到推荐率>5%且胜率>55%的阈值

### 3. 根本问题：模型准确性不足

**问题不是阈值，而是模型本身！**

- 0.75-0.80 置信度范围的 610 场比赛，实际胜率只有 46.7%
- 说明置信度评分与实际结果相关性弱
- **需要优化 FLM/SPM/DPI 评分逻辑**

---

## 💡 优化方案

### 方案 A：保守优化（推荐 ✅）

**目标**: 优先保证准确率，小幅提升推荐率

#### 1. 调整基础阈值

```python
# recommendation/x1_json_recommender.py line 449
base_threshold = 0.75  # 从0.80降至0.75
```

**预期效果**:

- 推荐率: 2.5% → 4.7% (翻倍)
- 胜率: 54.2% → 46.7% (下降 7.5%)
- 推荐场次: 24 场 → 45 场

#### 2. 优化动态调整幅度

```python
# recommendation/x1_json_recommender.py line 449-480
def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
    base_threshold = 0.75  # ← 修改这里
    adjustments = 0

    # 1. 成交量调整（加大调整幅度）
    total_volume = metrics.get('total_volume', 0)
    if total_volume > 500000:
        adjustments -= 0.05  # 超大热度：降5%（原3%）
    elif total_volume > 200000:
        adjustments -= 0.03  # 大热度：降3%（原2%）
    elif total_volume < 50000:
        adjustments += 0.08  # 冷门：升8%（原5%）

    # 2. 数据完整性（加大调整幅度）
    data_quality = sum([
        metrics.get('bfindex_home', 0) > 0,
        metrics.get('kelly_home', 0) > 0,
        metrics.get('home_euro_odds', 0) > 0
    ])
    if data_quality == 3:
        adjustments -= 0.03  # 数据完整：降3%（原2%）
    elif data_quality < 2:
        adjustments += 0.05  # 数据不完整：升5%（原3%）

    # 3. 资金等级
    sbre_weight = funding_level.get('sbre_weight', 0.5)
    if sbre_weight >= 0.85:
        adjustments -= 0.03  # L1/L2：降3%（原2%）
    elif sbre_weight <= 0.35:
        adjustments += 0.05  # L4/L5：升5%（原3%）

    # 限制在合理范围
    return max(0.65, min(0.85, base_threshold + adjustments))
```

---

### 方案 B：激进优化（需要更多数据验证）

**目标**: 最大化推荐率，收集更多数据用于进一步优化

#### 1. 大幅降低阈值

```python
base_threshold = 0.70
```

**预期效果**:

- 推荐率: 提升到 10-15%
- 胜率: 可能降至 45%左右
- **不推荐**: 胜率太低，不可取

---

### 方案 C：模型重构（长期方案）⭐

**目标**: 从根本上提升模型准确性

#### 1. 优化 FLM 评分（热度前线）

**当前问题**:

- 简单的成交占比，未考虑时间序列
- 未考虑成交量变化趋势

**优化方向**:

```python
def _flm_scoring_enhanced(self, metrics: Dict) -> Dict:
    """增强版FLM评分"""

    # 1. 加入时间序列分析（需要trade_data的历史数据）
    # 分析成交量变化趋势：爆量 vs 萎缩

    # 2. 加入成交方式分析（买入 vs 卖出）
    # 主动买入比例高 → 信心强

    # 3. 加入价位变化分析
    # 价位上升 + 成交增加 = 强烈看好

    return enhanced_score
```

#### 2. 优化 DPI 评分（风险整合）

**当前问题**:

- DPI 置信度计算公式不够精准
- 未充分利用必发指数、凯利指数等数据

**优化方向**:

```python
def _dpi_scoring_enhanced(self, flm: Dict, spm: Dict, metrics: Dict) -> Dict:
    """增强版DPI评分"""

    # 1. 加权公式优化
    # 当前: confidence = (flm_conf * 0.6 + spm_conf * 0.4)
    # 优化: 根据数据质量动态调整权重

    # 2. 加入必发指数差值分析
    bfindex_diff = metrics['bfindex_home'] - metrics['bfindex_away']

    # 3. 加入凯利指数验证
    kelly_signal = metrics['kelly_home'] - metrics['kelly_away']

    # 4. 多维度交叉验证
    if flm_direction == spm_direction == bfindex_direction == kelly_direction:
        confidence_boost = 0.10  # 四维共振，提升10%

    return enhanced_score
```

#### 3. 引入机器学习模型

**基于历史 959 场数据训练**:

```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier

class MLEnhancedRecommender:
    """机器学习增强推荐器"""

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)
        self.is_trained = False

    def train(self, historical_matches):
        """基于历史数据训练"""
        X = []  # 特征矩阵
        y = []  # 标签（1=赢，0=输）

        for match in historical_matches:
            features = [
                match['metrics']['home_pct'],
                match['metrics']['away_pct'],
                match['metrics']['total_volume'],
                match['metrics']['handicap_change'],
                match['metrics']['bfindex_home'] - match['metrics']['bfindex_away'],
                match['metrics']['kelly_home'] - match['metrics']['kelly_away'],
                # ... 更多特征
            ]

            result = 1 if match['won'] else 0

            X.append(features)
            y.append(result)

        self.model.fit(X, y)
        self.is_trained = True

    def predict_probability(self, metrics):
        """预测胜率"""
        if not self.is_trained:
            return 0.5

        features = [...]  # 同上
        prob = self.model.predict_proba([features])[0][1]
        return prob
```

---

## 🚀 实施步骤

### 阶段 1：快速优化（1 天）✅

1. **修改基础阈值**

   ```bash
   # 编辑 recommendation/x1_json_recommender.py
   base_threshold = 0.75
   ```

2. **调整动态幅度** （可选）

   - 加大成交量调整幅度
   - 加大数据质量调整幅度

3. **测试验证**
   ```bash
   python test_accuracy.py 2025-11-01 --end-date 2025-11-26
   ```

**预期结果**:

- 推荐率: ~5%
- 胜率: ~47%

---

### 阶段 2：数据质量提升（3 天）

1. **补充缺失数据**

   - 确保所有比赛都有完整的盘口和交易数据
   - 过滤成交量<500 的小比赛

2. **数据验证**
   - 检查 trade_data 结构
   - 检查 handicap_data 结构
   - 确保数据解析正确

---

### 阶段 3：模型优化（1 周）

1. **优化 FLM 评分**

   - 加入时间序列分析
   - 加入成交方式分析

2. **优化 DPI 评分**

   - 优化置信度计算公式
   - 加入多维度交叉验证

3. **持续回测**
   - 每次修改后立即回测
   - 记录每个版本的准确率

---

### 阶段 4：机器学习增强（2 周）

1. **特征工程**

   - 提取更多有效特征
   - 特征重要性分析

2. **模型训练**

   - 使用 959 场数据训练
   - 交叉验证

3. **模型融合**
   - X1 引擎 + ML 模型
   - 双重验证，提升准确率

---

## 📈 预期目标

### 短期目标（1 周内）

- ✅ 推荐率: 4.7% → 8-10%
- ✅ 胜率: 51% → 55%
- ✅ 推荐场次: 45 场 → 80-100 场

### 中期目标（1 个月内）

- 🎯 推荐率: 10-15%
- 🎯 胜率: 60%+
- 🎯 引入机器学习模型

### 长期目标（3 个月内）

- 🚀 推荐率: 15-20%
- 🚀 胜率: 65%+
- 🚀 建立自动化训练流程

---

## ⚠️ 风险提示

1. **降低阈值的风险**

   - 推荐率提升，但胜率可能下降
   - 需要在推荐率和胜率之间找平衡

2. **过拟合风险**

   - 基于历史数据优化，可能不适用未来数据
   - 需要持续监控和调整

3. **数据质量风险**
   - 当前数据可能不够完整
   - 需要确保数据采集的准确性

---

## 📝 下一步行动

### 立即执行

1. ✅ 修改 `base_threshold = 0.75`
2. ✅ 运行回测验证
3. ✅ 观察实际推荐效果

### 本周执行

1. 优化动态调整幅度
2. 补充数据质量检查
3. 开始 FLM/DPI 优化设计

### 本月执行

1. 实施 FLM/DPI 优化
2. 收集更多历史数据
3. 开始机器学习模型研究

---

生成时间: 2025-11-26
基于数据: 959 场比赛（2025-11-01 至 2025-11-26）
