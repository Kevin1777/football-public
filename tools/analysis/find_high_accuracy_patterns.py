"""
分析回测数据，找出70%+准确率的特征组合
"""
import json
from pathlib import Path
from collections import defaultdict

def analyze_high_accuracy_patterns():
    """分析高准确率模式"""
    
    # 读取V3回测结果
    result_file = Path("backtest_详细结果_20251126_163803.json")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data['results']
    
    # 多维度统计
    patterns = {
        'by_pct_diff': defaultdict(lambda: {'total': 0, 'win': 0}),
        'by_volume': defaultdict(lambda: {'total': 0, 'win': 0}),
        'by_confidence': defaultdict(lambda: {'total': 0, 'win': 0}),
        'by_league': defaultdict(lambda: {'total': 0, 'win': 0}),
        'by_bf_support': defaultdict(lambda: {'total': 0, 'win': 0}),
        'combined': defaultdict(lambda: {'total': 0, 'win': 0, 'examples': []})
    }
    
    for result in results:
        validation = result.get('validation', {})
        recommendation = result.get('recommendation', {})
        match_info = result.get('match_info', {})
        
        if not validation.get('recommended'):
            continue
        
        result_type = validation.get('result', '')
        is_win = result_type in ['WIN', 'HALF_WIN']
        
        direction = recommendation.get('direction', 'none')
        confidence = recommendation.get('confidence', 0)
        reason = recommendation.get('reason', '')
        league = match_info.get('league', '')
        
        # 从reason中提取占比差
        pct_diff = 0
        if '优势' in reason:
            import re
            match = re.search(r'优势(\d+\.?\d*)%', reason)
            if match:
                pct_diff = float(match.group(1))
        
        # 统计：按占比差分组
        if pct_diff >= 50:
            pct_group = '50+'
        elif pct_diff >= 40:
            pct_group = '40-50'
        elif pct_diff >= 35:
            pct_group = '35-40'
        elif pct_diff >= 30:
            pct_group = '30-35'
        else:
            pct_group = '<30'
        
        patterns['by_pct_diff'][pct_group]['total'] += 1
        if is_win:
            patterns['by_pct_diff'][pct_group]['win'] += 1
        
        # 统计：按置信度分组
        if confidence >= 0.85:
            conf_group = '0.85+'
        elif confidence >= 0.80:
            conf_group = '0.80-0.85'
        elif confidence >= 0.75:
            conf_group = '0.75-0.80'
        else:
            conf_group = '<0.75'
        
        patterns['by_confidence'][conf_group]['total'] += 1
        if is_win:
            patterns['by_confidence'][conf_group]['win'] += 1
        
        # 统计：按联赛
        patterns['by_league'][league]['total'] += 1
        if is_win:
            patterns['by_league'][league]['win'] += 1
        
        # 组合条件：高占比差 + 高置信度
        if pct_diff >= 40 and confidence >= 0.80:
            key = 'pct40+_conf80+'
            patterns['combined'][key]['total'] += 1
            if is_win:
                patterns['combined'][key]['win'] += 1
            
            if len(patterns['combined'][key]['examples']) < 3:
                patterns['combined'][key]['examples'].append({
                    'match': match_info.get('label', ''),
                    'pct_diff': pct_diff,
                    'confidence': confidence,
                    'result': result_type
                })
        
        if pct_diff >= 45 and confidence >= 0.85:
            key = 'pct45+_conf85+'
            patterns['combined'][key]['total'] += 1
            if is_win:
                patterns['combined'][key]['win'] += 1
        
        if pct_diff >= 50:
            key = 'pct50+'
            patterns['combined'][key]['total'] += 1
            if is_win:
                patterns['combined'][key]['win'] += 1
    
    # 打印分析结果
    print("=" * 80)
    print("🎯 寻找70%+准确率的特征组合")
    print("=" * 80)
    print()
    
    print("📊 按占比差分组:")
    for group in ['50+', '40-50', '35-40', '30-35', '<30']:
        data = patterns['by_pct_diff'][group]
        if data['total'] > 0:
            rate = data['win'] / data['total'] * 100
            marker = '⭐' if rate >= 70 else '✅' if rate >= 60 else '  '
            print(f"  {marker} {group:10s}: {data['win']:3d}/{data['total']:3d} = {rate:5.1f}%")
    print()
    
    print("📊 按置信度分组:")
    for group in ['0.85+', '0.80-0.85', '0.75-0.80', '<0.75']:
        data = patterns['by_confidence'][group]
        if data['total'] > 0:
            rate = data['win'] / data['total'] * 100
            marker = '⭐' if rate >= 70 else '✅' if rate >= 60 else '  '
            print(f"  {marker} {group:10s}: {data['win']:3d}/{data['total']:3d} = {rate:5.1f}%")
    print()
    
    print("📊 按联赛分组（推荐≥10场）:")
    league_list = [(league, data) for league, data in patterns['by_league'].items() 
                   if data['total'] >= 10]
    league_list.sort(key=lambda x: x[1]['win']/x[1]['total'], reverse=True)
    
    for league, data in league_list[:15]:
        rate = data['win'] / data['total'] * 100
        marker = '⭐' if rate >= 70 else '✅' if rate >= 60 else '  '
        print(f"  {marker} {league:15s}: {data['win']:3d}/{data['total']:3d} = {rate:5.1f}%")
    print()
    
    print("🎯 组合条件（达到70%准确率）:")
    combined_list = [(key, data) for key, data in patterns['combined'].items()]
    combined_list.sort(key=lambda x: x[1]['win']/x[1]['total'] if x[1]['total'] > 0 else 0, 
                      reverse=True)
    
    for key, data in combined_list:
        if data['total'] > 0:
            rate = data['win'] / data['total'] * 100
            marker = '⭐⭐⭐' if rate >= 70 else '⭐⭐' if rate >= 65 else '⭐' if rate >= 60 else '  '
            print(f"  {marker} {key:20s}: {data['win']:3d}/{data['total']:3d} = {rate:5.1f}%")
            
            if data['examples']:
                print(f"      示例:")
                for ex in data['examples']:
                    print(f"      - {ex['match']} (占比{ex['pct_diff']:.1f}%, 置信{ex['confidence']:.2f}) -> {ex['result']}")
    
    print()
    print("=" * 80)
    print("💡 推荐策略（达到70%准确率）:")
    print()
    
    # 找出最佳组合
    best_combos = []
    for key, data in combined_list:
        if data['total'] >= 20:  # 至少20场样本
            rate = data['win'] / data['total'] * 100
            if rate >= 70:
                best_combos.append((key, data, rate))
    
    if best_combos:
        print("✅ 发现高准确率组合:")
        for key, data, rate in best_combos:
            print(f"   - {key}: {rate:.1f}% ({data['win']}/{data['total']})")
            print(f"     ROI: +{(data['win']*0.9 - (data['total']-data['win']))/data['total']*100:.1f}%")
    else:
        print("⚠️  需要更严格的条件才能达到70%")
        print()
        print("建议策略:")
        print("1. 占比差 ≥ 45%")
        print("2. 置信度 ≥ 0.85")
        print("3. 优先顶级联赛（英超、西甲、德甲）")
        print("4. 必发指数必须支持")
        print("5. 成交量 ≥ 150,000")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    analyze_high_accuracy_patterns()
