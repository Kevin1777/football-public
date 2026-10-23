#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1推荐模型 - 准确率回测

功能：
1. 从JSON文件名中提取实际比分
2. 对比推荐结果与实际结果
3. 计算准确率
"""

import re
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from recommendation.x1_json_recommender import X1JSONRecommender

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def extract_score_from_filename(filename: str) -> Optional[Tuple[int, int]]:
    """
    从文件名中提取比分
    
    示例:
    - 2025-09-18_瑞士超_卢加诺_vs_洛桑_1_1_0100.json -> (1, 1)
    - 2025-09-18_丹麦杯_奥尔堡_vs_中日德兰_0_3_0000.json -> (0, 3)
    """
    # 匹配模式: _数字_数字_时间.json
    pattern = r'_(\d+)_(\d+)_\d{4}\.json$'
    match = re.search(pattern, filename)
    
    if match:
        home_score = int(match.group(1))
        away_score = int(match.group(2))
        return (home_score, away_score)
    
    return None


def determine_actual_result(home_score: int, away_score: int, handicap: float) -> str:
    """
    根据实际比分和盘口，判断实际结果
    
    Args:
        home_score: 主队实际得分
        away_score: 客队实际得分
        handicap: 盘口值（负数=主队让球，正数=客队让球）
        
    Returns:
        'home': 主队赢盘
        'away': 客队赢盘
        'draw': 走盘
    """
    # 计算让球后的比分差
    score_diff = home_score - away_score  # 正=主队赢，负=客队赢
    adjusted_diff = score_diff + handicap  # 加上盘口调整
    
    if adjusted_diff > 0:
        return 'home'
    elif adjusted_diff < 0:
        return 'away'
    else:
        return 'draw'  # 走盘


def backtest_accuracy():
    """回测准确率"""
    
    print("=" * 80)
    print("🎯 X1 JSON推荐模型 - 准确率回测")
    print("=" * 80)
    print()
    
    recommender = X1JSONRecommender()
    data_dir = Path("data")
    
    # 查找所有包含比分的JSON文件
    all_json_files = list(data_dir.rglob("2025-*_*_*_*.json"))
    
    # 过滤出包含比分的文件
    scored_files = []
    for json_file in all_json_files:
        score = extract_score_from_filename(json_file.name)
        if score is not None:
            scored_files.append(json_file)
    
    print(f"📂 找到 {len(scored_files)} 个包含比分的比赛文件")
    print(f"⏳ 开始回测...")
    print()
    
    # 统计数据
    stats = {
        'total': 0,
        'with_recommendation': 0,
        'correct': 0,
        'wrong': 0,
        'draw': 0,  # 走盘
        'no_recommendation': 0,
        'by_confidence': {
            'high': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},  # >=0.85
            'mid': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},   # 0.60-0.85
            'low': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0}    # <0.60
        },
        'by_direction': {
            'home': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},
            'away': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0}
        }
    }
    
    results = []
    
    for i, json_file in enumerate(scored_files, 1):
        if i % 50 == 0:
            print(f"  处理中... {i}/{len(scored_files)}")
        
        # 提取实际比分
        actual_score = extract_score_from_filename(json_file.name)
        if not actual_score:
            continue
        
        home_score, away_score = actual_score
        
        # 生成推荐
        result = recommender.recommend(str(json_file))
        
        # 如果熔断，跳过
        if result.get('meltdown'):
            stats['no_recommendation'] += 1
            continue
        
        stats['total'] += 1
        
        # 提取推荐信息
        rec = result.get('recommendation', {})
        direction = rec.get('direction', 'none')
        confidence = rec.get('confidence', 0)
        
        # 如果无推荐，跳过
        if direction == 'none':
            stats['no_recommendation'] += 1
            continue
        
        stats['with_recommendation'] += 1
        
        # 获取盘口
        metrics = result.get('scores', {})
        match_info = result.get('match_info', {})
        
        # 从原始数据中获取盘口值
        # 注意：我们需要从推荐结果中提取盘口信息
        handicap_str = rec.get('handicap', '')
        
        # 简化判断：主队赢还是客队赢（不考虑盘口）
        if home_score > away_score:
            actual_result = 'home'
        elif away_score > home_score:
            actual_result = 'away'
        else:
            actual_result = 'draw'
        
        # 判断推荐是否正确
        is_correct = (direction == actual_result)
        is_draw = (actual_result == 'draw')
        
        if is_draw:
            stats['draw'] += 1
        elif is_correct:
            stats['correct'] += 1
        else:
            stats['wrong'] += 1
        
        # 按置信度统计
        if confidence >= 0.85:
            conf_level = 'high'
        elif confidence >= 0.60:
            conf_level = 'mid'
        else:
            conf_level = 'low'
        
        stats['by_confidence'][conf_level]['total'] += 1
        if is_draw:
            stats['by_confidence'][conf_level]['draw'] += 1
        elif is_correct:
            stats['by_confidence'][conf_level]['correct'] += 1
        else:
            stats['by_confidence'][conf_level]['wrong'] += 1
        
        # 按方向统计
        stats['by_direction'][direction]['total'] += 1
        if is_draw:
            stats['by_direction'][direction]['draw'] += 1
        elif is_correct:
            stats['by_direction'][direction]['correct'] += 1
        else:
            stats['by_direction'][direction]['wrong'] += 1
        
        # 保存结果
        results.append({
            'file': json_file.name,
            'match': f"{match_info.get('home', 'N/A')} vs {match_info.get('away', 'N/A')}",
            'actual_score': f"{home_score}-{away_score}",
            'recommendation': direction,
            'confidence': confidence,
            'actual_result': actual_result,
            'is_correct': is_correct,
            'is_draw': is_draw
        })
    
    print()
    print(f"✅ 回测完成！")
    print()
    
    # 生成报告
    print("=" * 80)
    print("📊 回测结果")
    print("=" * 80)
    print()
    
    print(f"总计比赛数: {len(scored_files)}")
    print(f"有推荐的比赛: {stats['with_recommendation']}")
    print(f"无推荐/熔断: {stats['no_recommendation']}")
    print()
    
    if stats['with_recommendation'] > 0:
        total_decided = stats['correct'] + stats['wrong']
        accuracy = stats['correct'] / total_decided * 100 if total_decided > 0 else 0
        
        print("=" * 80)
        print("🎯 整体准确率")
        print("=" * 80)
        print(f"推荐正确: {stats['correct']}")
        print(f"推荐错误: {stats['wrong']}")
        print(f"走盘（平局）: {stats['draw']}")
        print(f"准确率: {accuracy:.1f}% ({stats['correct']}/{total_decided})")
        print()
        
        print("=" * 80)
        print("📈 按置信度分析")
        print("=" * 80)
        
        for level_name, level_label in [('high', '🟢 高置信度 (≥0.85)'), 
                                         ('mid', '🟡 中置信度 (0.60-0.85)'), 
                                         ('low', '🔴 低置信度 (<0.60)')]:
            level_stats = stats['by_confidence'][level_name]
            level_decided = level_stats['correct'] + level_stats['wrong']
            
            if level_decided > 0:
                level_accuracy = level_stats['correct'] / level_decided * 100
                print(f"{level_label}")
                print(f"  总数: {level_stats['total']}")
                print(f"  正确: {level_stats['correct']}")
                print(f"  错误: {level_stats['wrong']}")
                print(f"  走盘: {level_stats['draw']}")
                print(f"  准确率: {level_accuracy:.1f}%")
                print()
        
        print("=" * 80)
        print("🎯 按推荐方向分析")
        print("=" * 80)
        
        for direction_name, direction_label in [('home', '主队'), ('away', '客队')]:
            dir_stats = stats['by_direction'][direction_name]
            dir_decided = dir_stats['correct'] + dir_stats['wrong']
            
            if dir_decided > 0:
                dir_accuracy = dir_stats['correct'] / dir_decided * 100
                print(f"{direction_label}推荐:")
                print(f"  总数: {dir_stats['total']}")
                print(f"  正确: {dir_stats['correct']}")
                print(f"  错误: {dir_stats['wrong']}")
                print(f"  走盘: {dir_stats['draw']}")
                print(f"  准确率: {dir_accuracy:.1f}%")
                print()
        
        # 显示部分错误案例
        print("=" * 80)
        print("❌ 错误案例示例（前10个）")
        print("=" * 80)
        
        wrong_cases = [r for r in results if not r['is_correct'] and not r['is_draw']][:10]
        for i, case in enumerate(wrong_cases, 1):
            print(f"{i}. {case['match']}")
            print(f"   实际比分: {case['actual_score']}")
            print(f"   推荐: {case['recommendation']}, 置信度: {case['confidence']:.2f}")
            print(f"   实际结果: {case['actual_result']}")
            print()
        
        # 显示高置信度正确案例
        print("=" * 80)
        print("✅ 高置信度正确案例（前10个）")
        print("=" * 80)
        
        high_conf_correct = [r for r in results if r['is_correct'] and r['confidence'] >= 0.85][:10]
        for i, case in enumerate(high_conf_correct, 1):
            print(f"{i}. {case['match']}")
            print(f"   实际比分: {case['actual_score']}")
            print(f"   推荐: {case['recommendation']}, 置信度: {case['confidence']:.2f}")
            print(f"   ✅ 推荐正确")
            print()
    
    print("=" * 80)
    
    return stats, results


if __name__ == "__main__":
    stats, results = backtest_accuracy()
    
    # 导出详细结果
    import json
    with open("X1_准确率回测结果.json", 'w', encoding='utf-8') as f:
        json.dump({
            'statistics': stats,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print()
    print("✅ 详细结果已导出: X1_准确率回测结果.json")
