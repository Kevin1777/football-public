"""Run actual core modules on invented inputs without the web app or network.

Usage: python -m examples.offline_demo --output demo-output
"""

import argparse
from html import escape
import json
from pathlib import Path

from recommendation.feature_extractor import FeatureExtractor
from recommendation.result_validator import ResultValidator
from recommendation.scoring_model import SignalScoringModel
from recommendation.threshold_filter import DynamicThresholdFilter

DEFAULT_INPUT = Path(__file__).with_name("matches.synthetic.json")
REPORT_TEMPLATE = Path(__file__).with_name("report.html")


def build_report(fixture_path=DEFAULT_INPUT):
    """Extract, score, filter, and settle each synthetic fixture independently.

    Direction and final scores are fixture inputs, never model predictions.
    Settlement intentionally includes filtered cases to cover every result type.
    """
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True:
        raise ValueError("This demo accepts explicitly synthetic fixtures only")
    extractor = FeatureExtractor()
    model = SignalScoringModel()
    filters = DynamicThresholdFilter()
    validator = ResultValidator()
    cases = []
    for match in fixture["matches"]:
        metrics = extractor.extract_metrics({
            "match_info": {"home": match["home"], "away": match["away"], "league": "Synthetic"},
            "handicap_data": {"current_handicap": match["handicap"]},
            "trade_data": {"data": [{
                "总成交量": match["volume"], "比例_主": 50, "比例_和": 20, "比例_客": 30,
                "必指_主": 42, "必指_客": 35, "凯利_主": 93, "凯利_客": 96,
                "热指_主": match["hot_home"], "热指_客": match["hot_away"],
            }]},
        })
        home_score, home_signals = model.calculate_score(metrics, "home", match["handicap"])
        away_score, away_signals = model.calculate_score(metrics, "away", match["handicap"])
        eligible, reason = filters.should_recommend(metrics, home_score, away_score, match["direction"])
        settlement = validator.validate({"direction": match["direction"]}, tuple(match["score"]), match["handicap"])
        cases.append({
            "id": match["id"], "home": match["home"], "away": match["away"],
            "fixture_direction": match["direction"], "home_handicap": match["handicap"],
            "actual_score": match["score"], "metrics": metrics,
            "scores": {"home": home_score, "away": away_score},
            "signals": {"home": home_signals, "away": away_signals},
            "filter": {"eligible": eligible, "reason": reason}, "settlement": settlement,
        })
    return {
        "synthetic": True,
        "scope": "Core-module demonstration only. Fixture directions are predetermined; no live collection or notifications.",
        "cases": cases,
        "outcomes": {name: sum(c["settlement"]["result"] == name for c in cases)
                     for name in ("win", "half_win", "draw", "half_lose", "lose")},
    }


def render_report(report):
    rows = []
    for case in report["cases"]:
        result = case["settlement"]["result"]
        cells = [
            escape(case["id"]),
            f'<strong>{escape(case["home"])}</strong><span class="versus">vs {escape(case["away"])}</span>',
            escape(case["fixture_direction"]), f'{case["home_handicap"]:+g}',
            f'{case["scores"]["home"]:g} / {case["scores"]["away"]:g}',
            f'<span class="pill {"pass" if case["filter"]["eligible"] else "hold"}">{"PASS" if case["filter"]["eligible"] else "HOLD"}</span>',
            f'{case["actual_score"][0]} : {case["actual_score"][1]}',
            f'<span class="outcome {result}">{escape(result.replace("_", " "))}</span>',
        ]
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    return (REPORT_TEMPLATE.read_text(encoding="utf-8")
            .replace("<!--CASE_ROWS-->", "\n".join(rows))
            .replace("<!--CASE_COUNT-->", str(len(report["cases"]))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("demo-output"))
    args = parser.parse_args(argv)
    report = build_report()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "index.html").write_text(render_report(report), encoding="utf-8")
    print(f'Synthetic demo: {len(report["cases"])} cases; outcomes={report["outcomes"]}')
    print(f"Report: {(args.output / 'index.html').resolve()}")
    print("No network requests, credentials, browser automation, or notifications were used.")


if __name__ == "__main__":
    main()
