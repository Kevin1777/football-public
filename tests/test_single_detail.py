#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试单个明细链接"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient
from parser.html_parser import parse_bifa_html

def test_single_detail():
    """测试单个明细链接"""
    print("="*80)
    print("测试单个明细链接抓取")
    print("="*80)
    
    # 使用你提供的链接
    test_url = "https://www.bifaw.com/bifaw/matchDetails.php?getuid=dG1paWQ9MzQ5NjU5MDkmbWFya2V0aWQ9MjUwNjUyNDAyJmhvbWVfc2lkPTMxNTc0OCZhd2F5X3NpZD00MTkwODcmb3BlbnRpbWU9MTc2MzM4ODAwMCZmZmY9MCZ0ZWFtbXNnPSVFNiVBQyVBNyVFNiVCNCVCMlUyMEAlRTUlQkUlQjclRTUlOUIlQkRVMjAoJUU0JUI4JUFEKUAlRTYlODQlOEYlRTUlQTQlQTclRTUlODglQTlVMjAmbmJzcDtAJm5ic3A7Jg=="
    
    print(f"\n测试URL:")
    print(f"{test_url[:100]}...")
    
    client = BifawClient()
    
    # 检查登录
    status = client.get_cookie_status()
    if not status.get("exists"):
        print("\n❌ 未登录，请先访问 http://127.0.0.1:5001/collect 完成登录")
        return
    
    print(f"\n✅ 已登录")
    
    try:
        print("\n开始抓取...")
        print("="*80)
        
        html = client.fetch_match_detail_selenium(
            detail_url=test_url,
            timeout=60  # 给足够的时间
        )
        
        if not html:
            print("❌ 未获取到HTML")
            return
        
        print(f"\n✅ 成功获取HTML，长度: {len(html):,} 字符")
        
        # 检查HTML中的关键内容
        keywords = ["成交时间", "买家挂牌", "卖家挂牌", "赔率", "<table"]
        found = [kw for kw in keywords if kw in html]
        print(f"\n关键字检查:")
        for kw in keywords:
            status = "✅" if kw in html else "❌"
            print(f"  {status} {kw}")
        
        if not found:
            print("\n⚠️  HTML中没有找到任何关键字")
            print("可能原因：")
            print("  1. 登录状态失效")
            print("  2. 页面加载超时")
            print("  3. 网站结构变化")
            print(f"\n请检查 debug_html 目录中的文件")
            return
        
        # 尝试解析
        print("\n开始解析HTML...")
        result = parse_bifa_html(html)
        
        if isinstance(result, pd.DataFrame) and not result.empty:
            print(f"✅ 解析成功！")
            print(f"   数据行数: {len(result)}")
            print(f"   数据列数: {len(result.columns)}")
            print(f"\n列名: {', '.join(result.columns[:10])}")
            print(f"\n前5行数据:")
            print(result.head().to_string())
            
            print("\n" + "="*80)
            print("🎉 测试成功！")
            print("="*80)
        elif isinstance(result, str):
            print(f"❌ 解析失败: {result}")
        else:
            print(f"❌ 未知结果类型: {type(result)}")
            
    except Exception as e:
        print(f"\n❌ 抓取失败: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n💡 提示：查看 debug_html 目录中的截图和HTML文件")

if __name__ == "__main__":
    import pandas as pd
    test_single_detail()
