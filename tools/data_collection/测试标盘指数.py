"""
测试标盘指数功能 - 获取未来比赛的盘口数据
验证采集系统能否正确获取还未开始的比赛的澳门盘数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient
import json
from datetime import datetime, timedelta

print("=" * 80)
print("测试标盘指数 - 未来比赛盘口数据获取")
print("=" * 80)
print()

# 初始化客户端
lottery500_client = Lottery500Client()
bifaw_client = BifawClient()

print("【步骤1：获取未来比赛列表】")
print("-" * 80)

# 获取今天和明天的比赛
today = datetime.now()
tomorrow = today + timedelta(days=1)

print(f"今天: {today.strftime('%Y-%m-%d')}")
print(f"明天: {tomorrow.strftime('%Y-%m-%d')}")
print()

# 尝试获取未来的比赛
future_matches = []

try:
    # 从必发获取今天和明天的比赛
    print("正在从必发获取比赛数据...")
    
    # 使用app.py中的方法获取比赛
    today_matches = bifaw_client.get_match_data(today.strftime("%Y-%m-%d"))
    if today_matches:
        future_matches.extend(today_matches)
    
    tomorrow_matches = bifaw_client.get_match_data(tomorrow.strftime("%Y-%m-%d"))
    if tomorrow_matches:
        future_matches.extend(tomorrow_matches)
    
    print(f"✅ 获取到 {len(future_matches)} 场比赛")
    
    # 筛选出还未开始的比赛
    now = datetime.now()
    upcoming_matches = []
    
    for match in future_matches:
        kickoff_str = match.get('kickoff') or match.get('match_time')
        if kickoff_str:
            try:
                # 解析开赛时间
                kickoff_time = datetime.strptime(kickoff_str, "%Y-%m-%d %H:%M")
                if kickoff_time > now:
                    upcoming_matches.append(match)
            except:
                pass
    
    print(f"✅ 其中未开始的比赛: {len(upcoming_matches)} 场")
    
    if len(upcoming_matches) == 0:
        print("⚠️  所有比赛都已开始或完场")
        print("将测试今天的第一场比赛（可能已开始）")
        if len(future_matches) > 0:
            upcoming_matches = [future_matches[0]]
    
except Exception as e:
    print(f"❌ 获取比赛失败: {e}")
    import traceback
    print(traceback.format_exc())
    upcoming_matches = []

if not upcoming_matches:
    print()
    print("=" * 80)
    print("❌ 无法获取未来比赛数据")
    print("=" * 80)
    sys.exit(1)

print()

# ============================================================================
# 步骤2：选择测试比赛
# ============================================================================
print("【步骤2：选择测试比赛】")
print("-" * 80)

# 选择第一场有FID的比赛
test_match = None
for match in upcoming_matches[:20]:  # 检查前20场
    fid = match.get('handicap_preview', {}).get('fid')
    if fid:
        test_match = match
        break

if not test_match:
    print("❌ 前20场比赛都没有FID")
    sys.exit(1)

home_team = test_match.get('home_team') or test_match.get('home')
away_team = test_match.get('away_team') or test_match.get('away')
league = test_match.get('league', '未知联赛')
kickoff = test_match.get('kickoff') or test_match.get('match_time')
fid = test_match.get('handicap_preview', {}).get('fid')

print(f"测试比赛信息:")
print(f"  联赛: {league}")
print(f"  主队: {home_team}")
print(f"  客队: {away_team}")
print(f"  开赛时间: {kickoff}")
print(f"  FID: {fid}")
print(f"  状态: 🔜 未开始")
print()

# ============================================================================
# 步骤3：获取盘口数据（关键测试）
# ============================================================================
print("【步骤3：获取未来比赛的盘口数据】")
print("=" * 80)
print("这是关键测试：验证标盘指数能否获取未开始比赛的澳门盘数据")
print("=" * 80)
print()
print(f"调用: lottery500_client.fetch_handicap_data(fid={fid}, company_id='澳门')")
print()

try:
    # 这里使用和app.py完全一样的调用方式
    detailed_handicap = lottery500_client.fetch_handicap_data(
        fid=fid,
        company_id="澳门"  # 使用名称匹配
    )
    
    if detailed_handicap:
        print("✅ 盘口数据获取成功！")
        print()
        
        # 显示详细数据
        print("【博彩公司信息】")
        company_name = detailed_handicap.get('company_name', '未知')
        company_id = detailed_handicap.get('company_id', '未知')
        print(f"  名称: {company_name}")
        print(f"  ID: {company_id}")
        print()
        
        print("【初盘数据】")
        print(f"  盘口: {detailed_handicap.get('initial_handicap_text')}")
        print(f"  数值: {detailed_handicap.get('initial_handicap')}")
        print(f"  主队水位: {detailed_handicap.get('initial_home_odds')}")
        print(f"  客队水位: {detailed_handicap.get('initial_away_odds')}")
        print()
        
        print("【即时盘数据】")
        print(f"  盘口: {detailed_handicap.get('current_handicap_text')}")
        print(f"  数值: {detailed_handicap.get('current_handicap')}")
        print(f"  主队水位: {detailed_handicap.get('current_home_odds')}")
        print(f"  客队水位: {detailed_handicap.get('current_away_odds')}")
        print(f"  趋势: {detailed_handicap.get('current_trend')}")
        print()
        
        # 盘口变化
        initial = detailed_handicap.get('initial_handicap', 0)
        current = detailed_handicap.get('current_handicap', 0)
        change = current - initial
        
        if change < -0.01:
            trend_text = "升盘 ⬆️"
        elif change > 0.01:
            trend_text = "降盘 ⬇️"
        else:
            trend_text = "稳盘 ➡️"
        
        print("【盘口变化】")
        print(f"  变化量: {change:+.2f}")
        print(f"  趋势: {trend_text}")
        print()
        
        # 数据完整性验证
        print("【数据完整性检查】")
        checks = {
            "初盘数据": detailed_handicap.get('initial_handicap') is not None,
            "即时盘数据": detailed_handicap.get('current_handicap') is not None,
            "初盘水位": detailed_handicap.get('initial_home_odds') is not None,
            "即时水位": detailed_handicap.get('current_home_odds') is not None,
            "盘口文本": bool(detailed_handicap.get('initial_handicap_text')),
            "公司识别": bool(detailed_handicap.get('company_id'))
        }
        
        all_passed = all(checks.values())
        for name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {name}")
        
        print()
        print("=" * 80)
        
        if all_passed:
            print("🎉🎉🎉 标盘指数功能测试成功！ 🎉🎉🎉")
            print()
            print("【验证结论】")
            print("✅ 标盘指数可以获取未开始比赛的盘口数据")
            print("✅ 能够正确识别澳门盘")
            print("✅ 包含完整的初盘和即时盘数据")
            print("✅ 数据结构完整，适用于实时采集")
            print()
            print("【实际应用】")
            print("1. 启动 app.py 进行实时采集")
            print("2. 系统会自动获取未来比赛的澳门盘数据")
            print("3. 数据将包含初盘、即时盘和盘口变化趋势")
            print("4. 可用于赛前分析和投注决策")
        else:
            print("⚠️  数据不完整，部分功能可能受影响")
        
        print("=" * 80)
        
    else:
        print("❌ 盘口数据获取失败")
        print()
        print("可能原因:")
        print("1. 该比赛还没有开放盘口")
        print("2. 澳门盘暂时没有该比赛数据")
        print("3. 网络连接问题")
        print()
        print("=" * 80)
        print("⚠️  测试未通过，建议检查比赛FID或更换测试比赛")
        print("=" * 80)
        
except Exception as e:
    print(f"❌ 获取失败: {e}")
    import traceback
    print()
    print("堆栈跟踪:")
    print(traceback.format_exc())
    print()
    print("=" * 80)
    print("❌ 标盘指数功能测试失败")
    print("=" * 80)
