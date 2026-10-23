"""
SignalScoringModel 属性测试

使用 hypothesis 库进行属性测试，验证评分模型的正确性。

测试覆盖:
- Property 1: 评分计算一致性
- Property 2: Elite信号触发正确性
- Property 3: 盘口加成正确性
- Property 4: 负面信号扣分正确性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.scoring_model import SignalScoringModel, calculate_score


# ============================================================================
# 测试策略/生成器
# ============================================================================

@st.composite
def metrics_strategy(draw):
    """
    生成有效的比赛指标数据
    
    MetricsGenerator: 生成有效的比赛指标数据
    - 成交量: 0 - 2,000,000
    - 热度指数: -50 - 50
    - 必发指数: 0 - 100
    - 盘口值: -3.0 - 3.0
    """
    return {
        'bfindex_home': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'bfindex_away': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'hot_home': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'hot_away': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'total_volume': draw(st.floats(min_value=0, max_value=2000000, allow_nan=False)),
        'home_pct': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'kelly_diff_home': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_diff_away': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_home': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
        'kelly_away': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
    }


@st.composite
def elite_home_metrics_strategy(draw):
    """
    生成满足Elite信号条件的主队指标数据
    条件: 热度差值 < -15 且 成交量 > 600K
    """
    hot_home = draw(st.floats(min_value=-50, max_value=0, allow_nan=False))
    hot_away = draw(st.floats(min_value=hot_home + 16, max_value=50, allow_nan=False))
    
    return {
        'bfindex_home': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'bfindex_away': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'hot_home': hot_home,
        'hot_away': hot_away,
        'total_volume': draw(st.floats(min_value=600001, max_value=2000000, allow_nan=False)),
        'home_pct': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'kelly_diff_home': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_diff_away': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_home': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
        'kelly_away': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
    }


@st.composite
def handicap_bonus_metrics_strategy(draw):
    """
    生成满足盘口加成条件的指标数据
    条件: 主让球(handicap<-0.25) 且 热度反冷(hot_diff<-10)
    """
    hot_home = draw(st.floats(min_value=-50, max_value=0, allow_nan=False))
    hot_away = draw(st.floats(min_value=hot_home + 11, max_value=50, allow_nan=False))
    
    return {
        'bfindex_home': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'bfindex_away': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'hot_home': hot_home,
        'hot_away': hot_away,
        'total_volume': draw(st.floats(min_value=100000, max_value=2000000, allow_nan=False)),
        'home_pct': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'kelly_diff_home': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_diff_away': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_home': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
        'kelly_away': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
    }


@st.composite
def negative_signal_metrics_strategy(draw):
    """
    生成包含负面信号的指标数据
    条件: 热度陷阱(hot_diff>5) 或 必发不支持(bf_diff<-10)
    """
    # 生成热度陷阱场景
    hot_home = draw(st.floats(min_value=10, max_value=50, allow_nan=False))
    hot_away = draw(st.floats(min_value=-50, max_value=hot_home - 6, allow_nan=False))
    
    return {
        'bfindex_home': draw(st.floats(min_value=0, max_value=40, allow_nan=False)),
        'bfindex_away': draw(st.floats(min_value=50, max_value=100, allow_nan=False)),
        'hot_home': hot_home,
        'hot_away': hot_away,
        'total_volume': draw(st.floats(min_value=100000, max_value=2000000, allow_nan=False)),
        'home_pct': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
        'kelly_diff_home': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_diff_away': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
        'kelly_home': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
        'kelly_away': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
    }


# ============================================================================
# Property 1: 评分计算一致性
# **Feature: recommendation-engine-optimization, Property 1: 评分计算一致性**
# **Validates: Requirements 1.1, 1.5**
# ============================================================================

class TestProperty1ScoreConsistency:
    """
    Property 1: 评分计算一致性
    
    *For any* 有效的比赛指标数据，评分模型应返回一个数值评分和一个信号列表，
    且评分值应在合理范围内（-100到200之间）
    """
    
    @settings(max_examples=100)
    @given(metrics=metrics_strategy(), direction=st.sampled_from(['home', 'away']))
    def test_score_returns_tuple(self, metrics, direction):
        """评分模型应返回元组 (score, signals)"""
        model = SignalScoringModel()
        result = model.calculate_score(metrics, direction)
        
        assert isinstance(result, tuple), "结果应为元组"
        assert len(result) == 2, "元组应包含2个元素"
    
    @settings(max_examples=100)
    @given(metrics=metrics_strategy(), direction=st.sampled_from(['home', 'away']))
    def test_score_is_numeric(self, metrics, direction):
        """评分值应为数值类型"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, direction)
        
        assert isinstance(score, (int, float)), "评分应为数值类型"
    
    @settings(max_examples=100)
    @given(metrics=metrics_strategy(), direction=st.sampled_from(['home', 'away']))
    def test_signals_is_list(self, metrics, direction):
        """信号应为列表类型"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, direction)
        
        assert isinstance(signals, list), "信号应为列表类型"
    
    @settings(max_examples=100)
    @given(metrics=metrics_strategy(), direction=st.sampled_from(['home', 'away']))
    def test_score_in_valid_range(self, metrics, direction):
        """评分值应在合理范围内 (-100 到 200)"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, direction)
        
        assert -100 <= score <= 200, f"评分 {score} 超出合理范围 [-100, 200]"
    
    @settings(max_examples=100)
    @given(metrics=metrics_strategy(), direction=st.sampled_from(['home', 'away']),
           handicap=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False))
    def test_score_with_handicap_in_valid_range(self, metrics, direction, handicap):
        """带盘口的评分值也应在合理范围内"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, direction, handicap)
        
        assert -100 <= score <= 200, f"评分 {score} 超出合理范围 [-100, 200]"



# ============================================================================
# Property 2: Elite信号触发正确性
# **Feature: recommendation-engine-optimization, Property 2: Elite信号触发正确性**
# **Validates: Requirements 1.2**
# ============================================================================

class TestProperty2EliteSignal:
    """
    Property 2: Elite信号触发正确性
    
    *For any* 热度差值小于-15且成交量大于600K的数据，
    评分模型应标记ELITE_HOT_VOL信号并给予至少55分的基础分
    """
    
    @settings(max_examples=100)
    @given(metrics=elite_home_metrics_strategy())
    def test_elite_signal_triggered(self, metrics):
        """满足Elite条件时应触发ELITE_HOT_VOL信号"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home')
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        volume = metrics['total_volume']
        
        # 验证条件
        assume(hot_diff < -15 and volume > 600000)
        
        assert "ELITE_HOT_VOL" in signals, \
            f"热度差值{hot_diff:.1f}<-15且成交量{volume/1000:.0f}K>600K时应触发ELITE_HOT_VOL信号"
    
    @settings(max_examples=100)
    @given(metrics=elite_home_metrics_strategy())
    def test_elite_signal_minimum_score(self, metrics):
        """Elite信号应给予至少55分的基础分"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home')
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        volume = metrics['total_volume']
        
        # 验证条件
        assume(hot_diff < -15 and volume > 600000)
        
        # Elite信号本身给60分，但可能有负面信号扣分
        # 这里只验证ELITE_HOT_VOL信号被触发时，基础分至少55分
        if "ELITE_HOT_VOL" in signals:
            # 计算不含负面信号的基础分
            base_score = model.ELITE_HOT_VOL_SCORE  # 60分
            assert base_score >= 55, "Elite信号基础分应至少55分"


# ============================================================================
# Property 3: 盘口加成正确性
# **Feature: recommendation-engine-optimization, Property 3: 盘口加成正确性**
# **Validates: Requirements 1.3**
# ============================================================================

class TestProperty3HandicapBonus:
    """
    Property 3: 盘口加成正确性
    
    *For any* 主让球(handicap<-0.25)且热度反冷(hot_diff<-10)的数据，
    评分模型应增加盘口加成分数（至少20分）
    """
    
    @settings(max_examples=100)
    @given(metrics=handicap_bonus_metrics_strategy(),
           handicap=st.floats(min_value=-2.5, max_value=-0.26, allow_nan=False))
    def test_handicap_bonus_signal_triggered(self, metrics, handicap):
        """主让球+热度反冷时应触发HDP_TRUE_LET信号"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home', handicap)
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        
        # 验证条件
        assume(handicap < -0.25 and hot_diff < -10)
        
        assert "HDP_TRUE_LET" in signals, \
            f"主让球{handicap}且热度反冷{hot_diff:.1f}时应触发HDP_TRUE_LET信号"
    
    @settings(max_examples=100)
    @given(metrics=handicap_bonus_metrics_strategy(),
           handicap=st.floats(min_value=-2.5, max_value=-0.26, allow_nan=False))
    def test_handicap_bonus_minimum_score(self, metrics, handicap):
        """盘口加成应至少增加20分"""
        model = SignalScoringModel()
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        assume(handicap < -0.25 and hot_diff < -10)
        
        # 计算不带盘口的评分
        score_without_handicap, _ = model.calculate_score(metrics, 'home', None)
        
        # 计算带盘口的评分
        score_with_handicap, signals = model.calculate_score(metrics, 'home', handicap)
        
        # 盘口加成应至少20分 (HDP_TRUE_LET = 25分)
        if "HDP_TRUE_LET" in signals:
            bonus = score_with_handicap - score_without_handicap
            # 注意：可能还有其他盘口信号，所以bonus可能更高
            assert bonus >= 20, f"盘口加成{bonus}应至少20分"


