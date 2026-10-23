#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高胜率特征分析 - 找出胜率70%+的推荐特征
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from recommendation.x1_json_recommender import X1JSONRecommender
from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager


def load_matches(start_date_str, end_date_str=None):
    """加载比赛数据"""
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.now()
    
    matches = []
    current_date = start_date
    
    while current_date <= end_date:
        date_path = Path("data") / str(current_date.year) / f"{current_date.month:02d}" / f"{current_date.day:02d}"
        
        if date_path.exists():
            for json_file in date_path.glob("*.json"):
                if json_file.stem.startswith("标盘指数") or json_file.name.startswith("盘口数据"):
                    continue
                
                if not json_file.stem.startswith("2025-"):
                    continue
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    match_info = data.get("match_info", {})
                    if match_info:
                        label = match_info.get("label", "")
                        score_match = re.search(r'(\d+)-(\d+)', label) if label else None
                        
                        if score_match:
                            actual_score = (int(score_match.group(1)), int(score_match.group(2)))
                            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', json_file.name)
                            if date_match:
                                year, month, day = date_match.groups()
                                file_path = Path("data") / year / month / day / json_file.name
                                
                                matches.append({
                                    "file": json_file.name,
                                    "file_path": str(file_path),
                                    "match_info": match_info,
                                    "actual_score": actual_score,
                                    "data": data
                                })
                
                except Exception as e:
                    continue
        
        current_date += timedelta(days=1)
    
    return matches


def analyze_winners(matches, recommender):
    """分析获胜比赛的特征"""
    
    print("\n" + "=" * 80)
    print("🔍 高胜率特征分析")
    print("=" * 80)
    
    winning_features = []
    losing_features = []
    
    print(f"\n⏳ 分析 {len(matches)} 场比赛...")
    
    for i, match in enumerate(matches):
        if i % 100 == 0:
            print(f"  处理中... {i}/{len(matches)}")
        
        try:
            recommendation = recommender.recommend(match["file_path"])
            
            if not recommendation:
                continue
            
            direction = recommendation.get("recommendation", {}).get("direction", "none")
            if direction == "none":
                continue
            
            has_meltdown = bool(recommendation.get("meltdown", {}).get("type"))
            if has_meltdown:
                continue
            
            # 获取特征
            scores = recommendation.get("scores", {})
            funding = recommendation.get("funding_level", {})
            confidence = recommendation.get("recommendation", {}).get("confidence", 0)
            
            flm = scores.get("FLM", {})
            spm = scores.get("SPM", {})
            dpi = scores.get("DPI", {})
            
            # 计算结果
            actual_score = match["actual_score"]
            handicap_data = match["data"].get("handicap_data", {})
            
            if handicap_data:
                hd = handicap_data
                handicap = hd.get("current", {}).get("handicap", 0)
                if handicap is None:
                    handicap = hd.get("initial", {}).get("handicap", 0)
                
                home_score, away_score = actual_score
                adjusted_home = home_score + handicap
                diff = adjusted_home - away_score
                
                won = False
                if direction == "home" and diff > 0.25:
                    won = True
                elif direction == "away" and diff < -0.25:
                    won = True
                
                features = {
                    "confidence": confidence,
                    "flm_confidence": flm.get("confidence", 0),
                    "spm_confidence": spm.get("confidence", 0),
                    "dpi_confidence": dpi.get("confidence", 0),
                    "total_volume": funding.get("total_volume", 0),
                    "funding_level": funding.get("level", ""),
                    "home_pct": flm.get("home_pct", 0),
                    "away_pct": flm.get("away_pct", 0),
                    "direction": direction,
                    "label": match["match_info"].get("label", ""),
                    "won": won
                }
                
                if won:
                    winning_features.append(features)
                else:
                    losing_features.append(features)
        
        except Exception as e:
            continue
    
    print(f"\n✅ 分析完成")
    print(f"   获胜推荐: {len(winning_features)}场")
    print(f"   失败推荐: {len(losing_features)}场")
    
    return winning_features, losing_features


