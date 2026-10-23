"""
FeatureExtractor 属性测试

使用 hypothesis 库进行属性测试，验证特征提取器的正确性。

测试覆盖:
- Property 11: 特征提取完整性
- Property 19: 缺失字段默认值处理
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.feature_extractor import FeatureExtractor, MetricsData, extract_metrics

# Cover ASCII and Chinese names without expensive cold-start Unicode generation.
NAME_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789中文测试球队联赛 -_"


# ============================================================================
# 测试策略/生成器
# ============================================================================

@st.composite
def valid_match_data_strategy(draw):
    """生成有效的比赛JSON数据"""
    return {
        'match_info': {
            'league': draw(st.text(alphabet=NAME_ALPHABET, min_size=1, max_size=20)),
            'home': draw(st.text(alphabet=NAME_ALPHABET, min_size=1, max_size=20)),
            'away': draw(st.text(alphabet=NAME_ALPHABET, min_size=1, max_size=20)),
        },
        'handicap_data': {
            'current_handicap': draw(st.floats(min_value=-3.0, max_value=3.0, allow_nan=False)),
            'initial_handicap': draw(st.floats(min_value=-3.0, max_value=3.0, allow_nan=False)),
            'current_home_odds': draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
            'current_away_odds': draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
            'initial_home_odds': draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
            'initial_away_odds': draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
            'handicap_trend': draw(st.sampled_from(['升盘', '降盘', '稳盘', ''])),
            'current_handicap_text': draw(st.text(alphabet=NAME_ALPHABET, max_size=10)),
        },
        'trade_data': {
            'data': [{
                '总成交量': draw(st.floats(min_value=0, max_value=2000000, allow_nan=False)),
                '比例_主': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '比例_和': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '比例_客': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '主胜_欧赔': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False)),
                '和局_欧赔': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False)),
                '客胜_欧赔': draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False)),
                '必指_主': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '必指_和': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '必指_客': draw(st.floats(min_value=0, max_value=100, allow_nan=False)),
                '凯利_主': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
                '凯利_和': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
                '凯利_客': draw(st.floats(min_value=50, max_value=150, allow_nan=False)),
                '热指_主': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
                '热指_客': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
                '凯差_主': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
                '凯差_客': draw(st.floats(min_value=-50, max_value=50, allow_nan=False)),
            }]
        }
    }


@st.composite
def partial_match_data_strategy(draw):
    """生成部分字段缺失的比赛数据"""
    return {
        'match_info': {},
        'handicap_data': {},
        'trade_data': {
            'data': [{
                '总成交量': draw(st.floats(min_value=0, max_value=2000000, allow_nan=False)),
            }]
        }
    }


# ============================================================================
# Property 11: 特征提取完整性
# **Feature: recommendation-engine-optimization, Property 11: 特征提取完整性**
# **Validates: Requirements 4.1**
# ============================================================================

class TestProperty11FeatureCompleteness:
    """
    Property 11: 特征提取完整性
    
    *For any* 有效的比赛JSON数据，特征提取器应返回包含所有核心指标的字典
    （成交量、三方占比、盘口、赔率、必发指数、凯利指数、热度指数）
    """
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_returns_dict(self, data):
        """特征提取器应返回字典"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert isinstance(metrics, dict), "应返回字典类型"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_volume(self, data):
        """应包含成交量字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'total_volume' in metrics, "应包含total_volume字段"
        assert isinstance(metrics['total_volume'], (int, float)), "total_volume应为数值"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_three_way_pct(self, data):
        """应包含三方占比字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'home_pct' in metrics, "应包含home_pct字段"
        assert 'draw_pct' in metrics, "应包含draw_pct字段"
        assert 'away_pct' in metrics, "应包含away_pct字段"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_handicap(self, data):
        """应包含盘口字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'handicap_current' in metrics, "应包含handicap_current字段"
        assert 'handicap_initial' in metrics, "应包含handicap_initial字段"
        assert 'handicap_change' in metrics, "应包含handicap_change字段"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_odds(self, data):
        """应包含赔率字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'home_odds' in metrics, "应包含home_odds字段"
        assert 'away_odds' in metrics, "应包含away_odds字段"
        assert 'home_euro_odds' in metrics, "应包含home_euro_odds字段"
        assert 'away_euro_odds' in metrics, "应包含away_euro_odds字段"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_bfindex(self, data):
        """应包含必发指数字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'bfindex_home' in metrics, "应包含bfindex_home字段"
        assert 'bfindex_away' in metrics, "应包含bfindex_away字段"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_kelly(self, data):
        """应包含凯利指数字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'kelly_home' in metrics, "应包含kelly_home字段"
        assert 'kelly_away' in metrics, "应包含kelly_away字段"
    
    @settings(max_examples=100)
    @given(data=valid_match_data_strategy())
    def test_contains_hot_index(self, data):
        """应包含热度指数字段"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        assert 'hot_home' in metrics, "应包含hot_home字段"
        assert 'hot_away' in metrics, "应包含hot_away字段"


# ============================================================================
# Property 19: 缺失字段默认值处理
# **Feature: recommendation-engine-optimization, Property 19: 缺失字段默认值处理**
# **Validates: Requirements 8.2**
# ============================================================================

class TestProperty19MissingFieldDefaults:
    """
    Property 19: 缺失字段默认值处理
    
    *For any* 包含缺失字段的比赛数据，推荐引擎应使用默认值（0）并继续处理，不抛出异常
    """
    
    @settings(max_examples=100)
    @given(data=partial_match_data_strategy())
    def test_handles_missing_fields_without_exception(self, data):
        """缺失字段时不应抛出异常"""
        extractor = FeatureExtractor()
        
        # 不应抛出异常
        try:
            metrics = extractor.extract_metrics(data)
            assert isinstance(metrics, dict)
        except Exception as e:
            pytest.fail(f"处理缺失字段时抛出异常: {e}")
    
    @settings(max_examples=100)
    @given(data=partial_match_data_strategy())
    def test_missing_fields_use_default_zero(self, data):
        """缺失字段应使用默认值0"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics(data)
        
        # 检查缺失字段是否使用默认值
        assert metrics.get('bfindex_home', None) == 0.0, "缺失的bfindex_home应为0"
        assert metrics.get('kelly_home', None) == 0.0, "缺失的kelly_home应为0"
        assert metrics.get('hot_home', None) == 0.0, "缺失的hot_home应为0"
    
    def test_empty_data_returns_defaults(self):
        """空数据应返回默认值"""
        extractor = FeatureExtractor()
        metrics = extractor.extract_metrics({})
        
        assert isinstance(metrics, dict)
        assert metrics['total_volume'] == 0.0
        assert metrics['home_pct'] == 0.0
        assert metrics['handicap_current'] == 0.0
    
    def test_none_values_handled(self):
        """None值应被处理为默认值"""
        extractor = FeatureExtractor()
        data = {
            'trade_data': {
                'data': [{
                    '总成交量': None,
                    '比例_主': None,
                }]
            },
            'handicap_data': {
                'current_handicap': None,
            }
        }
        
        metrics = extractor.extract_metrics(data)
        
        assert metrics['total_volume'] == 0.0
        assert metrics['home_pct'] == 0.0
        assert metrics['handicap_current'] == 0.0


