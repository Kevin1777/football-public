"""
分析主胜信号为什么亏损
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def pf(v):
    if v is None or v == '':
        return None
    try:
        return float(str(v).replace(',', ''))
    except:
        return None


def main():
    data_dir = Path(__file__).parent.parent.parent / "data" / "2025" / "12"
    
    target_dates = ['05', '06', '07']
    
    print("=" * 80)
    print("📊 主胜信号亏损分析")
    print("=" * 80)
    
    home_bets = []
    
    for day in target_dates:
        day_dir = data_dir / day
        if not day_dir.exists():
            continue
        
        for f in sorted(day_dir.glob("*.json")):
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
                
                ra = pf(L.get('热指_客'))
                ya = pf(L.get('赢亏_客'))
                oh = pf(L.get('主胜_欧赔'))
                
                p = score.replace(' ', '').split('-')
                home_goals, away_goals = int(p[0]), int(p[1])
                actual = 'home' if home_goals > away_goals else 'away' if away_goals > home_goals else 'draw'
                
                league = mi.get('league', '')
                home = mi.get('home_team', '')
                away = mi.get('away_team', '')
                
                # 主胜信号条件
                if ra and oh and oh > 1.8:
                    signal = None
                    if ra > 20 and ya and ya < -10:
                        signal = f'客热{ra:.0f}+怕客{ya:.0f}'
                    elif ra > 22:
                        signal = f'客热{ra:.0f}'
                    
                    if signal:
                        home_bets.append({
                            'league': league,
                            'home': home,
                            'away': away,
                            'score': score,
                            'actual': actual,
                            'signal': signal,
                            'odds': oh,
                            'ra': ra,
                            'ya': ya or 0,
                            'won': actual == 'home'
                        })
            except:
                pass
    
    # 分析
    print(f"\n总推荐: {len(home_bets)}场")
    wins = [b for b in home_bets if b['won']]
    losses = [b for b in home_bets if not b['won']]
    
    print(f"命中: {len(wins)}场")
    print(f"未中: {len(losses)}场")
    
    # 分析未中的比赛
    print("\n" + "=" * 80)
    print("❌ 未命中的比赛分析")
    print("=" * 80)
    
    draw_count = sum(1 for b in losses if b['actual'] == 'draw')
    away_count = sum(1 for b in losses if b['actual'] == 'away')
    
    print(f"\n未中原因:")
    print(f"  - 打成平局: {draw_count}场 ({draw_count/len(losses)*100:.0f}%)")
    print(f"  - 客队赢了: {away_count}场 ({away_count/len(losses)*100:.0f}%)")
    
    print("\n【未中详情】")
    for b in losses:
        result = "平局" if b['actual'] == 'draw' else "客胜"
        print(f"  {result} | {b['league'][:8]} | {b['home'][:8]} vs {b['away'][:8]} | {b['score']} | 赔率{b['odds']:.2f}")
    
    # 按赔率区间分析
    print("\n" + "=" * 80)
    print("按赔率区间分析")
    print("=" * 80)
    
    odds_ranges = [
        (1.8, 2.0, '1.8-2.0'),
        (2.0, 2.5, '2.0-2.5'),
        (2.5, 3.0, '2.5-3.0'),
        (3.0, 10, '3.0+'),
    ]
    
    for low, high, name in odds_ranges:
        subset = [b for b in home_bets if low <= b['odds'] < high]
        if subset:
            w = sum(1 for b in subset if b['won'])
            inv = len(subset) * 100
            ret = sum(100 * b['odds'] for b in subset if b['won'])
            prf = ret - inv
            roi = prf / inv * 100
            status = "✅" if prf > 0 else "❌"
            print(f"  {name}: {len(subset)}场 | 胜率{w/len(subset)*100:.0f}% | {status} ROI:{roi:+.0f}%")
    
    # 按条件分析
    print("\n" + "=" * 80)
    print("按信号条件分析")
    print("=" * 80)
    
    # 有怕客 vs 只有客热
    with_ya = [b for b in home_bets if '怕客' in b['signal']]
    only_ra = [b for b in home_bets if '怕客' not in b['signal']]
    
    for name, subset in [('客热+怕客', with_ya), ('只有客热', only_ra)]:
        if subset:
            w = sum(1 for b in subset if b['won'])
            inv = len(subset) * 100
            ret = sum(100 * b['odds'] for b in subset if b['won'])
            prf = ret - inv
            roi = prf / inv * 100
            status = "✅" if prf > 0 else "❌"
            print(f"  {name}: {len(subset)}场 | 胜率{w/len(subset)*100:.0f}% | {status} ROI:{roi:+.0f}%")
    
    # 历史对比
    print("\n" + "=" * 80)
    print("与历史样本对比")
    print("=" * 80)
    
    # 加载全部周末数据
    all_data_dir = Path(__file__).parent.parent.parent / "data"
    all_home = []
    
    from datetime import datetime
    
    for y in all_data_dir.iterdir():
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
                    if weekday < 5:  # 只要周末
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
                        
                        ra = pf(L.get('热指_客'))
                        ya = pf(L.get('赢亏_客'))
                        oh = pf(L.get('主胜_欧赔'))
                        
                        p = score.replace(' ', '').split('-')
                        home_goals, away_goals = int(p[0]), int(p[1])
                        actual = 'home' if home_goals > away_goals else 'away' if away_goals > home_goals else 'draw'
                        
                        if ra and oh and oh > 1.8:
                            if ra > 20 and ya and ya < -10:
                                all_home.append({'odds': oh, 'won': actual == 'home', 'signal': '客热+怕客'})
                            elif ra > 22:
                                all_home.append({'odds': oh, 'won': actual == 'home', 'signal': '只客热'})
                    except:
                        pass
    
    print(f"\n历史周末总样本: {len(all_home)}场")
    
    w = sum(1 for b in all_home if b['won'])
    inv = len(all_home) * 100
    ret = sum(100 * b['odds'] for b in all_home if b['won'])
    prf = ret - inv
    roi = prf / inv * 100
    print(f"历史胜率: {w/len(all_home)*100:.1f}%")
    print(f"历史ROI: {roi:+.1f}%")
    
    # 分条件
    for sig in ['客热+怕客', '只客热']:
        subset = [b for b in all_home if b['signal'] == sig]
        if subset:
            w = sum(1 for b in subset if b['won'])
            inv = len(subset) * 100
            ret = sum(100 * b['odds'] for b in subset if b['won'])
            prf = ret - inv
            roi = prf / inv * 100
            status = "✅" if prf > 0 else "❌"
            print(f"  {sig}: {len(subset)}场 | 胜率{w/len(subset)*100:.1f}% | {status} ROI:{roi:+.1f}%")


if __name__ == "__main__":
    main()
