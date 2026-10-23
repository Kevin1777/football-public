"""
重新分析已有的回测结果文件
"""

import json
from pathlib import Path

def analyze_result(result_file: str):
    """分析回测结果文件"""
    
    print(f"\n📂 读取结果文件: {result_file}")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    
    total = len(results)
    success = sum(1 for r in results if r.get('success'))
    
    # 统计推荐情况
    recommended_count = 0
    win_count = 0
    half_win_count = 0
    half_lose_count = 0
    lose_count = 0
    total_profit = 0.0
    
    for result in results:
        if not result.get('success'):
            continue
            
        validation = result.get('validation', {})
        if validation.get('recommended'):
            recommended_count += 1
            result_type = validation.get('result', '')
            profit = validation.get('profit', 0.0)
            total_profit += profit
            
            # 根据result类型统计
            if result_type == 'WIN':
                win_count += 1
            elif result_type == 'HALF_WIN':
                half_win_count += 1
            elif result_type == 'HALF_LOSE':
                half_lose_count += 1
            elif result_type == 'LOSE':
                lose_count += 1
    
    # 盈利场次（全赢+半赢）
    profit_count = win_count + half_win_count
    # 亏损场次（全输+半输）
    loss_count = lose_count + half_lose_count
    # 盈利率
    profit_rate = (profit_count / recommended_count * 100) if recommended_count > 0 else 0
    
    print("\n" + "="*80)
    print("📊 回测统计结果")
    print("="*80)
    print(f"总比赛数: {total}")
    print(f"成功回测: {success}")
    print(f"\n推荐情况:")
    print(f"  发出推荐: {recommended_count} 场")
    print(f"  📈 盈利场次: {profit_count} 场 ({profit_rate:.2f}%)")
    print(f"     全赢: {win_count} 场")
    print(f"     半赢: {half_win_count} 场")
    print(f"  📉 亏损场次: {loss_count} 场")
    print(f"     全输: {lose_count} 场")
    print(f"     半输: {half_lose_count} 场")
    print(f"  💰 总盈亏: {total_profit:+.2f} 单位")
    print(f"  ⏸️  不推荐: {success - recommended_count} 场")
    print("="*80)
    
    # 分析推荐方向
    direction_stats = {}
    
    for result in results:
        if not result.get('success'):
            continue
            
        validation = result.get('validation', {})
        if not validation.get('recommended'):
            continue
            
        recommendation = result.get('recommendation', {})
        direction = recommendation.get('最终推荐', {}).get('direction', '未知')
        
        if direction not in direction_stats:
            direction_stats[direction] = {'total': 0, 'profit': 0, 'win': 0, 'lose': 0}
        
        direction_stats[direction]['total'] += 1
        profit = validation.get('profit', 0.0)
        direction_stats[direction]['profit'] += profit
        
        if profit > 0:
            direction_stats[direction]['win'] += 1
        elif profit < 0:
            direction_stats[direction]['lose'] += 1
    
    print("\n推荐方向统计:")
    for direction, stats in sorted(direction_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        if stats['total'] > 0:
            win_rate = stats['win'] / stats['total'] * 100
            avg_profit = stats['profit'] / stats['total']
            print(f"  {direction}: {stats['win']}/{stats['total']} 盈利 ({win_rate:.1f}%), 平均: {avg_profit:+.2f}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # 查找最新的回测结果文件
    result_files = list(Path('.').glob('backtest_详细结果_*.json'))
    
    if not result_files:
        print("❌ 未找到回测结果文件！")
    else:
        # 按修改时间排序，取最新的
        latest_file = max(result_files, key=lambda p: p.stat().st_mtime)
        analyze_result(str(latest_file))
