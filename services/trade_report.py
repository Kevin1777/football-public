from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from parser.pdf_parser import HEADER_ALIASES, HEADER_KEYWORD


@dataclass
class DirectionStats:
    name: str
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    latest_price: Optional[float] = None
    latest_odds: Optional[float] = None
    latest_heat: Optional[float] = None

    @property
    def net_volume(self) -> float:
        return self.buy_volume - self.sell_volume


def _to_number(value: Optional[str]) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _format_number(value: Optional[float], digits: int = 0) -> str:
    if value is None or math.isnan(value):
        return "-"
    if digits == 0:
        return f"{value:,.0f}"
    return f"{value:,.{digits}f}"


def _parse_trade_times(df: pd.DataFrame, metadata: Dict[str, Optional[str]]) -> pd.Series:
    event_datetime = metadata.get("datetime")
    year = None
    if isinstance(event_datetime, str):
        try:
            event_dt = datetime.strptime(event_datetime, "%Y-%m-%d %H:%M")
            year = event_dt.year
        except ValueError:
            pass

    time_series = None
    for candidate in HEADER_ALIASES:
        if candidate in df.columns:
            time_series = df[candidate]
            break
    if time_series is None:
        time_series = df.get(HEADER_KEYWORD, pd.Series([None] * len(df), index=df.index))

    parsed_times: List[Optional[datetime]] = []
    for value in time_series:
        parsed = None
        if isinstance(value, str):
            text = value.strip()
            for fmt in ("%m-%d %H:%M:%S", "%m-%d %H:%M"):
                try:
                    base = datetime.strptime(text, fmt)
                    if year is not None:
                        parsed = base.replace(year=year)
                    else:
                        parsed = base
                    break
                except ValueError:
                    continue
        parsed_times.append(parsed)
    return pd.Series(parsed_times, index=df.index)


def _compute_direction_stats(df: pd.DataFrame, prefix: str, heat_col: str) -> DirectionStats:
    stats = DirectionStats(name=prefix)

    volume_col = f"{prefix}_现成交量"
    action_col = f"{prefix}_方式"

    if volume_col in df.columns and action_col in df.columns:
        for volume, action in zip(df[volume_col], df[action_col]):
            vol = _to_number(volume) or 0.0
            if not vol:
                continue
            if isinstance(action, str) and action.strip() == "卖":
                stats.sell_volume += vol
            else:
                stats.buy_volume += vol

    price_col = f"{prefix}_价位"
    odds_col = f"{prefix}_欧赔"

    if price_col in df.columns:
        stats.latest_price = _to_number(next((v for v in df[price_col] if _to_number(v) is not None), None))
    if stats.latest_price is None and price_col in df.columns:
        stats.latest_price = _to_number(df[price_col].iloc[0])  # type: ignore[index]

    if odds_col in df.columns:
        stats.latest_odds = _to_number(next((v for v in df[odds_col] if _to_number(v) is not None), None))
    if stats.latest_odds is None and odds_col in df.columns:
        stats.latest_odds = _to_number(df[odds_col].iloc[0])  # type: ignore[index]

    if heat_col in df.columns:
        stats.latest_heat = _to_number(next((v for v in df[heat_col] if _to_number(v) is not None), None))
        if stats.latest_heat is None:
            stats.latest_heat = _to_number(df[heat_col].iloc[0])  # type: ignore[index]

    return stats


def _summarise_volume(df: pd.DataFrame) -> Tuple[float, float]:
    total_volume = 0.0
    last_volume = 0.0
    if "总成交量" in df.columns:
        numeric_series = df["总成交量"].map(_to_number)
        total_volume = float(numeric_series.dropna().max() or 0.0)
        last_volume = float(numeric_series.dropna().iloc[0]) if not numeric_series.dropna().empty else 0.0
    return total_volume, last_volume


