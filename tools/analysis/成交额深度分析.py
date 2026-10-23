"""
成交额深度分析 - 找出最佳成交额阈值
"""

import json
from pathlib import Path
from collections import defaultdict

def load_v3_results():
    """加载V3结果（有完整成交量数据）"""
    result_file = Path('backtest_详细结果_20251123_131959.json')
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_volume_features(result):
    """提取成交额特征"""
    if not result.get('success'):
        return None
    
    validation = result.get('validation', {})
    if not validation.get('recommended'):
        return None
    
    recommendation = result.get('recommendation', {})
    match_info = result.get('match_info', {})
    
    # 从数据中提取成交量信息
    trade_data_rows = result.get('trade_data_rows', 0)
    
    # 解析盘口
    handicap_data = result.get('handicap_data', {})
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
    
    # 趋势
    if abs(handicap_change) < 0.01:
        trend = '稳盘'
    elif handicap_change < -0.5:
        trend = '中大升'
    elif handicap_change < 0:
        trend = '小升'
    else:
        trend = '降盘'
    
    # 方向
    is_home = '主队' in recommendation.get('direction', '')
    
    # 结果
    profit = validation.get('profit', 0.0)
    is_profit = profit > 0
    
    # 置信度
    confidence = recommendation.get('confidence', 0)
    
    return {
        'trade_data_rows': trade_data_rows,
        'handicap_change': handicap_change,
        'trend': trend,
        'is_home': is_home,
        'confidence': confidence,
        'profit': profit,
        'is_profit': is_profit,
        'league': match_info.get('league', ''),
    }


def analyze_by_volume_threshold(features_list):
    """按成交数据量阈值分析"""
    
    print("\n" + "="*80)
    print("📊 按成交数据量（行数）分析准确率")
    print("="*80)
    
    thresholds = [10, 20, 30, 40, 50, 75, 100, 150, 200, 250, 300]
    
    print(f"\n{'阈值（行）':>12} {'样本数':>8} {'盈利场次':>10} {'准确率':>10} {'平均盈利':>12} {'总盈利':>10}")
    print("-" * 80)
    
    best_threshold = None
    best_win_rate = 0
    
    for threshold in thresholds:
        filtered = [f for f in features_list if f['trade_data_rows'] >= threshold]
        
        if len(filtered) < 10:  # 至少10场样本
            continue
        
        win_count = sum(1 for f in filtered if f['is_profit'])
        win_rate = win_count / len(filtered)
        avg_profit = sum(f['profit'] for f in filtered) / len(filtered)
        total_profit = sum(f['profit'] for f in filtered)
        
        symbol = "💎" if win_rate >= 0.70 else ("⭐" if win_rate >= 0.65 else ("✅" if win_rate >= 0.60 else ""))
        
        print(f"{symbol} ≥{threshold:3d}行 {len(filtered):>8}场 {win_count:>4}/{len(filtered):<4} {win_rate*100:>9.1f}% {avg_profit:>+12.3f} {total_profit:>+10.2f}")
        
        if win_rate > best_win_rate and len(filtered) >= 20:
            best_win_rate = win_rate
            best_threshold = threshold
    
    print(f"\n💡 最佳阈值: ≥{best_threshold}行 (准确率{best_win_rate*100:.1f}%)")
    
    return best_threshold


