"""
回测功能测试脚本
"""
import requests
import json


def test_single_backtest_api():
    """测试单场回测API"""
    
    url = "http://127.0.0.1:5001/api/backtest/single"
    
    # 示例数据（需要替换为实际的历史比赛）
    test_data = {
        "match": {
            "home": "曼联",
            "away": "利物浦",
            "league": "英超",
            "kickoff": "2025-11-10 20:00"
        },
        "detail_url": "https://example.com/match_detail",  # 需要实际的完场回查URL
        "actual_score": [2, 1],  # 实际比分：曼联2:1利物浦
    }
    
    print("=" * 70)
    print("单场回测测试")
    print("=" * 70)
    print(f"\n比赛：{test_data['match']['home']} vs {test_data['match']['away']}")
    print(f"实际比分：{test_data['actual_score'][0]} : {test_data['actual_score'][1]}")
    
    try:
        print("\n发送回测请求...")
        response = requests.post(url, json=test_data, timeout=60)
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                print("\n✅ 回测成功！\n")
                
                # 显示回测报告
                if result.get("backtest_report"):
                    print(result["backtest_report"])
                
                # 显示验证结果
                validation = result.get("validation", {})
                print("\n\n【关键信息】")
                print(f"推荐结果：{validation.get('result', 'N/A')}")
                print(f"盈亏：{validation.get('profit', 0):+.2f} 单位")
                print(f"说明：{validation.get('message', 'N/A')}")
                
                # 保存完整结果
                with open("backtest_result.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print("\n完整结果已保存到: backtest_result.json")
                
            else:
                print(f"\n❌ 回测失败: {result.get('error', 'N/A')}")
        else:
            print(f"\n❌ 请求失败: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器")
        print("请确保Flask服务已启动: python app.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")


def test_single_backtest_direct():
    """直接测试回测功能（不通过API）"""
    from backtest import BacktestEngine
    from recommendation import HandicapRecommendationEngineX1
    from services import BifawClient, Lottery500Client
    
    print("\n" + "=" * 70)
    print("直接测试回测功能")
    print("=" * 70)
    
    # 初始化
    print("\n初始化引擎...")
    bifaw_client = BifawClient()
    lottery500_client = Lottery500Client()
    recommendation_engine = HandicapRecommendationEngineX1()
    backtest_engine = BacktestEngine(
        recommendation_engine,
        lottery500_client,
        bifaw_client
    )
    
    # 测试数据
    match_info = {
        "home": "曼联",
        "away": "利物浦",
        "league": "英超",
        "kickoff": "2025-11-10 20:00"
    }
    
    detail_url = "https://example.com/match_detail"  # 需要实际URL
    actual_score = (2, 1)  # 曼联2:1利物浦
    
    print(f"\n比赛：{match_info['home']} vs {match_info['away']}")
    print(f"实际比分：{actual_score[0]} : {actual_score[1]}")
    print("\n执行回测...")
    
    # 执行回测
    result = backtest_engine.backtest_single_match(
        match_info=match_info,
        detail_url=detail_url,
        actual_score=actual_score
    )
    
    if result.get('success'):
        print("\n✅ 回测成功！")
        
        # 生成报告
        from backtest import format_backtest_report
        report = format_backtest_report(result)
        print(report)
        
        # 显示关键信息
        validation = result.get('validation', {})
        print("\n【关键信息】")
        print(f"推荐结果：{validation.get('result', 'N/A')}")
        print(f"盈亏：{validation.get('profit', 0):+.2f} 单位")
    else:
        print(f"\n❌ 回测失败: {result.get('error', 'N/A')}")


def interactive_backtest():
    """交互式回测"""
    print("\n" + "=" * 70)
    print("交互式回测")
    print("=" * 70)
    
    # 获取比赛信息
    print("\n请输入比赛信息:")
    home = input("主队名称: ")
    away = input("客队名称: ")
    league = input("联赛名称: ")
    kickoff = input("开赛时间 (例如: 2025-11-10 20:00): ")
    
    # 获取明细URL
    print("\n请输入明细URL:")
    print("（可以从完场回查页面获取）")
    detail_url = input("明细URL: ")
    
    # 获取实际比分
    print("\n请输入实际比分:")
    home_score = int(input("主队得分: "))
    away_score = int(input("客队得分: "))
    
    # 构建请求数据
    test_data = {
        "match": {
            "home": home,
            "away": away,
            "league": league,
            "kickoff": kickoff
        },
        "detail_url": detail_url,
        "actual_score": [home_score, away_score]
    }
    
    # 发送请求
    url = "http://127.0.0.1:5001/api/backtest/single"
    
    print("\n执行回测...")
    try:
        response = requests.post(url, json=test_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                print("\n✅ 回测成功！\n")
                
                # 显示报告
                if result.get("backtest_report"):
                    print(result["backtest_report"])
                
                # 保存结果
                filename = f"backtest_{home}_vs_{away}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n结果已保存到: {filename}")
                
            else:
                print(f"\n❌ 回测失败: {result.get('error', 'N/A')}")
        else:
            print(f"\n❌ 请求失败 ({response.status_code})")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")


def show_example():
    """显示使用示例"""
    print("\n" + "=" * 70)
    print("回测功能使用示例")
    print("=" * 70)
    
    print("""
【回测流程】

1. 从完场回查获取历史比赛明细
   - 登录必发网站
   - 进入完场回查页面
   - 找到想要回测的比赛
   - 复制明细页面URL

2. 准备比赛信息
   - 主队名称
   - 客队名称
   - 联赛名称
   - 开赛时间
   - 实际比分

3. 执行回测
   方式1：通过API
   ```python
   import requests
   
   response = requests.post(
       "http://127.0.0.1:5001/api/backtest/single",
       json={
           "match": {
               "home": "曼联",
               "away": "利物浦",
               "league": "英超",
               "kickoff": "2025-11-10 20:00"
           },
           "detail_url": "https://...",
           "actual_score": [2, 1]
       }
   )
   result = response.json()
   ```
   
   方式2：交互式输入
   运行本脚本并选择选项3

4. 查看回测结果
   - 推荐方向
   - 实际结果
   - 是否命中
   - 盈亏情况

【盈亏计算说明】

- 全赢：盈利 0.90 单位（按水位0.90计算）
- 半赢：盈利 0.45 单位
- 走水：盈亏 0.00 单位
- 半输：亏损 -0.50 单位
- 全输：亏损 -1.00 单位

【示例】

比赛：曼联 vs 利物浦
实际比分：2:1
推荐：客队受让0.5（即利物浦+0.5）

计算：利物浦1球 + 0.5 = 1.5 vs 曼联2球
结果：1.5 < 2，客队输
推荐结果：错误（全输）
盈亏：-1.00单位
    """)


if __name__ == "__main__":
    print("回测功能测试\n")
    
    print("选择测试方式：")
    print("1. API测试（需要Flask服务运行）")
    print("2. 直接测试（不通过API）")
    print("3. 交互式回测")
    print("4. 查看使用示例")
    
    choice = input("\n请输入 (1/2/3/4): ")
    
    if choice == "1":
        test_single_backtest_api()
    elif choice == "2":
        test_single_backtest_direct()
    elif choice == "3":
        interactive_backtest()
    elif choice == "4":
        show_example()
    else:
        print("无效选择")
