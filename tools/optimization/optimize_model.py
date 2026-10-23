#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型优化脚本 - 基于历史数据优化推荐引擎
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

# 添加项目根目录到路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from recommendation.x1_json_recommender import X1JSONRecommender
from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager


def load_all_matches(start_date_str, end_date_str=None):
    """加载所有比赛数据"""
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.now()
    
    matches = []
    current_date = start_date
    
    print(f"\n📂 加载历史数据...")
    print(f"   日期范围: {start_date_str} 至 {end_date.strftime('%Y-%m-%d')}")
    print("=" * 80)
    
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
                            
                            # 构建文件路径
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
    
    print(f"✅ 共加载 {len(matches)} 场比赛\n")
    return matches


def analyze_data_quality(matches):
    """分析数据质量"""
    
    print("\n" + "=" * 80)
    print("📊 数据质量分析")
    print("=" * 80)
    
    stats = {
        "total": len(matches),
        "has_handicap": 0,
        "has_trade_data": 0,
        "complete_data": 0,
        "handicap_companies": defaultdict(int),
        "trade_volume_ranges": defaultdict(int)
    }
    
    for match in matches:
        data = match["data"]
        
        # 检查盘口数据
        if data.get("handicap_data"):
            stats["has_handicap"] += 1
            hd = data["handicap_data"]
            if "company" in hd:
                stats["handicap_companies"][hd["company"]] += 1
        
        # 检查交易数据
        if data.get("trade_data"):
            td = data["trade_data"]
            if "trades" in td and td["trades"]:
                stats["has_trade_data"] += 1
                
                # 计算总成交量
                total_volume = sum(t.get("volume", 0) for t in td["trades"])
                
                if total_volume < 500:
                    stats["trade_volume_ranges"]["<500"] += 1
                elif total_volume < 2000:
                    stats["trade_volume_ranges"]["500-2000"] += 1
                elif total_volume < 10000:
                    stats["trade_volume_ranges"]["2000-10000"] += 1
                else:
                    stats["trade_volume_ranges"][">10000"] += 1
        
        # 完整数据
        if data.get("handicap_data") and data.get("trade_data"):
            stats["complete_data"] += 1
    
    print(f"\n总场次: {stats['total']}")
    print(f"有盘口数据: {stats['has_handicap']} ({stats['has_handicap']/stats['total']*100:.1f}%)")
    print(f"有交易数据: {stats['has_trade_data']} ({stats['has_trade_data']/stats['total']*100:.1f}%)")
    print(f"完整数据: {stats['complete_data']} ({stats['complete_data']/stats['total']*100:.1f}%)")
    
    print(f"\n盘口公司分布:")
    for company, count in sorted(stats["handicap_companies"].items(), key=lambda x: -x[1])[:5]:
        print(f"  {company}: {count}场")
    
    print(f"\n成交量分布:")
    for range_key, count in sorted(stats["trade_volume_ranges"].items()):
        print(f"  {range_key}: {count}场")
    
    return stats


def analyze_recommendations(matches, recommender):
    """分析推荐结果分布"""
    
    print("\n" + "=" * 80)
    print("🎯 推荐结果分析")
    print("=" * 80)
    
    confidence_ranges = {
        "0.50-0.60": [],
        "0.60-0.70": [],
        "0.70-0.75": [],
        "0.75-0.80": [],
        "0.80-0.85": [],
        "0.85-0.90": [],
        "0.90-1.00": []
    }
    
    meltdown_reasons = defaultdict(int)
    direction_stats = {"home": 0, "away": 0, "none": 0}
    
    print("\n⏳ 分析推荐置信度分布...")
    
    for i, match in enumerate(matches):
        if i % 100 == 0:
            print(f"  处理中... {i}/{len(matches)}")
        
        try:
            recommendation = recommender.recommend(match["file_path"])
            
            if recommendation:
                direction = recommendation.get("recommendation", {}).get("direction", "none")
                confidence = recommendation.get("recommendation", {}).get("confidence", 0)
                
                direction_stats[direction] += 1
                
                # 融断原因
                meltdown = recommendation.get("meltdown", {})
                if meltdown.get("type"):
                    meltdown_reasons[meltdown.get("type")] += 1
                
                # 置信度分布
                if confidence >= 0.90:
                    confidence_ranges["0.90-1.00"].append((match, recommendation, confidence))
                elif confidence >= 0.85:
                    confidence_ranges["0.85-0.90"].append((match, recommendation, confidence))
                elif confidence >= 0.80:
                    confidence_ranges["0.80-0.85"].append((match, recommendation, confidence))
                elif confidence >= 0.75:
                    confidence_ranges["0.75-0.80"].append((match, recommendation, confidence))
                elif confidence >= 0.70:
                    confidence_ranges["0.70-0.75"].append((match, recommendation, confidence))
                elif confidence >= 0.60:
                    confidence_ranges["0.60-0.70"].append((match, recommendation, confidence))
                else:
                    confidence_ranges["0.50-0.60"].append((match, recommendation, confidence))
        
        except Exception as e:
            continue
    
    print("\n推荐方向分布:")
    for direction, count in direction_stats.items():
        print(f"  {direction}: {count}场 ({count/len(matches)*100:.1f}%)")
    
    print("\n融断原因分布:")
    for reason, count in sorted(meltdown_reasons.items(), key=lambda x: -x[1])[:10]:
        print(f"  {reason}: {count}场")
    
    print("\n置信度分布:")
    for range_key, items in confidence_ranges.items():
        print(f"  {range_key}: {len(items)}场")
    
    return confidence_ranges, meltdown_reasons, direction_stats


