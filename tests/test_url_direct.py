#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试URL返回内容
"""

import requests

# 测试不同的URL格式
urls = [
    "https://live.500.com/wanchang.php?date=2025-11-18",
    "https://live.500.com/wanchang.php?date=20251118",
    "https://live.500.com/wanchang.php?date=2025/11/18",
    "https://live.500.com/wanchang.php",  # 不带参数
]

for url in urls:
    print(f"\n{'='*80}")
    print(f"测试URL: {url}")
    print('='*80)
    
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'gb2312'
        
        print(f"状态码: {response.status_code}")
        print(f"响应长度: {len(response.text)} 字符")
        
        # 搜索一些关键字
        keywords = ['曼城', '布莱顿', '切尔西', '阿森纳', '英超', 'Premier', '2025-11-18', '11-18']
        found = []
        for kw in keywords:
            if kw in response.text:
                found.append(kw)
        
        if found:
            print(f"✅ 找到关键字: {', '.join(found)}")
        else:
            print(f"❌ 未找到任何关键字")
            
        # 显示前500个字符
        print(f"\n前500字符预览:")
        print(response.text[:500])
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")

print(f"\n{'='*80}")
print("测试完成")
print(f"{'='*80}")
