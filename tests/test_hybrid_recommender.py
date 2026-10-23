"""
HybridRecommender 属性测试

使用 hypothesis 库进行属性测试，验证混合推荐器的正确性。

测试覆盖:
- Property 16: 混合推荐优先级正确性
- Property 17: 混合推荐置信度增强
- Property 18: 混合推荐来源标记
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.hybrid_recommender import HybridRecommender, HybridResult, recommend


# ============================================================================
# Property 16: 混合推荐优先级正确性
# **Feature: recommendation-engine-optimization, Property 16: 混合推荐优先级正确性**
# **Validates: Requirements 7.1**
# ============================================================================

class TestProperty16RulePriority:
    """
    Property 16: 混合推荐优先级正确性
    
    *For any* 规则推荐置信度>=0.85的场景，混合推荐器应优先采用规则推荐结果
    """
    
    @settings(max_examples=100)
    @given(
        rule_confidence=st.floats(min_value=0.85, max_value=1.0),
        model_confidence=st.floats(min_value=0.0, max_value=1.0),
        rule_direction=st.sampled_from(['home_win', 'away_win']),
        model_direction=st.sampled_from(['home', 'away', 'none'])
    )
    def test_high_confidence_rule_priority(self, rule_confidence, model_confidence, 
                                           rule_direction, model_direction):
        """规则置信度>=0.85时应优先采用规则推荐"""
        recommender = HybridRecommender()
        
        model_result = {'direction': model_direction, 'confidence': model_confidence, 'reason': '模型推荐'}
        rule_result = {'recommendation': rule_direction, 'confidence': rule_confidence, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        expected_direction = 'home' if rule_direction == 'home_win' else 'away'
        assert result['direction'] == expected_direction, \
            f"规则置信度{rule_confidence}>=0.85时应采用规则方向{expected_direction}"
        assert result['source'] == 'rule', "高置信度规则应标记为rule来源"


# ============================================================================
# Property 17: 混合推荐置信度增强
# **Feature: recommendation-engine-optimization, Property 17: 混合推荐置信度增强**
# **Validates: Requirements 7.2**
# ============================================================================

class TestProperty17ConfidenceBoost:
    """
    Property 17: 混合推荐置信度增强
    
    *For any* 规则推荐与模型推荐方向一致的场景，混合推荐器应增强置信度（乘以1.3系数，上限1.0）
    """
    
    @settings(max_examples=100)
    @given(
        rule_confidence=st.floats(min_value=0.3, max_value=0.84),  # 低于优先阈值
        model_confidence=st.floats(min_value=0.3, max_value=0.84),
        direction=st.sampled_from(['home', 'away'])
    )
    def test_same_direction_confidence_boost(self, rule_confidence, model_confidence, direction):
        """规则与模型方向一致时应增强置信度"""
        recommender = HybridRecommender()
        
        rule_direction = 'home_win' if direction == 'home' else 'away_win'
        model_result = {'direction': direction, 'confidence': model_confidence, 'reason': '模型推荐'}
        rule_result = {'recommendation': rule_direction, 'confidence': rule_confidence, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        # 计算期望的增强置信度
        avg_confidence = (rule_confidence + model_confidence) / 2
        expected_boost = min(avg_confidence * 1.3, 1.0)
        
        assert result['source'] == 'hybrid', "方向一致时应标记为hybrid来源"
        assert abs(result['confidence'] - expected_boost) < 0.001, \
            f"置信度应为{expected_boost}，实际为{result['confidence']}"
    
    @settings(max_examples=100)
    @given(
        rule_confidence=st.floats(min_value=0.5, max_value=0.84),
        model_confidence=st.floats(min_value=0.5, max_value=0.84),
        direction=st.sampled_from(['home', 'away'])
    )
    def test_confidence_not_exceed_one(self, rule_confidence, model_confidence, direction):
        """增强后的置信度不应超过1.0"""
        recommender = HybridRecommender()
        
        rule_direction = 'home_win' if direction == 'home' else 'away_win'
        model_result = {'direction': direction, 'confidence': model_confidence, 'reason': '模型推荐'}
        rule_result = {'recommendation': rule_direction, 'confidence': rule_confidence, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['confidence'] <= 1.0, f"置信度{result['confidence']}不应超过1.0"


# ============================================================================
# Property 18: 混合推荐来源标记
# **Feature: recommendation-engine-optimization, Property 18: 混合推荐来源标记**
# **Validates: Requirements 7.5**
# ============================================================================

class TestProperty18SourceLabel:
    """
    Property 18: 混合推荐来源标记
    
    *For any* 混合推荐结果，应正确标记推荐来源（rule/model/hybrid）
    """
    
    @settings(max_examples=100)
    @given(
        rule_confidence=st.floats(min_value=0.0, max_value=1.0),
        model_confidence=st.floats(min_value=0.0, max_value=1.0),
        rule_direction=st.sampled_from(['home_win', 'away_win', 'none']),
        model_direction=st.sampled_from(['home', 'away', 'none'])
    )
    def test_source_always_valid(self, rule_confidence, model_confidence, 
                                  rule_direction, model_direction):
        """来源标记应始终是有效值"""
        recommender = HybridRecommender()
        
        model_result = {'direction': model_direction, 'confidence': model_confidence, 'reason': '模型推荐'}
        rule_result = {'recommendation': rule_direction, 'confidence': rule_confidence, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        valid_sources = ['rule', 'model', 'hybrid']
        assert result['source'] in valid_sources, \
            f"来源'{result['source']}'不是有效值，应为{valid_sources}之一"
    
    @settings(max_examples=100)
    @given(
        model_confidence=st.floats(min_value=0.0, max_value=1.0),
        model_direction=st.sampled_from(['home', 'away', 'none'])
    )
    def test_no_rule_source_is_model(self, model_confidence, model_direction):
        """无规则结果时来源应为model"""
        recommender = HybridRecommender()
        
        model_result = {'direction': model_direction, 'confidence': model_confidence, 'reason': '模型推荐'}
        
        result = recommender.recommend(model_result, None)
        
        assert result['source'] == 'model', "无规则结果时来源应为model"


# ============================================================================
# 单元测试 - 具体场景
# ============================================================================

class TestSpecificScenarios:
    """具体场景测试"""
    
    def test_high_confidence_rule_wins(self):
        """高置信度规则优先"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'away', 'confidence': 0.9, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'home_win', 'confidence': 0.90, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['direction'] == 'home'
        assert result['source'] == 'rule'
    
    def test_same_direction_hybrid(self):
        """方向一致时为混合推荐"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'home', 'confidence': 0.6, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'home_win', 'confidence': 0.7, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['direction'] == 'home'
        assert result['source'] == 'hybrid'
        # (0.6 + 0.7) / 2 * 1.3 = 0.845
        assert abs(result['confidence'] - 0.845) < 0.001
    
    def test_conflict_higher_rule_wins(self):
        """冲突时高置信度规则获胜"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'away', 'confidence': 0.5, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'home_win', 'confidence': 0.7, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['direction'] == 'home'
        assert result['source'] == 'rule'
        # 0.7 * 0.8 = 0.56
        assert abs(result['confidence'] - 0.56) < 0.001
    
    def test_conflict_higher_model_wins(self):
        """冲突时高置信度模型获胜"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'away', 'confidence': 0.8, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'home_win', 'confidence': 0.5, 'reason': '规则推荐'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['direction'] == 'away'
        assert result['source'] == 'model'
        # 0.8 * 0.8 = 0.64
        assert abs(result['confidence'] - 0.64) < 0.001
    
    def test_no_rule_result(self):
        """无规则结果时使用模型"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'home', 'confidence': 0.75, 'reason': '模型推荐'}
        
        result = recommender.recommend(model_result, None)
        
        assert result['direction'] == 'home'
        assert result['source'] == 'model'
        assert result['confidence'] == 0.75
    
    def test_rule_none_direction(self):
        """规则无推荐时使用模型"""
        recommender = HybridRecommender()
        
        model_result = {'direction': 'away', 'confidence': 0.65, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'none', 'confidence': 0.0, 'reason': '无匹配规则'}
        
        result = recommender.recommend(model_result, rule_result)
        
        assert result['direction'] == 'away'
        assert result['source'] == 'model'
    
    def test_normalize_direction(self):
        """方向标准化"""
        recommender = HybridRecommender()
        
        assert recommender._normalize_direction('home_win') == 'home'
        assert recommender._normalize_direction('away_win') == 'away'
        assert recommender._normalize_direction('home') == 'home'
        assert recommender._normalize_direction('away') == 'away'
        assert recommender._normalize_direction('none') == 'none'
        assert recommender._normalize_direction('draw') == 'none'
    
    def test_get_source_label(self):
        """来源标签"""
        recommender = HybridRecommender()
        
        assert recommender.get_source_label('rule') == '规则推荐'
        assert recommender.get_source_label('model') == '模型推荐'
        assert recommender.get_source_label('hybrid') == '混合推荐'
        assert recommender.get_source_label('unknown') == '未知来源'


# ============================================================================
# 便捷函数测试
# ============================================================================

class TestConvenienceFunction:
    """便捷函数测试"""
    
    def test_recommend_function(self):
        """测试recommend便捷函数"""
        model_result = {'direction': 'home', 'confidence': 0.7, 'reason': '模型推荐'}
        rule_result = {'recommendation': 'home_win', 'confidence': 0.6, 'reason': '规则推荐'}
        
        result = recommend(model_result, rule_result)
        
        assert result['direction'] == 'home'
        assert result['source'] == 'hybrid'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
