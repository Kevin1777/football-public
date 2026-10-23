"""
ResultFormatter 属性测试

使用 hypothesis 库进行属性测试，验证推荐结果格式化器的正确性。

测试覆盖:
- Property 13: 推荐结果结构完整性
- Property 14: 拒绝原因明确性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.result_formatter import (
    ResultFormatter, RecommendationResult, 
    format_result, format_rejection
)


# ============================================================================
# Property 13: 推荐结果结构完整性
# **Feature: recommendation-engine-optimization, Property 13: 推荐结果结构完整性**
# **Validates: Requirements 5.1, 5.2, 5.3**
# ============================================================================

class TestProperty13ResultCompleteness:
    """
    Property 13: 推荐结果结构完整性
    
    *For any* 有推荐方向的结果，应包含信号列表（最多4个）、推荐级别、置信度和格式化文本
    """
    
    @settings(max_examples=100)
    @given(
        direction=st.sampled_from(['home', 'away']),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        level=st.sampled_from(['Elite', 'Strong', 'Standard']),
        score=st.floats(min_value=0, max_value=200, allow_nan=False),
        handicap=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False)
    )
    def test_result_contains_signals(self, direction, confidence, level, score, handicap):
        """推荐结果应包含信号列表"""
        formatter = ResultFormatter()
        signals = ['ELITE_HOT_VOL', 'PCT_BF', 'HIGH_BF', 'KELLY_SIG', 'EXTRA_SIG']
        
        result = formatter.format_result(
            direction=direction,
            confidence=confidence,
            level=level,
            score=score,
            signals=signals,
            home_team='主队',
            away_team='客队',
            handicap=handicap
        )
        
        assert 'signals' in result, "结果应包含signals字段"
        assert isinstance(result['signals'], list), "signals应为列表"
        assert len(result['signals']) <= 4, "信号列表最多4个"
    
    @settings(max_examples=100)
    @given(
        direction=st.sampled_from(['home', 'away']),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        level=st.sampled_from(['Elite', 'Strong', 'Standard']),
        score=st.floats(min_value=0, max_value=200, allow_nan=False),
        handicap=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False)
    )
    def test_result_contains_level(self, direction, confidence, level, score, handicap):
        """推荐结果应包含推荐级别"""
        formatter = ResultFormatter()
        
        result = formatter.format_result(
            direction=direction,
            confidence=confidence,
            level=level,
            score=score,
            signals=['SIG1'],
            home_team='主队',
            away_team='客队',
            handicap=handicap
        )
        
        assert 'level' in result, "结果应包含level字段"
        assert result['level'] == level, "level应与输入一致"
    
    @settings(max_examples=100)
    @given(
        direction=st.sampled_from(['home', 'away']),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        level=st.sampled_from(['Elite', 'Strong', 'Standard']),
        score=st.floats(min_value=0, max_value=200, allow_nan=False),
        handicap=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False)
    )
    def test_result_contains_confidence(self, direction, confidence, level, score, handicap):
        """推荐结果应包含置信度"""
        formatter = ResultFormatter()
        
        result = formatter.format_result(
            direction=direction,
            confidence=confidence,
            level=level,
            score=score,
            signals=['SIG1'],
            home_team='主队',
            away_team='客队',
            handicap=handicap
        )
        
        assert 'confidence' in result, "结果应包含confidence字段"
        assert 0.0 <= result['confidence'] <= 1.0, "confidence应在0-1之间"
    
    @settings(max_examples=100)
    @given(
        direction=st.sampled_from(['home', 'away']),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        level=st.sampled_from(['Elite', 'Strong', 'Standard']),
        score=st.floats(min_value=0, max_value=200, allow_nan=False),
        handicap=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False)
    )
    def test_result_contains_formatted_text(self, direction, confidence, level, score, handicap):
        """推荐结果应包含格式化文本"""
        formatter = ResultFormatter()
        
        result = formatter.format_result(
            direction=direction,
            confidence=confidence,
            level=level,
            score=score,
            signals=['SIG1'],
            home_team='曼联',
            away_team='利物浦',
            handicap=handicap
        )
        
        assert 'formatted' in result, "结果应包含formatted字段"
        assert isinstance(result['formatted'], str), "formatted应为字符串"
        assert len(result['formatted']) > 0, "formatted不应为空"


# ============================================================================
# Property 14: 拒绝原因明确性
# **Feature: recommendation-engine-optimization, Property 14: 拒绝原因明确性**
# **Validates: Requirements 5.4**
# ============================================================================

class TestProperty14RejectionReason:
    """
    Property 14: 拒绝原因明确性
    
    *For any* 拒绝推荐的结果，应返回非空的拒绝原因字符串
    """
    
    @settings(max_examples=100)
    @given(reason=st.text(min_size=1, max_size=100))
    def test_rejection_has_reason(self, reason):
        """拒绝推荐应包含原因"""
        formatter = ResultFormatter()
        result = formatter.format_rejection(reason)
        
        assert 'reason' in result, "拒绝结果应包含reason字段"
        assert isinstance(result['reason'], str), "reason应为字符串"
        assert len(result['reason']) > 0, "reason不应为空"
    
    @settings(max_examples=100)
    @given(reason=st.text(min_size=1, max_size=100))
    def test_rejection_direction_is_none(self, reason):
        """拒绝推荐的direction应为none"""
        formatter = ResultFormatter()
        result = formatter.format_rejection(reason)
        
        assert result['direction'] == 'none', "拒绝推荐的direction应为none"
    
    @settings(max_examples=100)
    @given(reason=st.text(min_size=1, max_size=100))
    def test_rejection_confidence_is_zero(self, reason):
        """拒绝推荐的confidence应为0"""
        formatter = ResultFormatter()
        result = formatter.format_rejection(reason)
        
        assert result['confidence'] == 0.0, "拒绝推荐的confidence应为0"
    
    def test_empty_reason_uses_default(self):
        """空原因应使用默认值"""
        formatter = ResultFormatter()
        result = formatter.format_rejection('')
        
        assert result['reason'] == '未知原因', "空原因应使用默认值'未知原因'"


# ============================================================================
# 单元测试 - 格式化文本
# ============================================================================

class TestFormatText:
    """格式化文本测试"""
    
    def test_format_home_let(self):
        """主队让球格式化"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('home', -0.5, '曼联', '利物浦')
        
        assert text == '曼联 -0.5'
    
    def test_format_home_receive(self):
        """主队受让格式化"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('home', 0.5, '曼联', '利物浦')
        
        assert text == '曼联 +0.5'
    
    def test_format_away_let(self):
        """客队让球格式化"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('away', -0.5, '曼联', '利物浦')
        
        assert text == '利物浦 +0.5'
    
    def test_format_away_receive(self):
        """客队受让格式化"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('away', 0.5, '曼联', '利物浦')
        
        assert text == '利物浦 -0.5'
    
    def test_format_draw(self):
        """平手盘格式化"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('home', 0, '曼联', '利物浦')
        
        assert text == '曼联 平手'
    
    def test_format_none_direction(self):
        """无推荐方向"""
        formatter = ResultFormatter()
        text = formatter.format_recommendation_text('none', 0, '曼联', '利物浦')
        
        assert text == ''


