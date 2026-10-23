#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""直接测试解析保存的HTML"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser.html_parser import parse_bifa_html
from bs4 import BeautifulSoup

# 读取最新的HTML文件
html_files = sorted(Path('debug_html').glob('detail_success_*.html'), key=lambda p: p.stat().st_mtime, reverse=True)

if not html_files:
    print("未找到HTML文件")
    sys.exit(1)

latest_file = html_files[0]
print(f"测试文件: {latest_file.name}\n")

html = latest_file.read_text(encoding='utf-8', errors='ignore')

# 先用BeautifulSoup直接检查
print("="*80)
print("BeautifulSoup直接检查:")
print("="*80)

soup = BeautifulSoup(html, 'html.parser')
all_tables = soup.find_all('table')
print(f"找到 {len(all_tables)} 个table标签\n")

for idx, table in enumerate(all_tables, 1):
    table_id = table.get('id', 'no-id')
    table_class = table.get('class', [])
    
    # 检查tr和td
    all_trs = table.find_all('tr')
    all_tds = table.find_all('td')
    
    print(f"{idx}. ID:{table_id}, Class:{table_class}")
    print(f"   find_all('tr'): {len(all_trs)}")
    print(f"   find_all('td'): {len(all_tds)}")
    
    if len(all_tds) > 10:
        print(f"   ✅ 这个表格有数据！")
        # 显示第一个td的内容
        first_td = all_tds[0]
        print(f"   第一个<td>内容: {first_td.get_text(strip=True)}")

print("\n" + "="*80)
print("使用parse_bifa_html解析:")
print("="*80)

result = parse_bifa_html(html)

if isinstance(result, str):
    print(f"❌ 解析失败: {result}")
else:
    import pandas as pd
    if isinstance(result, pd.DataFrame):
        print(f"✅ 解析成功！")
        print(f"   数据行数: {len(result)}")
        print(f"   数据列数: {len(result.columns)}")
        print(f"\n列名: {list(result.columns)}")
        print(f"\n前3行:")
        print(result.head(3).to_string())
