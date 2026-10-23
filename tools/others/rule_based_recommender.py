#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于规则的推荐器 - Rule-Based Recommender

功能：
1. 加载从比分反推中发现的高置信度规则
2. 将规则应用到新比赛进行推荐
3. 与现有推荐引擎集成

使用方法：
    from rule_based_recommender import RuleBasedRecommender
    
    recommender = RuleBasedRecommender()
    recommendation = recommender.evaluate(match_features)
    
作者：AI System
日期：2025-11-22
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RuleBasedRecommender:
    """基于规则的推荐器"""
    
    def __init__(self, rules_config_file: str = "model_rules_config.json"):
        """
        初始化推荐器
        
        Args:
            rules_config_file: 规则配置文件路径
        """
        self.rules_config_file = Path(rules_config_file)
        self.rules = []
        self.load_rules()
        
    def load_rules(self):
        """加载规则配置"""
        if not self.rules_config_file.exists():
            logger.warning(f"规则配置文件不存在: {self.rules_config_file}")
            return
        
        try:
            with open(self.rules_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.rules = config.get('rules', [])
            logger.info(f"✅ 加载了 {len(self.rules)} 条规则")
            
            for rule in self.rules:
                logger.info(f"  - {rule['name']}: 胜率 {rule['win_rate']*100:.1f}%")
                
        except Exception as e:
            logger.error(f"加载规则配置失败: {e}")
    
    def evaluate(self, features: Dict) -> Dict:
        """
        评估比赛特征并给出推荐
        
        Args:
            features: 比赛特征字典，包含：
                - home_volume_pct: 主队成交占比
                - away_volume_pct: 客队成交占比
                - handicap_current: 当前盘口
                - handicap_change: 盘口变化
                - concentration: 成交集中度
                - kelly_home_anomaly: 主队凯利异常
                - kelly_away_anomaly: 客队凯利异常
                - home_odds: 主队欧赔
                - away_odds: 客队欧赔
                - total_volume: 总成交量
        
        Returns:
            推荐结果字典：
                - matched_rules: 匹配的规则列表
                - recommendation: 推荐方向 (home_win/away_win/draw/none)
                - confidence: 置信度 (0-1)
                - reason: 推荐理由
        """
        matched_rules = []
        
        # 规则1: 盘口变化>0.25(升盘) AND 主队成交>55%
        if (features.get('handicap_change', 0) > 0.25 and
            features.get('home_volume_pct', 0) > 55 and
            features.get('concentration', 0) > 0.7):
            matched_rules.append({
                'name': '盘口变化>0.25(升盘) AND 主队成交>55%',
                'confidence': 1.0,
                'expected_result': 'home_win'
            })
        
        # 规则2: 主队高成交集中 + 让球
        if (features.get('home_volume_pct', 0) > 70 and
            features.get('handicap_current', 0) < -0.5 and
            features.get('concentration', 0) > 0.7):
            matched_rules.append({
                'name': '主队成交占比>70% AND 主队让球>0.5 AND 集中度>0.7',
                'confidence': 0.85,
                'expected_result': 'home_win'
            })
        
        # 规则3: 客队高成交 + 受让
        if (features.get('away_volume_pct', 0) > 60 and
            features.get('handicap_current', 0) > 0.5 and
            features.get('concentration', 0) > 0.65):
            matched_rules.append({
                'name': '客队成交占比>60% AND 客队受让>0.5 AND 集中度>0.65',
                'confidence': 0.80,
                'expected_result': 'away_win'
            })
        
        # 规则4: 主队低赔 + 高成交
        if (features.get('home_odds', 99) < 1.5 and
            features.get('home_volume_pct', 0) > 65 and
            features.get('total_volume', 0) > 100000):
            matched_rules.append({
                'name': '主队欧赔<1.5 AND 主队成交>65% AND 总成交量>10万',
                'confidence': 0.75,
                'expected_result': 'home_win'
            })
        
        # 规则5: 凯利异常低 + 成交高（陷阱盘）
        if (features.get('kelly_home_anomaly', 0) < -0.1 and
            features.get('home_volume_pct', 0) > 60):
            matched_rules.append({
                'name': '主队凯利异常<-0.1 AND 主队成交>60% (陷阱盘)',
                'confidence': 0.70,
                'expected_result': 'away_win'
            })
        
        # 规则6: 客队凯利异常高 + 成交支持
        if (features.get('kelly_away_anomaly', 0) > 0.15 and
            features.get('away_volume_pct', 0) > 50):
            matched_rules.append({
                'name': '客队凯利异常>0.15 AND 客队成交>50%',
                'confidence': 0.75,
                'expected_result': 'away_win'
            })
        
        # 生成推荐
        if not matched_rules:
            return {
                'matched_rules': [],
                'recommendation': 'none',
                'confidence': 0.0,
                'reason': '无匹配规则'
            }
        
        # 选择置信度最高的规则
        best_rule = max(matched_rules, key=lambda r: r['confidence'])
        
        # 如果有多条规则，计算综合置信度
        if len(matched_rules) > 1:
            # 检查规则是否一致
            results = [r['expected_result'] for r in matched_rules]
            if len(set(results)) == 1:
                # 所有规则指向同一结果，提高置信度
                avg_confidence = sum(r['confidence'] for r in matched_rules) / len(matched_rules)
                confidence = min(avg_confidence * 1.2, 1.0)
                reason = f"匹配 {len(matched_rules)} 条规则，方向一致"
            else:
                # 规则冲突，降低置信度
                confidence = best_rule['confidence'] * 0.7
                reason = f"匹配 {len(matched_rules)} 条规则，但存在冲突"
        else:
            confidence = best_rule['confidence']
            reason = f"匹配规则: {best_rule['name']}"
        
        return {
            'matched_rules': matched_rules,
            'recommendation': best_rule['expected_result'],
            'confidence': confidence,
            'reason': reason
        }
    
    def get_rule_summary(self) -> str:
        """获取规则摘要"""
        if not self.rules:
            return "未加载任何规则"
        
        summary = f"规则库包含 {len(self.rules)} 条规则:\n"
        for i, rule in enumerate(self.rules, 1):
            summary += f"{i}. {rule['name']}\n"
            summary += f"   期望结果: {rule['expected_result']}\n"
            summary += f"   胜率: {rule['win_rate']*100:.1f}%\n"
            summary += f"   样本数: {rule['matches']}\n\n"
        
        return summary


class HybridRecommender:
    """混合推荐器 - 结合规则和现有模型"""
    
    def __init__(self, rules_config_file: str = "model_rules_config.json"):
        """
        初始化混合推荐器
        
        Args:
            rules_config_file: 规则配置文件路径
        """
        self.rule_recommender = RuleBasedRecommender(rules_config_file)
    
    def recommend(self, features: Dict, model_score: Dict) -> Dict:
        """
        综合规则和模型给出推荐
        
        Args:
            features: 比赛特征
            model_score: 现有模型的评分结果
        
        Returns:
            综合推荐结果
        """
        # 1. 获取规则推荐
        rule_result = self.rule_recommender.evaluate(features)
        
        # 2. 如果规则匹配且置信度高，优先采用规则
        if rule_result['confidence'] >= 0.85:
            return {
                'recommendation': rule_result['recommendation'],
                'confidence': rule_result['confidence'],
                'source': 'rule',
                'reason': f"高置信度规则: {rule_result['reason']}",
                'rule_details': rule_result
            }
        
        # 3. 如果规则推荐与模型一致，增强置信度
        model_recommendation = model_score.get('recommendation', 'none')
        if (rule_result['recommendation'] == model_recommendation and 
            rule_result['recommendation'] != 'none'):
            enhanced_confidence = min(
                (rule_result['confidence'] + model_score.get('confidence', 0)) / 2 * 1.3,
                1.0
            )
            return {
                'recommendation': rule_result['recommendation'],
                'confidence': enhanced_confidence,
                'source': 'hybrid',
                'reason': f"规则与模型一致: {rule_result['reason']}",
                'rule_details': rule_result,
                'model_details': model_score
            }
        
        # 4. 规则与模型冲突时，根据置信度决定
        if rule_result['confidence'] > model_score.get('confidence', 0):
            return {
                'recommendation': rule_result['recommendation'],
                'confidence': rule_result['confidence'] * 0.8,
                'source': 'rule',
                'reason': f"规则置信度更高: {rule_result['reason']}",
                'rule_details': rule_result,
                'model_details': model_score
            }
        
        # 5. 默认使用模型推荐
        return {
            'recommendation': model_recommendation,
            'confidence': model_score.get('confidence', 0),
            'source': 'model',
            'reason': model_score.get('reason', '模型推荐'),
            'rule_details': rule_result,
            'model_details': model_score
        }


def test_recommender():
    """测试推荐器"""
    logging.basicConfig(level=logging.INFO)
    
    recommender = RuleBasedRecommender()
    
    # 打印规则摘要
    print("\n" + "="*80)
    print("规则库摘要")
    print("="*80)
    print(recommender.get_rule_summary())
    
    # 测试案例1: 符合升盘规则
    print("\n" + "="*80)
    print("测试案例1: 盘口升盘 + 主队成交集中")
    print("="*80)
    test_features_1 = {
        'handicap_change': 0.3,
        'home_volume_pct': 70,
        'concentration': 0.75,
        'handicap_current': -1.0,
        'total_volume': 200000
    }
    result_1 = recommender.evaluate(test_features_1)
    print(f"推荐: {result_1['recommendation']}")
    print(f"置信度: {result_1['confidence']}")
    print(f"理由: {result_1['reason']}")
    print(f"匹配规则数: {len(result_1['matched_rules'])}")
    
    # 测试案例2: 陷阱盘
    print("\n" + "="*80)
    print("测试案例2: 凯利异常低 + 主队成交高（陷阱盘）")
    print("="*80)
    test_features_2 = {
        'kelly_home_anomaly': -0.15,
        'home_volume_pct': 70,
        'handicap_current': -0.75
    }
    result_2 = recommender.evaluate(test_features_2)
    print(f"推荐: {result_2['recommendation']}")
    print(f"置信度: {result_2['confidence']}")
    print(f"理由: {result_2['reason']}")
    
    # 测试案例3: 无匹配规则
    print("\n" + "="*80)
    print("测试案例3: 无明显特征")
    print("="*80)
    test_features_3 = {
        'home_volume_pct': 50,
        'away_volume_pct': 30,
        'handicap_current': -0.25
    }
    result_3 = recommender.evaluate(test_features_3)
    print(f"推荐: {result_3['recommendation']}")
    print(f"置信度: {result_3['confidence']}")
    print(f"理由: {result_3['reason']}")


if __name__ == "__main__":
    test_recommender()
