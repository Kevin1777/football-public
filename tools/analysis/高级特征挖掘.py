"""
高级特征挖掘 - 深度分析211场推荐的细节
找出最有价值的组合特征
"""

import json
from pathlib import Path
from collections import defaultdict
import numpy as np

def load_v2_results():
    """加载V2优化引擎的回测结果"""
    result_file = Path('backtest_详细结果_20251123_131153.json')
    
    if not result_file.exists():
        print("❌ 未找到V2结果文件！")
        return None
    
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_features(result):
    """提取单场比赛的所有特征"""
    if not result.get('success'):
        return None
    
    validation = result.get('validation', {})
    if not validation.get('recommended'):
        return None
    
    recommendation = result.get('recommendation', {})
    match_info = result.get('match_info', {})
    handicap_data = result.get('handicap_data', {})
    
    # 解析盘口
    initial_str = handicap_data.get('initial', 'None (0)')
    current_str = handicap_data.get('current', 'None (0)')
    
    try:
        initial_handicap = float(initial_str.split('(')[1].split(')')[0])
    except:
        initial_handicap = 0
    
    try:
        current_handicap = float(current_str.split('(')[1].split(')')[0])
    except:
        current_handicap = 0
    
    handicap_change = current_handicap - initial_handicap
    
    # 判断盘口趋势
    if abs(handicap_change) < 0.01:
        trend = '稳盘'
    elif handicap_change < 0:
        trend = '升盘'
    else:
        trend = '降盘'
    
    # 判断盘口大小
    abs_handicap = abs(current_handicap)
    if abs_handicap == 0:
        size = '平手'
    elif abs_handicap <= 0.5:
        size = '小盘(<0.5)'
    elif abs_handicap <= 0.75:
        size = '小盘(0.5-0.75)'
    elif abs_handicap <= 1.25:
        size = '中盘(1-1.25)'
    elif abs_handicap <= 1.75:
        size = '中盘(1.5-1.75)'
    elif abs_handicap <= 2.5:
        size = '大盘(2-2.5)'
    else:
        size = '大盘(2.5+)'
    
    # 推荐方向
    direction = recommendation.get('direction', '')
    is_home = '主队' in direction
    is_away = '客队' in direction
    
    # 比赛结果
    actual_score = result.get('actual_score', [0, 0])
    home_score = actual_score[0] if len(actual_score) > 0 else 0
    away_score = actual_score[1] if len(actual_score) > 1 else 0
    goal_diff = home_score - away_score
    total_goals = home_score + away_score
    
    # 盈利情况
    profit = validation.get('profit', 0.0)
    result_type = validation.get('result', '')
    is_profit = profit > 0
    
    # 置信度
    confidence = recommendation.get('confidence', 0)
    
    # 联赛
    league = match_info.get('league', '')
    
    return {
        'initial_handicap': initial_handicap,
        'current_handicap': current_handicap,
        'handicap_change': handicap_change,
        'abs_handicap': abs_handicap,
        'trend': trend,
        'size': size,
        'direction': direction,
        'is_home': is_home,
        'is_away': is_away,
        'home_score': home_score,
        'away_score': away_score,
        'goal_diff': goal_diff,
        'total_goals': total_goals,
        'profit': profit,
        'result_type': result_type,
        'is_profit': is_profit,
        'confidence': confidence,
        'league': league,
    }


def analyze_handicap_change_precision(features_list):
    """精确分析盘口变化幅度"""
    
    print("\n" + "="*80)
    print("📊 盘口变化幅度精确分析")
    print("="*80)
    
    # 按盘口变化幅度分组
    ranges = {
        '稳盘(-0.01~+0.01)': (-0.01, 0.01),
        '微升(-0.25~-0.01)': (-0.25, -0.01),
        '小升(-0.5~-0.25)': (-0.5, -0.25),
        '中升(-0.75~-0.5)': (-0.75, -0.5),
        '大升(<-0.75)': (-10, -0.75),
        '微降(+0.01~+0.25)': (0.01, 0.25),
        '小降(+0.25~+0.5)': (0.25, 0.5),
        '中降(+0.5~+0.75)': (0.5, 0.75),
        '大降(>+0.75)': (0.75, 10),
    }
    
    stats = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        change = f['handicap_change']
        for range_name, (min_c, max_c) in ranges.items():
            if min_c < change <= max_c:
                stats[range_name]['total'] += 1
                stats[range_name]['profit_sum'] += f['profit']
                if f['is_profit']:
                    stats[range_name]['profit'] += 1
                break
    
    # 排序输出
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['profit_sum'] / x[1]['total'] if x[1]['total'] > 0 else 0, reverse=True)
    
    for range_name, s in sorted_stats:
        if s['total'] >= 3:  # 至少3场样本
            win_rate = s['profit'] / s['total'] * 100
            avg_profit = s['profit_sum'] / s['total']
            print(f"{range_name:20} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  平均: {avg_profit:+.3f}")


