#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试标题提取"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser.html_parser import parse_bifa_html

html_file = Path('debug_html/detail_success_20251117_202611.html')
html = html_file.read_text(encoding='utf-8', errors='ignore')

print("="*60)
print("测试标题提取")
print("="*60)

result = parse_bifa_html(html)

if hasattr(result, 'attrs'):
    metadata = result.attrs.get('metadata', [])
    if metadata:
        meta = metadata[0]
        title_meta = meta.get('title_meta', {})
        
        print(f"\n✅ 标题信息:")
        print(f"  联赛: {title_meta.get('league')}")
        print(f"  时间: {title_meta.get('datetime')}")
        print(f"  主队: {title_meta.get('home')}")
        print(f"  客队: {title_meta.get('away')}")
        
        # 生成显示标题
        league = title_meta.get('league') or '未知联赛'
        datetime = title_meta.get('datetime') or '未知时间'
        home = title_meta.get('home') or '主队?'
        away = title_meta.get('away') or '客队?'
        
        print(f"\n📋 显示标题:")
        print(f"  {league} · {datetime}")
        print(f"  {home} vs {away}")
        
    else:
        print("❌ 未找到metadata")
else:
    print("❌ 解析失败")
