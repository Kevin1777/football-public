#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速验证V2模型是否生效
"""

from recommendation.x1_json_recommender import X1JSONRecommender
from pathlib import Path

print("=" * 80)
print("🔍 验证V2模型是否生效")
print("=" * 80)

# 初始化推荐引擎
recommender = X1JSONRecommender()

# 测试一场比赛
test_file = Path("data/2025/11/22/2025-11-22_中超_北京国安_vs_梅州客家_5_1_1530.json")

if test_file.exists():
    print(f"\n测试文件: {test_file.name}")
    
    # 调用推荐
    result = recommender.recommend(str(test_file))
    
    print(f"\n推荐结果:")
    print(f"  版本: {result.get('version', 'N/A')}")
    print(f"  方向: {result.get('recommendation', {}).get('direction', 'N/A')}")
    print(f"  置信度: {result.get('recommendation', {}).get('confidence', 0):.2f}")
    print(f"  理由: {result.get('recommendation', {}).get('reason', 'N/A')}")
    
    # 检查是否是V2
    if 'V2' in result.get('version', ''):
        print("\n✅ V2模型生效！")
    else:
        print("\n❌ 还在使用旧版本")
        
    # 检查FLM分数
    scores = result.get('scores', {})
    flm = scores.get('FLM', {})
    print(f"\nFLM数据:")
    print(f"  类型: {type(flm)}")
    print(f"  内容: {flm}")
    
    if 'home_pct' in flm:
        print(f"  主队成交占比: {flm.get('home_pct', 0):.1f}%")
        print(f"  客队成交占比: {flm.get('away_pct', 0):.1f}%")
        
else:
    print(f"\n❌ 测试文件不存在: {test_file}")

print("\n" + "=" * 80)
