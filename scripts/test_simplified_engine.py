"""
测试简化版引擎

对比三个版本：
1. X1原版：51.5%
2. 极简规则：56.0%
3. 简化版引擎：？？？

目标：准确率60%+
"""

import sys
from pathlib import Path
import json
import pandas as pd
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.handicap_engine_simplified import SimplifiedHandicapEngine


def check_prediction_correct(
    recommendation,
    home_score,
    away_score,
    handicap
):
    """检查推荐是否正确"""
    final_rec = recommendation.get('最终推荐', {})
    direction = final_rec.get('direction', '')
    should_bet = final_rec.get('should_bet', False)
    
    if not should_bet or not direction or direction == '观望':
        return None, "观望"
    
    # 判断实际结果
    home_with_handicap = home_score + handicap
    if home_with_handicap > away_score:
        actual_result = "主队赢盘"
    elif home_with_handicap < away_score:
        actual_result = "客队赢盘"
    else:
        actual_result = "走盘"
    
    # 判断推荐方向
    if "主队" in direction or "主" in direction:
        predicted = "主队赢盘"
    elif "客队" in direction or "客" in direction:
        predicted = "客队赢盘"
    else:
        return None, f"未识别方向: {direction}"
    
    is_correct = (predicted == actual_result)
    confidence = final_rec.get('confidence', 0)
    reason = f"推荐{predicted}, 实际{actual_result}, 置信度{confidence:.0%}"
    
    return is_correct, reason


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        if json_file.stem.startswith(('2025-', '2024-')) and json_file.stem.count('_') >= 4:
            json_files.append(json_file)
    
    engine = SimplifiedHandicapEngine()
    
    stats = {
        'total': 0,
        'correct': 0,
        'observed': 0,
        'by_handicap': {
            '大盘口(>1球)': {'total': 0, 'correct': 0, 'observed': 0},
            '小盘口(<0.5球)': {'total': 0, 'correct': 0, 'observed': 0},
            '中盘口(0.5-1.0球)': {'total': 0, 'correct': 0, 'observed': 0},
        },
        'by_confidence': defaultdict(lambda: {'total': 0, 'correct': 0})
    }
    
    examples = {'correct': [], 'wrong': []}
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            match_info = data.get('match_info', {})
            score = match_info.get('score')
            
            if not score:
                continue
            
            parts = score.split('-')
            home_score = int(parts[0])
            away_score = int(parts[1])
            
            trade_data = pd.DataFrame(data['trade_data']['data'])
            if trade_data.empty:
                continue
            
            # 生成推荐
            recommendation = engine.generate_recommendation(
                trade_data=trade_data,
                metadata=data.get('metadata', []),
                handicap_data=data.get('handicap_data', {})
            )
            
            # 获取盘口
            handicap_raw = data['handicap_data'].get('current_handicap', 0)
            handicap_str = data['handicap_data'].get('current_handicap_str', '')
            
            if handicap_raw != 0 and '受' not in handicap_str:
                handicap = -abs(handicap_raw)
            else:
                handicap = handicap_raw
            
            # 检查正确性
            is_correct, reason = check_prediction_correct(
                recommendation, home_score, away_score, handicap
            )
            
            # 分类统计
            abs_handicap = abs(handicap)
            if abs_handicap > 1.0:
                category = '大盘口(>1球)'
            elif abs_handicap < 0.5:
                category = '小盘口(<0.5球)'
            else:
                category = '中盘口(0.5-1.0球)'
            
            if is_correct is None:
                stats['observed'] += 1
                stats['by_handicap'][category]['observed'] += 1
                continue
            
            stats['total'] += 1
            stats['by_handicap'][category]['total'] += 1
            
            if is_correct:
                stats['correct'] += 1
                stats['by_handicap'][category]['correct'] += 1
            
            # 按置信度统计
            confidence = recommendation.get('最终推荐', {}).get('confidence', 0)
            conf_level = f"{int(confidence*100)}%"
            stats['by_confidence'][conf_level]['total'] += 1
            if is_correct:
                stats['by_confidence'][conf_level]['correct'] += 1
            
            # 保存案例
            example = {
                'home': match_info['home'],
                'away': match_info['away'],
                'score': score,
                'handicap': handicap,
                'handicap_str': handicap_str,
                'direction': recommendation.get('最终推荐', {}).get('direction', ''),
                'confidence': confidence,
                'reason': reason,
                'category': category
            }
            
            if is_correct and len(examples['correct']) < 5:
                examples['correct'].append(example)
            elif not is_correct and len(examples['wrong']) < 5:
                examples['wrong'].append(example)
            
        except Exception as e:
            continue
    
    # 输出结果
    print("\n" + "="*80)
    print("简化版引擎回测结果")
    print("="*80 + "\n")
    
    print("📊 整体统计\n")
    print(f"总比赛数: {stats['total'] + stats['observed']}")
    print(f"有推荐: {stats['total']}")
    print(f"观望: {stats['observed']}")
    print(f"推荐正确: {stats['correct']}")
    print(f"推荐错误: {stats['total'] - stats['correct']}")
    
    if stats['total'] > 0:
        acc = stats['correct'] / stats['total'] * 100
        print(f"\n⭐ 准确率: {acc:.1f}%")
    
    print("\n" + "="*80)
    print("📊 分盘口统计\n")
    
    for category, data in stats['by_handicap'].items():
        if data['total'] > 0:
            acc = data['correct'] / data['total'] * 100
            print(f"{category}:")
            print(f"  推荐: {data['total']}场, 正确: {data['correct']}场, 准确率: {acc:.1f}%")
            if data['observed'] > 0:
                print(f"  观望: {data['observed']}场")
    
    print("\n" + "="*80)
    print("📊 分置信度统计\n")
    
    for conf_level in sorted(stats['by_confidence'].keys(), reverse=True):
        data = stats['by_confidence'][conf_level]
        if data['total'] > 0:
            acc = data['correct'] / data['total'] * 100
            print(f"置信度{conf_level}: {data['correct']}/{data['total']} = {acc:.1f}%")
    
    print("\n" + "="*80)
    print("✅ 正确案例（前5个）\n")
    
    for i, ex in enumerate(examples['correct'], 1):
        print(f"{i}. {ex['home']} vs {ex['away']}")
        print(f"   比分: {ex['score']}, 盘口: {ex['handicap_str']}({ex['handicap']})")
        print(f"   推荐: {ex['direction']}, 置信度: {ex['confidence']:.0%}")
        print(f"   类别: {ex['category']}\n")
    
    print("="*80)
    print("❌ 错误案例（前5个）\n")
    
    for i, ex in enumerate(examples['wrong'], 1):
        print(f"{i}. {ex['home']} vs {ex['away']}")
        print(f"   比分: {ex['score']}, 盘口: {ex['handicap_str']}({ex['handicap']})")
        print(f"   推荐: {ex['direction']}, 置信度: {ex['confidence']:.0%}")
        print(f"   {ex['reason']}")
        print(f"   类别: {ex['category']}\n")
    
    print("="*80)
    print("📈 对比总结\n")
    
    if stats['total'] > 0:
        simplified_acc = stats['correct'] / stats['total'] * 100
        print(f"X1原版准确率:      51.5%")
        print(f"极简规则准确率:    56.0%")
        print(f"简化版引擎准确率: {simplified_acc:.1f}%")
        
        if simplified_acc >= 60:
            print("\n✅ 成功！准确率达到60%+")
            print("   简化版引擎优于X1原版和极简规则")
        elif simplified_acc >= 56:
            print("\n⚠️  改进有限，与极简规则相当")
            print("   需要进一步优化策略")
        else:
            print("\n❌ 表现不佳，低于极简规则")
            print("   需要重新审视策略")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
