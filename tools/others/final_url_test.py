"""最终URL测试 - 直接测试matchDetails.php"""
from datetime import datetime
from services import BifawClient
from bs4 import BeautifulSoup
import re

print("="*80)
print("🎯 最终测试：找到正确的标盘明细URL")
print("="*80)

client = BifawClient()

# 获取完场比赛
matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 5), rows=1)
first_match = matches[0]
match_id = first_match.get('match_id')

print(f"\n【测试比赛】")
print(f"比赛: {first_match.get('home')} vs {first_match.get('away')}")
print(f"matchid: {match_id}")
print(f"原始URL: {first_match.get('detail_url')}")

# 基于页面中的onclick调用，尝试不同的URL格式
test_configs = [
    {
        "name": "matchDetails - 完场专用",
        "url": f"https://www.bifaw.com/bifaw/matchDetails.php?matchid={match_id}&fff=4",
        "desc": "使用matchid参数 + fff=4标记完场"
    },
    {
        "name": "matchDetails - 标准格式",
        "url": f"https://www.bifaw.com/bifaw/matchDetails.php?matchid={match_id}",
        "desc": "使用matchid参数"
    },
    {
        "name": "matchDetails - ID参数",
        "url": f"https://www.bifaw.com/bifaw/matchDetails.php?id={match_id}",
        "desc": "使用id参数"
    },
    {
        "name": "historysporttery - 完场明细",
        "url": f"https://www.bifaw.com/bifaw/historysporttery.php?matchid={match_id}",
        "desc": "完场专用明细页面"
    },
]

results = []

for config in test_configs:
    print(f"\n{'='*80}")
    print(f"测试: {config['name']}")
    print(f"说明: {config['desc']}")
    print(f"URL: {config['url']}")
    print("-"*80)
    
    try:
        html = client.fetch_match_detail_selenium(
            detail_url=config['url'],
            match=first_match
        )
        
        # 分析HTML
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        
        # 查找时间序列数据的特征
        time_cells = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    text = cell.get_text(strip=True)
                    # 匹配明细时间格式：11-02 14:10
                    if re.match(r'\d{2}-\d{2}\s+\d{2}:\d{2}', text):
                        time_cells.append(text)
        
        max_rows = max([len(t.find_all("tr")) for t in tables]) if tables else 0
        
        # 检查是否有"成交时间"列头
        has_time_header = "成交时间" in html
        
        result = {
            "url": config['url'],
            "tables": len(tables),
            "max_rows": max_rows,
            "time_cells": len(time_cells),
            "has_time_header": has_time_header
        }
        results.append(result)
        
        print(f"结果:")
        print(f"  表格数: {len(tables)}")
        print(f"  最大行数: {max_rows}")
        print(f"  时间单元格数: {len(time_cells)}")
        print(f"  包含'成交时间': {has_time_header}")
        
        # 判断是否成功
        if time_cells and has_time_header and max_rows > 20:
            print(f"\n  ✅ 成功！这是标盘明细页面")
            print(f"  时间数据样本:")
            for t in time_cells[:5]:
                print(f"    {t}")
                
            # 保存HTML
            debug_file = f"debug_html/SUCCESS_{config['name'].replace(' ', '_')}.html"
            import os
            os.makedirs("debug_html", exist_ok=True)
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  📁 HTML已保存: {debug_file}")
            print(f"\n  🎉 找到正确的URL格式！")
            break
        else:
            print(f"  ❌ 这不是标盘明细页面（可能是汇总页面）")
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        results.append({
            "url": config['url'],
            "error": str(e)
        })

# 总结
print(f"\n\n{'='*80}")
print("【测试总结】")
print("="*80)

for i, result in enumerate(results, 1):
    print(f"\n{i}. {result.get('url', 'ERROR')}")
    if 'error' in result:
        print(f"   ❌ 错误: {result['error']}")
    else:
        print(f"   表格: {result['tables']}, 最大行数: {result['max_rows']}, 时间单元格: {result['time_cells']}")
        if result['time_cells'] > 0 and result['max_rows'] > 20:
            print(f"   ✅ 这是明细页面！")
        else:
            print(f"   ⚠️  这是汇总页面")

print(f"\n{'='*80}")
print("测试完成！")
print("="*80)
