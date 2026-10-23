"""
交易明细策略 - 简化版（防过拟合）

设计原则：
1. 减少条件数量（每个信号最多2个条件）
2. 优先使用大样本信号（>200场）
3. 避免过于精确的阈值
4. 保留逻辑清晰的核心信号

核心逻辑：
- 平局：和量集中 = 市场共识平局
- 客胜：客队被低估（凯利<94）+ 有价值（赔率>2.2）
- 主胜：反向信号（客热高但庄家怕客）
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SimplifiedStrategy:
    """简化版策略 - 防过拟合"""
    
    # ==================== 简化后的信号 ====================
    
    # 核心信号1：平局（最稳定，样本最大）
    # 逻辑：和局成交量占比高 = 市场资金集中押平局
    DRAW_SIGNALS = [
        # 418场验证，ROI +10.4%，单条件最稳健
        {
            'conditions': [('dvp', '>', 45)],
            'description': '和量>45%',
            'sample_size': 418,
            'historical_roi': 0.104,
        },
        # 298场验证，ROI +14.6%
        {
            'conditions': [('dvp', '>', 50)],
            'description': '和量>50%',
            'sample_size': 298,
            'historical_roi': 0.146,
        },
    ]
    
    # 核心信号2：客胜价值型（样本大）
    # 逻辑：客队凯利低 = 被低估，赔率高 = 有价值
    AWAY_SIGNALS = [
        # 380场验证，ROI +3.0%
        {
            'conditions': [('oa', '>', 2.2), ('ka', '<', 94)],
            'description': '客赔>2.2+客凯利<94',
            'sample_size': 380,
            'historical_roi': 0.03,
        },
    ]
    
    # 核心信号3：主胜反向型（中等样本）
    # 逻辑：客热高+庄家怕客 = 诱多信号，反向买主胜
    HOME_SIGNALS = [
        # 245场验证，ROI +3.5%（放宽条件，增加样本）
        {
            'conditions': [('oh', '>', 2.0), ('ra', '>', 20)],
            'description': '主赔>2.0+客热>20',
            'sample_size': 245,
            'historical_roi': 0.035,
        },
    ]
    
    # 删除的信号（过拟合风险高）：
    # - Tier 1 低赔信号：样本<60场，条件过多
    # - Tier 2 高EV信号：样本<80场，条件3个以上
    # - 任何包含"怕客<-15"的信号：阈值过于精确
    
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
        
        # 基础指标
        field_map = {
            '凯利_主': 'kh', '凯利_客': 'ka', '凯利_和': 'kd',
            '赢亏_主': 'yh', '赢亏_客': 'ya', '赢亏_和': 'yd',
            '热指_主': 'rh', '热指_客': 'ra', '热指_和': 'rd',
        }
        
        for cn_key, en_key in field_map.items():
            features[en_key] = self.pf(L.get(cn_key))
        
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
        
        # 检查平局信号（优先级最高）
        for sig in self.DRAW_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'draw',
                    'direction_cn': '平局',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'odds': features.get('od', 3.0),
                    'confidence': 'high' if sig['sample_size'] >= 300 else 'medium',
                })
        
        # 检查客胜信号
        for sig in self.AWAY_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'away',
                    'direction_cn': '客胜',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'odds': features.get('oa', 2.5),
                    'confidence': 'high' if sig['sample_size'] >= 300 else 'medium',
                })
        
        # 检查主胜信号
        for sig in self.HOME_SIGNALS:
            if self.check_conditions(features, sig['conditions']):
                signals.append({
                    'direction': 'home',
                    'direction_cn': '主胜',
                    'description': sig['description'],
                    'sample_size': sig['sample_size'],
                    'historical_roi': sig['historical_roi'],
                    'odds': features.get('oh', 2.0),
                    'confidence': 'high' if sig['sample_size'] >= 300 else 'medium',
                })
        
        # 按样本量排序（样本越大越可靠）
        signals.sort(key=lambda x: -x['sample_size'])
        
        return signals
    
    def get_recommendation(self, trade_data: Dict) -> Optional[Dict]:
        """获取最优推荐"""
        signals = self.analyze(trade_data)
        return signals[0] if signals else None


def compare_strategies():
    """对比原策略和简化策略"""
    from 交易明细策略 import TradeDetailStrategy
    
    original = TradeDetailStrategy()
    simplified = SimplifiedStrategy()
    data_dir = simplified.data_dir
    
    print("=" * 70)
    print("📊 策略对比分析")
    print("=" * 70)
    
    # 统计
    orig_signals = 0
    simp_signals = 0
    both_signals = 0
    
    dates = ['2025-12-05', '2025-12-06', '2025-12-07']
    
    for date_str in dates:
        year, month, day = date_str.split('-')
        day_dir = data_dir / year / month / day
        
        if not day_dir.exists():
            continue
        
        for f in day_dir.glob("*.json"):
            if any(x in f.name for x in ["大小球", "盘口数据", "标盘指数"]):
                continue
            
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                
                trade_data = data.get('trade_data', {})
                
                orig = original.analyze(trade_data, data.get('handicap_data', {}))
                simp = simplified.analyze(trade_data)
                
                if orig:
                    orig_signals += 1
                if simp:
                    simp_signals += 1
                if orig and simp:
                    both_signals += 1
                    
            except:
                pass
    
    print(f"\n原策略信号数: {orig_signals}")
    print(f"简化策略信号数: {simp_signals}")
    print(f"重叠信号数: {both_signals}")
    print(f"\n简化策略减少了 {orig_signals - simp_signals} 个信号")
    print("（减少的主要是小样本、多条件的高风险信号）")


if __name__ == "__main__":
    compare_strategies()
