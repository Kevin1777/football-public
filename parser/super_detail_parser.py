"""
超级明细解析器 - 整合标盘、大小球、让球指数、比分数据

支持的页面类型：
1. matchDetails.php - 标盘明细
2. OuDetails.php - 大小球明细  
3. AisaDetails.php - 让球指数明细（亚盘）
4. CorrectDetails.php - 比分明细（波胆）

超级JSON格式设计：
{
    "match_info": {...},           # 比赛基本信息
    "standard_trade": {...},       # 标盘交易明细
    "ou_trade": {...},             # 大小球交易明细
    "handicap_trade": {...},       # 让球指数交易明细（亚盘）
    "correct_score_trade": {...},  # 比分交易明细（波胆）
    "handicap_data": {...},        # 盘口数据（各公司）
    "summary": {...}               # 汇总统计
}
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd
from bs4 import BeautifulSoup, Tag

# 让球指数（亚盘）表头关键字
HANDICAP_HEADER_KEYWORDS = (
    "成交时间", "总成交量", "主队", "客队", "让球", "盘口",
    "主胜", "客胜", "已成交", "现成交", "方式"
)

# 比分（波胆）表头关键字
CORRECT_SCORE_HEADER_KEYWORDS = (
    "成交时间", "总成交量", "比分", "赔率", "已成交", "现成交", "方式"
)

TIME_CELL_PATTERN = re.compile(r"\d{2}-\d{2}\s+\d{2}:\d{2}")


def normalize_cell(text: str) -> str:
    """标准化单元格文本"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    text = text.replace('\xa0', ' ').replace('\u3000', ' ')
    return text.strip()


def _table_to_matrix(table: Tag) -> List[List[str]]:
    """将HTML表格转换为二维数组"""
    rows: List[List[str]] = []
    spans: Dict[int, Tuple[str, int]] = {}
    
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells and not spans:
            continue
        
        row: List[str] = []
        col = 0
        
        while col in spans:
            value, remain = spans[col]
            row.append(value)
            if remain > 1:
                spans[col] = (value, remain - 1)
            else:
                del spans[col]
            col += 1
        
        for cell in cells:
            while col in spans:
                value, remain = spans[col]
                row.append(value)
                if remain > 1:
                    spans[col] = (value, remain - 1)
                else:
                    del spans[col]
                col += 1
            
            text = normalize_cell(cell.get_text(" ", strip=True))
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            
            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    spans[col] = (text, rowspan - 1)
                col += 1
        
        if any(row):
            rows.append(row)
    
    return rows


