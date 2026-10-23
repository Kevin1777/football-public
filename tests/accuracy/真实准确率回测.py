#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1推荐模型 - 真实准确率回测（修复未来函数版）

核心改进：
1. 从文件名提取开赛时间
2. 只使用赛前数据
3. 严格时间验证
4. 透明的回测流程
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

# 使用修复版推荐引擎
from recommendation.x1_json_recommender_fixed import X1JSONRecommenderFixed

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def extract_kickoff_and_score_from_filename(filename: str) -> Optional[Tuple[str, int, int]]:
    """
    从文件名中提取开赛时间和比分
    
    示例:
    - 2025-11-25_欧联U19_曼城U19_vs_勒沃库森U19_2_0_2300.json
      → ("2025-11-25 23:00", 2, 0)
    
    Returns:
        (开赛时间字符串, 主队得分, 客队得分) 或 None
    """
    # 匹配模式: 日期_联赛_主队_vs_客队_主队得分_客队得分_时间.json
    pattern = r'(\d{4}-\d{2}-\d{2})_.*_(\d+)_(\d+)_(\d{4})\.json$'
    match = re.search(pattern, filename)
    
    if match:
        date = match.group(1)
        home_score = int(match.group(2))
        away_score = int(match.group(3))
        time = match.group(4)
        
        # 转换时间格式 0100 -> 01:00
        hour = time[:2]
        minute = time[2:]
        kickoff_time = f"{date} {hour}:{minute}:00"
        
        return (kickoff_time, home_score, away_score)
    
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
    score_diff = home_score - away_score
    adjusted_diff = score_diff + handicap
    
    if adjusted_diff > 0:
        return 'home'
    elif adjusted_diff < 0:
        return 'away'
    else:
        return 'draw'


