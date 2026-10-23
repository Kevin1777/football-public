#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行测试脚本 - 测试已有数据的推荐准确率
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from recommendation.x1_json_recommender import X1JSONRecommender
from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager


def load_matches_from_date(start_date_str, end_date_str=None):
    """从data文件夹加载指定日期范围的比赛数据"""
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.now()
    
    matches = []
    current_date = start_date
    
    print(f"\n📂 开始扫描数据文件...")
    print(f"   日期范围: {start_date_str} 至 {end_date.strftime('%Y-%m-%d')}")
    print("=" * 80)
    
    while current_date <= end_date:
        date_path = Path("data") / str(current_date.year) / f"{current_date.month:02d}" / f"{current_date.day:02d}"
        
        if date_path.exists():
            date_matches = 0
            
            # 遍历该日期目录下的JSON文件
            for json_file in date_path.glob("*.json"):
                # 跳过非比赛文件
                if json_file.stem.startswith("标盘指数") or json_file.name.startswith("盘口数据"):
                    continue
                
                # 只读取比赛JSON文件
                if not json_file.stem.startswith("2025-"):
                    continue
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    match_info = data.get("match_info", {})
                    if match_info:
                        # 提取比分
                        label = match_info.get("label", "")
                        score_match = re.search(r'(\d+)-(\d+)', label) if label else None
                        
                        if score_match:
                            actual_score = (int(score_match.group(1)), int(score_match.group(2)))
                            
                            matches.append({
                                "file": json_file.name,
                                "match_info": match_info,
                                "actual_score": actual_score,
                                "data": data
                            })
                            date_matches += 1
                
                except Exception as e:
                    print(f"   ⚠️  读取文件失败: {json_file.name}, 错误: {e}")
                    continue
            
            if date_matches > 0:
                print(f"   {current_date.strftime('%Y-%m-%d')}: 读取 {date_matches} 场比赛")
        
        current_date += timedelta(days=1)
    
    print("=" * 80)
    print(f"✅ 共加载 {len(matches)} 场比赛\n")
    
    return matches


def calculate_bet_result(recommendation, actual_score, handicap_data):
    """计算推荐结果（适配VIS格式）- 必须考虑让球盘口"""
    if not recommendation:
        return None, "无推荐"
    
    # 检查是否融断
    if recommendation.get("meltdown", {}).get("type"):
        return None, "融断/不推荐"
    
    # 获取推荐方向
    direction = recommendation.get("recommendation", {}).get("direction", "none")
    if direction == "none":
        return None, "不推荐"
    
    # 🔥 关键：必须获取盘口数据
    if not handicap_data:
        return None, "无盘口数据"
    
    hd = handicap_data.get("handicap_data", {})
    if not hd:
        return None, "无盘口数据"
    
    # 获取当前盘口（优先）或初始盘口
    current_handicap = hd.get("current_handicap")
    initial_handicap = hd.get("initial_handicap")
    
    # 尝试从不同字段获取盘口（注意：0是有效值）
    handicap = None
    if current_handicap is not None:
        handicap = float(current_handicap)
    elif initial_handicap is not None:
        handicap = float(initial_handicap)
    
    if handicap is None:
        return None, f"无盘口值(current={current_handicap}, initial={initial_handicap})"
    
    home_score, away_score = actual_score
    
    # 🔥 计算让球后的比分
    # 盘口为负数表示主队让球，为正数表示主队受让
    adjusted_home = home_score + handicap
    diff = adjusted_home - away_score
    
    # 判断结果
    if direction == "home":
        if diff > 0.25:
            return "win", "全赢"
        elif diff > 0 and diff <= 0.25:
            return "half_win", "赢半"
        elif abs(diff) < 0.01:  # 浮点数比较
            return "draw", "走水"
        elif diff < 0 and diff >= -0.25:
            return "half_lose", "输半"
        else:
            return "lose", "全输"
    
    elif direction == "away":
        if diff < -0.25:
            return "win", "全赢"
        elif diff < 0 and diff >= -0.25:
            return "half_win", "赢半"
        elif abs(diff) < 0.01:
            return "draw", "走水"
        elif diff > 0 and diff <= 0.25:
            return "half_lose", "输半"
        else:
            return "lose", "全输"
    
    return None, "未知方向"


