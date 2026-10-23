#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全方案对比测试 - 一次性测试所有策略并对比
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime
from collections import Counter

from recommendation.x1_json_recommender_fixed import X1JSONRecommenderFixed

logging.basicConfig(level=logging.ERROR, format='%(message)s')
logger = logging.getLogger(__name__)


# ========== 联赛配置 ==========
LEAGUE_TIERS = {
    'S级': ['英超', '西甲', '德甲', '意甲', '法甲', '欧冠', '欧联', '世界杯'],
    'A级': ['英冠', '荷甲', '葡超', '巴甲', '阿甲', '中超', '亚冠', '美职业'],
    'B级': ['英甲', '德乙', '法乙', 'J联赛', '俄超', '土超', '比甲'],
    'C级': []
}

def get_league_tier(league: str) -> str:
    """获取联赛等级"""
    if not league:
        return 'C级'
    for tier, leagues in LEAGUE_TIERS.items():
        if any(l in league for l in leagues):
            return tier
    return 'C级'


# ========== 数据提取 ==========
def extract_match_info(filename: str) -> Optional[Tuple[str, int, int, str]]:
    """从文件名提取信息"""
    parts = filename.split('_')
    if len(parts) < 5:
        return None
    
    league = parts[1]
    pattern = r'(\d{4}-\d{2}-\d{2})_.*_(\d+)_(\d+)_(\d{4})\.json$'
    match = re.search(pattern, filename)
    
    if match:
        date = match.group(1)
        home_score = int(match.group(2))
        away_score = int(match.group(3))
        time = match.group(4)
        hour = time[:2]
        minute = time[2:]
        kickoff_time = f"{date} {hour}:{minute}:00"
        return (kickoff_time, home_score, away_score, league)
    return None


# ========== 策略实现 ==========

