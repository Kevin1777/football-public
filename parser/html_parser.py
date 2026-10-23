from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

from .pdf_parser import (
    HEADER_ALIASES,
    HEADER_KEYWORD,
    _merge_duplicate_columns,
    extract_section,
    normalize_cell,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG_DIR = BASE_DIR / "debug_html"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_TABLE_PATH = DEBUG_DIR / "latest_table.json"

HEADER_KEYWORDS = HEADER_ALIASES
TIME_CELL_PATTERN = re.compile(r"\d{2}-\d{2}\s+\d{2}:\d{2}")
NOISE_ROW_KEYWORDS: Tuple[str, ...] = (
    "标盘交易历史/现有订单",
    "标盘明细",
    "最新交易:",
    "独家走势",
    "盘口说明",
    "点击刷新数据",
)


def _dump_debug_matrix(matrix: List[List[Optional[str]]], *, label: str) -> None:
    try:
        payload = {
            "label": label,
            "rows": matrix[:10],
            "row_lengths": [len(row) for row in matrix[:10]],
        }
        DEBUG_TABLE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _table_to_matrix(table: Tag, *, label: str = "") -> List[List[Optional[str]]]:
    """
    将 HTML 表格转换为二维数组，同时展开 rowspan/colspan。

    通过手动处理跨行 / 跨列表头，兼容缺少 lxml 依赖的运行环境。
    """

    rows: List[List[Optional[str]]] = []
    spans: Dict[int, Tuple[Optional[str], int]] = {}

    def _parse_span(value: Optional[str], default: int) -> int:
        if not value:
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells and not spans:
            continue

        row: List[Optional[str]] = []
        col = 0

        while True:
            span = spans.get(col)
            if not span:
                break
            value, remain = span
            row.append(value)
            if remain > 1:
                spans[col] = (value, remain - 1)
            else:
                spans.pop(col)
            col += 1

        for cell in cells:
            while True:
                span = spans.get(col)
                if not span:
                    break
                value, remain = span
                row.append(value)
                if remain > 1:
                    spans[col] = (value, remain - 1)
                else:
                    spans.pop(col)
                col += 1

            text = normalize_cell(cell.get_text(" ", strip=True))
            colspan = _parse_span(cell.get("colspan"), 1)
            rowspan = _parse_span(cell.get("rowspan"), 1)

            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    spans[col] = (text, rowspan - 1)
                else:
                    spans.pop(col, None)
                col += 1

        if any(value is not None for value in row):
            rows.append(row)

    filtered_rows: List[List[Optional[str]]] = []
    for row in rows:
        joined = " ".join(cell or "" for cell in row).strip()
        if not joined:
            continue
        if any(keyword in joined for keyword in NOISE_ROW_KEYWORDS):
            continue
        filtered_rows.append(row)

    debug_label = label or table.get("id") or "unknown_table"
    _dump_debug_matrix(filtered_rows, label=debug_label)
    return filtered_rows


def _find_parent_with_tag(element: Tag, tag_names: Iterable[str]) -> Optional[Tag]:
    tag_names = {name.lower() for name in tag_names}
    current: Optional[Tag] = element
    while current is not None:
        if getattr(current, "name", "").lower() in tag_names:
            return current
        current = current.parent  # type: ignore[assignment]
    return None


def _find_candidate_tables(html: str) -> List[List[List[Optional[str]]]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: List[List[List[Optional[str]]]] = []
    for table in soup.find_all("table"):
        table_label = table.get("id") or table.get("class", [""])[0] or "table"
        matrix = _table_to_matrix(table, label=table_label)
        if not matrix:
            continue
        content = " ".join(cell or "" for row in matrix for cell in row)
        
        # 计算时间格式单元格数量
        time_hits = sum(
            1
            for row in matrix
            for cell in row
            if cell and TIME_CELL_PATTERN.search(cell)
        )
        
        # 检查是否包含关键字
        has_keyword = any(keyword in content for keyword in HEADER_KEYWORDS)
        keyword_count = sum(1 for kw in HEADER_KEYWORDS if kw in content)
        
        # 🔥 检查前2-3行是否是表头（不含时间格式）
        header_rows_count = 0
        for idx, row in enumerate(matrix[:3]):
            row_text = " ".join(cell or "" for cell in row)
            has_time_in_row = bool(TIME_CELL_PATTERN.search(row_text))
            has_keyword_in_row = any(kw in row_text for kw in HEADER_KEYWORDS)
            # 如果有关键字且没有时间，可能是表头
            if has_keyword_in_row and not has_time_in_row:
                header_rows_count += 1
            else:
                break  # 遇到数据行就停止
        
        # 接受表格的条件（满足任一即可）：
        # 1. 包含关键字 + 至少1个时间
        # 2. 包含关键字 + 至少5行
        # 3. 包含多个关键字（>=2个）且行数少（<=3行）- 可能是表头
        # 4. 包含多个关键字（>=3个）
        # 5. 有大量时间单元格（>=10个），即使没有关键字（说明是数据表）
        accept = False
        reason = ""
        
        if has_keyword and time_hits >= 1:
            accept = True
            reason = f"有关键字+时间"
        elif has_keyword and len(matrix) >= 5:
            accept = True
            reason = f"有关键字+多行"
        elif keyword_count >= 2 and len(matrix) <= 3 and time_hits == 0:  # 新增：表头识别
            accept = True
            reason = f"表头(关键字+少行)"
        elif keyword_count >= 3:
            accept = True
            reason = f"多个关键字"
        elif time_hits >= 10:  # 大量时间数据说明是数据表
            accept = True
            reason = f"大量时间数据"
        
        if accept:
            candidates.append(matrix)
            print(f"[表格识别] {table_label}: {len(matrix)}行, {time_hits}个时间, {keyword_count}个关键字, {header_rows_count}行表头 ({reason})")
    
    return candidates


def _extract_title_from_html(html: str) -> Dict[str, Optional[str]]:
    """从HTML中提取比赛标题信息和总交易额"""
    soup = BeautifulSoup(html, "html.parser")
    
    result = {
        "league": None,
        "datetime": None,
        "home": None,
        "away": None,
        "total_volume": None  # 🔥 新增：总交易额
    }
    
    # 🔥 提取总交易额（从页面中查找）
    # 格式1: "总交易额：123,456" 或 "总成交量：123,456"
    # 格式2: 在某个div或span中显示
    try:
        import re
        # 方法1：直接文本搜索
        volume_patterns = [
            r'总交易额[：:]​s*([\d,]+)',
            r'总成交量[：:]​s*([\d,]+)',
            r'成交总额[：:]​s*([\d,]+)',
            r'交易总额[：:]​s*([\d,]+)',
        ]
        for pattern in volume_patterns:
            match = re.search(pattern, html)
            if match:
                volume_str = match.group(1).replace(',', '')
                try:
                    result["total_volume"] = float(volume_str)
                    print(f"[总交易额] 提取成功: {result['total_volume']:,.0f}")
                    break
                except:
                    pass
    except Exception as e:
        print(f"[总交易额] 提取失败: {e}")
    
    # 优先从div.teammsg提取比赛信息
    teammsg_div = soup.find('div', class_='teammsg')
    if teammsg_div:
        text = teammsg_div.get_text(strip=True)
        # 格式: "国际友谊开赛时间:2025-11-18 00:30卡塔尔[52]VS津巴布韦[129]比分标盘明细"
        import re
        # 提取联赛名称
        league_match = re.match(r'^([^开赛时间]+)', text)
        result["league"] = league_match.group(1) if league_match else None
        
        # 提取时间
        time_match = re.search(r'开赛时间[：:]​s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', text)
        result["datetime"] = time_match.group(1) if time_match else None
        
        # 提取主客队
        vs_match = re.search(r'(\d{2}:\d{2})(.*?)VS(.*?)(?:比分|标盘)', text)
        if vs_match:
            result["home"] = vs_match.group(2).strip()
            result["away"] = vs_match.group(3).strip()
        
        return result
    
    # 备选：从<title>提取
    title_tag = soup.find('title')
    if title_tag:
        text = title_tag.get_text(strip=True)
        # 格式: "国际友谊,卡塔尔[52],津巴布韦[129],标盘明细_必发指数网"
        parts = text.replace('_必发指数网', '').split(',')
        if len(parts) >= 3:
            result["league"] = parts[0]
            result["home"] = parts[1]
            result["away"] = parts[2].replace('标盘明细', '').strip()
    
    return result


def parse_bifa_html(html: str, match: Optional[Dict[str, object]] = None) -> Union[pd.DataFrame, str]:
    """
    解析必发指数网页中的标盘明细表格。

    Args:
        html: 已登录后的页面 HTML
        match: 可选的比赛信息字典，如果提供则优先使用

    Returns:
        pandas.DataFrame 或错误信息字符串
    """
    # 提取页面标题信息，如果提供了match参数则优先使用
    if match:
        page_title_meta = {
            "league": match.get("league"),
            "datetime": match.get("kickoff"),
            "home": match.get("home"),
            "away": match.get("away")
        }
    else:
        page_title_meta = _extract_title_from_html(html)
    
    candidates = _find_candidate_tables(html)
    if not candidates:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = DEBUG_DIR / f"no_table_{timestamp}.html"
        try:
            debug_file.write_text(html, encoding="utf-8", errors="ignore")
        except Exception:
            pass
        keywords_hint = "、".join(HEADER_KEYWORDS)
        return f"解析失败：页面中未找到包含关键字（{keywords_hint}）的表格。"

    # 尝试查找表头表格和数据表格
    header_matrix = None
    data_matrix = None
    
    for matrix in candidates:
        content = " ".join(cell or "" for row in matrix for cell in row)
        has_keyword = any(keyword in content for keyword in HEADER_KEYWORDS)
        
        # 检查是否包含时间格式
        time_count = sum(
            1 for row in matrix for cell in row 
            if cell and TIME_CELL_PATTERN.search(cell)
        )
        
        # 🔥 检查前几行是否是纯表头（无时间、有关键字）
        header_rows = []
        data_start_idx = 0
        for idx, row in enumerate(matrix):
            row_text = " ".join(cell or "" for cell in row)
            has_time = bool(TIME_CELL_PATTERN.search(row_text))
            has_kw = any(kw in row_text for kw in HEADER_KEYWORDS)
            # 如果有关键字且没有时间，是表头行
            if has_kw and not has_time:
                header_rows.append(row)
                data_start_idx = idx + 1
            elif has_time:
                # 遇到第一个有时间的行，停止
                break
        
        # 如果有关键字且行数少，可能是表头表格
        if has_keyword and len(matrix) <= 3 and time_count == 0:
            if not header_matrix or len(matrix) > len(header_matrix):
                header_matrix = matrix
                print(f"[表头识别] 找到独立表头表格：{len(matrix)}行")
        # 如果有大量时间数据或行数足够，可能是数据表
        elif time_count >= 10 or (len(matrix) >= 10 and not has_keyword):
            data_matrix = matrix
            print(f"[数据识别] 找到数据表格：{len(matrix)}行，{time_count}个时间")
    
    # 🔥🔥🔥 支持多页：识别所有数据表格并合并 🔥🔥🔥
    complete_tables = []  # 存储所有完整的数据表格
    
    # 先按行数排序，优先处理最大的表格（很可能是主数据表格）
    candidates_sorted = sorted(candidates, key=lambda m: len(m), reverse=True)
    
    print(f"[表格排序] 按行数排序后，前3个表格行数：{[len(m) for m in candidates_sorted[:3]]}")
    
    for matrix in candidates_sorted:
        # 检查是否是完整表格（前几行是表头，后面是数据）
        has_header_rows = 0
        data_start_row = 0
        
        # 从前面开始逐行检查，找到第一个数据行
        for idx, row in enumerate(matrix):
            row_text = " ".join(cell or "" for cell in row)
            has_time = bool(TIME_CELL_PATTERN.search(row_text))
            has_kw = any(kw in row_text for kw in HEADER_KEYWORDS)
            
            # 如果有关键字且没有时间，是表头行
            if has_kw and not has_time:
                has_header_rows += 1
            elif has_time:
                # 找到第一个有时间的行，后面都是数据
                data_start_row = idx
                break
        
        # 检查数据行数量
        has_data_rows = 0
        # 🔥 修复：即使data_start_row=0（无表头），也要统计数据行
        start_from = data_start_row if data_start_row > 0 else 0
        for row in matrix[start_from:]:
            row_text = " ".join(cell or "" for cell in row)
            if TIME_CELL_PATTERN.search(row_text):
                has_data_rows += 1
        
        # 如果有表头又有足够的数据行，这是完整表格
        if has_header_rows >= 1 and has_data_rows >= 5:
            print(f"[完整表格] 找到包含表头({has_header_rows}行)+数据({has_data_rows}行)的完整表格，总共{len(matrix)}行")
            section = extract_section(matrix)
            if section:
                complete_tables.append(section)
                # 🔥 不break，继续查找其他表格（多页场景）
        # 🔥 放宽条件：即使没有明显表头，但有大量数据行（>20行），也认为是数据表格
        elif has_data_rows >= 20:
            print(f"[完整表格] 找到大型数据表格（{has_data_rows}行数据），判定为数据表格")
            section = extract_section(matrix)
            if section:
                complete_tables.append(section)
                # 🔥 不break，继续查找
    
    # 如果找到了多个完整表格，合并它们
    if len(complete_tables) > 1:
        print(f"[多表格合并] 找到 {len(complete_tables)} 个数据表格，准备合并")
        sections = complete_tables
    elif len(complete_tables) == 1:
        print(f"[单表格] 找到 1 个完整表格")
        sections = complete_tables
    else:
        # 没有找到完整表格，尝试其他方法
        print(f"[未找到完整表格] 尝试合并分离的表头和数据")
        complete_table_found = False
        # 如果找到了分离的表头和数据，尝试合并
        if header_matrix and data_matrix:
            print("[合并] 尝试合并分离的表头和数据表格")
            # 将表头行添加到数据表格前面
            merged_matrix = header_matrix + data_matrix
            section = extract_section(merged_matrix)
            if section:
                sections = [section]
            else:
                # 合并失败，分别处理
                sections = []
                for matrix in candidates:
                    section = extract_section(matrix)
                    if section:
                        sections.append(section)
        else:
            # 正常处理
            sections = []
            for matrix in candidates:
                section = extract_section(matrix)
                if section:
                    sections.append(section)

    if not sections:
        return "解析失败：未能从网页表格中识别有效数据。"

    rows: List[Dict[str, Optional[str]]] = []
    metadata: List[Dict[str, Optional[str]]] = []
    notes: List[str] = []

    # 只添加一次metadata，使用页面级别的标题信息
    first_section = sections[0] if sections else {}
    metadata.append(
        {
            "source": "html",
            "title": first_section.get("title"),
            "subtitle": first_section.get("subtitle"),
            "title_meta": page_title_meta,  # 使用页面级别的标题信息（优先使用传入的match）
        }
    )

    for section in sections:
        for row in section["rows"]:
            rows.append(dict(row))
        notes.extend(section.get("notes", []))

    if not rows:
        return "解析失败：识别到表格，但未抽取到有效数据行。"

    df = pd.DataFrame(rows).replace("", pd.NA)
    df = _merge_duplicate_columns(df)
    df = df.dropna(axis=1, how="all")
    
    # 🔥🔥🔥 多表格合并时去重：根据成交时间去重 🔥🔥🔥
    if len(sections) > 1:
        print(f"[数据去重] 合并了 {len(sections)} 个表格，共 {len(df)} 行，开始去重...")
        initial_rows = len(df)
        
        # 如果有"成交时间"列，根据它去重
        if "成交时间" in df.columns:
            # 保留第一次出现的数据
            df = df.drop_duplicates(subset=["成交时间"], keep="first")
            removed = initial_rows - len(df)
            if removed > 0:
                print(f"[数据去重] 根据成交时间去重，移除了 {removed} 行重复数据，剩余 {len(df)} 行")
            else:
                print(f"[数据去重] 无重复数据")
        else:
            print(f"[数据去重] 未找到成交时间列，跳过去重")

    if metadata:
        df.attrs["metadata"] = metadata
    if notes:
        df.attrs["notes"] = notes

    return df


def parse_match_list(html: str, base_url: str) -> List[Dict[str, Optional[str]]]:
    """
    从标盘列表页 HTML 中解析每一场比赛的标盘明细链接与基础信息。
    """

    soup = BeautifulSoup(html, "html.parser")
    matches: List[Dict[str, Optional[str]]] = []
    
    # 先检查是否有matchDetails.php链接
    all_links = soup.find_all("a")
    match_details_links = [a for a in all_links if "matchDetails.php" in (a.get("href") or "") or "matchDetails.php" in (a.get("onclick") or "")]
    sporttery_links = [a for a in all_links if "sporttery.php" in (a.get("href") or "") or "sporttery.php" in (a.get("onclick") or "")]
    
    print(f"\n[HTML解析器] 总共找到 {len(all_links)} 个<a>标签")
    print(f"  - matchDetails.php 链接: {len(match_details_links)} 个")
    print(f"  - sporttery.php 链接: {len(sporttery_links)} 个")
    
    if match_details_links:
        print(f"\n[重要] 发现 matchDetails.php 链接，前3个示例：")
        for idx, link in enumerate(match_details_links[:3], 1):
            href = link.get('href', '')
            onclick = link.get('onclick', '')
            text = link.get_text(strip=True)
            print(f"  {idx}. 文本: {text[:30]}")
            print(f"     href: {href[:100] if href else '(空)'}")
            print(f"     onclick: {onclick[:100] if onclick else '(空)'}")
    else:
        print(f"\n[警告] 未找到 matchDetails.php 链接！")
        if sporttery_links:
            print(f"只找到 sporttery.php 链接，前3个示例：")
            for idx, link in enumerate(sporttery_links[:3], 1):
                href = link.get('href', '')
                onclick = link.get('onclick', '')
                text = link.get_text(strip=True)
                print(f"  {idx}. 文本: {text[:30]}")
                print(f"     href: {href[:100] if href else '(空)'}")
                print(f"     onclick: {onclick[:100] if onclick else '(空)'}")

    for link in soup.find_all("a"):
        text = (link.get_text() or "").strip()
        href = link.get("href") or ""
        onclick = link.get("onclick") or ""

        candidate = False
        detail_params: Optional[Dict[str, Optional[str]]] = None
        
        # 优先查找matchDetails.php链接（真正的明细页面）
        if "matchDetails.php" in href:
            candidate = True
        elif "matchDetails.php" in onclick:
            match = re.search(r"'([^']+matchDetails\.php[^']*)'", onclick)
            if match:
                href = match.group(1)
                candidate = True
        # 其次查找sporttery.php链接（备用）
        elif "sporttery.php" in href:
            candidate = True
        elif "sporttery.php" in onclick:
            match = re.search(r"'([^']+sporttery\.php[^']*)'", onclick)
            if match:
                href = match.group(1)
                candidate = True
        elif "标盘明细" in text:
            candidate = True

        if not candidate:
            continue

        if href.startswith("javascript"):
            href = ""

        if not href and onclick:
            match = re.search(r"'([^']+sporttery\.php[^']*)'", onclick)
            if match:
                href = match.group(1)

        if not href:
            continue

        container = _find_parent_with_tag(link, {"table", "tbody", "tr", "div"})
        if container is None:
            container = link.parent  # type: ignore[assignment]

        block_text = container.get_text(" ", strip=True) if container else text

        league = None
        kickoff = None
        home = None
        away = None

        # 提取 openMatchDetails 所需参数，便于后续构造精确的明细抓取请求
        detail_match = re.search(
            r"openMatchDetails\('([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)'\)",
            onclick or "",
        )
        if detail_match:
            detail_params = {
                "match_id": detail_match.group(1) or None,
                "match_mid": detail_match.group(2) or None,
                "open_time": detail_match.group(3) or None,
                "home_sid": detail_match.group(4) or None,
                "away_sid": detail_match.group(5) or None,
                "extra": detail_match.group(6) or None,
                "flag": detail_match.group(7) or None,
            }

        league_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+联)", block_text)
        if league_match:
            league = league_match.group(1)

        kickoff_match = re.search(r"(\d{2}-\d{2}\s*\d{2}:\d{2})", block_text)
        if kickoff_match:
            kickoff = kickoff_match.group(1).replace("  ", " ").strip()

        vs_match = re.search(
            r"([A-Za-z\u4e00-\u9fa5\d\[\]()（）·.\s]+?)\s*(?:VS|vs|Vs|vS)\s*([A-Za-z\u4e00-\u9fa5\d\[\]()（）·.\s]+)",
            block_text,
        )
        if vs_match:
            home = vs_match.group(1).strip()
            away = vs_match.group(2).strip()

        label_parts = [part for part in [kickoff, league, home, "vs", away] if part]
        label = " ".join(label_parts) if label_parts else (text or block_text[:80])

        matches.append(
            {
                "match_id": detail_params.get("match_id") if detail_params else None,
                "league": league,
                "kickoff": kickoff,
                "home": home,
                "away": away,
                "label": label,
                "detail_url": urljoin(base_url, href),
                "detail_params": detail_params,
            }
        )

    return matches

