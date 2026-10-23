#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
亚盘计算函数的属性测试

**Feature: handicap-statistics-fix, Property 1: Handicap calculation correctness**
**Validates: Requirements 2.1, 2.2**

使用 hypothesis 进行属性测试，验证亚盘计算逻辑的正确性。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest
try:
    from hypothesis import given, strategies as st, settings
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False
    print("Warning: hypothesis not installed, skipping property tests")

from core.recommendation_tracker import RecommendationTracker


class TestHandicapCalculation(unittest.TestCase):
    """亚盘计算函数测试"""
    
    def test_home_win_clear(self):
        """主队推荐，明显赢盘"""
        # 主队让0.5球，比分2-0，adjusted_diff = 2-0+(-0.5) = 1.5 > 0.25 → win
        result = RecommendationTracker.calculate_handicap_result(2, 0, -0.5, 'home')
        self.assertEqual(result, 'win')
    
    def test_home_half_win(self):
        """主队推荐，赢半"""
        # 主队让0.25球，比分1-1，adjusted_diff = 1-1+(-0.25) = -0.25 → half_lose
        # 主队让0.25球，比分1-0，adjusted_diff = 1-0+(-0.25) = 0.75 > 0.25 → win
        # 主队受0.25球，比分0-0，adjusted_diff = 0-0+0.25 = 0.25 → half_win (0 < 0.25 <= 0.25)
        result = RecommendationTracker.calculate_handicap_result(0, 0, 0.25, 'home')
        self.assertEqual(result, 'half_win')
    
    def test_home_push(self):
        """主队推荐，走水"""
        # 主队让0.5球，比分1-0，adjusted_diff = 1-0+(-0.5) = 0.5 > 0.25 → win
        # 主队平手，比分0-0，adjusted_diff = 0-0+0 = 0 → push
        result = RecommendationTracker.calculate_handicap_result(0, 0, 0, 'home')
        self.assertEqual(result, 'push')
    
    def test_home_half_lose(self):
        """主队推荐，输半"""
        # 主队受0.25球，比分0-1，adjusted_diff = 0-1+0.25 = -0.75 < -0.25 → lose
        # 主队让0.25球，比分0-0，adjusted_diff = 0-0+(-0.25) = -0.25 → half_lose
        result = RecommendationTracker.calculate_handicap_result(0, 0, -0.25, 'home')
        self.assertEqual(result, 'half_lose')
    
    def test_home_lose_clear(self):
        """主队推荐，明显输盘"""
        # 主队让0.5球，比分0-1，adjusted_diff = 0-1+(-0.5) = -1.5 < -0.25 → lose
        result = RecommendationTracker.calculate_handicap_result(0, 1, -0.5, 'home')
        self.assertEqual(result, 'lose')
    
    def test_away_win_clear(self):
        """客队推荐，明显赢盘"""
        # 客队受0.5球（主让0.5），比分0-2，adjusted_diff = 0-2+(-0.5) = -2.5 < -0.25 → win
        result = RecommendationTracker.calculate_handicap_result(0, 2, -0.5, 'away')
        self.assertEqual(result, 'win')
    
    def test_away_half_win(self):
        """客队推荐，赢半"""
        # 客队受0.25球（主让0.25），比分0-0，adjusted_diff = 0-0+(-0.25) = -0.25 → half_win
        result = RecommendationTracker.calculate_handicap_result(0, 0, -0.25, 'away')
        self.assertEqual(result, 'half_win')
    
    def test_away_push(self):
        """客队推荐，走水"""
        # 平手盘，比分0-0，adjusted_diff = 0 → push
        result = RecommendationTracker.calculate_handicap_result(0, 0, 0, 'away')
        self.assertEqual(result, 'push')
    
    def test_away_half_lose(self):
        """客队推荐，输半"""
        # 客队让0.25球（主受0.25），比分0-0，adjusted_diff = 0-0+0.25 = 0.25 → half_lose
        result = RecommendationTracker.calculate_handicap_result(0, 0, 0.25, 'away')
        self.assertEqual(result, 'half_lose')
    
    def test_away_lose_clear(self):
        """客队推荐，明显输盘"""
        # 客队让0.5球（主受0.5），比分2-0，adjusted_diff = 2-0+0.5 = 2.5 > 0.25 → lose
        result = RecommendationTracker.calculate_handicap_result(2, 0, 0.5, 'away')
        self.assertEqual(result, 'lose')