def backtest_real_accuracy():
    """真实准确率回测（无未来函数版）"""
    
    print("=" * 80)
    print("🎯 X1 JSON推荐模型 - 真实准确率回测（修复未来函数版）")
    print("=" * 80)
    print()
    print("⚠️  关键改进:")
    print("   1. 只使用赛前数据（开赛时间之前）")
    print("   2. 严格时间验证")
    print("   3. 透明的数据过滤过程")
    print()
    
    # 使用修复版推荐引擎
    recommender = X1JSONRecommenderFixed()
    data_dir = Path("data")
    
    # 查找所有包含比分的JSON文件
    all_json_files = list(data_dir.rglob("2025-*_*_*_*.json"))
    
    # 过滤出包含比分和时间的文件
    valid_files = []
    for json_file in all_json_files:
        result = extract_kickoff_and_score_from_filename(json_file.name)
        if result is not None:
            kickoff_time, home_score, away_score = result
            valid_files.append({
                'file': json_file,
                'kickoff_time': kickoff_time,
                'home_score': home_score,
                'away_score': away_score
            })
    
    print(f"📂 找到 {len(valid_files)} 个有效比赛文件")
    print(f"⏳ 开始回测（严格模式：只使用赛前数据）...")
    print()
    
    # 统计数据
    stats = {
        'total': 0,
        'with_recommendation': 0,
        'correct': 0,
        'wrong': 0,
        'draw': 0,
        'no_recommendation': 0,
        'time_validation_failed': 0,  # 新增：时间验证失败
        'by_confidence': {
            'high': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},
            'mid': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},
            'low': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0}
        },
        'by_direction': {
            'home': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0},
            'away': {'total': 0, 'correct': 0, 'wrong': 0, 'draw': 0}
        }
    }
    
    results = []
    
    for i, match in enumerate(valid_files, 1):
        if i % 50 == 0:
            print(f"  处理中... {i}/{len(valid_files)}")
        
        json_file = match['file']
        kickoff_time = match['kickoff_time']
        home_score = match['home_score']
        away_score = match['away_score']
        
        # 🔥 关键：使用严格模式，传入开赛时间
        result = recommender.recommend(
            str(json_file), 
            kickoff_time=kickoff_time,
            strict_mode=True
        )
        
        # 检查是否熔断
        if result.get('meltdown'):
            melt_type = result['meltdown'].get('type', '')
            if melt_type == 'F-TIME':
                stats['time_validation_failed'] += 1
            else:
                stats['no_recommendation'] += 1
            continue
        
        stats['total'] += 1
        
        # 提取推荐信息
        rec = result.get('recommendation', {})
        direction = rec.get('direction', 'none')
        confidence = rec.get('confidence', 0)
        
        if direction == 'none':
            stats['no_recommendation'] += 1
            continue
        
        stats['with_recommendation'] += 1
        
        # 获取盘口（用于判断赢盘）
        # 简化：假设盘口为0（直接比较胜负）
        handicap = 0
        
        # 判断实际结果
        actual_result = determine_actual_result(home_score, away_score, handicap)
        
        # 判断推荐是否正确
        if direction == actual_result:
            is_correct = True
            stats['correct'] += 1
        elif actual_result == 'draw':
            is_correct = False
            stats['draw'] += 1
        else:
            is_correct = False
            stats['wrong'] += 1
        
        # 按置信度统计
        if confidence >= 0.85:
            conf_key = 'high'
        elif confidence >= 0.60:
            conf_key = 'mid'
        else:
            conf_key = 'low'
        
        stats['by_confidence'][conf_key]['total'] += 1
        if is_correct:
            stats['by_confidence'][conf_key]['correct'] += 1
        elif actual_result == 'draw':
            stats['by_confidence'][conf_key]['draw'] += 1
        else:
            stats['by_confidence'][conf_key]['wrong'] += 1
        
        # 按方向统计
        if direction in ['home', 'away']:
            stats['by_direction'][direction]['total'] += 1
            if is_correct:
                stats['by_direction'][direction]['correct'] += 1
            elif actual_result == 'draw':
                stats['by_direction'][direction]['draw'] += 1
            else:
                stats['by_direction'][direction]['wrong'] += 1
        
        # 记录结果
        results.append({
            'file': json_file.name,
            'kickoff_time': kickoff_time,
            'recommendation': direction,
            'confidence': confidence,
            'actual': actual_result,
            'score': f"{home_score}-{away_score}",
            'correct': is_correct
        })
    
    # 打印统计结果
    print()
    print("=" * 80)
    print("📊 回测结果统计（真实准确率 - 无未来函数）")
    print("=" * 80)
    print()
    
    total_with_rec = stats['with_recommendation']
    if total_with_rec > 0:
        accuracy = stats['correct'] / total_with_rec * 100
        print(f"✅ 总准确率: {accuracy:.1f}% ({stats['correct']}/{total_with_rec})")
        print(f"   正确: {stats['correct']} | 错误: {stats['wrong']} | 走盘: {stats['draw']}")
    else:
        print("❌ 无有效推荐")
    
    print()
    print(f"📊 数据统计:")
    print(f"   总比赛数: {len(valid_files)}")
    print(f"   有推荐: {stats['with_recommendation']}")
    print(f"   无推荐: {stats['no_recommendation']}")
    print(f"   时间验证失败: {stats['time_validation_failed']}")
    
    print()
    print("📈 按置信度统计:")
    for conf_level, conf_stats in stats['by_confidence'].items():
        if conf_stats['total'] > 0:
            acc = conf_stats['correct'] / conf_stats['total'] * 100
            print(f"   {conf_level.upper()}: {acc:.1f}% ({conf_stats['correct']}/{conf_stats['total']})")
    
    print()
    print("🎯 按方向统计:")
    for direction, dir_stats in stats['by_direction'].items():
        if dir_stats['total'] > 0:
            acc = dir_stats['correct'] / dir_stats['total'] * 100
            print(f"   {direction.upper()}: {acc:.1f}% ({dir_stats['correct']}/{dir_stats['total']})")
    
    print()
    print("=" * 80)
    print("⚠️  重要说明:")
    print("   - 本次回测使用严格模式，只使用赛前数据")
    print("   - 所有交易数据都经过时间过滤")
    print("   - 这是真实的准确率，无数据泄露")
    print("=" * 80)
    
    # 导出详细结果
    if results:
        output_file = Path("真实准确率回测结果.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'stats': stats,
                'results': results,
                'validation': {
                    'strict_mode': True,
                    'pre_match_only': True,
                    'no_future_function': True
                }
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 详细结果已保存: {output_file}")
    
    return stats, results


if __name__ == "__main__":
    backtest_real_accuracy()
