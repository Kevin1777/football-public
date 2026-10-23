#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试API响应格式"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser.html_parser import parse_bifa_html

html_file = Path('debug_html/detail_success_20251117_202611.html')
html = html_file.read_text(encoding='utf-8', errors='ignore')

print("="*60)
print("模拟API响应")
print("="*60)

result = parse_bifa_html(html)

if hasattr(result, 'attrs'):
    metadata = result.attrs.get('metadata', [])
    
    print("\n📦 API返回的metadata:")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    
    if metadata:
        meta = metadata[0]
        title_meta = meta.get('title_meta', {})
        
        print("\n🎯 前端应该显示:")
        datetime = title_meta.get('datetime') or '未知时间'
        league = title_meta.get('league') or '未知联赛'
        home = title_meta.get('home') or '主队?'
        away = title_meta.get('away') or '客队?'
        
        display_title = f"{datetime} · {league} · {home} vs {away}"
        print(f"  {display_title}")
        
        # 模拟前端代码
        print("\n💻 前端代码执行:")
        print(f"  const {{ league, datetime, home, away }} = item.title_meta;")
        print(f"  league = '{league}'")
        print(f"  datetime = '{datetime}'")
        print(f"  home = '{home}'")
        print(f"  away = '{away}'")
        print(f"  显示: {display_title}")
