"""
对比平衡版和精选版
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def pf(v):
    if v is None or v == '':
        return None
    try:
        return float(str(v).replace(',', ''))
    except:
        return None


def load_data():
    data_dir = Path(__file__).parent.parent.parent / "data"
    results = []
    
    for y in data_dir.iterdir():
        if not y.is_dir() or not y.name.isdigit():
            continue
        for m in y.iterdir():
            if not m.is_dir():
                continue
            for d in m.iterdir():
                if not d.is_dir():
                    continue
                
                try:
                    date_str = f"{y.name}-{m.name}-{d.name}"
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    weekday = dt.weekday()
                    is_weekend = weekday >= 5
                except:
                    continue
                
                for f in d.glob("*.json"):
                    if any(x in f.name for x in ["大小球", "盘口数据", "标盘指数"]):
                        continue
                    try:
                        with open(f, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                        
                        mi = data.get('match_info', {})
                        td = data.get('trade_data', {})
                        score = mi.get('score')
                        if not score:
                            continue
                        
                        dl = td.get('data', [])
                        if not dl or len(dl) < 3:
                            continue
                        
                        L = dl[0]
                        
                        p = score.replace(' ', '').split('-')
                        h, a = int(p[0]), int(p[1])
                        actual = 'home' if h > a else 'away' if a > h else 'draw'
                        
                        s = {}
                        for k, n in [
                            ('凯利_主','kh'),('凯利_客','ka'),('凯利_和','kd'),
                            ('赢亏_主','yh'),('赢亏_客','ya'),
                            ('热指_主','rh'),('热指_客','ra'),
                        ]:
                            s[n] = pf(L.get(k))
                        
                        hv = pf(L.get('主胜_已成交量',0)) or 0
                        dv = pf(L.get('和局_已成交量',0)) or 0
                        av = pf(L.get('客胜_已成交量',0)) or 0
                        t = hv + dv + av
                        if t > 0:
                            s['dvp'] = dv/t*100
                        
                        s['oh'] = pf(L.get('主胜_欧赔'))
                        s['od'] = pf(L.get('和局_欧赔'))
                        s['oa'] = pf(L.get('客胜_欧赔'))
                        
                        results.append({
                            'actual': actual,
                            's': s,
                            'date': date_str,
                            'weekday': weekday,
                            'is_weekend': is_weekend,
                            'month': f"{y.name}-{m.name}",
                            'league': mi.get('league', ''),
                            'file': f.name
                        })
                    except:
                        pass
    return results


def simulate(matches, name, conds, direction, min_odds=0):
    BET = 100
    filtered = []
    
    for r in matches:
        s = r['s']
        
        # 检查条件
        ok = True
        for f, op, v in conds:
            x = s.get(f)
            if x is None:
                ok = False
                break
            if op == '>' and not x > v:
                ok = False
            elif op == '<' and not x < v:
                ok = False
        
        if not ok:
            continue
        
        if direction == 'draw':
            odds = s.get('od') or 0
        elif direction == 'home':
            odds = s.get('oh') or 0
        else:
            odds = s.get('oa') or 0
        
        if odds < min_odds:
            continue
        
        won = (r['actual'] == direction)
        filtered.append({
            'won': won,
            'odds': odds,
            'month': r['month'],
            'date': r['date'],
            'league': r['league'],
            'file': r['file']
        })
    
    if not filtered:
        return None
    
    # 总体统计
    wins = sum(1 for m in filtered if m['won'])
    investment = len(filtered) * BET
    returns = sum(BET * m['odds'] for m in filtered if m['won'])
    profit = returns - investment
    roi = profit / investment * 100 if investment > 0 else 0
    avg_odds = sum(m['odds'] for m in filtered) / len(filtered)
    
    # 按月统计
    monthly = defaultdict(lambda: {'bets': 0, 'wins': 0, 'profit': 0})
    for m in filtered:
        monthly[m['month']]['bets'] += 1
        if m['won']:
            monthly[m['month']]['wins'] += 1
            monthly[m['month']]['profit'] += BET * m['odds'] - BET
        else:
            monthly[m['month']]['profit'] -= BET
    
    return {
        'name': name,
        'count': len(filtered),
        'wins': wins,
        'win_rate': wins / len(filtered) * 100,
        'avg_odds': avg_odds,
        'investment': investment,
        'returns': returns,
        'profit': profit,
        'roi': roi,
        'monthly': dict(monthly),
        'matches': filtered
    }


def main():
    print("=" * 80)
    print("📊 平衡版 vs 精选版 详细对比")
    print("=" * 80)
    
    print("\n加载数据...")
    all_data = load_data()
    weekend = [r for r in all_data if r['is_weekend']]
    
    print(f"周末数据: {len(weekend)}场")
    
    # 定义两个方案
    plans = [
        ('平衡版', [('dvp', '>', 45), ('kd', '<', 96)], 'draw', 2.5),
        ('精选版', [('dvp', '>', 47), ('kd', '<', 96)], 'draw', 2.5),
    ]
    
    results = []
    for name, conds, direction, min_odds in plans:
        r = simulate(weekend, name, conds, direction, min_odds)
        if r:
            results.append(r)
    
    # ==================== 总体对比 ====================
    print("\n" + "=" * 80)
    print("【总体对比】")
    print("=" * 80)
    
    print(f"\n{'指标':<15} {'平衡版':<20} {'精选版':<20}")
    print("-" * 55)
    
    bal, sel = results[0], results[1]
    print(f"{'场次':<15} {bal['count']:<20} {sel['count']:<20}")
    print(f"{'命中':<15} {bal['wins']:<20} {sel['wins']:<20}")
    print(f"{'胜率':<15} {bal['win_rate']:.1f}%{'':<16} {sel['win_rate']:.1f}%")
    print(f"{'平均赔率':<15} {bal['avg_odds']:.2f}{'':<17} {sel['avg_odds']:.2f}")
    print(f"{'投入':<15} {bal['investment']:,}元{'':<14} {sel['investment']:,}元")
    print(f"{'回收':<15} {bal['returns']:,.0f}元{'':<12} {sel['returns']:,.0f}元")
    print(f"{'盈亏':<15} {bal['profit']:+,.0f}元{'':<12} {sel['profit']:+,.0f}元")
    print(f"{'ROI':<15} {bal['roi']:+.1f}%{'':<16} {sel['roi']:+.1f}%")
    
    # ==================== 按月对比 ====================
    print("\n" + "=" * 80)
    print("【按月收益对比】")
    print("=" * 80)
    
    all_months = sorted(set(list(bal['monthly'].keys()) + list(sel['monthly'].keys())))
    
    print(f"\n{'月份':<12} {'平衡版场次':<12} {'平衡版收益':<15} {'精选版场次':<12} {'精选版收益':<15}")
    print("-" * 70)
    
    for month in all_months:
        b = bal['monthly'].get(month, {'bets': 0, 'profit': 0})
        s = sel['monthly'].get(month, {'bets': 0, 'profit': 0})
        
        b_status = "✅" if b['profit'] > 0 else "❌" if b['profit'] < 0 else "⚪"
        s_status = "✅" if s['profit'] > 0 else "❌" if s['profit'] < 0 else "⚪"
        
        print(f"{month:<12} {b['bets']:<12} {b_status} {b['profit']:+,.0f}元{'':<8} {s['bets']:<12} {s_status} {s['profit']:+,.0f}元")
    
    # ==================== 每周末场次预估 ====================
    print("\n" + "=" * 80)
    print("【每周末场次预估】")
    print("=" * 80)
    
    # 统计周末天数
    weekend_days = len(set(r['date'] for r in weekend))
    
    print(f"\n数据跨度: {weekend_days}个周末天")
    print(f"平衡版: {bal['count']}场 / {weekend_days}天 = {bal['count']/weekend_days:.1f}场/天")
    print(f"精选版: {sel['count']}场 / {weekend_days}天 = {sel['count']/weekend_days:.1f}场/天")
    
    print(f"\n每周末（2天）预估:")
    print(f"  平衡版: ~{bal['count']/weekend_days*2:.0f}场")
    print(f"  精选版: ~{sel['count']/weekend_days*2:.0f}场")
    
    # ==================== 收益模拟 ====================
    print("\n" + "=" * 80)
    print("【不同注码收益模拟】")
    print("=" * 80)
    
    print(f"\n{'单注金额':<12} {'平衡版月盈利':<18} {'精选版月盈利':<18}")
    print("-" * 50)
    
    months_count = len(all_months)
    for bet in [100, 200, 500, 1000]:
        b_monthly = bal['profit'] / months_count * (bet / 100)
        s_monthly = sel['profit'] / months_count * (bet / 100)
        print(f"{bet}元{'':<8} {b_monthly:+,.0f}元/月{'':<8} {s_monthly:+,.0f}元/月")
    
    # ==================== 赔率分布 ====================
    print("\n" + "=" * 80)
    print("【赔率分布对比】")
    print("=" * 80)
    
    for r in results:
        print(f"\n{r['name']}:")
        odds_dist = {'2.5-3.0': 0, '3.0-3.5': 0, '3.5-4.0': 0, '4.0+': 0}
        for m in r['matches']:
            if m['odds'] < 3.0:
                odds_dist['2.5-3.0'] += 1
            elif m['odds'] < 3.5:
                odds_dist['3.0-3.5'] += 1
            elif m['odds'] < 4.0:
                odds_dist['3.5-4.0'] += 1
            else:
                odds_dist['4.0+'] += 1
        
        for rng, cnt in odds_dist.items():
            pct = cnt / r['count'] * 100
            bar = '█' * int(pct / 3)
            print(f"  {rng}: {cnt:3d}场 ({pct:5.1f}%) {bar}")
    
    # ==================== 最近比赛示例 ====================
    print("\n" + "=" * 80)
    print("【最近命中示例（精选版）】")
    print("=" * 80)
    
    recent_wins = [m for m in sel['matches'] if m['won']][-10:]
    for m in recent_wins:
        print(f"  ✅ {m['date']} | 赔率{m['odds']:.2f} | {m['file'][:40]}...")
    
    # ==================== 建议 ====================
    print("\n" + "=" * 80)
    print("💡 建议")
    print("=" * 80)
    
    print(f"""
【平衡版】和量>45%+和凯利<96
  - 场次更多: {bal['count']}场
  - ROI: {bal['roi']:+.1f}%
  - 适合：想要更多投注机会

【精选版】和量>47%+和凯利<96  
  - 场次较少: {sel['count']}场
  - ROI: {sel['roi']:+.1f}% ⭐更高
  - 适合：追求更高收益率

【组合建议】
  - 精选版信号出现时：单注可以加大
  - 平衡版额外信号（精选版没有的）：单注可以减小
""")


if __name__ == "__main__":
    main()
