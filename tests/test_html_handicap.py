#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试从HTML页面获取盘口数据
"""

import requests
from bs4 import BeautifulSoup

fid = "1353435"

print("=" * 80)
print(f"测试从HTML页面获取盘口数据 - FID: {fid}")
print("=" * 80)

url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"

print(f"\n访问: {url}")

# 添加浏览器headers避免被识别为爬虫
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Referer': 'https://odds.500.com/',
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    response.encoding = 'gb2312'
    
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        print(f"✅ 成功获取HTML！")
        print(f"响应长度: {len(response.text)} 字符")
        
        # 保存HTML
        with open(f"debug_yazhi_{fid}.html", 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"已保存到: debug_yazhi_{fid}.html")
        
        # 尝试查找盘口数据
        html = response.text
        
        # 搜索关键字
        keywords = ['一球/球半', '球半', '半球', '平手', '澳门', '初盘', '即时']
        found = []
        for kw in keywords:
            if kw in html:
                found.append(kw)
        
        if found:
            print(f"\n✅ 找到盘口关键字: {', '.join(found)}")
        else:
            print(f"\n⚠️  未找到盘口关键字")
        
        # 使用BeautifulSoup解析
        soup = BeautifulSoup(html, 'html.parser')
        
        # 查找可能包含盘口数据的表格或div
        tables = soup.find_all('table')
        print(f"\n找到 {len(tables)} 个表格")
        
        # 查找包含"澳门"的元素
        aomen_elements = soup.find_all(string=lambda text: text and '澳门' in text)
        if aomen_elements:
            print(f"找到 {len(aomen_elements)} 个包含'澳门'的元素")
            for i, elem in enumerate(aomen_elements[:3], 1):
                print(f"  {i}. {elem[:50]}...")
        
        # 显示前1000字符
        print(f"\nHTML前1000字符:")
        print(html[:1000])
        
    else:
        print(f"❌ 失败: {response.status_code}")
        if response.status_code == 403:
            print("403 Forbidden - 可能需要更复杂的反爬虫处理")
            
except Exception as e:
    print(f"❌ 请求异常: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 80}")
print("测试完成")
print(f"{'=' * 80}")
