"""
推荐方向格式化工具

统一将推荐引擎输出的 recommendation/current_handicap 等字段
格式化成 “主队+0.25” 或 “客队-0.5” 的简洁文本，方便各类推送展示。
"""
from __future__ import annotations

from typing import Dict


def _format_handicap_value(handicap_value: float) -> str:
    """
    格式化盘口值（智能去零：-0.50 -> -0.5, 1.00 -> 1, +0.25 -> +0.25）
    """
    if handicap_value is None or abs(handicap_value) < 0.001:
        return "0"

    val = float(handicap_value)
    
    # 1. 整数：去掉小数点
    if val.is_integer():
        return f"{int(val):+d}"
    
    # 2. 一位小数（如0.5）：保留一位
    if (val * 10).is_integer():
        return f"{val:+.1f}"
        
    # 3. 两位小数（如0.25）：保留两位
    return f"{val:+.2f}"


def format_recommendation_direction(
    recommendation: Dict,
    home_team: str = "主队",
    away_team: str = "客队",
) -> str:
    """
    将推荐结果中的方向转换为“主队+0.25”格式。

    Args:
        recommendation: 推荐结果字典
        home_team: 主队名称
        away_team: 客队名称

    Returns:
        str: 格式化后的推荐方向
    """
    rec_text = recommendation.get("recommendation", "") or ""
    current_handicap = recommendation.get("current_handicap")

    # 没有推荐或明确“不推荐”
    if not rec_text.strip() or "不推荐" in rec_text:
        return "不推荐"

    # 主队推荐：直接使用当前盘口
    if "主队" in rec_text or rec_text.lower() == "home":
        handicap_str = _format_handicap_value(current_handicap)
        return f"{home_team} {handicap_str}"

    # 客队推荐：取盘口相反数
    if "客队" in rec_text or rec_text.lower() == "away":
        reversed_handicap = (-current_handicap) if current_handicap is not None else None
        handicap_str = _format_handicap_value(reversed_handicap)
        return f"{away_team} {handicap_str}"

    # 无法解析方向，返回原文
    return rec_text.strip() or "不推荐"


