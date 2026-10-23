"""
BetTypeSelector 属性测试

使用 hypothesis 库进行属性测试，验证投注类型选择器的正确性。

测试覆盖:
- Property 8: 逆盘投注类型选择
- Property 9: 深盘蚊子肉投注类型选择
- Property 10: 让球推荐信息完整性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.bet_type_selector import BetTypeSelector, select_bet_type


# ============================================================================
# Property 8: 逆盘投注类型选择
# **Feature: recommendation-engine-optimization, Property 8: 逆盘投注类型选择**
# **Validates: Requirements 3.1**
# ============================================================================

class TestProperty8NiPanBetType:
    """
    Property 8: 逆盘投注类型选择
    
    *For any* 推荐方向为受让方（逆盘）的场景，投注类型选择器应返回handicap类型
    """
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=0.25, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_home_ni_pan_returns_handicap(self, handicap, euro_odds):
        """主队受让（逆盘）时应返回handicap类型"""
        selector = BetTypeSelector()
        # 主队推荐 + 主队受让 (handicap > 0) = 逆盘
        result = selector.select_bet_type('home', handicap, euro_odds, '主队', '客队')
        
        assert result['bet_type'] == 'handicap', \
            f"主队受让{handicap}时应返回handicap类型"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=-2.0, max_value=-0.25, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_away_ni_pan_returns_handicap(self, handicap, euro_odds):
        """客队受让（逆盘）时应返回handicap类型"""
        selector = BetTypeSelector()
        # 客队推荐 + 客队受让 (handicap < 0) = 逆盘
        result = selector.select_bet_type('away', handicap, euro_odds, '主队', '客队')
        
        assert result['bet_type'] == 'handicap', \
            f"客队受让{handicap}时应返回handicap类型"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=0.25, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_ni_pan_reason_contains_shourang(self, handicap, euro_odds):
        """逆盘推荐理由应包含'受让'关键词"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', handicap, euro_odds, '主队', '客队')
        
        assert '受让' in result['handicap_bet_reason'], \
            f"逆盘推荐理由'{result['handicap_bet_reason']}'应包含'受让'关键词"


# ============================================================================
# Property 9: 深盘蚊子肉投注类型选择
# **Feature: recommendation-engine-optimization, Property 9: 深盘蚊子肉投注类型选择**
# **Validates: Requirements 3.2**
# ============================================================================

class TestProperty9DeepMosquitoBetType:
    """
    Property 9: 深盘蚊子肉投注类型选择
    
    *For any* 深盘(>=1.0)且欧赔<1.6的场景，投注类型选择器应返回handicap类型
    """
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=-2.0, max_value=-1.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=1.59, allow_nan=False)
    )
    def test_deep_mosquito_home_returns_handicap(self, handicap, euro_odds):
        """深盘蚊子肉（主队让球）时应返回handicap类型"""
        selector = BetTypeSelector()
        # 主队推荐 + 主队让球 (handicap < 0) + 欧赔<1.6 = 深盘蚊子肉
        result = selector.select_bet_type('home', handicap, euro_odds, '主队', '客队')
        
        assert result['bet_type'] == 'handicap', \
            f"深盘{abs(handicap)}蚊子肉欧赔{euro_odds}时应返回handicap类型"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=1.0, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=1.59, allow_nan=False)
    )
    def test_deep_mosquito_away_returns_handicap(self, handicap, euro_odds):
        """深盘蚊子肉（客队让球）时应返回handicap类型"""
        selector = BetTypeSelector()
        # 客队推荐 + 客队让球 (handicap > 0) + 欧赔<1.6 = 深盘蚊子肉
        result = selector.select_bet_type('away', handicap, euro_odds, '主队', '客队')
        
        assert result['bet_type'] == 'handicap', \
            f"深盘{abs(handicap)}蚊子肉欧赔{euro_odds}时应返回handicap类型"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=-2.0, max_value=-1.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=1.59, allow_nan=False)
    )
    def test_deep_mosquito_reason_contains_keyword(self, handicap, euro_odds):
        """深盘蚊子肉推荐理由应包含'蚊子肉'关键词"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', handicap, euro_odds, '主队', '客队')
        
        assert '蚊子肉' in result['handicap_bet_reason'], \
            f"深盘蚊子肉推荐理由'{result['handicap_bet_reason']}'应包含'蚊子肉'关键词"


# ============================================================================
# Property 10: 让球推荐信息完整性
# **Feature: recommendation-engine-optimization, Property 10: 让球推荐信息完整性**
# **Validates: Requirements 3.5**
# ============================================================================

class TestProperty10HandicapInfoCompleteness:
    """
    Property 10: 让球推荐信息完整性
    
    *For any* 让球推荐结果，应包含完整的队名、盘口值和盘口类型描述
    """
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=0.25, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_handicap_result_contains_team_name(self, handicap, euro_odds):
        """让球推荐应包含队名"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', handicap, euro_odds, '曼联', '利物浦')
        
        if result['bet_type'] == 'handicap':
            assert '曼联' in result['handicap_bet_reason'], \
                f"让球推荐理由'{result['handicap_bet_reason']}'应包含队名'曼联'"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=0.25, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_handicap_result_contains_handicap_value(self, handicap, euro_odds):
        """让球推荐应包含盘口值"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', handicap, euro_odds, '曼联', '利物浦')
        
        if result['bet_type'] == 'handicap':
            # 检查理由中是否包含数字（盘口值）
            import re
            has_number = bool(re.search(r'[+-]?\d+\.?\d*', result['handicap_bet_reason']))
            assert has_number, \
                f"让球推荐理由'{result['handicap_bet_reason']}'应包含盘口值"
    
    @settings(max_examples=100)
    @given(
        handicap=st.floats(min_value=0.25, max_value=2.0, allow_nan=False),
        euro_odds=st.floats(min_value=1.1, max_value=5.0, allow_nan=False)
    )
    def test_handicap_result_contains_type_description(self, handicap, euro_odds):
        """让球推荐应包含盘口类型描述"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', handicap, euro_odds, '曼联', '利物浦')
        
        if result['bet_type'] == 'handicap':
            # 检查是否包含盘口类型关键词
            type_keywords = ['平手盘', '平半盘', '半球盘', '半一盘', '一球盘', '球半盘', '深盘']
            has_type = any(kw in result['handicap_bet_reason'] for kw in type_keywords)
            assert has_type, \
                f"让球推荐理由'{result['handicap_bet_reason']}'应包含盘口类型描述"


