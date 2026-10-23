#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试批量回测日志是否正常记录
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("🔍 测试批量回测日志记录")
print("=" * 80)
print()

# 导入必要模块
from recommendation.x1_json_recommender import X1JSONRecommender
import pandas as pd
import logging

# 配置日志查看
logging.basicConfig(level=logging.INFO)

print("1️⃣ 测试generate_recommendation方法并查看日志...")
print()

# 创建引擎
engine = X1JSONRecommender()

# 创建测试数据
test_trade_data = pd.DataFrame({
    '时间': ['2025-11-25 19:00', '2025-11-25 19:10'],
    '主队': [0.88, 0.87],
    '客队': [0.96, 0.97],
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

print("调用generate_recommendation...")
print()

result = engine.generate_recommendation(
    trade_data=test_trade_data,
    metadata=test_metadata,
    handicap_data=test_handicap_data
)

print(f"推荐结果: {result.get('direction', 'none')}")
print(f"置信度: {result.get('confidence', 0):.2f}")
print(f"是否推荐: {result.get('should_bet', False)}")
print()

print("=" * 80)
print("2️⃣ 检查日志文件")
print("=" * 80)
print()

import time
time.sleep(1)  # 等待日志写入

# 检查日志文件
log_files = {
    'app_full.log': Path('logs/app_full.log'),
    'backtest_detail.log': Path('logs/backtest_detail.log'),
}

for name, path in log_files.items():
    if path.exists():
        print(f"✅ {name} 存在")
        print(f"   大小: {path.stat().st_size} bytes")
        
        # 读取最后20行
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            last_lines = lines[-20:] if len(lines) > 20 else lines
            
        # 查找关键日志
        found_dynamic = False
        found_decision = False
        
        for line in last_lines:
            if 'dynamic_threshold' in line:
                found_dynamic = True
                print(f"   ✅ 找到dynamic_threshold:")
                print(f"      {line.strip()}")
            if '推荐决策' in line or '📊' in line:
                found_decision = True
                if not found_dynamic:  # 避免重复打印
                    print(f"   📊 推荐决策日志:")
                    print(f"      {line.strip()}")
        
        if not found_dynamic and not found_decision:
            print(f"   ⚠️  未找到推荐决策日志")
            print(f"   最后5行:")
            for line in last_lines[-5:]:
                print(f"      {line.strip()}")
    else:
        print(f"❌ {name} 不存在")
    print()

print("=" * 80)
print("🎯 测试结论")
print("=" * 80)
print()

if found_dynamic or found_decision:
    print("✅ 日志系统正常工作")
    print("✅ 推荐决策日志已记录")
    print()
    print("下一步：在Web界面进行批量回测，日志将自动记录到这些文件中")
else:
    print("⚠️  日志可能未完全记录")
    print("建议：检查日志级别和logger配置")

print()
print("=" * 80)
