"""
测试系统优化功能
验证告警和健康检查是否正常工作
"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_alert_manager():
    """测试告警管理器"""
    print("="*60)
    print("  1. 测试告警管理器")
    print("="*60)
    
    from utils.alert_manager import get_alert_manager
    
    # 硬编码的企业微信Webhook（与app.py保持一致）
    WECOM_WEBHOOK_URL = ""
    
    # 从环境变量获取Webhook，如果没有则使用硬编码
    webhook = os.getenv('WECOM_ALERT_WEBHOOK') or os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
    
    if not webhook:
        print("❌ 未配置WECOM_ALERT_WEBHOOK或WECOM_WEBHOOK")
        print("   请在.env文件中配置后重试")
        return False
    
    print(f"✅ 找到Webhook配置")
    print(f"   URL: {webhook[:50]}...")
    
    alert_manager = get_alert_manager(wecom_webhook=webhook)
    print(f"✅ 告警管理器已初始化")
    print(f"   冷却期: {alert_manager.cooldown_minutes}分钟")
    
    # 测试发送告警
    print("\n发送测试告警...")
    success = alert_manager.send_alert(
        alert_type="test",
        title="系统优化测试",
        message="这是一条测试告警消息，验证告警功能是否正常工作。",
        force=True  # 强制发送，忽略冷却期
    )
    
    if success:
        print("✅ 测试告警发送成功！请检查企业微信群消息")
    else:
        print("❌ 测试告警发送失败，请检查Webhook配置")
    
    return success

def test_health_checker():
    """测试健康检查器"""
    print("\n" + "="*60)
    print("  2. 测试健康检查器")
    print("="*60)
    
    from utils.health_checker import HealthChecker
    
    health_checker = HealthChecker(
        data_dir=Path('data'),
        log_dir=Path('logs')
    )
    
    print("✅ 健康检查器已初始化")
    print("\n开始健康检查...")
    
    result = health_checker.run_full_check()
    
    print("\n检查结果:")
    print(f"  总检查项: {result['total_checks']}")
    print(f"  通过项数: {result['passed_checks']}")
    print(f"  是否全部通过: {'✅ 是' if result['all_passed'] else '❌ 否'}")
    
    if result['issues']:
        print(f"\n发现 {len(result['issues'])} 个问题:")
        for i, issue in enumerate(result['issues'], 1):
            level_icon = "⚠️" if issue['level'] == 'warning' else "❌"
            print(f"  {i}. {level_icon} [{issue['component']}] {issue['message']}")
    else:
        print("\n✅ 未发现任何问题，系统健康！")
    
    return result['all_passed']

def test_operation_logger():
    """测试操作日志"""
    print("\n" + "="*60)
    print("  3. 测试操作日志")
    print("="*60)
    
    from utils.operation_logger import get_operation_logger
    
    logger = get_operation_logger()
    
    print(f"✅ 操作日志管理器已初始化")
    print(f"   日志目录: {logger.log_dir}")
    print(f"   轮转周期: {logger.rotation_hours}小时")
    print(f"   保留天数: {logger.keep_days}天")
    
    # 获取日志统计
    stats = logger.get_log_stats()
    
    print("\n日志统计:")
    if 'error' in stats:
        print(f"  ❌ 获取统计失败: {stats['error']}")
        return False
    
    print(f"  当前日志大小: {stats.get('current_log_size', 0) / 1024:.2f} KB")
    print(f"  当前日志行数: {stats.get('current_log_lines', 0)} 行")
    print(f"  归档文件数量: {stats.get('archive_count', 0)} 个")
    
    if stats.get('archive_count', 0) > 0:
        print(f"  最早归档: {stats.get('oldest_archive', 'N/A')}")
        print(f"  最新归档: {stats.get('newest_archive', 'N/A')}")
    
    return True

def test_schedule_manager():
    """测试调度管理器"""
    print("\n" + "="*60)
    print("  4. 测试调度管理器")
    print("="*60)
    
    try:
        import requests
        
        # 测试API
        response = requests.get('http://localhost:5000/api/push/scheduled_tasks', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                total = data['total']
                print(f"✅ 调度管理器正常")
                print(f"   已调度任务: {total} 场比赛")
                
                if total > 0:
                    print("\n前3场比赛:")
                    for i, task in enumerate(data['tasks'][:3], 1):
                        print(f"  {i}. {task['home_team']} vs {task['away_team']}")
                        print(f"     推送时间: {task['push_time']}")
                return True
            else:
                print(f"❌ 调度管理器异常: {data.get('message')}")
                return False
        else:
            print(f"❌ API请求失败: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  服务未启动，无法测试调度管理器")
        print("   请先启动服务: python app.py")
        return None
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    from datetime import datetime
    
    print("="*60)
    print("  系统优化功能测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # 测试告警管理器
    results['alert'] = test_alert_manager()
    
    # 测试健康检查器
    results['health'] = test_health_checker()
    
    # 测试操作日志
    results['logger'] = test_operation_logger()
    
    # 测试调度管理器
    results['schedule'] = test_schedule_manager()
    
    # 总结
    print("\n" + "="*60)
    print("  测试总结")
    print("="*60)
    
    print("\n测试结果:")
    for name, result in results.items():
        if result is True:
            icon = "✅"
            status = "通过"
        elif result is False:
            icon = "❌"
            status = "失败"
        else:
            icon = "⚠️"
            status = "跳过"
        
        print(f"  {icon} {name.capitalize()}: {status}")
    
    # 统计
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)
    
    print(f"\n总计: {passed}/{total-skipped} 通过")
    if skipped > 0:
        print(f"跳过: {skipped} 项（需要服务运行）")
    
    print("\n" + "="*60)
    if failed == 0:
        print("  ✅ 所有测试通过！系统优化成功")
    else:
        print("  ⚠️  部分测试失败，请检查配置")
    print("="*60)

if __name__ == "__main__":
    try:
        # 加载环境变量
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            print("⚠️  未安装python-dotenv，跳过.env文件加载")
            print("   可以手动设置环境变量或安装: pip install python-dotenv\n")
        
        main()
    except KeyboardInterrupt:
        print("\n\n测试已取消")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
