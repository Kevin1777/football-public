from __future__ import annotations

import itertools
import json
import re
import unicodedata
import warnings
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

import pandas as pd
import pdfplumber
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover - 兼容旧 Python
    pass

# 默认使用基于线条的表格检测，可适配类似必发指数网的复杂网格
DEFAULT_TABLE_SETTINGS: Dict[str, Union[str, float, bool]] = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}

HEADER_KEYWORD = "成交时间"
HEADER_ALIASES: Tuple[str, ...] = (
    HEADER_KEYWORD,
    "买家挂牌",
    "买家挂牌(元)",
    "买家挂牌价",
    "最新成交",
    "挂买总量",      # matchDetails.php页面使用的列名
    "挂卖总量",      # matchDetails.php页面使用的列名
    "已成交总量",    # matchDetails.php页面使用的列名
    "总成交量",      # matchDetails.php页面使用的列名
    "即时成交",      # matchDetails.php页面使用的列名
)
NOTE_KEYWORDS = ("备注", "温馨提醒")
METADATA_DELIMITER = " "

# 示例 PDF，便于直接运行脚本自测
PDF_FILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "墨西联,华雷斯[春9],普埃布拉[春18],标盘明细_必发指数网.pdf"
)


def normalize_cell(cell: Optional[str]) -> Optional[str]:
    """将单元格内容做 Unicode 规范化、去除换行及多余空白。"""
    if cell is None:
        return None
    text = unicodedata.normalize("NFKC", str(cell))
    text = text.replace("\n", " ").strip()
    return text or None