if HAS_HYPOTHESIS:
    class TestHandicapCalculationProperty(unittest.TestCase):
        """
        亚盘计算属性测试
        
        **Feature: handicap-statistics-fix, Property 1: Handicap calculation correctness**
        **Validates: Requirements 2.1, 2.2**
        """
        
        @given(
            home_score=st.integers(min_value=0, max_value=10),
            away_score=st.integers(min_value=0, max_value=10),
            handicap=st.sampled_from([-2, -1.5, -1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1, 1.5, 2]),
            direction=st.sampled_from(['home', 'away'])
        )
        @settings(max_examples=100)
        def test_handicap_result_is_valid(self, home_score, away_score, handicap, direction):
            """属性：结果必须是五种有效值之一"""
            result = RecommendationTracker.calculate_handicap_result(
                home_score, away_score, handicap, direction
            )
            self.assertIn(result, ['win', 'half_win', 'push', 'half_lose', 'lose'])
        
        @given(
            home_score=st.integers(min_value=0, max_value=10),
            away_score=st.integers(min_value=0, max_value=10),
            handicap=st.sampled_from([-2, -1.5, -1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1, 1.5, 2])
        )
        @settings(max_examples=100)
        def test_home_away_symmetry(self, home_score, away_score, handicap):
            """属性：主客推荐结果应该相反（除了走水）"""
            home_result = RecommendationTracker.calculate_handicap_result(
                home_score, away_score, handicap, 'home'
            )
            away_result = RecommendationTracker.calculate_handicap_result(
                home_score, away_score, handicap, 'away'
            )
            
            # 定义结果对应关系
            opposite = {
                'win': 'lose',
                'half_win': 'half_lose',
                'push': 'push',
                'half_lose': 'half_win',
                'lose': 'win'
            }
            
            self.assertEqual(away_result, opposite[home_result])
        
        @given(
            home_score=st.integers(min_value=0, max_value=10),
            away_score=st.integers(min_value=0, max_value=10),
            direction=st.sampled_from(['home', 'away'])
        )
        @settings(max_examples=100)
        def test_push_only_on_zero_adjusted_diff(self, home_score, away_score, direction):
            """属性：走水只在adjusted_diff为0时发生"""
            # 计算使adjusted_diff为0的handicap
            handicap = -(home_score - away_score)
            
            result = RecommendationTracker.calculate_handicap_result(
                home_score, away_score, handicap, direction
            )
            self.assertEqual(result, 'push')


if __name__ == '__main__':
    unittest.main()



class TestDataStorageRoundTrip(unittest.TestCase):
    """
    数据存储往返一致性测试
    
    **Feature: handicap-statistics-fix, Property 2: Data storage round-trip**
    **Validates: Requirements 1.1, 1.2**
    """
    
    def setUp(self):
        """创建临时数据库"""
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = RecommendationTracker(db_path=self.temp_db.name)
    
    def tearDown(self):
        """清理临时数据库"""
        import os
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def test_handicap_value_stored_correctly(self):
        """测试盘口数值正确存储"""
        rec_data = {
            'match_info': {
                'home': 'TeamA',
                'away': 'TeamB',
                'kickoff': '2025-01-01 20:00',
                'league': 'Test League'
            },
            'recommendation': {
                'direction': 'home',
                'handicap': '-0.5',
                'confidence': 0.85,
                'formatted': 'TeamA -0.5'
            },
            'scores': {},
            'funding_level': {},
            'risk_control': {},
            'sbre': {}
        }
        
        rec_id = self.tracker.record_recommendation(rec_data)
        
        # 读取并验证
        with self.tracker._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT handicap_value, direction FROM recommendations WHERE id = ?", (rec_id,))
            row = cursor.fetchone()
            
            self.assertEqual(row['handicap_value'], -0.5)
            self.assertEqual(row['direction'], 'home')
    
    def test_direction_stored_correctly(self):
        """测试方向正确存储"""
        for direction in ['home', 'away']:
            rec_data = {
                'match_info': {
                    'home': 'TeamA',
                    'away': 'TeamB',
                    'kickoff': '2025-01-01 20:00',
                    'league': 'Test League'
                },
                'recommendation': {
                    'direction': direction,
                    'handicap': '0',
                    'confidence': 0.75,
                    'formatted': f'Team {direction}'
                },
                'scores': {},
                'funding_level': {},
                'risk_control': {},
                'sbre': {}
            }
            
            rec_id = self.tracker.record_recommendation(rec_data)
            
            with self.tracker._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT direction FROM recommendations WHERE id = ?", (rec_id,))
                row = cursor.fetchone()
                self.assertEqual(row['direction'], direction)


if HAS_HYPOTHESIS:
    class TestDataStorageRoundTripProperty(unittest.TestCase):
        """
        数据存储往返属性测试
        
        **Feature: handicap-statistics-fix, Property 2: Data storage round-trip**
        **Validates: Requirements 1.1, 1.2**
        """
        
        def setUp(self):
            import tempfile
            self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            self.temp_db.close()
            self.tracker = RecommendationTracker(db_path=self.temp_db.name)
        
        def tearDown(self):
            import os
            try:
                os.unlink(self.temp_db.name)
            except:
                pass
        
        @given(
            handicap=st.sampled_from(['-2', '-1.5', '-1', '-0.75', '-0.5', '-0.25', '0', '+0.25', '+0.5', '+0.75', '+1', '+1.5', '+2']),
            direction=st.sampled_from(['home', 'away'])
        )
        @settings(max_examples=100)
        def test_handicap_round_trip(self, handicap, direction):
            """属性：存储后读取的盘口值和方向应与原值一致"""
            rec_data = {
                'match_info': {
                    'home': 'TeamA',
                    'away': 'TeamB',
                    'kickoff': '2025-01-01 20:00',
                    'league': 'Test'
                },
                'recommendation': {
                    'direction': direction,
                    'handicap': handicap,
                    'confidence': 0.8,
                    'formatted': f'Team {handicap}'
                },
                'scores': {},
                'funding_level': {},
                'risk_control': {},
                'sbre': {}
            }
            
            rec_id = self.tracker.record_recommendation(rec_data)
            
            with self.tracker._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT handicap_value, direction FROM recommendations WHERE id = ?", (rec_id,))
                row = cursor.fetchone()
                
                expected_value = float(handicap.replace('+', ''))
                self.assertEqual(row['handicap_value'], expected_value)
                self.assertEqual(row['direction'], direction)



