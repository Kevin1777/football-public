"""
ResultValidator 属性测试

使用 hypothesis 库进行属性测试，验证结果验证器的正确性。

测试覆盖:
- Property 15: 盘口结果验证正确性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.result_validator import ResultValidator, ValidationResult, validate


# ============================================================================
# Property 15: 盘口结果验证正确性
# **Feature: recommendation-engine-optimization, Property 15: 盘口结果验证正确性**
# **Validates: Requirements 6.2**
# ============================================================================

class TestProperty15HandicapValidation:
    """
    Property 15: 盘口结果验证正确性
    
    *For any* 盘口值和比分组合，结果验证器应正确计算推荐是否正确
    （全赢/半赢/走水/半输/全输）
    """
    
    @settings(max_examples=100)
    @given(
        home_score=st.integers(min_value=0, max_value=5),
        away_score=st.integers(min_value=0, max_value=5),
        handicap=st.sampled_from([-2.0, -1.5, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]),
        direction=st.sampled_from(['home', 'away'])
    )
    def test_returns_valid_result(self, home_score, away_score, handicap, direction):
        """验证器应返回有效的结果类型"""
        validator = ResultValidator()
        recommendation = {'direction': direction}
        
        result = validator.validate(recommendation, (home_score, away_score), handicap)
        
        valid_results = ['win', 'half_win', 'draw', 'half_lose', 'lose']
        assert result['result'] in valid_results, f"结果'{result['result']}'不是有效类型"
    
    @settings(max_examples=100)
    @given(
        home_score=st.integers(min_value=0, max_value=5),
        away_score=st.integers(min_value=0, max_value=5),
        handicap=st.sampled_from([-2.0, -1.5, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]),
        direction=st.sampled_from(['home', 'away'])
    )
    def test_is_correct_matches_result(self, home_score, away_score, handicap, direction):
        """is_correct应与result一致（win/half_win为True）"""
        validator = ResultValidator()
        recommendation = {'direction': direction}
        
        result = validator.validate(recommendation, (home_score, away_score), handicap)
        
        if result['result'] in ['win', 'half_win']:
            assert result['is_correct'] == True, "win/half_win时is_correct应为True"
        else:
            assert result['is_correct'] == False, "draw/half_lose/lose时is_correct应为False"
    
    @settings(max_examples=100)
    @given(
        home_score=st.integers(min_value=0, max_value=5),
        away_score=st.integers(min_value=0, max_value=5),
        handicap=st.sampled_from([-2.0, -1.5, -1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]),
        direction=st.sampled_from(['home', 'away'])
    )
    def test_profit_matches_result(self, home_score, away_score, handicap, direction):
        """profit应与result一致"""
        validator = ResultValidator()
        recommendation = {'direction': direction}
        
        result = validator.validate(recommendation, (home_score, away_score), handicap)
        
        expected_profits = {
            'win': 1.0,
            'half_win': 0.5,
            'draw': 0.0,
            'half_lose': -0.5,
            'lose': -1.0,
        }
        
        expected = expected_profits[result['result']]
        assert result['profit'] == expected, f"result={result['result']}时profit应为{expected}"


# ============================================================================
# 单元测试 - 具体场景
# ============================================================================

class TestSpecificScenarios:
    """具体场景测试"""
    
    def test_home_win_full(self):
        """主队全赢：主队让0.5，比分2:0"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (2, 0), -0.5)
        
        # 主队净胜2球，让0.5球，调整后差值=2+(-0.5)=1.5>0.25，全赢
        assert result['result'] == 'win'
        assert result['profit'] == 1.0
        assert result['is_correct'] == True
    
    def test_home_half_win(self):
        """主队半赢：主队让0.75，比分1:0"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (1, 0), -0.75)
        
        # 主队净胜1球，让0.75球，调整后差值=1+(-0.75)=0.25，半赢
        assert result['result'] == 'half_win'
        assert result['profit'] == 0.5
        assert result['is_correct'] == True
    
    def test_home_draw(self):
        """主队走水：主队让0.5，比分1:1"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (1, 1), -0.5)
        
        # 主队净胜0球，让0.5球，调整后差值=0+(-0.5)=-0.5<-0.25，全输
        assert result['result'] == 'lose'
    
    def test_home_half_lose(self):
        """主队半输：主队让0.25，比分0:0"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (0, 0), -0.25)
        
        # 主队净胜0球，让0.25球，调整后差值=0+(-0.25)=-0.25，半输
        assert result['result'] == 'half_lose'
        assert result['profit'] == -0.5
        assert result['is_correct'] == False
    
    def test_home_lose_full(self):
        """主队全输：主队让1，比分0:1"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (0, 1), -1.0)
        
        # 主队净胜-1球，让1球，调整后差值=-1+(-1)=-2<-0.25，全输
        assert result['result'] == 'lose'
        assert result['profit'] == -1.0
        assert result['is_correct'] == False
    
    def test_away_win_full(self):
        """客队全赢：主队受让0.5，比分0:2"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'away'}, (0, 2), 0.5)
        
        # 客队净胜2球，主队受让0.5，调整后差值=2-0.5=1.5>0.25，全赢
        assert result['result'] == 'win'
        assert result['profit'] == 1.0
        assert result['is_correct'] == True
    
    def test_away_half_win(self):
        """客队半赢：主队受让0.75，比分0:1"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'away'}, (0, 1), 0.75)
        
        # 客队净胜1球，主队受让0.75，调整后差值=1-0.75=0.25，半赢
        assert result['result'] == 'half_win'
        assert result['profit'] == 0.5
    
    def test_draw_handicap(self):
        """走水：平手盘，比分0:0"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'home'}, (0, 0), 0)
        
        # 平手盘，0:0，调整后差值=0，走水
        assert result['result'] == 'draw'
        assert result['profit'] == 0.0
    
    def test_none_direction(self):
        """无推荐方向"""
        validator = ResultValidator()
        result = validator.validate({'direction': 'none'}, (1, 0), -0.5)
        
        assert result['result'] == 'draw'
        assert result['is_correct'] == False


# ============================================================================
# 单元测试 - 统计计算
# ============================================================================

class TestStatistics:
    """统计计算测试"""
    
    def test_calculate_statistics(self):
        """计算统计指标"""
        validator = ResultValidator()
        
        results = [
            {'result': 'win', 'is_correct': True, 'profit': 1.0},
            {'result': 'win', 'is_correct': True, 'profit': 1.0},
            {'result': 'half_win', 'is_correct': True, 'profit': 0.5},
            {'result': 'lose', 'is_correct': False, 'profit': -1.0},
            {'result': 'lose', 'is_correct': False, 'profit': -1.0},
        ]
        
        stats = validator.calculate_statistics(results)
        
        assert stats['total'] == 5
        assert stats['win'] == 2
        assert stats['half_win'] == 1
        assert stats['lose'] == 2
        assert stats['correct'] == 3
        assert stats['win_rate'] == 60.0  # 3/5 * 100
        assert stats['total_profit'] == 0.5  # 1+1+0.5-1-1
        assert stats['roi'] == 10.0  # 0.5/5 * 100
    
    def test_empty_results(self):
        """空结果列表"""
        validator = ResultValidator()
        stats = validator.calculate_statistics([])
        
        assert stats['total'] == 0
        assert stats['win_rate'] == 0.0
        assert stats['roi'] == 0.0


# ============================================================================
# 单元测试 - 欧赔验证
# ============================================================================

class TestEuroBet:
    """欧赔验证测试"""
    
    def test_euro_home_win(self):
        """欧赔主胜"""
        validator = ResultValidator()
        result = validator.validate_euro_bet('home', 2, 1)
        
        assert result['result'] == 'win'
        assert result['is_correct'] == True
    
    def test_euro_home_lose(self):
        """欧赔主负"""
        validator = ResultValidator()
        result = validator.validate_euro_bet('home', 0, 1)
        
        assert result['result'] == 'lose'
        assert result['is_correct'] == False
    
    def test_euro_away_win(self):
        """欧赔客胜"""
        validator = ResultValidator()
        result = validator.validate_euro_bet('away', 0, 2)
        
        assert result['result'] == 'win'
        assert result['is_correct'] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
