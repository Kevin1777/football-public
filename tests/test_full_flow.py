#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试完整的抓取流程"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient
from parser.html_parser import parse_bifa_html

def test_full_flow():
    """测试完整流程"""
    print("="*80)
    print("测试完整抓取流程")
    print("="*80)
    
    client = BifawClient()
    
    # 检查登录
    status = client.get_cookie_status()
    if not status.get("exists"):
        print("\n❌ 未登录")
        return
    
    print(f"\n✅ 已登录")
    
    # 1. 获取场次列表（会自动捕获真实链接）
    print("\n" + "="*80)
    print("步骤1: 获取场次列表")
    print("="*80)
    
    matches = client.fetch_match_list_v2(rows=20, days=1, force_refresh=True)
    
    if not matches:
        print("❌ 未获取到场次")
        return
    
    print(f"\n✅ 获取到 {len(matches)} 场比赛")
    
    # 检查是否有matchDetails.php链接
    match_details_count = sum(1 for m in matches if "matchDetails.php" in m.get("detail_url", ""))
    print(f"   其中 {match_details_count} 个使用 matchDetails.php 链接")
    
    # 2. 测试抓取第一场比赛的明细
    if matches:
        print("\n" + "="*80)
        print("步骤2: 抓取第一场比赛的明细")
        print("="*80)
        
        first_match = matches[0]
        print(f"\n比赛: {first_match.get('label')}")
        print(f"URL: {first_match.get('detail_url')[:80]}...")
        
        if "matchDetails.php" in first_match.get('detail_url', ''):
            print("✅ 使用真实的 matchDetails.php 链接")
        else:
            print("⚠️  使用备用链接")
        
        try:
            print("\n开始抓取...")
            html = client.fetch_match_detail_selenium(
                detail_url=first_match.get('detail_url'),
                timeout=20
            )
            
            if html:
                print(f"✅ 成功获取HTML，长度: {len(html):,} 字符")
                
                # 解析
                print("\n尝试解析HTML...")
                result = parse_bifa_html(html)
                
                if isinstance(result, dict):
                    df = result.get('df')
                    if df is not None and not df.empty:
                        print(f"✅ 解析成功！数据行数: {len(df)}")
                        print(f"\n前5行数据:")
                        print(df.head().to_string())
                        
                        print("\n" + "="*80)
                        print("🎉 测试成功！系统已能正常抓取明细数据")
                        print("="*80)
                    else:
                        print("⚠️  数据表为空")
                elif isinstance(result, str):
                    print(f"⚠️  parse_bifa_html返回了字符串而不是字典")
                    print(f"返回内容: {result[:200]}...")
                    print("\n💡 提示：可能需要使用 parse_bifa_pdf 或其他解析函数")
                else:
                    print(f"❌ 解析失败，返回类型: {type(result)}")
            else:
                print("❌ 未获取到HTML")
                
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_full_flow()