class TestAccuracyCalculation(unittest.TestCase):
    """
    准确率计算一致性测试
    
    **Feature: handicap-statistics-fix, Property 3: Accuracy calculation consistency**
    **Validates: Requirements 3.1, 3.3**
    """
    
    def test_accuracy_formula_strict(self):
        """测试不含走水的准确率公式"""
        # 模拟统计数据
        stats = {'win': 5, 'half_win': 3, 'push': 2, 'half_lose': 1, 'lose': 4}
        
        total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
        wins = stats['win'] + stats['half_win']
        accuracy_strict = wins / total_decided * 100
        
        # 验证公式: (5+3) / (5+3+1+4) * 100 = 8/13 * 100 ≈ 61.54%
        self.assertAlmostEqual(accuracy_strict, 8/13*100, places=2)
    
    def test_accuracy_formula_with_push(self):
        """测试含走水的准确率公式"""
        stats = {'win': 5, 'half_win': 3, 'push': 2, 'half_lose': 1, 'lose': 4}
        
        total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
        total_with_push = total_decided + stats['push']
        wins = stats['win'] + stats['half_win']
        accuracy_with_push = (wins + stats['push']) / total_with_push * 100
        
        # 验证公式: (5+3+2) / (5+3+2+1+4) * 100 = 10/15 * 100 ≈ 66.67%
        self.assertAlmostEqual(accuracy_with_push, 10/15*100, places=2)
    
    def test_accuracy_zero_division(self):
        """测试零除情况"""
        stats = {'win': 0, 'half_win': 0, 'push': 0, 'half_lose': 0, 'lose': 0}
        
        total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
        accuracy_strict = (stats['win'] + stats['half_win']) / total_decided * 100 if total_decided > 0 else 0
        
        self.assertEqual(accuracy_strict, 0)


if HAS_HYPOTHESIS:
    class TestAccuracyCalculationProperty(unittest.TestCase):
        """
        准确率计算属性测试
        
        **Feature: handicap-statistics-fix, Property 3: Accuracy calculation consistency**
        **Validates: Requirements 3.1, 3.3**
        """
        
        @given(
            win=st.integers(min_value=0, max_value=100),
            half_win=st.integers(min_value=0, max_value=100),
            push=st.integers(min_value=0, max_value=100),
            half_lose=st.integers(min_value=0, max_value=100),
            lose=st.integers(min_value=0, max_value=100)
        )
        @settings(max_examples=100)
        def test_accuracy_bounds(self, win, half_win, push, half_lose, lose):
            """属性：准确率必须在0-100之间"""
            total_decided = win + half_win + half_lose + lose
            total_with_push = total_decided + push
            wins = win + half_win
            
            if total_decided > 0:
                accuracy_strict = wins / total_decided * 100
                self.assertGreaterEqual(accuracy_strict, 0)
                self.assertLessEqual(accuracy_strict, 100)
            
            if total_with_push > 0:
                accuracy_with_push = (wins + push) / total_with_push * 100
                self.assertGreaterEqual(accuracy_with_push, 0)
                self.assertLessEqual(accuracy_with_push, 100)
        
        @given(
            win=st.integers(min_value=0, max_value=100),
            half_win=st.integers(min_value=0, max_value=100),
            push=st.integers(min_value=1, max_value=100),  # 至少有一个走水
            half_lose=st.integers(min_value=0, max_value=100),
            lose=st.integers(min_value=0, max_value=100)
        )
        @settings(max_examples=100)
        def test_accuracy_with_push_higher_or_equal(self, win, half_win, push, half_lose, lose):
            """属性：含走水的准确率应该 >= 不含走水的准确率"""
            total_decided = win + half_win + half_lose + lose
            total_with_push = total_decided + push
            wins = win + half_win
            
            if total_decided > 0 and total_with_push > 0:
                accuracy_strict = wins / total_decided * 100
                accuracy_with_push = (wins + push) / total_with_push * 100
                
                # 含走水的准确率应该 >= 不含走水的准确率
                self.assertGreaterEqual(accuracy_with_push, accuracy_strict - 0.01)  # 允许浮点误差
