"""
ResultFormatter - 推荐结果格式化器

格式化推荐结果，确保输出结构完整。

核心功能:
1. 格式化推荐文本（如"曼联 -0.5"）
2. 限制信号列表（最多4个）
3. 生成拒绝原因
4. 生成让球推荐详细理由

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RecommendationResult:
    """推荐结果数据类"""
    direction: str = 'none'  # 'home' | 'away' | 'none'
    confidence: float = 0.0  # 0.0 - 1.0
    level: str = ''  # 'Elite' | 'Strong' | 'Standard' | ''
    score: float = 0.0
    reason: str = ''
    signals: List[str] = field(default_factory=list)
    
    # 投注类型
    bet_type: str = 'euro'  # 'euro' | 'handicap'
    handicap_bet: Optional[str] = None
    handicap_bet_reason: str = ''
    
    # 格式化输出
    formatted: str = ''  # e.g., "曼联 -0.5"
    home_team: str = ''
    away_team: str = ''
    handicap: float = 0.0
    
    # 来源标记
    source: str = 'model'  # 'rule' | 'model' | 'hybrid'
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'direction': self.direction,
            'confidence': self.confidence,
            'level': self.level,
            'score': self.score,
            'reason': self.reason,
            'signals': self.signals[:4],  # 最多4个信号
            'bet_type': self.bet_type,
            'handicap_bet': self.handicap_bet,
            'handicap_bet_reason': self.handicap_bet_reason,
            'formatted': self.formatted,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'handicap': self.handicap,
            'source': self.source,
        }


class ResultFormatter:
    """
    推荐结果格式化器
    
    负责格式化推荐结果，确保输出结构完整。
    """
    
    MAX_SIGNALS = 4  # 最多显示的信号数量
    
    def __init__(self):
        """初始化格式化器"""
        pass
    
    def format_result(
        self,
        direction: str,
        confidence: float,
        level: str,
        score: float,
        signals: List[str],
        home_team: str,
        away_team: str,
        handicap: float,
        bet_type: str = 'euro',
        handicap_bet: Optional[str] = None,
        handicap_bet_reason: str = '',
        source: str = 'model'
    ) -> Dict:
        """
        格式化推荐结果
        
        Args:
            direction: 推荐方向
            confidence: 置信度
            level: 推荐级别
            score: 评分
            signals: 信号列表
            home_team: 主队名称
            away_team: 客队名称
            handicap: 盘口值
            bet_type: 投注类型
            handicap_bet: 让球推荐方向
            handicap_bet_reason: 让球推荐理由
            source: 推荐来源
            
        Returns:
            格式化的推荐结果字典
        """
        result = RecommendationResult(
            direction=direction,
            confidence=confidence,
            level=level,
            score=score,
            signals=signals[:self.MAX_SIGNALS],
            home_team=home_team,
            away_team=away_team,
            handicap=handicap,
            bet_type=bet_type,
            handicap_bet=handicap_bet,
            handicap_bet_reason=handicap_bet_reason,
            source=source,
        )
        
        # 生成格式化文本
        result.formatted = self.format_recommendation_text(
            direction, handicap, home_team, away_team
        )
        
        # 生成原因
        if direction != 'none':
            result.reason = self._generate_reason(level, score, signals)
        
        return result.to_dict()
    
    def format_recommendation_text(
        self,
        direction: str,
        handicap: float,
        home_team: str,
        away_team: str
    ) -> str:
        """
        格式化推荐文本
        
        Args:
            direction: 推荐方向
            handicap: 盘口值
            home_team: 主队名称
            away_team: 客队名称
            
        Returns:
            格式化的推荐文本，如 "曼联 -0.5"
        """
        if direction == 'none':
            return ''
        
        team = home_team if direction == 'home' else away_team
        
        if direction == 'home':
            if handicap == 0:
                return f"{team} 平手"
            elif handicap > 0:
                return f"{team} +{handicap}"
            else:
                return f"{team} {handicap}"
        else:
            away_hcap = -handicap
            if away_hcap == 0:
                return f"{team} 平手"
            elif away_hcap > 0:
                return f"{team} +{away_hcap}"
            else:
                return f"{team} {away_hcap}"
    
    def _generate_reason(
        self,
        level: str,
        score: float,
        signals: List[str]
    ) -> str:
        """
        生成推荐原因
        
        Args:
            level: 推荐级别
            score: 评分
            signals: 信号列表
            
        Returns:
            推荐原因字符串
        """
        signal_str = ','.join(signals[:self.MAX_SIGNALS])
        return f"{level} {score:.0f}分 ({signal_str})"
    
    def format_rejection(self, reason: str) -> Dict:
        """
        格式化拒绝推荐结果
        
        Args:
            reason: 拒绝原因
            
        Returns:
            拒绝推荐结果字典
        """
        if not reason:
            reason = "未知原因"
        
        return {
            'direction': 'none',
            'confidence': 0.0,
            'level': '',
            'score': 0.0,
            'reason': reason,
            'signals': [],
            'bet_type': 'euro',
            'handicap_bet': None,
            'handicap_bet_reason': '',
            'formatted': '',
            'home_team': '',
            'away_team': '',
            'handicap': 0.0,
            'source': 'model',
        }
    
    def format_handicap_reason(
        self,
        team: str,
        handicap_display: float,
        handicap_type: str,
        bet_reason: str
    ) -> str:
        """
        格式化让球推荐详细理由
        
        Args:
            team: 队名
            handicap_display: 显示用盘口值
            handicap_type: 盘口类型（如"半一盘"）
            bet_reason: 投注理由（如"顺盘"、"受让"）
            
        Returns:
            格式化的让球推荐理由，如 "让球推荐: 曼联 -0.50 (半一盘顺盘)"
        """
        return f"让球推荐: {team} {handicap_display:+.2f} ({handicap_type}{bet_reason})"
    
    def limit_signals(self, signals: List[str], max_count: int = None) -> List[str]:
        """
        限制信号列表数量
        
        Args:
            signals: 信号列表
            max_count: 最大数量（默认4个）
            
        Returns:
            限制后的信号列表
        """
        if max_count is None:
            max_count = self.MAX_SIGNALS
        return signals[:max_count]
    
    def validate_result(self, result: Dict) -> bool:
        """
        验证推荐结果结构完整性
        
        Args:
            result: 推荐结果字典
            
        Returns:
            是否结构完整
        """
        required_fields = [
            'direction', 'confidence', 'level', 'reason', 'signals'
        ]
        
        for field in required_fields:
            if field not in result:
                return False
        
        # 有推荐方向时需要额外字段
        if result.get('direction') not in ['none', None]:
            extra_fields = ['formatted', 'home_team', 'away_team']
            for field in extra_fields:
                if field not in result:
                    return False
        
        return True


# 便捷函数
def format_result(
    direction: str,
    confidence: float,
    level: str,
    score: float,
    signals: List[str],
    home_team: str,
    away_team: str,
    handicap: float,
    **kwargs
) -> Dict:
    """
    便捷函数：格式化推荐结果
    """
    formatter = ResultFormatter()
    return formatter.format_result(
        direction, confidence, level, score, signals,
        home_team, away_team, handicap, **kwargs
    )


def format_rejection(reason: str) -> Dict:
    """
    便捷函数：格式化拒绝推荐结果
    """
    formatter = ResultFormatter()
    return formatter.format_rejection(reason)
