"""检查V4拒绝原因"""
import json

data = json.load(open('backtest_详细结果_20251126_165756.json', encoding='utf-8'))

target_leagues = ['英超', '西甲', '德甲', '意甲', '法甲', '葡超', '英冠', '荷甲']

targets = [r for r in data['results'] if r['match_info'].get('league') in target_leagues]

print(f"目标联赛比赛总数: {len(targets)}")
print()

if targets:
    print("前10场目标联赛的拒绝原因:")
    for r in targets[:10]:
        league = r['match_info']['league']
        reason = r['recommendation'].get('reason', 'N/A')
        # 只显示字符串原因
        if isinstance(reason, str):
            print(f"{league}: {reason[:80]}")
        else:
            print(f"{league}: <非字符串原因>")
else:
    print("未找到目标联赛比赛！")
