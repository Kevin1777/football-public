#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试V2模型
"""

import json
from pathlib import Path
from recommendation.x1_json_recommender import X1JSONRecommender

test_file = Path("data/2025/11/22/2025-11-22_中超_北京国安_vs_梅州客家_5_1_1530.json")

with open(test_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

recommender = X1JSONRecommender()

# 提取metrics
metrics = recommender._extract_metrics(data)

print("=" * 80)
print("🔍 调试V2模型")
print("=" * 80)

print(f"\nmetrics提取结果:")
print(f"  total_volume: {metrics.get('total_volume', 0):,}")
print(f"  home_pct: {metrics.get('home_pct', 0):.1f}%")
print(f"  away_pct: {metrics.get('away_pct', 0):.1f}%")
print(f"  pct_diff: {metrics.get('home_pct', 0) - metrics.get('away_pct', 0):.1f}%")
print(f"  bfindex_home: {metrics.get('bfindex_home', 0):.1f}")
print(f"  bfindex_away: {metrics.get('bfindex_away', 0):.1f}")
print(f"  bfindex_diff: {metrics.get('bfindex_home', 0) - metrics.get('bfindex_away', 0):.1f}")

# 调用V2方法
v2_result = recommender._recommend_v2_simple(metrics)

print(f"\nV2推荐结果:")
print(f"  direction: {v2_result.get('direction', 'N/A')}")
print(f"  confidence: {v2_result.get('confidence', 0):.2f}")
print(f"  reason: {v2_result.get('reason', 'N/A')}")

# 检查条件
pct_diff = metrics.get('home_pct', 0) - metrics.get('away_pct', 0)
bfindex_diff = metrics.get('bfindex_home', 0) - metrics.get('bfindex_away', 0)
total_volume = metrics.get('total_volume', 0)

print(f"\n条件检查:")
print(f"  total_volume >= 50000: {total_volume >= 50000} ({total_volume:,})")
print(f"  pct_diff >= 30: {pct_diff >= 30} ({pct_diff:.1f})")
print(f"  bfindex_diff >= 0: {bfindex_diff >= 0} ({bfindex_diff:.1f})")

if total_volume >= 50000 and pct_diff >= 30 and bfindex_diff >= 0:
    print("\n✅ 应该推荐主胜！")
elif total_volume >= 50000 and pct_diff <= -30 and bfindex_diff <= 0:
    print("\n✅ 应该推荐客胜！")
else:
    print("\n❌ 不满足推荐条件")

print("\n" + "=" * 80)