class Strategy:
    """策略基类"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.stats = {
            'total': 0,
            'recommended': 0,
            'correct': 0,
            'wrong': 0,
            'draw': 0
        }
    
    def should_recommend(self, confidence: float, direction: str, 
                        match_info: Dict, metrics: Dict) -> bool:
        """判断是否推荐（子类实现）"""
        raise NotImplementedError
    
    def get_accuracy(self) -> float:
        """计算准确率"""
        valid = self.stats['correct'] + self.stats['wrong']
        return self.stats['correct'] / valid * 100 if valid > 0 else 0
    
    def get_recommendation_rate(self) -> float:
        """推荐率"""
        return self.stats['recommended'] / self.stats['total'] * 100 if self.stats['total'] > 0 else 0


class CurrentStrategy(Strategy):
    """当前方案：固定阈值0.80"""
    def __init__(self):
        super().__init__("当前方案", "固定阈值0.80")
        self.threshold = 0.80
    
    def should_recommend(self, confidence, direction, match_info, metrics):
        return direction != 'none' and confidence >= self.threshold


class TieredThresholdStrategy(Strategy):
    """策略1：分级阈值"""
    def __init__(self):
        super().__init__("策略1：分级阈值", "联赛分级+成交量+数据质量动态阈值")
    
    def calculate_threshold(self, match_info: Dict, metrics: Dict) -> float:
        """计算动态阈值"""
        base = 0.80
        adj = 0
        
        # 联赛等级
        tier = get_league_tier(match_info.get('league', ''))
        tier_adj = {'S级': -0.05, 'A级': -0.03, 'B级': 0.00, 'C级': 0.05}
        adj += tier_adj.get(tier, 0.05)
        
        # 成交量
        volume = metrics.get('total_volume', 0)
        if volume > 500000:
            adj -= 0.03
        elif volume > 200000:
            adj -= 0.02
        elif volume < 50000:
            adj += 0.05
        
        # 数据质量
        quality = sum([
            metrics.get('bfindex_home', 0) > 0,
            metrics.get('kelly_home', 0) > 0,
            metrics.get('home_euro_odds', 0) > 0
        ])
        if quality == 3:
            adj -= 0.02
        elif quality < 2:
            adj += 0.03
        
        return max(0.70, min(0.90, base + adj))
    
    def should_recommend(self, confidence, direction, match_info, metrics):
        if direction == 'none':
            return False
        threshold = self.calculate_threshold(match_info, metrics)
        return confidence >= threshold


class ConfidenceRangeStrategy(Strategy):
    """策略3：置信区间（降低到0.75）"""
    def __init__(self):
        super().__init__("策略3：置信区间", "阈值降低到0.75，分级推荐")
        self.threshold = 0.75
    
    def should_recommend(self, confidence, direction, match_info, metrics):
        return direction != 'none' and confidence >= self.threshold


class LeagueExpandStrategy(Strategy):
    """策略4：扩展联赛（只推荐主流联赛）"""
    def __init__(self):
        super().__init__("策略4：扩展联赛", "优先主流联赛，降低阈值")
        self.main_leagues = ['英超', '西甲', '德甲', '意甲', '法甲', '欧冠', '欧联', 
                            '英冠', '荷甲', '葡超', '中超', '亚冠']
    
    def should_recommend(self, confidence, direction, match_info, metrics):
        if direction == 'none':
            return False
        
        league = match_info.get('league', '')
        is_main = any(l in league for l in self.main_leagues)
        
        if is_main:
            return confidence >= 0.75  # 主流联赛降低阈值
        else:
            return confidence >= 0.85  # 其他联赛提高阈值


class AggressiveStrategy(Strategy):
    """策略5：激进模式（阈值0.70）"""
    def __init__(self):
        super().__init__("策略5：激进模式", "阈值0.70，最大化覆盖")
        self.threshold = 0.70
    
    def should_recommend(self, confidence, direction, match_info, metrics):
        return direction != 'none' and confidence >= self.threshold


# ========== 主测试函数 ==========

def run_comprehensive_test():
    """运行全方案对比测试"""
    
    print("=" * 100)
    print("🔬 全方案对比测试")
    print("=" * 100)
    print()
    
    # 初始化所有策略
    strategies = [
        CurrentStrategy(),
        TieredThresholdStrategy(),
        ConfidenceRangeStrategy(),
        LeagueExpandStrategy(),
        AggressiveStrategy()
    ]
    
    print("📋 测试方案:")
    for i, s in enumerate(strategies, 1):
        print(f"   {i}. {s.name}: {s.description}")
    print()
    
    # 加载数据
    engine = X1JSONRecommenderFixed()
    data_dir = Path("data")
    all_files = list(data_dir.rglob("2025-*.json"))
    
    # 筛选有比分的文件
    valid_matches = []
    for f in all_files:
        info = extract_match_info(f.name)
        if info:
            kickoff_time, home_score, away_score, league = info
            valid_matches.append({
                'file': f,
                'kickoff_time': kickoff_time,
                'home_score': home_score,
                'away_score': away_score,
                'league': league
            })
    
    print(f"📂 找到 {len(valid_matches)} 场有效比赛")
    print(f"⏳ 开始测试...")
    print()
    
    # 测试每场比赛
    for i, match in enumerate(valid_matches, 1):
        if i % 200 == 0:
            print(f"  处理进度... {i}/{len(valid_matches)} ({i/len(valid_matches)*100:.1f}%)")
        
        try:
            # 生成推荐
            result = engine.recommend(
                str(match['file']),
                kickoff_time=match['kickoff_time'],
                strict_mode=True
            )
            
            if result.get('meltdown'):
                for strategy in strategies:
                    strategy.stats['total'] += 1
                continue
            
            rec = result.get('recommendation', {})
            direction = rec.get('direction', 'none')
            confidence = rec.get('confidence', 0)
            
            # 实际结果
            if match['home_score'] > match['away_score']:
                actual = 'home'
            elif match['away_score'] > match['home_score']:
                actual = 'away'
            else:
                actual = 'draw'
            
            # 提取metrics（简化版）
            metrics = {
                'total_volume': result.get('funding_level', {}).get('total_volume', 0),
                'bfindex_home': 80,  # 简化
                'kelly_home': 0.9,
                'home_euro_odds': 1.8
            }
            
            match_info = {'league': match['league']}
            
            # 测试每个策略
            for strategy in strategies:
                strategy.stats['total'] += 1
                
                if strategy.should_recommend(confidence, direction, match_info, metrics):
                    strategy.stats['recommended'] += 1
                    
                    if direction == actual:
                        strategy.stats['correct'] += 1
                    elif actual == 'draw':
                        strategy.stats['draw'] += 1
                    else:
                        strategy.stats['wrong'] += 1
        
        except Exception as e:
            for strategy in strategies:
                strategy.stats['total'] += 1
            continue
    
    print()
    print("=" * 100)
    print("📊 对比结果")
    print("=" * 100)
    print()
    
    # 输出结果表格
    print(f"{'方案':<20} {'准确率':<12} {'推荐量':<15} {'推荐率':<12} {'正确':<8} {'错误':<8} {'走盘':<8}")
    print("-" * 100)
    
    results = []
    for strategy in strategies:
        acc = strategy.get_accuracy()
        rec_rate = strategy.get_recommendation_rate()
        rec_count = strategy.stats['recommended']
        
        results.append({
            'name': strategy.name,
            'accuracy': acc,
            'recommended': rec_count,
            'rec_rate': rec_rate,
            'correct': strategy.stats['correct'],
            'wrong': strategy.stats['wrong'],
            'draw': strategy.stats['draw']
        })
        
        print(f"{strategy.name:<20} {acc:>6.1f}%     "
              f"{rec_count:>4}场 ({rec_rate:>5.1f}%)  "
              f"{rec_rate:>6.1f}%    "
              f"{strategy.stats['correct']:>6}   "
              f"{strategy.stats['wrong']:>6}   "
              f"{strategy.stats['draw']:>6}")
    
    print()
    print("=" * 100)
    print("💡 综合分析")
    print("=" * 100)
    print()
    
    # 找出最优方案
    best_accuracy = max(results, key=lambda x: x['accuracy'])
    most_recommended = max(results, key=lambda x: x['recommended'])
    
    # 计算综合得分
    for r in results:
        # 综合得分 = 准确率权重60% + 推荐量权重40%
        acc_score = r['accuracy'] / 100 * 60
        rec_score = (r['recommended'] / most_recommended['recommended']) * 40
        r['综合得分'] = acc_score + rec_score
    
    best_overall = max(results, key=lambda x: x['综合得分'])
    
    print(f"🏆 最高准确率: {best_accuracy['name']} ({best_accuracy['accuracy']:.1f}%)")
    print(f"📈 最多推荐: {most_recommended['name']} ({most_recommended['recommended']}场)")
    print(f"⭐ 综合最优: {best_overall['name']} (得分{best_overall['综合得分']:.1f})")
    print()
    
    print("📊 详细评分:")
    sorted_results = sorted(results, key=lambda x: x['综合得分'], reverse=True)
    for i, r in enumerate(sorted_results, 1):
        stars = "⭐" * min(5, int(r['综合得分'] / 20) + 1)
        print(f"   {i}. {r['name']:<20} "
              f"准确率{r['accuracy']:>5.1f}% | "
              f"推荐{r['recommended']:>3}场 | "
              f"得分{r['综合得分']:>5.1f} {stars}")
    
    print()
    print("=" * 100)
    print("💡 推荐方案")
    print("=" * 100)
    print()
    
    # 智能推荐
    if best_overall['name'] == "当前方案":
        print("✅ 建议：保持当前方案")
        print("   当前方案已经是最优平衡")
    else:
        print(f"✅ 建议：切换到 {best_overall['name']}")
        print(f"   准确率: {best_overall['accuracy']:.1f}%")
        print(f"   推荐量: {best_overall['recommended']}场")
        
        current = results[0]  # 当前方案
        print()
        print("   对比当前方案:")
        acc_diff = best_overall['accuracy'] - current['accuracy']
        rec_diff = best_overall['recommended'] - current['recommended']
        print(f"   准确率变化: {acc_diff:+.1f}个百分点")
        print(f"   推荐量变化: {rec_diff:+d}场 ({rec_diff/current['recommended']*100:+.1f}%)")
    
    print()
    print("=" * 100)
    
    # 保存结果
    output = {
        'test_time': datetime.now().isoformat(),
        'total_matches': len(valid_matches),
        'results': results,
        'recommendation': {
            'best_overall': best_overall['name'],
            'reason': f"综合得分{best_overall['综合得分']:.1f}，平衡准确率和推荐量"
        }
    }
    
    with open('全方案对比结果.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ 详细结果已保存到: 全方案对比结果.json")
    print()
    
    return results


if __name__ == "__main__":
    run_comprehensive_test()
