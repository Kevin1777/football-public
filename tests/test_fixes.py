"""测试所有修复"""
from datetime import datetime
from services import BifawClient

print("="*70)
print("测试修复结果")
print("="*70)

client = BifawClient()

# 测试1: 比分是否正确
print("\n1️⃣  测试比分解析...")
matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 5), rows=5)

if matches:
    print(f"✅ 找到 {len(matches)} 场比赛")
    print("\n前3场比赛：")
    for i, match in enumerate(matches[:3], 1):
        print(f"\n  {i}. {match.get('league')}")
        print(f"     {match.get('home')} {match.get('score')} {match.get('away')}")
        print(f"     时间: {match.get('kickoff')}")
else:
    print("❌ 未找到比赛")

# 测试2: 排序是否正确（最新的在前）
print("\n\n2️⃣  测试排序...")
if len(matches) >= 2:
    first_time = matches[0].get('kickoff', '')
    last_time = matches[-1].get('kickoff', '')
    print(f"第一场: {first_time}")
    print(f"最后一场: {last_time}")
    if first_time >= last_time:
        print("✅ 排序正确（倒序，最新在前）")
    else:
        print("⚠️  排序可能不对")

print("\n" + "="*70)
print("测试完成！")
print("="*70)
print("\n下一步：")
print("1. 运行 'python app.py' 启动服务器")
print("2. 访问 http://fb.kevinsun7.dpdns.org（或localhost:5001）")
print("3. 查看采集控制台（现在是首页）")
print("4. 测试完场回查功能，验证比分显示")