def analyze_goal_patterns(features_list):
    """分析进球模式"""
    
    print("\n" + "="*80)
    print("⚽ 进球模式分析")
    print("="*80)
    
    # 总进球数
    print("\n总进球数:")
    goal_stats = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        total = f['total_goals']
        if total <= 1:
            key = '低进球(0-1)'
        elif total <= 2:
            key = '中进球(2)'
        elif total <= 3:
            key = '中进球(3)'
        else:
            key = '高进球(4+)'
        
        goal_stats[key]['total'] += 1
        goal_stats[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            goal_stats[key]['profit'] += 1
    
    for key in ['低进球(0-1)', '中进球(2)', '中进球(3)', '高进球(4+)']:
        s = goal_stats[key]
        if s['total'] > 0:
            win_rate = s['profit'] / s['total'] * 100
            avg_profit = s['profit_sum'] / s['total']
            print(f"  {key:15} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  平均: {avg_profit:+.3f}")
    
    # 分差
    print("\n比分分差:")
    diff_stats = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        diff = abs(f['goal_diff'])
        if diff == 0:
            key = '平局'
        elif diff == 1:
            key = '1球分差'
        elif diff == 2:
            key = '2球分差'
        else:
            key = '3+球分差'
        
        diff_stats[key]['total'] += 1
        diff_stats[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            diff_stats[key]['profit'] += 1
    
    for key in ['平局', '1球分差', '2球分差', '3+球分差']:
        s = diff_stats[key]
        if s['total'] > 0:
            win_rate = s['profit'] / s['total'] * 100
            avg_profit = s['profit_sum'] / s['total']
            print(f"  {key:15} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  平均: {avg_profit:+.3f}")


def analyze_confidence_bands(features_list):
    """分析置信度区间"""
    
    print("\n" + "="*80)
    print("📈 置信度精细分区")
    print("="*80)
    
    bands = {
        '40-45%': (0.4, 0.45),
        '45-50%': (0.45, 0.5),
        '50-55%': (0.5, 0.55),
        '55-60%': (0.55, 0.6),
        '60-65%': (0.6, 0.65),
        '65-70%': (0.65, 0.7),
        '70-75%': (0.7, 0.75),
        '75-80%': (0.75, 0.8),
        '80%+': (0.8, 1.0),
    }
    
    stats = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        conf = f['confidence']
        for band_name, (min_c, max_c) in bands.items():
            if min_c <= conf < max_c:
                stats[band_name]['total'] += 1
                stats[band_name]['profit_sum'] += f['profit']
                if f['is_profit']:
                    stats[band_name]['profit'] += 1
                break
    
    for band in ['40-45%', '45-50%', '50-55%', '55-60%', '60-65%', '65-70%', '70-75%', '75-80%', '80%+']:
        s = stats[band]
        if s['total'] > 0:
            win_rate = s['profit'] / s['total'] * 100
            avg_profit = s['profit_sum'] / s['total']
            print(f"{band:10} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  平均: {avg_profit:+.3f}")


def find_golden_combinations(features_list):
    """寻找黄金组合"""
    
    print("\n" + "="*80)
    print("💎 黄金组合特征（盈利率>70%）")
    print("="*80)
    
    # 组合1: 盘口大小 + 趋势
    print("\n1️⃣ 盘口大小 × 趋势:")
    combo1 = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        key = f"{f['size']} + {f['trend']}"
        combo1[key]['total'] += 1
        combo1[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            combo1[key]['profit'] += 1
    
    # 排序并输出高胜率组合
    sorted_combo1 = sorted(combo1.items(), key=lambda x: x[1]['profit'] / x[1]['total'] if x[1]['total'] >= 5 else 0, reverse=True)
    
    for key, s in sorted_combo1[:10]:  # 前10
        if s['total'] >= 5:
            win_rate = s['profit'] / s['total'] * 100
            if win_rate >= 65:  # 只显示65%+
                avg_profit = s['profit_sum'] / s['total']
                print(f"  {key:40} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  {avg_profit:+.3f}")
    
    # 组合2: 盘口大小 + 方向
    print("\n2️⃣ 盘口大小 × 方向:")
    combo2 = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        direction_type = '主队' if f['is_home'] else '客队'
        key = f"{f['size']} + {direction_type}"
        combo2[key]['total'] += 1
        combo2[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            combo2[key]['profit'] += 1
    
    sorted_combo2 = sorted(combo2.items(), key=lambda x: x[1]['profit'] / x[1]['total'] if x[1]['total'] >= 5 else 0, reverse=True)
    
    for key, s in sorted_combo2[:10]:
        if s['total'] >= 5:
            win_rate = s['profit'] / s['total'] * 100
            if win_rate >= 65:
                avg_profit = s['profit_sum'] / s['total']
                print(f"  {key:40} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  {avg_profit:+.3f}")
    
    # 组合3: 趋势 + 方向
    print("\n3️⃣ 趋势 × 方向:")
    combo3 = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        direction_type = '主队' if f['is_home'] else '客队'
        key = f"{f['trend']} + {direction_type}"
        combo3[key]['total'] += 1
        combo3[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            combo3[key]['profit'] += 1
    
    sorted_combo3 = sorted(combo3.items(), key=lambda x: x[1]['profit'] / x[1]['total'] if x[1]['total'] >= 5 else 0, reverse=True)
    
    for key, s in sorted_combo3:
        if s['total'] >= 5:
            win_rate = s['profit'] / s['total'] * 100
            if win_rate >= 60:
                avg_profit = s['profit_sum'] / s['total']
                print(f"  {key:40} {s['profit']:3}/{s['total']:3} ({win_rate:5.1f}%)  {avg_profit:+.3f}")


def find_failure_patterns(features_list):
    """找出失败模式"""
    
    print("\n" + "="*80)
    print("⚠️  高风险模式（需要避开）")
    print("="*80)
    
    # 找出盈利率<40%的组合
    combo = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in features_list:
        direction_type = '主队' if f['is_home'] else '客队'
        key = f"{f['size']} + {f['trend']} + {direction_type}"
        combo[key]['total'] += 1
        combo[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            combo[key]['profit'] += 1
    
    # 找出低胜率模式
    bad_patterns = []
    for key, s in combo.items():
        if s['total'] >= 5:
            win_rate = s['profit'] / s['total'] * 100
            if win_rate < 40:
                avg_profit = s['profit_sum'] / s['total']
                bad_patterns.append((key, s, win_rate, avg_profit))
    
    bad_patterns.sort(key=lambda x: x[2])
    
    for key, s, win_rate, avg_profit in bad_patterns[:10]:
        print(f"  {key:50} {s['profit']:2}/{s['total']:2} ({win_rate:5.1f}%)  {avg_profit:+.3f}")


def main():
    """主函数"""
    
    print("\n" + "="*80)
    print("🔍 高级特征挖掘 - V2优化引擎深度分析")
    print("="*80)
    
    data = load_v2_results()
    if not data:
        return
    
    results = data.get('results', [])
    
    # 提取所有推荐的特征
    features_list = []
    for result in results:
        features = extract_features(result)
        if features:
            features_list.append(features)
    
    print(f"\n提取了 {len(features_list)} 场推荐的特征")
    print(f"总盈利场次: {sum(1 for f in features_list if f['is_profit'])}")
    print(f"总盈利金额: {sum(f['profit'] for f in features_list):+.2f}")
    
    # 执行各种分析
    analyze_handicap_change_precision(features_list)
    analyze_goal_patterns(features_list)
    analyze_confidence_bands(features_list)
    find_golden_combinations(features_list)
    find_failure_patterns(features_list)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