# ============================================================================
# 单元测试 - 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_limit_signals(self):
        """限制信号数量"""
        formatter = ResultFormatter()
        signals = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
        
        limited = formatter.limit_signals(signals)
        
        assert len(limited) == 4
        assert limited == ['S1', 'S2', 'S3', 'S4']
    
    def test_validate_result_complete(self):
        """验证完整结果"""
        formatter = ResultFormatter()
        result = {
            'direction': 'home',
            'confidence': 0.85,
            'level': 'Elite',
            'reason': 'test',
            'signals': ['S1'],
            'formatted': '曼联 -0.5',
            'home_team': '曼联',
            'away_team': '利物浦',
        }
        
        assert formatter.validate_result(result) == True
    
    def test_validate_result_incomplete(self):
        """验证不完整结果"""
        formatter = ResultFormatter()
        result = {'direction': 'home'}
        
        assert formatter.validate_result(result) == False
    
    def test_format_handicap_reason(self):
        """格式化让球推荐理由"""
        formatter = ResultFormatter()
        reason = formatter.format_handicap_reason('曼联', -0.5, '半一盘', '顺盘')
        
        assert reason == '让球推荐: 曼联 -0.50 (半一盘顺盘)'
    
    def test_recommendation_result_to_dict(self):
        """RecommendationResult转换为字典"""
        result = RecommendationResult(
            direction='home',
            confidence=0.85,
            level='Elite',
            score=75,
            signals=['S1', 'S2', 'S3', 'S4', 'S5'],
        )
        
        d = result.to_dict()
        
        assert d['direction'] == 'home'
        assert d['confidence'] == 0.85
        assert len(d['signals']) == 4  # 最多4个


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