def find_high_winrate_conditions(winning_features, losing_features):
    """找出高胜率的条件组合"""
    
    print("\n" + "=" * 80)
    print("🎯 寻找70%+胜率的条件组合")
    print("=" * 80)
    
    total = len(winning_features) + len(losing_features)
    base_winrate = len(winning_features) / total * 100 if total > 0 else 0
    
    print(f"\n基础胜率: {base_winrate:.1f}% ({len(winning_features)}/{total})")
    
    # 测试不同条件组合
    conditions = []
    
    # 1. 置信度阈值
    for threshold in [0.75, 0.78, 0.80, 0.82, 0.85, 0.88, 0.90, 0.92, 0.95]:
        wins = sum(1 for f in winning_features if f["confidence"] >= threshold)
        losses = sum(1 for f in losing_features if f["confidence"] >= threshold)
        total_cond = wins + losses
        
        if total_cond >= 5:  # 至少5场才有统计意义
            winrate = wins / total_cond * 100
            conditions.append({
                "name": f"置信度 ≥ {threshold:.2f}",
                "wins": wins,
                "losses": losses,
                "total": total_cond,
                "winrate": winrate,
                "recommendation_rate": total_cond / total * 100
            })
    
    # 2. FLM置信度
    for threshold in [0.80, 0.85, 0.90, 0.95]:
        wins = sum(1 for f in winning_features if f["flm_confidence"] >= threshold)
        losses = sum(1 for f in losing_features if f["flm_confidence"] >= threshold)
        total_cond = wins + losses
        
        if total_cond >= 5:
            winrate = wins / total_cond * 100
            conditions.append({
                "name": f"FLM置信度 ≥ {threshold:.2f}",
                "wins": wins,
                "losses": losses,
                "total": total_cond,
                "winrate": winrate,
                "recommendation_rate": total_cond / total * 100
            })
    
    # 3. 成交量级别
    for min_volume in [50000, 100000, 200000, 500000]:
        wins = sum(1 for f in winning_features if f["total_volume"] >= min_volume)
        losses = sum(1 for f in losing_features if f["total_volume"] >= min_volume)
        total_cond = wins + losses
        
        if total_cond >= 5:
            winrate = wins / total_cond * 100
            conditions.append({
                "name": f"成交量 ≥ {min_volume:,}",
                "wins": wins,
                "losses": losses,
                "total": total_cond,
                "winrate": winrate,
                "recommendation_rate": total_cond / total * 100
            })
    
    # 4. 组合条件：高置信度 + 高FLM
    for conf_threshold in [0.85, 0.90]:
        for flm_threshold in [0.90, 0.95]:
            wins = sum(1 for f in winning_features 
                      if f["confidence"] >= conf_threshold and f["flm_confidence"] >= flm_threshold)
            losses = sum(1 for f in losing_features 
                        if f["confidence"] >= conf_threshold and f["flm_confidence"] >= flm_threshold)
            total_cond = wins + losses
            
            if total_cond >= 3:
                winrate = wins / total_cond * 100
                conditions.append({
                    "name": f"置信度≥{conf_threshold:.2f} + FLM≥{flm_threshold:.2f}",
                    "wins": wins,
                    "losses": losses,
                    "total": total_cond,
                    "winrate": winrate,
                    "recommendation_rate": total_cond / total * 100
                })
    
    # 5. 组合条件：高置信度 + 大成交量
    for conf_threshold in [0.85, 0.90]:
        for volume_threshold in [100000, 200000]:
            wins = sum(1 for f in winning_features 
                      if f["confidence"] >= conf_threshold and f["total_volume"] >= volume_threshold)
            losses = sum(1 for f in losing_features 
                        if f["confidence"] >= conf_threshold and f["total_volume"] >= volume_threshold)
            total_cond = wins + losses
            
            if total_cond >= 3:
                winrate = wins / total_cond * 100
                conditions.append({
                    "name": f"置信度≥{conf_threshold:.2f} + 成交量≥{volume_threshold:,}",
                    "wins": wins,
                    "losses": losses,
                    "total": total_cond,
                    "winrate": winrate,
                    "recommendation_rate": total_cond / total * 100
                })
    
    # 按胜率排序
    conditions.sort(key=lambda x: -x["winrate"])
    
    print(f"\n{'条件':<40} {'推荐场次':<10} {'推荐率':<10} {'胜场':<8} {'负场':<8} {'胜率':<10}")
    print("-" * 90)
    
    high_winrate_conditions = []
    for cond in conditions:
        winrate_color = "✅" if cond["winrate"] >= 70 else "⚠️" if cond["winrate"] >= 60 else ""
        print(f"{winrate_color} {cond['name']:<38} {cond['total']:<10} {cond['recommendation_rate']:<9.1f}% {cond['wins']:<8} {cond['losses']:<8} {cond['winrate']:<9.1f}%")
        
        if cond["winrate"] >= 70:
            high_winrate_conditions.append(cond)
    
    return high_winrate_conditions


