"""
一键测试所有推送功能
测试告警、比赛推荐、整点播报等所有推送是否正常
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 硬编码的企业微信Webhook
WECOM_WEBHOOK_URL = ""

def print_section(title, icon="🧪"):
    """打印分节标题"""
    print("\n" + "="*70)
    print(f"  {icon} {title}")
    print("="*70)

def test_1_alert_push():
    """测试1: 告警推送"""
    print_section("测试1: 告警推送", "🚨")
    
    try:
        from utils.alert_manager import get_alert_manager
        
        webhook = os.getenv('WECOM_ALERT_WEBHOOK') or os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        alert_manager = get_alert_manager(wecom_webhook=webhook)
        
        print("发送测试告警...")
        success = alert_manager.send_alert(
            alert_type="test_all_push",
            title="【测试1】告警推送测试",
            message="这是告警推送测试消息，用于验证系统异常时能否正常推送告警。\n\n测试项目：告警系统",
            force=True
        )
        
        if success:
            print("✅ 告警推送成功！")
            return True
        else:
            print("❌ 告警推送失败")
            return False
    except Exception as e:
        print(f"❌ 告警推送异常: {e}")
        return False

def test_2_wecom_basic():
    """测试2: 企业微信基础推送"""
    print_section("测试2: 企业微信基础推送", "📱")
    
    try:
        import requests
        
        webhook = os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        
        # 测试Markdown格式
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"""# 【测试2】企业微信推送测试

⏰ **测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 测试内容
- ✅ Markdown格式支持
- ✅ 文本格式化
- ✅ 表情符号显示

## 测试状态
**状态**: 正常
**测试项目**: 企业微信基础推送

---
_Football Analysis System_
"""
            }
        }
        
        print("发送企业微信Markdown消息...")
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                print("✅ 企业微信推送成功！")
                return True
            else:
                print(f"❌ 企业微信推送失败: {result.get('errmsg')}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 企业微信推送异常: {e}")
        return False

def test_3_match_recommendation():
    """测试3: 比赛推荐推送格式"""
    print_section("测试3: 比赛推荐推送格式", "⚽")
    
    try:
        import requests
        
        webhook = os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        
        # 模拟比赛推荐消息
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"""# 【测试3】比赛推荐推送

## ⚽ 比赛信息
**联赛**: 英超
**对阵**: 曼联 vs 曼城
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 📊 盘口分析
- **初盘**: 半球 0.90/0.90
- **即时盘**: 半球 0.85/0.95
- **盘口变化**: ⬇️ 降水

## 🎯 推荐方向
**推荐**: 主队 (曼联)
**理由**: 
1. 主场优势明显
2. 盘口支持主队
3. 近期状态良好

---
⏰ 推送时间: {datetime.now().strftime('%H:%M:%S')}
"""
            }
        }
        
        print("发送比赛推荐格式测试...")
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code == 200 and response.json().get('errcode') == 0:
            print("✅ 比赛推荐推送格式正常！")
            return True
        else:
            print("❌ 比赛推荐推送失败")
            return False
    except Exception as e:
        print(f"❌ 比赛推荐推送异常: {e}")
        return False

def test_4_hourly_broadcast():
    """测试4: 整点播报推送格式"""
    print_section("测试4: 整点播报推送格式", "📢")
    
    try:
        import requests
        
        webhook = os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        
        # 模拟整点播报消息
        now = datetime.now()
        hour = now.hour
        next_hour = (hour + 1) % 24
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"""# 【测试4】{next_hour}:00 整点播报

## 📊 比赛概况
- 📅 时段: {next_hour}:00 - {(next_hour+1)%24}:00
- ⚽ 比赛总数: 3 场
- 🕐 未开始: 2 场
- ⚽ 进行中: 1 场

## 📋 比赛列表

### 1. 🕐 英超 21:00
**曼联 vs 曼城**
盘口: 半球 0.90

### 2. 🕐 西甲 21:30
**皇马 vs 巴萨**
盘口: 平手/半球 0.85

### 3. ⚽ 意甲 21:15 (进行中)
**尤文 vs AC米兰**
盘口: 半球/一球 0.95

