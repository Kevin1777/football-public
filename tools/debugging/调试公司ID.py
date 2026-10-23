"""
调试博彩公司ID对应关系
查看HTML中所有公司的ID和名称
"""
import requests
from bs4 import BeautifulSoup

fid = "1185975"  # 山东泰山 vs 天津津门虎
url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"

print(f"URL: {url}\n")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

response = requests.get(url, headers=headers, timeout=10)
response.encoding = 'gb2312'

print("=" * 80)
print("亚洲盘口公司列表")
print("=" * 80)

soup = BeautifulSoup(response.text, 'html.parser')

# 查找所有带id的tr（博彩公司行）
all_rows = soup.find_all('tr', id=True)

print(f"找到 {len(all_rows)} 个博彩公司\n")

for idx, row in enumerate(all_rows[:30], 1):  # 前30家
    row_id = row.get('id', '')
    
    # 提取公司名称（通常在第一个td中）
    tds = row.find_all('td', recursive=False)
    company_name = "未知"
    
    for td in tds[:3]:  # 检查前3个td
        text = td.get_text(strip=True)
        # 公司名称通常不是数字且长度合理
        if text and not text.replace('.', '').replace('↑', '').replace('↓', '').isdigit() and len(text) < 20:
            # 排除特殊字符
            if text not in ['水', '盘', '值', '初', '即']:
                company_name = text
                break
    
    # 查找盘口数据表格
    tables = row.find_all('table', class_='pl_table_data')
    
    if len(tables) >= 2:
        # 即时盘（第一个table）
        current_table = tables[0]
        current_tds = current_table.find_all('td')
        if len(current_tds) >= 3:
            current_home = current_tds[0].get_text(strip=True)
            current_handicap_td = current_tds[1]
            current_handicap = current_handicap_td.get_text(strip=True)
            current_away = current_tds[2].get_text(strip=True)
        else:
            current_home = current_handicap = current_away = "N/A"
        
        # 初盘（第二个table）
        initial_table = tables[1]
        initial_tds = initial_table.find_all('td')
        if len(initial_tds) >= 3:
            initial_home = initial_tds[0].get_text(strip=True)
            initial_handicap = initial_tds[1].get_text(strip=True)
            initial_away = initial_tds[2].get_text(strip=True)
        else:
            initial_home = initial_handicap = initial_away = "N/A"
        
        # 清理盘口文本（去除升降标记和箭头）
        import re
        current_handicap = re.sub(r'[升降↑↓]', '', current_handicap).strip()
        initial_handicap = re.sub(r'[升降↑↓]', '', initial_handicap).strip()
        
        print(f"{idx:2d}. ID={row_id:<4} 【{company_name}】")
        print(f"    初盘: {initial_home:<7} {initial_handicap:<15} {initial_away:<7}")
        print(f"    即时: {current_home:<7} {current_handicap:<15} {current_away:<7}")
        
        # 特别标注重要公司
        if '澳门' in company_name or '88' in row_id:
            print(f"    ⭐⭐⭐ 这是澳门盘！")
        elif 'Bet365' in company_name or '35' == row_id:
            print(f"    ⭐⭐ Bet365")
        elif '立博' in company_name or '4' == row_id:
            print(f"    ⭐⭐ 立博")
        
        print()

print("\n" + "=" * 80)
print("根据上面的列表，找到澳门盘对应的ID")
print("=" * 80)
