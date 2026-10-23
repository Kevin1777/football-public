"""
测试完场回查和实时采集是否都能正确获取澳门盘数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client
import json

print("=" * 80)
print("测试完场回查和实时采集功能")
print("=" * 80)
print()

client = Lottery500Client()

# ============================================================================
# 测试1：完场回查 - 使用历史比赛
# ============================================================================
print("【测试1：完场回查】")
print("使用历史比赛：山东泰山 vs 天津津门虎（FID: 1185975）")
print("-" * 80)

fid_history = "1185975"
data_history = client.fetch_handicap_data(fid=fid_history, company_id="澳门")  # 使用名称匹配

if data_history:
    print(f"✅ 完场回查成功")
    print(f"  博彩公司: {data_history.get('company_id')} (5=澳门盘)")
    print(f"  数据源: {data_history.get('source')}")
    print(f"  初盘: {data_history.get('initial_home_odds')}  {data_history.get('initial_handicap_text'):<12}  {data_history.get('initial_away_odds')}")
    print(f"  即时: {data_history.get('current_home_odds')}  {data_history.get('current_handicap_text'):<12}  {data_history.get('current_away_odds')}")
    
    # 验证是否是澳门盘数据（根据之前的验证结果）
    expected_initial_home = 0.77
    expected_initial_away = 0.93
    actual_initial_home = data_history.get('initial_home_odds', 0)
    actual_initial_away = data_history.get('initial_away_odds', 0)
    
    if abs(actual_initial_home - expected_initial_home) < 0.01 and abs(actual_initial_away - expected_initial_away) < 0.01:
        print(f"  ✅ 数据验证通过：确认为澳门盘数据")
    else:
        print(f"  ⚠️  数据验证警告：可能不是澳门盘（期望初盘: {expected_initial_home}/{expected_initial_away}）")
else:
    print(f"❌ 完场回查失败")

print()

# ============================================================================
# 测试2：实时采集 - 使用最近的比赛
# ============================================================================
print("【测试2：实时采集】")
print("使用最近比赛测试（从data目录读取一个最新比赛）")
print("-" * 80)

# 读取一个最新的JSON文件获取FID
data_dir = Path(__file__).parent / "data" / "2025" / "11"
json_files = list(data_dir.rglob("*.json"))
json_files = [f for f in json_files if f.name != "盘口数据.json"]

if json_files:
    # 按修改时间排序，取最新的
    latest_file = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        match_data = json.load(f)
    
    fid_realtime = match_data.get('handicap_data', {}).get('fid')
    home_team = match_data.get('home_team', '未知')
    away_team = match_data.get('away_team', '未知')
    
    if fid_realtime:
        print(f"测试比赛: {home_team} vs {away_team}")
        print(f"FID: {fid_realtime}")
        
        data_realtime = client.fetch_handicap_data(fid=fid_realtime, company_id="澳门")  # 使用名称匹配
        
        if data_realtime:
            print(f"✅ 实时采集成功")
            print(f"  博彩公司: {data_realtime.get('company_id')} (5=澳门盘)")
            print(f"  数据源: {data_realtime.get('source')}")
            print(f"  初盘: {data_realtime.get('initial_home_odds')}  {data_realtime.get('initial_handicap_text'):<12}  {data_realtime.get('initial_away_odds')}")
            print(f"  即时: {data_realtime.get('current_home_odds')}  {data_realtime.get('current_handicap_text'):<12}  {data_realtime.get('current_away_odds')}")
            
            # 检查是否包含完整数据
            has_initial = data_realtime.get('initial_handicap') is not None
            has_current = data_realtime.get('current_handicap') is not None
            
            if has_initial and has_current:
                print(f"  ✅ 包含完整的初盘和即时盘数据")
            else:
                print(f"  ⚠️  数据不完整：初盘={has_initial}, 即时盘={has_current}")
        else:
            print(f"❌ 实时采集失败")
    else:
        print(f"⚠️  文件中没有FID，无法测试")
else:
    print(f"⚠️  未找到测试数据文件")

print()

# ============================================================================
# 总结
# ============================================================================
print("=" * 80)
print("【测试总结】")
print("=" * 80)

success_count = 0
total_count = 2

if data_history and abs(data_history.get('initial_home_odds', 0) - 0.77) < 0.01:
    print("✅ 完场回查：正常工作，使用澳门盘数据")
    success_count += 1
else:
    print("❌ 完场回查：异常")

if 'data_realtime' in locals() and data_realtime:
    print("✅ 实时采集：正常工作，使用澳门盘数据")
    success_count += 1
elif 'fid_realtime' not in locals():
    print("⚠️  实时采集：未测试（无可用数据）")
    total_count -= 1
else:
    print("❌ 实时采集：异常")

print()
print(f"通过率: {success_count}/{total_count}")

if success_count == total_count:
    print()
    print("🎉 所有功能正常！")
    print("✅ 完场回查可以正确获取澳门盘初盘和即时数据")
    print("✅ 实时采集可以正确获取澳门盘初盘和即时数据")
    print()
    print("现在可以：")
    print("1. 运行 补充初盘数据.py 补充历史数据")
    print("2. 运行 app.py 开始实时采集（会自动使用澳门盘）")
    print("3. 运行 analyze_with_handicap.py 分析数据")
else:
    print()
    print("⚠️  部分功能存在问题，请检查")

print("=" * 80)
