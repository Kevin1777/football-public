#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
登录状态测试脚本
用于快速诊断 cookies 是否有效
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient

def test_cookies():
    """测试 cookies 状态"""
    print("=" * 60)
    print("正在测试登录状态...")
    print("=" * 60)
    
    client = BifawClient()
    
    # 1. 检查 cookies 文件
    print("\n[1] 检查 cookies 文件")
    status = client.get_cookie_status()
    print(f"   状态: {status}")
    
    if not status.get("exists"):
        print("   ❌ cookies.json 文件不存在")
        print("   👉 请访问 http://127.0.0.1:5001/collect 完成登录")
        return False
    
    print(f"   ✅ cookies.json 存在")
    print(f"   最后更新: {status.get('updated_at')}")
    
    # 2. 测试访问主页
    print("\n[2] 测试访问主页")
    try:
        html = client.fetch_page_html("/bifaw/index.php", timeout=15)
        
        # 检查登录状态
        has_login_form = "登录" in html and "验证码" in html
        has_content = "必发指数" in html or "标盘" in html
        
        print(f"   页面大小: {len(html)} 字符")
        print(f"   包含登录表单: {has_login_form}")
        print(f"   包含站内内容: {has_content}")
        
        if has_login_form:
            print("   ❌ Cookies 已过期，需要重新登录")
            return False
        elif has_content:
            print("   ✅ Cookies 有效，登录状态正常")
            return True
        else:
            print("   ⚠️ 无法确定登录状态")
            debug_file = Path(__file__).parent / "debug_html" / "login_test.html"
            debug_file.parent.mkdir(exist_ok=True)
            debug_file.write_text(html, encoding="utf-8")
            print(f"   📄 页面内容已保存到: {debug_file}")
            return None
            
    except Exception as e:
        print(f"   ❌ 访问失败: {e}")
        return False
    
    # 3. 测试获取场次列表
    print("\n[3] 测试获取场次列表")
    try:
        matches = client.fetch_match_list_v2(rows=10, days=1, force_refresh=True)
        print(f"   ✅ 成功获取 {len(matches)} 场比赛")
        
        if matches:
            print("\n   前 3 场比赛:")
            for i, match in enumerate(matches[:3], 1):
                label = match.get("label", "未知比赛")
                detail_url = match.get("detail_url", "")
                print(f"   {i}. {label}")
                print(f"      完整URL: {detail_url}")
                print(f"      detail_params: {match.get('detail_params', {})}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 获取场次失败: {e}")
        return False

def main():
    """主函数"""
    try:
        result = test_cookies()
        
        print("\n" + "=" * 60)
        if result is True:
            print("✅ 登录状态正常，可以开始抓取明细")
            print("\n下一步操作:")
            print("1. 访问 http://127.0.0.1:5001/collect")
            print("2. 点击'获取场次'按钮")
            print("3. 选择比赛并点击'抓取明细'")
        elif result is False:
            print("❌ 登录状态异常，需要重新登录")
            print("\n解决方法:")
            print("1. 访问 http://127.0.0.1:5001/collect")
            print("2. 点击'获取验证码'")
            print("3. 输入验证码并提交")
            print("4. 登录成功后再次运行此脚本")
        else:
            print("⚠️ 无法确定登录状态")
            print("\n请检查:")
            print("1. 网络连接是否正常")
            print("2. 必发指数网是否可访问")
            print("3. debug_html/login_test.html 文件内容")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
