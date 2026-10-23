# X1 JSON 推荐模型 - 使用说明

## 📋 概述

基于 X1 全侦破版母本解构，设计的简化推荐模型。**仅使用 data 目录中的 JSON 文件作为数据源**，不依赖外部 API 或图像识别。

## 🎯 核心特性

### 1. 数据源

- ✅ **标盘指数\_latest.json**: 盘口数据（初始盘/即时盘/赔率变化）
- ✅ **比赛 JSON 文件**: 成交明细、必发指数、凯利指数、欧赔等
- ❌ **不需要**: UG 盘口图、Betfair 资金图、PDF 成交明细

### 2. X1 核心模块（简化版）

#### FLM (Frontline Logic Module) - 热度前线

- 分析三方成交占比（主/和/客）
- 识别资金倾向方向
- 判断热度类型：强热支持 / 热度支持 / 热度均衡 / 虚热

#### SPM (Structure Pressure Module) - 结构承压

- 盘口变化分析（升盘/降盘/平盘）
- 赔率水位变化分析
- 结构类型判断：顺势结构 / 诱导结构 / 中性结构

#### DPI (Directional Pressure Integration) - 风险整合

- 综合 FLM 和 SPM 结果
- 方向一致性判断
- 风险等级评定：低风险 / 中风险 / 高风险

### 3. 风控机制

| 机制          | 触发条件            | 作用               |
| ------------- | ------------------- | ------------------ |
| **SmartSafe** | 高成交量 + 结构矛盾 | 结构支撑缺失警报   |
| **SS-Dagger** | 盘口与赔率相反      | 诱导识别           |
| **LVC**       | 凯利指数>120        | 落点验证，虚脱预警 |
| **TPI**       | 深盘配低水          | 穿盘陷阱预警       |

### 4. SBRE 反解机制

- **触发条件**: L1/L2 资金等级 + 诱导结构
- **作用**: 反向推荐（诱导盘通常反向）
- **权重**: L1(1.0) > L2(0.85) > L3(0.65) > L4(0.35) > L5(0.15)

## 📊 资金等级标准（X1 原版）

```python
L1: 0 - 50,000
L2: 50,000 - 150,000
L3: 150,000 - 700,000
L4: 700,000 - 1,500,000
L5: > 1,500,000
```

## 🚀 使用方法

### 方法 1: Python 脚本调用

```python
from recommendation.x1_json_recommender import X1JSONRecommender

# 初始化推荐器
recommender = X1JSONRecommender()

# 生成推荐
result = recommender.recommend(
    "data/2025/11/25/2025-11-25_欧联U19_曼彻斯特城U19_vs_勒沃库森U19_2300.json"
)

# 查看结果
print(result['recommendation'])
# {
#   'direction': 'home',
#   'handicap': '主队 球半/两球 @0.8',
#   'confidence': 0.85,
#   'confidence_pct': '85.0%',
#   'reason': '强热支持, 顺势结构, 低风险'
# }
```

### 方法 2: 命令行测试

```bash
cd d:\MSM\Cursor\football
python recommendation/x1_json_recommender.py
```

### 方法 3: 批量处理

```python
from pathlib import Path
from recommendation.x1_json_recommender import X1JSONRecommender

recommender = X1JSONRecommender()
data_dir = Path("data/2025/11/25")

for json_file in data_dir.glob("2025-*.json"):
    result = recommender.recommend(str(json_file))

    if result['recommendation']['direction'] != 'none':
        print(f"✅ {json_file.stem}")
        print(f"   推荐: {result['recommendation']['handicap']}")
        print(f"   置信度: {result['recommendation']['confidence_pct']}")
        print(f"   理由: {result['recommendation']['reason']}")
        print()
```

## 📤 输出格式（VIS-E01 简化版）

```json
{
  "version": "X1-JSON-V1.0",
  "timestamp": "2025-11-25T21:30:00",
  "match_info": {
    "home": "曼彻斯特城U19",
    "away": "勒沃库森U19",
    "league": "欧联U19",
    "kickoff": "2025-11-25 23:00"
  },
  "data_source": {
    "ug_pdf": "✅ JSON数据",
    "handicap": "✅ 500彩票网",
    "vim": "✖ 未触发（模块下线）"
  },
  "funding_level": {
    "level": "L3",
    "total_volume": 312000,
    "sbre_weight": 0.65
  },
  "scores": {
    "FLM": {
      "direction": "home_strong",
      "confidence": 0.92,
      "level": "强热支持",
      "home_pct": 70.2,
      "away_pct": 18.3,
      "draw_pct": 11.5
    },
    "SPM": {
      "structure": "顺势结构",
      "confidence": 0.8,
      "handicap_signal": "home_favor",
      "odds_signal": "home_favor",
      "handicap_change": 0.25
    },
    "DPI": {
      "risk_level": "低风险",
      "confidence": 0.88,
      "recommendation": "home",
      "pressure_index": 88
    }
  },
  "risk_control": {
    "SmartSafe": false,
    "SS-Dagger": false,
    "LVC": false,
    "TPI": false,
    "messages": []
  },
  "sbre": {
    "triggered": false,
    "direction": null,
    "confidence": 0.0,
    "reason": ""
  },
  "recommendation": {
    "direction": "home",
    "handicap": "主队 球半/两球 @0.8",
    "confidence": 0.88,
    "confidence_pct": "88.0%",
    "reason": "强热支持, 顺势结构, 低风险"
  },
  "risk_notes": ["无显著风险"]
}
```

