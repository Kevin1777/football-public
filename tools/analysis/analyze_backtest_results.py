"""
分析回测结果，找出优化方向
"""
import json
from pathlib import Path
from collections import defaultdict

def analyze_backtest():
    """分析回测结果"""
    
    # 读取最新的回测结果
    result_file = Path("backtest_详细结果_20251126_163109.json")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data['results']
    
    # 统计数据
    stats = {
        'total': len(results),
        'recommended': 0,
        'not_recommended': 0,
        'win': 0,
        'lose': 0,
        'half_win': 0,
        'half_lose': 0,
        'draw': 0,
        'by_confidence': defaultdict(lambda: {'total': 0, 'win': 0, 'lose': 0}),
        'by_direction': defaultdict(lambda: {'total': 0, 'win': 0, 'lose': 0}),
        'by_league': defaultdict(lambda: {'total': 0, 'win': 0, 'lose': 0}),
        'missed_opportunities': []  # 未推荐但本应赢的比赛
    }
    
    for result in results:
        validation = result.get('validation', {})
        recommendation = result.get('recommendation', {})
        match_info = result.get('match_info', {})
        
        if validation.get('recommended'):
            stats['recommended'] += 1
            result_type = validation.get('result', '')
            direction = recommendation.get('direction', 'none')
            confidence = recommendation.get('confidence', 0)
            league = match_info.get('league', '')
            
            # 按结果统计
            if result_type == 'WIN':
                stats['win'] += 1
                stats['by_direction'][direction]['win'] += 1
                stats['by_league'][league]['win'] += 1
            elif result_type == 'LOSE':
                stats['lose'] += 1
                stats['by_direction'][direction]['lose'] += 1
                stats['by_league'][league]['lose'] += 1
            elif result_type == 'HALF_WIN':
                stats['half_win'] += 1
            elif result_type == 'HALF_LOSE':
                stats['half_lose'] += 1
            elif result_type == 'DRAW':
                stats['draw'] += 1
            
            # 按置信度统计
            if confidence >= 0.90:
                conf_level = 'high'
            elif confidence >= 0.75:
                conf_level = 'mid'
            else:
                conf_level = 'low'
            
            stats['by_confidence'][conf_level]['total'] += 1
            if result_type in ['WIN', 'HALF_WIN']:
                stats['by_confidence'][conf_level]['win'] += 1
            elif result_type in ['LOSE', 'HALF_LOSE']:
                stats['by_confidence'][conf_level]['lose'] += 1
            
            stats['by_direction'][direction]['total'] += 1
            stats['by_league'][league]['total'] += 1
        else:
            stats['not_recommended'] += 1
            
            # 检查是否错过机会（未推荐但比赛很明显）
            actual_score = result.get('actual_score', [0, 0])
            if len(actual_score) == 2:
                home_score, away_score = actual_score
                score_diff = abs(home_score - away_score)
                
                # 如果比分差距≥2，说明比赛很明显，应该推荐
                if score_diff >= 2:
                    stats['missed_opportunities'].append({
                        'match': match_info.get('label', ''),
                        'score': f"{home_score}-{away_score}",
                        'reason': recommendation.get('reason', '')
                    })
    
    # 打印分析报告
    print("=" * 80)
    print("📊 回测结果深度分析")
    print("=" * 80)
    print()
    
    print(f"总比赛数: {stats['total']}")
    print(f"推荐场次: {stats['recommended']} ({stats['recommended']/stats['total']*100:.1f}%)")
    print(f"未推荐: {stats['not_recommended']} ({stats['not_recommended']/stats['total']*100:.1f}%)")
    print()
    
    print("📈 推荐结果:")
    total_profit = stats['win'] + stats['half_win']
    total_loss = stats['lose'] + stats['half_lose']
    win_rate = total_profit / stats['recommended'] * 100 if stats['recommended'] > 0 else 0
    print(f"   盈利场次: {total_profit} ({win_rate:.1f}%)")
    print(f"   - 全赢: {stats['win']}")
    print(f"   - 半赢: {stats['half_win']}")
    print(f"   亏损场次: {total_loss}")
    print(f"   - 全输: {stats['lose']}")
    print(f"   - 半输: {stats['half_lose']}")
    print(f"   走水: {stats['draw']}")
    print()
    
    print("🎯 按置信度统计:")
    for level in ['high', 'mid', 'low']:
        data = stats['by_confidence'][level]
        if data['total'] > 0:
            rate = data['win'] / data['total'] * 100
            print(f"   {level.upper()}: {data['win']}/{data['total']} = {rate:.1f}%")
    print()
    
    print("🏆 按方向统计:")
    for direction in ['home', 'away']:
        data = stats['by_direction'][direction]
        if data['total'] > 0:
            rate = data['win'] / data['total'] * 100
            print(f"   {direction}: {data['win']}/{data['total']} = {rate:.1f}%")
    print()
    
    print("🏅 按联赛统计（推荐场次≥10）:")
    league_list = [(league, data) for league, data in stats['by_league'].items() if data['total'] >= 10]
    league_list.sort(key=lambda x: x[1]['win']/x[1]['total'], reverse=True)
    
    for league, data in league_list[:10]:
        rate = data['win'] / data['total'] * 100
        print(f"   {league}: {data['win']}/{data['total']} = {rate:.1f}%")
    print()
    
    print(f"❌ 错过的机会（大比分未推荐）: {len(stats['missed_opportunities'])} 场")
    if stats['missed_opportunities']:
        print("   示例:")
        for missed in stats['missed_opportunities'][:5]:
            print(f"   - {missed['match']} ({missed['score']}) - {missed['reason']}")
    
    print()
    print("=" * 80)
    
    # 核心问题总结
    print()
    print("💡 优化建议:")
    print()
    
    # 1. 胜率问题
    if win_rate < 55:
        print("1. ⚠️  整体胜率偏低（<55%）")
        print("   建议：")
        print("   - 提高推荐阈值，减少低质量推荐")
        print("   - 加入更多风控指标")
        print()
    
    # 2. 置信度分布
    high_conf = stats['by_confidence']['high']
    if high_conf['total'] < stats['recommended'] * 0.3:
        print("2. ⚠️  高置信度推荐占比过低")
        print(f"   当前: {high_conf['total']}/{stats['recommended']} = {high_conf['total']/stats['recommended']*100:.1f}%")
        print("   建议：优化置信度计算公式，增加高置信度推荐")
        print()
    
    # 3. 错过机会
    if len(stats['missed_opportunities']) > 50:
        print(f"3. ⚠️  错过机会过多（{len(stats['missed_opportunities'])}场）")
        print("   建议：降低推荐阈值，捕获更多明显机会")
        print()
    
    # 4. 方向偏差
    home_data = stats['by_direction']['home']
    away_data = stats['by_direction']['away']
    if home_data['total'] > 0 and away_data['total'] > 0:
        home_rate = home_data['win'] / home_data['total']
        away_rate = away_data['win'] / away_data['total']
        if abs(home_rate - away_rate) > 0.1:
            print("4. ⚠️  主客队推荐胜率差异较大")
            print(f"   主队: {home_rate*100:.1f}%, 客队: {away_rate*100:.1f}%")
            print("   建议：针对性调整主客队推荐逻辑")
            print()
    
    print("=" * 80)


if __name__ == "__main__":
    analyze_backtest()
