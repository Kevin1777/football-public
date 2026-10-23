"""
验证收益计算 - 检查赔率是否正确
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
    data_dir = Path(__file__).parent.parent.parent / "data"
    
    BET = 100
    
    # 测试：和量>45%+和凯利<96 平局信号
    print("=" * 80)
    print("验证：和量>45%+和凯利<96 平局信号")
    print("=" * 80)
    
    matches = []
    
    for y in data_dir.iterdir():
        if not y.is_dir() or not y.name.isdigit():
            continue
        for m in y.iterdir():
            if not m.is_dir():
                continue
            for d in m.iterdir():
                if not d.is_dir():
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
                        
                        # 提取指标
                        hv = pf(L.get('主胜_已成交量',0)) or 0
                        dv = pf(L.get('和局_已成交量',0)) or 0
                        av = pf(L.get('客胜_已成交量',0)) or 0
                        t = hv + dv + av
                        if t <= 0:
                            continue
                        
                        dvp = dv/t*100
                        kd = pf(L.get('凯利_和'))
                        od = pf(L.get('和局_欧赔'))
                        
                        if dvp is None or kd is None or od is None:
                            continue
                        
                        # 检查条件：和量>45%+和凯利<96
                        if dvp > 45 and kd < 96:
                            # 解析比分
                            p = score.replace(' ', '').split('-')
                            h, a = int(p[0]), int(p[1])
                            is_draw = (h == a)
                            
                            matches.append({
                                'file': f.name,
                                'score': score,
                                'dvp': dvp,
                                'kd': kd,
                                'odds': od,
                                'is_draw': is_draw
                            })
                    except:
                        pass
    
    print(f"\n匹配场次: {len(matches)}场")
    
    # 显示前10场详细
    print("\n【前10场详细】")
    for i, m in enumerate(matches[:10], 1):
        result = "✅平" if m['is_draw'] else "❌"
        print(f"{i}. {result} {m['file'][:40]}...")
        print(f"   比分:{m['score']} | 和量:{m['dvp']:.1f}% | 和凯利:{m['kd']:.1f} | 和赔:{m['odds']:.2f}")
    
    # 计算收益
    wins = sum(1 for m in matches if m['is_draw'])
    total_bet = len(matches) * BET
    total_return = sum(BET * m['odds'] for m in matches if m['is_draw'])
    profit = total_return - total_bet
    roi = profit / total_bet * 100 if total_bet > 0 else 0
    avg_odds = sum(m['odds'] for m in matches) / len(matches) if matches else 0
    
    print(f"\n【收益统计】")
    print(f"总场次: {len(matches)}")
    print(f"命中: {wins}场 ({wins/len(matches)*100:.1f}%)")
    print(f"平均赔率: {avg_odds:.2f}")
    print(f"投入: {total_bet:,}元")
    print(f"回收: {total_return:,.0f}元")
    print(f"盈亏: {profit:+,.0f}元")
    print(f"ROI: {roi:+.1f}%")
    
    # 验证计算
    print(f"\n【验证计算】")
    print(f"理论EV = 胜率 × 赔率 - 1 = {wins/len(matches)*100:.1f}% × {avg_odds:.2f} - 1 = {wins/len(matches) * avg_odds - 1:.2f}")
    print(f"实际ROI = {roi/100:.2f}")
    
    # 显示赔率分布
    print(f"\n【赔率分布】")
    odds_ranges = {'2.5-3.0': 0, '3.0-3.5': 0, '3.5-4.0': 0, '4.0+': 0}
    for m in matches:
        if m['odds'] < 3.0:
            odds_ranges['2.5-3.0'] += 1
        elif m['odds'] < 3.5:
            odds_ranges['3.0-3.5'] += 1
        elif m['odds'] < 4.0:
            odds_ranges['3.5-4.0'] += 1
        else:
            odds_ranges['4.0+'] += 1
    
    for r, c in odds_ranges.items():
        print(f"  {r}: {c}场 ({c/len(matches)*100:.1f}%)")
    
    # 显示几场高赔率的详细
    print(f"\n【高赔率场次详细（赔率>3.5）】")
    high_odds = [m for m in matches if m['odds'] > 3.5]
    high_wins = sum(1 for m in high_odds if m['is_draw'])
    print(f"高赔率场次: {len(high_odds)}场")
    print(f"高赔率命中: {high_wins}场 ({high_wins/len(high_odds)*100:.1f}%)" if high_odds else "")
    
    for m in high_odds[:5]:
        result = "✅平" if m['is_draw'] else "❌"
        print(f"  {result} 赔率{m['odds']:.2f} | {m['file'][:35]}...")


if __name__ == "__main__":
    main()