## 🔍 熔断类型

| 类型       | 说明     | 触发条件                  |
| ---------- | -------- | ------------------------- |
| **F-GATE** | 数据门控 | JSON 文件缺失或加载失败   |
| **F-EVD**  | 数据校验 | 必要字段不完整            |
| **F-CONS** | 风控熔断 | 多个风控机制触发 + 高风险 |
| **F-CAP**  | 执行异常 | 程序运行错误              |

## 📈 推荐逻辑流程

```
1. 加载JSON数据
   ↓
2. 数据完整性检查 (F-GATE/F-EVD)
   ↓
3. 提取核心指标
   - 成交量、占比、盘口、赔率、必发指数、凯利指数等
   ↓
4. 资金等级判定 (L1~L5)
   ↓
5. FLM评分 - 热度前线
   - 判断资金倾向方向
   ↓
6. SPM评分 - 结构承压
   - 判断盘口赔率一致性
   ↓
7. DPI评分 - 风险整合
   - 综合FLM和SPM，给出风险等级
   ↓
8. 风控检测
   - SmartSafe / SS-Dagger / LVC / TPI
   ↓
9. SBRE反解（如触发）
   - L1/L2 + 诱导结构 → 反向推荐
   ↓
10. 生成最终推荐
    - VIS格式输出
```

## 🎓 与 X1 母本的对应关系

| X1 母本                    | 简化版          | 说明                        |
| -------------------------- | --------------- | --------------------------- |
| UG 盘口图 + Betfair 资金图 | JSON 成交明细   | 从 JSON 提取三方占比替代    |
| 成交明细 PDF               | trade_data 字段 | 直接使用 JSON 中的交易数据  |
| WebFlow 实时采集           | 静态 JSON 文件  | 离线分析，不需要实时抓取    |
| GPT-4o 图像识别            | ❌ 不需要       | 全部数据已结构化            |
| VIM 成交轨迹               | ✖ 模块下线      | X1 母本已明确下线           |
| FLM/SPM/DPI                | ✅ 保持一致     | 核心评分逻辑完全保留        |
| SBRE 反解                  | ✅ 保持一致     | 资金等级权重表一致          |
| 四风控机制                 | ✅ 保持一致     | SmartSafe/SS-Dagger/LVC/TPI |
| VIS-E01 输出               | ✅ 简化版       | 保留核心字段                |

## ⚠️ 重要说明

### 1. 数据要求

- JSON 文件必须包含 `match_info`, `handicap_data`, `trade_data` 三个主要字段
- `trade_data.data` 数组至少有一条记录
- 盘口数据必须包含 `current_handicap` 和 `initial_handicap`

### 2. 推荐置信度解读

- **>= 0.85**: 高置信度，可考虑跟投
- **0.60 ~ 0.85**: 中置信度，谨慎参考
- **< 0.60**: 低置信度，不建议跟投
- **0.0 (none)**: 熔断，禁止下注

### 3. 风控优先级

- SBRE 反解 > DPI 评分 > SPM 承压 > FLM 热度
- 任意熔断触发 → 立即停止推荐

## 🔧 扩展建议

### 1. 集成到现有系统

```python
# 在 app.py 中集成
from recommendation.x1_json_recommender import X1JSONRecommender

x1_recommender = X1JSONRecommender()

@app.route('/api/recommend_x1', methods=['POST'])
def recommend_x1():
    json_path = request.json.get('json_path')
    result = x1_recommender.recommend(json_path)
    return jsonify(result)
```

### 2. 批量回测

```python
# 对历史数据进行批量测试
import glob

for json_file in glob.glob("data/2025/11/**/*.json", recursive=True):
    result = x1_recommender.recommend(json_file)
    # 记录推荐结果，后续对比实际比分
```

### 3. 实时监控

```python
# 监控新增JSON文件，自动生成推荐
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class JSONHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.json'):
            result = x1_recommender.recommend(event.src_path)
            # 推送通知或存储结果
```

## 📞 问题反馈

如遇到以下情况：

1. ❌ JSON 文件格式不匹配
2. ❌ 推荐结果异常
3. ❌ 熔断频繁触发
4. ❌ 置信度计算不合理

请检查：

- JSON 文件是否完整（是否包含所有必要字段）
- 数据是否合理（成交量、盘口、赔率等是否异常）
- 日志输出（`logging.basicConfig(level=logging.DEBUG)`）

---

**版本**: X1-JSON-V1.0  
**更新日期**: 2025-11-25  
**基于**: X1 全侦破版母本（GROK4 本地部署版）
