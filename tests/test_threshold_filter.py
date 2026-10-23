"""
DynamicThresholdFilter 属性测试

使用 hypothesis 库进行属性测试，验证阈值过滤器的正确性。

测试覆盖:
- Property 5: 成交量过滤正确性
- Property 6: 深盘过滤正确性
- Property 7: 评分差值过滤正确性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.threshold_filter import DynamicThresholdFilter, should_recommend


# ============================================================================
# 测试策略/生成器
# ============================================================================

@st.composite
def low_volume_metrics_strategy(draw):
    """生成低成交量的指标数据 (volume < 50K)"""
    return {
        'total_volume': draw(st.floats(min_value=0, max_value=49999, allow_nan=False)),
        'handicap_current': draw(st.floats(min_value=-1.5, max_value=1.5, allow_nan=False)),
    }


@st.composite
def deep_handicap_metrics_strategy(draw):
    """生成深盘指标数据 (handicap >= 2.0)"""
    handicap = draw(st.floats(min_value=2.0, max_value=3.0, allow_nan=False))
    # 随机选择正负
    if draw(st.booleans()):
        handicap = -handicap
    
    return {
        'total_volume': draw(st.floats(min_value=100000, max_value=2000000, allow_nan=False)),
        'handicap_current': handicap,
    }


@st.composite
def normal_metrics_strategy(draw):
    """生成正常的指标数据"""
    return {
        'total_volume': draw(st.floats(min_value=100000, max_value=2000000, allow_nan=False)),
        'handicap_current': draw(st.floats(min_value=-1.5, max_value=1.5, allow_nan=False)),
    }


# ============================================================================
# Property 5: 成交量过滤正确性
# **Feature: recommendation-engine-optimization, Property 5: 成交量过滤正确性**
# **Validates: Requirements 2.2**
# ============================================================================

class TestProperty5VolumeFilter:
    """
    Property 5: 成交量过滤正确性
    
    *For any* 成交量低于50K的比赛数据，推荐引擎应拒绝推荐并返回包含"成交量"关键词的拒绝原因
    """
    
    @settings(max_examples=100)
    @given(metrics=low_volume_metrics_strategy())
    def test_low_volume_rejected(self, metrics):
        """成交量低于50K时应拒绝推荐"""
        filter_obj = DynamicThresholdFilter()
        should_rec, reason = filter_obj.should_recommend(metrics, 60, 30)
        
        volume = metrics['total_volume']
        assume(volume < 50000)
        
        assert should_rec == False, f"成交量{volume/1000:.0f}K<50K时应拒绝推荐"
    
    @settings(max_examples=100)
    @given(metrics=low_volume_metrics_strategy())
    def test_low_volume_reason_contains_keyword(self, metrics):
        """拒绝原因应包含"成交量"关键词"""
        filter_obj = DynamicThresholdFilter()
        should_rec, reason = filter_obj.should_recommend(metrics, 60, 30)
        
        volume = metrics['total_volume']
        assume(volume < 50000)
        
        assert "成交量" in reason, f"拒绝原因'{reason}'应包含'成交量'关键词"
    
    @settings(max_examples=100)
    @given(volume=st.floats(min_value=50000, max_value=2000000, allow_nan=False))
    def test_sufficient_volume_not_rejected_by_volume(self, volume):
        """成交量充足时不应因成交量被拒绝"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': volume, 'handicap_current': 0.5}
        
        result = filter_obj._filter_by_volume(metrics)
        
        assert result.should_recommend == True, f"成交量{volume/1000:.0f}K>=50K时不应因成交量被拒绝"


# ============================================================================
# Property 6: 深盘过滤正确性
# **Feature: recommendation-engine-optimization, Property 6: 深盘过滤正确性**
# **Validates: Requirements 2.3**
# ============================================================================