# ============================================================================
# 单元测试 - 深盘顺盘
# ============================================================================

class TestDeepShunPan:
    """深盘顺盘测试"""
    
    def test_deep_shun_pan_home_returns_handicap(self):
        """深盘顺盘（主队让球）应返回handicap类型"""
        selector = BetTypeSelector()
        # 主队推荐 + 主队让球 (handicap < -1.0) + 欧赔>=1.6 = 深盘顺盘
        result = selector.select_bet_type('home', -1.5, 2.0, '主队', '客队')
        
        assert result['bet_type'] == 'handicap'
        assert '顺盘' in result['handicap_bet_reason']
    
    def test_deep_shun_pan_away_returns_handicap(self):
        """深盘顺盘（客队让球）应返回handicap类型"""
        selector = BetTypeSelector()
        # 客队推荐 + 客队让球 (handicap > 1.0) + 欧赔>=1.6 = 深盘顺盘
        result = selector.select_bet_type('away', 1.5, 2.0, '主队', '客队')
        
        assert result['bet_type'] == 'handicap'
        assert '顺盘' in result['handicap_bet_reason']


# ============================================================================
# 单元测试 - 浅盘顺盘过滤
# ============================================================================

class TestShallowShunPanFilter:
    """浅盘顺盘过滤测试"""
    
    def test_shallow_shun_pan_should_filter(self):
        """浅盘顺盘应标记为需要过滤"""
        selector = BetTypeSelector()
        # 主队推荐 + 主队让球 (handicap < 0 且 < 1.0) = 浅盘顺盘
        result = selector.select_bet_type('home', -0.5, 2.0, '主队', '客队')
        
        assert result['should_filter'] == True, "浅盘顺盘应标记为需要过滤"
    
    def test_shallow_ni_pan_should_not_filter(self):
        """浅盘逆盘不应标记为需要过滤"""
        selector = BetTypeSelector()
        # 主队推荐 + 主队受让 (handicap > 0 且 < 1.0) = 浅盘逆盘
        result = selector.select_bet_type('home', 0.5, 2.0, '主队', '客队')
        
        assert result['should_filter'] == False, "浅盘逆盘不应标记为需要过滤"


# ============================================================================
# 单元测试 - 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_zero_handicap(self):
        """平手盘应返回欧赔类型"""
        selector = BetTypeSelector()
        result = selector.select_bet_type('home', 0, 2.0, '主队', '客队')
        
        assert result['bet_type'] == 'euro'
    
    def test_format_handicap_recommendation(self):
        """格式化让球推荐文本"""
        selector = BetTypeSelector()
        
        # 主队让球
        text = selector.format_handicap_recommendation('home', -0.5, '曼联', '利物浦')
        assert text == '曼联 -0.5'
        
        # 主队受让
        text = selector.format_handicap_recommendation('home', 0.5, '曼联', '利物浦')
        assert text == '曼联 +0.5'
        
        # 客队让球
        text = selector.format_handicap_recommendation('away', -0.5, '曼联', '利物浦')
        assert text == '利物浦 +0.5'
        
        # 平手
        text = selector.format_handicap_recommendation('home', 0, '曼联', '利物浦')
        assert text == '曼联 平手'
    
    def test_handicap_type_names(self):
        """盘口类型名称"""
        selector = BetTypeSelector()
        
        assert selector._get_handicap_type_name(0.1) == '平手盘'
        assert selector._get_handicap_type_name(0.5) == '平半盘'
        assert selector._get_handicap_type_name(0.75) == '半球盘'
        assert selector._get_handicap_type_name(1.0) == '半一盘'
        assert selector._get_handicap_type_name(1.25) == '一球盘'
        assert selector._get_handicap_type_name(1.5) == '球半盘'
        assert selector._get_handicap_type_name(2.0) == '深盘'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
