"""
修正后完整策略测试 - 12月5-7日
主胜条件收紧：必须同时满足 客热>20 + 怕客<-10 + 赔率>2.0
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def pf(v):
    if v is None or v == '':
        return None
    try:
        return float(str(v).replace(',', ''))
    except:
        return None


def test_weekend(dates, data_dir):
    BET = 100
    
    draw_bets = []
    home_bets = []
    away_bets = []
    
    for day in dates:
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
                ra = pf(L.get('热指_客'))
                rh = pf(L.get('热指_主'))
                ya = pf(L.get('赢亏_客'))
                yh = pf(L.get('赢亏_主'))
                
                oh = pf(L.get('主胜_欧赔'))
                od = pf(L.get('和局_欧赔'))
                oa = pf(L.get('客胜_欧赔'))
                
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
                if dvp and kd and od and od >= 2.5:
                    if dvp > 47 and kd < 96:
                        draw_bets.append({
                            **match_base,
                            'signal': '精选',
                            'desc': f'和量{dvp:.0f}%+凯利{kd:.0f}',
                            'odds': od,
                            'won': actual == 'draw'
                        })
                    elif dvp > 45 and kd < 96:
                        draw_bets.append({
                            **match_base,
                            'signal': '平衡',
                            'desc': f'和量{dvp:.0f}%+凯利{kd:.0f}',
                            'odds': od,
                            'won': actual == 'draw'
                        })
                
                # ========== 主胜信号【修正】==========
                # 必须同时满足：赔率>2.0 + 客热>20 + 怕客<-10
                if ra and ya and oh:
                    if oh > 2.0 and ra > 20 and ya < -10:
                        home_bets.append({
                            **match_base,
                            'signal': '主胜',
                            'desc': f'客热{ra:.0f}+怕客{ya:.0f}',
                            'odds': oh,
                            'won': actual == 'home'
                        })
                
                # ========== 客胜信号 ==========
                if ka and oa and oa > 2.0:
                    if ka < 94:
                        away_bets.append({
                            **match_base,
                            'signal': '客胜',
                            'desc': f'客凯利{ka:.0f}',
                            'odds': oa,
                            'won': actual == 'away'
                        })
                
            except:
                pass
    
    return draw_bets, home_bets, away_bets


def print_results(name, bets, BET=100):
    if not bets:
        print(f"\n{name}: 无推荐")
        return 0
    
    wins = sum(1 for b in bets if b['won'])
    investment = len(bets) * BET
    returns = sum(BET * b['odds'] for b in bets if b['won'])
    profit = returns - investment
    roi = profit / investment * 100
    
    status = "✅" if profit > 0 else "❌"
    print(f"\n{name}: {len(bets)}场 | 命中{wins}场({wins/len(bets)*100:.0f}%) | {status} ROI:{roi:+.1f}% | 盈亏:{profit:+.0f}元")
    
    print(f"{'结果':<4} {'条件':<16} {'联赛':<8} {'比赛':<24} {'赔率':<6} {'盈亏':<8}")
    print("-" * 75)
    for b in bets:
        result = "✅" if b['won'] else "❌"
        p = BET * b['odds'] - BET if b['won'] else -BET
        match = f"{b['home'][:8]} vs {b['away'][:8]}"
        print(f"{result:<4} {b['desc']:<16} {b['league'][:6]:<8} {match:<24} {b['odds']:<6.2f} {p:+.0f}元")
    
    return profit


def main():
    print("=" * 80)
    print("📊 修正后策略测试 - 12月5-7日")
    print("=" * 80)
    print("\n【修正内容】")
    print("  主胜：删除「只有客热」，必须同时满足 赔率>2.0 + 客热>20 + 怕客<-10")
    
    data_dir = Path(__file__).parent.parent.parent / "data" / "2025" / "12"
    dates = ['05', '06', '07']
    
    draw, home, away = test_weekend(dates, data_dir)
    
    print("\n" + "=" * 80)
    print("🎯 平局信号")
    print("=" * 80)
    draw_profit = print_results("平局", draw)
    
    print("\n" + "=" * 80)
    print("🏠 主胜信号【修正后】")
    print("=" * 80)
    home_profit = print_results("主胜", home)
    
    print("\n" + "=" * 80)
    print("✈️ 客胜信号")
    print("=" * 80)
    away_profit = print_results("客胜", away)
    
    # 汇总
    print("\n" + "=" * 80)
    print("📊 修正后策略汇总")
    print("=" * 80)
    
    all_bets = draw + home + away
    total_count = len(all_bets)
    total_wins = sum(1 for b in all_bets if b['won'])
    total_investment = total_count * 100
    total_profit = draw_profit + home_profit + away_profit
    
    print(f"\n{'类型':<8} {'场次':<8} {'盈亏':<12} {'ROI':<10}")
    print("-" * 40)
    print(f"{'平局':<8} {len(draw):<8} {draw_profit:+.0f}元{'':<6} {draw_profit/len(draw)/100*100:+.1f}%" if draw else "")
    print(f"{'主胜':<8} {len(home):<8} {home_profit:+.0f}元{'':<6} {home_profit/len(home)/100*100:+.1f}%" if home else "")
    print(f"{'客胜':<8} {len(away):<8} {away_profit:+.0f}元{'':<6} {away_profit/len(away)/100*100:+.1f}%" if away else "")
    print("-" * 40)
    print(f"{'合计':<8} {total_count:<8} {total_profit:+.0f}元{'':<6} {total_profit/total_investment*100:+.1f}%")
    
    print(f"\n💰 投入 {total_investment:,}元 → 盈利 {total_profit:+,.0f}元")
    
    # 与修正前对比
    print("\n" + "=" * 80)
    print("📈 修正前后对比")
    print("=" * 80)
    print(f"\n{'项目':<12} {'修正前':<15} {'修正后':<15}")
    print("-" * 45)
    print(f"{'主胜场次':<12} {'24场':<15} {f'{len(home)}场':<15}")
    print(f"{'主胜ROI':<12} {'-14.8%':<15} {f'{home_profit/len(home)/100*100:+.1f}%' if home else 'N/A':<15}")
    print(f"{'总场次':<12} {'99场':<15} {f'{total_count}场':<15}")
    print(f"{'总ROI':<12} {'+12.7%':<15} {f'{total_profit/total_investment*100:+.1f}%':<15}")
    print(f"{'总盈利':<12} {'+1,257元':<15} {f'{total_profit:+,.0f}元':<15}")


if __name__ == "__main__":
    main()