def analyze_volume_with_trend(features_list, volume_threshold):
    """结合成交额和趋势分析"""
    
    print("\n" + "="*80)
    print(f"🔬 成交额（≥{volume_threshold}行）+ 趋势组合分析")
    print("="*80)
    
    # 过滤高成交额
    high_volume = [f for f in features_list if f['trade_data_rows'] >= volume_threshold]
    
    print(f"\n过滤后样本: {len(high_volume)}/224场")
    
    # 按趋势分析
    trends = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in high_volume:
        key = f['trend']
        trends[key]['total'] += 1
        trends[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            trends[key]['profit'] += 1
    
    print(f"\n{'趋势':15} {'样本数':>8} {'准确率':>10} {'平均盈利':>12}")
    print("-" * 60)
    
    for trend in ['中大升', '小升', '稳盘', '降盘']:
        if trend in trends:
            s = trends[trend]
            win_rate = s['profit'] / s['total']
            avg_profit = s['profit_sum'] / s['total']
            
            symbol = "💎" if win_rate >= 0.70 else ("⭐" if win_rate >= 0.65 else "✅")
            print(f"{symbol} {trend:15} {s['total']:>8}场 {win_rate*100:>9.1f}% {avg_profit:>+12.3f}")


def analyze_volume_with_direction(features_list, volume_threshold):
    """结合成交额和方向分析"""
    
    print("\n" + "="*80)
    print(f"🔬 成交额（≥{volume_threshold}行）+ 方向组合分析")
    print("="*80)
    
    # 过滤高成交额
    high_volume = [f for f in features_list if f['trade_data_rows'] >= volume_threshold]
    
    # 按方向分析
    directions = defaultdict(lambda: {'total': 0, 'profit': 0, 'profit_sum': 0.0})
    
    for f in high_volume:
        key = '主队' if f['is_home'] else '客队'
        directions[key]['total'] += 1
        directions[key]['profit_sum'] += f['profit']
        if f['is_profit']:
            directions[key]['profit'] += 1
    
    print(f"\n{'方向':10} {'样本数':>8} {'准确率':>10} {'平均盈利':>12}")
    print("-" * 50)
    
    for direction in ['主队', '客队']:
        if direction in directions:
            s = directions[direction]
            win_rate = s['profit'] / s['total']
            avg_profit = s['profit_sum'] / s['total']
            
            symbol = "💎" if win_rate >= 0.70 else ("⭐" if win_rate >= 0.65 else "✅")
            print(f"{symbol} {direction:10} {s['total']:>8}场 {win_rate*100:>9.1f}% {avg_profit:>+12.3f}")


def test_optimal_strategy(features_list, volume_threshold):
    """测试最优策略"""
    
    print("\n" + "="*80)
    print("🎯 V5策略测试：成交额预筛选 + 精准特征")
    print("="*80)
    
    # 策略1: 成交额 + 中大升 + 主队
    filtered = [f for f in features_list if 
                f['trade_data_rows'] >= volume_threshold and
                f['trend'] == '中大升' and
                f['is_home']]
    
    if len(filtered) >= 5:
        win_rate = sum(1 for f in filtered if f['is_profit']) / len(filtered)
        avg_profit = sum(f['profit'] for f in filtered) / len(filtered)
        total_profit = sum(f['profit'] for f in filtered)
        
        print(f"\n策略1: 高成交额(≥{volume_threshold}行) + 中大升 + 主队")
        print(f"  样本数: {len(filtered)}场")
        print(f"  准确率: {win_rate*100:.1f}%")
        print(f"  平均盈利: {avg_profit:+.3f}")
        print(f"  总盈利: {total_profit:+.2f}")
        print(f"  推荐率: {len(filtered)/224*100:.1f}%")
    
    # 策略2: 成交额 + (中大升 OR 稳盘) + 主队 + 高置信度
    filtered = [f for f in features_list if 
                f['trade_data_rows'] >= volume_threshold and
                f['trend'] in ['中大升', '稳盘'] and
                f['is_home'] and
                f['confidence'] >= 0.70]
    
    if len(filtered) >= 5:
        win_rate = sum(1 for f in filtered if f['is_profit']) / len(filtered)
        avg_profit = sum(f['profit'] for f in filtered) / len(filtered)
        total_profit = sum(f['profit'] for f in filtered)
        
        print(f"\n策略2: 高成交额 + 中大升/稳盘 + 主队 + 高置信度(≥70%)")
        print(f"  样本数: {len(filtered)}场")
        print(f"  准确率: {win_rate*100:.1f}%")
        print(f"  平均盈利: {avg_profit:+.3f}")
        print(f"  总盈利: {total_profit:+.2f}")
        print(f"  推荐率: {len(filtered)/224*100:.1f}%")
    
    # 策略3: 成交额 + 任意升盘 + 主队 + 超高置信度
    filtered = [f for f in features_list if 
                f['trade_data_rows'] >= volume_threshold and
                f['trend'] in ['中大升', '小升'] and
                f['is_home'] and
                f['confidence'] >= 0.75]
    
    if len(filtered) >= 5:
        win_rate = sum(1 for f in filtered if f['is_profit']) / len(filtered)
        avg_profit = sum(f['profit'] for f in filtered) / len(filtered)
        total_profit = sum(f['profit'] for f in filtered)
        
        print(f"\n策略3: 高成交额 + 升盘 + 主队 + 超高置信度(≥75%)")
        print(f"  样本数: {len(filtered)}场")
        print(f"  准确率: {win_rate*100:.1f}%")
        print(f"  平均盈利: {avg_profit:+.3f}")
        print(f"  总盈利: {total_profit:+.2f}")
        print(f"  推荐率: {len(filtered)/224*100:.1f}%")


def analyze_low_volume_risks(features_list):
    """分析低成交额的风险"""
    
    print("\n" + "="*80)
    print("⚠️  低成交额风险分析")
    print("="*80)
    
    thresholds = [
        ('极低（<50行）', 0, 50),
        ('低（50-100行）', 50, 100),
        ('中（100-150行）', 100, 150),
        ('高（150行+）', 150, 1000),
    ]
    
    print(f"\n{'成交额区间':20} {'样本数':>8} {'准确率':>10} {'平均盈利':>12}")
    print("-" * 60)
    
    for name, min_v, max_v in thresholds:
        filtered = [f for f in features_list if min_v <= f['trade_data_rows'] < max_v]
        
        if len(filtered) > 0:
            win_rate = sum(1 for f in filtered if f['is_profit']) / len(filtered)
            avg_profit = sum(f['profit'] for f in filtered) / len(filtered)
            
            symbol = "❌" if win_rate < 0.55 else ("⚠️" if win_rate < 0.60 else "✅")
            print(f"{symbol} {name:20} {len(filtered):>8}场 {win_rate*100:>9.1f}% {avg_profit:>+12.3f}")


def main():
    """主函数"""
    
    print("\n" + "="*80)
    print("📊 成交额深度分析")
    print("="*80)
    
    data = load_v3_results()
    results = data.get('results', [])
    
    # 提取特征
    features_list = []
    for result in results:
        features = extract_volume_features(result)
        if features:
            features_list.append(features)
    
    print(f"\n分析 {len(features_list)} 场V3推荐")
    
    # 分析成交额分布
    volumes = [f['trade_data_rows'] for f in features_list]
    print(f"\n成交数据行数统计:")
    print(f"  最小: {min(volumes)}行")
    print(f"  最大: {max(volumes)}行")
    print(f"  平均: {sum(volumes)/len(volumes):.0f}行")
    print(f"  中位数: {sorted(volumes)[len(volumes)//2]}行")
    
    # 执行分析
    best_threshold = analyze_by_volume_threshold(features_list)
    analyze_volume_with_trend(features_list, best_threshold)
    analyze_volume_with_direction(features_list, best_threshold)
    test_optimal_strategy(features_list, best_threshold)
    analyze_low_volume_risks(features_list)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
