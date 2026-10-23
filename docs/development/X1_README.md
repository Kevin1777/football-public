# X1 JSON 推荐模型

> 基于 X1 全侦破版母本解构，仅使用 JSON 数据的足球让球盘口推荐系统

[![版本](https://img.shields.io/badge/版本-v1.0-blue.svg)](.)
[![状态](https://img.shields.io/badge/状态-可用-green.svg)](.)
[![Python](https://img.shields.io/badge/Python-3.8+-yellow.svg)](.)

---

## 🚀 5 秒钟了解

```python
from recommendation.x1_json_recommender import X1JSONRecommender

recommender = X1JSONRecommender()
result = recommender.recommend("data/2025/11/25/比赛.json")

print(result['recommendation'])
# {
#   'direction': 'home',
#   'handicap': '主队 球半/两球 @0.8',
#   'confidence': 0.87,
#   'confidence_pct': '87.0%',
#   'reason': '强热支持, 顺势结构, 低风险'
# }
```

---

## 📋 核心特性

| 特性                | 说明                           |
| ------------------- | ------------------------------ |
| ✅ **无图像依赖**   | 不需要 UG 盘口图、资金图、PDF  |
| ✅ **纯 JSON 输入** | 仅使用 data 目录中的 JSON 文件 |
| ✅ **离线推荐**     | 毫秒级响应，可批量处理         |
| ✅ **完整 X1 逻辑** | FLM/SPM/DPI/SBRE/风控 100%保留 |
| ✅ **易于测试**     | 确定性输出，可重复验证         |

---

## 📖 文档导航

| 文档                                        | 用途                    | 适合人群 |
| ------------------------------------------- | ----------------------- | -------- |
| 🚀 [快速开始](./X1_快速开始.md)             | 5 分钟上手 + 常见问题   | 新用户   |
| 📚 [使用说明](./X1_JSON推荐模型使用说明.md) | 详细技术文档 + API 参考 | 开发者   |
| 📊 [项目总结](./X1_项目总结.md)             | 架构设计 + 实现细节     | 技术人员 |

---

## 🎯 X1 核心模块

```
┌─────────────────────────────────────────┐
│          X1 推荐引擎架构                 │
├─────────────────────────────────────────┤
│                                         │
│  📊 评分模块                             │
│  ├── FLM (热度前线)                      │
│  ├── SPM (结构承压)                      │
│  └── DPI (风险整合)                      │
│                                         │
│  ⚠️ 风控机制                             │
│  ├── SmartSafe (结构支撑检测)            │
│  ├── SS-Dagger (诱导识别)               │
│  ├── LVC (落点验证)                      │
│  └── TPI (穿盘预警)                      │
│                                         │
│  🔄 SBRE反解                             │
│  └── L1/L2诱导盘反向推荐                 │
│                                         │
│  🔥 熔断系统                             │
│  └── F-GATE/F-EVD/F-CONS/F-CAP          │
│                                         │
└─────────────────────────────────────────┘
```

---

## 💻 快速开始

### 1. 测试单个比赛

```bash
python test_x1_json_recommender.py "data/2025/11/25/比赛.json"
```

### 2. 测试最新 10 场比赛

```bash
python test_x1_json_recommender.py
```

### 3. Python 脚本调用

```python
from recommendation.x1_json_recommender import X1JSONRecommender

recommender = X1JSONRecommender()

# 单个比赛推荐
result = recommender.recommend("data/2025/11/25/比赛.json")

# 提取关键信息
if result['recommendation']['direction'] != 'none':
    print(f"✅ {result['recommendation']['handicap']}")
    print(f"📊 {result['recommendation']['confidence_pct']}")
else:
    print(f"❌ 熔断: {result['meltdown']['reason']}")
```

### 4. 批量处理

```python
from pathlib import Path

data_dir = Path("data/2025/11/25")
for json_file in data_dir.glob("2025-*.json"):
    result = recommender.recommend(str(json_file))
    # 处理结果...
```

---

## 📊 输出格式

```json
{
  "version": "X1-JSON-V1.0",
  "match_info": {
    "home": "曼彻斯特城U19",
    "away": "勒沃库森U19",
    "league": "欧联U19"
  },
  "funding_level": {
    "level": "L3",
    "total_volume": 3321
  },
  "scores": {
    "FLM": { "level": "强热支持", "confidence": 0.91 },
    "SPM": { "structure": "顺势结构", "confidence": 0.8 },
    "DPI": { "risk_level": "低风险", "confidence": 0.88 }
  },
  "recommendation": {
    "direction": "home",
    "handicap": "主队 球半/两球 @0.8",
    "confidence": 0.88,
    "confidence_pct": "88.0%",
    "reason": "强热支持, 顺势结构, 低风险"
  }
}
```

---

## 🎓 与 X1 母本对应

| X1 母本          | JSON 版本 | 状态       |
| ---------------- | --------- | ---------- |
| FLM/SPM/DPI 评分 | ✅        | 完全实现   |
| SBRE 反解机制    | ✅        | 权重表 1:1 |
| 四风控机制       | ✅        | 完全实现   |
| 资金等级 L1~L5   | ✅        | 阈值一致   |
| VIS-E01 输出     | ✅        | 简化版     |
| UG 盘口图        | ❌        | JSON 替代  |
| Betfair 资金图   | ❌        | JSON 替代  |
| GPT-4o 识别      | ❌        | 不需要     |
| VIM 轨迹         | ✖         | 已下线     |

---

## 📈 推荐置信度解读

| 置信度      | 等级    | 建议       |
| ----------- | ------- | ---------- |
| ≥ 0.85      | 🟢 高   | 可考虑跟投 |
| 0.60 ~ 0.85 | 🟡 中   | 谨慎参考   |
| < 0.60      | 🔴 低   | 不建议跟投 |
| 0.0 (none)  | ⚫ 熔断 | 禁止下注   |

---

## 🔧 项目结构

```
football/
├── recommendation/
│   └── x1_json_recommender.py      # 核心引擎 (600行)
├── test_x1_json_recommender.py     # 测试工具 (350行)
├── X1_README.md                    # 本文档
├── X1_快速开始.md                   # 快速上手
├── X1_JSON推荐模型使用说明.md      # 详细文档
└── X1_项目总结.md                  # 技术总结
```

---

## ⚡ 性能特点

- 🚀 **响应速度**: < 10ms per match
- 📦 **内存占用**: < 50MB
- 🔄 **批处理**: 支持并发
- 💾 **离线运行**: 无需网络

---

## 📞 快速帮助

### Q: 如何开始？

**A**: 阅读 [快速开始文档](./X1_快速开始.md)

### Q: 推荐准确率？

**A**: 取决于数据质量，高置信度推荐(≥0.85)通常有较高准确率

### Q: 如何调参？

**A**: 修改 `x1_json_recommender.py` 中的阈值参数

### Q: 如何集成？

**A**: 参考 [使用说明文档](./X1_JSON推荐模型使用说明.md) 的集成部分

---

## 📝 版本信息

- **版本**: X1-JSON-V1.0
- **发布日期**: 2025-11-25
- **基于**: X1 本地部署版 · UG-only 修复母本（GROK4 适配版）
- **Python 要求**: 3.8+
- **依赖**: json, logging, pathlib (标准库)

---

## 📄 许可

本项目基于 X1 母本核心逻辑解构实现。

---

## 🔗 相关链接

- 📖 [完整文档](./X1_JSON推荐模型使用说明.md)
- 🚀 [快速开始](./X1_快速开始.md)
- 📊 [项目总结](./X1_项目总结.md)
- 💻 [源代码](./recommendation/x1_json_recommender.py)

---

**立即开始**: `python test_x1_json_recommender.py`
