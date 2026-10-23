#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对比测试：固定阈值0.80 vs 动态阈值（联赛分级）
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from recommendation.x1_json_recommender_fixed import X1JSONRecommenderFixed

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


# 联赛等级配置
LEAGUE_TIERS = {
    'S级': ['英超', '西甲', '德甲', '意甲', '法甲', '欧冠', '欧联', '世界杯', '欧洲杯'],
    'A级': ['英冠', '荷甲', '葡超', '巴甲', '阿甲', '中超', '亚冠', '美职业'],
    'B级': ['英甲', '德乙', '法乙', 'J联赛', '俄超', '土超'],
    'C级': []  # 其他所有
}

def get_league_tier(league: str) -> str:
    """获取联赛等级"""
    if not league:
        return 'C级'
    
    for tier, leagues in LEAGUE_TIERS.items():
        if any(l in league for l in leagues):
            return tier
    return 'C级'


def extract_kickoff_and_score(filename: str) -> Optional[Tuple[str, int, int, str]]:
    """从文件名提取开赛时间、比分和联赛"""
    # 提取联赛名称
    parts = filename.split('_')
    if len(parts) < 5:
        return None
    
    league = parts[1]  # 第二部分是联赛
    
    # 提取比分和时间
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
        
        return (kickoff_time, home_score, away_score, league)
    
    return None


