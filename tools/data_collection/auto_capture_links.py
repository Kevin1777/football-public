#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动捕获明细链接（无头模式，适合服务器）
自动点击按钮并捕获真实的明细页面链接
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from services import BifawClient
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import json

BASE_DIR = Path(__file__).resolve().parent
DEBUG_DIR = BASE_DIR / "debug_html"
DEBUG_DIR.mkdir(exist_ok=True)

def capture_detail_links():
    """自动点击按钮并捕获明细链接"""
    print("="*80)
    print("自动捕获明细链接（无头模式）")
    print("="*80)
    
    client = BifawClient()
    
    # 检查登录状态
    status = client.get_cookie_status()
    if not status.get("exists"):
        print("\n❌ 未登录，请先访问 http://127.0.0.1:5001/collect 完成登录")
        return
    
    print(f"\n✅ 已登录 (最后更新: {status.get('updated_at')})")
    
    print("\n正在启动Selenium...")
    driver = client._init_driver()
    
    try:
        # 注入cookies
        print("正在注入cookies...")
        client._inject_cookies(driver)
        
        # 访问列表页
        target_url = "https://www.bifaw.com/bifaw/index.php"
        print(f"\n访问列表页: {target_url}")
        driver.get(target_url)
        
        # 等待页面加载
        print("等待页面加载...")
        WebDriverWait(driver, 15).until(
            lambda d: "标盘明细" in d.page_source or "必发指数" in d.page_source
        )
        
        # 额外等待JS执行
        time.sleep(3)
        print("✅ 页面加载完成\n")
        
        # 保存页面HTML
        html_path = DEBUG_DIR / f"list_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_path.write_text(driver.page_source, encoding="utf-8", errors="ignore")
        print(f"页面HTML已保存: {html_path}\n")
        
        # 查找所有"标盘明细"按钮（包括 <li> 标签）
        print("正在查找'标盘明细'按钮...")
        detail_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '标盘明细')] | //a[contains(text(), '标盘明细')] | //button[contains(text(), '标盘明细')]")
        
        if not detail_buttons:
            print("❌ 未找到'标盘明细'按钮")
            print("\n尝试查找其他可能的按钮...")
            # 尝试查找包含"明细"的按钮
            detail_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '明细')] | //*[contains(text(), '明细')]")
        
        if not detail_buttons:
            print("❌ 仍未找到任何明细按钮")
            return
        
        print(f"✅ 找到 {len(detail_buttons)} 个按钮\n")
        
        # 点击前5个按钮捕获链接
        captured_links = []
        max_buttons = min(5, len(detail_buttons))
        
        print(f"开始点击前 {max_buttons} 个按钮...\n")
        print("="*80)
        
        for idx in range(max_buttons):
            try:
                # 重新获取按钮（避免stale element）
                detail_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '标盘明细')]")
                if idx >= len(detail_buttons):
                    break
                
                btn = detail_buttons[idx]
                
                print(f"\n[按钮 {idx+1}/{max_buttons}]")
                
                # 获取按钮信息
                try:
                    btn_text = btn.text or btn.get_attribute('value') or '(无文本)'
                    btn_href = btn.get_attribute('href') or ''
                    btn_onclick = btn.get_attribute('onclick') or ''
                    btn_tag = btn.tag_name
                    
                    print(f"  标签: {btn_tag}")
                    print(f"  按钮文本: {btn_text[:50]}")
                    if btn_href:
                        print(f"  href: {btn_href[:80]}")
                    if btn_onclick:
                        print(f"  onclick: {btn_onclick}")
                        print(f"  🔍 检测到onclick事件！")
                except Exception as e:
                    print(f"  ⚠️  获取按钮信息失败: {e}")
                
                # 记录当前窗口
                original_windows = set(driver.window_handles)
                original_url = driver.current_url
                
                # 点击按钮
                print(f"  ⏳ 正在点击...")
                try:
                    btn.click()
                except Exception as click_error:
                    print(f"  ⚠️  点击失败: {click_error}")
                    # 尝试用JS点击
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"  ✓ 使用JS点击成功")
                    except:
                        print(f"  ✗ JS点击也失败，跳过")
                        continue
                
                # 等待响应
                time.sleep(2)
                
                # 检查是否打开了新窗口
                new_windows = set(driver.window_handles) - original_windows
                
                if new_windows:
                    # 切换到新窗口
                    new_window = new_windows.pop()
                    driver.switch_to.window(new_window)
                    
                    # 等待页面加载
                    time.sleep(1)
                    
                    # 获取新窗口URL
                    detail_url = driver.current_url
                    page_title = driver.title or "(无标题)"
                    
                    print(f"  ✅ 新窗口已打开")
                    print(f"  📄 标题: {page_title[:50]}")
                    print(f"  🔗 URL: {detail_url}")
                    
                    # 检查是否是matchDetails.php
                    if "matchDetails.php" in detail_url:
                        print(f"  🎉🎉🎉 这是正确的 matchDetails.php 链接！")
                        
                        # 保存页面内容
                        detail_html_path = DEBUG_DIR / f"detail_{idx+1}_{datetime.now().strftime('%H%M%S')}.html"
                        try:
                            detail_html_path.write_text(driver.page_source, encoding="utf-8", errors="ignore")
                            print(f"  💾 明细页面已保存: {detail_html_path.name}")
                        except:
                            pass
                    
                    captured_links.append({
                        "index": idx + 1,
                        "url": detail_url,
                        "title": page_title,
                        "is_match_details": "matchDetails.php" in detail_url
                    })
                    
                    # 关闭新窗口
                    driver.close()
                    driver.switch_to.window(list(original_windows)[0])
                    
                else:
                    # 检查当前页面URL是否改变
                    current_url = driver.current_url
                    if current_url != original_url:
                        print(f"  ✅ 当前页面已跳转")
                        print(f"  🔗 URL: {current_url}")
                        
                        if "matchDetails.php" in current_url:
                            print(f"  🎉🎉🎉 这是正确的 matchDetails.php 链接！")
                        
                        captured_links.append({
                            "index": idx + 1,
                            "url": current_url,
                            "title": driver.title or "(无标题)",
                            "is_match_details": "matchDetails.php" in current_url
                        })
                        
                        # 返回列表页
                        driver.back()
                        time.sleep(2)
                    else:
                        print(f"  ⚠️  页面未发生变化")
                
            except Exception as e:
                print(f"  ❌ 处理第 {idx+1} 个按钮时出错: {e}")
                continue
        
        # 输出汇总
        print("\n" + "="*80)
        print("捕获完成！")
        print("="*80)
        print(f"\n📊 统计信息:")
        print(f"  - 尝试点击: {max_buttons} 个按钮")
        print(f"  - 成功捕获: {len(captured_links)} 个链接")
        
        match_details_count = sum(1 for link in captured_links if link['is_match_details'])
        print(f"  - matchDetails.php: {match_details_count} 个")
        
        if captured_links:
            print(f"\n📝 捕获到的链接：")
            print("-"*80)
            for link in captured_links:
                print(f"\n{link['index']}. {link['title'][:50]}")
                print(f"   {link['url']}")
                if link['is_match_details']:
                    print(f"   ✅ matchDetails.php 链接")
        
        # 保存结果到JSON
        result_file = DEBUG_DIR / f"captured_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(captured_links, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存到: {result_file}")
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n正在关闭浏览器...")
        driver.quit()

if __name__ == "__main__":
    capture_detail_links()
