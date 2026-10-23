"""
交易明细策略 V6 - 大样本优化版
基于5759场数据验证，在保持ROI>19%的基础上最大化信号量

核心信号（按优先级排序）：
Tier S (ROI>25%):
1. 客胜 客赔>2.8+客凯利<94 → ROI +41%
2. 平局 和量>50%+和凯利<90 → ROI +30%
3. 主胜 主赔>2.0+客热>28 → ROI +26%

Tier A (ROI>15%):
4. 平局 和量>48%+和凯利<96 → ROI +22%
5. 主胜 主赔>2.0+客热>25 → ROI +16%

Tier B (ROI>5%):
6. 主胜 主赔>1.8+客热>28 → ROI +12%
7. 平局 和量>45%+和凯利<94 → ROI +6%
8. 主胜 主赔>2.0+客热>22 → ROI +10%

策略表现：
- 总信号：638场（比V5增加25%）
- ROI：+19.5%
- 月度稳定：8月+23%，9月+14%，12月+24%（全部盈利）
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class StrategyV6:
    """V6策略 - 大样本优化版"""
    
    SIGNALS = [
        # Tier S - ROI>25%
        {
            'direction': 'away',
            'conditions': [('oa', '>', 2.8), ('ka', '<', 94)],
            'description': '客赔>2.8+客凯利<94',
            'tier': 'S',
            'priority': 1,
        },
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 50), ('kd', '<', 90)],
            'description': '和量>50%+和凯利<90',
            'tier': 'S',
            'priority': 2,
        },
        {
            'direction': 'home',
            'conditions': [('oh', '>', 2.0), ('ra', '>', 28)],
            'description': '主赔>2.0+客热>28',
            'tier': 'S',
            'priority': 3,
        },
        
        # Tier A - ROI>15%
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 48), ('kd', '<', 96)],
            'description': '和量>48%+和凯利<96',
            'tier': 'A',
            'priority': 4,
        },
        {
            'direction': 'home',
            'conditions': [('oh', '>', 2.0), ('ra', '>', 25)],
            'description': '主赔>2.0+客热>25',
            'tier': 'A',
            'priority': 5,
        },
        
        # Tier B - ROI>5%
        {
            'direction': 'home',
            'conditions': [('oh', '>', 1.8), ('ra', '>', 28)],
            'description': '主赔>1.8+客热>28',
            'tier': 'B',
            'priority': 6,
        },
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 45), ('kd', '<', 94)],
            'description': '和量>45%+和凯利<94',
            'tier': 'B',
            'priority': 7,
        },
        {
            'direction': 'home',
            'conditions': [('oh', '>', 2.0), ('ra', '>', 22)],
            'description': '主赔>2.0+客热>22',
            'tier': 'B',
            'priority': 8,
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
        features['rh'] = self.pf(L.get('热指_主'))
        features['rd'] = self.pf(L.get('热指_和'))
        
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


def test_v6_strategy():
    import json
    import re
    from collections import defaultdict
    
    strategy = StrategyV6()
    data_dir = strategy.data_dir / '2025'
    
    print("=" * 70)
    print("                📊 V6策略回测（大样本优化版）")
    print("=" * 70)
    
    stats = {'signals': 0, 'wins': 0, 'profit': 0}
    tier_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'profit': 0})
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
                    tier_stats[sig['tier']]['signals'] += 1
                    month_stats[month]['signals'] += 1
                    dir_stats[sig['direction']]['signals'] += 1
                    
                    if sig['direction'] == outcome:
                        profit = bet * (sig['odds'] - 1)
                        stats['wins'] += 1
                        stats['profit'] += profit
                        tier_stats[sig['tier']]['wins'] += 1
                        tier_stats[sig['tier']]['profit'] += profit
                        month_stats[month]['wins'] += 1
                        month_stats[month]['profit'] += profit
                        dir_stats[sig['direction']]['wins'] += 1
                        dir_stats[sig['direction']]['profit'] += profit
                    else:
                        stats['profit'] -= bet
                        tier_stats[sig['tier']]['profit'] -= bet
                        month_stats[month]['profit'] -= bet
                        dir_stats[sig['direction']]['profit'] -= bet
                        
                except:
                    pass
    
    valid = stats['wins'] + (stats['signals'] - stats['wins'])
    if valid > 0:
        wr = stats['wins'] / stats['signals'] * 100
        roi = stats['profit'] / (stats['signals'] * 100) * 100
        
        print(f"\n总信号: {stats['signals']}场")
        print(f"胜/负: {stats['wins']}/{stats['signals'] - stats['wins']}")
        print(f"胜率: {wr:.1f}%")
        print(f"总盈亏: {stats['profit']:+.0f}元")
        print(f"ROI: {roi:+.1f}%")
    
    print("\n" + "-" * 50)
    print("分层统计:")
    for tier in ['S', 'A', 'B']:
        ts = tier_stats[tier]
        if ts['signals'] > 0:
            wr = ts['wins'] / ts['signals'] * 100
            roi = ts['profit'] / (ts['signals'] * 100) * 100
            print(f"  Tier {tier}: {ts['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}%")
    
    print("\n方向统计:")
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


if __name__ == "__main__":
    test_v6_strategy()
