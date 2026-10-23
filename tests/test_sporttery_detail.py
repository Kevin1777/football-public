"""测试sporttery.php是否能获取标盘明细"""
from datetime import datetime
from services import BifawClient
from bs4 import BeautifulSoup
import re

print("="*80)
print("🔍 测试 sporttery.php 是否有标盘明细数据")
print("="*80)

client = BifawClient()

# 1. 获取完场比赛
matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 5), rows=1)
first_match = matches[0]

print(f"\n【测试比赛】")
print(f"比赛: {first_match.get('home')} vs {first_match.get('away')}")
print(f"原始URL: {first_match.get('detail_url')}")

# 2. 测试不同的URL参数组合
base_url = f"https://www.bifaw.com/bifaw/sporttery.php"
match_id = first_match.get('match_id')

test_urls = [
    # 原始URL
    f"{base_url}?matchid={match_id}&type=1&oddstype=1&subtype=8",
    # 尝试不同的subtype
    f"{base_url}?matchid={match_id}&type=1&oddstype=1&subtype=1",
    f"{base_url}?matchid={match_id}&type=1&oddstype=1&subtype=2",
    # 尝试matchDetails
    f"https://www.bifaw.com/bifaw/matchDetails.php?id={match_id}",
    # 尝试不带参数
    f"{base_url}?matchid={match_id}",
]

print(f"\n【测试不同URL】")
print("-"*80)

for i, url in enumerate(test_urls, 1):
    print(f"\n测试 {i}: {url}")
    try:
        html = client.fetch_match_detail_selenium(
            detail_url=url,
            match=first_match
        )
        
        # 分析HTML
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        
        # 查找时间序列数据
        time_cells = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    text = cell.get_text(strip=True)
                    # 匹配时间格式：11-02 14:10 或 14:10:30
                    if re.search(r'\d{2}[-:]\d{2}.*\d{2}:\d{2}', text):
                        time_cells.append(text)
        
        max_rows = max([len(t.find_all("tr")) for t in tables]) if tables else 0
        
        print(f"   表格数: {len(tables)}")
        print(f"   最大行数: {max_rows}")
        print(f"   时间单元格数: {len(time_cells)}")
        
        if len(time_cells) >= 10:
            print(f"   ✅ 找到时间序列数据！样本:")
            for t in time_cells[:5]:
                print(f"      {t}")
        elif max_rows > 20:
            print(f"   ⚠️  有大量行但没有时间格式（可能是其他格式）")
        else:
            print(f"   ❌ 没有找到时间序列数据（可能只是汇总）")
            
        # 保存HTML用于检查
        debug_file = f"debug_html/sporttery_test_{i}.html"
        import os
        os.makedirs("debug_html", exist_ok=True)
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   📁 HTML已保存: {debug_file}")
        
    except Exception as e:
        print(f"   ❌ 错误: {e}")

print("\n" + "="*80)
print("测试完成！")
print("="*80)

print("\n【建议】")
print("1. 检查保存的HTML文件，找到包含时间序列数据的那个")
print("2. 对比URL参数，确定正确的参数组合")
print("3. 如果都没有，可能需要通过JavaScript交互才能获取明细")