---
⏰ 播报时间: {now.strftime('%H:%M:%S')}
📅 下次播报: {next_hour+1}:59
"""
            }
        }
        
        print("发送整点播报格式测试...")
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code == 200 and response.json().get('errcode') == 0:
            print("✅ 整点播报推送格式正常！")
            return True
        else:
            print("❌ 整点播报推送失败")
            return False
    except Exception as e:
        print(f"❌ 整点播报推送异常: {e}")
        return False

def test_5_pre_match_notification():
    """测试5: 赛前提醒推送格式"""
    print_section("测试5: 赛前提醒推送格式", "⏰")
    
    try:
        import requests
        
        webhook = os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        
        # 模拟赛前提醒消息
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"""# 【测试5】⏰ 赛前5分钟提醒

## ⚽ 比赛即将开始
**联赛**: 欧冠
**对阵**: 拜仁 vs 巴黎圣日耳曼
**开始时间**: {(datetime.now()).strftime('%Y-%m-%d %H:%M')}
**距离开始**: 5分钟

## 📊 盘口信息
- **初盘**: 平手/半球 0.95/0.85
- **即时盘**: 平手/半球 0.90/0.90
- **盘口走势**: 主队降水

## 🎯 推荐分析
**推荐方向**: 主队 (拜仁)
**置信度**: 中等
**关键因素**: 
1. 主场优势
2. 近期状态
3. 盘口支持

---
⚠️ 请注意关注比赛动态
⏰ 推送时间: {datetime.now().strftime('%H:%M:%S')}
"""
            }
        }
        
        print("发送赛前提醒格式测试...")
        response = requests.post(webhook, json=payload, timeout=10)
        
        if response.status_code == 200 and response.json().get('errcode') == 0:
            print("✅ 赛前提醒推送格式正常！")
            return True
        else:
            print("❌ 赛前提醒推送失败")
            return False
    except Exception as e:
        print(f"❌ 赛前提醒推送异常: {e}")
        return False

def test_6_error_notification():
    """测试6: 错误通知推送格式"""
    print_section("测试6: 错误通知推送格式", "❌")
    
    try:
        from utils.alert_manager import get_alert_manager
        
        webhook = os.getenv('WECOM_ALERT_WEBHOOK') or os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
        alert_manager = get_alert_manager(wecom_webhook=webhook)
        
        print("发送错误通知测试...")
        
        # 测试各种错误类型
        test_cases = [
            ("登录失败", "模拟登录失败场景"),
            ("数据采集失败", "模拟数据采集失败场景"),
        ]
        
        for i, (title, msg) in enumerate(test_cases, 1):
            print(f"  [{i}/{len(test_cases)}] 测试{title}通知...")
            success = alert_manager.send_alert(
                alert_type=f"test_error_{i}",
                title=f"【测试6.{i}】{title}",
                message=msg,
                force=True
            )
            if not success:
                print(f"  ❌ {title}通知失败")
                return False
            time.sleep(1)  # 避免太快
        
        print("✅ 错误通知推送格式正常！")
        return True
    except Exception as e:
        print(f"❌ 错误通知推送异常: {e}")
        return False

def main():
    """主测试函数"""
    print("="*70)
    print("  🚀 一键测试所有推送功能")
    print(f"  ⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\n📱 测试将向企业微信群发送多条测试消息")
    print("⏱️  预计耗时: 约30秒")
    print("✅ 所有消息都是测试消息，带有【测试】标记")
    
    input("\n按回车键开始测试...")
    
    results = {}
    
    # 执行所有测试
    tests = [
        ("告警推送", test_1_alert_push),
        ("企业微信基础推送", test_2_wecom_basic),
        ("比赛推荐格式", test_3_match_recommendation),
        ("整点播报格式", test_4_hourly_broadcast),
        ("赛前提醒格式", test_5_pre_match_notification),
        ("错误通知格式", test_6_error_notification),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
            time.sleep(2)  # 每个测试间隔2秒，避免太快
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results[name] = False
    
    # 总结
    print_section("测试总结", "📊")
    
    print("\n测试结果:")
    for name, result in results.items():
        icon = "✅" if result else "❌"
        status = "通过" if result else "失败"
        print(f"  {icon} {name}: {status}")
    
    # 统计
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    print("\n" + "="*70)
    if passed == total:
        print("  ✅ 所有推送功能测试通过！")
        print("  📱 请检查企业微信群，应该收到6+条测试消息")
    else:
        print(f"  ⚠️  {total - passed} 项测试失败")
        print("  请检查网络连接和Webhook配置")
    print("="*70)
    
    print("\n💡 提示:")
    print("  - 如果收到测试消息，说明推送功能正常")
    print("  - 生产环境中的推送将使用相同的方式")
    print("  - 告警会自动发送，无需手动触发")

if __name__ == "__main__":
    try:
        # 加载环境变量
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 测试已取消")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
