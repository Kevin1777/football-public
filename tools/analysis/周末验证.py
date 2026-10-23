"""
验证12月5-7日周末表现
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
    
    # 12月5-7日
    target_dates = ['05', '06', '07']
    
    print("=" * 80)
    print("📊 12月5-7日周末验证（平衡版 + 精选版）")
    print("=" * 80)
    
    BET = 100
    all_matches = []
    
    for day in target_dates:
        day_dir = data_dir / day
        if not day_dir.exists():
            print(f"\n⚠️ {day}日数据不存在")
            continue
        
        print(f"\n{'='*80}")
        print(f"📅 12月{day}日")
        print("=" * 80)
        
        day_matches = []
        
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
                od = pf(L.get('和局_欧赔'))
                
                if dvp is None or kd is None or od is None:
                    continue
                
                # 解析比分
                p = score.replace(' ', '').split('-')
                h, a = int(p[0]), int(p[1])
                is_draw = (h == a)
                
                # 检查信号
                is_balanced = (dvp > 45 and kd < 96)  # 平衡版
                is_selected = (dvp > 47 and kd < 96)  # 精选版
                
                if is_balanced or is_selected:
                    league = mi.get('league', '')
                    home = mi.get('home_team', '')
                    away = mi.get('away_team', '')
                    
                    match_info = {
                        'date': day,
                        'league': league,
                        'home': home,
                        'away': away,
                        'score': score,
                        'dvp': dvp,
                        'kd': kd,
                        'odds': od,
                        'is_draw': is_draw,
                        'is_balanced': is_balanced,
                        'is_selected': is_selected,
                        'file': f.name
                    }
                    day_matches.append(match_info)
                    all_matches.append(match_info)
            except Exception as e:
                pass
        
        # 显示当天比赛
        if day_matches:
            print(f"\n当天推荐: {len(day_matches)}场")
            print("-" * 80)
            
            for m in day_matches:
                result = "✅平局" if m['is_draw'] else "❌"
                tier = "⭐精选" if m['is_selected'] else "平衡"
                profit = BET * m['odds'] - BET if m['is_draw'] else -BET
                
                print(f"{result} [{tier}] {m['league']}")
                print(f"   {m['home']} vs {m['away']} | 比分:{m['score']}")
                print(f"   和量:{m['dvp']:.1f}% | 和凯利:{m['kd']:.1f} | 赔率:{m['odds']:.2f} | 盈亏:{profit:+.0f}元")
                print()
    
    # ==================== 汇总 ====================
    print("\n" + "=" * 80)
    print("📊 周末汇总（12月5-7日）")
    print("=" * 80)
    
    # 平衡版统计
    balanced = [m for m in all_matches if m['is_balanced']]
    balanced_wins = sum(1 for m in balanced if m['is_draw'])
    balanced_investment = len(balanced) * BET
    balanced_returns = sum(BET * m['odds'] for m in balanced if m['is_draw'])
    balanced_profit = balanced_returns - balanced_investment
    
    # 精选版统计
    selected = [m for m in all_matches if m['is_selected']]
    selected_wins = sum(1 for m in selected if m['is_draw'])
    selected_investment = len(selected) * BET
    selected_returns = sum(BET * m['odds'] for m in selected if m['is_draw'])
    selected_profit = selected_returns - selected_investment
    
    print(f"\n【平衡版】和量>45%+和凯利<96")
    print(f"   推荐: {len(balanced)}场 | 命中: {balanced_wins}场 ({balanced_wins/len(balanced)*100:.1f}%)" if balanced else "   无推荐")
    print(f"   投入: {balanced_investment}元 | 回收: {balanced_returns:.0f}元 | 盈亏: {balanced_profit:+.0f}元")
    if balanced:
        print(f"   ROI: {balanced_profit/balanced_investment*100:+.1f}%")
    
    print(f"\n【精选版】和量>47%+和凯利<96")
    print(f"   推荐: {len(selected)}场 | 命中: {selected_wins}场 ({selected_wins/len(selected)*100:.1f}%)" if selected else "   无推荐")
    print(f"   投入: {selected_investment}元 | 回收: {selected_returns:.0f}元 | 盈亏: {selected_profit:+.0f}元")
    if selected:
        print(f"   ROI: {selected_profit/selected_investment*100:+.1f}%")
    
    # 组合策略
    print(f"\n【组合策略】精选版单注200 + 平衡版额外单注100")
    combo_investment = 0
    combo_returns = 0
    
    for m in all_matches:
        if m['is_selected']:
            combo_investment += 200
            if m['is_draw']:
                combo_returns += 200 * m['odds']
        elif m['is_balanced']:
            combo_investment += 100
            if m['is_draw']:
                combo_returns += 100 * m['odds']
    
    combo_profit = combo_returns - combo_investment
    print(f"   投入: {combo_investment}元 | 回收: {combo_returns:.0f}元 | 盈亏: {combo_profit:+.0f}元")
    if combo_investment > 0:
        print(f"   ROI: {combo_profit/combo_investment*100:+.1f}%")
    
    # 详细列表
    print("\n" + "=" * 80)
    print("📋 详细推荐列表")
    print("=" * 80)
    
    print(f"\n{'日期':<8} {'类型':<6} {'联赛':<12} {'比赛':<30} {'赔率':<6} {'结果':<8} {'盈亏':<10}")
    print("-" * 90)
    
    for m in all_matches:
        tier = "⭐精选" if m['is_selected'] else "平衡"
        match_name = f"{m['home'][:10]} vs {m['away'][:10]}"
        result = "✅平局" if m['is_draw'] else "❌"
        profit = BET * m['odds'] - BET if m['is_draw'] else -BET
        
        print(f"12/{m['date']:<5} {tier:<6} {m['league'][:10]:<12} {match_name:<30} {m['odds']:<6.2f} {result:<8} {profit:+.0f}元")


if __name__ == "__main__":
    main()
