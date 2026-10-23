from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parser.html_parser import parse_bifa_html, parse_match_list
from parser.pdf_parser import parse_bifa_pdf
from services import BifawClient, generate_trade_report


def _format_dataframe(df: pd.DataFrame) -> dict:
    table_html = df.to_html(classes="data", header=True, index=False, justify="left")
    row_count, col_count = df.shape
    csv_text = df.to_csv(index=False)
    metadata = df.attrs.get("metadata", [])
    report_payload = generate_trade_report(df, metadata)
    return {
        "row_count": row_count,
        "col_count": col_count,
        "table_html": table_html,
        "csv_text": csv_text,
        "metadata": metadata,
        "report": report_payload["text"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="自动抓取必发指数标盘明细")
    parser.add_argument(
        "--match",
        required=True,
        help="用于匹配赛事的关键字（可用‘vs’分隔，例如：金浦市民 vs 富川FC）",
    )
    parser.add_argument(
        "--list-url",
        default="https://www.bifaw.com/bifaw/index.php",
        help="标盘列表页 URL，默认使用近期赛事页面。",
    )
    parser.add_argument(
        "--output",
        help="可选：将结果写入指定 JSON 文件。",
    )
    args = parser.parse_args()

    keywords = [part.strip() for part in args.match.replace("VS", "vs").split("vs")]
    keywords = [kw for kw in keywords if kw]
    if not keywords:
        parser.error("无法从 --match 参数中提取关键字，请使用“球队A vs 球队B”格式。")

    client = BifawClient()

    print(f"[INFO] 正在获取列表页：{args.list_url}")
    list_html = client.fetch_dynamic_page_html(args.list_url)
    matches = parse_match_list(list_html, args.list_url)
    target = None
    for entry in matches:
        label = entry.get("label") or ""
        if all(keyword in label for keyword in keywords):
            target = entry
            break

    if not target:
        raise SystemExit(f"[ERROR] 未找到包含关键字 {keywords} 的标盘明细链接。")

    detail_href = target["detail_url"]
    print(f"[INFO] 匹配成功，明细链接：{detail_href}")
    response = client.fetch_match_detail_response(detail_url=detail_href)
    content_type = (response.headers.get("Content-Type") or "").lower()

    if "pdf" in content_type or detail_href.lower().endswith(".pdf"):
        tmp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = Path(tmp_file.name)
            df_or_error = parse_bifa_pdf(str(tmp_path))
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    else:
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        df_or_error = parse_bifa_html(response.text)
    if isinstance(df_or_error, str):
        raise SystemExit(f"[ERROR] 解析失败：{df_or_error}")

    if df_or_error.empty:
        raise SystemExit("[ERROR] 解析结果为空。")

    payload = _format_dataframe(df_or_error)
    print(f"[INFO] 成功解析 {payload['row_count']} 行 × {payload['col_count']} 列数据。")

    print(json.dumps(payload["metadata"], ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[INFO] 结果已写入：{args.output}")

    else:
        print("[INFO] CSV 前 3 行示例：")
        csv_lines = payload["csv_text"].splitlines()
        for line in csv_lines[:4]:
            print(line)


if __name__ == "__main__":
    main()

