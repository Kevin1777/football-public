#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最终准确率测试 - 使用正确的数据结构
"""

import json
import logging
from pathlib import Path
from rule_based_recommender import RuleBasedRecommender

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def safe_float(value, default=0):
    try:
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace(',', '').replace('%', ''))
    except:
        return default


def safe_number(value, default=0):
    try:
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace(',', ''))
    except:
        return default


def test_accuracy():
    """测试规则推荐准确率"""
    
    detail_cache_dir = Path("detail_cache")
    recommender = RuleBasedRecommender()
    
    logger.info("="*80)
    logger.info("📊 规则推荐系统准确率测试")
    logger.info("="*80)
    
    stats = {
        'total': 0,
        'rule_recommended': 0,
        'rule_correct': 0,
        'model_recommended': 0,
        'model_correct': 0,
        'skipped': 0
    }
    
    results = []
    
    # 加载比赛
    for json_file in detail_cache_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            match_info = data.get('match_info', {})
            score = match_info.get('score', '')
            
            # 只处理有比分的
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
            
            # 提取交易数据（关键：从trade_data['data']中提取）
            trade_data_wrapper = data.get('trade_data', {})
            trade_records = trade_data_wrapper.get('data', [])
            
            if not trade_records:
                stats['skipped'] += 1
                continue
            
            # 取最后一条记录
            last_record = trade_records[0]
            
            # 提取盘口数据
            handicap = data.get('handicap_data', {})
            
            # 构建特征
            features = {
                'home_volume_pct': safe_float(last_record.get('比例_主', 0)),
                'away_volume_pct': safe_float(last_record.get('比例_客', 0)),
                'draw_volume_pct': safe_float(last_record.get('比例_和', 0)),
                'total_volume': safe_number(last_record.get('总成交量', 0)),
                'home_odds': safe_float(last_record.get('主胜_欧赔', 0)),
                'away_odds': safe_float(last_record.get('客胜_欧赔', 0)),
                'draw_odds': safe_float(last_record.get('和局_欧赔', 0)),
                'kelly_home_anomaly': safe_float(last_record.get('凯利_主', 100)) / 100.0 - 1.0,
                'kelly_away_anomaly': safe_float(last_record.get('凯利_客', 100)) / 100.0 - 1.0,
                'handicap_current': safe_float(handicap.get('current_handicap', 0)),
                'handicap_initial': safe_float(handicap.get('initial_handicap', 0)),
            }
            
            features['handicap_change'] = features['handicap_current'] - features['handicap_initial']
            features['concentration'] = max(
                features['home_volume_pct'],
                features['away_volume_pct'],
                features['draw_volume_pct']
            ) / 100.0
            
            # 跳过特征不足的
            if features['concentration'] == 0:
                stats['skipped'] += 1
                continue
            
            stats['total'] += 1
            
            # 规则推荐
            rule_result = recommender.evaluate(features)
            rule_rec = rule_result['recommendation']
            rule_conf = rule_result['confidence']
            rule_reason = rule_result['reason']
            
            # 简单模型推荐（集中度策略）
            if features['concentration'] > 0.6:
                if features['home_volume_pct'] > features['away_volume_pct']:
                    model_rec = 'home_win'
                elif features['away_volume_pct'] > features['home_volume_pct']:
                    model_rec = 'away_win'
                else:
                    model_rec = 'draw'
            else:
                model_rec = 'none'
            
            # 统计规则
            rule_correct = False
            model_correct = False
            
            if rule_rec != 'none':
                stats['rule_recommended'] += 1
                if rule_rec == actual_result:
                    stats['rule_correct'] += 1
                    rule_correct = True
            
            if model_rec != 'none':
                stats['model_recommended'] += 1
                if model_rec == actual_result:
                    stats['model_correct'] += 1
                    model_correct = True
            
            # 显示结果
            match_name = f"{match_info.get('home_team', 'N/A')} vs {match_info.get('away_team', 'N/A')}"
            
            if rule_rec != 'none':
                if rule_correct:
                    logger.info(f"✅ [{stats['total']}] {match_name}")
                    logger.info(f"   比分:{score} | 实际:{actual_result} | 规则推荐:{rule_rec}(置信度:{rule_conf:.2f}) - 正确!")
                    logger.info(f"   理由: {rule_reason}")
                else:
                    logger.info(f"❌ [{stats['total']}] {match_name}")
                    logger.info(f"   比分:{score} | 实际:{actual_result} | 规则推荐:{rule_rec}(置信度:{rule_conf:.2f}) - 错误")
                    logger.info(f"   理由: {rule_reason}")
            
            results.append({
                'match': match_name,
                'score': score,
                'actual': actual_result,
                'rule_rec': rule_rec,
                'rule_conf': rule_conf,
                'rule_correct': rule_correct,
                'model_rec': model_rec,
                'model_correct': model_correct,
                'features': {
                    'concentration': features['concentration'],
                    'handicap_change': features['handicap_change'],
                    'home_volume_pct': features['home_volume_pct']
                }
            })
            
        except Exception as e:
            logger.debug(f"处理失败 {json_file.name}: {e}")
            continue
    
    # 打印统计
    logger.info("\n" + "="*80)
    logger.info("📊 最终统计结果")
    logger.info("="*80)
    logger.info(f"\n有效测试场次: {stats['total']}")
    logger.info(f"跳过场次（无数据）: {stats['skipped']}")
    
    logger.info("\n【规则推荐】")
    logger.info(f"  推荐场次: {stats['rule_recommended']}")
    logger.info(f"  正确场次: {stats['rule_correct']}")
    logger.info(f"  错误场次: {stats['rule_recommended'] - stats['rule_correct']}")
    if stats['rule_recommended'] > 0:
        accuracy = stats['rule_correct'] / stats['rule_recommended'] * 100
        logger.info(f"  ✅ 准确率: {accuracy:.1f}%")
    else:
        logger.info(f"  ⚠️  未匹配到任何规则")
    
    logger.info("\n【简单模型（集中度>0.6）】")
    logger.info(f"  推荐场次: {stats['model_recommended']}")
    logger.info(f"  正确场次: {stats['model_correct']}")
    if stats['model_recommended'] > 0:
        accuracy = stats['model_correct'] / stats['model_recommended'] * 100
        logger.info(f"  准确率: {accuracy:.1f}%")
    
    logger.info("\n" + "="*80)
    
    # 保存结果
    with open('final_test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'stats': stats,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    logger.info("✅ 详细结果已保存: final_test_results.json")


if __name__ == "__main__":
    test_accuracy()
