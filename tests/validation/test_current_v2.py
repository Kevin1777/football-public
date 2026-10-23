#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试当前环境的V2模型
"""

import sys
import json
import pandas as pd
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 重新导入（清除缓存）
if 'recommendation.x1_json_recommender' in sys.modules:
    del sys.modules['recommendation.x1_json_recommender']

from recommendation.x1_json_recommender import X1JSONRecommender

print("=" * 80)
print("🔍 测试当前环境的V2模型")
print("=" * 80)

# 加载测试数据
test_file = PROJECT_ROOT / "data/2025/11/22/2025-11-22_中超_北京国安_vs_梅州客家_5_1_1530.json"

if not test_file.exists():
    print(f"\n❌ 测试文件不存在: {test_file}")
    sys.exit(1)

with open(test_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

recommender = X1JSONRecommender()

print("\n【测试1】recommend() 方法（新方法）:")
print("-" * 80)
result1 = recommender.recommend(str(test_file))
print(f"版本: {result1.get('version', 'N/A')}")
print(f"方向: {result1.get('recommendation', {}).get('direction', 'N/A')}")
print(f"置信度: {result1.get('recommendation', {}).get('confidence', 0):.2f}")

print("\n【测试2】generate_recommendation() 方法（批量回测用）:")
print("-" * 80)

# 模拟批量回测的数据格式
trade_data_list = data.get('trade_data', {}).get('data', [])
trade_df = pd.DataFrame(trade_data_list)
metadata = {
    'league': '中超',
    'home': '北京国安',
    'away': '梅州客家'
}
handicap_data = data.get('handicap_data', {})

result2 = recommender.generate_recommendation(trade_df, metadata, handicap_data)

print(f"版本: {result2.get('version', 'N/A')}")
print(f"引擎: {result2.get('engine', 'N/A')}")
print(f"方向: {result2.get('direction', 'N/A')}")
print(f"置信度: {result2.get('confidence', 0):.2f}")
print(f"理由: {result2.get('reason', 'N/A')}")

print("\n【判断】:")
print("-" * 80)

v1_count = 0
v2_count = 0

if 'V2' in result1.get('version', '') or 'v2' in result1.get('engine', ''):
    print("✅ recommend() 使用 V2")
    v2_count += 1
else:
    print("❌ recommend() 使用 V1")
    v1_count += 1

if 'V2' in result2.get('version', '') or 'v2' in result2.get('engine', ''):
    print("✅ generate_recommendation() 使用 V2")
    v2_count += 1
else:
    print("❌ generate_recommendation() 使用 V1")
    v1_count += 1

print("\n" + "=" * 80)
if v2_count == 2:
    print("🎉 结论：完全使用 V2 模型！")
elif v2_count == 1:
    print("⚠️  结论：部分使用 V2 模型")
else:
    print("❌ 结论：还在使用 V1 模型")
print("=" * 80)
