"""检查数据中的凯利指数"""
import json
from pathlib import Path

# 随机检查几个数据文件
data_dir = Path("data/2025/11/09")
json_files = list(data_dir.glob("*.json"))[:5]

for json_file in json_files:
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n文件: {json_file.name}")
    print(f"联赛: {data['match_info'].get('league', 'N/A')}")
    
    trade_data = data.get('trade_data', {}).get('data', [])
    if trade_data:
        latest = trade_data[0]
        print(f"凯利_主: {latest.get('凯利_主', 'N/A')}")
        print(f"凯利_客: {latest.get('凯利_客', 'N/A')}")
        print(f"比例_主: {latest.get('比例_主', 'N/A')}")
        print(f"比例_客: {latest.get('比例_客', 'N/A')}")
        print(f"必指_主: {latest.get('必指_主', 'N/A')}")
        print(f"必指_客: {latest.get('必指_客', 'N/A')}")
