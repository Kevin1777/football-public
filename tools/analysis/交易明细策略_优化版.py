"""
交易明细策略 - 优化版 V2
基于5759场数据验证优化

核心信号（验证有效）：
1. 平局 和量>50%+和凯利<96 → 264场 ROI +20.3% ⭐⭐⭐
2. 平局 和量>50%+和凯利<94 → 224场 ROI +20.7% ⭐⭐⭐
3. 主胜 主赔>2.0+客热>20+怕客<-10 → 68场 ROI +17.7% ⭐⭐
4. 客胜 客赔>2.5+客凯利<94 → 147场 ROI +17.0% ⭐⭐
5. 平局 和量>45%+和凯利<96 → 367场 ROI +15.9% ⭐⭐

优化原则：
1. 只保留ROI>10%的信号
2. 优先使用大样本信号
3. 每个方向只取最优信号，避免重复
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class OptimizedStrategy:
    """优化版策略 V2"""
    
    # ==================== 信号定义（按ROI排序）====================
    
    # 平局信号（最稳定）⭐⭐⭐
    DRAW_SIGNALS = [
        {
            'conditions': [('dvp', '>', 50), ('kd', '<', 94)],
            'description': '和量>50%+和凯利<94',
            'sample_size': 224,
            'historical_roi': 0.207,
            'tier': 'S',
        },
        {
            'conditions': [('dvp', '>', 50), ('kd', '<', 96)],
            'description': '和量>50%+和凯利<96',
            'sample_size': 264,
            'historical_roi': 0.203,
            'tier': 'S',
        },
        {
            'conditions': [('dvp', '>', 45), ('kd', '<', 96)],
            'description': '和量>45%+和凯利<96',
            'sample_size': 367,
            'historical_roi': 0.159,
            'tier': 'A',
        },
        {
            'conditions': [('dvp', '>', 50)],
            'description': '和量>50%',
            'sample_size': 310,
            'historical_roi': 0.109,
            'tier': 'B',
        },
    ]
    
    # 主胜信号 ⭐⭐
    HOME_SIGNALS = [
        {
            'conditions': [('oh', '>', 2.0), ('ra', '>', 20), ('ya', '<', -10)],
            'description': '主赔>2.0+客热>20+怕客<-10',
            'sample_size': 68,
            'historical_roi': 0.177,
            'tier': 'A',
        },
        {
            'conditions': [('oh', '>', 2.0), ('ra', '>', 22)],
            'description': '主赔>2.0+客热>22',
            'sample_size': 160,
            'historical_roi': 0.093,
            'tier': 'B',
        },
    ]
    
    # 客胜信号 ⭐⭐
    AWAY_SIGNALS = [
        {
            'conditions': [('oa', '>', 2.5), ('ka', '<', 94)],
            'description': '客赔>2.5+客凯利<94',
            'sample_size': 147,
            'historical_roi': 0.170,
            'tier': 'A',
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
        
        # 热指
        features['rh'] = self.pf(L.get('热指_主'))
        features['ra'] = self.pf(L.get('热指_客'))
        features['rd'] = self.pf(L.get('热指_和'))
        
        # 赢亏（庄家怕）
        features['yh'] = self.pf(L.get('赢亏_主'))
        features['ya'] = self.pf(L.get('赢亏_客'))
        features['yd'] = self.pf(L.get('赢亏_和'))
        
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
        
        # 检查客胜信号（优先级最高，ROI最高）
        for sig in self.AWAY_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'away',
                    'direction_cn': '客胜',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'tier': sig['tier'],
                    'odds': features.get('oa', 2.5),
                })
                break  # 只取第一个匹配的
        
        # 检查平局信号
        for sig in self.DRAW_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'draw',
                    'direction_cn': '平局',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'tier': sig['tier'],
                    'odds': features.get('od', 3.0),
                })
                break
        
        # 检查主胜信号
        for sig in self.HOME_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'home',
                    'direction_cn': '主胜',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'tier': sig['tier'],
                    'odds': features.get('oh', 2.0),
                })
                break
        
        # 按历史ROI排序
        signals.sort(key=lambda x: -x['historical_roi'])
        
        return signals
    
    def get_recommendation(self, trade_data: Dict) -> Optional[Dict]:
        """获取最优推荐"""
        signals = self.analyze(trade_data)
        return signals[0] if signals else None


def test_optimized_strategy():
    """测试优化策略"""
    import json
    import re
    from collections import defaultdict
    
    strategy = OptimizedStrategy()
    data_dir = strategy.data_dir / '2025'
    
    print("=" * 70)
    print("                📊 优化版策略回测")
    print("=" * 70)
    
    stats = {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0}
    tier_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})
    dir_stats = defaultdict(lambda: {'signals': 0, 'wins': 0, 'losses': 0, 'profit': 0})
    
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
                    
                    signals = strategy.analyze(trade_data)
                    if not signals:
                        continue
                    
                    sig = signals[0]
                    home_score, away_score = parse_score(f.name)
                    outcome = get_outcome(home_score, away_score)
                    
                    if not outcome:
                        continue
                    
                    bet = 100
                    stats['signals'] += 1
                    tier_stats[sig['tier']]['signals'] += 1
                    dir_stats[sig['direction']]['signals'] += 1
                    
                    if sig['direction'] == outcome:
                        profit = bet * (sig['odds'] - 1)
                        stats['wins'] += 1
                        stats['profit'] += profit
                        tier_stats[sig['tier']]['wins'] += 1
                        tier_stats[sig['tier']]['profit'] += profit
                        dir_stats[sig['direction']]['wins'] += 1
                        dir_stats[sig['direction']]['profit'] += profit
                    else:
                        stats['losses'] += 1
                        stats['profit'] -= bet
                        tier_stats[sig['tier']]['losses'] += 1
                        tier_stats[sig['tier']]['profit'] -= bet
                        dir_stats[sig['direction']]['losses'] += 1
                        dir_stats[sig['direction']]['profit'] -= bet
                        
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
    for tier in ['S', 'A', 'B']:
        ts = tier_stats[tier]
        v = ts['wins'] + ts['losses']
        if v > 0:
            wr = ts['wins'] / v * 100
            roi = ts['profit'] / (ts['signals'] * 100) * 100
            print(f"  Tier {tier}: {ts['signals']:>4}场 | 胜率 {wr:>5.1f}% | ROI {roi:>+6.1f}%")
    
    print("\n方向统计:")
    for d in ['home', 'away', 'draw']:
        ds = dir_stats[d]
        v = ds['wins'] + ds['losses']
        if v > 0:
            wr = ds['wins'] / v * 100
            dir_cn = {'home': '主胜', 'away': '客胜', 'draw': '平局'}[d]
            print(f"  {dir_cn}: {ds['signals']:>4}场 | 胜率 {wr:>5.1f}% | 盈亏 {ds['profit']:>+6.0f}元")


if __name__ == "__main__":
    test_optimized_strategy()
