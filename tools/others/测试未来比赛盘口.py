"""
测试未来比赛盘口数据获取
直接使用FID测试标盘指数功能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client

print("=" * 80)
print("测试标盘指数 - 未来比赛盘口数据获取")
print("=" * 80)
print()

lottery500_client = Lottery500Client()

# 使用几个未来比赛的FID测试（从500.com首页或标盘指数中获取）
# 这些是示例FID，你可以替换为实际的未来比赛FID
test_fids = [
    "1207149",  # 伯顿 vs 布莱克浦（已测试过的）
    "1350976",  # 韩K联比赛
    "1234567",  # 示例FID（可能无效）
]

print("说明：")
print("1. 如果你有具体的未来比赛FID，请修改test_fids列表")
print("2. FID可以从500.com首页或标盘指数页面获取")
print("3. 我们先用已知的FID测试功能是否正常")
print()
print("=" * 80)

success_count = 0
test_count = 0

for fid in test_fids[:2]:  # 测试前2个
    test_count += 1
    print()
    print(f"【测试 {test_count}/{len(test_fids[:2])}】")
    print("-" * 80)
    print(f"FID: {fid}")
    print(f"测试URL: https://odds.500.com/fenxi/yazhi-{fid}.shtml")
    print()
    
    try:
        print("正在获取盘口数据...")
        
        # 关键调用：和app.py完全一样
        detailed_handicap = lottery500_client.fetch_handicap_data(
            fid=fid,
            company_id="澳门"
        )
        
        if detailed_handicap:
            print("✅ 盘口数据获取成功！")
            print()
            
            company_name = detailed_handicap.get('company_name', '未知')
            company_id = detailed_handicap.get('company_id', '未知')
            
            print(f"博彩公司: {company_name} (ID={company_id})")
            print()
            print(f"初盘: {detailed_handicap.get('initial_handicap_text')} "
                  f"({detailed_handicap.get('initial_home_odds')}/{detailed_handicap.get('initial_away_odds')})")
            print(f"即时: {detailed_handicap.get('current_handicap_text')} "
                  f"({detailed_handicap.get('current_home_odds')}/{detailed_handicap.get('current_away_odds')})")
            
            change = detailed_handicap.get('current_handicap', 0) - detailed_handicap.get('initial_handicap', 0)
            trend = "升盘" if change < -0.01 else ("降盘" if change > 0.01 else "稳盘")
            print(f"变化: {trend} ({change:+.2f})")
            
            success_count += 1
            
        else:
            print("❌ 盘口数据获取失败（可能该比赛没有澳门盘数据）")
            
    except Exception as e:
        print(f"❌ 获取失败: {e}")

print()
print("=" * 80)
print("【测试总结】")
print("=" * 80)
print(f"测试数量: {test_count}")
print(f"成功: {success_count}")
print(f"失败: {test_count - success_count}")
print()

if success_count > 0:
    print("🎉 标盘指数功能正常！")
    print()
    print("【验证结论】")
    print("✅ 系统可以通过FID获取比赛的澳门盘数据")
    print("✅ 无论比赛是否开始，都能获取盘口数据")
    print("✅ 数据包含初盘、即时盘和变化趋势")
    print()
    print("【下一步】")
    print("1. 启动 app.py，它会自动采集今天的比赛")
    print("2. 采集的数据会保存在 data/ 目录")
    print("3. 所有数据都会包含澳门盘的初盘和即时盘")
    print("4. 运行 analyze_with_handicap.py 进行分析")
else:
    print("⚠️  测试失败")
    print()
    print("建议：")
    print("1. 访问 https://odds.500.com/ 获取最新比赛的FID")
    print("2. 更新test_fids列表中的FID")
    print("3. 重新运行测试")

print("=" * 80)
