"""
FeatureExtractor - 特征提取器

从比赛JSON数据中提取核心指标，处理缺失字段。

核心指标:
- 成交量 (total_volume)
- 三方占比 (home_pct, draw_pct, away_pct)
- 盘口变化 (handicap_current, handicap_initial, handicap_change)
- 赔率变化 (home_odds, away_odds, home_odds_change, away_odds_change)
- 必发指数 (bfindex_home, bfindex_draw, bfindex_away)
- 凯利指数 (kelly_home, kelly_draw, kelly_away)
- 热度指数 (hot_home, hot_away)

Requirements: 4.1, 8.2
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MetricsData:
    """比赛指标数据类"""
    # 成交量
    total_volume: float = 0.0
    
    # 三方占比
    home_pct: float = 0.0
    draw_pct: float = 0.0
    away_pct: float = 0.0
    
    # 盘口数据
    handicap_current: float = 0.0
    handicap_initial: float = 0.0
    handicap_change: float = 0.0
    handicap_trend: str = ''
    handicap_str: str = ''
    
    # 赔率数据
    home_odds: float = 0.0
    away_odds: float = 0.0
    home_odds_change: float = 0.0
    away_odds_change: float = 0.0
    
    # 欧赔
    home_euro_odds: float = 0.0
    draw_euro_odds: float = 0.0
    away_euro_odds: float = 0.0
    
    # 必发指数
    bfindex_home: float = 0.0
    bfindex_draw: float = 0.0
    bfindex_away: float = 0.0
    
    # 凯利指数
    kelly_home: float = 0.0
    kelly_draw: float = 0.0
    kelly_away: float = 0.0
    
    # 热度指数
    hot_home: float = 0.0
    hot_away: float = 0.0
    
    # 凯利差值
    kelly_diff_home: float = 0.0
    kelly_diff_away: float = 0.0
    
    # 赔付率
    payout_home: float = 0.0
    payout_draw: float = 0.0
    payout_away: float = 0.0
    
    # 赢亏
    profit_home: float = 0.0
    profit_away: float = 0.0
    
    # 比赛信息
    match_info: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'total_volume': self.total_volume,
            'home_pct': self.home_pct,
            'draw_pct': self.draw_pct,
            'away_pct': self.away_pct,
            'handicap_current': self.handicap_current,
            'handicap_initial': self.handicap_initial,
            'handicap_change': self.handicap_change,
            'handicap_trend': self.handicap_trend,
            'handicap_str': self.handicap_str,
            'home_odds': self.home_odds,
            'away_odds': self.away_odds,
            'home_odds_change': self.home_odds_change,
            'away_odds_change': self.away_odds_change,
            'home_euro_odds': self.home_euro_odds,
            'draw_euro_odds': self.draw_euro_odds,
            'away_euro_odds': self.away_euro_odds,
            'bfindex_home': self.bfindex_home,
            'bfindex_draw': self.bfindex_draw,
            'bfindex_away': self.bfindex_away,
            'kelly_home': self.kelly_home,
            'kelly_draw': self.kelly_draw,
            'kelly_away': self.kelly_away,
            'hot_home': self.hot_home,
            'hot_away': self.hot_away,
            'kelly_diff_home': self.kelly_diff_home,
            'kelly_diff_away': self.kelly_diff_away,
            'payout_home': self.payout_home,
            'payout_draw': self.payout_draw,
            'payout_away': self.payout_away,
            'profit_home': self.profit_home,
            'profit_away': self.profit_away,
            'match_info': self.match_info,
        }


class FeatureExtractor:
    """
    特征提取器
    
    从比赛JSON数据中提取核心指标。
    """
    
    # 必需的核心指标字段
    REQUIRED_FIELDS = [
        'total_volume',
        'home_pct', 'draw_pct', 'away_pct',
        'handicap_current',
        'home_odds', 'away_odds',
        'bfindex_home', 'bfindex_away',
        'kelly_home', 'kelly_away',
        'hot_home', 'hot_away',
    ]
    
    def __init__(self):
        """初始化提取器"""
        pass
    
    def extract_metrics(self, data: Dict) -> Dict:
        """
        从比赛数据中提取核心指标
        
        Args:
            data: 比赛JSON数据，包含:
                - match_info: 比赛信息
                - handicap_data: 盘口数据
                - trade_data: 交易数据
                
        Returns:
            指标字典
        """
        trade_data = data.get('trade_data', {})
        trade_list = trade_data.get('data', [])
        handicap = data.get('handicap_data', {})
        
        # 获取最新一条交易数据
        latest = trade_list[0] if trade_list else {}
        
        # 提取各项指标
        metrics = MetricsData()
        
        # 成交量
        metrics.total_volume = self._safe_float(
            latest.get('总成交量') or latest.get('价位', 0)
        )
        
        # 三方占比
        metrics.home_pct = self._safe_float(
            latest.get('比例_主') or latest.get('额外列6', 0)
        )
        metrics.draw_pct = self._safe_float(
            latest.get('比例_和') or latest.get('额外列7', 0)
        )
        metrics.away_pct = self._safe_float(
            latest.get('比例_客') or latest.get('额外列8', 0)
        )
        
        # 盘口数据
        metrics.handicap_current = self._extract_handicap_current(data, handicap)
        metrics.handicap_initial = self._safe_float(handicap.get('initial_handicap', 0))
        metrics.handicap_change = metrics.handicap_initial - metrics.handicap_current
        metrics.handicap_trend = handicap.get('handicap_trend', '')
        metrics.handicap_str = handicap.get('current_handicap_text', '')
        
        # 赔率数据
        metrics.home_odds = self._safe_float(handicap.get('current_home_odds', 0))
        metrics.away_odds = self._safe_float(handicap.get('current_away_odds', 0))
        initial_home_odds = self._safe_float(handicap.get('initial_home_odds', 0))
        initial_away_odds = self._safe_float(handicap.get('initial_away_odds', 0))
        metrics.home_odds_change = metrics.home_odds - initial_home_odds
        metrics.away_odds_change = metrics.away_odds - initial_away_odds
        
        # 欧赔
        metrics.home_euro_odds = self._safe_float(latest.get('主胜_欧赔', 0))
        metrics.draw_euro_odds = self._safe_float(latest.get('和局_欧赔', 0))
        metrics.away_euro_odds = self._safe_float(latest.get('客胜_欧赔', 0))
        
        # 必发指数
        metrics.bfindex_home = self._safe_float(
            latest.get('必指_主') or latest.get('额外列12', 0)
        )
        metrics.bfindex_draw = self._safe_float(
            latest.get('必指_和') or latest.get('额外列13', 0)
        )
        metrics.bfindex_away = self._safe_float(
            latest.get('必指_客') or latest.get('额外列14', 0)
        )
        
        # 凯利指数
        metrics.kelly_home = self._safe_float(latest.get('凯利_主', 0))
        metrics.kelly_draw = self._safe_float(latest.get('凯利_和', 0))
        metrics.kelly_away = self._safe_float(latest.get('凯利_客', 0))
        
        # 热度指数
        metrics.hot_home = self._safe_float(
            latest.get('热指_主') or latest.get('额外列16', 0)
        )
        metrics.hot_away = self._safe_float(
            latest.get('热指_客') or latest.get('额外列17', 0)
        )
        
        # 凯利差值
        metrics.kelly_diff_home = self._safe_float(
            latest.get('凯差_主') or latest.get('额外列18', 0)
        )
        metrics.kelly_diff_away = self._safe_float(
            latest.get('凯差_客') or latest.get('额外列19', 0)
        )
        
        # 赔付率
        metrics.payout_home = self._safe_float(latest.get('赔付率_主', 0))
        metrics.payout_draw = self._safe_float(latest.get('赔付率_和', 0))
        metrics.payout_away = self._safe_float(latest.get('赔付率_客', 0))
        
        # 赢亏
        metrics.profit_home = self._safe_float(
            latest.get('赢亏_主') or latest.get('额外列20', 0)
        )
        metrics.profit_away = self._safe_float(
            latest.get('赢亏_客') or latest.get('额外列22', 0)
        )
        
        # 比赛信息
        metrics.match_info = data.get('match_info', {})
        
        return metrics.to_dict()

    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        安全转换为浮点数，处理None和字符串
        
        Args:
            value: 输入值
            default: 默认值
            
        Returns:
            浮点数
        """
        if value is None:
            return default
        
        try:
            # 处理带逗号的数字字符串
            if isinstance(value, str):
                value = value.replace(',', '')
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _extract_handicap_current(self, data: Dict, handicap: Dict) -> float:
        """
        提取当前盘口值
        
        优先从handicap_data读取，否则从raw.macth读取
        
        Args:
            data: 完整数据
            handicap: 盘口数据
            
        Returns:
            当前盘口值
        """
        current_handicap = self._safe_float(handicap.get('current_handicap', 0))
        
        if current_handicap == 0:
            # 尝试从raw.macth读取 (macth[21]是盘口)
            match_info = data.get('match_info', {})
            raw = match_info.get('raw', {})
            macth = raw.get('macth', '').split(',')
            if len(macth) > 21 and macth[21]:
                current_handicap = self._safe_float(macth[21])
        
        return current_handicap
    
    def validate_metrics(self, metrics: Dict) -> bool:
        """
        验证指标是否完整
        
        Args:
            metrics: 指标字典
            
        Returns:
            是否包含所有必需字段
        """
        for field in self.REQUIRED_FIELDS:
            if field not in metrics:
                return False
        return True
    
    def get_missing_fields(self, metrics: Dict) -> list:
        """
        获取缺失的字段列表
        
        Args:
            metrics: 指标字典
            
        Returns:
            缺失字段列表
        """
        missing = []
        for field in self.REQUIRED_FIELDS:
            if field not in metrics:
                missing.append(field)
        return missing
    
    def extract_from_dataframe(self, trade_data, metadata, handicap_data) -> Dict:
        """
        从DataFrame格式数据中提取指标（兼容旧接口）
        
        Args:
            trade_data: DataFrame格式的交易数据
            metadata: 元数据（list或dict）
            handicap_data: 盘口数据
            
        Returns:
            指标字典
        """
        # 统一metadata格式
        if isinstance(metadata, list):
            meta = {
                'league': metadata[0] if len(metadata) > 0 else '',
                'home': metadata[1] if len(metadata) > 1 else '',
                'away': metadata[2] if len(metadata) > 2 else ''
            }
        elif isinstance(metadata, dict):
            meta = metadata
        else:
            meta = {'league': str(metadata) if metadata else '', 'home': '', 'away': ''}
        
        # 构建JSON格式数据
        temp_data = {
            'match_info': {
                'league': meta.get('league', ''),
                'home_team': meta.get('home', ''),
                'away_team': meta.get('away', ''),
                'home': meta.get('home', ''),
                'away': meta.get('away', ''),
            },
            'handicap_data': handicap_data or {},
            'trade_data': {
                'data': trade_data.to_dict('records') if hasattr(trade_data, 'to_dict') else []
            }
        }
        
        return self.extract_metrics(temp_data)


# 便捷函数
def extract_metrics(data: Dict) -> Dict:
    """
    便捷函数：从比赛数据中提取核心指标
    
    Args:
        data: 比赛JSON数据
        
    Returns:
        指标字典
    """
    extractor = FeatureExtractor()
    return extractor.extract_metrics(data)
