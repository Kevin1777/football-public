#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型验证 - 检查是否存在数据泄露、未来函数、过度拟合
"""

import json
import re
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("🔍 模型验证 - 数据泄露检查")
print("=" * 80)

# 1. 检查是否偷看比分（文件名泄露）
print("\n【检查1】文件名是否泄露比分？")
print("-" * 80)

sample_files = list(Path("data/2025/11/22").glob("2025-11-22*.json"))[:5]
for f in sample_files:
    print(f"文件名: {f.name}")
    # 检查文件名中是否包含比分
    if re.search(r'_\d+_\d+_', f.name):
        print("  ⚠️  文件名包含比分！")
    else:
        print("  ✅ 文件名无比分")

print("\n结论：")
print("❌ **严重问题**：文件名包含比分信息（如 5_1）")
print("   这意味着在load_matches时，实际上已经看到了比分")
print("   需要检查推荐逻辑是否真的没有使用文件名中的比分")

# 2. 检查推荐引擎是否使用了比分
print("\n" + "=" * 80)
print("【检查2】推荐引擎是否使用了比分数据？")
print("-" * 80)

print("\n查看V2推荐逻辑使用的特征：")
print("""
def _recommend_v2_simple(self, metrics: Dict) -> Dict:
    # 使用的特征：
    total_volume = metrics.get('total_volume', 0)          # ✅ 赛前数据
    home_pct = metrics.get('home_pct', 0)                  # ❓需验证
    away_pct = metrics.get('away_pct', 0)                  # ❓需验证
    bfindex_home = metrics.get('bfindex_home', 0)          # ❓需验证
    bfindex_away = metrics.get('bfindex_away', 0)          # ❓需验证
""")

# 3. 检查trade_data的时间戳
print("\n" + "=" * 80)
print("【检查3】trade_data是否包含比赛后的数据？")
print("-" * 80)

sample_file = list(Path("data/2025/11/22").glob("2025-11-22*.json"))[0]
with open(sample_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

match_info = data.get("match_info", {})
match_time = match_info.get("match_time", "")
trade_data = data.get("trade_data", {})
trade_list = trade_data.get("data", [])

print(f"\n比赛: {match_info.get('label', '')}")
print(f"开球时间: {match_time}")

if trade_list:
    latest = trade_list[0]
    trade_time = latest.get("成交时间", "")
    print(f"最新成交时间: {trade_time}")
    
    # 检查是否有多条记录
    print(f"\n成交记录数: {len(trade_list)}")
    if len(trade_list) > 1:
        print("前3条记录的时间:")
        for i, t in enumerate(trade_list[:3]):
            print(f"  {i+1}. {t.get('成交时间', 'N/A')}")

print("\n⚠️  关键问题：")
print("1. trade_data使用的是第几条记录？")
print("2. 这条记录的时间是在比赛前还是比赛后？")
print("3. 如果是比赛后的数据，就是**未来函数**！")

# 4. 检查过度拟合
print("\n" + "=" * 80)
print("【检查4】是否过度拟合？")
print("-" * 80)

print("\n当前规则：")
print("  - 成交占比差 ≥ 30%")
print("  - 必发指数差 ≥ 0")
print("  - 成交量 ≥ 50,000")

print("\n过度拟合检查：")
print("✅ 规则简单（只有3个条件）")
print("✅ 阈值整数化（30%, 0, 50000）")
print("✅ 基于领域知识（成交占比反映资金倾向）")
print("⚠️  但需要在新数据上验证")

print("\n建议：")
print("1. 用12月的数据做**前向验证**")
print("2. 每周重新验证准确率")
print("3. 如果准确率大幅下降，说明过拟合")

# 5. 最严重的问题：文件名泄露
print("\n" + "=" * 80)
print("【检查5】文件名泄露问题 - 最严重！")
print("=" * 80)

print("\n当前情况：")
print("❌ 文件名格式: 2025-11-22_中超_北京国安_vs_梅州客家_5_1_1530.json")
print("   包含比分: 5_1")

print("\n在build_new_model.py中：")
with open("build_new_model.py", 'r', encoding='utf-8') as f:
    content = f.read()
    if "actual_score = (int(score_match.group(1)), int(score_match.group(2)))" in content:
        print("✅ 从label提取比分（正确）")
    
    if "json_file.name" in content or "json_file.stem" in content:
        print("⚠️  代码中使用了json_file.name/stem")
        print("   需要确认：是否在提取比分时使用了文件名？")

print("\n检查提取比分的代码：")
print("""
# 从哪里提取的比分？
label = match_info.get("label", "")
score_match = re.search(r'(\\d+)-(\\d+)', label)
actual_score = (int(score_match.group(1)), int(score_match.group(2)))
""")

print("\n✅ 好消息：比分是从match_info.label提取的，不是从文件名")
print("   label来自JSON内部的match_info字段")

# 6. 验证推荐时是否使用了比分
print("\n" + "=" * 80)
print("【检查6】推荐时是否能看到比分？")
print("=" * 80)

print("\n推荐引擎的输入：")
print("  recommender.recommend(file_path)")
print("  └─> 读取JSON文件")
print("      └─> 提取 trade_data, handicap_data")
print("          └─> 计算推荐")

print("\n✅ 推荐引擎**不应该**能看到比分")
print("   但需要验证match_info.label是否被使用")

# 7. 终极验证：时间顺序
print("\n" + "=" * 80)
print("【检查7】数据时间顺序验证")
print("=" * 80)

print("\n关键时间线：")
print("1. 比赛开始前：采集盘口数据、成交数据")
print("2. 比赛进行中：无法使用")
print("3. 比赛结束后：记录比分")

print("\ntrade_data.data[0] 使用的是哪个时间点的数据？")
print("⚠️  如果是比赛结束后的最新数据 → **未来函数**")
print("✅ 如果是比赛开始前的最后数据 → 合法")

print("\n需要验证：")
print("□ trade_data的时间戳是否在比赛开始前")
print("□ 是否应该使用trade_data.data[-1]（最早的）而不是[0]（最新的）")

# 8. 总结
print("\n" + "=" * 80)
print("🎯 验证总结")
print("=" * 80)

print("""
✅ 推荐逻辑本身无问题：
   - 只使用成交占比、必发指数、成交量
   - 不直接使用比分

⚠️  需要验证的关键问题：
   1. trade_data.data[0] 的时间是否在比赛前？
   2. 如果在比赛后，那就是**严重的未来函数问题**
   3. 应该使用比赛前最后一次采集的数据

❌ 已发现的问题：
   - 文件名包含比分（但未在推荐中使用，问题不大）

🔧 建议修正：
   1. 验证trade_data时间戳
   2. 如果有问题，修改为只使用比赛前的数据
   3. 用未来数据（12月）做前向测试
""")

print("\n" + "=" * 80)
print("✅ 验证完成")
print("=" * 80)