def test_accuracy(start_date, end_date=None):
    """测试准确率"""
    
    print("\n" + "=" * 80)
    print("🎯 批量回测 - X1 JSON推荐引擎准确率测试")
    print("=" * 80)
    
    # 初始化推荐引擎
    print("\n⚙️  初始化推荐引擎...")
    recommender = X1JSONRecommender()
    lottery500_client = Lottery500Client(data_dir=str(BASE_DIR / "data"))
    bifaw_client = BifawClient()
    detail_cache_manager = DetailCacheManager(cache_dir=str(BASE_DIR / "data"))
    
    print("✅ 推荐引擎初始化完成\n")
    
    # 加载比赛数据
    matches = load_matches_from_date(start_date, end_date)
    
    if not matches:
        print("❌ 没有找到比赛数据！")
        return
    
    # 统计
    stats = {
        "total": len(matches),
        "recommended": 0,
        "no_bet": 0,
        "win": 0,
        "lose": 0,
        "half_win": 0,
        "half_lose": 0,
        "draw": 0,
        "error": 0
    }
    
    results = []
    
    print("🔄 开始批量回测...\n")
    print("=" * 80)
    
    for i, match in enumerate(matches, 1):
        match_info = match["match_info"]
        actual_score = match["actual_score"]
        file_path = Path("data") / match["file"]
        
        # 构建完整的文件路径
        label = match_info.get("label", "未知比赛")
        
        # 从文件名中提取日期
        date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', match["file"])
        if date_match:
            year, month, day = date_match.groups()
            file_path = Path("data") / year / month / day / match["file"]
        
        try:
            # 🔥 先检查是否有完整的盘口数据（注意：0是有效值，不能用not判断）
            hd = match["data"].get("handicap_data", {})
            if not hd or (hd.get("current_handicap") is None and hd.get("initial_handicap") is None):
                # 跳过没有盘口数据的比赛
                stats["no_bet"] += 1
                if i <= 5:  # 打印前5个跳过的原因
                    print(f"  跳过 {i}: 无盘口数据")
                continue
            
            # 获取推荐 - 直接传递文件路径
            recommendation = recommender.recommend(str(file_path))
            
            # 调试：打印推荐结果
            if i == 1:
                print(f"\n调试 - 推荐结果示例:")
                print(f"  键: {list(recommendation.keys()) if recommendation else 'None'}")
                print(f"  内容: {recommendation}\n")
            
            # 判断是否有推荐（VIS格式）
            direction = recommendation.get("recommendation", {}).get("direction", "none")
            has_meltdown = bool(recommendation.get("meltdown", {}).get("type"))
            
            if recommendation and direction != "none" and not has_meltdown:
                stats["recommended"] += 1
                
                # 计算结果
                result_type, result_label = calculate_bet_result(recommendation, actual_score, match["data"])
                
                if result_type:
                    stats[result_type] += 1
                    
                    result_emoji = {
                        "win": "✅",
                        "half_win": "⬆️",
                        "draw": "➖",
                        "half_lose": "⬇️",
                        "lose": "❌"
                    }.get(result_type, "❓")
                    
                    direction_text = {"home": "主胜", "away": "客胜"}.get(direction, direction)
                    confidence = recommendation.get("recommendation", {}).get("confidence", 0)
                    
                    # 获取盘口信息用于显示
                    hd = match["data"].get("handicap_data", {})
                    handicap = hd.get("current_handicap") or hd.get("initial_handicap") or 0
                    handicap_str = f"盘口{handicap:+.2f}" if handicap != 0 else "平手盘"
                    
                    print(f"[{i:3d}/{len(matches)}] {result_emoji} {result_label}: {label}")
                    print(f"         推荐: {direction_text} (置信度{confidence:.2f}) | 实际: {actual_score[0]}-{actual_score[1]} | {handicap_str}")
                    
                    results.append({
                        "label": label,
                        "recommendation": recommendation.get("recommended_bet"),
                        "actual_score": f"{actual_score[0]}-{actual_score[1]}",
                        "result": result_label
                    })
            else:
                stats["no_bet"] += 1
                # print(f"[{i:3d}/{len(matches)}] ⏭️  不推荐: {label}")
        
        except Exception as e:
            stats["error"] += 1
            print(f"[{i:3d}/{len(matches)}] ⚠️  错误: {label} - {e}")
    
    print("=" * 80)
    
    # 计算胜率
    total_bets = stats["win"] + stats["lose"] + stats["half_win"] + stats["half_lose"] + stats["draw"]
    if total_bets > 0:
        # 全赢=1分, 赢半=0.5分, 走水=0分, 输半=-0.5分, 全输=-1分
        points = stats["win"] + stats["half_win"] * 0.5 - stats["half_lose"] * 0.5 - stats["lose"]
        win_rate = (points / total_bets) * 100
    else:
        win_rate = 0
    
    # 显示结果
    print("\n" + "=" * 80)
    print("📊 回测结果统计")
    print("=" * 80)
    print(f"\n总场次: {stats['total']}")
    print(f"推荐场次: {stats['recommended']} ({stats['recommended']/stats['total']*100:.1f}%)")
    print(f"不推荐: {stats['no_bet']} ({stats['no_bet']/stats['total']*100:.1f}%)")
    
    if stats['error'] > 0:
        print(f"错误: {stats['error']}")
    
    print(f"\n{'─' * 80}")
    print("推荐结果分布:")
    print(f"{'─' * 80}")
    print(f"  ✅ 全赢: {stats['win']}")
    print(f"  ⬆️ 赢半: {stats['half_win']}")
    print(f"  ➖ 走水: {stats['draw']}")
    print(f"  ⬇️ 输半: {stats['half_lose']}")
    print(f"  ❌ 全输: {stats['lose']}")
    
    print(f"\n{'=' * 80}")
    print(f"🎯 引擎胜率: {win_rate:.1f}%")
    print("=" * 80)
    
    # 胜率评价
    if win_rate >= 60:
        print("\n✨ 评价: 优秀！")
    elif win_rate >= 55:
        print("\n👍 评价: 良好")
    elif win_rate >= 50:
        print("\n✔️  评价: 及格")
    else:
        print("\n⚠️  评价: 需要优化")
    
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试推荐引擎准确率")
    parser.add_argument("start_date", help="开始日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--end-date", help="结束日期 (格式: YYYY-MM-DD，默认为今天)")
    
    args = parser.parse_args()
    
    test_accuracy(args.start_date, args.end_date)