def parse_handicap_trade_html(html: str) -> Dict[str, Any]:
    """
    解析让球指数（亚盘）交易明细页面
    
    URL格式: AisaDetails.php?getuid=...
    
    列顺序（根据实际页面）:
    成交时间 | 总成交量 | 
    主队: SB、价位、已成交量、现成交量、方式、赔付率、比例、必指、赔指、赢亏、赔付 |
    客队: SB、价位、已成交量、现成交量、方式、赔付率、比例、必指、赔指、赢亏、赔付 |
    SB让球
    
    返回格式:
    {
        "handicap_line": -0.75,
        "columns": [...],
        "data": [...],
        "total_records": 100
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # 🔥 定义让球交易明细的列名（按实际页面顺序）
    HANDICAP_COLUMNS = [
        "成交时间", "总成交量",
        # 主队 11列
        "主队_SB", "主队_价位", "主队_已成交量", "主队_现成交量", "主队_方式",
        "主队_赔付率", "主队_比例", "主队_必指", "主队_赔指", "主队_赢亏", "主队_赔付",
        # 客队 11列
        "客队_SB", "客队_价位", "客队_已成交量", "客队_现成交量", "客队_方式",
        "客队_赔付率", "客队_比例", "客队_必指", "客队_赔指", "客队_赢亏", "客队_赔付",
        # 让球
        "SB让球",
    ]
    
    result = {
        "handicap_line": None,
        "columns": HANDICAP_COLUMNS,
        "data": [],
        "total_records": 0
    }
    
    # 提取让球数信息
    hdp_match = re.search(r'hdp\s*[=:]\s*["\']?(-?[\d.]+)', html)
    if hdp_match:
        result["handicap_line"] = float(hdp_match.group(1))
    
    def parse_handicap_row(cells) -> Optional[Dict]:
        """解析让球数据行"""
        if len(cells) < 10:
            return None
        
        time_text = normalize_cell(cells[0].get_text())
        if not TIME_CELL_PATTERN.search(time_text):
            return None
        
        record = {
            "成交时间": time_text,
            "总成交量": normalize_cell(cells[1].get_text()) if len(cells) > 1 else None,
        }
        
        # 主队数据 (索引 2-12，共11列)
        if len(cells) > 2:
            record["主队_SB"] = normalize_cell(cells[2].get_text())
        if len(cells) > 3:
            record["主队_价位"] = normalize_cell(cells[3].get_text())
        if len(cells) > 4:
            record["主队_已成交量"] = normalize_cell(cells[4].get_text())
        if len(cells) > 5:
            record["主队_现成交量"] = normalize_cell(cells[5].get_text())
        if len(cells) > 6:
            record["主队_方式"] = normalize_cell(cells[6].get_text())
        if len(cells) > 7:
            record["主队_赔付率"] = normalize_cell(cells[7].get_text())
        if len(cells) > 8:
            record["主队_比例"] = normalize_cell(cells[8].get_text())
        if len(cells) > 9:
            record["主队_必指"] = normalize_cell(cells[9].get_text())
        if len(cells) > 10:
            record["主队_赔指"] = normalize_cell(cells[10].get_text())
        if len(cells) > 11:
            record["主队_赢亏"] = normalize_cell(cells[11].get_text())
        if len(cells) > 12:
            record["主队_赔付"] = normalize_cell(cells[12].get_text())
        
        # 客队数据 (索引 13-23，共11列)
        if len(cells) > 13:
            record["客队_SB"] = normalize_cell(cells[13].get_text())
        if len(cells) > 14:
            record["客队_价位"] = normalize_cell(cells[14].get_text())
        if len(cells) > 15:
            record["客队_已成交量"] = normalize_cell(cells[15].get_text())
        if len(cells) > 16:
            record["客队_现成交量"] = normalize_cell(cells[16].get_text())
        if len(cells) > 17:
            record["客队_方式"] = normalize_cell(cells[17].get_text())
        if len(cells) > 18:
            record["客队_赔付率"] = normalize_cell(cells[18].get_text())
        if len(cells) > 19:
            record["客队_比例"] = normalize_cell(cells[19].get_text())
        if len(cells) > 20:
            record["客队_必指"] = normalize_cell(cells[20].get_text())
        if len(cells) > 21:
            record["客队_赔指"] = normalize_cell(cells[21].get_text())
        if len(cells) > 22:
            record["客队_赢亏"] = normalize_cell(cells[22].get_text())
        if len(cells) > 23:
            record["客队_赔付"] = normalize_cell(cells[23].get_text())
        
        # SB让球 (索引 24)
        if len(cells) > 24:
            record["SB让球"] = normalize_cell(cells[24].get_text())
        
        return record
    
    # 🔥 方法1: 直接查找带有class="item"的数据行
    item_rows = soup.find_all("tr", class_="item")
    if item_rows:
        for row in item_rows:
            cells = row.find_all("td")
            record = parse_handicap_row(cells)
            if record:
                result["data"].append(record)
        
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result
    
    # 🔥 方法2: 查找id="table_1"的表格
    table_1 = soup.find("table", id="table_1")
    if table_1:
        rows = table_1.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            record = parse_handicap_row(cells)
            if record:
                result["data"].append(record)
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result
    
    result["total_records"] = len(result["data"])
    return result


def parse_ou_trade_html(html: str) -> Dict[str, Any]:
    """
    解析大小球交易明细页面
    
    URL格式: ouDetails.php?getuid=...
    
    列顺序（根据实际页面，与让球类似）:
    成交时间 | 总成交量 | 
    大球: SB、价位、已成交量、现成交量、方式、赔付率、比例、必指、赔指、赢亏、赔付 |
    小球: SB、价位、已成交量、现成交量、方式、赔付率、比例、必指、赔指、赢亏、赔付 |
    SB大小
    
    返回格式:
    {
        "ou_line": 2.5,
        "columns": [...],
        "data": [...],
        "total_records": 100
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # 🔥 定义大小球交易明细的列名（按实际页面顺序）
    OU_COLUMNS = [
        "成交时间", "总成交量",
        # 大球 11列
        "大球_SB", "大球_价位", "大球_已成交量", "大球_现成交量", "大球_方式",
        "大球_赔付率", "大球_比例", "大球_必指", "大球_赔指", "大球_赢亏", "大球_赔付",
        # 小球 11列
        "小球_SB", "小球_价位", "小球_已成交量", "小球_现成交量", "小球_方式",
        "小球_赔付率", "小球_比例", "小球_必指", "小球_赔指", "小球_赢亏", "小球_赔付",
        # 大小
        "SB大小",
    ]
    
    result = {
        "ou_line": None,
        "columns": OU_COLUMNS,
        "data": [],
        "total_records": 0
    }
    
    # 提取大小球盘口
    hdp_match = re.search(r'hdp\s*[=:]\s*["\']?([\d.]+)', html)
    if hdp_match:
        result["ou_line"] = float(hdp_match.group(1))
    
    def parse_ou_row(cells) -> Optional[Dict]:
        """解析大小球数据行"""
        if len(cells) < 10:
            return None
        
        time_text = normalize_cell(cells[0].get_text())
        if not TIME_CELL_PATTERN.search(time_text):
            return None
        
        record = {
            "成交时间": time_text,
            "总成交量": normalize_cell(cells[1].get_text()) if len(cells) > 1 else None,
        }
        
        # 大球数据 (索引 2-12，共11列)
        if len(cells) > 2:
            record["大球_SB"] = normalize_cell(cells[2].get_text())
        if len(cells) > 3:
            record["大球_价位"] = normalize_cell(cells[3].get_text())
        if len(cells) > 4:
            record["大球_已成交量"] = normalize_cell(cells[4].get_text())
        if len(cells) > 5:
            record["大球_现成交量"] = normalize_cell(cells[5].get_text())
        if len(cells) > 6:
            record["大球_方式"] = normalize_cell(cells[6].get_text())
        if len(cells) > 7:
            record["大球_赔付率"] = normalize_cell(cells[7].get_text())
        if len(cells) > 8:
            record["大球_比例"] = normalize_cell(cells[8].get_text())
        if len(cells) > 9:
            record["大球_必指"] = normalize_cell(cells[9].get_text())
        if len(cells) > 10:
            record["大球_赔指"] = normalize_cell(cells[10].get_text())
        if len(cells) > 11:
            record["大球_赢亏"] = normalize_cell(cells[11].get_text())
        if len(cells) > 12:
            record["大球_赔付"] = normalize_cell(cells[12].get_text())
        
        # 小球数据 (索引 13-23，共11列)
        if len(cells) > 13:
            record["小球_SB"] = normalize_cell(cells[13].get_text())
        if len(cells) > 14:
            record["小球_价位"] = normalize_cell(cells[14].get_text())
        if len(cells) > 15:
            record["小球_已成交量"] = normalize_cell(cells[15].get_text())
        if len(cells) > 16:
            record["小球_现成交量"] = normalize_cell(cells[16].get_text())
        if len(cells) > 17:
            record["小球_方式"] = normalize_cell(cells[17].get_text())
        if len(cells) > 18:
            record["小球_赔付率"] = normalize_cell(cells[18].get_text())
        if len(cells) > 19:
            record["小球_比例"] = normalize_cell(cells[19].get_text())
        if len(cells) > 20:
            record["小球_必指"] = normalize_cell(cells[20].get_text())
        if len(cells) > 21:
            record["小球_赔指"] = normalize_cell(cells[21].get_text())
        if len(cells) > 22:
            record["小球_赢亏"] = normalize_cell(cells[22].get_text())
        if len(cells) > 23:
            record["小球_赔付"] = normalize_cell(cells[23].get_text())
        
        # SB大小 (索引 24)
        if len(cells) > 24:
            record["SB大小"] = normalize_cell(cells[24].get_text())
        
        return record
    
    # 🔥 方法1: 直接查找带有class="item"的数据行
    item_rows = soup.find_all("tr", class_="item")
    if item_rows:
        for row in item_rows:
            cells = row.find_all("td")
            record = parse_ou_row(cells)
            if record:
                result["data"].append(record)
        
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result
    
    # 🔥 方法2: 查找id="table_1"的表格
    table_1 = soup.find("table", id="table_1")
    if table_1:
        rows = table_1.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            record = parse_ou_row(cells)
            if record:
                result["data"].append(record)
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result

    
    result["total_records"] = len(result["data"])
    return result


def parse_correct_score_html(html: str) -> Dict[str, Any]:
    """
    解析比分（波胆）交易明细页面
    
    URL格式: CorrectDetails.php?getuid=...
    
    比分顺序（共19个）:
    - 主胜(7个): 3:2, 3:1, 3:0, 2:1, 2:0, 1:0, 其它
    - 和局(5个): 3:3, 2:2, 1:1, 0:0, 其它
    - 客胜(7个): 2:3, 1:3, 0:3, 1:2, 0:2, 0:1, 其它
    
    每个比分有4列: 价位、成交量、比例、赔付率
    
    返回格式（与标盘格式一致）:
    {
        "columns": [...],
        "data": [...],
        "total_records": 100
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # 🔥 定义19个比分（按页面顺序）
    SCORE_NAMES = [
        # 主胜 (7个)
        "主胜_3:2", "主胜_3:1", "主胜_3:0", "主胜_2:1", "主胜_2:0", "主胜_1:0", "主胜_其它",
        # 和局 (5个)
        "和局_3:3", "和局_2:2", "和局_1:1", "和局_0:0", "和局_其它",
        # 客胜 (7个)
        "客胜_2:3", "客胜_1:3", "客胜_0:3", "客胜_1:2", "客胜_0:2", "客胜_0:1", "客胜_其它",
    ]
    
    # 🔥 定义比分交易明细的列名
    CORRECT_SCORE_COLUMNS = ["成交时间", "总成交量"]
    for score in SCORE_NAMES:
        CORRECT_SCORE_COLUMNS.extend([
            f"{score}_价位", f"{score}_成交量", f"{score}_比例", f"{score}_赔付率"
        ])
    
    result = {
        "columns": CORRECT_SCORE_COLUMNS,
        "data": [],
        "total_records": 0
    }
    
    def parse_row(cells) -> Optional[Dict]:
        """解析单行数据"""
        if len(cells) < 10:  # 至少要有一些数据
            return None
        
        time_text = normalize_cell(cells[0].get_text())
        if not TIME_CELL_PATTERN.search(time_text):
            return None
        
        record = {
            "成交时间": time_text,
            "总成交量": normalize_cell(cells[1].get_text()) if len(cells) > 1 else None,
        }
        
        # 从第3列开始，每4列是一个比分的数据
        col_idx = 2
        for score in SCORE_NAMES:
            if col_idx + 3 < len(cells):
                record[f"{score}_价位"] = normalize_cell(cells[col_idx].get_text()) if col_idx < len(cells) else None
                record[f"{score}_成交量"] = normalize_cell(cells[col_idx + 1].get_text()) if col_idx + 1 < len(cells) else None
                record[f"{score}_比例"] = normalize_cell(cells[col_idx + 2].get_text()) if col_idx + 2 < len(cells) else None
                record[f"{score}_赔付率"] = normalize_cell(cells[col_idx + 3].get_text()) if col_idx + 3 < len(cells) else None
            col_idx += 4
        
        return record
    
    # 🔥 方法1: 直接查找带有class="item"的数据行
    item_rows = soup.find_all("tr", class_="item")
    if item_rows:
        for row in item_rows:
            cells = row.find_all("td")
            record = parse_row(cells)
            if record:
                result["data"].append(record)
        
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result
    
    # 🔥 方法2: 查找id="table_1"的表格
    table_1 = soup.find("table", id="table_1")
    if table_1:
        rows = table_1.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            record = parse_row(cells)
            if record:
                result["data"].append(record)
        
        if result["data"]:
            result["total_records"] = len(result["data"])
            return result
    
    result["total_records"] = len(result["data"])
    return result


class SuperDetailParser:
    """
    超级明细解析器
    整合所有类型的交易明细数据到一个统一的JSON格式
    """
    
    def __init__(self):
        self.match_info = {}
        self.standard_trade = {}
        self.ou_trade = {}
        self.handicap_trade = {}
        self.correct_score_trade = {}
        self.handicap_data = {}
    
    def parse_all(
        self,
        standard_html: Optional[str] = None,
        ou_html: Optional[str] = None,
        handicap_html: Optional[str] = None,
        correct_score_html: Optional[str] = None,
        match_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        解析所有类型的明细数据
        """
        result = {
            "version": "2.0",
            "created_at": datetime.now().isoformat(),
            "match_info": match_info or {},
            "standard_trade": {},
            "ou_trade": {},
            "handicap_trade": {},
            "correct_score_trade": {},
            "handicap_data": {},
            "summary": {}
        }
        
        # 解析标盘明细
        if standard_html:
            from .html_parser import parse_bifa_html
            try:
                df = parse_bifa_html(standard_html, match_info)
                if isinstance(df, pd.DataFrame):
                    result["standard_trade"] = {
                        "columns": df.columns.tolist(),
                        "data": df.to_dict(orient="records"),
                        "total_records": len(df)
                    }
            except Exception as e:
                print(f"[标盘解析] 失败: {e}")
        
        # 解析大小球明细
        if ou_html:
            try:
                ou_data = self._parse_ou_html(ou_html)
                result["ou_trade"] = ou_data
            except Exception as e:
                print(f"[大小球解析] 失败: {e}")
        
        # 解析让球指数明细
        if handicap_html:
            try:
                hdp_data = parse_handicap_trade_html(handicap_html)
                result["handicap_trade"] = hdp_data
            except Exception as e:
                print(f"[让球解析] 失败: {e}")
        
        # 解析比分明细
        if correct_score_html:
            try:
                cs_data = parse_correct_score_html(correct_score_html)
                result["correct_score_trade"] = cs_data
            except Exception as e:
                print(f"[比分解析] 失败: {e}")
        
        result["summary"] = self._generate_summary(result)
        
        return result
    
    def _parse_ou_html(self, html: str) -> Dict[str, Any]:
        """解析大小球明细HTML（使用与标盘相同的格式）"""
        soup = BeautifulSoup(html, "html.parser")
        
        # 🔥 定义大小球交易明细的列名（按实际页面顺序）
        OU_COLUMNS = [
            "成交时间", "总成交量",
            # 大球 11列
            "大球_SB", "大球_价位", "大球_已成交量", "大球_现成交量", "大球_方式",
            "大球_赔付率", "大球_比例", "大球_必指", "大球_赔指", "大球_赢亏", "大球_赔付",
            # 小球 11列
            "小球_SB", "小球_价位", "小球_已成交量", "小球_现成交量", "小球_方式",
            "小球_赔付率", "小球_比例", "小球_必指", "小球_赔指", "小球_赢亏", "小球_赔付",
            # 大小
            "SB大小",
        ]
        
        result = {
            "ou_line": None,
            "columns": OU_COLUMNS,
            "data": [],
            "total_records": 0
        }
        
        ou_match = re.search(r'大小球[：:]\s*([\d.]+)', html)
        if ou_match:
            result["ou_line"] = float(ou_match.group(1))
        
        tables = soup.find_all("table")
        for table in tables:
            matrix = _table_to_matrix(table)
            if len(matrix) > 2:
                table_text = " ".join(" ".join(row) for row in matrix[:3])
                if "大" in table_text and "小" in table_text:
                    result["data"] = self._parse_ou_table(matrix)
                    result["total_records"] = len(result["data"])
                    break
        
        return result
    
    def _parse_ou_table(self, matrix: List[List[str]]) -> List[Dict]:
        """解析大小球表格数据（使用中文列名，完整25列）"""
        records = []
        
        header_idx = 0
        for idx, row in enumerate(matrix[:3]):
            row_text = " ".join(row)
            if "成交时间" in row_text or "总成交" in row_text:
                header_idx = idx
                break
        
        for row in matrix[header_idx + 1:]:
            if not row:
                continue
            
            row_text = " ".join(row)
            if not TIME_CELL_PATTERN.search(row_text):
                continue
            
            record = {
                "成交时间": row[0] if len(row) > 0 else None,
                "总成交量": row[1] if len(row) > 1 else None,
            }
            
            # 大球数据 (索引 2-12，共11列)
            if len(row) > 2:
                record["大球_SB"] = row[2]
            if len(row) > 3:
                record["大球_价位"] = row[3]
            if len(row) > 4:
                record["大球_已成交量"] = row[4]
            if len(row) > 5:
                record["大球_现成交量"] = row[5]
            if len(row) > 6:
                record["大球_方式"] = row[6]
            if len(row) > 7:
                record["大球_赔付率"] = row[7]
            if len(row) > 8:
                record["大球_比例"] = row[8]
            if len(row) > 9:
                record["大球_必指"] = row[9]
            if len(row) > 10:
                record["大球_赔指"] = row[10]
            if len(row) > 11:
                record["大球_赢亏"] = row[11]
            if len(row) > 12:
                record["大球_赔付"] = row[12]
            
            # 小球数据 (索引 13-23，共11列)
            if len(row) > 13:
                record["小球_SB"] = row[13]
            if len(row) > 14:
                record["小球_价位"] = row[14]
            if len(row) > 15:
                record["小球_已成交量"] = row[15]
            if len(row) > 16:
                record["小球_现成交量"] = row[16]
            if len(row) > 17:
                record["小球_方式"] = row[17]
            if len(row) > 18:
                record["小球_赔付率"] = row[18]
            if len(row) > 19:
                record["小球_比例"] = row[19]
            if len(row) > 20:
                record["小球_必指"] = row[20]
            if len(row) > 21:
                record["小球_赔指"] = row[21]
            if len(row) > 22:
                record["小球_赢亏"] = row[22]
            if len(row) > 23:
                record["小球_赔付"] = row[23]
            
            # SB大小 (索引 24)
            if len(row) > 24:
                record["SB大小"] = row[24]
            
            records.append(record)
        
        return records
    
    def _generate_summary(self, data: Dict) -> Dict[str, Any]:
        """生成汇总统计"""
        # 🔥 适配新格式：data 而不是 trade_records
        summary = {
            "has_standard_trade": bool(data.get("standard_trade", {}).get("data")),
            "has_ou_trade": bool(data.get("ou_trade", {}).get("data") or data.get("ou_trade", {}).get("trade_records")),
            "has_handicap_trade": bool(data.get("handicap_trade", {}).get("data") or data.get("handicap_trade", {}).get("trade_records")),
            "has_correct_score_trade": bool(data.get("correct_score_trade", {}).get("data") or data.get("correct_score_trade", {}).get("trade_records")),
        }
        
        summary["standard_trade_count"] = len(data.get("standard_trade", {}).get("data", []))
        summary["ou_trade_count"] = len(data.get("ou_trade", {}).get("data", []) or data.get("ou_trade", {}).get("trade_records", []))
        summary["handicap_trade_count"] = len(data.get("handicap_trade", {}).get("data", []) or data.get("handicap_trade", {}).get("trade_records", []))
        summary["correct_score_count"] = len(data.get("correct_score_trade", {}).get("data", []) or data.get("correct_score_trade", {}).get("trade_records", []))
        
        completeness = sum([
            summary["has_standard_trade"],
            summary["has_ou_trade"],
            summary["has_handicap_trade"],
            summary["has_correct_score_trade"]
        ])
        summary["completeness_score"] = completeness / 4.0
        summary["completeness_level"] = ["无数据", "基础", "中等", "良好", "完整"][completeness]
        
        return summary


def create_super_json(
    match_info: Dict,
    standard_data: Optional[Dict] = None,
    ou_data: Optional[Dict] = None,
    handicap_data: Optional[Dict] = None,
    correct_score_data: Optional[Dict] = None,
    handicap_companies: Optional[Dict] = None,
    # 🔥 新增：所有盘口信息支持
    handicap_all_lines: Optional[List[Dict]] = None,
    ou_all_lines: Optional[List[Dict]] = None,
    handicap_main_line: Optional[str] = None,
    ou_main_line: Optional[str] = None,
) -> Dict[str, Any]:
    """
    创建超级JSON格式数据
    
    Args:
        match_info: 比赛基本信息
        standard_data: 标盘交易数据
        ou_data: 大小球交易数据
        handicap_data: 让球指数交易数据
        correct_score_data: 比分交易数据
        handicap_companies: 各公司盘口数据
        handicap_all_lines: 所有让球盘口信息列表
        ou_all_lines: 所有大小球盘口信息列表
        handicap_main_line: 让球主盘口
        ou_main_line: 大小球主盘口
    
    Returns:
        超级JSON格式数据
    """
    # 🔥 自动从 match_info 中提取盘口列表（如果没有单独传递）
    if handicap_all_lines is None:
        handicap_all_lines = match_info.get('handicap_all_lines', [])
    if ou_all_lines is None:
        ou_all_lines = match_info.get('ou_all_lines', [])
    if handicap_main_line is None:
        handicap_main_line = match_info.get('handicap_main_line') or match_info.get('handicap_hdp')
    if ou_main_line is None:
        ou_main_line = match_info.get('ou_main_line') or match_info.get('ou_hdp')
    
    # ========== 计算标盘数据（胜负平交易额）==========
    standard_count = 0
    standard_volume = None  # 总成交量
    home_volume = None      # 主胜成交量
    draw_volume = None      # 和局成交量
    away_volume = None      # 客胜成交量
    
    if standard_data:
        data_list = standard_data.get('data', [])
        standard_count = standard_data.get('total_records', len(data_list))
        
        # 从最新一条记录获取交易额
        if data_list:
            latest = data_list[0]  # 第一条是最新的
            standard_volume = latest.get('总成交量')
            home_volume = latest.get('主胜_已成交量')
            draw_volume = latest.get('和局_已成交量')
            away_volume = latest.get('客胜_已成交量')
    
    # ========== 计算大小球数据 ==========
    ou_count = 0
    ou_line = None
    ou_volume = None  # 大小球总成交量
    
    if ou_data:
        # 🔥 适配新格式：data 而不是 trade_records
        ou_records = ou_data.get('data', []) or ou_data.get('trade_records', [])
        ou_count = ou_data.get('total_records', len(ou_records))
        ou_line = ou_data.get('ou_line')
        
        # 从最新一条记录获取交易额
        if ou_records:
            latest = ou_records[0]
            ou_volume = latest.get('总成交量') or latest.get('total_volume')
    
    # ========== 计算让球数据 ==========
    handicap_count = 0
    handicap_line = None
    handicap_volume = None  # 让球总成交量
    handicap_home_volume = None  # 🔥 主队已成交量
    handicap_away_volume = None  # 🔥 客队已成交量
    
    if handicap_data:
        # 🔥 适配新格式：支持多盘口数据
        if 'lines' in handicap_data:
            # 新格式：多盘口数据
            handicap_line = handicap_data.get('main_line')
            # 从主盘口获取数据
            for line_data in handicap_data.get('lines', []):
                if line_data.get('is_main'):
                    hc_records = line_data.get('trade_records', [])
                    handicap_count = len(hc_records)
                    if hc_records:
                        latest = hc_records[0]
                        handicap_volume = latest.get('总成交量') or latest.get('total_volume')
                        handicap_home_volume = latest.get('主队_已成交量') or latest.get('home_volume')
                        handicap_away_volume = latest.get('客队_已成交量') or latest.get('away_volume')
                    break
            # 如果没有主盘口，使用第一个盘口
            if handicap_count == 0 and handicap_data.get('lines'):
                first_line = handicap_data['lines'][0]
                hc_records = first_line.get('trade_records', [])
                handicap_count = len(hc_records)
                if hc_records:
                    latest = hc_records[0]
                    handicap_volume = latest.get('总成交量') or latest.get('total_volume')
                    handicap_home_volume = latest.get('主队_已成交量') or latest.get('home_volume')
                    handicap_away_volume = latest.get('客队_已成交量') or latest.get('away_volume')
        else:
            # 旧格式：单盘口数据
            hc_records = handicap_data.get('data', []) or handicap_data.get('trade_records', [])
            handicap_count = handicap_data.get('total_records', len(hc_records))
            handicap_line = handicap_data.get('handicap_line')
            
            # 从最新一条记录获取交易额（使用中文列名）
            if hc_records:
                latest = hc_records[0]
                handicap_volume = latest.get('总成交量') or latest.get('total_volume')
                handicap_home_volume = latest.get('主队_已成交量') or latest.get('home_volume')
                handicap_away_volume = latest.get('客队_已成交量') or latest.get('away_volume')
    
    # ========== 计算比分数据 ==========
    correct_score_count = 0
    correct_score_volume = None
    
    if correct_score_data:
        # 🔥 适配新格式：data 而不是 trade_records
        cs_records = correct_score_data.get('data', []) or correct_score_data.get('trade_records', [])
        correct_score_count = correct_score_data.get('total_records', len(cs_records))
        
        if cs_records:
            latest = cs_records[0]
            correct_score_volume = latest.get('总成交量') or latest.get('total_volume')
    
    # ========== 🔥 处理所有盘口信息 ==========
    # 让球盘口列表
    handicap_lines_info = []
    if handicap_all_lines:
        for line_info in handicap_all_lines:
            handicap_lines_info.append({
                "hdp_home": line_info.get('hdp_home'),      # 主队视角盘口
                "hdp_away": line_info.get('hdp_away'),      # 客队视角盘口
                "sb": line_info.get('sb'),                   # SB值
                "volume": line_info.get('volume'),           # 成交量
                "is_main": line_info.get('is_main', False),  # 是否主盘口
            })
    
    # 大小球盘口列表
    ou_lines_info = []
    if ou_all_lines:
        for line_info in ou_all_lines:
            ou_lines_info.append({
                "line": line_info.get('line'),               # 盘口值
                "sb": line_info.get('sb'),                   # SB值
                "volume": line_info.get('volume'),           # 成交量
                "is_main": line_info.get('is_main', False),  # 是否主盘口
            })
    
    # ========== 🔥 数据摘要 - 放在JSON最前面，方便快速验证 ==========
    data_summary = {
        "_说明": "四合一交易明细数据摘要（最新成交数据）",
        "标盘_胜负平": {
            "记录数": standard_count,
            "总成交量": standard_volume,
            "主胜成交量": home_volume,
            "和局成交量": draw_volume,
            "客胜成交量": away_volume
        },
        "大小球": {
            "记录数": ou_count,
            "主盘口": ou_line or ou_main_line,
            "总成交量": ou_volume,
            "所有盘口数": len(ou_lines_info) if ou_lines_info else 0
        },
        "让球_亚盘": {
            "记录数": handicap_count,
            "主盘口": handicap_line or handicap_main_line,
            "总成交量": handicap_volume,
            "主队成交量": handicap_home_volume,  # 🔥 新增
            "客队成交量": handicap_away_volume,  # 🔥 新增
            "所有盘口数": len(handicap_lines_info) if handicap_lines_info else 0
        },
        "比分_波胆": {
            "记录数": correct_score_count,
            "总成交量": correct_score_volume
        },
        "数据完整度": f"{sum([standard_count>0, ou_count>0, handicap_count>0, correct_score_count>0])}/4"
    }
    
    result = {
        "_数据摘要": data_summary,  # 放在最前面
        "version": "2.1",  # 🔥 版本升级
        "format": "super_detail",
        "created_at": datetime.now().isoformat(),
        "match_info": match_info,
        "standard_trade": standard_data or {},
        "ou_trade": ou_data or {},
        "handicap_trade": handicap_data or {},
        "correct_score_trade": correct_score_data or {},
        "handicap_data": handicap_companies or {},
        # 🔥 新增：所有盘口信息
        "all_handicap_lines": {
            "main_line": handicap_main_line or handicap_line,
            "lines": handicap_lines_info,
            "total_count": len(handicap_lines_info)
        } if handicap_lines_info else {},
        "all_ou_lines": {
            "main_line": ou_main_line or ou_line,
            "lines": ou_lines_info,
            "total_count": len(ou_lines_info)
        } if ou_lines_info else {},
        "summary": {}
    }
    
    summary = {
        "has_standard_trade": bool(standard_data),
        "has_ou_trade": bool(ou_data),
        "has_handicap_trade": bool(handicap_data),
        "has_correct_score_trade": bool(correct_score_data),
        "has_handicap_companies": bool(handicap_companies),
        "has_all_handicap_lines": bool(handicap_lines_info),
        "has_all_ou_lines": bool(ou_lines_info),
        "standard_count": standard_count,
        "ou_count": ou_count,
        "handicap_count": handicap_count,
        "correct_score_count": correct_score_count,
        "handicap_lines_count": len(handicap_lines_info),
        "ou_lines_count": len(ou_lines_info),
    }
    
    completeness = sum([
        summary["has_standard_trade"],
        summary["has_ou_trade"],
        summary["has_handicap_trade"],
        summary["has_correct_score_trade"],
    ])
    summary["completeness_score"] = completeness / 4.0
    summary["completeness_level"] = ["无数据", "基础", "中等", "良好", "完整"][completeness]
    
    result["summary"] = summary
    
    return result


def save_super_json(data: Dict, filepath: Union[str, Path]) -> None:
    """保存超级JSON到文件"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"[超级JSON] 已保存: {filepath}")


def load_super_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    """加载超级JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
