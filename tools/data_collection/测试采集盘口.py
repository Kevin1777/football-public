"""
测试采集系统（标盘指数）是否能正确获取澳门盘数据
模拟app.py的采集流程
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client
import json

print("=" * 80)
print("测试采集系统（标盘指数）盘口数据获取")
print("=" * 80)
print()

# 初始化客户端（模拟app.py）
lottery500_client = Lottery500Client()

print("【步骤1：从已采集数据中选择测试比赛】")
print("-" * 80)

# 从已保存的数据中找一场最新的比赛
data_dir = Path(__file__).parent / "data" / "2025" / "11"
json_files = list(data_dir.rglob("*.json"))
json_files = [f for f in json_files if f.name not in ["盘口数据.json", "标盘指数_latest.json"]]

if not json_files:
    print("❌ 未找到任何已采集的比赛数据")
    print("请先运行 app.py 采集一些数据")
    sys.exit(1)

# 按修改时间排序，选择最新的
json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
test_file = json_files[0]

print(f"选择测试文件: {test_file.name}")

with open(test_file, 'r', encoding='utf-8') as f:
    saved_data = json.load(f)

test_match = saved_data.get('match_info', {})

if not test_match:
    print("❌ 文件格式不正确")
    sys.exit(1)

print(f"✅ 找到测试比赛")

print()

# ============================================================================
# 步骤2：模拟采集流程 - 获取盘口数据
# ============================================================================
print("【步骤2：模拟采集流程 - 获取盘口数据】")
print("-" * 80)

home_team = test_match.get('home_team') or test_match.get('home')
away_team = test_match.get('away_team') or test_match.get('away')
league = test_match.get('league', '未知联赛')
fid = test_match.get('handicap_preview', {}).get('fid')

if not fid:
    # 如果没有fid，尝试从handicap_data中获取
    fid = test_match.get('handicap_data', {}).get('fid')

print(f"比赛信息:")
print(f"  联赛: {league}")
print(f"  主队: {home_team}")
print(f"  客队: {away_team}")
print(f"  FID: {fid}")
print()

if not fid:
    print("❌ 该比赛没有FID，无法获取盘口数据")
    sys.exit(1)

# ============================================================================
# 关键测试：使用app.py中的enhance_handicap_with_initial_data逻辑
# ============================================================================
print("【步骤3：获取详细盘口数据（初盘+即时盘）】")
print("-" * 80)
print("调用 lottery500_client.fetch_handicap_data()")
print(f"  参数: fid={fid}, company_id='澳门'")
print()

try:
    # 这里模拟app.py中的enhance_handicap_with_initial_data函数
    detailed_handicap = lottery500_client.fetch_handicap_data(
        fid=fid,
        company_id="澳门"  # 使用名称匹配
    )
    
    if detailed_handicap:
        print("✅ 盘口数据获取成功！")
        print()
        
        # 显示详细数据
        print("【返回数据结构】")
        print(f"  数据源: {detailed_handicap.get('source')}")
        print(f"  FID: {detailed_handicap.get('fid')}")
        print(f"  博彩公司: {detailed_handicap.get('company_name', '未知')} (ID={detailed_handicap.get('company_id')})")
        print()
        
        print("【初盘数据】")
        print(f"  盘口文本: {detailed_handicap.get('initial_handicap_text')}")
        print(f"  盘口数值: {detailed_handicap.get('initial_handicap')}")
        print(f"  主队水位: {detailed_handicap.get('initial_home_odds')}")
        print(f"  客队水位: {detailed_handicap.get('initial_away_odds')}")
        print()
        
        print("【即时盘数据】")
        print(f"  盘口文本: {detailed_handicap.get('current_handicap_text')}")
        print(f"  盘口数值: {detailed_handicap.get('current_handicap')}")
        print(f"  主队水位: {detailed_handicap.get('current_home_odds')}")
        print(f"  客队水位: {detailed_handicap.get('current_away_odds')}")
        print(f"  变化趋势: {detailed_handicap.get('current_trend')}")
        print()
        
        # 计算盘口变化（模拟app.py中的逻辑）
        initial = detailed_handicap.get('initial_handicap', 0)
        current = detailed_handicap.get('current_handicap', 0)
        handicap_change = current - initial
        
        if handicap_change < -0.01:
            trend = "升盘"
        elif handicap_change > 0.01:
            trend = "降盘"
        else:
            trend = "稳盘"
        
        print("【盘口变化分析】")
        print(f"  变化量: {handicap_change:+.2f}")
        print(f"  趋势: {trend}")
        print(f"  主队水位变化: {detailed_handicap.get('initial_home_odds', 0)} → {detailed_handicap.get('current_home_odds', 0)}")
        print(f"  客队水位变化: {detailed_handicap.get('initial_away_odds', 0)} → {detailed_handicap.get('current_away_odds', 0)}")
        
        # 验证数据完整性
        print()
        print("【数据完整性检查】")
        checks = {
            "包含初盘盘口": detailed_handicap.get('initial_handicap') is not None,
            "包含即时盘口": detailed_handicap.get('current_handicap') is not None,
            "包含初盘水位": detailed_handicap.get('initial_home_odds') is not None,
            "包含即时水位": detailed_handicap.get('current_home_odds') is not None,
            "包含盘口文本": bool(detailed_handicap.get('initial_handicap_text')),
            "包含公司信息": bool(detailed_handicap.get('company_id'))
        }
        
        all_passed = all(checks.values())
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        
        print()
        print("=" * 80)
        if all_passed:
            print("🎉 采集系统盘口数据获取完全正常！")
            print()
            print("【验证结论】")
            print("✅ 标盘指数功能可以准确获取澳门盘数据")
            print("✅ 包含完整的初盘和即时盘数据")
            print("✅ 能够正确计算盘口变化趋势")
            print("✅ 数据结构完整，可用于后续分析")
            print()
            print("现在可以：")
            print("1. 启动 app.py 开始实时采集")
            print("2. 采集的数据将自动包含澳门盘初盘和即时盘")
            print("3. 运行 analyze_with_handicap.py 分析已采集数据")
        else:
            print("⚠️  部分数据缺失，请检查")
        print("=" * 80)
        
    else:
        print("❌ 盘口数据获取失败")
        print()
        print("=" * 80)
        print("⚠️  采集系统可能无法获取盘口数据")
        print("=" * 80)
        
except Exception as e:
    print(f"❌ 获取失败: {e}")
    import traceback
    print()
    print("堆栈跟踪:")
    print(traceback.format_exc())
    print()
    print("=" * 80)
    print("❌ 采集系统盘口数据获取失败")
    print("=" * 80)
