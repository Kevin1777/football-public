#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试使用Selenium获取动态生成的matchDetails.php链接
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient

def test_selenium_links():
    """测试Selenium获取链接"""
    print("="*80)
    print("开始测试Selenium获取动态链接...")
    print("="*80)
    
    client = BifawClient()
    
    # 检查登录状态
    status = client.get_cookie_status()
    if not status.get("exists"):
        print("\n❌ 未登录，请先访问 http://127.0.0.1:5001/collect 完成登录")
        return
    
    print(f"\n✅ 已登录 (最后更新: {status.get('updated_at')})")
    
    # 使用Selenium获取场次列表
    print("\n" + "="*80)
    print("正在使用Selenium访问页面并获取场次...")
    print("="*80)
    
    try:
        matches = client.fetch_match_list_v2(rows=10, days=1, force_refresh=True)
        
        print(f"\n成功获取 {len(matches)} 场比赛\n")
        
        if matches:
            print("前5场比赛的链接：")
            print("-"*80)
            for i, match in enumerate(matches[:5], 1):
                label = match.get("label", "未知比赛")
                detail_url = match.get("detail_url", "")
                
                print(f"\n{i}. {label}")
                print(f"   URL: {detail_url}")
                
                # 检查是否是matchDetails.php链接
                if "matchDetails.php" in detail_url:
                    print("   ✅ 这是正确的 matchDetails.php 链接！")
                elif "sporttery.php" in detail_url:
                    print("   ⚠️  这是 sporttery.php 链接（可能不是真正的明细页面）")
                else:
                    print("   ❓ 未知链接类型")
        else:
            print("未获取到任何比赛")
            
    except Exception as e:
        print(f"\n❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_selenium_links()
