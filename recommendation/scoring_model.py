"""
SignalScoringModel - 信号评分模型 V7.2

从 x1_json_recommender.py 中提取的独立评分模块。
基于5759场历史数据挖掘的高价值信号模式。

核心发现:
1. 极热反转 + 高成交 = 最强信号 (hot<-15 + vol>600K = 69.6%)
2. 客队ELITE = 68.5%, ROI +30%
3. 成交量是关键过滤器

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """评分结果数据类"""
    score: float
    signals: List[str]
    direction: str  # 'home' | 'away'
    
    def __post_init__(self):
        # 确保评分在合理范围内 (-100 到 200)
        self.score = max(-100, min(200, self.score))


class SignalScoringModel:
    """
    V7.2 信号评分模型
    
    负责根据比赛指标计算推荐评分和识别信号。
    """
    
    # 评分阈值常量
    ELITE_THRESHOLD = 55      # Elite级别 (66%+胜率)
    STRONG_THRESHOLD = 45     # Strong级别 (60%+胜率)
    STANDARD_THRESHOLD = 35   # Standard级别 (55%+胜率)
    MIN_SCORE_DIFF = 20       # 最小分差
    
    # 信号分数常量
    ELITE_HOT_VOL_SCORE = 60      # 极热反转+高成交
    SUPER_HOT_VOL_SCORE = 55      # 超级热度反转
    STRONG_HOT_VOL_SCORE = 50     # 强热度反转
    HOT_VOL_SCORE = 40            # 热度+成交
    HOT_MED_SCORE = 30            # 中等热度
    
    PCT_BF_SCORE = 35             # 高成交比例+高必发
    HIGH_PCT_SCORE = 15           # 高成交比例
    HIGH_BF_SCORE = 25            # 高必发指数
    BF_DIFF_PLUS_SCORE = 15       # 必发差值优势
    BF_PLUS_SCORE = 10            # 必发正向
    
    HOT_REV_SCORE = 20            # 热度反转
    KELLY_SIG_SCORE = 20          # 凯利信号
    LOW_KELLY_SCORE = 10          # 低凯利
    
    BF_LOW_GOLD_SCORE = 30        # 必发低金矿 (bf<40)
    ULTRA_VOL_SCORE = 15          # 超高成交量
    DEEP_ELITE_SCORE = 40         # 深盘Elite
    HALF_BALL_COLD_SCORE = 30     # 球半盘冷门
    
    HDP_TRUE_LET_SCORE = 25       # 真让球
    HDP_KELLY_SCORE = 20          # 盘口凯利
    DEEP_LET_SCORE = 15           # 深让球
    HDP_HOT_TRAP_SCORE = 30       # 假热诱盘
    DEEP_RCV_SCORE = 15           # 深受让
    
    # 负面信号扣分
    HOT_TRAP_PENALTY = -30        # 热度陷阱
    BF_NEG_PENALTY = -25          # 必发不支持
    LOW_VOL_PENALTY = -20         # 成交量过低
    ANTI_HDP_PENALTY = -25        # 逆盘惩罚
    
    def __init__(self):
        """初始化评分模型"""
        pass
    
    def calculate_score(
        self, 
        metrics: Dict, 
        direction: str, 
        handicap: Optional[float] = None
    ) -> Tuple[float, List[str]]:
        """
        计算推荐评分
        
        Args:
            metrics: 比赛指标字典，包含:
                - bfindex_home/away: 必发指数
                - hot_home/away: 热度指数
                - total_volume: 成交量
                - home_pct: 主队成交占比
                - kelly_diff_home/away: 凯利差值
                - kelly_home/away: 凯利指数
            direction: 推荐方向 ('home' | 'away')
            handicap: 盘口值 (可选)
            
        Returns:
            (score, signals): 评分值和触发的信号列表
        """
        if direction == 'home':
            score, signals = self._calculate_home_score(metrics, handicap)
        else:
            score, signals = self._calculate_away_score(metrics, handicap)
        
        # 确保评分在合理范围内 (-100 到 200)
        score = max(-100, min(200, score))
        return score, signals

    
    def _extract_base_metrics(self, metrics: Dict) -> Dict:
        """
        提取基础指标，处理缺失字段
        
        Args:
            metrics: 原始指标字典
            
        Returns:
            标准化的指标字典
        """
        return {
            'bf_h': float(metrics.get('bfindex_home', 0) or 0),
            'bf_a': float(metrics.get('bfindex_away', 0) or 0),
            'hot_h': float(metrics.get('hot_home', 0) or 0),
            'hot_a': float(metrics.get('hot_away', 0) or 0),
            'volume': float(metrics.get('total_volume', 0) or 0),
            'pct_h': float(metrics.get('home_pct', 0) or 0),
            'kd_h': float(metrics.get('kelly_diff_home', 0) or 0),
            'kd_a': float(metrics.get('kelly_diff_away', 0) or 0),
            'kelly_h': float(metrics.get('kelly_home', 0) or 0),
            'kelly_a': float(metrics.get('kelly_away', 0) or 0),
        }
    
    def _calculate_home_score(
        self, 
        metrics: Dict, 
        handicap: Optional[float] = None
    ) -> Tuple[float, List[str]]:
        """
        计算主队评分 V7
        
        核心信号:
        1. 极热反转 + 高成交 (最强信号)
        2. 高成交比例 + 高必发
        3. 必发指数优势
        4. 盘口加成
        """
        score = 0
        signals = []
        
        # 提取指标
        m = self._extract_base_metrics(metrics)
        bf_diff = m['bf_h'] - m['bf_a']
        hot_diff = m['hot_h'] - m['hot_a']
        
        # 1. 🔥 极端热度反转 + 高成交 (最强信号!)
        # hot<-15 + vol>600K = 69.6%
        if hot_diff < -15 and m['volume'] > 600000:
            score += self.ELITE_HOT_VOL_SCORE
            signals.append("ELITE_HOT_VOL")
        elif hot_diff < -12 and m['volume'] > 500000:
            score += self.SUPER_HOT_VOL_SCORE
            signals.append("SUPER_HOT_VOL")
        elif hot_diff < -10 and m['volume'] > 500000:
            score += self.STRONG_HOT_VOL_SCORE
            signals.append("STRONG_HOT_VOL")
        elif hot_diff < -10 and m['volume'] > 300000:
            score += self.HOT_VOL_SCORE
            signals.append("HOT_VOL")
        elif hot_diff < -10 and m['volume'] > 200000:
            score += self.HOT_MED_SCORE
            signals.append("HOT_MED")
        
        # 2. 高成交比例 + 高必发 (64.1%)
        if m['pct_h'] > 60 and m['bf_h'] > 45:
            score += self.PCT_BF_SCORE
            signals.append("PCT_BF")
        elif m['pct_h'] > 60:
            score += self.HIGH_PCT_SCORE
            signals.append("HIGH_PCT")
        
        # 3. 必发指数优势
        if m['bf_h'] > 50:
            score += self.HIGH_BF_SCORE
            signals.append("HIGH_BF")
        elif bf_diff > 15:
            score += self.BF_DIFF_PLUS_SCORE
            signals.append("BF_DIFF+")
        elif bf_diff > 10:
            score += self.BF_PLUS_SCORE
            signals.append("BF+")
        
        # 4. 热度反转 (无高成交时)
        if hot_diff < -5 and m['volume'] > 200000 and "HOT" not in str(signals):
            score += self.HOT_REV_SCORE
            signals.append("HOT_REV")
        
        # 5. 凯利指数信号
        if m['kelly_h'] < 90 and m['kd_h'] < 5:
            score += self.KELLY_SIG_SCORE
            signals.append("KELLY_SIG")
        elif m['kelly_h'] < 95:
            score += self.LOW_KELLY_SCORE
            signals.append("LOW_KELLY")
        
        # 6. 负面信号 (扣分)
        if hot_diff > 5:  # 主队过热
            score += self.HOT_TRAP_PENALTY
            signals.append("HOT_TRAP!")
        if bf_diff < -10:  # 必发不支持
            score += self.BF_NEG_PENALTY
            signals.append("BF_NEG!")
        if m['volume'] < 50000:  # 成交量过低
            score += self.LOW_VOL_PENALTY
            signals.append("LOW_VOL!")
        
        # 7. 🔥 V7.3 深度特征加成
        # 必发低(<40) = ROI+80%, 胜率80.6%
        if m['bf_h'] < 40:
            score += self.BF_LOW_GOLD_SCORE
            signals.append("BF_LOW_GOLD")
        
        # 超高量(>500K) = ROI+73%
        if m['volume'] > 500000:
            score += self.ULTRA_VOL_SCORE
            signals.append("ULTRA_VOL")
        
        # 8. 盘口加成
        if handicap is not None:
            score, signals = self._apply_home_handicap_bonus(
                score, signals, handicap, hot_diff, m['kelly_h']
            )
        
        return score, signals
    
    def _calculate_away_score(
        self, 
        metrics: Dict, 
        handicap: Optional[float] = None
    ) -> Tuple[float, List[str]]:
        """
        计算客队评分 V7
        
        客队ELITE = 68.5%, ROI +30%
        """
        score = 0
        signals = []
        
        # 提取指标
        m = self._extract_base_metrics(metrics)
        bf_diff = m['bf_h'] - m['bf_a']
        hot_diff = m['hot_h'] - m['hot_a']
        
        # 1. 极端热度反转 + 高成交 (68.5%最强!)
        if hot_diff > 15 and m['volume'] > 600000:
            score += self.ELITE_HOT_VOL_SCORE
            signals.append("ELITE_HOT_VOL")
        elif hot_diff > 10 and m['volume'] > 500000:
            score += self.STRONG_HOT_VOL_SCORE
            signals.append("STRONG_HOT_VOL")
        elif hot_diff > 5 and m['volume'] > 300000:
            score += self.PCT_BF_SCORE
            signals.append("HOT_VOL")
        
        # 2. 必发指数支持
        if m['bf_a'] > 45 and hot_diff > 5:
            score += 30
            signals.append("BF_HOT")
        elif bf_diff < -15:
            score += self.HOT_REV_SCORE
            signals.append("BF_DIFF+")
        elif bf_diff < -10:
            score += self.BF_PLUS_SCORE
            signals.append("BF+")
        
        # 3. 凯利信号
        if m['kelly_a'] < 95 and m['kd_a'] < 10:
            score += self.LOW_KELLY_SCORE + 5
            signals.append("KELLY_SIG")
        
        # 4. 负面信号
        if hot_diff < -5:
            score += self.HOT_TRAP_PENALTY
            signals.append("HOT_TRAP!")
        if bf_diff > 10:
            score += self.BF_NEG_PENALTY
            signals.append("BF_NEG!")
        if m['volume'] < 50000:
            score += self.LOW_VOL_PENALTY
            signals.append("LOW_VOL!")
        
        # 5. 🔥 V7.3 深度特征加成
        if m['bf_a'] < 40:
            score += self.BF_LOW_GOLD_SCORE
            signals.append("BF_LOW_GOLD")
        
        if m['volume'] > 500000:
            score += self.ULTRA_VOL_SCORE
            signals.append("ULTRA_VOL")
        
        # 6. 盘口加成
        if handicap is not None:
            score, signals = self._apply_away_handicap_bonus(
                score, signals, handicap, hot_diff, m['kelly_a']
            )
        
        return score, signals

    
    def _apply_home_handicap_bonus(
        self, 
        score: float, 
        signals: List[str], 
        handicap: float,
        hot_diff: float,
        kelly_h: float
    ) -> Tuple[float, List[str]]:
        """
        应用主队盘口加成
        
        核心发现:
        - 主让球+热度反冷 = 真让 (76.7%胜率)
        - 主让+凯利低 = 机构看好 (74.5%胜率)
        - 深让球确定性高 (95.6%胜率)
        """
        abs_hdp = abs(handicap)
        
        # 深盘(>1.5) + Elite级别 = ROI+180%
        if abs_hdp > 1.5 and hot_diff < -15:
            score += self.DEEP_ELITE_SCORE
            signals.append("DEEP_ELITE")
        # 球半盘(1.0-1.5) + 极冷门 = ROI+91%
        elif 1.0 < abs_hdp <= 1.5 and hot_diff < -15:
            score += self.HALF_BALL_COLD_SCORE
            signals.append("HALF_BALL_COLD")
        
        # 主让球 + 热度反冷 = 真让 (76.7%胜率)
        if handicap < -0.25 and hot_diff < -10:
            score += self.HDP_TRUE_LET_SCORE
            signals.append("HDP_TRUE_LET")
        # 主让 + 凯利低 = 机构看好 (74.5%胜率)
        if handicap < -0.25 and kelly_h < 95:
            score += self.HDP_KELLY_SCORE
            signals.append("HDP_KELLY")
        # 深让球确定性高 (95.6%胜率)
        if handicap <= -1.5:
            score += self.DEEP_LET_SCORE
            signals.append("DEEP_LET")
        # 逆盘惩罚: 主受让却推主队
        if handicap > 0.5:
            score += self.ANTI_HDP_PENALTY
            signals.append("ANTI_HDP!")
        
        return score, signals
    
    def _apply_away_handicap_bonus(
        self, 
        score: float, 
        signals: List[str], 
        handicap: float,
        hot_diff: float,
        kelly_a: float
    ) -> Tuple[float, List[str]]:
        """
        应用客队盘口加成
        
        核心发现:
        - 主受让+热度过热 = 假热诱盘 (83.8%胜率!)
        - 主受让+凯利低 = 机构看好客队 (81.9%胜率)
        - 深受让确定性高 (95.7%胜率)
        """
        abs_hdp = abs(handicap)
        
        # 深盘(>1.5) + Elite级别 = ROI+180%
        if abs_hdp > 1.5 and hot_diff > 15:
            score += self.DEEP_ELITE_SCORE
            signals.append("DEEP_ELITE")
        # 球半盘(1.0-1.5) + 极冷门 = ROI+91%
        elif 1.0 < abs_hdp <= 1.5 and hot_diff > 15:
            score += self.HALF_BALL_COLD_SCORE
            signals.append("HALF_BALL_COLD")
        
        # 主受让 + 热度过热 = 假热诱盘 (83.8%胜率!)
        if handicap > 0.25 and hot_diff > 10:
            score += self.HDP_HOT_TRAP_SCORE
            signals.append("HDP_HOT_TRAP")
        # 主受让 + 凯利低 = 机构看好客队 (81.9%胜率)
        if handicap > 0.25 and kelly_a < 95:
            score += self.HDP_KELLY_SCORE + 5  # 客队盘口信号更强
            signals.append("HDP_KELLY")
        # 深受让确定性高 (95.7%胜率)
        if handicap >= 1.5:
            score += self.DEEP_RCV_SCORE
            signals.append("DEEP_RCV")
        # 逆盘惩罚: 主让球却推客队
        if handicap < -0.5:
            score += self.ANTI_HDP_PENALTY
            signals.append("ANTI_HDP!")
        
        return score, signals
    
    def get_recommendation_level(
        self, 
        score: float, 
        signals: List[str],
        hot_diff: float
    ) -> Tuple[str, float]:
        """
        根据评分和信号确定推荐级别
        
        Args:
            score: 评分值
            signals: 信号列表
            hot_diff: 热度差值
            
        Returns:
            (level, confidence): 推荐级别和置信度
        """
        has_v7_elite = "ELITE_HOT_VOL" in signals or "SUPER_HOT_VOL" in signals
        has_v7_strong = "STRONG_HOT_VOL" in signals or "HOT_VOL" in signals
        has_hdp_signal = any(s in signals for s in ["HDP_TRUE_LET", "HDP_KELLY", "DEEP_LET", "HDP_HOT_TRAP", "DEEP_RCV"])
        has_hot_reversal = abs(hot_diff) > 5
        
        # Elite: V7信号 或 (盘口信号+高分)
        if has_v7_elite or (has_hdp_signal and score >= 70):
            return 'Elite', 0.92
        elif has_v7_strong and score >= self.STRONG_THRESHOLD:
            return 'Strong', 0.85
        elif (score >= self.ELITE_THRESHOLD and has_hot_reversal) or has_hdp_signal:
            return 'Standard', 0.78
        else:
            return '', 0.0
    
    def validate_score_range(self, score: float) -> bool:
        """
        验证评分是否在合理范围内
        
        Args:
            score: 评分值
            
        Returns:
            是否在合理范围内 (-100 到 200)
        """
        return -100 <= score <= 200


# 便捷函数
def calculate_score(
    metrics: Dict, 
    direction: str, 
    handicap: Optional[float] = None
) -> Tuple[float, List[str]]:
    """
    便捷函数：计算推荐评分
    
    Args:
        metrics: 比赛指标字典
        direction: 推荐方向 ('home' | 'away')
        handicap: 盘口值 (可选)
        
    Returns:
        (score, signals): 评分值和触发的信号列表
    """
    model = SignalScoringModel()
    return model.calculate_score(metrics, direction, handicap)
