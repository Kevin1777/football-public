#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试Web API抓取明细"""

import requests
import json

def test_web_api():
    """测试Web API"""
    print("="*80)
    print("测试Web API抓取明细")
    print("="*80)
    
    base_url = "http://127.0.0.1:5001"
    
    # 1. 获取场次列表
    print("\n步骤1: 获取场次列表")
    response = requests.get(f"{base_url}/api/bifaw/matches?refresh=1&rows=20&days=1")
    
    if response.status_code != 200:
        print(f"❌ 获取场次失败: {response.status_code}")
        return
    
    matches = response.json()
    print(f"✅ 获取到 {len(matches)} 场比赛")
    
    if not matches:
        print("❌ 没有比赛数据")
        return
    
    # 检查有多少matchDetails.php链接
    match_details_count = sum(1 for m in matches if "matchDetails.php" in m.get("detail_url", ""))
    print(f"   其中 {match_details_count} 个使用 matchDetails.php 链接")
    
    # 2. 测试抓取第一场比赛
    first_match = matches[0]
    print(f"\n步骤2: 抓取明细")
    print(f"比赛: {first_match.get('label')}")
    print(f"URL: {first_match.get('detail_url')[:80]}...")
    
    if "matchDetails.php" in first_match.get('detail_url', ''):
        print("✅ 使用真实的 matchDetails.php 链接")
    
    # 发送抓取请求
    print("\n正在抓取...")
    payload = {
        "detail_url": first_match.get("detail_url"),
        "match": first_match,
        "use_selenium": True
    }
    
    response = requests.post(
        f"{base_url}/api/bifaw/match_detail",
        json=payload,
        timeout=60
    )
    
    if response.status_code != 200:
        print(f"❌ 抓取失败: {response.status_code}")
        print(f"响应: {response.text}")
        return
    
    result = response.json()
    
    if result.get("success"):
        print(f"✅ 抓取成功！")
        print(f"   数据行数: {result.get('row_count')}")
        print(f"   数据列数: {result.get('col_count')}")
        print(f"   消息: {result.get('message')}")
        
        print("\n" + "="*80)
        print("🎉 Web API测试成功！")
        print("="*80)
        print("\n💡 现在你可以：")
        print("   1. 打开浏览器访问 http://127.0.0.1:5001/collect")
        print("   2. 点击'获取场次'")
        print("   3. 选择任意比赛，点击'抓取明细'")
        print("   4. 查看数据表格")
    else:
        print(f"❌ 抓取失败: {result.get('message')}")

if __name__ == "__main__":
    test_web_api()
