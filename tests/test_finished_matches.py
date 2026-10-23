"""测试完场回查功能"""
from datetime import datetime, timedelta
from services import BifawClient

def test_finished_matches():
    """测试获取完场比赛"""
    client = BifawClient()
    
    # 测试最近7天的数据
    print(f"\n{'='*60}")
    print("测试最近7天的完场比赛数据")
    print(f"{'='*60}\n")
    
    found_data = False
    
    for days_ago in range(1, 8):
        test_date = datetime.now() - timedelta(days=days_ago)
        date_str = test_date.strftime('%Y-%m-%d')
        
        print(f"\n📅 测试日期: {date_str}")
        print("-" * 40)
        
        try:
            matches = client.fetch_finished_matches(target_date=test_date, rows=200)
            print(f"结果: {len(matches)} 场比赛")
            
            if matches:
                found_data = True
                print(f"\n✅ 找到数据！显示前3场：")
        
                for i, match in enumerate(matches[:3], 1):
                    print(f"\n  {i}. {match.get('label')}")
                    print(f"     联赛: {match.get('league')}")
                    print(f"     比分: {match.get('score')}")
                break  # 找到数据后停止
                
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    if not found_data:
        print("\n" + "="*60)
        print("⚠️  未找到任何比赛数据")
        print("="*60)
        print("\n可能的原因：")
        print("1. 🔐 登录已过期 - 请在网页端重新登录")
        print("2. 🌐 网络连接问题")
        print("3. 📅 最近一周确实没有比赛数据")
        print("\n解决方法：")
        print("1. 访问 http://127.0.0.1:5001/collect")
        print("2. 点击'获取验证码'完成登录")
        print("3. 登录成功后再次尝试查询")

if __name__ == "__main__":
    test_finished_matches()
