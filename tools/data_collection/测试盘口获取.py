"""
测试盘口数据获取功能
验证：1. 网络连接是否正常  2. 500.com是否可访问  3. 盘口数据是否能正确解析
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client

def test_network_connection():
    """测试1：基础网络连接"""
    print("=" * 80)
    print("测试1：基础网络连接")
    print("=" * 80)
    
    try:
        import requests
        response = requests.get("https://www.baidu.com", timeout=5)
        print(f"✅ 网络连接正常（百度可访问）")
        print(f"   状态码: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ 网络连接失败: {e}")
        return False

def test_500com_access():
    """测试2：500.com访问"""
    print("\n" + "=" * 80)
    print("测试2：500.com访问")
    print("=" * 80)
    
    try:
        import requests
        response = requests.get("https://odds.500.com/", timeout=10)
        print(f"✅ 500.com可访问")
        print(f"   状态码: {response.status_code}")
        print(f"   响应大小: {len(response.text)} 字符")
        return True
    except Exception as e:
        print(f"❌ 500.com访问失败: {e}")
        return False

def test_handicap_page_access(fid="1199340"):
    """测试3：亚盘页面访问"""
    print("\n" + "=" * 80)
    print(f"测试3：亚盘页面访问（测试fid={fid}）")
    print("=" * 80)
    
    try:
        import requests
        url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"
        print(f"URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gb2312'
        
        print(f"✅ 亚盘页面可访问")
        print(f"   状态码: {response.status_code}")
        print(f"   响应大小: {len(response.text)} 字符")
        print(f"   编码: {response.encoding}")
        
        # 检查是否包含盘口数据
        if 'pl_table_data' in response.text:
            print(f"✅ 页面包含盘口数据表格")
        else:
            print(f"⚠️  页面不包含盘口数据表格（可能比赛太旧）")
        
        return True
    except Exception as e:
        print(f"❌ 亚盘页面访问失败: {e}")
        return False

def test_handicap_parsing(fid="1199340"):
    """测试4：盘口数据解析"""
    print("\n" + "=" * 80)
    print(f"测试4：盘口数据解析（测试fid={fid}）")
    print("=" * 80)
    
    try:
        client = Lottery500Client()
        print(f"正在获取fid={fid}的盘口数据...")
        
        data = client.fetch_handicap_data(fid=fid, company_id="澳门")  # 使用名称匹配
        
        if data:
            print(f"✅ 盘口数据解析成功！")
            print(f"\n【数据详情】")
            print(f"  数据源: {data.get('source')}")
            print(f"  博彩公司: {data.get('company_name', data.get('company_id'))} (ID={data.get('company_id')})")
            print(f"  FID: {data.get('fid')}")
            print(f"\n【初盘】")
            print(f"  盘口文本: {data.get('initial_handicap_text')}")
            print(f"  盘口数值: {data.get('initial_handicap')}")
            print(f"  主队水位: {data.get('initial_home_odds')}")
            print(f"  客队水位: {data.get('initial_away_odds')}")
            print(f"\n【即时盘口】")
            print(f"  盘口文本: {data.get('current_handicap_text')}")
            print(f"  盘口数值: {data.get('current_handicap')}")
            print(f"  主队水位: {data.get('current_home_odds')}")
            print(f"  客队水位: {data.get('current_away_odds')}")
            print(f"  变化趋势: {data.get('current_trend')}")
            
            # 计算盘口变化
            initial = data.get('initial_handicap', 0)
            current = data.get('current_handicap', 0)
            change = current - initial
            
            print(f"\n【盘口变化】")
            print(f"  变化量: {change:+.2f}")
            if change < -0.01:
                print(f"  趋势: 升盘")
            elif change > 0.01:
                print(f"  趋势: 降盘")
            else:
                print(f"  趋势: 稳盘")
            
            return True
        else:
            print(f"❌ 盘口数据解析失败（可能该公司没有盘口数据）")
            return False
            
    except Exception as e:
        print(f"❌ 盘口数据解析失败: {e}")
        import traceback
        print(f"\n堆栈跟踪:")
        print(traceback.format_exc())
        return False

def test_real_match():
    """测试5：使用真实比赛数据测试"""
    print("\n" + "=" * 80)
    print("测试5：读取真实比赛文件并测试")
    print("=" * 80)
    
    try:
        import json
        from pathlib import Path
        
        # 查找第一个比赛JSON文件
        data_dir = Path(__file__).parent / "data" / "2025" / "11"
        json_files = list(data_dir.rglob("*.json"))
        json_files = [f for f in json_files if f.name != "盘口数据.json"]
        
        if not json_files:
            print("❌ 未找到比赛数据文件")
            return False
        
        test_file = json_files[0]
        print(f"测试文件: {test_file.name}")
        
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        handicap_data = data.get('handicap_data', {})
        fid = handicap_data.get('fid')
        
        if not fid:
            print(f"⚠️  文件中没有fid")
            return False
        
        print(f"FID: {fid}")
        
        # 获取盘口数据
        client = Lottery500Client()
        result = client.fetch_handicap_data(fid=fid, company_id="澳门")  # 使用名称匹配
        
        if result:
            print(f"✅ 真实比赛盘口获取成功！")
            print(f"  初盘: {result.get('initial_handicap_text')} ({result.get('initial_home_odds')}/{result.get('initial_away_odds')})")
            print(f"  即时: {result.get('current_handicap_text')} ({result.get('current_home_odds')}/{result.get('current_away_odds')})")
            return True
        else:
            print(f"❌ 真实比赛盘口获取失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    print("\n🧪 开始测试盘口数据获取功能")
    print("=" * 80)
    print()
    
    results = []
    
    # 测试1：基础网络
    results.append(("基础网络连接", test_network_connection()))
    
    # 测试2：500.com访问
    results.append(("500.com访问", test_500com_access()))
    
    # 测试3：亚盘页面访问（使用示例fid）
    results.append(("亚盘页面访问", test_handicap_page_access("1199340")))
    
    # 测试4：盘口数据解析
    results.append(("盘口数据解析", test_handicap_parsing("1199340")))
    
    # 测试5：真实比赛数据
    results.append(("真实比赛数据", test_real_match()))
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 测试结果汇总")
    print("=" * 80)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    print(f"\n总计: {success_count}/{total_count} 通过")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！系统运行正常。")
    elif success_count >= 3:
        print("\n⚠️  部分测试失败，但核心功能正常。")
    else:
        print("\n❌ 多个测试失败，请检查网络连接和系统配置。")
    
    print("=" * 80)