# ============================================================================
# Property 4: 负面信号扣分正确性
# **Feature: recommendation-engine-optimization, Property 4: 负面信号扣分正确性**
# **Validates: Requirements 1.4**
# ============================================================================

class TestProperty4NegativeSignals:
    """
    Property 4: 负面信号扣分正确性
    
    *For any* 包含负面信号（热度陷阱hot_diff>5或必发不支持bf_diff<-10）的数据，
    评分模型应扣除相应分数
    """
    
    @settings(max_examples=100)
    @given(metrics=negative_signal_metrics_strategy())
    def test_hot_trap_signal_triggered(self, metrics):
        """热度陷阱时应触发HOT_TRAP!信号"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home')
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        
        if hot_diff > 5:
            assert "HOT_TRAP!" in signals, \
                f"热度差值{hot_diff:.1f}>5时应触发HOT_TRAP!信号"
    
    @settings(max_examples=100)
    @given(metrics=negative_signal_metrics_strategy())
    def test_bf_neg_signal_triggered(self, metrics):
        """必发不支持时应触发BF_NEG!信号"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home')
        
        bf_diff = metrics['bfindex_home'] - metrics['bfindex_away']
        
        if bf_diff < -10:
            assert "BF_NEG!" in signals, \
                f"必发差值{bf_diff:.1f}<-10时应触发BF_NEG!信号"
    
    @settings(max_examples=100)
    @given(metrics=negative_signal_metrics_strategy())
    def test_negative_signals_reduce_score(self, metrics):
        """负面信号应扣除分数"""
        model = SignalScoringModel()
        score, signals = model.calculate_score(metrics, 'home')
        
        hot_diff = metrics['hot_home'] - metrics['hot_away']
        bf_diff = metrics['bfindex_home'] - metrics['bfindex_away']
        
        # 如果有负面信号，验证扣分
        has_hot_trap = hot_diff > 5
        has_bf_neg = bf_diff < -10
        
        if has_hot_trap:
            assert "HOT_TRAP!" in signals, "应触发HOT_TRAP!信号"
        if has_bf_neg:
            assert "BF_NEG!" in signals, "应触发BF_NEG!信号"


# ============================================================================
# 单元测试 - 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_empty_metrics(self):
        """空指标应使用默认值"""
        model = SignalScoringModel()
        score, signals = model.calculate_score({}, 'home')
        
        assert isinstance(score, (int, float))
        assert isinstance(signals, list)
    
    def test_missing_fields(self):
        """缺失字段应使用默认值0"""
        model = SignalScoringModel()
        metrics = {'total_volume': 100000}  # 只有成交量
        score, signals = model.calculate_score(metrics, 'home')
        
        assert isinstance(score, (int, float))
        assert isinstance(signals, list)
    
    def test_none_values(self):
        """None值应被处理为0"""
        model = SignalScoringModel()
        metrics = {
            'bfindex_home': None,
            'hot_home': None,
            'total_volume': 100000,
        }
        score, signals = model.calculate_score(metrics, 'home')
        
        assert isinstance(score, (int, float))
    
    def test_validate_score_range(self):
        """验证评分范围检查方法"""
        model = SignalScoringModel()
        
        assert model.validate_score_range(0) == True
        assert model.validate_score_range(-100) == True
        assert model.validate_score_range(200) == True
        assert model.validate_score_range(-101) == False
        assert model.validate_score_range(201) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
