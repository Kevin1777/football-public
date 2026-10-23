"""检查数据中的联赛分布"""
import json
from pathlib import Path
from collections import Counter

# 扫描所有JSON
all_leagues = []
data_dir = Path("data")

for json_file in data_dir.rglob("2025-*.json"):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        league = data['match_info'].get('league', '')
        if league:
            all_leagues.append(league)
    except:
        pass

# 统计
league_counts = Counter(all_leagues)

print("联赛分布（前30）：")
for league, count in league_counts.most_common(30):
    print(f"{league:20s}: {count:4d} 场")

# V4目标联赛
tier1 = ['英超', '西甲', '德甲']
tier2 = ['意甲', '法甲', '葡超', '英冠', '荷甲']

tier1_count = sum(league_counts[l] for l in tier1)
tier2_count = sum(league_counts[l] for l in tier2)

print(f"\nV4目标联赛统计:")
print(f"Tier1 (英超/西甲/德甲): {tier1_count} 场")
print(f"Tier2 (意甲/法甲/葡超/英冠/荷甲): {tier2_count} 场")
print(f"合计: {tier1_count + tier2_count} 场 / {len(all_leagues)} 场 ({(tier1_count + tier2_count)/len(all_leagues)*100:.1f}%)")