# ============================================================================
# 单元测试 - 边界条件
# ============================================================================

class TestEdgeCases:
    """边界条件测试"""
    
    def test_safe_float_with_comma_string(self):
        """处理带逗号的数字字符串"""
        extractor = FeatureExtractor()
        
        assert extractor._safe_float("1,234,567") == 1234567.0
        assert extractor._safe_float("100,000") == 100000.0
    
    def test_safe_float_with_invalid_string(self):
        """处理无效字符串"""
        extractor = FeatureExtractor()
        
        assert extractor._safe_float("invalid") == 0.0
        assert extractor._safe_float("") == 0.0
    
    def test_metrics_data_to_dict(self):
        """MetricsData转换为字典"""
        metrics = MetricsData(
            total_volume=100000,
            home_pct=60,
            handicap_current=-0.5
        )
        
        d = metrics.to_dict()
        
        assert d['total_volume'] == 100000
        assert d['home_pct'] == 60
        assert d['handicap_current'] == -0.5
    
    def test_validate_metrics(self):
        """验证指标完整性"""
        extractor = FeatureExtractor()
        
        # 完整指标
        complete_metrics = {
            'total_volume': 100000,
            'home_pct': 60, 'draw_pct': 20, 'away_pct': 20,
            'handicap_current': -0.5,
            'home_odds': 0.9, 'away_odds': 0.9,
            'bfindex_home': 50, 'bfindex_away': 50,
            'kelly_home': 95, 'kelly_away': 95,
            'hot_home': 10, 'hot_away': -10,
        }
        assert extractor.validate_metrics(complete_metrics) == True
        
        # 不完整指标
        incomplete_metrics = {'total_volume': 100000}
        assert extractor.validate_metrics(incomplete_metrics) == False
    
    def test_get_missing_fields(self):
        """获取缺失字段"""
        extractor = FeatureExtractor()
        
        metrics = {'total_volume': 100000}
        missing = extractor.get_missing_fields(metrics)
        
        assert 'home_pct' in missing
        assert 'bfindex_home' in missing
        assert 'total_volume' not in missing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
