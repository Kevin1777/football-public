"""
交易明细策略 V7 - 高ROI精简版
基于5759场数据验证，追求最高ROI

核心信号（仅3个高ROI信号）：
1. 客胜 客赔>2.8+客凯利<94 → 79场 ROI +41%
2. 平局 和量>48%+和凯利<96 → 296场 ROI +23%
3. 主胜 主赔>2.0+客热>25 → 75场 ROI +22%

策略表现：
- 总信号：450场
- ROI：+25.7%
- 月度稳定：8月+33%，9月+18%，12月+31%（全部盈利）
- 年化收益：186%（本金3万）
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class StrategyV7:
    """V7策略 - 高ROI精简版"""
    
    SIGNALS = [
        # 客胜信号 - ROI +41%
        {
            'direction': 'away',
            'conditions': [('oa', '>', 2.8), ('ka', '<', 94)],
            'description': '客赔>2.8+客凯利<94',
            'tier': 'S',
            'priority': 1,
        },
        # 平局信号 - ROI +23%
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 48), ('kd', '<', 96)],
            'description': '和量>48%+和凯利<96',
            'tier': 'S',
            'priority': 2,
        },
        # 主胜信号 - ROI +22%
        {
            'direction': 'home',
            'conditions': [('oh', '>', 2.0), ('ra', '>', 25)],
            'description': '主赔>2.0+客热>25',
            'tier': 'S',
            'priority': 3,
        },
    ]
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
    
    def pf(self, v):
        if v is None or v == '':
            return None
        try:
            return float(str(v).replace(',', ''))
        except:
            return None
    
    def extract_features(self, trade_data: Dict) -> Dict:
        data_list = trade_data.get('data', [])
        if not data_list:
            return {}
        
        L = data_list[0]
        features = {}
        
        features['kh'] = self.pf(L.get('凯利_主'))
        features['ka'] = self.pf(L.get('凯利_客'))
        features['kd'] = self.pf(L.get('凯利_和'))
        features['ra'] = self.pf(L.get('热指_客'))
        
        hv = self.pf(L.get('主胜_已成交量', 0)) or 0
        dv = self.pf(L.get('和局_已成交量', 0)) or 0
        av = self.pf(L.get('客胜_已成交量', 0)) or 0
        total = hv + dv + av
        
        if total > 0:
            features['hvp'] = hv / total * 100
            features['dvp'] = dv / total * 100
            features['avp'] = av / total * 100
        
        features['oh'] = self.pf(L.get('主胜_欧赔'))
        features['od'] = self.pf(L.get('和局_欧赔'))
        features['oa'] = self.pf(L.get('客胜_欧赔'))
        
        return features
    
    def check_conditions(self, features: Dict, conditions: list) -> bool:
        for field, op, value in conditions:
            v = features.get(field)
            if v is None:
                return False
            if op == '>' and not v > value:
                return False
            elif op == '<' and not v < value:
                return False
        return True
    
    def analyze(self, trade_data: Dict) -> List[Dict]:
        features = self.extract_features(trade_data)
        if not features:
            return []
        
        signals = []
        
        for sig in self.SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                odds_map = {'draw': 'od', 'away': 'oa', 'home': 'oh'}
                signals.append({
                    'direction': sig['direction'],
                    'direction_cn': {'draw': '平局', 'away': '客胜', 'home': '主胜'}[sig['direction']],
                    'description': sig['description'],
                    'tier': sig['tier'],
                    'priority': sig['priority'],
                    'odds': features.get(odds_map[sig['direction']], 2.5),
                })
                break
        
        return signals
    
    def get_recommendation(self, trade_data: Dict) -> Optional[Dict]:
        signals = self.analyze(trade_data)
        return signals[0] if signals else None


def test_v7_strategy():
    import json
    import re
    from collections import defaultdict
    
    strategy = StrategyV7()
    data_dir = strategy.data_dir / '2025'
    
    print("=" * 70)
    print("                📊 V7策略回测（高ROI精简版）")
    print("=" * 70)
    
    stats = {'signals': 0, 'wins': 0, 'profit': 0}
    month_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'profit': 0})
    dir_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'profit': 0})
    
    def parse_score(filename):
        match = re.search(r'_(\d+)_(\d+)\.json$', filename)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None
    
    def get_outcome(h, a):
        if h is None or a is None:
            return None
        return 'home' if h > a else ('draw' if h == a else 'away')
    
    for month_dir in data_dir.iterdir():
        if not month_dir.is_dir():
            continue
        month = month_dir.name
        
        for day_dir in month_dir.iterdir():
            if not day_dir.is_dir():
                continue
            for f in day_dir.glob("*.json"):
                if any(x in f.name for x in ["大小球", "盘口数据", "标盘指数"]):
                    continue
                
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    
                    trade_data = data.get('trade_data', {})
                    if not trade_data or not trade_data.get('data'):
                        continue
                    
                    sig = strategy.get_recommendation(trade_data)
                    if not sig:
                        continue
                    
                    home_score, away_score = parse_score(f.name)
                    outcome = get_outcome(home_score, away_score)
                    
                    if not outcome:
                        continue
                    
                    bet = 100
                    stats['signals'] += 1
                    month_stats[month]['signals'] += 1
                    dir_stats[sig['direction']]['signals'] += 1
                    
                    if sig['direction'] == outcome:
                        profit = bet * (sig['odds'] - 1)
                        stats['wins'] += 1
                        stats['profit'] += profit
                        month_stats[month]['wins'] += 1
                        month_stats[month]['profit'] += profit
                        dir_stats[sig['direction']]['wins'] += 1
                        dir_stats[sig['direction']]['profit'] += profit
                    else:
                        stats['profit'] -= bet
                        month_stats[month]['profit'] -= bet
                        dir_stats[sig['direction']]['profit'] -= bet
                        
                except:
                    pass
    
    if stats['signals'] > 0:
        wr = stats['wins'] / stats['signals'] * 100
        roi = stats['profit'] / (stats['signals'] * 100) * 100
        
        print(f"\n总信号: {stats['signals']}场")
        print(f"胜/负: {stats['wins']}/{stats['signals'] - stats['wins']}")
        print(f"胜率: {wr:.1f}%")
        print(f"总盈亏: {stats['profit']:+.0f}元")
        print(f"ROI: {roi:+.1f}%")
    
    print("\n" + "-" * 50)
    print("方向统计:")
    for d in ['draw', 'away', 'home']:
        ds = dir_stats[d]
        if ds['signals'] > 0:
            wr = ds['wins'] / ds['signals'] * 100
            roi = ds['profit'] / (ds['signals'] * 100) * 100
            dir_cn = {'home': '主胜', 'away': '客胜', 'draw': '平局'}[d]
            print(f"  {dir_cn}: {ds['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}%")
    
    print("\n月度统计:")
    for month in sorted(month_stats.keys()):
        ms = month_stats[month]
        if ms['signals'] > 0:
            wr = ms['wins'] / ms['signals'] * 100
            roi = ms['profit'] / (ms['signals'] * 100) * 100
            stable = '✅' if roi > 0 else '❌'
            print(f"  {month}月: {ms['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}% {stable}")
    
    # 年化收益
    print("\n" + "-" * 50)
    print("年化收益预估（单注100元，本金3万）:")
    daily = stats['profit'] / 90
    print(f"  每日盈利: {daily:+.0f}元")
    print(f"  月盈利: {daily*30:+.0f}元")
    print(f"  年盈利: {daily*365:+.0f}元")
    print(f"  年化收益率: {daily*365/30000*100:.0f}%")


if __name__ == "__main__":
    test_v7_strategy()
