"""
BetTypeSelector - 智能投注类型选择器

根据盘口特征自动选择最优投注类型（欧赔或让球盘）。

核心规则 (基于409场数据验证):
1. 逆盘（受让方）: 让球胜率100%!
2. 深盘蚊子肉(<1.6): 让球ROI+23.2%
3. 深盘(>=1.0)顺盘: 让球ROI+31%
4. 浅中盘(<1.0)顺盘: 过滤不推荐

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BetTypeResult:
    """投注类型选择结果"""
    bet_type: str  # 'euro' | 'handicap'
    handicap_bet: Optional[str]  # 让球推荐方向
    handicap_bet_reason: str  # 让球推荐理由
    team_name: str  # 推荐队名
    handicap_display: float  # 显示用盘口值


class BetTypeSelector:
    """
    智能投注类型选择器
    
    根据盘口特征选择最优投注类型。
    """
    
    # 阈值常量
    DEEP_HANDICAP = 1.0          # 深盘阈值
    MOSQUITO_ODDS = 1.6          # 蚊子肉欧赔阈值
    
    def __init__(self):
        """初始化选择器"""
        pass
    
    def select_bet_type(
        self, 
        direction: str, 
        handicap: float, 
        euro_odds: float,
        home_team: str = '',
        away_team: str = ''
    ) -> Dict:
        """
        选择最优投注类型
        
        Args:
            direction: 推荐方向 ('home' | 'away')
            handicap: 盘口值 (正值=主队受让，负值=主队让球)
            euro_odds: 推荐方欧赔
            home_team: 主队名称
            away_team: 客队名称
            
        Returns:
            {
                'bet_type': 'euro' | 'handicap',
                'handicap_bet': str | None,
                'handicap_bet_reason': str,
                'should_filter': bool  # 是否应该过滤不推荐
            }
        """
        # 平手盘直接返回欧赔
        if handicap == 0:
            return {
                'bet_type': 'euro',
                'handicap_bet': None,
                'handicap_bet_reason': '',
                'should_filter': False
            }
        
        abs_hdp = abs(handicap)
        
        # 判断是否逆盘推荐
        is_ni_pan = self._is_ni_pan(direction, handicap)
        
        # 1. 逆盘（受让方）: 让球胜率100%!
        if is_ni_pan:
            return self._select_ni_pan_bet(direction, handicap, home_team, away_team)
        
        # 2. 深盘蚊子肉(<1.6): 让球ROI+23.2%
        if abs_hdp >= self.DEEP_HANDICAP and euro_odds > 0 and euro_odds < self.MOSQUITO_ODDS:
            return self._select_deep_mosquito_bet(direction, handicap, home_team, away_team)
        
        # 3. 深盘(>=1.0)顺盘: 让球ROI+31%
        if abs_hdp >= self.DEEP_HANDICAP:
            return self._select_deep_shun_pan_bet(direction, handicap, home_team, away_team)
        
        # 4. 浅中盘(<1.0)顺盘: 过滤不推荐
        return {
            'bet_type': 'euro',
            'handicap_bet': None,
            'handicap_bet_reason': '',
            'should_filter': True  # 标记应该过滤
        }
    
    def _is_ni_pan(self, direction: str, handicap: float) -> bool:
        """
        判断是否为逆盘推荐
        
        逆盘定义:
        - 主队推荐 + 主队受让 (handicap > 0)
        - 客队推荐 + 客队受让 (handicap < 0)
        
        Args:
            direction: 推荐方向
            handicap: 盘口值
            
        Returns:
            是否为逆盘
        """
        if direction == 'home' and handicap > 0:
            return True
        if direction == 'away' and handicap < 0:
            return True
        return False
    
    def _get_handicap_type_name(self, abs_hdp: float) -> str:
        """
        获取盘口类型名称
        
        Args:
            abs_hdp: 盘口绝对值
            
        Returns:
            盘口类型名称
        """
        if abs_hdp < 0.25:
            return '平手盘'
        elif abs_hdp <= 0.5:
            return '平半盘'
        elif abs_hdp <= 0.75:
            return '半球盘'
        elif abs_hdp <= 1.0:
            return '半一盘'
        elif abs_hdp <= 1.25:
            return '一球盘'
        elif abs_hdp <= 1.5:
            return '球半盘'
        else:
            return '深盘'
    
    def _select_ni_pan_bet(
        self, 
        direction: str, 
        handicap: float,
        home_team: str,
        away_team: str
    ) -> Dict:
        """
        选择逆盘投注类型
        
        逆盘（受让方）: 让球胜率100%!
        """
        abs_hdp = abs(handicap)
        hdp_type = self._get_handicap_type_name(abs_hdp)
        team = home_team if direction == 'home' else away_team
        
        # 计算显示用盘口值
        if direction == 'home':
            hdp_display = handicap  # 主队受让，显示正值
        else:
            hdp_display = -handicap  # 客队受让，显示正值
        
        return {
            'bet_type': 'handicap',
            'handicap_bet': direction,
            'handicap_bet_reason': f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}受让)",
            'should_filter': False,
            'team_name': team,
            'handicap_display': hdp_display
        }

    
    def _select_deep_mosquito_bet(
        self, 
        direction: str, 
        handicap: float,
        home_team: str,
        away_team: str
    ) -> Dict:
        """
        选择深盘蚊子肉投注类型
        
        深盘蚊子肉(<1.6): 让球ROI+23.2%远高于欧赔!
        """
        abs_hdp = abs(handicap)
        hdp_type = self._get_handicap_type_name(abs_hdp)
        team = home_team if direction == 'home' else away_team
        
        # 顺盘让球
        if direction == 'home':
            hdp_display = -handicap  # 主队让球，显示负值
        else:
            hdp_display = handicap  # 客队让球，显示负值
        
        return {
            'bet_type': 'handicap',
            'handicap_bet': direction,
            'handicap_bet_reason': f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}避蚊子肉ROI+23%)",
            'should_filter': False,
            'team_name': team,
            'handicap_display': hdp_display
        }
    
    def _select_deep_shun_pan_bet(
        self, 
        direction: str, 
        handicap: float,
        home_team: str,
        away_team: str
    ) -> Dict:
        """
        选择深盘顺盘投注类型
        
        深盘(>=1.0)顺盘: 让球ROI+31%验证
        """
        abs_hdp = abs(handicap)
        hdp_type = self._get_handicap_type_name(abs_hdp)
        team = home_team if direction == 'home' else away_team
        
        # 顺盘让球
        if direction == 'home':
            hdp_display = -handicap  # 主队让球，显示负值
        else:
            hdp_display = handicap  # 客队让球，显示负值
        
        return {
            'bet_type': 'handicap',
            'handicap_bet': direction,
            'handicap_bet_reason': f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}顺盘)",
            'should_filter': False,
            'team_name': team,
            'handicap_display': hdp_display
        }
    
    def format_handicap_recommendation(
        self, 
        direction: str, 
        handicap: float,
        home_team: str,
        away_team: str
    ) -> str:
        """
        格式化让球推荐文本
        
        Args:
            direction: 推荐方向
            handicap: 盘口值
            home_team: 主队名称
            away_team: 客队名称
            
        Returns:
            格式化的推荐文本，如 "曼联 -0.5"
        """
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


# 便捷函数
def select_bet_type(
    direction: str, 
    handicap: float, 
    euro_odds: float,
    home_team: str = '',
    away_team: str = ''
) -> Dict:
    """
    便捷函数：选择最优投注类型
    
    Args:
        direction: 推荐方向 ('home' | 'away')
        handicap: 盘口值
        euro_odds: 推荐方欧赔
        home_team: 主队名称
        away_team: 客队名称
        
    Returns:
        投注类型选择结果
    """
    selector = BetTypeSelector()
    return selector.select_bet_type(direction, handicap, euro_odds, home_team, away_team)
