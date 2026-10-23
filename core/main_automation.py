"""自动化系统主控制器"""
import logging
import sys
from pathlib import Path
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from automation.scheduler import AutoScheduler
from automation.batch_collector import BatchCollector
from notification.telegram_bot import TelegramNotifier
from automation.database import MatchDatabase


def setup_telegram():
    """配置Telegram Bot"""
    print("\n" + "="*60)
    print("📱 Telegram Bot 配置")
    print("="*60)
    
    print("\n请按以下步骤获取配置信息：")
    print("1. 在Telegram中搜索 @BotFather")
    print("2. 发送 /newbot 创建新机器人")
    print("3. 按提示设置机器人名称和用户名")
    print("4. 获取Bot Token，并仅保存在本地配置中")
    print("\n5. 在Telegram中搜索 @userinfobot")
    print("6. 发送任意消息获取你的Chat ID（纯数字）")
    
    print("\n请输入配置信息：")
    bot_token = input("Bot Token: ").strip()
    chat_id = input("Chat ID: ").strip()
    
    if not bot_token or not chat_id:
        print("❌ 配置不完整，退出")
        return False
    
    # 保存配置
    TelegramNotifier.create_config(bot_token, chat_id)
    
    # 测试连接
    print("\n测试Telegram连接...")
    notifier = TelegramNotifier(bot_token, chat_id)
    
    if notifier.send_test_message():
        print("✅ Telegram配置成功！请检查你的Telegram收到测试消息。")
        return True
    else:
        print("❌ Telegram测试失败，请检查配置")
        return False


def show_menu():
    """显示主菜单"""
    print("\n" + "="*60)
    print("⚽ 足球比赛自动推荐系统")
    print("="*60)
    print("\n请选择操作：")
    print("1. 🚀 启动自动化调度器（推荐）")
    print("2. 📊 批量采集历史数据")
    print("3. 📱 配置Telegram Bot")
    print("4. 📈 查看数据库统计")
    print("5. 🧪 测试Telegram推送")
    print("0. ❌ 退出")
    print("-" * 60)


def view_statistics():
    """查看统计信息"""
    print("\n" + "="*60)
    print("📈 数据库统计")
    print("="*60 + "\n")
    
    db = MatchDatabase()
    stats = db.get_statistics()
    
    print(f"📁 数据库位置: {stats.get('database_path')}")
    print(f"⚽ 总比赛数: {stats.get('total_matches', 0)}")
    print(f"✅ 已完场: {stats.get('finished_matches', 0)}")
    print(f"📤 成功推送: {stats.get('successful_notifications', 0)}")
    print(f"🎯 生成推荐: {stats.get('recommendations_made', 0)}")


def test_telegram():
    """测试Telegram推送"""
    print("\n测试Telegram推送...")
    
    notifier = TelegramNotifier()
    
    # 构造测试推荐数据
    test_data = {
        "match_info": {
            "league": "测试联赛",
            "datetime": "2025-11-17 21:00",
            "home": "主队测试",
            "away": "客队测试"
        },
        "recommendation": {
            "direction": "主胜",
            "confidence": 0.75,
            "reason": "这是一条测试推荐消息"
        }
    }
    
    if notifier.send_recommendation(test_data):
        print("✅ 测试消息已发送，请检查Telegram")
    else:
        print("❌ 发送失败，请检查配置")


def start_automation():
    """启动自动化系统"""
    print("\n" + "="*60)
    print("🚀 启动自动化调度器")
    print("="*60)
    print("\n系统功能：")
    print("✅ 每小时自动检查即将开始的比赛")
    print("✅ 自动采集交易明细并分析")
    print("✅ 生成推荐并推送到Telegram")
    print("✅ 每天凌晨3点采集前一天的完场数据")
    print("\n按 Ctrl+C 停止\n")
    
    input("按回车键开始...")
    
    try:
        scheduler = AutoScheduler()
        scheduler.start()
    except KeyboardInterrupt:
        print("\n\n⏹️  系统已停止")


def batch_collect():
    """批量采集历史数据"""
    print("\n" + "="*60)
    print("📊 批量采集历史数据")
    print("="*60 + "\n")
    
    print("请选择采集范围：")
    days = input("采集最近N天的数据（默认7天）: ").strip()
    days = int(days) if days.isdigit() else 7
    
    delay = input("请求间隔秒数（默认3秒）: ").strip()
    delay = int(delay) if delay.isdigit() else 3
    
    print(f"\n将采集最近 {days} 天的数据，间隔 {delay} 秒")
    confirm = input("确认开始？(y/n): ").strip().lower()
    
    if confirm == 'y':
        collector = BatchCollector()
        collector.collect_recent_days(days=days, delay=delay)
    else:
        print("已取消")


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('automation_main.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 检查Telegram配置
    config_file = Path(__file__).parent / "telegram_config.json"
    telegram_configured = config_file.exists()
    
    while True:
        show_menu()
        
        if not telegram_configured:
            print("\n⚠️  提示：尚未配置Telegram Bot，建议先配置（选项3）")
        
        choice = input("\n请输入选项: ").strip()
        
        if choice == "1":
            start_automation()
        elif choice == "2":
            batch_collect()
        elif choice == "3":
            if setup_telegram():
                telegram_configured = True
        elif choice == "4":
            view_statistics()
        elif choice == "5":
            test_telegram()
        elif choice == "0":
            print("\n👋 再见！")
            break
        else:
            print("\n❌ 无效选项，请重新选择")
        
        if choice != "0":
            input("\n按回车键继续...")


if __name__ == "__main__":
    main()
