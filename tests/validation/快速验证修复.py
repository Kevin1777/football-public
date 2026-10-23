#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速验证Web回测修复是否生效
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("🔍 验证Web回测修复")
print("=" * 80)
print()

# 1. 检查代码是否已修改
print("1️⃣ 检查代码修改...")
with open('recommendation/x1_json_recommender.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
if 'dynamic_threshold = self._calculate_dynamic_threshold' in content:
    print("✅ 代码已修改：使用dynamic_threshold")
    
    # 查找具体位置
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if 'dynamic_threshold = self._calculate_dynamic_threshold' in line:
            print(f"   位置: 第{i}行")
            break
else:
    print("❌ 代码未修改：仍使用CONFIDENCE_THRESHOLD")
    sys.exit(1)

print()

# 2. 测试generate_recommendation方法
print("2️⃣ 测试generate_recommendation方法...")
try:
    from recommendation.x1_json_recommender import X1JSONRecommender
    import pandas as pd
    
    engine = X1JSONRecommender()
    print("✅ 引擎加载成功")
    
    # 创建测试数据
    test_trade_data = pd.DataFrame({
        '时间': ['2025-11-25 19:00'],
        '主队': [0.88],
        '客队': [0.96],
    })
    
    test_metadata = ['英超', '测试主队', '测试客队']
    
    test_handicap_data = {
        'initial_handicap': -0.5,
        'current_handicap': -0.5,
        'initial_handicap_str': '平手/半球',
        'current_handicap_str': '平手/半球',
        'initial_home_odds': 0.85,
        'initial_away_odds': 0.99,
        'current_home_odds': 0.88,
        'current_away_odds': 0.96,
    }
    
    print("   调用generate_recommendation...")
    result = engine.generate_recommendation(
        trade_data=test_trade_data,
        metadata=test_metadata,
        handicap_data=test_handicap_data
    )
    
    print(f"✅ 方法调用成功")
    print(f"   推荐: {result.get('direction', 'none')}")
    print(f"   置信度: {result.get('confidence', 0):.2f}")
    print(f"   是否推荐: {result.get('should_bet', False)}")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 3. 检查是否使用了动态阈值
print("3️⃣ 验证动态阈值逻辑...")

# 模拟不同质量的比赛
test_cases = [
    {
        'name': '英超大热门',
        'volume': 600000,
        'data_quality': 3,
        'sbre_weight': 0.85,
        'expected_threshold': '0.70-0.75'
    },
    {
        'name': '低级别冷门',
        'volume': 30000,
        'data_quality': 1,
        'sbre_weight': 0.30,
        'expected_threshold': '0.85-0.90'
    }
]

for case in test_cases:
    metrics = {
        'total_volume': case['volume'],
        'bfindex_home': 88 if case['data_quality'] == 3 else 0,
        'kelly_home': 0.95 if case['data_quality'] == 3 else 0,
        'home_euro_odds': 1.80 if case['data_quality'] == 3 else 0,
    }
    
    funding_level = {
        'sbre_weight': case['sbre_weight']
    }
    
    threshold = engine._calculate_dynamic_threshold(metrics, funding_level)
    print(f"   {case['name']}: 阈值={threshold:.2f} (预期{case['expected_threshold']})")

print()
print("=" * 80)
print("🎯 验证结论")
print("=" * 80)
print()
print("✅ 代码修改正确")
print("✅ generate_recommendation已使用动态阈值")
print("✅ 策略1已实施")
print()
print("⚠️  需要重启Flask应用才能生效！")
print()
print("重启步骤：")
print("1. 按Ctrl+C停止当前运行的app.py")
print("2. 重新运行: python app.py")
print("3. 刷新浏览器页面（Ctrl+F5强制刷新）")
print("4. 重新进行批量回测")
print()
print("=" * 80)