class TestProperty6DeepHandicapFilter:
    """
    Property 6: 深盘过滤正确性
    
    *For any* 盘口深度超过2.0的比赛数据，推荐引擎应拒绝推荐并返回包含"深盘"关键词的拒绝原因
    """
    
    @settings(max_examples=100)
    @given(metrics=deep_handicap_metrics_strategy())
    def test_deep_handicap_rejected(self, metrics):
        """盘口深度超过2.0时应拒绝推荐"""
        filter_obj = DynamicThresholdFilter()
        should_rec, reason = filter_obj.should_recommend(metrics, 60, 30)
        
        abs_handicap = abs(metrics['handicap_current'])
        assume(abs_handicap >= 2.0)
        
        assert should_rec == False, f"盘口深度{abs_handicap}>=2.0时应拒绝推荐"
    
    @settings(max_examples=100)
    @given(metrics=deep_handicap_metrics_strategy())
    def test_deep_handicap_reason_contains_keyword(self, metrics):
        """拒绝原因应包含"深盘"关键词"""
        filter_obj = DynamicThresholdFilter()
        should_rec, reason = filter_obj.should_recommend(metrics, 60, 30)
        
        abs_handicap = abs(metrics['handicap_current'])
        assume(abs_handicap >= 2.0)
        
        assert "深盘" in reason, f"拒绝原因'{reason}'应包含'深盘'关键词"
    
    @settings(max_examples=100)
    @given(handicap=st.floats(min_value=-1.99, max_value=1.99, allow_nan=False))
    def test_normal_handicap_not_rejected_by_depth(self, handicap):
        """正常盘口深度时不应因深盘被拒绝"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': handicap}
        
        result = filter_obj._filter_by_deep_handicap(metrics)
        
        assert result.should_recommend == True, f"盘口深度{abs(handicap)}<2.0时不应因深盘被拒绝"


# ============================================================================
# Property 7: 评分差值过滤正确性
# **Feature: recommendation-engine-optimization, Property 7: 评分差值过滤正确性**
# **Validates: Requirements 2.4**
# ============================================================================

class TestProperty7ScoreDiffFilter:
    """
    Property 7: 评分差值过滤正确性
    
    *For any* 主客队评分差值小于20分的比赛数据，推荐引擎应拒绝推荐
    """
    
    @settings(max_examples=100)
    @given(
        score_home=st.floats(min_value=0, max_value=100, allow_nan=False),
        score_away=st.floats(min_value=0, max_value=100, allow_nan=False)
    )
    def test_small_score_diff_rejected(self, score_home, score_away):
        """评分差值小于20时应拒绝推荐"""
        score_diff = abs(score_home - score_away)
        assume(score_diff < 20)
        
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': 0.5}
        should_rec, reason = filter_obj.should_recommend(metrics, score_home, score_away)
        
        assert should_rec == False, f"评分差值{score_diff:.0f}<20时应拒绝推荐"
    
    @settings(max_examples=100)
    @given(
        score_home=st.floats(min_value=0, max_value=100, allow_nan=False),
        score_away=st.floats(min_value=0, max_value=100, allow_nan=False)
    )
    def test_small_score_diff_reason_contains_keyword(self, score_home, score_away):
        """拒绝原因应包含"评分"关键词"""
        score_diff = abs(score_home - score_away)
        assume(score_diff < 20)
        
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': 0.5}
        should_rec, reason = filter_obj.should_recommend(metrics, score_home, score_away)
        
        assert "评分" in reason, f"拒绝原因'{reason}'应包含'评分'关键词"
    
    @settings(max_examples=100)
    @given(
        score_home=st.floats(min_value=50, max_value=100, allow_nan=False),
        score_away=st.floats(min_value=0, max_value=30, allow_nan=False)
    )
    def test_large_score_diff_not_rejected_by_score(self, score_home, score_away):
        """评分差值充足时不应因评分被拒绝"""
        score_diff = abs(score_home - score_away)
        assume(score_diff >= 20)
        
        filter_obj = DynamicThresholdFilter()
        
        result = filter_obj._filter_by_score_diff(score_home, score_away)
        
        assert result.should_recommend == True, f"评分差值{score_diff:.0f}>=20时不应因评分被拒绝"


# ============================================================================
# 单元测试 - 浅盘顺盘过滤
# ============================================================================

class TestShallowHandicapFilter:
    """浅盘顺盘过滤测试"""
    
    def test_shallow_shun_pan_home_rejected(self):
        """浅盘顺盘(主队推荐+主队让球)应被过滤"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': -0.5}  # 主队让0.5
        
        result = filter_obj._filter_by_shallow_handicap(metrics, 'home')
        
        assert result.should_recommend == False, "浅盘顺盘应被过滤"
    
    def test_shallow_shun_pan_away_rejected(self):
        """浅盘顺盘(客队推荐+客队让球)应被过滤"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': 0.5}  # 客队让0.5
        
        result = filter_obj._filter_by_shallow_handicap(metrics, 'away')
        
        assert result.should_recommend == False, "浅盘顺盘应被过滤"
    
    def test_shallow_ni_pan_not_rejected(self):
        """浅盘逆盘不应被过滤"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': -0.5}  # 主队让0.5
        
        result = filter_obj._filter_by_shallow_handicap(metrics, 'away')  # 推客队=逆盘
        
        assert result.should_recommend == True, "浅盘逆盘不应被过滤"
    
    def test_deep_handicap_not_filtered(self):
        """深盘不应被浅盘过滤器过滤"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': 100000, 'handicap_current': -1.5}  # 深盘
        
        result = filter_obj._filter_by_shallow_handicap(metrics, 'home')
        
        assert result.should_recommend == True, "深盘不应被浅盘过滤器过滤"


# ============================================================================
# 单元测试 - 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_empty_metrics(self):
        """空指标应使用默认值"""
        filter_obj = DynamicThresholdFilter()
        should_rec, reason = filter_obj.should_recommend({}, 60, 30)
        
        # 空指标 volume=0 应被拒绝
        assert should_rec == False
        assert "成交量" in reason
    
    def test_none_values(self):
        """None值应被处理为0"""
        filter_obj = DynamicThresholdFilter()
        metrics = {'total_volume': None, 'handicap_current': None}
        should_rec, reason = filter_obj.should_recommend(metrics, 60, 30)
        
        assert should_rec == False
    
    def test_tier1_league_detection(self):
        """一级联赛检测"""
        filter_obj = DynamicThresholdFilter()
        
        assert filter_obj.is_tier1_league('英超') == True
        assert filter_obj.is_tier1_league('西甲') == True
        assert filter_obj.is_tier1_league('未知联赛') == False
        assert filter_obj.is_tier1_league('') == False
        assert filter_obj.is_tier1_league(None) == False
    
    def test_get_thresholds(self):
        """获取阈值配置"""
        filter_obj = DynamicThresholdFilter()
        
        thresholds = filter_obj.get_thresholds('英超')
        assert thresholds['league_tier'] == 1
        assert thresholds['min_volume'] == 50000
        
        thresholds = filter_obj.get_thresholds('未知联赛')
        assert thresholds['league_tier'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