def generate_optimized_code(high_winrate_conditions):
    """生成优化代码"""
    
    if not high_winrate_conditions:
        print("\n❌ 未找到70%+胜率的条件")
        return
    
    print("\n" + "=" * 80)
    print("💡 推荐的优化策略")
    print("=" * 80)
    
    best = high_winrate_conditions[0]
    
    print(f"\n🎯 最佳策略: {best['name']}")
    print(f"   预期胜率: {best['winrate']:.1f}%")
    print(f"   推荐率: {best['recommendation_rate']:.1f}%")
    print(f"   推荐场次: {best['total']}场")
    
    # 解析条件并生成代码
    name = best['name']
    
    print(f"\n📝 修改建议:")
    print(f"\n在 recommendation/x1_json_recommender.py 的 _calculate_dynamic_threshold 函数中:")
    
    if "置信度" in name and "FLM" in name:
        conf_match = re.search(r'置信度≥([\d.]+)', name)
        flm_match = re.search(r'FLM≥([\d.]+)', name)
        if conf_match and flm_match:
            conf_threshold = float(conf_match.group(1))
            flm_threshold = float(flm_match.group(1))
            
            print(f"""
```python
def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
    # 🔥 策略：高置信度+高FLM才推荐（目标胜率70%+）
    base_threshold = {conf_threshold}  # 基础阈值提高
    
    # 严格要求FLM置信度
    flm_confidence = metrics.get('flm_confidence', 0)
    if flm_confidence < {flm_threshold}:
        base_threshold += 0.10  # FLM不达标，大幅提高阈值
    
    adjustments = 0
    # ... 其他调整保持不变
    
    return max(0.70, min(0.95, base_threshold + adjustments))
```
""")
    
    elif "置信度" in name and "成交量" in name:
        conf_match = re.search(r'置信度≥([\d.]+)', name)
        vol_match = re.search(r'成交量≥([\d,]+)', name)
        if conf_match and vol_match:
            conf_threshold = float(conf_match.group(1))
            volume_threshold = int(vol_match.group(1).replace(',', ''))
            
            print(f"""
```python
def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
    # 🔥 策略：高置信度+大成交量才推荐（目标胜率70%+）
    base_threshold = {conf_threshold}  # 基础阈值提高
    
    # 严格要求成交量
    total_volume = metrics.get('total_volume', 0)
    if total_volume < {volume_threshold}:
        base_threshold += 0.10  # 成交量不达标，大幅提高阈值
    
    adjustments = 0
    # ... 其他调整保持不变
    
    return max(0.70, min(0.95, base_threshold + adjustments))
```
""")
    
    elif "置信度" in name:
        conf_match = re.search(r'置信度 ≥ ([\d.]+)', name)
        if conf_match:
            conf_threshold = float(conf_match.group(1))
            
            print(f"""
```python
def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
    # 🔥 策略：只推荐高置信度比赛（目标胜率70%+）
    base_threshold = {conf_threshold}  # 大幅提高基础阈值
    
    adjustments = 0
    # ... 其他调整保持不变
    
    return max(0.70, min(0.95, base_threshold + adjustments))
```
""")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🎯 高胜率特征分析 - 目标胜率70%+")
    print("=" * 80)
    
    # 初始化
    print("\n⚙️  初始化引擎...")
    recommender = X1JSONRecommender()
    
    # 加载数据
    print("\n📂 加载历史数据...")
    matches = load_matches("2025-11-01", "2025-11-26")
    print(f"✅ 共加载 {len(matches)} 场比赛")
    
    # 分析获胜特征
    winning_features, losing_features = analyze_winners(matches, recommender)
    
    # 寻找高胜率条件
    high_winrate_conditions = find_high_winrate_conditions(winning_features, losing_features)
    
    # 生成优化代码
    generate_optimized_code(high_winrate_conditions)
    
    print("\n" + "=" * 80)
    print("✅ 分析完成")
    print("=" * 80 + "\n")
