"""
完整验证 - 平局 + 分胜负信号
12月5-7日周末
"""

import sys
import json
from pathlib import Path

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
    print("📊 完整策略验证（平局 + 分胜负）12月5-7日")
    print("=" * 80)
    
    BET = 100
    
    # 收集所有推荐
    draw_bets = []
    home_bets = []
    away_bets = []
    
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
                
                # 提取指标
                hv = pf(L.get('主胜_已成交量', 0)) or 0
                dv = pf(L.get('和局_已成交量', 0)) or 0
                av = pf(L.get('客胜_已成交量', 0)) or 0
                t = hv + dv + av
                if t <= 0:
                    continue
                
                dvp = dv / t * 100
                kd = pf(L.get('凯利_和'))
                ka = pf(L.get('凯利_客'))
                ra = pf(L.get('热指_客'))  # 客热
                rh = pf(L.get('热指_主'))  # 主热
                ya = pf(L.get('赢亏_客'))  # 怕客
                yh = pf(L.get('赢亏_主'))  # 怕主
                
                oh = pf(L.get('主胜_欧赔'))
                od = pf(L.get('和局_欧赔'))
                oa = pf(L.get('客胜_欧赔'))
                
                # 解析比分
                p = score.replace(' ', '').split('-')
                home_goals, away_goals = int(p[0]), int(p[1])
                actual = 'home' if home_goals > away_goals else 'away' if away_goals > home_goals else 'draw'
                
                league = mi.get('league', '')
                home = mi.get('home_team', '')
                away = mi.get('away_team', '')
                
                match_base = {
                    'date': day,
                    'league': league,
                    'home': home,
                    'away': away,
                    'score': score,
                    'actual': actual
                }
                
                # ========== 平局信号 ==========
                if dvp and kd:
                    # 精选版：和量>47%+和凯利<96
                    if dvp > 47 and kd < 96 and od and od >= 2.5:
                        draw_bets.append({
                            **match_base,
                            'signal': '精选',
                            'desc': f'和量{dvp:.0f}%+凯利{kd:.0f}',
                            'odds': od,
                            'won': actual == 'draw'
                        })
                    # 平衡版额外：和量>45%+和凯利<96（不重复）
                    elif dvp > 45 and kd < 96 and od and od >= 2.5:
                        draw_bets.append({
                            **match_base,
                            'signal': '平衡',
                            'desc': f'和量{dvp:.0f}%+凯利{kd:.0f}',
                            'odds': od,
                            'won': actual == 'draw'
                        })
                
                # ========== 主胜信号（赔率>1.8）==========
                if ra and oh and oh > 1.8:
                    # 客热>20+怕客<-10
                    if ra > 20 and ya and ya < -10:
                        home_bets.append({
                            **match_base,
                            'signal': '主胜',
                            'desc': f'客热{ra:.0f}+怕客{ya:.0f}',
                            'odds': oh,
                            'won': actual == 'home'
                        })
                    # 客热>22（不重复）
                    elif ra > 22:
                        home_bets.append({
                            **match_base,
                            'signal': '主胜',
                            'desc': f'客热{ra:.0f}',
                            'odds': oh,
                            'won': actual == 'home'
                        })
                
                # ========== 客胜信号（赔率>2.0）==========
                if rh and oa and oa > 2.0:
                    # 主热>20+怕主<-10
                    if rh > 20 and yh and yh < -10:
                        away_bets.append({
                            **match_base,
                            'signal': '客胜',
                            'desc': f'主热{rh:.0f}+怕主{yh:.0f}',
                            'odds': oa,
                            'won': actual == 'away'
                        })
                    # 客凯利<94（不重复）
                    elif ka and ka < 94:
                        away_bets.append({
                            **match_base,
                            'signal': '客胜',
                            'desc': f'客凯利{ka:.0f}',
                            'odds': oa,
                            'won': actual == 'away'
                        })
                
            except Exception as e:
                pass
    
    # ==================== 平局信号 ====================
    print("\n" + "=" * 80)
    print("🎯 平局信号")
    print("=" * 80)
    
    if draw_bets:
        wins = sum(1 for b in draw_bets if b['won'])
        investment = len(draw_bets) * BET
        returns = sum(BET * b['odds'] for b in draw_bets if b['won'])
        profit = returns - investment
        
        print(f"\n推荐: {len(draw_bets)}场 | 命中: {wins}场 ({wins/len(draw_bets)*100:.1f}%)")
        print(f"投入: {investment}元 | 盈亏: {profit:+.0f}元 | ROI: {profit/investment*100:+.1f}%")
        
        print(f"\n{'结果':<6} {'类型':<6} {'联赛':<10} {'比赛':<25} {'赔率':<6} {'盈亏':<8}")
        print("-" * 70)
        for b in draw_bets:
            result = "✅" if b['won'] else "❌"
            p = BET * b['odds'] - BET if b['won'] else -BET
            match = f"{b['home'][:8]} vs {b['away'][:8]}"
            print(f"{result:<6} {b['signal']:<6} {b['league'][:8]:<10} {match:<25} {b['odds']:<6.2f} {p:+.0f}元")
    
    # ==================== 主胜信号 ====================
    print("\n" + "=" * 80)
    print("🏠 主胜信号（赔率>1.8）")
    print("=" * 80)
    
    if home_bets:
        wins = sum(1 for b in home_bets if b['won'])
        investment = len(home_bets) * BET
        returns = sum(BET * b['odds'] for b in home_bets if b['won'])
        profit = returns - investment
        
        print(f"\n推荐: {len(home_bets)}场 | 命中: {wins}场 ({wins/len(home_bets)*100:.1f}%)")
        print(f"投入: {investment}元 | 盈亏: {profit:+.0f}元 | ROI: {profit/investment*100:+.1f}%")
        
        print(f"\n{'结果':<6} {'条件':<18} {'联赛':<10} {'比赛':<25} {'赔率':<6} {'盈亏':<8}")
        print("-" * 80)
        for b in home_bets:
            result = "✅" if b['won'] else "❌"
            p = BET * b['odds'] - BET if b['won'] else -BET
            match = f"{b['home'][:8]} vs {b['away'][:8]}"
            print(f"{result:<6} {b['desc']:<18} {b['league'][:8]:<10} {match:<25} {b['odds']:<6.2f} {p:+.0f}元")
    else:
        print("\n无符合条件的主胜推荐")
    
    # ==================== 客胜信号 ====================
    print("\n" + "=" * 80)
    print("✈️ 客胜信号（赔率>2.0）")
    print("=" * 80)
    
    if away_bets:
        wins = sum(1 for b in away_bets if b['won'])
        investment = len(away_bets) * BET
        returns = sum(BET * b['odds'] for b in away_bets if b['won'])
        profit = returns - investment
        
        print(f"\n推荐: {len(away_bets)}场 | 命中: {wins}场 ({wins/len(away_bets)*100:.1f}%)")
        print(f"投入: {investment}元 | 盈亏: {profit:+.0f}元 | ROI: {profit/investment*100:+.1f}%")
        
        print(f"\n{'结果':<6} {'条件':<18} {'联赛':<10} {'比赛':<25} {'赔率':<6} {'盈亏':<8}")
        print("-" * 80)
        for b in away_bets:
            result = "✅" if b['won'] else "❌"
            p = BET * b['odds'] - BET if b['won'] else -BET
            match = f"{b['home'][:8]} vs {b['away'][:8]}"
            print(f"{result:<6} {b['desc']:<18} {b['league'][:8]:<10} {match:<25} {b['odds']:<6.2f} {p:+.0f}元")
    else:
        print("\n无符合条件的客胜推荐")
    
    # ==================== 总汇总 ====================
    print("\n" + "=" * 80)
    print("📊 完整策略汇总（12月5-7日）")
    print("=" * 80)
    
    all_bets = draw_bets + home_bets + away_bets
    total_investment = len(all_bets) * BET
    total_returns = sum(BET * b['odds'] for b in all_bets if b['won'])
    total_profit = total_returns - total_investment
    total_wins = sum(1 for b in all_bets if b['won'])
    
    print(f"\n{'类型':<10} {'场次':<8} {'命中':<8} {'胜率':<10} {'盈亏':<12} {'ROI':<10}")
    print("-" * 60)
    
    for name, bets in [('平局', draw_bets), ('主胜', home_bets), ('客胜', away_bets)]:
        if bets:
            w = sum(1 for b in bets if b['won'])
            inv = len(bets) * BET
            ret = sum(BET * b['odds'] for b in bets if b['won'])
            prf = ret - inv
            roi = prf / inv * 100 if inv > 0 else 0
            status = "✅" if prf > 0 else "❌"
            print(f"{name:<10} {len(bets):<8} {w:<8} {w/len(bets)*100:.1f}%{'':<5} {status}{prf:+.0f}元{'':<5} {roi:+.1f}%")
    
    print("-" * 60)
    print(f"{'合计':<10} {len(all_bets):<8} {total_wins:<8} {total_wins/len(all_bets)*100:.1f}%{'':<5} {total_profit:+.0f}元{'':<7} {total_profit/total_investment*100:+.1f}%")
    
    print(f"\n💰 投入 {total_investment}元 → 盈利 {total_profit:+.0f}元")


if __name__ == "__main__":
    main()
