#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试盘口数据API的URL
"""

import requests

# 从前面成功匹配的比赛ID测试
fid = "1353435"  # 坦皮科马德罗 vs 瓜达拉哈拉大学
company_id = "3"  # 澳门盘

print("=" * 80)
print(f"测试盘口数据API - FID: {fid}")
print("=" * 80)

# 尝试多种可能的URL格式
urls = [
    f"https://odds.500.com/fenxi/inc/yazhiAjax.php?fid={fid}&cid={company_id}",  # 原URL
    f"https://odds.500.com/fenxi/yazhi-{fid}.shtml",  # 亚洲盘页面
    f"https://live.500.com/ajax/handicap.php?fid={fid}",  # 可能的Ajax接口
    f"https://odds.500.com/api/handicap?fid={fid}&cid={company_id}",  # 可能的API
]

for i, url in enumerate(urls, 1):
    print(f"\n{'-' * 80}")
    print(f"尝试 {i}: {url}")
    print('-' * 80)
    
    try:
        response = requests.get(url, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ 成功！")
            print(f"响应长度: {len(response.text)} 字符")
            print(f"内容类型: {response.headers.get('Content-Type', 'N/A')}")
            
            # 显示前500字符
            print(f"\n前500字符预览:")
            print(response.text[:500])
            
            # 保存完整响应
            filename = f"debug_handicap_{fid}_url{i}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"\n已保存到: {filename}")
            
            break  # 找到可用的URL就停止
        else:
            print(f"❌ 失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

print(f"\n{'=' * 80}")
print("测试完成")
print(f"{'=' * 80}")
print("\n建议：")
print("1. 打开浏览器访问 https://odds.500.com/fenxi/yazhi-1353435.shtml")
print("2. 按F12打开开发者工具")
print("3. 切换到Network标签")
print("4. 刷新页面")
print("5. 查找包含盘口数据的XHR请求")
print("6. 把那个URL告诉我")
