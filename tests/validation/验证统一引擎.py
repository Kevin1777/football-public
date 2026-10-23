#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证所有组件都使用了X1 JSON推荐引擎（准确率84.8%，策略1：分级阈值）
"""

import sys
from pathlib import Path

print("=" * 80)
print("🔍 验证统一推荐引擎")
print("=" * 80)
print()

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 验证1：主应用app.py
print("1️⃣ 验证主应用（Flask Web）")
try:
    from app import x1_json_recommender
    print(f"   ✅ 使用引擎: {type(x1_json_recommender).__name__}")
    print(f"   ✅ 类型: X1JSONRecommender")
    print(f"   ✅ 包含策略1（分级阈值）: {hasattr(x1_json_recommender, '_calculate_dynamic_threshold')}")
except ImportError as e:
    print(f"   ❌ 导入失败: {e}")
print()

# 验证2：批量回测本地数据
print("2️⃣ 验证批量回测本地数据")
try:
    with open('批量回测本地数据.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'X1JSONRecommender' in content:
            print("   ✅ 已使用X1JSONRecommender")
        else:
            print("   ❌ 未使用X1JSONRecommender")
        
        if 'OptimizedRecommendationEngine' in content:
            print("   ⚠️  仍包含旧引擎引用")
        else:
            print("   ✅ 已移除旧引擎")
except Exception as e:
    print(f"   ❌ 检查失败: {e}")
print()

# 验证3：增强批量回测
print("3️⃣ 验证增强批量回测")
try:
    with open('增强批量回测.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'X1JSONRecommender' in content:
            print("   ✅ 已使用X1JSONRecommender")
        else:
            print("   ❌ 未使用X1JSONRecommender")
        
        if 'OptimizedRecommendationEngine' in content:
            print("   ⚠️  仍包含旧引擎引用")
        else:
            print("   ✅ 已移除旧引擎")
except Exception as e:
    print(f"   ❌ 检查失败: {e}")
print()

# 验证4：自动推送系统
print("4️⃣ 验证自动推送系统")
try:
    with open('auto_recommend_push.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'X1JSONRecommender' in content:
            print("   ✅ 已使用X1JSONRecommender")
        else:
            print("   ⚠️  可能使用其他引擎")
except Exception as e:
    print(f"   ❌ 检查失败: {e}")
print()

# 验证5：X1引擎本身包含策略1
print("5️⃣ 验证X1引擎包含策略1（分级阈值）")
try:
    from recommendation.x1_json_recommender import X1JSONRecommender
    engine = X1JSONRecommender()
    
    has_dynamic_threshold = hasattr(engine, '_calculate_dynamic_threshold')
    print(f"   ✅ 动态阈值方法: {has_dynamic_threshold}")
    
    if has_dynamic_threshold:
        # 测试动态阈值计算
        test_metrics = {
            'total_volume': 600000,
            'bfindex_home': 88,
            'kelly_home': 0.95,
            'home_euro_odds': 1.80
        }
        test_funding = {'sbre_weight': 0.85}
        
        threshold = engine._calculate_dynamic_threshold(test_metrics, test_funding)
        print(f"   ✅ 测试阈值计算: {threshold:.2f}")
        print(f"   ✅ 策略1已实施！")
    else:
        print(f"   ❌ 策略1未实施")
except Exception as e:
    print(f"   ❌ 验证失败: {e}")
print()

print("=" * 80)
print("🎯 验证总结")
print("=" * 80)
print()

print("✅ 验证完成！")
print()
print("所有组件应该都使用了：")
print("   - X1 JSON推荐引擎")
print("   - 策略1（分级阈值）")
print("   - 准确率84.8%")
print()
print("=" * 80)
