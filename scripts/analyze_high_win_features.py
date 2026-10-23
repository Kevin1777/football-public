#!/usr/bin/env python3
"""Analyze historical matches to surface high-win-rate feature patterns."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class MatchRecord:
    """Normalized record containing raw recommendation + actual outcome."""

    match_id: str
    score: str
    actual_result: str  # home_win / draw / away_win
    recommendation_direction: Optional[str]
    recommendation_confidence: Optional[float]
    recommendation_result: Optional[str]
    features: Dict[str, Optional[str]]


def parse_score(score_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse "2-1" / "2 : 1" style score into ints."""

    if not score_str:
        return None

    digits = []
    buf = ""
    for ch in score_str:
        if ch.isdigit():
            buf += ch
        elif buf:
            digits.append(int(buf))
            buf = ""
    if buf:
        digits.append(int(buf))

    if len(digits) >= 2:
        return digits[0], digits[1]
    return None


def actual_result_from_score(score_str: Optional[str]) -> Optional[str]:
    parsed = parse_score(score_str)
    if not parsed:
        return None
    home, away = parsed
    if home > away:
        return "home_win"
    if home < away:
        return "away_win"
    return "draw"


def normalize_recommendation_direction(direction: Optional[str]) -> Optional[str]:
    if not direction:
        return None

    text = direction.strip()
    if not text or "不推荐" in text or text.lower() in {"none", "n/a"}:
        return None

    lowered = text.lower()
    if "draw" in lowered or "平" in text:
        return "draw"

    # Prefer explicit "主" / "客" cues
    if "主" in text and "客" not in text:
        return "home_win"
    if "客" in text and "主" not in text:
        return "away_win"

    # English fallbacks
    if "home" in lowered and "away" not in lowered:
        return "home_win"
    if "away" in lowered and "home" not in lowered:
        return "away_win"

    return None


def extract_features(analysis: Dict) -> Dict[str, Optional[str]]:
    volume = analysis.get("volume_analysis", {}) or {}
    odds = analysis.get("odds_analysis", {}) or {}
    spread = analysis.get("spread_analysis", {}) or {}
    recommendation = analysis.get("recommendation", {}) or {}

    flm = analysis.get("评分等级", {}).get("FLM") if isinstance(analysis.get("评分等级"), dict) else None
    spm = analysis.get("评分等级", {}).get("SPM") if isinstance(analysis.get("评分等级"), dict) else None
    dpi = analysis.get("评分等级", {}).get("DPI") if isinstance(analysis.get("评分等级"), dict) else None

    funding = analysis.get("资金等级", {}) if isinstance(analysis.get("资金等级"), dict) else {}
    risk = analysis.get("风控机制", {}) if isinstance(analysis.get("风控机制"), dict) else {}

    return {
        "dominant_side": volume.get("dominant_side"),
        "market_sentiment": spread.get("market_sentiment"),
        "home_odds_trend": odds.get("home_odds_trend"),
        "away_odds_trend": odds.get("away_odds_trend"),
        "flm_score": flm,
        "spm_score": spm,
        "dpi_score": dpi,
        "funding_level": funding.get("level"),
        "risk_trigger_smart": "ON" if risk.get("SmartSafe") else "OFF" if risk else None,
        "risk_trigger_dagger": "ON" if risk.get("SS-Dagger") else "OFF" if risk else None,
        "risk_trigger_tpi": "ON" if risk.get("TPI") else "OFF" if risk else None,
        "analyzer_direction": recommendation.get("direction"),
        "analyzer_confidence_bucket": bucket_confidence(recommendation.get("confidence")),
    }


