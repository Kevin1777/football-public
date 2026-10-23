#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web API是否使用V2模型
"""

import requests
import json

print("=" * 80)
print("🔍 测试Web API是否使用V2模型")
print("=" * 80)

# 准备测试数据
test_matches = [
    {
        "match_info": {
            "label": "2025-11-22 15:30 中超 北京国安 5-1 梅州客家",
            "league": "中超",
            "home": "北京国安",
            "away": "梅州客家",
            "kickoff": "2025-11-22 15:30"
        },
        "actual_score": [5, 1],
        "detail_url": "",
        "detail_params": {}
    }
]

# 调用批量回测API
url = "http://127.0.0.1:5001/api/backtest/batch"

print(f"\n请求URL: {url}")
print(f"比赛数量: {len(test_matches)}")

try:
    response = requests.post(url, json={"matches": test_matches}, timeout=30)
    
    print(f"\n响应状态: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n回测结果:")
        print(f"  总场次: {result.get('total', 0)}")
        print(f"  成功: {result.get('success_count', 0)}")
        print(f"  失败: {result.get('failed', 0)}")
        
        # 检查第一场比赛的推荐详情
        results = result.get('results', [])
        if results:
            first = results[0]
            recommendation = first.get('recommendation', {})
            
            print(f"\n第一场比赛推荐:")
            print(f"  版本: {recommendation.get('version', 'N/A')}")
            print(f"  引擎: {recommendation.get('engine', 'N/A')}")
            print(f"  方向: {recommendation.get('direction', 'N/A')}")
            print(f"  置信度: {recommendation.get('confidence', 0):.2f}")
            print(f"  理由: {recommendation.get('reason', 'N/A')}")
            
            # 检查是否是V2
            version = recommendation.get('version', '')
            engine = recommendation.get('engine', '')
            
            if 'V2' in version or 'v2' in engine:
                print(f"\n✅ 确认使用V2模型！")
            else:
                print(f"\n❌ 还在使用旧版本！")
                print(f"\n完整推荐数据:")
                print(json.dumps(recommendation, indent=2, ensure_ascii=False))
    else:
        print(f"\n❌ 请求失败: {response.text}")

except requests.exceptions.ConnectionError:
    print(f"\n❌ 无法连接到服务器，请确认服务器是否启动")
except Exception as e:
    print(f"\n❌ 错误: {e}")

print("\n" + "=" * 80)