def _normalize_header_alias(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    # 只归一化真正的时间列别名，不归一化其他列
    time_aliases = (HEADER_KEYWORD, "买家挂牌", "买家挂牌(元)", "买家挂牌价", "最新成交")
    for alias in time_aliases:
        if alias in value:
            return HEADER_KEYWORD
    return value


def build_column_names(
    level1: Sequence[Optional[str]],
    level2: Sequence[Optional[str]],
) -> List[str]:
    """根据两行表头生成唯一的列名。"""
    names: List[str] = []
    seen: Dict[str, int] = {}
    last_level1: Optional[str] = None
    last_level2: Optional[str] = None

    for top, bottom in itertools.zip_longest(level1, level2, fillvalue=None):
        top = normalize_cell(top) or last_level1
        bottom = normalize_cell(bottom) or last_level2

        if top:
            last_level1 = top
        if bottom:
            last_level2 = bottom

        top_norm = _normalize_header_alias(top)
        bottom_norm = _normalize_header_alias(bottom)

        if top and bottom:
            if top_norm == bottom_norm:
                base = top_norm or top or bottom
            elif top_norm == HEADER_KEYWORD and bottom_norm == HEADER_KEYWORD:
                base = HEADER_KEYWORD
            else:
                base = f"{top_norm or top}_{bottom_norm or bottom}"
        else:
            base = top or bottom or "列"

        base = base.replace(" ", "")
        index = seen.get(base, 0)
        if index:
            name = f"{base}_{index + 1}"
        else:
            name = base
        seen[base] = index + 1
        names.append(name)

    return names


def _parse_title(raw_title: Optional[str]) -> Dict[str, Optional[str]]:
    if not raw_title:
        return {"league": None, "datetime": None, "home": None, "away": None}

    text = unicodedata.normalize("NFKC", raw_title)
    text = text.replace("ＶＳ", "VS").replace(" vs ", " VS ").replace(" Vs ", " VS ")
    text = text.replace("：", ":")

    league = None
    datetime_part = None
    home_part = None
    away_part = None

    match = re.search(
        r"^\s*(?P<league>\S+).*?开赛时间:(?P<datetime>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(?P<home>\S+)\s+VS\s+(?P<away>\S+)",
        text,
    )
    if match:
        league = match.group("league")
        datetime_part = match.group("datetime").strip()
        home_part = match.group("home")
        away_part = match.group("away")
    else:
        parts = [part for part in text.split(METADATA_DELIMITER) if part]
        league = parts[0] if parts else None

        if "VS" in text:
            left, _, right = text.partition("VS")
            left = left.strip()
            right = right.strip()

            if "时间:" in left:
                datetime_part = left.split("时间:", 1)[-1].strip()

            if left:
                home_part = left.split()[-1]
            if right:
                away_part = right.split()[0]

    return {
        "league": league,
        "datetime": datetime_part,
        "home": home_part,
        "away": away_part,
    }


def locate_header(
    rows: Sequence[Sequence[Optional[str]]],
) -> Tuple[Optional[int], int]:
    """查找包含“成交时间”的表头行及其起始列索引。"""

    def matches_header(value: Optional[str]) -> bool:
        if not value:
            return False
        return any(alias in value for alias in HEADER_ALIASES)

    def find_header_col(cells: Sequence[Optional[str]]) -> Optional[int]:
        for col_idx, value in enumerate(cells):
            if matches_header(value):
                return col_idx
        return None

    for idx in range(len(rows) - 1):
        first = rows[idx]
        second = rows[idx + 1]
        if not first or not second:
            continue

        col = find_header_col(first)
        if col is None:
            col = find_header_col(second)
            if col is not None:
                return idx + 1, col
        else:
            return idx, col

    return None, 0


def extract_section(table: Sequence[Sequence[Optional[str]]]) -> Optional[Dict]:
    """从单个 table 结果中解析出结构化数据。"""
    normalized_rows: List[List[Optional[str]]] = [
        [normalize_cell(cell) for cell in row] for row in table
    ]
    normalized_rows = [
        row for row in normalized_rows if any(cell is not None for cell in row)
    ]
    if not normalized_rows:
        return None

    header_index, header_col = locate_header(normalized_rows)
    
    # 如果找不到表头，但表格有大量数据行，自动处理
    if header_index is None:
        # 检查第一行是否像数据行（包含时间格式或数字）
        import re
        first_row_text = " ".join(str(c) for c in normalized_rows[0] if c)
        has_time = bool(re.search(r"\d{2}-\d{2}\s+\d{2}:\d{2}", first_row_text))
        # 检查是否包含数字（可能是赔率、成交量等）
        has_numbers = bool(re.search(r"\d+\.\d+|\d{3,}", first_row_text))
        
        # 放宽条件：有时间或有数字数据且行数足够
        if (has_time or has_numbers) and len(normalized_rows) >= 5:
            # 这是一个纯数据表格（表头在别处）
            # 使用预定义的标准列名，而不是自动生成
            header_index = -1  # 标记为无表头
            header_col = 0
            # 使用标准列名顺序（与必发指数网的标准表头一致）
            # 44列完整表头：成交时间、总成交量、主胜(5列)、和局(5列)、客胜(5列)、
            # 比例(3列)、赔付率(3列)、必指(3列)、赔指(3列)、赢亏(3列)、赔付(3列)、凯利(3列)、凯差(3列)、热指(3列)
            standard_columns = [
                "成交时间", "总成交量",
                # 主胜 (5列)
                "主胜_欧赔", "主胜_价位", "主胜_已成交量", "主胜_现成交量", "主胜_方式",
                # 和局 (5列)
                "和局_欧赔", "和局_价位", "和局_已成交量", "和局_现成交量", "和局_方式",
                # 客胜 (5列)
                "客胜_欧赔", "客胜_价位", "客胜_已成交量", "客胜_现成交量", "客胜_方式",
                # 比例 (3列)
                "比例_主", "比例_和", "比例_客",
                # 赔付率 (3列)
                "赔付率_主", "赔付率_和", "赔付率_客",
                # 必指 (3列)
                "必指_主", "必指_和", "必指_客",
                # 赔指 (3列)
                "赔指_主", "赔指_和", "赔指_客",
                # 赢亏 (3列)
                "赢亏_主", "赢亏_和", "赢亏_客",
                # 赔付 (3列)
                "赔付_主", "赔付_和", "赔付_客",
                # 凯利 (3列)
                "凯利_主", "凯利_和", "凯利_客",
                # 凯差 (3列)
                "凯差_主", "凯差_和", "凯差_客",
                # 热指 (3列)
                "热指_主", "热指_和", "热指_客",
            ]
            max_cols = max(len(row) for row in normalized_rows)
            # 如果列数多于标准列名，补充额外列
            if max_cols > len(standard_columns):
                column_names = standard_columns + [f"额外列{i-len(standard_columns)+1}" for i in range(len(standard_columns), max_cols)]
            else:
                column_names = standard_columns[:max_cols]
        else:
            return None
    elif header_index + 1 >= len(normalized_rows):
        return None

    def slice_from_col(row: Sequence[Optional[str]]) -> List[Optional[str]]:
        return list(row[header_col:]) if header_col < len(row) else []

    # 如果header_index == -1，说明是无表头的纯数据表格
    if header_index == -1:
        # 已经在上面生成了column_names
        data_start_index = 0  # 从第一行开始就是数据
    else:
        header_level1 = slice_from_col(normalized_rows[header_index])
        
        # 检查第二行是否真的是表头，还是数据行
        import re
        if header_index + 1 < len(normalized_rows):
            header_level2 = slice_from_col(normalized_rows[header_index + 1])
            # 检查第二行是否包含时间格式（如果有，说明是数据行）
            second_row_text = " ".join(str(c) for c in header_level2 if c)
            is_data_row = bool(re.search(r"\d{2}-\d{2}\s+\d{2}:\d{2}", second_row_text))
            
            # 🔥 进一步检查：如果第二行包含大量数字（但不是关键字），很可能是数据行
            if not is_data_row:
                # 检查是否有超过一半的单元格是纯数字或带逗号的数字
                numeric_cells = 0
                non_empty_cells = 0
                for cell in header_level2:
                    if cell and cell.strip():
                        non_empty_cells += 1
                        # 检查是否是数字（可能带逗号、小数点）
                        cleaned = str(cell).replace(',', '').replace('.', '').strip()
                        if cleaned.isdigit() or (len(cleaned) > 0 and cleaned.replace('-', '').isdigit()):
                            numeric_cells += 1
                
                # 如果超过50%的单元格是数字，且不是关键字，可能是数据行
                if non_empty_cells > 0 and numeric_cells / non_empty_cells > 0.5:
                    # 再检查是否包含关键字（表头通常包含关键字）
                    has_header_keyword = any(
                        any(alias in str(cell) for alias in HEADER_ALIASES)
                        for cell in header_level2 if cell
                    )
                    if not has_header_keyword:
                        is_data_row = True
                        print(f"[表头识别] 第二行包含大量数字({numeric_cells}/{non_empty_cells})且无关键字，判定为数据行")
            
            if is_data_row:
                # 第二行是数据行，不是表头！只使用一级表头
                column_names = [normalize_cell(c) or f"列{i+1}" for i, c in enumerate(header_level1)]
                # 修正数据起始位置
                data_start_index = header_index + 1  # 从第二行开始就是数据
                print(f"[表头识别] 只使用一级表头，从第{header_index + 1}行开始是数据")
            else:
                # 第二行是表头的第二级，使用两级表头
                column_names = build_column_names(header_level1, header_level2)
                data_start_index = header_index + 2  # 从第三行开始是数据
                print(f"[表头识别] 使用两级表头，从第{header_index + 2}行开始是数据")
        else:
            # 只有一行表头
            column_names = [normalize_cell(c) or f"列{i+1}" for i, c in enumerate(header_level1)]
            data_start_index = header_index + 1

    title_cell = (
        normalized_rows[0][header_col]
        if normalized_rows and header_col < len(normalized_rows[0])
        else None
    )
    subtitle_cell = (
        normalized_rows[1][header_col]
        if len(normalized_rows) > 1 and header_col < len(normalized_rows[1])
        else None
    )
    title = title_cell
    subtitle = (
        subtitle_cell
        if isinstance(subtitle_cell, str) or subtitle_cell is None
        else None
    )
    title_meta = _parse_title(title)
    if title and HEADER_KEYWORD in title:
        title = None
    if subtitle and HEADER_KEYWORD in subtitle:
        subtitle = None

    notes: List[str] = []
    data_rows: List[Dict[str, Optional[str]]] = []

    # data_start_index已在上面根据表头情况确定
    for original_row in normalized_rows[data_start_index:]:
        row = slice_from_col(original_row)
        if all(value is None for value in row):
            continue
        first_cell = row[0] if row else None
        if first_cell and any(keyword in first_cell for keyword in NOTE_KEYWORDS):
            notes.append(" ".join(cell for cell in row if cell))
            continue

        row_dict: Dict[str, Optional[str]] = {}
        for column_name, value in itertools.zip_longest(
            column_names, row, fillvalue=None
        ):
            row_dict[column_name] = value
        data_rows.append(row_dict)

    if not data_rows:
        print(f"[extract_section] 数据行为空: total_rows={len(normalized_rows)}, data_start={data_start_index}, header_idx={header_index}")
        # 输出前3行样本用于调试
        for i, row in enumerate(normalized_rows[:3]):
            print(f"  Row {i}: {row[:5]}")
        return None

    return {
        "title": title,
        "title_meta": title_meta,
        "subtitle": subtitle,
        "columns": column_names,
        "rows": data_rows,
        "notes": notes,
    }


def iter_sections(
    pdf_path: Union[str, Path],
    table_settings: Optional[Dict[str, Union[str, float, bool]]] = None,
    page_number: Optional[int] = None,
) -> Iterator[Dict]:
    """遍历 PDF 中的所有有效表格区域。"""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(path)

    settings = dict(DEFAULT_TABLE_SETTINGS)
    if table_settings:
        settings.update(table_settings)

    with pdfplumber.open(str(path)) as pdf:
        if page_number is not None:
            indices = [page_number]
        else:
            indices = range(len(pdf.pages))

        for idx in indices:
            if idx < 0 or idx >= len(pdf.pages):
                raise IndexError(f"页码 {idx} 超出范围 0-{len(pdf.pages) - 1}")

            page = pdf.pages[idx]
            tables = page.extract_tables(settings)
            for table_index, table in enumerate(tables):
                section = extract_section(table)
                if not section:
                    continue
                section["page_number"] = idx + 1  # 习惯从 1 开始
                section["table_index"] = table_index
                yield section


def parse_bifa_pdf(
    pdf_path: Union[str, Path],
    page_number: Optional[int] = None,
    drop_unclassified: bool = True,  # 兼容旧参数，保留但不再使用
    drop_all_na_columns: bool = True,
    table_settings: Optional[Dict[str, Union[str, float, bool]]] = None,
) -> Union[pd.DataFrame, str]:
    """
    解析必发指数类 PDF，返回结构化 DataFrame。

    Args:
        pdf_path: PDF 文件路径
        page_number: 指定页码（默认 None 表示解析全部页面）
        drop_unclassified: 保留旧参数以兼容历史调用（已无实际作用）
        drop_all_na_columns: 是否删除全为空的列
        table_settings: 覆盖默认 table_settings 的自定义配置
    """
    if not drop_unclassified:
        warnings.warn(
            "drop_unclassified 参数已废弃，现有解析逻辑不再产生『未归类』列。",
            UserWarning,
        )

    try:
        sections = list(
            iter_sections(
                pdf_path,
                table_settings=table_settings,
                page_number=page_number,
            )
        )
    except FileNotFoundError:
        return f"解析失败：未找到文件 {pdf_path}"
    except IndexError as exc:
        return f"解析失败：{exc}"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"解析失败：{exc}"

    if not sections:
        return "解析失败：未在 PDF 中识别到符合结构的表格。"

    rows: List[Dict[str, Optional[str]]] = []
    notes: List[str] = []
    metadata: List[Dict[str, Optional[str]]] = []
    for section in sections:
        metadata.append(
            {
                "page_number": section.get("page_number"),
                "table_index": section.get("table_index"),
                "title": section.get("title"),
                "subtitle": section.get("subtitle"),
                "title_meta": section.get("title_meta"),
            }
        )
        for row in section["rows"]:
            rows.append(dict(row))
        notes.extend(section.get("notes", []))

    if not rows:
        return "解析失败：识别到表格，但未抽取到有效数据行。"

    df = pd.DataFrame(rows).replace("", pd.NA)
    df = _merge_duplicate_columns(df)
    if drop_all_na_columns:
        df = df.dropna(axis=1, how="all")

    df.attrs["sections"] = sections
    if notes:
        df.attrs["notes"] = notes
    if metadata:
        df.attrs["metadata"] = metadata

    return df


def _print_preview(df: pd.DataFrame, limit: int = 3) -> None:
    preview_df = df.fillna("")
    for idx, row in enumerate(preview_df.head(limit).to_dict(orient="records"), start=1):
        print(f"\n--- 第 {idx} 行 ---")
        print(json.dumps(row, ensure_ascii=False, indent=2))


def _merge_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """合并带有 _2/_3 等后缀的重复列，优先使用最左侧非空值。"""
    duplicates: Dict[str, List[str]] = {}
    for column in list(df.columns):
        if "_" not in column:
            continue
        base, suffix = column.rsplit("_", 1)
        if suffix.isdigit() and base in df.columns:
            duplicates.setdefault(base, []).append(column)

    for base, extras in duplicates.items():
        ordered = [base] + sorted(
            extras, key=lambda name: int(name.rsplit("_", 1)[1])
        )
        merged = df[ordered].bfill(axis=1).iloc[:, 0]
        df[base] = merged
        df = df.drop(columns=extras)

    return df


if __name__ == "__main__":
    print("--- 开始运行主解析器 ---")
    result = parse_bifa_pdf(PDF_FILE_PATH)

    if isinstance(result, pd.DataFrame):
        if result.empty:
            print("[失败] 解析结果为空。")
        else:
            print(f"[成功] 成功解析到 {len(result)} 行数据。")
            _print_preview(result, limit=3)

            if result.attrs.get("notes"):
                print("\n--- 备注 ---")
                for note in result.attrs["notes"]:
                    print(note)
    else:
        print(f"[失败] {result}")