def _build_risk_notes(direction_stats: List[DirectionStats]) -> List[str]:
    notes: List[str] = []
    for stats in direction_stats:
        if stats.latest_heat is not None and stats.latest_heat < 0:
            notes.append(f"⚠️ {stats.name} 热指为 {stats.latest_heat:.2f}，存在降温迹象")
        if stats.sell_volume > stats.buy_volume and stats.buy_volume > 0:
            notes.append(f"⚠️ {stats.name} 卖出量 {stats.sell_volume:,.0f} 超过买入量 {stats.buy_volume:,.0f}")
    return notes


def _build_suggestion(direction_stats: List[DirectionStats]) -> str:
    if not direction_stats:
        return "暂无建议（缺少有效成交数据）"
    sorted_stats = sorted(direction_stats, key=lambda s: s.net_volume, reverse=True)
    top = sorted_stats[0]
    if top.net_volume <= 0:
        return "暂无明确方向（净流量偏弱）"

    runner_up = sorted_stats[1] if len(sorted_stats) > 1 else None
    if runner_up and (top.net_volume - runner_up.net_volume) / max(abs(top.net_volume), 1) < 0.15:
        return "暂无明确方向（多方净流差距不足）"

    return f"倾向关注 {top.name} 方向（净流量 {top.net_volume:,.0f} ）"


def generate_trade_report(
    df: pd.DataFrame,
    metadata: Optional[List[Dict[str, Optional[str]]]] = None,
) -> Dict[str, str]:
    metadata = metadata or []
    primary_meta = metadata[0] if metadata else {}
    parsed_times = _parse_trade_times(df, primary_meta)
    df = df.copy()
    df["__parsed_time"] = parsed_times

    total_volume, latest_total = _summarise_volume(df)

    direction_mappings = [
        ("主胜", "热指_主"),
        ("和局", "热指_和"),
        ("客胜", "热指_客"),
    ]
    direction_stats = [
        _compute_direction_stats(df, prefix, heat_col)
        for prefix, heat_col in direction_mappings
        if prefix in df.columns or f"{prefix}_现成交量" in df.columns
    ]

    last_time = df["__parsed_time"].dropna().iloc[0] if df["__parsed_time"].dropna().empty is False else None
    last_time_text = last_time.strftime("%Y-%m-%d %H:%M") if isinstance(last_time, datetime) else "未知"

    risk_notes = _build_risk_notes(direction_stats)
    suggestion = _build_suggestion(direction_stats)

    meta_line = ""
    if primary_meta:
        meta_line = " | ".join(
            [
                primary_meta.get("datetime") or "时间未知",
                primary_meta.get("league") or "联赛未知",
                primary_meta.get("home") or "主队未知",
                primary_meta.get("away") or "客队未知",
            ]
        )

    metrics_lines = [
        f"总成交量：{_format_number(total_volume)}",
        f"最新成交记录：{last_time_text}，当时总量 {_format_number(latest_total)}",
    ]
    for stats in direction_stats:
        metrics_lines.append(
            f"{stats.name} 净流量：{_format_number(stats.net_volume)} "
            f"(买入 { _format_number(stats.buy_volume)} / 卖出 {_format_number(stats.sell_volume)}) "
            f"价位：{_format_number(stats.latest_price, 2)} 欧赔：{_format_number(stats.latest_odds, 2)} "
            f"热指：{_format_number(stats.latest_heat, 2)}"
        )

    if not risk_notes:
        risk_notes.append("暂无明显异常。")

    report_lines = ["```VIS"]
    if meta_line:
        report_lines.append(f"【赛事信息】\n{meta_line}")
    report_lines.extend(
        [
            "【快照采集状态】",
            f"成交明细PDF：✅ 已解析 {len(df)} 行（页码 {primary_meta.get('page_number', '-') if primary_meta else '-'}）",
            "【成交指标总览】",
            *metrics_lines,
            "【风险提示】",
            *risk_notes,
            "【🎯 建议】",
            suggestion,
            "```",
        ]
    )

    return {
        "text": "\n".join(report_lines),
        "meta_line": meta_line,
        "risk_count": str(len(risk_notes)),
    }

