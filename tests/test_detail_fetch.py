#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试使用真实链接抓取明细数据"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient
from parser.html_parser import parse_bifa_html

def test_detail_fetch():
    """测试抓取明细"""
    print("="*80)
    print("测试使用真实链接抓取明细数据")
    print("="*80)
    
    # 读取捕获的链接
    json_files = list(Path('debug_html').glob('captured_links_*.json'))
    if not json_files:
        print("\n❌ 未找到捕获的链接文件，请先运行 auto_capture_links.py")
        return
    
    latest_json = sorted(json_files)[-1]
    print(f"\n读取文件: {latest_json.name}")
    
    with open(latest_json, 'r', encoding='utf-8') as f:
        links = json.load(f)
    
    if not links:
        print("❌ 文件中没有链接")
        return
    
    print(f"找到 {len(links)} 个链接\n")
    
    # 使用第一个链接测试
    test_link = links[0]
    test_url = test_link['url']
    
    print(f"测试链接:")
    print(f"  标题: {test_link['title']}")
    print(f"  URL: {test_url[:80]}...")
    
    # 初始化客户端
    client = BifawClient()
    
    # 检查登录
    status = client.get_cookie_status()
    if not status.get("exists"):
        print("\n❌ 未登录")
        return
    
    print(f"\n✅ 已登录")
    print("\n开始抓取...")
    
    try:
        # 使用Selenium抓取
        html = client.fetch_match_detail_selenium(detail_url=test_url, timeout=20)
        
        if html:
            print(f"✅ 成功获取HTML，长度: {len(html):,} 字符")
            
            # 检查关键内容
            keywords = ['买家挂牌', '卖家挂牌', '成交量', 'Back', 'Lay']
            found_keywords = [kw for kw in keywords if kw in html]
            
            print(f"\n找到的关键字: {', '.join(found_keywords) if found_keywords else '无'}")
            
            # 尝试解析
            print("\n尝试解析HTML...")
            result = parse_bifa_html(html)
            
            if result:
                print(f"✅ 解析成功！")
                print(f"   主队: {result.get('home_team', '未知')}")
                print(f"   客队: {result.get('away_team', '未知')}")
                print(f"   赛事: {result.get('league', '未知')}")
                
                df = result.get('df')
                if df is not None and not df.empty:
                    print(f"   数据行数: {len(df)}")
                    print(f"\n前5行数据:")
                    print(df.head().to_string())
                else:
                    print("   ⚠️  数据表为空")
            else:
                print("❌ 解析失败，返回None")
                
        else:
            print("❌ 未获取到HTML")
            
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_detail_fetch()
