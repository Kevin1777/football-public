#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
比分反推特征分析系统 - Score Reverse Engineer

核心功能：
1. 从已知比分结果反推交易特征模式
2. 识别高置信度的特征组合
3. 生成推荐规则库
4. 重构评分模型

使用方法：
    python score_reverse_engineer.py
    
作者：AI System  
日期：2025-11-22
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import pandas as pd
import numpy as np
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'reverse_engineer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ScoreReverseEngineer:
    """比分反推特征分析器"""
    
    def __init__(self, detail_cache_dir: str = "detail_cache"):
        self.detail_cache_dir = Path(detail_cache_dir)
        self.matches = []
        self.patterns = {
            'home_win': [],
            'away_win': [],
            'draw': []
        }
        self.rules = []
        
    def load_matches(self) -> int:
        """
        加载所有有比分的比赛数据
        
        Returns:
            加载的比赛数量
        """
        logger.info("="*80)
        logger.info("📥 开始加载有比分的比赛数据...")
        logger.info("="*80)
        
        if not self.detail_cache_dir.exists():
            logger.error(f"缓存目录不存在: {self.detail_cache_dir}")
            return 0
        
        loaded_count = 0
        for json_file in self.detail_cache_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查是否有比分
                match_info = data.get('match_info', {})
                score = match_info.get('score', '')
                
                if score and '-' in score:
                    self.matches.append({
                        'filename': json_file.name,
                        'data': data,
                        'score': score
                    })
                    loaded_count += 1
                    
            except Exception as e:
                logger.warning(f"加载失败 {json_file.name}: {e}")
        
        logger.info(f"✅ 成功加载 {loaded_count} 场有比分的比赛")
        return loaded_count
    
    def extract_features(self, match: Dict) -> Optional[Dict]:
        """
        从比赛数据中提取关键特征
        
        Args:
            match: 比赛数据字典
            
        Returns:
            特征字典或None（如果提取失败）
        """
        try:
            data = match['data']
            features = {
                'filename': match['filename'],
                'score': match['score']
            }
            
            # 1. 解析比分结果
            score = match['score']
            parts = score.split('-')
            if len(parts) != 2:
                return None
                
            home_score = int(parts[0])
            away_score = int(parts[1])
            
            features['home_score'] = home_score
            features['away_score'] = away_score
            features['goal_diff'] = home_score - away_score
            features['total_goals'] = home_score + away_score
            
            # 分类结果
            if home_score > away_score:
                features['result'] = 'home_win'
            elif away_score > home_score:
                features['result'] = 'away_win'
            else:
                features['result'] = 'draw'
            
            # 2. 提取盘口特征
            handicap = data.get('handicap_data', {})
            if handicap:
                features['handicap_initial'] = float(handicap.get('initial_handicap', 0))
                features['handicap_current'] = float(handicap.get('current_handicap', 0))
                features['handicap_change'] = features['handicap_current'] - features['handicap_initial']
                features['home_odds_initial'] = float(handicap.get('initial_home_odds', 0))
                features['home_odds_current'] = float(handicap.get('current_home_odds', 0))
                features['away_odds_initial'] = float(handicap.get('initial_away_odds', 0))
                features['away_odds_current'] = float(handicap.get('current_away_odds', 0))
            
            # 3. 提取交易特征（取最后一条记录）
            trade_data = data.get('trade_data', {})
            if trade_data and 'data' in trade_data and len(trade_data['data']) > 0:
                last_record = trade_data['data'][0]  # 最新记录
                
                # 成交量分布
                features['home_volume_pct'] = self._safe_float(last_record.get('比例_主', 0))
                features['draw_volume_pct'] = self._safe_float(last_record.get('比例_和', 0))
                features['away_volume_pct'] = self._safe_float(last_record.get('比例_客', 0))
                features['total_volume'] = self._safe_number(last_record.get('总成交量', 0))
                
                # 欧赔
                features['home_odds'] = self._safe_float(last_record.get('主胜_欧赔', 0))
                features['draw_odds'] = self._safe_float(last_record.get('和局_欧赔', 0))
                features['away_odds'] = self._safe_float(last_record.get('客胜_欧赔', 0))
                
                # 凯利指数（归一化到0-1）
                features['kelly_home'] = self._safe_float(last_record.get('凯利_主', 100)) / 100.0
                features['kelly_draw'] = self._safe_float(last_record.get('凯利_和', 100)) / 100.0
                features['kelly_away'] = self._safe_float(last_record.get('凯利_客', 100)) / 100.0
                
                # 必发指数
                features['bfi_home'] = self._safe_float(last_record.get('必指_主', 0))
                features['bfi_draw'] = self._safe_float(last_record.get('必指_和', 0))
                features['bfi_away'] = self._safe_float(last_record.get('必指_客', 0))
                
                # 赔指
                features['pz_home'] = self._safe_float(last_record.get('赔指_主', 0))
                features['pz_draw'] = self._safe_float(last_record.get('赔指_和', 0))
                features['pz_away'] = self._safe_float(last_record.get('赔指_客', 0))
                
                # 热指
                features['hot_home'] = self._safe_float(last_record.get('热指_主', 0))
                features['hot_draw'] = self._safe_float(last_record.get('热指_和', 0))
                features['hot_away'] = self._safe_float(last_record.get('热指_客', 0))
                
                # 计算集中度
                volume_pcts = [
                    features['home_volume_pct'],
                    features['draw_volume_pct'],
                    features['away_volume_pct']
                ]
                features['concentration'] = max(volume_pcts) / 100.0 if max(volume_pcts) > 0 else 0
                
                # 计算凯利异常度
                features['kelly_home_anomaly'] = features['kelly_home'] - 1.0
                features['kelly_away_anomaly'] = features['kelly_away'] - 1.0
            
            # 4. 比赛信息
            match_info = data.get('match_info', {})
            features['league'] = match_info.get('league', '')
            features['home_team'] = match_info.get('home', '')
            features['away_team'] = match_info.get('away', '')
            features['kickoff'] = match_info.get('kickoff', '')
            
            return features
            
        except Exception as e:
            logger.error(f"特征提取失败 {match.get('filename')}: {e}")
            return None
    
    def _safe_float(self, value) -> float:
        """安全转换为浮点数"""
        try:
            if pd.isna(value):
                return 0.0
            return float(str(value).replace(',', ''))
        except:
            return 0.0
    
    def _safe_number(self, value) -> float:
        """安全转换数字（处理逗号分隔）"""
        try:
            if pd.isna(value):
                return 0.0
            return float(str(value).replace(',', ''))
        except:
            return 0.0


    def analyze_patterns(self):
        """分析特征模式，按结果分组"""
        logger.info("\n" + "="*80)
        logger.info("🔍 开始分析特征模式...")
        logger.info("="*80)
        
        # 提取所有特征并分组
        success_count = 0
        for match in self.matches:
            features = self.extract_features(match)
            if features and features.get('result'):
                result = features['result']
                self.patterns[result].append(features)
                success_count += 1
        
        logger.info(f"✅ 成功提取 {success_count} 场比赛的特征")
        
        # 统计各类结果数量
        total = success_count
        logger.info(f"\n📊 比赛结果分布:")
        for result_type in ['home_win', 'away_win', 'draw']:
            count = len(self.patterns[result_type])
            pct = count / total * 100 if total > 0 else 0
            logger.info(f"  {result_type:10s}: {count:3d} 场 ({pct:5.1f}%)")
        
        # 分析各类结果的特征
        logger.info("\n" + "="*80)
        logger.info("📈 开始分析各类结果的特征分布...")
        logger.info("="*80)
        
        for result_type in ['home_win', 'away_win', 'draw']:
            self._analyze_result_features(result_type)
    
    def _analyze_result_features(self, result_type: str):
        """分析特定结果类型的特征分布"""
        matches = self.patterns[result_type]
        if not matches:
            logger.info(f"\n{result_type}: 无数据")
            return
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 {result_type.upper()} 特征分析 (样本数: {len(matches)})")
        logger.info(f"{'='*80}")
        
        # 定义要分析的特征
        features_to_analyze = {
            '成交量集中度': 'concentration',
            '主队成交占比': 'home_volume_pct',
            '客队成交占比': 'away_volume_pct',
            '主队欧赔': 'home_odds',
            '客队欧赔': 'away_odds',
            '主队凯利异常': 'kelly_home_anomaly',
            '客队凯利异常': 'kelly_away_anomaly',
            '盘口变化': 'handicap_change',
            '当前盘口': 'handicap_current',
        }
        
        # 统计每个特征的分布
        stats = {}
        for name, key in features_to_analyze.items():
            values = [m[key] for m in matches if key in m and m[key] is not None]
            if values:
                stats[name] = {
                    'mean': np.mean(values),
                    'median': np.median(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'q25': np.percentile(values, 25),
                    'q75': np.percentile(values, 75),
                }
        
        # 输出统计结果
        for name, stat in stats.items():
            logger.info(f"\n{name}:")
            logger.info(f"  平均值: {stat['mean']:.3f}")
            logger.info(f"  中位数: {stat['median']:.3f}")
            logger.info(f"  标准差: {stat['std']:.3f}")
            logger.info(f"  范围: [{stat['min']:.3f}, {stat['max']:.3f}]")
            logger.info(f"  四分位: [Q25={stat['q25']:.3f}, Q75={stat['q75']:.3f}]")
    
    def find_high_confidence_rules(self, min_samples: int = 3, min_win_rate: float = 0.70):
        """
        找出高置信度的规则
        
        Args:
            min_samples: 最少样本数
            min_win_rate: 最低胜率
        """
        logger.info("\n" + "="*80)
        logger.info(f"🎯 开始挖掘高置信度规则 (最少{min_samples}样本, 胜率>{min_win_rate*100}%)")
        logger.info("="*80)
        
        all_features = []
        for result_type in ['home_win', 'away_win', 'draw']:
            all_features.extend(self.patterns[result_type])
        
        if len(all_features) == 0:
            logger.warning("没有可分析的数据")
            return
        
        # 规则1: 主队高成交集中 + 让球
        rule1 = self._test_rule(
            all_features,
            lambda f: (
                f.get('home_volume_pct', 0) > 70 and
                f.get('handicap_current', 0) < -0.5 and
                f.get('concentration', 0) > 0.7
            ),
            'home_win',
            "主队成交占比>70% AND 主队让球>0.5 AND 集中度>0.7",
            min_samples,
            min_win_rate
        )
        if rule1:
            self.rules.append(rule1)
        
        # 规则2: 客队高成交 + 受让
        rule2 = self._test_rule(
            all_features,
            lambda f: (
                f.get('away_volume_pct', 0) > 60 and
                f.get('handicap_current', 0) > 0.5 and
                f.get('concentration', 0) > 0.65
            ),
            'away_win',
            "客队成交占比>60% AND 客队受让>0.5 AND 集中度>0.65",
            min_samples,
            min_win_rate
        )
        if rule2:
            self.rules.append(rule2)
        
        # 规则3: 主队低赔 + 高成交
        rule3 = self._test_rule(
            all_features,
            lambda f: (
                f.get('home_odds', 99) < 1.5 and
                f.get('home_volume_pct', 0) > 65 and
                f.get('total_volume', 0) > 100000
            ),
            'home_win',
            "主队欧赔<1.5 AND 主队成交>65% AND 总成交量>10万",
            min_samples,
            min_win_rate
        )
        if rule3:
            self.rules.append(rule3)
        
        # 规则4: 盘口大幅升盘 + 成交跟进
        rule4 = self._test_rule(
            all_features,
            lambda f: (
                f.get('handicap_change', 0) > 0.25 and
                f.get('home_volume_pct', 0) > 55
            ),
            'home_win',
            "盘口变化>0.25(升盘) AND 主队成交>55%",
            min_samples,
            min_win_rate
        )
        if rule4:
            self.rules.append(rule4)
        
        # 规则5: 凯利异常低 + 成交高（陷阱盘）
        rule5 = self._test_rule(
            all_features,
            lambda f: (
                f.get('kelly_home_anomaly', 0) < -0.1 and
                f.get('home_volume_pct', 0) > 60
            ),
            'away_win',
            "主队凯利异常<-0.1 AND 主队成交>60% (陷阱盘)",
            min_samples,
            min_win_rate
        )
        if rule5:
            self.rules.append(rule5)
        
        # 规则6: 客队凯利异常高 + 成交支持
        rule6 = self._test_rule(
            all_features,
            lambda f: (
                f.get('kelly_away_anomaly', 0) > 0.15 and
                f.get('away_volume_pct', 0) > 50
            ),
            'away_win',
            "客队凯利异常>0.15 AND 客队成交>50%",
            min_samples,
            min_win_rate
        )
        if rule6:
            self.rules.append(rule6)
        
        logger.info(f"\n✅ 发现 {len(self.rules)} 条高置信度规则")
    
    def _test_rule(self, all_features: List[Dict], condition_func, expected_result: str, 
                   rule_name: str, min_samples: int, min_win_rate: float) -> Optional[Dict]:
        """
        测试一个规则
        
        Args:
            all_features: 所有特征数据
            condition_func: 条件判断函数
            expected_result: 期望结果
            rule_name: 规则名称
            min_samples: 最少样本数
            min_win_rate: 最低胜率
            
        Returns:
            规则字典或None
        """
        # 找出满足条件的比赛
        matched = [f for f in all_features if condition_func(f)]
        
        if len(matched) < min_samples:
            return None
        
        # 计算胜率
        wins = sum(1 for f in matched if f.get('result') == expected_result)
        win_rate = wins / len(matched) if len(matched) > 0 else 0
        
        if win_rate >= min_win_rate:
            rule = {
                'name': rule_name,
                'expected_result': expected_result,
                'matches': len(matched),
                'wins': wins,
                'win_rate': win_rate,
                'confidence': win_rate
            }
            
            logger.info(f"\n✅ 发现高置信度规则:")
            logger.info(f"  规则: {rule_name}")
            logger.info(f"  预期结果: {expected_result}")
            logger.info(f"  匹配样本: {len(matched)} 场")
            logger.info(f"  命中次数: {wins} 场")
            logger.info(f"  胜率: {win_rate*100:.1f}%")
            
            return rule
        
        return None
    
    def generate_model_config(self, output_file: str = "model_rules_config.json"):
        """
        生成模型配置文件
        
        Args:
            output_file: 输出文件名
        """
        logger.info("\n" + "="*80)
        logger.info("📝 生成模型配置文件...")
        logger.info("="*80)
        
        config = {
            'generated_at': datetime.now().isoformat(),
            'total_matches_analyzed': len(self.matches),
            'rules': self.rules,
            'statistics': {
                'home_wins': len(self.patterns['home_win']),
                'away_wins': len(self.patterns['away_win']),
                'draws': len(self.patterns['draw']),
            }
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 配置文件已保存: {output_path}")
        logger.info(f"   包含 {len(self.rules)} 条规则")
        
        return config
    
    def run_full_analysis(self):
        """运行完整的分析流程"""
        logger.info("\n" + "="*80)
        logger.info("🚀 开始完整的反推分析流程")
        logger.info("="*80)
        
        # 1. 加载数据
        count = self.load_matches()
        if count == 0:
            logger.error("没有可分析的数据，退出")
            return
        
        # 2. 分析特征模式
        self.analyze_patterns()
        
        # 3. 挖掘高置信度规则
        self.find_high_confidence_rules(min_samples=3, min_win_rate=0.70)
        
        # 4. 生成模型配置
        config = self.generate_model_config()
        
        logger.info("\n" + "="*80)
        logger.info("✅ 分析完成！")
        logger.info("="*80)
        logger.info(f"\n总结:")
        logger.info(f"  分析了 {count} 场比赛")
        logger.info(f"  发现 {len(self.rules)} 条高置信度规则")
        logger.info(f"  配置文件: model_rules_config.json")
        
        return config


if __name__ == "__main__":
    engineer = ScoreReverseEngineer()
    engineer.run_full_analysis()
