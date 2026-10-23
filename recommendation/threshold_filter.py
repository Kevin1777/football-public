"""
DynamicThresholdFilter - 动态阈值过滤器

根据比赛特征动态调整推荐阈值，过滤低质量推荐。

核心过滤规则:
1. 成交量过滤: volume < 50K 拒绝推荐
2. 深盘过滤: handicap > 2.0 拒绝推荐
3. 评分差值过滤: score_diff < 20 拒绝推荐
4. 浅盘顺盘过滤: handicap < 1.0 且顺盘时过滤

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """过滤结果数据类"""
    should_recommend: bool
    reason: str
    filter_type: str  # 'volume' | 'deep_handicap' | 'score_diff' | 'shallow_handicap' | 'pass'


class DynamicThresholdFilter:
    """
    动态阈值过滤器
    
    根据比赛特征判断是否应该推荐。
    """
    
    # 过滤阈值常量
    MIN_VOLUME = 50000           # 最小成交量 50K
    MAX_HANDICAP_DEPTH = 2.0     # 最大盘口深度
    MIN_SCORE_DIFF = 20          # 最小评分差值
    SHALLOW_HANDICAP = 1.0       # 浅盘阈值
    
    # 一级联赛列表
    TIER1_LEAGUES = {
        # 五大联赛
        '英超', '西甲', '德甲', '意甲', '法甲',
        # 五大联赛二级
        '英冠', '西乙', '德乙', '意乙', '法乙',
        # 欧战
        '欧冠杯', '欧罗巴杯', '欧会杯', '欧联杯',
        # 其他顶级联赛
        '中超', '葡超', '荷甲', '比甲', '土超', '苏超',
        '巴西甲', '阿甲', '美职业', '墨西联',
        '日职联', '日职乙', '韩K联', '澳超',
        # 杯赛
        '英足总杯', '英联杯', '德国杯', '西班牙杯', '意大利杯', '法国杯',
        # 亚冠
        '亚冠联', '亚冠精英', '亚冠联2'
    }
    
    def __init__(self):
        """初始化过滤器"""
        pass
    
    def should_recommend(
        self, 
        metrics: Dict, 
        score_home: float, 
        score_away: float,
        direction: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        判断是否应该推荐
        
        Args:
            metrics: 比赛指标字典
            score_home: 主队评分
            score_away: 客队评分
            direction: 推荐方向 (可选，用于浅盘顺盘过滤)
            
        Returns:
            (should_recommend, reason): 是否推荐及原因
        """
        # 1. 成交量过滤
        volume_result = self._filter_by_volume(metrics)
        if not volume_result.should_recommend:
            return False, volume_result.reason
        
        # 2. 深盘过滤
        handicap_result = self._filter_by_deep_handicap(metrics)
        if not handicap_result.should_recommend:
            return False, handicap_result.reason
        
        # 3. 评分差值过滤
        score_diff_result = self._filter_by_score_diff(score_home, score_away)
        if not score_diff_result.should_recommend:
            return False, score_diff_result.reason
        
        # 4. 浅盘顺盘过滤 (如果提供了方向)
        if direction:
            shallow_result = self._filter_by_shallow_handicap(metrics, direction)
            if not shallow_result.should_recommend:
                return False, shallow_result.reason
        
        return True, "通过所有过滤条件"
    
    def _filter_by_volume(self, metrics: Dict) -> FilterResult:
        """
        成交量过滤
        
        条件: 成交量 < 50K 时拒绝推荐
        
        Args:
            metrics: 比赛指标
            
        Returns:
            FilterResult
        """
        volume = float(metrics.get('total_volume', 0) or 0)
        
        if volume < self.MIN_VOLUME:
            return FilterResult(
                should_recommend=False,
                reason=f"成交量{volume/1000:.0f}K过低，低于{self.MIN_VOLUME/1000:.0f}K阈值",
                filter_type='volume'
            )
        
        return FilterResult(
            should_recommend=True,
            reason="成交量充足",
            filter_type='pass'
        )
    
    def _filter_by_deep_handicap(self, metrics: Dict) -> FilterResult:
        """
        深盘过滤
        
        条件: 盘口深度 > 2.0 时拒绝推荐
        
        Args:
            metrics: 比赛指标
            
        Returns:
            FilterResult
        """
        handicap = float(metrics.get('handicap_current', 0) or 0)
        abs_handicap = abs(handicap)
        
        if abs_handicap >= self.MAX_HANDICAP_DEPTH:
            return FilterResult(
                should_recommend=False,
                reason=f"超深盘{abs_handicap}跳过，超过{self.MAX_HANDICAP_DEPTH}阈值",
                filter_type='deep_handicap'
            )
        
        return FilterResult(
            should_recommend=True,
            reason="盘口深度正常",
            filter_type='pass'
        )
    
    def _filter_by_score_diff(
        self, 
        score_home: float, 
        score_away: float
    ) -> FilterResult:
        """
        评分差值过滤
        
        条件: 评分差值 < 20 时拒绝推荐
        
        Args:
            score_home: 主队评分
            score_away: 客队评分
            
        Returns:
            FilterResult
        """
        score_diff = abs(score_home - score_away)
        
        if score_diff < self.MIN_SCORE_DIFF:
            return FilterResult(
                should_recommend=False,
                reason=f"评分不足(主{score_home:.0f}/客{score_away:.0f},差{score_diff:.0f})",
                filter_type='score_diff'
            )
        
        return FilterResult(
            should_recommend=True,
            reason="评分差值充足",
            filter_type='pass'
        )

    
    def _filter_by_shallow_handicap(
        self, 
        metrics: Dict, 
        direction: str
    ) -> FilterResult:
        """
        浅盘顺盘过滤
        
        条件: 浅中盘(<1.0) 且 顺盘时过滤不推荐
        
        顺盘定义:
        - 主队推荐 + 主队让球 (handicap < 0)
        - 客队推荐 + 客队让球 (handicap > 0)
        
        Args:
            metrics: 比赛指标
            direction: 推荐方向 ('home' | 'away')
            
        Returns:
            FilterResult
        """
        handicap = float(metrics.get('handicap_current', 0) or 0)
        abs_handicap = abs(handicap)
        
        # 只过滤浅中盘
        if abs_handicap >= self.SHALLOW_HANDICAP:
            return FilterResult(
                should_recommend=True,
                reason="非浅盘，不过滤",
                filter_type='pass'
            )
        
        # 判断是否顺盘
        is_shun_pan = False
        if direction == 'home' and handicap < 0:
            # 主队推荐 + 主队让球 = 顺盘
            is_shun_pan = True
        elif direction == 'away' and handicap > 0:
            # 客队推荐 + 客队让球 = 顺盘
            is_shun_pan = True
        
        if is_shun_pan:
            return FilterResult(
                should_recommend=False,
                reason=f"浅中盘{abs_handicap}顺盘过滤，平局风险高",
                filter_type='shallow_handicap'
            )
        
        return FilterResult(
            should_recommend=True,
            reason="非顺盘，不过滤",
            filter_type='pass'
        )
    
    def is_tier1_league(self, league: str) -> bool:
        """
        判断是否为一级联赛
        
        Args:
            league: 联赛名称
            
        Returns:
            是否为一级联赛
        """
        if not league:
            return False
        return league in self.TIER1_LEAGUES
    
    def get_thresholds(self, league: str = None) -> Dict:
        """
        获取当前阈值配置
        
        Args:
            league: 联赛名称 (可选，用于动态调整)
            
        Returns:
            阈值配置字典
        """
        # 基础阈值
        thresholds = {
            'min_volume': self.MIN_VOLUME,
            'max_handicap_depth': self.MAX_HANDICAP_DEPTH,
            'min_score_diff': self.MIN_SCORE_DIFF,
            'shallow_handicap': self.SHALLOW_HANDICAP,
            'elite_threshold': 55,
            'strong_threshold': 45,
            'standard_threshold': 35,
        }
        
        # 一级联赛使用标准阈值
        if league and self.is_tier1_league(league):
            thresholds['league_tier'] = 1
        else:
            thresholds['league_tier'] = 2
        
        return thresholds


# 便捷函数
def should_recommend(
    metrics: Dict, 
    score_home: float, 
    score_away: float,
    direction: Optional[str] = None
) -> Tuple[bool, str]:
    """
    便捷函数：判断是否应该推荐
    
    Args:
        metrics: 比赛指标字典
        score_home: 主队评分
        score_away: 客队评分
        direction: 推荐方向 (可选)
        
    Returns:
        (should_recommend, reason): 是否推荐及原因
    """
    filter_obj = DynamicThresholdFilter()
    return filter_obj.should_recommend(metrics, score_home, score_away, direction)
