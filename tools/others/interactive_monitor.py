#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交互式监控模式：浏览器保持可见，你可以手动点击，程序会捕获所有URL变化和请求
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from utils.chrome_env import resolve_chrome_binary, resolve_chromedriver
import json

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies.json"
DEBUG_DIR = BASE_DIR / "debug_html"
DEBUG_DIR.mkdir(exist_ok=True)

def init_visible_driver():
    """初始化可见的浏览器"""
    options = Options()
    
    chrome_binary = resolve_chrome_binary()
    if not chrome_binary:
        raise RuntimeError("未找到 Chrome 浏览器")
    
    options.binary_location = chrome_binary
    # 注意：不使用 --headless，让浏览器可见
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # 启用性能日志以捕获网络请求
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    chromedriver_path = resolve_chromedriver()
    if not chromedriver_path:
        raise RuntimeError("未找到 chromedriver")
    
    try:
        service = Service(chromedriver_path, log_path="NUL")
    except TypeError:
        service = Service(chromedriver_path)
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver

def inject_cookies(driver):
    """注入cookies"""
    if not COOKIES_PATH.exists():
        print("❌ 未找到 cookies.json，请先登录")
        return False
    
    driver.get("https://www.bifaw.com")
    
    with open(COOKIES_PATH, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    
    driver.delete_all_cookies()
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        cookie = dict(cookie)
        cookie.pop("sameSite", None)
        expiry = cookie.get("expiry")
        if isinstance(expiry, float):
            cookie["expiry"] = int(expiry)
        domain = cookie.get("domain")
        if isinstance(domain, str) and domain.startswith("."):
            cookie["domain"] = domain.lstrip(".")
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"  注入cookie失败: {cookie.get('name')} - {e}")
    
    return True

def monitor_urls(driver, interval=1):
    """持续监控URL变化和网络请求"""
    print("\n" + "="*80)
    print("开始监控浏览器...")
    print("="*80)
    print("\n📌 说明：")
    print("  - 浏览器窗口已打开，你可以手动点击任何按钮")
    print("  - 程序会实时捕获所有URL变化和网络请求")
    print("  - 按 Ctrl+C 结束监控\n")
    
    last_url = ""
    captured_urls = []
    captured_requests = []
    
    log_file = DEBUG_DIR / f"monitor_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"监控开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        try:
            iteration = 0
            while True:
                iteration += 1
                current_url = driver.current_url
                
                # 检测URL变化
                if current_url != last_url:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"\n[{timestamp}] 🔗 URL变化:")
                    print(f"  {current_url}")
                    
                    f.write(f"\n[{timestamp}] URL变化:\n")
                    f.write(f"  {current_url}\n")
                    
                    # 特别标记matchDetails.php
                    if "matchDetails.php" in current_url:
                        print("  ✅✅✅ 这是 matchDetails.php 明细页面！")
                        f.write("  ✅✅✅ 这是 matchDetails.php 明细页面！\n")
                    
                    captured_urls.append({
                        "timestamp": timestamp,
                        "url": current_url
                    })
                    
                    last_url = current_url
                
                # 每5秒捕获一次网络日志（避免过于频繁）
                if iteration % 5 == 0:
                    try:
                        logs = driver.get_log('performance')
                        for log in logs:
                            message = json.loads(log['message'])
                            method = message.get('message', {}).get('method', '')
                            
                            # 只关注网络请求
                            if 'Network.request' in method or 'Network.response' in method:
                                params = message.get('message', {}).get('params', {})
                                request_url = params.get('request', {}).get('url') or params.get('response', {}).get('url')
                                
                                if request_url and 'bifaw' in request_url:
                                    if request_url not in [r['url'] for r in captured_requests]:
                                        timestamp = datetime.now().strftime('%H:%M:%S')
                                        print(f"[{timestamp}] 📡 网络请求: {request_url[:100]}...")
                                        
                                        f.write(f"[{timestamp}] 网络请求: {request_url}\n")
                                        
                                        if "matchDetails.php" in request_url:
                                            print("  ✅ 发现 matchDetails.php 请求！")
                                            f.write("  ✅ 发现 matchDetails.php 请求！\n")
                                        
                                        captured_requests.append({
                                            "timestamp": timestamp,
                                            "url": request_url
                                        })
                    except Exception as e:
                        pass  # 忽略日志读取错误
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("监控结束")
            print("="*80)
            
            f.write(f"\n\n{'='*80}\n")
            f.write(f"监控结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n\n")
            
            # 汇总输出
            print(f"\n📊 监控统计:")
            print(f"  - 捕获URL变化: {len(captured_urls)} 次")
            print(f"  - 捕获网络请求: {len(captured_requests)} 个")
            
            f.write(f"监控统计:\n")
            f.write(f"  - 捕获URL变化: {len(captured_urls)} 次\n")
            f.write(f"  - 捕获网络请求: {len(captured_requests)} 个\n\n")
            
            # 输出所有包含matchDetails的链接
            match_details_urls = [u for u in captured_urls if "matchDetails.php" in u['url']]
            match_details_requests = [r for r in captured_requests if "matchDetails.php" in r['url']]
            
            if match_details_urls or match_details_requests:
                print(f"\n✅ 找到 {len(match_details_urls) + len(match_details_requests)} 个 matchDetails.php 链接：")
                f.write(f"\n找到的 matchDetails.php 链接：\n")
                f.write("="*80 + "\n")
                
                for u in match_details_urls:
                    print(f"  [{u['timestamp']}] {u['url']}")
                    f.write(f"[{u['timestamp']}] {u['url']}\n")
                
                for r in match_details_requests:
                    if r['url'] not in [u['url'] for u in match_details_urls]:
                        print(f"  [{r['timestamp']}] {r['url']}")
                        f.write(f"[{r['timestamp']}] {r['url']}\n")
            else:
                print("\n⚠️  未发现 matchDetails.php 链接")
                f.write("\n未发现 matchDetails.php 链接\n")
            
            print(f"\n📝 详细日志已保存到: {log_file}")

def main():
    print("="*80)
    print("交互式浏览器监控")
    print("="*80)
    
    # 检查cookies
    if not COOKIES_PATH.exists():
        print("\n❌ 未找到 cookies.json")
        print("请先运行 Flask 服务器并完成登录：")
        print("  1. python app.py")
        print("  2. 访问 http://127.0.0.1:5001/collect")
        print("  3. 完成登录后再运行此脚本\n")
        return
    
    print("\n正在启动浏览器...")
    driver = init_visible_driver()
    
    try:
        print("正在注入 cookies...")
        if not inject_cookies(driver):
            driver.quit()
            return
        
        # 访问列表页
        print("\n正在访问列表页...")
        driver.get("https://www.bifaw.com/bifaw/index.php")
        
        # 等待页面加载
        time.sleep(3)
        
        print("\n✅ 浏览器已就绪！")
        print("\n现在你可以：")
        print("  1. 在浏览器窗口中手动点击'标盘明细'按钮")
        print("  2. 程序会自动捕获所有URL变化和网络请求")
        print("  3. 完成测试后，在命令行按 Ctrl+C 结束\n")
        
        # 开始监控
        monitor_urls(driver)
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n正在关闭浏览器...")
        driver.quit()

if __name__ == "__main__":
    main()
