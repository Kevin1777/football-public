"""
测试让球盘口推荐引擎
"""
import requests
import json


def test_recommendation_api():
    """测试推荐API"""
    
    url = "http://127.0.0.1:5001/api/recommendation/generate"
    
    # 测试数据（需要替换为实际的比赛信息）
    test_data = {
        "match": {
            "home": "曼联",
            "away": "利物浦",
            "league": "英超",
            "kickoff": "2025-11-20 20:00"
        },
        "detail_url": "https://example.com/match_detail",  # 需要实际的URL
        "format": "both"
    }
    
    print("=" * 70)
    print("测试让球盘口推荐引擎")
    print("=" * 70)
    
    try:
        print("\n发送请求...")
        response = requests.post(url, json=test_data, timeout=60)
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                print("\n✅ 推荐生成成功！\n")
                
                # 显示VIS输出
                if result.get("vis_output"):
                    print("【VIS-E01输出】")
                    print(result["vis_output"])
                
                # 显示Telegram消息
                if result.get("telegram_message"):
                    print("\n\n【Telegram消息】")
                    print(result["telegram_message"])
                
                # 保存完整结果
                with open("recommendation_result.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print("\n\n完整结果已保存到: recommendation_result.json")
                
            else:
                print(f"\n❌ 推荐生成失败: {result.get('message')}")
        else:
            print(f"\n❌ 请求失败: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器")
        print("请确保Flask服务已启动: python app.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")


def test_recommendation_direct():
    """直接测试推荐引擎（不通过API）"""
    from recommendation import HandicapRecommendationEngineX1, VISFormatter
    import pandas as pd
    
    print("\n" + "=" * 70)
    print("直接测试推荐引擎")
    print("=" * 70)
    
    engine = HandicapRecommendationEngineX1()
    formatter = VISFormatter()
    
    # 创建测试数据
    test_trade_data = pd.DataFrame({
        '时间': ['10:00', '10:05', '10:10'],
        '主队成交': [10000, 15000, 20000],
        '客队成交': [5000, 6000, 7000],
        '平局成交': [3000, 3500, 4000]
    })
    
    test_metadata = [{
        'title_meta': {
            'league': '英超',
            'home': '曼联',
            'away': '利物浦',
            'kickoff': '2025-11-20 20:00'
        }
    }]
    
    test_handicap = {
        'home_team': '曼联',
        'away_team': '利物浦',
        'current_handicap': -0.5,
        'current_handicap_str': '受半球',
        'initial_handicap': -0.25,
        'initial_handicap_str': '受平/半',
        'current_home_odds': 0.90,
        'current_away_odds': 0.90
    }
    
    # 生成推荐
    print("\n生成推荐...")
    result = engine.generate_recommendation(
        trade_data=test_trade_data,
        metadata=test_metadata,
        handicap_data=test_handicap
    )
    
    # 格式化输出
    print("\n" + formatter.format_output(result))
    
    print("\n\n" + formatter.format_telegram_message(result))


if __name__ == "__main__":
    print("让球盘口推荐引擎测试\n")
    
    choice = input("选择测试方式：\n1. API测试（需要Flask服务运行）\n2. 直接测试（使用模拟数据）\n请输入 (1/2): ")
    
    if choice == "1":
        test_recommendation_api()
    elif choice == "2":
        test_recommendation_direct()
    else:
        print("无效选择")