def test_comparison():
    """对比测试两种方案"""
    
    print("=" * 80)
    print("🔬 方案对比测试")
    print("=" * 80)
    print()
    print("方案A: 固定阈值0.80")
    print("方案C: 动态阈值（S级0.75, A级0.80, B级0.85, C级0.90）")
    print()
    
    # 初始化引擎
    engine = X1JSONRecommenderFixed()
    
    data_dir = Path("data")
    
    # 找所有有比分的文件
    all_files = list(data_dir.rglob("2025-*.json"))
    
    scored_files = []
    for f in all_files:
        info = extract_kickoff_and_score(f.name)
        if info:
            kickoff_time, home_score, away_score, league = info
            scored_files.append({
                'file': f,
                'kickoff_time': kickoff_time,
                'home_score': home_score,
                'away_score': away_score,
                'league': league
            })
    
    print(f"📂 找到 {len(scored_files)} 个有效比赛文件")
    print(f"⏳ 开始对比测试...")
    print()
    
    # 两种方案的统计
    stats = {
        'fixed_0.80': {'correct': 0, 'wrong': 0, 'draw': 0, 'no_rec': 0, 'total': 0},
        'dynamic': {'correct': 0, 'wrong': 0, 'draw': 0, 'no_rec': 0, 'total': 0, 'by_tier': {}}
    }
    
    for i, match in enumerate(scored_files, 1):
        if i % 200 == 0:
            print(f"  处理中... {i}/{len(scored_files)}")
        
        json_file = match['file']
        kickoff_time = match['kickoff_time']
        home_score = match['home_score']
        away_score = match['away_score']
        league = match['league']
        
        # 获取联赛等级
        tier = get_league_tier(league)
        
        # 实际结果
        if home_score > away_score:
            actual = 'home'
        elif away_score > home_score:
            actual = 'away'
        else:
            actual = 'draw'
        
        try:
            # 生成推荐
            result = engine.recommend(str(json_file), kickoff_time=kickoff_time, strict_mode=True)
            
            if result.get('meltdown'):
                continue
            
            rec = result.get('recommendation', {})
            direction = rec.get('direction', 'none')
            confidence = rec.get('confidence', 0)
            
            if direction == 'none':
                continue
            
            stats['fixed_0.80']['total'] += 1
            stats['dynamic']['total'] += 1
            
            # 方案A：固定阈值0.80
            if confidence >= 0.80:
                if direction == actual:
                    stats['fixed_0.80']['correct'] += 1
                elif actual == 'draw':
                    stats['fixed_0.80']['draw'] += 1
                else:
                    stats['fixed_0.80']['wrong'] += 1
            else:
                stats['fixed_0.80']['no_rec'] += 1
            
            # 方案C：动态阈值
            dynamic_thresholds = {
                'S级': 0.75,
                'A级': 0.80,
                'B级': 0.85,
                'C级': 0.90
            }
            threshold = dynamic_thresholds.get(tier, 0.90)
            
            if tier not in stats['dynamic']['by_tier']:
                stats['dynamic']['by_tier'][tier] = {
                    'correct': 0, 'wrong': 0, 'draw': 0, 'no_rec': 0, 'total': 0, 'threshold': threshold
                }
            
            stats['dynamic']['by_tier'][tier]['total'] += 1
            
            if confidence >= threshold:
                if direction == actual:
                    stats['dynamic']['correct'] += 1
                    stats['dynamic']['by_tier'][tier]['correct'] += 1
                elif actual == 'draw':
                    stats['dynamic']['draw'] += 1
                    stats['dynamic']['by_tier'][tier]['draw'] += 1
                else:
                    stats['dynamic']['wrong'] += 1
                    stats['dynamic']['by_tier'][tier]['wrong'] += 1
            else:
                stats['dynamic']['no_rec'] += 1
                stats['dynamic']['by_tier'][tier]['no_rec'] += 1
                
        except Exception as e:
            continue
    
    # 输出结果
    print()
    print("=" * 80)
    print("📊 对比结果")
    print("=" * 80)
    print()
    
    # 方案A
    a_stats = stats['fixed_0.80']
    a_valid = a_stats['correct'] + a_stats['wrong']
    if a_valid > 0:
        a_acc = a_stats['correct'] / a_valid * 100
        a_rec_count = a_valid + a_stats['draw']
        a_rec_rate = a_rec_count / a_stats['total'] * 100 if a_stats['total'] > 0 else 0
        
        print("📈 方案A: 固定阈值0.80")
        print(f"   准确率: {a_acc:.1f}% ({a_stats['correct']}/{a_valid})")
        print(f"   推荐数量: {a_rec_count}场 ({a_rec_rate:.1f}%)")
        print(f"   正确: {a_stats['correct']} | 错误: {a_stats['wrong']} | 走盘: {a_stats['draw']}")
    
    print()
    
    # 方案C
    c_stats = stats['dynamic']
    c_valid = c_stats['correct'] + c_stats['wrong']
    if c_valid > 0:
        c_acc = c_stats['correct'] / c_valid * 100
        c_rec_count = c_valid + c_stats['draw']
        c_rec_rate = c_rec_count / c_stats['total'] * 100 if c_stats['total'] > 0 else 0
        
        print("📈 方案C: 动态阈值（联赛分级）")
        print(f"   准确率: {c_acc:.1f}% ({c_stats['correct']}/{c_valid})")
        print(f"   推荐数量: {c_rec_count}场 ({c_rec_rate:.1f}%)")
        print(f"   正确: {c_stats['correct']} | 错误: {c_stats['wrong']} | 走盘: {c_stats['draw']}")
        print()
        
        # 按联赛等级统计
        print("   📊 分级统计:")
        for tier in ['S级', 'A级', 'B级', 'C级']:
            if tier in c_stats['by_tier']:
                tier_stats = c_stats['by_tier'][tier]
                tier_valid = tier_stats['correct'] + tier_stats['wrong']
                if tier_valid > 0:
                    tier_acc = tier_stats['correct'] / tier_valid * 100
                    tier_rec = tier_valid + tier_stats['draw']
                    print(f"      {tier} (阈值{tier_stats['threshold']}): {tier_acc:.1f}% ({tier_stats['correct']}/{tier_valid}) | 推荐{tier_rec}场")
    
    print()
    print("=" * 80)
    print("💡 对比结论")
    print("=" * 80)
    print()
    
    if a_valid > 0 and c_valid > 0:
        acc_diff = c_acc - a_acc
        rec_diff = c_rec_count - a_rec_count
        
        print(f"准确率差异: {acc_diff:+.1f}个百分点")
        print(f"推荐量差异: {rec_diff:+d}场")
        print()
        
        # 推荐
        if abs(acc_diff) < 2 and rec_diff > 50:
            print("✅ 推荐：方案C（动态阈值）")
            print("   理由：准确率相近，但推荐量更多")
        elif acc_diff > 3:
            print("✅ 推荐：方案C（动态阈值）")
            print("   理由：准确率更高")
        elif acc_diff < -3:
            print("✅ 推荐：方案A（固定0.80）")
            print("   理由：准确率更高")
        elif rec_diff > 0:
            print("✅ 推荐：方案C（动态阈值）")
            print("   理由：综合考虑推荐量和准确率")
        else:
            print("✅ 推荐：方案A（固定0.80）")
            print("   理由：更简单，效果相近")
    
    print()
    print("=" * 80)
    
    return stats


if __name__ == "__main__":
    test_comparison()
