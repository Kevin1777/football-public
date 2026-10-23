"""
测试让球盘口API功能
"""
import requests
import json
from datetime import datetime

# Flask应用的地址
BASE_URL = "http://127.0.0.1:5001"


def test_handicap_parse():
    """测试盘口解析功能"""
    print("\n=== 测试盘口解析 ===")
    
    from services.lottery500_client import Lottery500Client
    
    client = Lottery500Client()
    
    test_cases = [
        ("球半", "应该是 1.5"),
        ("受平/半", "应该是 -0.25"),
        ("平手", "应该是 0.0"),
        ("-1.5", "应该是 -1.5"),
        ("+0.25", "应该是 0.25"),
        ("一球", "应该是 1.0"),
        ("受让一球", "应该是 -1.0"),
        ("半球", "应该是 0.5"),
        ("受半球", "应该是 -0.5"),
        ("两球半", "应该是 2.5"),
    ]
    
    for handicap_str, expected in test_cases:
        value = client.parse_handicap(handicap_str)
        print(f"{handicap_str:15s} -> {value:6.2f}  ({expected})")


def test_search_match():
    """测试搜索比赛"""
    print("\n=== 测试搜索比赛 ===")
    
    # 测试数据（需要根据实际情况修改）
    test_data = {
        "home_team": "曼联",
        "away_team": "利物浦",
        "match_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    url = f"{BASE_URL}/api/handicap/search"
    
    try:
        response = requests.post(url, json=test_data, timeout=30)
        result = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        return result.get("fid")
    except Exception as e:
        print(f"错误: {e}")
        return None


def test_get_handicap_data(fid):
    """测试获取盘口数据"""
    if not fid:
        print("\n跳过测试获取盘口数据（没有fid）")
        return
    
    print(f"\n=== 测试获取盘口数据 (fid={fid}) ===")
    
    test_data = {
        "fid": fid,
        "company_id": "3"  # 澳门盘
    }
    
    url = f"{BASE_URL}/api/handicap/data"
    
    try:
        response = requests.post(url, json=test_data, timeout=30)
        result = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"错误: {e}")


def test_get_match_handicap():
    """测试一站式获取比赛盘口"""
    print("\n=== 测试一站式获取比赛盘口 ===")
    
    # 测试数据（需要根据实际情况修改）
    test_data = {
        "home_team": "曼联",
        "away_team": "利物浦",
        "match_date": datetime.now().strftime("%Y-%m-%d"),
        "company_id": "3"
    }
    
    url = f"{BASE_URL}/api/handicap/match"
    
    try:
        response = requests.post(url, json=test_data, timeout=30)
        result = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        if result.get("success"):
            data = result.get("data", {})
            print("\n盘口信息摘要:")
            print(f"  主队: {data.get('home_team')}")
            print(f"  客队: {data.get('away_team')}")
            print(f"  初盘让球: {data.get('initial_handicap')} ({data.get('initial_handicap_str')})")
            print(f"  即时盘让球: {data.get('current_handicap')} ({data.get('current_handicap_str')})")
            print(f"  初盘水位: {data.get('initial_home_odds')} / {data.get('initial_away_odds')}")
            print(f"  即时盘水位: {data.get('current_home_odds')} / {data.get('current_away_odds')}")
    except Exception as e:
        print(f"错误: {e}")


def test_batch_handicap():
    """测试批量获取盘口"""
    print("\n=== 测试批量获取盘口 ===")
    
    # 测试数据（需要根据实际情况修改）
    test_data = {
        "matches": [
            {
                "home_team": "曼联",
                "away_team": "利物浦",
                "match_date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "home_team": "切尔西",
                "away_team": "阿森纳",
                "match_date": datetime.now().strftime("%Y-%m-%d")
            }
        ],
        "company_id": "3"
    }
    
    url = f"{BASE_URL}/api/handicap/batch"
    
    try:
        response = requests.post(url, json=test_data, timeout=60)
        result = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"总数: {result.get('total')}")
        print(f"成功: {result.get('success_count')}")
        print(f"失败: {result.get('error_count')}")
        
        if result.get('results'):
            print("\n成功的比赛:")
            for r in result['results']:
                data = r['data']
                print(f"  [{r['index']}] {data['home_team']} vs {data['away_team']}")
                print(f"      即时盘: {data.get('current_handicap_str')} ({data.get('current_handicap')})")
        
        if result.get('errors'):
            print("\n失败的比赛:")
            for e in result['errors']:
                print(f"  [{e['index']}] {e['message']}")
    except Exception as e:
        print(f"错误: {e}")


def main():
    """主测试函数"""
    print("=" * 60)
    print("让球盘口API测试")
    print("=" * 60)
    
    # 1. 测试盘口解析
    test_handicap_parse()
    
    # 等待用户确认Flask服务器已启动
    input("\n\n请确保Flask服务器已启动 (127.0.0.1:5001)，按Enter继续测试API...")
    
    # 2. 测试搜索比赛
    fid = test_search_match()
    
    # 3. 测试获取盘口数据
    test_get_handicap_data(fid)
    
    # 4. 测试一站式获取
    test_get_match_handicap()
    
    # 5. 测试批量获取
    test_batch_handicap()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
