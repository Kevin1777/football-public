#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试列名"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser.html_parser import parse_bifa_html

html_file = sorted(Path('debug_html').glob('detail_success_*.html'), key=lambda p: p.stat().st_mtime, reverse=True)[0]
html = html_file.read_text(encoding='utf-8', errors='ignore')

print("="*60)
print(f"解析文件: {html_file.name}")
print("="*60)

result = parse_bifa_html(html)

if hasattr(result, 'columns'):
    print(f"\n✅ 解析成功！")
    print(f"数据行数: {len(result)}")
    print(f"数据列数: {len(result.columns)}")
    
    print(f"\n📋 所有列名 ({len(result.columns)}列):")
    for i, col in enumerate(result.columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\n🔍 前3行数据预览:")
    print(result.head(3).to_string(max_cols=10))
    
    # 检查是否有"总成交量"
    if '总成交量' in result.columns:
        print(f"\n✅ 找到'总成交量'列！")
        print(f"   前5个值: {result['总成交量'].head(5).tolist()}")
    else:
        print(f"\n❌ 未找到'总成交量'列！")
        print(f"   可能的原因：列名合并或命名问题")
else:
    print(f"❌ 解析失败: {result}")