def calculate_optimal_threshold(confidence_ranges, matches):
    """计算最优置信度阈值"""
    
    print("\n" + "=" * 80)
    print("🔬 最优阈值分析")
    print("=" * 80)
    
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.81, 0.85, 0.90]
    results = []
    
    for threshold in thresholds:
        recommended = 0
        win = 0
        lose = 0
        
        for range_key, items in confidence_ranges.items():
            for match, recommendation, confidence in items:
                if confidence >= threshold:
                    direction = recommendation.get("recommendation", {}).get("direction", "none")
                    
                    if direction == "none":
                        continue
                    
                    recommended += 1
                    
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
                        
                        # 简化判断（只看全赢全输）
                        if direction == "home":
                            if diff > 0.25:
                                win += 1
                            elif diff < -0.25:
                                lose += 1
                        elif direction == "away":
                            if diff < -0.25:
                                win += 1
                            elif diff > 0.25:
                                lose += 1
        
        if recommended > 0:
            win_rate = (win / recommended) * 100
            recommendation_rate = (recommended / len(matches)) * 100
            
            results.append({
                "threshold": threshold,
                "recommended": recommended,
                "win": win,
                "lose": lose,
                "win_rate": win_rate,
                "recommendation_rate": recommendation_rate
            })
    
    print("\n阈值对比（按推荐率排序）:\n")
    print(f"{'阈值':<8} {'推荐场次':<10} {'推荐率':<10} {'胜场':<8} {'负场':<8} {'胜率':<10}")
    print("-" * 70)
    
    for r in sorted(results, key=lambda x: -x["recommendation_rate"]):
        print(f"{r['threshold']:<8.2f} {r['recommended']:<10} {r['recommendation_rate']:<10.1f}% {r['win']:<8} {r['lose']:<8} {r['win_rate']:<10.1f}%")
    
    print("\n阈值对比（按胜率排序）:\n")
    print(f"{'阈值':<8} {'推荐场次':<10} {'推荐率':<10} {'胜场':<8} {'负场':<8} {'胜率':<10}")
    print("-" * 70)
    
    for r in sorted(results, key=lambda x: -x["win_rate"]):
        print(f"{r['threshold']:<8.2f} {r['recommended']:<10} {r['recommendation_rate']:<10.1f}% {r['win']:<8} {r['lose']:<8} {r['win_rate']:<10.1f}%")
    
    # 寻找平衡点：推荐率>5% 且 胜率>55%
    print("\n💡 推荐的阈值:")
    
    for r in results:
        if r["recommendation_rate"] >= 5 and r["win_rate"] >= 55:
            print(f"  ✅ 阈值 {r['threshold']:.2f}: 推荐率{r['recommendation_rate']:.1f}%, 胜率{r['win_rate']:.1f}% (推荐{r['recommended']}场)")
    
    return results


def suggest_optimizations(results, meltdown_reasons):
    """给出优化建议"""
    
    print("\n" + "=" * 80)
    print("💡 优化建议")
    print("=" * 80)
    
    # 1. 置信度阈值建议
    best_balance = None
    for r in results:
        if r["recommendation_rate"] >= 5 and r["win_rate"] >= 50:
            if not best_balance or r["win_rate"] > best_balance["win_rate"]:
                best_balance = r
    
    if best_balance:
        print(f"\n1. 调整置信度阈值")
        print(f"   当前阈值: 0.81")
        print(f"   建议阈值: {best_balance['threshold']:.2f}")
        print(f"   预期效果: 推荐率从4.7%提升至{best_balance['recommendation_rate']:.1f}%, 胜率{best_balance['win_rate']:.1f}%")
    
    # 2. 融断机制建议
    print(f"\n2. 优化融断机制")
    print(f"   当前最多融断原因: {max(meltdown_reasons.items(), key=lambda x: x[1])[0]}")
    print(f"   建议: 放宽LOW_CONFIDENCE的限制，或调整置信度计算逻辑")
    
    # 3. 数据质量建议
    print(f"\n3. 数据质量提升")
    print(f"   建议: 确保所有比赛都有完整的盘口和交易数据")
    print(f"   建议: 过滤成交量<500的小比赛")
    
    return best_balance


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🤖 X1推荐引擎模型优化")
    print("=" * 80)
    
    # 初始化
    print("\n⚙️  初始化引擎...")
    recommender = X1JSONRecommender()
    print("✅ 引擎初始化完成")
    
    # 加载数据
    matches = load_all_matches("2025-11-01", "2025-11-26")
    
    # 1. 数据质量分析
    data_stats = analyze_data_quality(matches)
    
    # 2. 推荐结果分析
    confidence_ranges, meltdown_reasons, direction_stats = analyze_recommendations(matches, recommender)
    
    # 3. 最优阈值计算
    results = calculate_optimal_threshold(confidence_ranges, matches)
    
    # 4. 优化建议
    best_threshold = suggest_optimizations(results, meltdown_reasons)
    
    # 5. 生成配置文件
    if best_threshold:
        config = {
            "confidence_threshold": best_threshold["threshold"],
            "updated_at": datetime.now().isoformat(),
            "training_data": {
                "start_date": "2025-11-01",
                "end_date": "2025-11-26",
                "total_matches": len(matches),
                "expected_recommendation_rate": best_threshold["recommendation_rate"],
                "expected_win_rate": best_threshold["win_rate"]
            }
        }
        
        config_file = Path("model_config_optimized.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, indent=2, ensure_ascii=False, fp=f)
        
        print(f"\n✅ 优化配置已保存到: {config_file}")
        print(f"\n下一步: 修改 recommendation/x1_json_recommender.py 中的置信度阈值为 {best_threshold['threshold']:.2f}")
    
    print("\n" + "=" * 80)
    print("✅ 优化分析完成")
    print("=" * 80 + "\n")
