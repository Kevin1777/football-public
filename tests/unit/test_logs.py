"""
测试操作日志功能
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

def print_section(title):
    """打印分节标题"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_log_stats():
    """测试日志统计"""
    print_section("1. 日志统计信息")
    
    response = requests.get(f"{BASE_URL}/api/logs/stats")
    data = response.json()
    
    if data['success']:
        stats = data['stats']
        print(f"✅ 当前日志大小: {stats.get('current_log_size_mb', 0)} MB")
        print(f"✅ 当前日志行数: {stats.get('current_log_lines', 0)} 行")
        print(f"✅ 归档文件数量: {stats.get('archive_count', 0)} 个")
        print(f"✅ 归档总大小: {stats.get('total_archive_size_mb', 0)} MB")
        
        if stats.get('oldest_archive'):
            print(f"✅ 最早归档: {stats['oldest_archive']}")
        if stats.get('newest_archive'):
            print(f"✅ 最新归档: {stats['newest_archive']}")
    else:
        print(f"❌ 失败: {data.get('message')}")

def test_view_logs():
    """测试查看日志"""
    print_section("2. 查看最近日志（最后10行）")
    
    response = requests.get(f"{BASE_URL}/api/logs/view?lines=10")
    data = response.json()
    
    if data['success']:
        print("✅ 日志内容:")
        print("-" * 60)
        print(data['content'])
        print("-" * 60)
    else:
        print(f"❌ 失败: {data.get('message')}")

def test_search_logs():
    """测试搜索日志"""
    print_section("3. 搜索日志")
    
    keywords = ["推送", "定时任务", "ERROR"]
    
    for keyword in keywords:
        print(f"\n🔍 搜索关键字: {keyword}")
        
        response = requests.post(
            f"{BASE_URL}/api/logs/search",
            json={
                "keyword": keyword,
                "max_results": 5
            }
        )
        data = response.json()
        
        if data['success']:
            total = data['total']
            print(f"✅ 找到 {total} 条匹配")
            
            if total > 0:
                print("\n前5条结果:")
                for i, result in enumerate(data['results'][:5], 1):
                    file_name = result.get('file', 'unknown')
                    line_num = result.get('line_num', 0)
                    content = result.get('content', '')[:80]  # 只显示前80个字符
                    print(f"  {i}. [{file_name}:{line_num}] {content}...")
        else:
            print(f"❌ 失败: {data.get('message')}")

def test_scheduled_tasks():
    """测试查看调度任务"""
    print_section("4. 查看已调度的推送任务")
    
    response = requests.get(f"{BASE_URL}/api/push/scheduled_tasks")
    data = response.json()
    
    if data['success']:
        total = data['total']
        print(f"✅ 共有 {total} 场比赛已调度推送")
        
        if total > 0:
            print("\n任务列表:")
            for i, task in enumerate(data['tasks'], 1):
                print(f"  {i}. {task['home_team']} vs {task['away_team']}")
                print(f"     比赛时间: {task['match_time']}")
                print(f"     推送时间: {task['push_time']}")
                print(f"     状态: {task['status']}")
    else:
        print(f"❌ 失败: {data.get('message')}")

def main():
    """主测试函数"""
    print("="*60)
    print("  操作日志功能测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # 测试日志统计
        test_log_stats()
        
        # 测试查看日志
        test_view_logs()
        
        # 测试搜索日志
        test_search_logs()
        
        # 测试调度任务
        test_scheduled_tasks()
        
        print("\n" + "="*60)
        print("  ✅ 所有测试完成")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 错误: 无法连接到服务器")
        print("   请确保服务已启动: python app.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

if __name__ == "__main__":
    main()
