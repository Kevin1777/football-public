#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速准确率测试 - 基于已有的规则发现逻辑

直接使用 score_reverse_engineer.py 中已验证的特征提取逻辑
"""

import json
import logging
from pathlib import Path
from rule_based_recommender import RuleBasedRecommender

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def load_and_test():
    """加载数据并测试规则推荐准确率"""
    
    detail_cache_dir = Path("detail_cache")
    recommender = RuleBasedRecommender()
    
    logger.info("="*80)
    logger.info("快速准确率测试")
    logger.info("="*80)
    
    # 统计
    stats = {
        'total': 0,
        'rule_recommended': 0,
        'rule_correct': 0,
        'model_recommended': 0,
        'model_correct': 0,
        'no_recommendation': 0
    }
    
    results = []
    
    # 加载所有比赛
    for json_file in detail_cache_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            match_info = data.get('match_info', {})
            score = match_info.get('score', '')
            
            if not score or '-' not in score:
                continue
            
            # 解析比分
            try:
                parts = score.split('-')
                home_score = int(parts[0].strip())
                away_score = int(parts[1].strip())
                
                if home_score > away_score:
                    actual_result = 'home_win'
                elif away_score > home_score:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
            except:
                continue
            
            # 提取特征
            trade_data_dict = data.get('trade_data', {})
            handicap_data = data.get('handicap_data', {})
            
            if not trade_data_dict:
                continue
            
            # 从字典中提取最近的交易记录（假设trade_data是时间戳为key的字典）
            if isinstance(trade_data_dict, dict):
                # 尝试找最后一个记录
                last_key = None
                for key in trade_data_dict.keys():
                    last_key = key
                
                if last_key:
                    last_record = trade_data_dict[last_key]
                else:
                    continue
            else:
                continue
            
            def safe_float(value, default=0):
                try:
                    if isinstance(value, (int, float)):
                        return float(value)
                    return float(str(value).replace(',', '').replace('%', ''))
                except:
                    return default
            
            features = {
                'home_volume_pct': safe_float(last_record.get('home_ratio', 0)),
                'away_volume_pct': safe_float(last_record.get('away_ratio', 0)),
                'draw_volume_pct': safe_float(last_record.get('draw_ratio', 0)),
                'total_volume': safe_float(last_record.get('total_volume', 0)),
                'home_odds': safe_float(last_record.get('home_odds', 0)),
                'away_odds': safe_float(last_record.get('away_odds', 0)),
                'draw_odds': safe_float(last_record.get('draw_odds', 0)),
                'kelly_home_anomaly': safe_float(last_record.get('kelly_home', 100)) / 100.0 - 1.0,
                'kelly_away_anomaly': safe_float(last_record.get('kelly_away', 100)) / 100.0 - 1.0,
                'handicap_current': safe_float(handicap_data.get('current_handicap', 0)),
                'handicap_initial': safe_float(handicap_data.get('initial_handicap', 0)),
            }
            
            features['handicap_change'] = features['handicap_current'] - features['handicap_initial']
            features['concentration'] = max(
                features['home_volume_pct'],
                features['away_volume_pct'],
                features['draw_volume_pct']
            ) / 100.0
            
            # 如果特征不足，跳过
            if features['concentration'] == 0:
                continue
            
            # 使用规则推荐
            rule_result = recommender.evaluate(features)
            rule_rec = rule_result['recommendation']
            
            # 简单模型推荐（集中度>0.6）
            if features['concentration'] > 0.6:
                if features['home_volume_pct'] > features['away_volume_pct']:
                    model_rec = 'home_win'
                elif features['away_volume_pct'] > features['home_volume_pct']:
                    model_rec = 'away_win'
                else:
                    model_rec = 'draw'
            else:
                model_rec = 'none'
            
            stats['total'] += 1
            
            # 统计规则推荐
            if rule_rec != 'none':
                stats['rule_recommended'] += 1
                if rule_rec == actual_result:
                    stats['rule_correct'] += 1
                    logger.info(f"✅ [{stats['total']}] {match_info.get('home_team', 'N/A')} vs {match_info.get('away_team', 'N/A')}")
                    logger.info(f"   比分:{score}, 规则推荐:{rule_rec}, 实际:{actual_result} - 正确!")
                else:
                    logger.info(f"❌ [{stats['total']}] {match_info.get('home_team', 'N/A')} vs {match_info.get('away_team', 'N/A')}")
                    logger.info(f"   比分:{score}, 规则推荐:{rule_rec}, 实际:{actual_result} - 错误")
            else:
                stats['no_recommendation'] += 1
            
            # 统计模型推荐
            if model_rec != 'none':
                stats['model_recommended'] += 1
                if model_rec == actual_result:
                    stats['model_correct'] += 1
            
            results.append({
                'match': f"{match_info.get('home_team', 'N/A')} vs {match_info.get('away_team', 'N/A')}",
                'score': score,
                'actual': actual_result,
                'rule_rec': rule_rec,
                'model_rec': model_rec,
                'concentration': features['concentration'],
                'handicap_change': features['handicap_change']
            })
            
        except Exception as e:
            logger.debug(f"处理失败 {json_file.name}: {e}")
            continue
    
    # 打印统计
    logger.info("\n" + "="*80)
    logger.info("📊 测试结果统计")
    logger.info("="*80)
    logger.info(f"\n总测试场次: {stats['total']}")
    logger.info(f"未推荐场次: {stats['no_recommendation']}")
    
    logger.info("\n【规则推荐】")
    logger.info(f"  推荐场次: {stats['rule_recommended']}")
    logger.info(f"  正确场次: {stats['rule_correct']}")
    if stats['rule_recommended'] > 0:
        accuracy = stats['rule_correct'] / stats['rule_recommended'] * 100
        logger.info(f"  ✅ 准确率: {accuracy:.1f}%")
    
    logger.info("\n【简单模型推荐（集中度>0.6）】")
    logger.info(f"  推荐场次: {stats['model_recommended']}")
    logger.info(f"  正确场次: {stats['model_correct']}")
    if stats['model_recommended'] > 0:
        accuracy = stats['model_correct'] / stats['model_recommended'] * 100
        logger.info(f"  准确率: {accuracy:.1f}%")
    
    logger.info("\n" + "="*80)
    
    # 保存结果
    with open('quick_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("✅ 详细结果已保存: quick_test_results.json")


if __name__ == "__main__":
    load_and_test()
