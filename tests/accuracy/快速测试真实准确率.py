#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试版 - 只测试最近30场比赛验证逻辑
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from recommendation.x1_json_recommender_fixed import X1JSONRecommenderFixed
from recommendation.x1_json_recommender import X1JSONRecommender

logging.basicConfig(level=logging.WARNING, format='%(message)s')  # 只显示警告
logger = logging.getLogger(__name__)


def extract_kickoff_and_score(filename: str) -> Optional[Tuple[str, int, int]]:
    """从文件名提取开赛时间和比分"""
    pattern = r'(\d{4}-\d{2}-\d{2})_.*_(\d+)_(\d+)_(\d{4})\.json$'
    match = re.search(pattern, filename)
    
    if match:
        date = match.group(1)
        home_score = int(match.group(2))
        away_score = int(match.group(3))
        time = match.group(4)
        
        hour = time[:2]
        minute = time[2:]
        kickoff_time = f"{date} {hour}:{minute}:00"
        
        return (kickoff_time, home_score, away_score)
    
    return None


def quick_test():
    """快速测试 - 对比新旧引擎"""
    
    print("=" * 80)
    print("🔬 快速测试 - 对比真实准确率 vs 虚假准确率")
    print("=" * 80)
    print()
    
    # 初始化两个引擎
    fixed_engine = X1JSONRecommenderFixed()  # 修复版（真实）
    old_engine = X1JSONRecommender()          # 原版（可能泄露）
    
    data_dir = Path("data")
    
    # 找所有文件
    all_files = list(data_dir.rglob("2025-*.json"))
    
    # 🔥 只保留文件名中包含比分的（有 _数字_数字_ 格式）
    scored_files = []
    for f in all_files:
        if extract_kickoff_and_score(f.name):
            scored_files.append(f)
    
    # 按修改时间排序，取最新30个
    scored_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    test_files = scored_files[:30]
    
    print(f"📂 总文件: {len(all_files)} | 有比分: {len(scored_files)} | 测试最近: {len(test_files)}")
    print()
    
    results = {
        'fixed': {'correct': 0, 'wrong': 0, 'no_rec': 0},
        'old': {'correct': 0, 'wrong': 0, 'no_rec': 0}
    }
    
    for i, json_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] {json_file.name[:60]}...")
        
        # 提取信息
        info = extract_kickoff_and_score(json_file.name)
        if not info:
            print("  ⚠️ 无法提取比分，跳过")
            continue
        
        kickoff_time, home_score, away_score = info
        actual_result = 'home' if home_score > away_score else ('away' if away_score > home_score else 'draw')
        
        try:
            # 测试修复版（真实）
            fixed_result = fixed_engine.recommend(
                str(json_file),
                kickoff_time=kickoff_time,
                strict_mode=True
            )
            
            fixed_rec = fixed_result.get('recommendation', {}).get('direction', 'none')
            
            if fixed_rec == 'none' or fixed_result.get('meltdown'):
                results['fixed']['no_rec'] += 1
                fixed_status = "⚪ 无推荐"
            elif fixed_rec == actual_result:
                results['fixed']['correct'] += 1
                fixed_status = "✅ 正确"
            else:
                results['fixed']['wrong'] += 1
                fixed_status = "❌ 错误"
            
            # 测试原版（可能泄露）
            old_result = old_engine.recommend(str(json_file))
            old_rec = old_result.get('recommendation', {}).get('direction', 'none')
            
            if old_rec == 'none' or old_result.get('meltdown'):
                results['old']['no_rec'] += 1
                old_status = "⚪ 无推荐"
            elif old_rec == actual_result:
                results['old']['correct'] += 1
                old_status = "✅ 正确"
            else:
                results['old']['wrong'] += 1
                old_status = "❌ 错误"
            
            print(f"  实际: {actual_result} | 修复版: {fixed_rec} {fixed_status} | 原版: {old_rec} {old_status}")
            print(f"  比分: {home_score}-{away_score}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            continue
        
        print()
    
    # 统计
    print("=" * 80)
    print("📊 测试结果对比")
    print("=" * 80)
    print()
    
    fixed_total = results['fixed']['correct'] + results['fixed']['wrong']
    old_total = results['old']['correct'] + results['old']['wrong']
    
    if fixed_total > 0:
        fixed_acc = results['fixed']['correct'] / fixed_total * 100
        print(f"🔧 修复版（真实）:")
        print(f"   准确率: {fixed_acc:.1f}%")
        print(f"   正确: {results['fixed']['correct']} | 错误: {results['fixed']['wrong']} | 无推荐: {results['fixed']['no_rec']}")
    else:
        print(f"🔧 修复版: 无有效推荐")
    
    print()
    
    if old_total > 0:
        old_acc = results['old']['correct'] / old_total * 100
        print(f"⚠️ 原版（可能泄露）:")
        print(f"   准确率: {old_acc:.1f}%")
        print(f"   正确: {results['old']['correct']} | 错误: {results['old']['wrong']} | 无推荐: {results['old']['no_rec']}")
    else:
        print(f"⚠️ 原版: 无有效推荐")
    
    print()
    print("=" * 80)
    
    if fixed_total > 0 and old_total > 0:
        diff = old_acc - fixed_acc
        if diff > 10:
            print(f"⚠️  警告: 原版比修复版高 {diff:.1f}%")
            print(f"   这可能说明原版使用了完场后的数据（数据泄露）")
        elif diff > 0:
            print(f"✅ 原版略高 {diff:.1f}%，差异在合理范围")
        else:
            print(f"✅ 修复版与原版接近，数据泄露可能性较小")
    
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    quick_test()
