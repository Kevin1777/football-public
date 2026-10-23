"""
周末优化 - 分析周末比赛分布，扩展信号并做样本外验证
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
                
                # 解析日期获取星期几
                try:
                    date_str = f"{y.name}-{m.name}-{d.name}"
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    weekday = dt.weekday()  # 0=周一, 6=周日
                    is_weekend = weekday >= 5  # 5=周六, 6=周日
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
                        
                        if s.get('ra') is not None and s.get('ya') is not None:
                            s['hfa'] = s['ra'] - s['ya']
                        if s.get('rh') is not None and s.get('yh') is not None:
                            s['hfh'] = s['rh'] - s['yh']
                        
                        results.append({
                            'actual': actual,
                            's': s,
                            'date': date_str,
                            'weekday': weekday,
                            'is_weekend': is_weekend,
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
    
    if len(filtered) < 20:
        return None
    
    wins = sum(1 for m in filtered if m['won'])
    investment = len(filtered) * BET
    returns = sum(BET * m['odds'] for m in filtered if m['won'])
    profit = returns - investment
    roi = profit / investment * 100
    avg_odds = sum(m['odds'] for m in filtered) / len(filtered)
    
    # 按月统计
    monthly = defaultdict(lambda: {'bets': 0, 'wins': 0, 'returns': 0})
    for m in filtered:
        monthly[m['month']]['bets'] += 1
        if m['won']:
            monthly[m['month']]['wins'] += 1
            monthly[m['month']]['returns'] += BET * m['odds']
    
    # 计算月份盈利比例
    pos_months = sum(1 for m, v in monthly.items() if v['returns'] - v['bets']*BET > 0)
    total_months = len(monthly)
    
    return {
        'count': len(filtered),
        'wins': wins,
        'win_rate': wins / len(filtered) * 100,
        'avg_odds': avg_odds,
        'profit': profit,
        'roi': roi,
        'pos_months': pos_months,
        'total_months': total_months,
        'stability': pos_months / total_months * 100 if total_months > 0 else 0
    }


def main():
    print("=" * 80)
    print("📊 周末优化 - 分析周末比赛并扩展信号")
    print("=" * 80)
    
    print("\n加载数据...")
    all_data = load_data()
    
    weekend = [r for r in all_data if r['is_weekend']]
    weekday = [r for r in all_data if not r['is_weekend']]
    
    print(f"\n总数据: {len(all_data)}场")
    print(f"周末(周六日): {len(weekend)}场 ({len(weekend)/len(all_data)*100:.1f}%)")
    print(f"工作日: {len(weekday)}场 ({len(weekday)/len(all_data)*100:.1f}%)")
    
    # 按星期分布
    weekday_dist = defaultdict(int)
    for r in all_data:
        weekday_dist[r['weekday']] += 1
    
    print("\n【按星期分布】")
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    for i in range(7):
        bar = '█' * (weekday_dist[i] // 30)
        print(f"  {weekday_names[i]}: {weekday_dist[i]:4d}场 {bar}")
    
    # ==================== 周末信号扩展 ====================
    print("\n" + "=" * 80)
    print("【周末信号挖掘 - 宽松阈值增加场次】")
    print("=" * 80)
    
    all_signals = []
    
    # 平局信号族 - 放宽阈值
    print("\n▶ 平局信号（周末）")
    for dvp_th in [40, 42, 44, 45, 47, 50]:
        for kd_th in [94, 96, 98, 100]:
            conds = [('dvp', '>', dvp_th)]
            if kd_th < 100:
                conds.append(('kd', '<', kd_th))
            
            r = test_signal(weekend, conds, 'draw', 2.5)
            if r and r['roi'] > 0 and r['stability'] >= 50:
                desc = f"和量>{dvp_th}%" + (f"+和凯利<{kd_th}" if kd_th < 100 else "")
                status = "✅" if r['roi'] > 8 else "⚪"
                print(f"  {status} {desc}: {r['count']}场 | ROI:{r['roi']:+.1f}% | 稳定性:{r['stability']:.0f}%")
                all_signals.append(('平局', desc, r['count'], r['roi'], r['stability']))
    
    # 主胜信号族 - 高赔区间
    print("\n▶ 主胜信号（周末，赔率>1.8）")
    for ra_th in [18, 20, 22, 24]:
        for ya_th in [0, -5, -10, -15]:
            conds = [('ra', '>', ra_th)]
            if ya_th < 0:
                conds.append(('ya', '<', ya_th))
            
            r = test_signal(weekend, conds, 'home', 1.8)
            if r and r['roi'] > 0 and r['count'] >= 30 and r['stability'] >= 40:
                desc = f"客热>{ra_th}" + (f"+怕客<{ya_th}" if ya_th < 0 else "")
                status = "✅" if r['roi'] > 8 else "⚪"
                print(f"  {status} 主胜@>1.8 | {desc}: {r['count']}场 | ROI:{r['roi']:+.1f}% | 稳定:{r['stability']:.0f}%")
                all_signals.append(('主胜>1.8', desc, r['count'], r['roi'], r['stability']))
    
    # 客胜信号族 - 高赔区间
    print("\n▶ 客胜信号（周末，赔率>2.0）")
    for rh_th in [18, 20, 22, 24]:
        for yh_th in [0, -5, -10]:
            conds = [('rh', '>', rh_th)]
            if yh_th < 0:
                conds.append(('yh', '<', yh_th))
            
            r = test_signal(weekend, conds, 'away', 2.0)
            if r and r['roi'] > 0 and r['count'] >= 30 and r['stability'] >= 40:
                desc = f"主热>{rh_th}" + (f"+怕主<{yh_th}" if yh_th < 0 else "")
                status = "✅" if r['roi'] > 8 else "⚪"
                print(f"  {status} 客胜@>2.0 | {desc}: {r['count']}场 | ROI:{r['roi']:+.1f}% | 稳定:{r['stability']:.0f}%")
                all_signals.append(('客胜>2.0', desc, r['count'], r['roi'], r['stability']))
    
    # 低赔高胜率信号（让球价值）
    print("\n▶ 低赔信号（周末，可用让球）")
    for ra_th in [20, 22, 24, 26]:
        for tv_th in [100000, 150000, 200000]:
            conds = [('ra', '>', ra_th), ('tv', '>', tv_th), ('oh', '<', 1.6)]
            r = test_signal(weekend, conds, 'home', 1.0)
            if r and r['win_rate'] >= 70 and r['count'] >= 20:
                desc = f"客热>{ra_th}+成交>{tv_th//1000}K+主赔<1.6"
                print(f"  ⚪ {desc}: {r['count']}场 | 胜率:{r['win_rate']:.1f}% | 可用让球")
                all_signals.append(('主胜让球', desc, r['count'], r['win_rate'], r['stability']))
    
    # ==================== 汇总 ====================
    print("\n" + "=" * 80)
    print("🏆 周末盈利信号汇总（按场次排序）")
    print("=" * 80)
    
    # 按场次排序
    all_signals.sort(key=lambda x: -x[2])
    
    total_weekend_signals = 0
    print("\n【推荐信号（稳定性≥50%）】")
    for direction, desc, count, roi_or_wr, stability in all_signals[:15]:
        if stability >= 50:
            star = "⭐" if roi_or_wr > 10 else ""
            print(f"  {star} {direction} | {desc}")
            print(f"     {count}场/周末 | ROI/胜率:{roi_or_wr:+.1f}% | 稳定:{stability:.0f}%月盈利")
            total_weekend_signals += count
    
    print(f"\n周末信号总场次（有重叠）: ~{total_weekend_signals}场")
    print(f"周末比赛总数: {len(weekend)}场")
    print(f"信号覆盖率: ~{total_weekend_signals/len(weekend)*100:.1f}%")
    
    # ==================== 样本外验证 ====================
    print("\n" + "=" * 80)
    print("📊 样本外验证 - 用最近月份验证")
    print("=" * 80)
    
    # 按月份分组
    months = sorted(set(r['month'] for r in weekend))
    print(f"\n数据月份: {', '.join(months)}")
    
    if len(months) >= 2:
        train_months = months[:-1]
        test_month = months[-1]
        
        train_data = [r for r in weekend if r['month'] in train_months]
        test_data = [r for r in weekend if r['month'] == test_month]
        
        print(f"\n训练集: {', '.join(train_months)} ({len(train_data)}场)")
        print(f"测试集: {test_month} ({len(test_data)}场)")
        
        # 用最优信号测试
        print("\n【样本外测试】和量>45%+和凯利<96")
        conds = [('dvp', '>', 45), ('kd', '<', 96)]
        
        train_r = test_signal(train_data, conds, 'draw', 2.5)
        test_r = test_signal(test_data, conds, 'draw', 2.5)
        
        if train_r:
            print(f"  训练集: {train_r['count']}场 | ROI:{train_r['roi']:+.1f}%")
        if test_r:
            print(f"  测试集: {test_r['count']}场 | ROI:{test_r['roi']:+.1f}%")
            if test_r['roi'] > 0:
                print(f"  ✅ 样本外验证通过!")
            else:
                print(f"  ⚠️ 样本外为负，需调整")
        
        # 测试更宽松的信号
        print("\n【样本外测试】和量>42%")
        conds = [('dvp', '>', 42)]
        
        train_r = test_signal(train_data, conds, 'draw', 2.5)
        test_r = test_signal(test_data, conds, 'draw', 2.5)
        
        if train_r:
            print(f"  训练集: {train_r['count']}场 | ROI:{train_r['roi']:+.1f}%")
        if test_r:
            print(f"  测试集: {test_r['count']}场 | ROI:{test_r['roi']:+.1f}%")


if __name__ == "__main__":
    main()
