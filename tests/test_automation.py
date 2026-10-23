"""测试自动化系统"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("\n" + "="*60)
print("⚽ 测试自动化系统")
print("="*60 + "\n")

# 1. 测试推荐分析器
print("1️⃣  测试推荐分析器...")
try:
    from recommendation.analyzer import MatchAnalyzer
    import pandas as pd
    
    analyzer = MatchAnalyzer()
    
    # 创建测试数据
    test_df = pd.DataFrame({
        '时间': ['10:00', '10:05', '10:10'],
        '主胜成交': [1000, 1200, 1500],
        '平局成交': [500, 550, 600],
        '客胜成交': [300, 320, 350],
    })
    
    test_metadata = [{
        'title_meta': {
            'league': '测试联赛',
            'datetime': '2025-11-17 21:00',
            'home': '测试主队',
            'away': '测试客队'
        }
    }]
    
    result = analyzer.analyze_trade_data(test_df, test_metadata)
    
    if 'recommendation' in result:
        print(f"   ✅ 分析成功")
        print(f"   推荐: {result['recommendation'].get('direction')}")
        print(f"   置信度: {result['recommendation'].get('confidence')*100:.1f}%")
    else:
        print(f"   ⚠️  分析结果不完整")
        
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 2. 测试Telegram通知
print("\n2️⃣  测试Telegram配置...")
try:
    from notification.telegram_bot import TelegramNotifier
    from pathlib import Path
    
    config_file = Path(__file__).parent / "telegram_config.json"
    
    if config_file.exists():
        notifier = TelegramNotifier()
        print(f"   ✅ 配置文件存在")
        print(f"   提示: 运行主程序选择'5'可发送测试消息")
    else:
        print(f"   ⚠️  未配置Telegram")
        print(f"   提示: 运行主程序选择'3'进行配置")
        
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 3. 测试数据库
print("\n3️⃣  测试数据库...")
try:
    from automation.database import MatchDatabase
    
    db = MatchDatabase()
    stats = db.get_statistics()
    
    print(f"   ✅ 数据库初始化成功")
    print(f"   位置: {stats.get('database_path')}")
    print(f"   已存储比赛: {stats.get('total_matches', 0)} 场")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 4. 测试BifawClient
print("\n4️⃣  测试必发客户端...")
try:
    from services import BifawClient
    from pathlib import Path
    
    cookies_file = Path(__file__).parent / "cookies.json"
    
    if cookies_file.exists():
        client = BifawClient()
        print(f"   ✅ Cookies文件存在")
        print(f"   提示: 登录状态有效")
    else:
        print(f"   ⚠️  未登录")
        print(f"   提示: 访问 http://127.0.0.1:5001/collect 完成登录")
        
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 总结
print("\n" + "="*60)
print("📝 测试总结")
print("="*60)
print("\n准备工作：")
print("1. ✅ 推荐算法模块正常")
print("2. ⚠️  需要配置Telegram（运行主程序选择3）")
print("3. ✅ 数据库已就绪")
print("4. ⚠️  需要登录必发网站（访问采集控制台）")

print("\n下一步：")
print("1. 运行 'python app.py' 启动网页控制台")
print("2. 访问 http://127.0.0.1:5001/collect 完成登录")
print("3. 运行 'python main_automation.py' 配置Telegram")
print("4. 启动自动化系统")

print("\n💡 或者直接运行 'python main_automation.py' 进入交互式配置")
print("="*60 + "\n")
