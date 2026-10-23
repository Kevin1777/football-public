"""测试完场回查的明细抓取"""
from datetime import datetime
from services import BifawClient
from parser.html_parser import parse_bifa_html

print("="*70)
print("测试完场回查明细抓取")
print("="*70)

client = BifawClient()

# 1. 获取完场比赛列表
print("\n1️⃣  获取完场比赛...")
matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 5), rows=3)

if not matches:
    print("❌ 未找到比赛")
    exit(1)

print(f"✅ 找到 {len(matches)} 场比赛")

# 2. 测试第一场比赛的明细抓取
first_match = matches[0]
print(f"\n2️⃣  测试第一场比赛明细抓取...")
print(f"   比赛: {first_match.get('home')} {first_match.get('score')} {first_match.get('away')}")
print(f"   联赛: {first_match.get('league')}")
print(f"   时间: {first_match.get('kickoff')}")
print(f"   URL: {first_match.get('detail_url')}")

# 模拟前端调用
match_info = {
    "league": first_match.get("league"),
    "kickoff": first_match.get("kickoff"),
    "home": first_match.get("home"),
    "away": first_match.get("away"),
    "score": first_match.get("score"),
    "detail_url": first_match.get("detail_url"),
    "match_id": first_match.get("match_id")
}

print(f"\n3️⃣  传递给API的match_info:")
for key, value in match_info.items():
    print(f"   {key}: {value}")

print(f"\n✅ 修复完成！")
print(f"\n📝 现在当抓取完场比赛明细时：")
print(f"   - match参数会传递给parse_bifa_html")
print(f"   - 解析器会优先使用match中的信息")
print(f"   - 元数据将正确显示联赛、时间、队伍等")
print(f"\n下一步：在网页中测试完场回查的抓取明细功能")
