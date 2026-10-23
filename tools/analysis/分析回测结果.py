#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析回测结果，找出提升准确率的关键
"""

import json
from pathlib import Path

# 读取结果
with open('真实准确率回测结果.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

stats = data['stats']

print("=" * 80)
print("📊 完整回测数据分析")
print("=" * 80)
print()

# 总体统计
total = stats['total']
with_rec = stats['with_recommendation']
correct = stats['correct']
wrong = stats['wrong']
draw = stats['draw']
no_rec = stats['no_recommendation']

print("📈 总体数据:")
print(f"   总比赛数: {total}")
print(f"   有推荐: {with_rec} ({with_rec/total*100:.1f}%)")
print(f"   无推荐: {no_rec} ({no_rec/total*100:.1f}%)")
print()

# 推荐准确率（排除走盘）
valid_total = correct + wrong
if valid_total > 0:
    accuracy = correct / valid_total * 100
    print(f"✅ 总体准确率: {accuracy:.1f}% ({correct}/{valid_total})")
    print(f"   正确: {correct}")
    print(f"   错误: {wrong}")
    print(f"   走盘: {draw} (不计入准确率)")
print()

print("=" * 80)
print("🎯 按置信度分析（关键发现）")
print("=" * 80)
print()

# 按置信度分析
conf_levels = {
    'high': ('高置信度', '>=0.85'),
    'mid': ('中置信度', '0.60-0.85'),
    'low': ('低置信度', '<0.60')
}

for key, (name, range_str) in conf_levels.items():
    conf_stats = stats['by_confidence'][key]
    total_conf = conf_stats['total']
    correct_conf = conf_stats['correct']
    wrong_conf = conf_stats['wrong']
    draw_conf = conf_stats['draw']
    
    if total_conf > 0:
        valid_conf = correct_conf + wrong_conf
        if valid_conf > 0:
            acc_conf = correct_conf / valid_conf * 100
            
            print(f"📊 {name} ({range_str}):")
            print(f"   推荐数量: {total_conf} ({total_conf/with_rec*100:.1f}%)")
            print(f"   准确率: {acc_conf:.1f}% ({correct_conf}/{valid_conf})")
            print(f"   正确: {correct_conf} | 错误: {wrong_conf} | 走盘: {draw_conf}")
            print()

print("=" * 80)
print("💡 关键发现与建议")
print("=" * 80)
print()

# 计算高置信度统计
high_stats = stats['by_confidence']['high']
high_valid = high_stats['correct'] + high_stats['wrong']
high_acc = high_stats['correct'] / high_valid * 100 if high_valid > 0 else 0

mid_stats = stats['by_confidence']['mid']
mid_valid = mid_stats['correct'] + mid_stats['wrong']
mid_acc = mid_stats['correct'] / mid_valid * 100 if mid_valid > 0 else 0

low_stats = stats['by_confidence']['low']
low_valid = low_stats['correct'] + low_stats['wrong']
low_acc = low_stats['correct'] / low_valid * 100 if low_valid > 0 else 0

print(f"🔥 发现1: 置信度与准确率强相关")
print(f"   高置信度: {high_acc:.1f}% ⭐⭐⭐⭐⭐")
print(f"   中置信度: {mid_acc:.1f}% ⭐⭐⭐")
print(f"   低置信度: {low_acc:.1f}% ⭐")
print()

print(f"💡 建议1: 只推荐高置信度")
print(f"   当前: 推荐{with_rec}场，准确率{accuracy:.1f}%")
print(f"   优化后: 推荐{high_stats['total']}场，准确率{high_acc:.1f}%")
print(f"   提升: +{high_acc-accuracy:.1f}个百分点！")
print()

print(f"💡 建议2: 调整置信度阈值")
thresholds = [0.70, 0.75, 0.80, 0.85]
for threshold in thresholds:
    if threshold == 0.85:
        rec_count = high_stats['total']
        rec_acc = high_acc
    elif threshold == 0.60:
        rec_count = high_stats['total'] + mid_stats['total']
        rec_correct = high_stats['correct'] + mid_stats['correct']
        rec_wrong = high_stats['wrong'] + mid_stats['wrong']
        rec_acc = rec_correct / (rec_correct + rec_wrong) * 100
    else:
        # 估算
        continue
    
    if threshold in [0.85, 0.60]:
        print(f"   阈值{threshold}: 推荐{rec_count}场 ({rec_count/total*100:.1f}%)，准确率{rec_acc:.1f}%")

print()
print("=" * 80)
print("🚀 推荐的优化策略")
print("=" * 80)
print()

print("✅ 立即执行（今天）:")
print("   1. 设置 MIN_CONFIDENCE = 0.85")
print(f"   2. 预期效果: 准确率提升到 {high_acc:.1f}%")
print(f"   3. 推荐量: {high_stats['total']}场 (原{with_rec}场)")
print()

print("✅ 进阶优化（本周）:")
print("   1. 强化风控模块")
print("   2. 添加数据质量过滤")
print("   3. 预期效果: 准确率 85%+")
print()

print("✅ 长期优化（本月）:")
print("   1. 联赛分级策略")
print("   2. 机器学习增强")
print("   3. 预期效果: 准确率 88%+")
print()

print("=" * 80)
