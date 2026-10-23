#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

# 读取HTML文件
with open(r"d:\MSM\Cursor\football\debug_html\500_finished_20251117_坦皮科马德罗_vs_哥达拿查拉大学.html", 'r', encoding='utf-8') as f:
    html = f.read()

print(f"HTML长度: {len(html)}")

# 测试正则表达式
pattern = r'(.{0,500})(shuju|yazhi|ouzhi|fenxi)-(\d+)\.shtml(.{0,500})'

matches = list(re.finditer(pattern, html))

print(f"\n找到 {len(matches)} 个匹配")

# 显示前5个匹配
for i, match in enumerate(matches[:5], 1):
    context_before = match.group(1)
    url_type = match.group(2)
    fid = match.group(3)
    context_after = match.group(4)
    
    print(f"\n匹配 {i}:")
    print(f"  URL类型: {url_type}")
    print(f"  FID: {fid}")
    print(f"  前文(最后100字): ...{context_before[-100:]}")
    print(f"  后文(前100字): {context_after[:100]}...")
    
    # 检查是否包含时间
    time_pattern = r'(\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})'
    time_match = re.search(time_pattern, context_before + context_after)
    if time_match:
        print(f"  时间: {time_match.group(1)}")
    
    # 检查是否包含联赛
    league_pattern = r'gy="([^",]+)'
    league_match = re.search(league_pattern, context_before + context_after)
    if league_match:
        print(f"  联赛: {league_match.group(1)}")
