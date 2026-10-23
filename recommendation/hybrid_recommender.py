"""
HybridRecommender - 混合推荐器

融合规则推荐与模型推荐，提升推荐置信度。

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HybridResult:
    """混合推荐结果"""
    direction: str  # 'home' | 'away' | 'none'
    confidence: float  # 0.0 - 1.0
    source: str  # 'rule' | 'model' | 'hybrid'
    reason: str
    rule_confidence: float = 0.0
    model_confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'direction': self.direction,
            'confidence': self.confidence,
            'source': self.source,
            'reason': self.reason,
            'rule_confidence': self.rule_confidence,
            'model_confidence': self.model_confidence,
        }


class HybridRecommender:
    """
    混合推荐器 - 融合规则与模型推荐
    
    优先级逻辑:
    1. 规则置信度>=0.85时，优先采用规则推荐
    2. 规则与模型方向一致时，增强置信度(乘以1.3)
    3. 规则与模型冲突时，根据置信度高低选择
    4. 无规则匹配时，使用模型推荐
    """
    
    # 配置常量
    RULE_PRIORITY_THRESHOLD = 0.85  # 规则优先阈值
    CONFIDENCE_BOOST_FACTOR = 1.3   # 置信度增强系数
    MAX_CONFIDENCE = 1.0            # 最大置信度
    CONFLICT_PENALTY = 0.8          # 冲突时的惩罚系数

    def __init__(self):
        """初始化混合推荐器"""
        pass
    
    def recommend(
        self, 
        model_result: Dict, 
        rule_result: Optional[Dict] = None
    ) -> Dict:
        """
        生成混合推荐
        
        Args:
            model_result: 模型推荐结果，包含:
                - direction: 推荐方向 ('home'/'away'/'none')
                - confidence: 置信度 (0.0-1.0)
                - reason: 推荐理由
            rule_result: 规则推荐结果（可选），包含:
                - recommendation: 推荐方向 ('home_win'/'away_win'/'none')
                - confidence: 置信度 (0.0-1.0)
                - reason: 推荐理由
                
        Returns:
            混合推荐结果字典
        """
        model_direction = model_result.get('direction', 'none')
        model_confidence = model_result.get('confidence', 0.0)
        model_reason = model_result.get('reason', '')
        
        # 无规则结果时，直接使用模型推荐
        if rule_result is None or not rule_result:
            return HybridResult(
                direction=model_direction,
                confidence=model_confidence,
                source='model',
                reason=model_reason,
                model_confidence=model_confidence,
            ).to_dict()
        
        rule_direction = self._normalize_direction(rule_result.get('recommendation', 'none'))
        rule_confidence = rule_result.get('confidence', 0.0)
        rule_reason = rule_result.get('reason', '')
        
        # 规则无推荐时，使用模型推荐
        if rule_direction == 'none':
            return HybridResult(
                direction=model_direction,
                confidence=model_confidence,
                source='model',
                reason=model_reason,
                rule_confidence=rule_confidence,
                model_confidence=model_confidence,
            ).to_dict()
        
        # 1. 规则置信度>=0.85时，优先采用规则推荐
        if rule_confidence >= self.RULE_PRIORITY_THRESHOLD:
            return HybridResult(
                direction=rule_direction,
                confidence=rule_confidence,
                source='rule',
                reason=f"高置信度规则: {rule_reason}",
                rule_confidence=rule_confidence,
                model_confidence=model_confidence,
            ).to_dict()
        
        # 2. 规则与模型方向一致时，增强置信度
        if rule_direction == model_direction and model_direction != 'none':
            enhanced_confidence = min(
                ((rule_confidence + model_confidence) / 2) * self.CONFIDENCE_BOOST_FACTOR,
                self.MAX_CONFIDENCE
            )
            return HybridResult(
                direction=rule_direction,
                confidence=enhanced_confidence,
                source='hybrid',
                reason=f"规则与模型一致: {rule_reason}",
                rule_confidence=rule_confidence,
                model_confidence=model_confidence,
            ).to_dict()
        
        # 3. 规则与模型冲突时，根据置信度高低选择
        if rule_direction != model_direction:
            if rule_confidence > model_confidence:
                return HybridResult(
                    direction=rule_direction,
                    confidence=rule_confidence * self.CONFLICT_PENALTY,
                    source='rule',
                    reason=f"规则置信度更高: {rule_reason}",
                    rule_confidence=rule_confidence,
                    model_confidence=model_confidence,
                ).to_dict()
            else:
                return HybridResult(
                    direction=model_direction,
                    confidence=model_confidence * self.CONFLICT_PENALTY,
                    source='model',
                    reason=f"模型置信度更高: {model_reason}",
                    rule_confidence=rule_confidence,
                    model_confidence=model_confidence,
                ).to_dict()
        
        # 4. 默认使用模型推荐
        return HybridResult(
            direction=model_direction,
            confidence=model_confidence,
            source='model',
            reason=model_reason,
            rule_confidence=rule_confidence,
            model_confidence=model_confidence,
        ).to_dict()
    
    def _normalize_direction(self, direction: str) -> str:
        """
        标准化推荐方向
        
        Args:
            direction: 原始方向字符串
            
        Returns:
            标准化后的方向 ('home'/'away'/'none')
        """
        if direction in ('home', 'home_win'):
            return 'home'
        elif direction in ('away', 'away_win'):
            return 'away'
        else:
            return 'none'
    
    def get_source_label(self, source: str) -> str:
        """
        获取来源标签的中文描述
        
        Args:
            source: 来源标识
            
        Returns:
            中文描述
        """
        labels = {
            'rule': '规则推荐',
            'model': '模型推荐',
            'hybrid': '混合推荐',
        }
        return labels.get(source, '未知来源')


def recommend(model_result: Dict, rule_result: Optional[Dict] = None) -> Dict:
    """
    便捷函数：生成混合推荐
    
    Args:
        model_result: 模型推荐结果
        rule_result: 规则推荐结果（可选）
        
    Returns:
        混合推荐结果字典
    """
    recommender = HybridRecommender()
    return recommender.recommend(model_result, rule_result)