def bucket_confidence(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None

    if val >= 0.8:
        return "80%+"
    if val >= 0.65:
        return "65-79%"
    if val >= 0.5:
        return "50-64%"
    return "<50%"


def load_records(db_path: Path) -> List[MatchRecord]:
    query = """
        SELECT m.match_id,
               m.score,
               a.recommendation_direction,
               a.confidence,
               a.analysis_json
        FROM matches m
        JOIN analysis_results a ON m.match_id = a.match_id
        WHERE m.score IS NOT NULL
          AND a.analysis_json IS NOT NULL
    """

    conn = sqlite3.connect(db_path)
    rows = conn.execute(query).fetchall()
    conn.close()

    records: List[MatchRecord] = []
    for match_id, score, rec_direction, confidence, analysis_blob in rows:
        actual = actual_result_from_score(score)
        if not actual:
            continue

        try:
            analysis = json.loads(analysis_blob)
        except json.JSONDecodeError:
            continue

        features = extract_features(analysis)
        normalized_direction = normalize_recommendation_direction(rec_direction)

        record = MatchRecord(
            match_id=match_id,
            score=score,
            actual_result=actual,
            recommendation_direction=rec_direction,
            recommendation_confidence=confidence,
            recommendation_result=normalized_direction,
            features=features,
        )
        records.append(record)

    return records


def compute_feature_stats(
    records: Iterable[MatchRecord],
    feature: str,
    min_samples: int,
) -> List[Dict]:
    groups: Dict[str, Dict] = defaultdict(
        lambda: {
            "count": 0,
            "home_win": 0,
            "draw": 0,
            "away_win": 0,
            "rec_count": 0,
            "rec_hits": 0,
        }
    )

    for record in records:
        value = record.features.get(feature)
        if not value:
            continue

        bucket = groups[value]
        bucket["count"] += 1
        bucket[record.actual_result] += 1
        if record.recommendation_result:
            bucket["rec_count"] += 1
            if record.recommendation_result == record.actual_result:
                bucket["rec_hits"] += 1

    results = []
    for value, stats in groups.items():
        if stats["count"] < min_samples:
            continue
        rec_rate = (stats["rec_hits"] / stats["rec_count"]) * 100 if stats["rec_count"] else None
        results.append(
            {
                "value": value,
                "count": stats["count"],
                "home_win_pct": stats["home_win"] / stats["count"] * 100,
                "draw_pct": stats["draw"] / stats["count"] * 100,
                "away_win_pct": stats["away_win"] / stats["count"] * 100,
                "recommendation_success": rec_rate,
            }
        )

    return sorted(
        results,
        key=lambda item: (
            -item["recommendation_success"] if item["recommendation_success"] is not None else 0,
            -item["count"],
        ),
    )


def compute_combo_stats(
    records: Iterable[MatchRecord],
    features: Sequence[str],
    min_samples: int,
) -> List[Dict]:
    groups: Dict[Tuple[str, ...], Dict] = defaultdict(
        lambda: {
            "count": 0,
            "rec_count": 0,
            "rec_hits": 0,
        }
    )

    for record in records:
        values = []
        skip = False
        for feature in features:
            value = record.features.get(feature)
            if not value:
                skip = True
                break
            values.append(value)
        if skip:
            continue

        key = tuple(values)
        bucket = groups[key]
        bucket["count"] += 1
        if record.recommendation_result:
            bucket["rec_count"] += 1
            if record.recommendation_result == record.actual_result:
                bucket["rec_hits"] += 1

    results = []
    for key, stats in groups.items():
        if stats["count"] < min_samples:
            continue
        rec_rate = (stats["rec_hits"] / stats["rec_count"]) * 100 if stats["rec_count"] else None
        results.append(
            {
                "values": key,
                "count": stats["count"],
                "recommendation_success": rec_rate,
            }
        )

    return sorted(
        results,
        key=lambda item: (
            -item["recommendation_success"] if item["recommendation_success"] is not None else 0,
            -item["count"],
        ),
    )


def analyze_signal_alignment(records: Iterable[MatchRecord]) -> Dict[str, float]:
    total = hits = 0
    for record in records:
        dominant = record.features.get("dominant_side")
        if not dominant:
            continue
        expected = {
            "home": "home_win",
            "away": "away_win",
            "draw": "draw",
        }.get(dominant)
        if not expected:
            continue
        total += 1
        if expected == record.actual_result:
            hits += 1
    return {
        "dominant_sample": total,
        "dominant_hit_rate": (hits / total * 100) if total else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Surface high-win-rate feature patterns from historical matches."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).parent.parent / "match_data.db",
        help="Path to match_data.db",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=5,
        help="Minimum samples required to include a feature bucket",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Top-N entries to print per section",
    )
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    records = load_records(args.db)
    if not records:
        print("No historical analysis records found (matches/analysis_results empty).")
        return

    print(f"Loaded {len(records)} analyzed matches from {args.db}")

    rec_with_prediction = [r for r in records if r.recommendation_result]
    if rec_with_prediction:
        hits = sum(1 for r in rec_with_prediction if r.recommendation_result == r.actual_result)
        print(
            f"Overall recommendation accuracy: {hits}/{len(rec_with_prediction)} = {hits / len(rec_with_prediction) * 100:.2f}%"
        )
    else:
        print("No recommendation directions stored; only feature-outcome stats will be shown.")

    alignment = analyze_signal_alignment(records)
    if alignment["dominant_sample"]:
        print(
            f"成交量主导方向命中率: {alignment['dominant_hit_rate']:.2f}% (n={alignment['dominant_sample']})"
        )

    feature_aliases = {
        "dominant_side": "成交量主导方向",
        "market_sentiment": "买卖盘情绪",
        "home_odds_trend": "主赔率趋势",
        "away_odds_trend": "客赔率趋势",
        "flm_score": "FLM评分",
        "spm_score": "SPM评分",
        "dpi_score": "DPI评分",
        "funding_level": "资金等级",
        "analyzer_confidence_bucket": "分析置信桶",
    }

    for feature, label in feature_aliases.items():
        stats = compute_feature_stats(records, feature, args.min_samples)
        if not stats:
            continue
        print(f"\n[{label}] Top {min(args.top, len(stats))}")
        for item in stats[: args.top]:
            rec_text = (
                f" | 推荐命中: {item['recommendation_success']:.1f}%"
                if item["recommendation_success"] is not None
                else ""
            )
            print(
                f"- {item['value']}: n={item['count']}, "
                f"主胜{item['home_win_pct']:.1f}%, 平{item['draw_pct']:.1f}%, 客胜{item['away_win_pct']:.1f}%{rec_text}"
            )

    combos = [
        ("dominant_side", "market_sentiment"),
        ("flm_score", "spm_score"),
        ("flm_score", "spm_score", "dpi_score"),
    ]

    for combo in combos:
        stats = compute_combo_stats(records, combo, args.min_samples)
        if not stats:
            continue
        label = " + ".join(feature_aliases.get(f, f) for f in combo)
        print(f"\n[{label}] Top {min(args.top, len(stats))}")
        for item in stats[: args.top]:
            rec_text = (
                f"推荐命中 {item['recommendation_success']:.1f}%"
                if item["recommendation_success"] is not None
                else "推荐数据不足"
            )
            print(f"- {' | '.join(item['values'])}: n={item['count']} | {rec_text}")


if __name__ == "__main__":
    main()
