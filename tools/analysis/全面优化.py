"""
全面优化 - 探索胜负平三个方向的更多优化空间
使用全部周末历史数据
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


def load_weekend_data():
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
                    if weekday < 5:
                        continue
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
                            ('凯差_主','ch'),('凯差_客','ca'),
                            ('赢亏_主','yh'),('赢亏_客','ya'),
                            ('热指_主','rh'),('热指_客','ra'),
                            ('必指_主','bh'),('必指_客','ba'),('必指_和','bd'),
                        ]:
                            s[n] = pf(L.get(k))
                        
                        hv = pf(L.get('主胜_已成交量',0)) or 0
                        dv = pf(L.get('和局_已成交量',0)) or 0
                        av = pf(L.get('客胜_已成交量',0)) or 0
                        t = hv + dv + av
                        if t > 0:
                            s['hvp'] = hv/t*100
                            s['dvp'] = dv/t*100
                            s['avp'] = av/t*100
                        
                        s['tv'] = pf(L.get('总成交量')) or 0
                        s['oh'] = pf(L.get('主胜_欧赔'))
                        s['od'] = pf(L.get('和局_欧赔'))
                        s['oa'] = pf(L.get('客胜_欧赔'))
                        
                        results.append({
                            'actual': actual,
                            's': s,
                            'date': date_str,
                            'month': f"{y.name}-{m.name}"
                        })
                    except:
                        pass
    return results


def check(s, conds):
    for f, op, v in conds:
        x = s.get(f)
        if x is None:
            return False
        if op == '>' and not x > v:
            return False
        elif op == '<' and not x < v:
            return False
        elif op == '>=' and not x >= v:
            return False
        elif op == '<=' and not x <= v:
            return False
    return True


def test_signal(matches, conds, direction, min_odds=0):
    BET = 100
    filtered = []
    
    for r in matches:
        s = r['s']
        if not check(s, conds):
            continue
        
        if direction == 'home':
            odds = s.get('oh') or 0
        elif direction == 'away':
            odds = s.get('oa') or 0
        else:
            odds = s.get('od') or 0
        
        if odds < min_odds:
            continue
        
        won = (r['actual'] == direction)
        filtered.append({'won': won, 'odds': odds, 'month': r['month']})
    
    if len(filtered) < 15:
        return None
    
    wins = sum(1 for m in filtered if m['won'])
    investment = len(filtered) * BET
    returns = sum(BET * m['odds'] for m in filtered if m['won'])
    profit = returns - investment
    roi = profit / investment * 100
    avg_odds = sum(m['odds'] for m in filtered) / len(filtered)
    
    # 按月统计稳定性
    monthly = defaultdict(lambda: {'profit': 0})
    for m in filtered:
        if m['won']:
            monthly[m['month']]['profit'] += BET * m['odds'] - BET
        else:
            monthly[m['month']]['profit'] -= BET
    
    pos_months = sum(1 for v in monthly.values() if v['profit'] > 0)
    total_months = len(monthly)
    stability = pos_months / total_months * 100 if total_months > 0 else 0
    
    return {
        'count': len(filtered),
        'wins': wins,
        'win_rate': wins / len(filtered) * 100,
        'avg_odds': avg_odds,
        'profit': profit,
        'roi': roi,
        'stability': stability
    }


def main():
    print("=" * 80)
    print("📊 全面优化探索 - 胜负平三个方向")
    print("=" * 80)
    
    print("\n加载周末数据...")
    data = load_weekend_data()
    print(f"周末总场次: {len(data)}")
    
    # ==================== 平局优化 ====================
    print("\n" + "=" * 80)
    print("🎯 平局信号优化")
    print("=" * 80)
    
    print("\n当前最优: 和量>47%+凯利<96 → ROI +26.9%")
    print("\n【探索更多组合】")
    
    draw_results = []
    
    # 探索不同阈值组合
    for dvp in [44, 45, 46, 47, 48, 50]:
        for kd in [90, 92, 94, 96]:
            conds = [('dvp', '>', dvp), ('kd', '<', kd)]
            r = test_signal(data, conds, 'draw', 2.5)
            if r and r['roi'] > 15 and r['stability'] >= 60:
                draw_results.append((f'和量>{dvp}%+凯利<{kd}', r))
    
    # 加入必指
    for dvp in [44, 46, 48]:
        for bd in [28, 30, 32]:
            conds = [('dvp', '>', dvp), ('bd', '>', bd)]
            r = test_signal(data, conds, 'draw', 2.5)
            if r and r['roi'] > 15 and r['stability'] >= 60:
                draw_results.append((f'和量>{dvp}%+必指>{bd}', r))
    
    # 三条件组合
    for dvp in [45, 47]:
        for kd in [94, 96]:
            for bd in [28, 30]:
                conds = [('dvp', '>', dvp), ('kd', '<', kd), ('bd', '>', bd)]
                r = test_signal(data, conds, 'draw', 2.5)
                if r and r['roi'] > 20 and r['stability'] >= 60:
                    draw_results.append((f'和量>{dvp}%+凯利<{kd}+必指>{bd}', r))
    
    draw_results.sort(key=lambda x: -x[1]['roi'])
    print(f"\n{'条件':<30} {'场次':<8} {'胜率':<8} {'ROI':<10} {'稳定性':<10}")
    print("-" * 70)
    for desc, r in draw_results[:10]:
        print(f"{desc:<30} {r['count']:<8} {r['win_rate']:.1f}%{'':<3} {r['roi']:+.1f}%{'':<4} {r['stability']:.0f}%月盈利")
    
    # ==================== 主胜优化 ====================
    print("\n" + "=" * 80)
    print("🏠 主胜信号优化")
    print("=" * 80)
    
    print("\n当前: 赔率>2.0+客热>20+怕客<-10")
    print("\n【探索更多组合】")
    
    home_results = []
    
    # 基础组合
    for ra in [18, 20, 22, 24]:
        for ya in [-5, -10, -15, -20]:
            conds = [('ra', '>', ra), ('ya', '<', ya)]
            for min_odds in [1.8, 2.0, 2.2]:
                r = test_signal(data, conds, 'home', min_odds)
                if r and r['roi'] > 5 and r['stability'] >= 50:
                    home_results.append((f'赔率>{min_odds}+客热>{ra}+怕客<{ya}', r))
    
    # 加入凯利
    for ra in [20, 22]:
        for kh in [92, 94]:
            conds = [('ra', '>', ra), ('kh', '<', kh)]
            r = test_signal(data, conds, 'home', 2.0)
            if r and r['roi'] > 5 and r['stability'] >= 50:
                home_results.append((f'赔率>2.0+客热>{ra}+主凯利<{kh}', r))
    
    # 加入必指
    for bh in [36, 38, 40]:
        conds = [('bh', '>', bh)]
        r = test_signal(data, conds, 'home', 2.0)
        if r and r['roi'] > 5 and r['stability'] >= 50:
            home_results.append((f'赔率>2.0+主必指>{bh}', r))
    
    # 三条件
    for ra in [20, 22]:
        for ya in [-10, -15]:
            for kh in [94, 96]:
                conds = [('ra', '>', ra), ('ya', '<', ya), ('kh', '<', kh)]
                r = test_signal(data, conds, 'home', 2.0)
                if r and r['roi'] > 8 and r['stability'] >= 50:
                    home_results.append((f'赔率>2.0+客热>{ra}+怕客<{ya}+凯利<{kh}', r))
    
    home_results.sort(key=lambda x: -x[1]['roi'])
    print(f"\n{'条件':<40} {'场次':<8} {'胜率':<8} {'ROI':<10} {'稳定性':<10}")
    print("-" * 80)
    for desc, r in home_results[:10]:
        print(f"{desc:<40} {r['count']:<8} {r['win_rate']:.1f}%{'':<3} {r['roi']:+.1f}%{'':<4} {r['stability']:.0f}%月盈利")
    
    # ==================== 客胜优化 ====================
    print("\n" + "=" * 80)
    print("✈️ 客胜信号优化")
    print("=" * 80)
    
    print("\n当前: 客凯利<94+赔率>2.0 → ROI +19.6%")
    print("\n【探索更多组合】")
    
    away_results = []
    
    # 基础凯利
    for ka in [90, 92, 94]:
        conds = [('ka', '<', ka)]
        for min_odds in [2.0, 2.2, 2.5]:
            r = test_signal(data, conds, 'away', min_odds)
            if r and r['roi'] > 0 and r['stability'] >= 50:
                away_results.append((f'赔率>{min_odds}+客凯利<{ka}', r))
    
    # 主热+怕主
    for rh in [20, 22, 24]:
        for yh in [-5, -10, -15]:
            conds = [('rh', '>', rh), ('yh', '<', yh)]
            r = test_signal(data, conds, 'away', 2.0)
            if r and r['roi'] > 5 and r['stability'] >= 50:
                away_results.append((f'赔率>2.0+主热>{rh}+怕主<{yh}', r))
    
    # 客必指
    for ba in [36, 38, 40]:
        conds = [('ba', '>', ba)]
        r = test_signal(data, conds, 'away', 2.0)
        if r and r['roi'] > 0 and r['stability'] >= 50:
            away_results.append((f'赔率>2.0+客必指>{ba}', r))
    
    # 组合
    for ka in [92, 94]:
        for rh in [20, 22]:
            conds = [('ka', '<', ka), ('rh', '>', rh)]
            r = test_signal(data, conds, 'away', 2.0)
            if r and r['roi'] > 5 and r['stability'] >= 50:
                away_results.append((f'赔率>2.0+客凯利<{ka}+主热>{rh}', r))
    
    # 凯利+怕主
    for ka in [92, 94]:
        for yh in [-10, -15]:
            conds = [('ka', '<', ka), ('yh', '<', yh)]
            r = test_signal(data, conds, 'away', 2.0)
            if r and r['roi'] > 8 and r['stability'] >= 50:
                away_results.append((f'赔率>2.0+客凯利<{ka}+怕主<{yh}', r))
    
    away_results.sort(key=lambda x: -x[1]['roi'])
    print(f"\n{'条件':<40} {'场次':<8} {'胜率':<8} {'ROI':<10} {'稳定性':<10}")
    print("-" * 80)
    for desc, r in away_results[:10]:
        print(f"{desc:<40} {r['count']:<8} {r['win_rate']:.1f}%{'':<3} {r['roi']:+.1f}%{'':<4} {r['stability']:.0f}%月盈利")
    
    # ==================== 最优推荐 ====================
    print("\n" + "=" * 80)
    print("🏆 最优信号推荐")
    print("=" * 80)
    
    print("\n【平局】")
    if draw_results:
        best = draw_results[0]
        print(f"  ⭐ {best[0]}")
        print(f"     {best[1]['count']}场 | 胜率{best[1]['win_rate']:.1f}% | ROI:{best[1]['roi']:+.1f}% | 稳定性:{best[1]['stability']:.0f}%")
    
    print("\n【主胜】")
    if home_results:
        best = home_results[0]
        print(f"  ⭐ {best[0]}")
        print(f"     {best[1]['count']}场 | 胜率{best[1]['win_rate']:.1f}% | ROI:{best[1]['roi']:+.1f}% | 稳定性:{best[1]['stability']:.0f}%")
    
    print("\n【客胜】")
    if away_results:
        best = away_results[0]
        print(f"  ⭐ {best[0]}")
        print(f"     {best[1]['count']}场 | 胜率{best[1]['win_rate']:.1f}% | ROI:{best[1]['roi']:+.1f}% | 稳定性:{best[1]['stability']:.0f}%")


if __name__ == "__main__":
    main()
