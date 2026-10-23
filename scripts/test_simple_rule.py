"""
极简规则测试 - 验证数据质量

最简单的规则：
1. 大盘口（>1球）：支持受让方（冷门）
2. 小盘口（<0.5球）：支持让球方（热门）
3. 中盘口：观望

如果这个简单规则准确率>55%，说明数据正确
如果准确率≈50%，说明数据可能有问题
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))


def simple_rule_predict(handicap):
    """
    极简规则：
    - 大盘口（主队让>1球）：支持客队
    - 小盘口（主队让<0.5球）：支持主队
    - 中盘口：观望
    """
    if handicap < -1.0:
        return "客队赢盘"  # 主队让太多，支持客队
    elif handicap > 1.0:
        return "主队赢盘"  # 客队让太多，支持主队
    elif handicap < -0.25:
        return "主队赢盘"  # 主队小让，支持主队
    elif handicap > 0.25:
        return "客队赢盘"  # 客队小让，支持客队
    else:
        return None  # 平手或接近平手，观望


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        if json_file.stem.startswith(('2025-', '2024-')) and json_file.stem.count('_') >= 4:
            json_files.append(json_file)
    
    stats = {
        'total': 0,
        'correct': 0,
        'observed': 0,
        'by_handicap': {
            '大盘口(>1球)': {'total': 0, 'correct': 0},
            '小盘口(<0.5球)': {'total': 0, 'correct': 0},
            '中盘口': {'total': 0, 'correct': 0},
        }
    }
    
    examples = []
    
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
            
            # 获取盘口
            handicap_raw = data['handicap_data'].get('current_handicap', 0)
            handicap_str = data['handicap_data'].get('current_handicap_str', '')
            
            if handicap_raw != 0 and '受' not in handicap_str:
                handicap = -abs(handicap_raw)
            else:
                handicap = handicap_raw
            
            # 简单规则预测
            predicted = simple_rule_predict(handicap)
            
            if predicted is None:
                stats['observed'] += 1
                continue
            
            # 判断实际结果
            home_with_handicap = home_score + handicap
            if home_with_handicap > away_score:
                actual = "主队赢盘"
            elif home_with_handicap < away_score:
                actual = "客队赢盘"
            else:
                actual = "走盘"
            
            stats['total'] += 1
            is_correct = (predicted == actual)
            
            if is_correct:
                stats['correct'] += 1
            
            # 分类统计
            if abs(handicap) > 1.0:
                category = '大盘口(>1球)'
            elif abs(handicap) < 0.5:
                category = '小盘口(<0.5球)'
            else:
                category = '中盘口'
            
            stats['by_handicap'][category]['total'] += 1
            if is_correct:
                stats['by_handicap'][category]['correct'] += 1
            
            # 保存前10个案例
            if len(examples) < 10:
                examples.append({
                    'home': match_info['home'],
                    'away': match_info['away'],
                    'score': score,
                    'handicap': handicap,
                    'handicap_str': handicap_str,
                    'predicted': predicted,
                    'actual': actual,
                    'correct': is_correct
                })
            
        except Exception as e:
            continue
    
    # 输出结果
    print("\n" + "="*80)
    print("极简规则测试结果")
    print("="*80 + "\n")
    
    print("📊 整体统计\n")
    print(f"总比赛数: {stats['total']}")
    print(f"推荐正确: {stats['correct']}")
    print(f"观望: {stats['observed']}")
    print(f"准确率: {stats['correct']/stats['total']*100:.1f}%\n")
    
    print("="*80)
    print("📊 分类统计\n")
    
    for category, data in stats['by_handicap'].items():
        if data['total'] > 0:
            acc = data['correct'] / data['total'] * 100
            print(f"{category}: {data['correct']}/{data['total']} = {acc:.1f}%")
    
    print("\n" + "="*80)
    print("📋 案例样本（前10个）\n")
    
    for i, ex in enumerate(examples, 1):
        status = "✅" if ex['correct'] else "❌"
        print(f"{i}. {status} {ex['home']} vs {ex['away']}")
        print(f"   比分: {ex['score']}, 盘口: {ex['handicap_str']}({ex['handicap']})")
        print(f"   预测: {ex['predicted']}, 实际: {ex['actual']}\n")
    
    print("="*80)
    print("📈 结论\n")
    
    overall_acc = stats['correct']/stats['total']*100
    
    if overall_acc > 55:
        print("✅ 简单规则有效（>55%）")
        print("   说明：数据正确，可以继续优化模型")
    elif overall_acc > 48 and overall_acc < 52:
        print("❌ 简单规则无效（≈50%）")
        print("   说明：可能数据有问题，或者盘口理解错误")
    else:
        print("⚠️  简单规则略有效果")
        print("   说明：数据基本正确，需要更复杂的策略")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
