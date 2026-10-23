"""
交易明细策略 V4 - 最终优化版
基于5759场数据验证，专注高ROI+月度稳定

核心信号（按优先级排序）：
1. 平局 和量>50%+和凯利<90 → 108场 ROI +30.4% ⭐⭐⭐ Tier S
2. 客胜 客赔>3.0+客凯利<94 → 50场 ROI +36.6% ⭐⭐⭐ Tier S
3. 平局 和量>50%+和凯利<96 → 264场 ROI +19.6% ⭐⭐ Tier A

策略表现：
- 总信号：313场
- ROI：+22.7%
- 月度稳定：8月+29.4%，9月+15.9%，12月+25.0%（全部盈利）

相比V3策略：
- ROI从+15.1%提升到+22.7%（提升50%）
- 信号数从496场减少到313场（更精准）
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class StrategyV4:
    """V4策略 - 高ROI+月度稳定"""
    
    # ==================== 核心信号（按优先级排序）====================
    
    SIGNALS = [
        # Tier S - 最高优先级，ROI>25%
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 50), ('kd', '<', 90)],
            'description': '和量>50%+和凯利<90',
            'sample_size': 108,
            'historical_roi': 0.304,
            'tier': 'S',
            'priority': 1,
        },
        {
            'direction': 'away',
            'conditions': [('oa', '>', 3.0), ('ka', '<', 94)],
            'description': '客赔>3.0+客凯利<94',
            'sample_size': 50,
            'historical_roi': 0.366,
            'tier': 'S',
            'priority': 2,
        },
        
        # Tier A - 高优先级，ROI>15%
        {
            'direction': 'draw',
            'conditions': [('dvp', '>', 50), ('kd', '<', 96)],
            'description': '和量>50%+和凯利<96',
            'sample_size': 264,
            'historical_roi': 0.196,
            'tier': 'A',
            'priority': 3,
        },
    ]
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
    
    def pf(self, v):
        """解析浮点数"""
        if v is None or v == '':
            return None
        try:
            return float(str(v).replace(',', ''))
        except:
            return None
    
    def extract_features(self, trade_data: Dict) -> Dict:
        """从交易数据中提取特征"""
        data_list = trade_data.get('data', [])
        if not data_list:
            return {}
        
        L = data_list[0]
        features = {}
        
        # 凯利指数
        features['kh'] = self.pf(L.get('凯利_主'))
        features['ka'] = self.pf(L.get('凯利_客'))
        features['kd'] = self.pf(L.get('凯利_和'))
        
        # 成交量占比
        hv = self.pf(L.get('主胜_已成交量', 0)) or 0
        dv = self.pf(L.get('和局_已成交量', 0)) or 0
        av = self.pf(L.get('客胜_已成交量', 0)) or 0
        total = hv + dv + av
        
        if total > 0:
            features['hvp'] = hv / total * 100
            features['dvp'] = dv / total * 100
            features['avp'] = av / total * 100
        
        features['tv'] = self.pf(L.get('总成交量')) or 0
        
        # 欧赔
        features['oh'] = self.pf(L.get('主胜_欧赔'))
        features['od'] = self.pf(L.get('和局_欧赔'))
        features['oa'] = self.pf(L.get('客胜_欧赔'))
        
        return features
    
    def check_conditions(self, features: Dict, conditions: list) -> bool:
        """检查条件"""
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
        """分析并返回信号"""
        features = self.extract_features(trade_data)
        if not features:
            return []
        
        signals = []
        
        # 按优先级检查信号
        for sig in self.SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                odds_map = {'draw': 'od', 'away': 'oa', 'home': 'oh'}
                signals.append({
                    'direction': sig['direction'],
                    'direction_cn': {'draw': '平局', 'away': '客胜', 'home': '主胜'}[sig['direction']],
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'tier': sig['tier'],
                    'priority': sig['priority'],
                    'odds': features.get(odds_map[sig['direction']], 2.5),
                })
                break  # 只取第一个匹配的（最高优先级）
        
        return signals
    
    def get_recommendation(self, trade_data: Dict) -> Optional[Dict]:
        """获取最优推荐"""
        signals = self.analyze(trade_data)
        return signals[0] if signals else None


def test_v4_strategy():
    """测试V4策略"""
    import json
    import re
    from collections import defaultdict
    
    strategy = StrategyV4()
    data_dir = strategy.data_dir / '2025'
    
    print("=" * 70)
    print("                📊 V4策略回测（高ROI+月度稳定）")
    print("=" * 70)
    
    stats = {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0}
    tier_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})
    dir_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})
    month_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})
    
    def parse_score(filename):
        match = re.search(r'_(\d+)_(\d+)\.json$', filename)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None
    
    def get_outcome(h, a):
        if h is None or a is None:
            return None
        if h > a:
            return 'home'
        elif h == a:
            return 'draw'
        else:
            return 'away'
    
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
                    dir_stats[sig['direction']]['signals'] += 1
                    month_stats[month]['signals'] += 1
                    
                    if sig['direction'] == outcome:
                        profit = bet * (sig['odds'] - 1)
                        stats['wins'] += 1
                        stats['profit'] += profit
                        tier_stats[sig['tier']]['wins'] += 1
                        tier_stats[sig['tier']]['profit'] += profit
                        dir_stats[sig['direction']]['wins'] += 1
                        dir_stats[sig['direction']]['profit'] += profit
                        month_stats[month]['wins'] += 1
                        month_stats[month]['profit'] += profit
                    else:
                        stats['losses'] += 1
                        stats['profit'] -= bet
                        tier_stats[sig['tier']]['losses'] += 1
                        tier_stats[sig['tier']]['profit'] -= bet
                        dir_stats[sig['direction']]['losses'] += 1
                        dir_stats[sig['direction']]['profit'] -= bet
                        month_stats[month]['losses'] += 1
                        month_stats[month]['profit'] -= bet
                        
                except:
                    pass
    
    # 输出结果
    valid = stats['wins'] + stats['losses']
    if valid > 0:
        wr = stats['wins'] / valid * 100
        roi = stats['profit'] / (stats['signals'] * 100) * 100
        
        print(f"\n总信号: {stats['signals']}场")
        print(f"胜/负: {stats['wins']}/{stats['losses']}")
        print(f"胜率: {wr:.1f}%")
        print(f"总盈亏: {stats['profit']:+.0f}元")
        print(f"ROI: {roi:+.1f}%")
    
    print("\n" + "-" * 50)
    print("分层统计:")
    for tier in ['S', 'A']:
        ts = tier_stats[tier]
        v = ts['wins'] + ts['losses']
        if v > 0:
            wr = ts['wins'] / v * 100
            roi = ts['profit'] / (ts['signals'] * 100) * 100
            print(f"  Tier {tier}: {ts['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}%")
    
    print("\n方向统计:")
    for d in ['draw', 'away']:
        ds = dir_stats[d]
        v = ds['wins'] + ds['losses']
        if v > 0:
            wr = ds['wins'] / v * 100
            roi = ds['profit'] / (ds['signals'] * 100) * 100
            dir_cn = {'home': '主胜', 'away': '客胜', 'draw': '平局'}[d]
            print(f"  {dir_cn}: {ds['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}%")
    
    print("\n月度统计:")
    for month in sorted(month_stats.keys()):
        ms = month_stats[month]
        v = ms['wins'] + ms['losses']
        if v > 0:
            wr = ms['wins'] / v * 100
            roi = ms['profit'] / (ms['signals'] * 100) * 100
            stable = '✅' if roi > 0 else '❌'
            print(f"  {month}月: {ms['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}% {stable}")


if __name__ == "__main__":
    test_v4_strategy()
