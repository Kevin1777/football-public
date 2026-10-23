#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Selenium辅助函数：用于获取真实的明细链接
"""

import time
from typing import Dict, List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import re

def capture_detail_urls_from_buttons(driver, max_buttons: int = 50) -> Dict[str, str]:
    """
    通过点击'标盘明细'按钮获取真实的明细链接
    
    Args:
        driver: Selenium WebDriver实例
        max_buttons: 最多点击的按钮数量
        
    Returns:
        Dict[match_id, detail_url]: match_id到真实明细URL的映射
    """
    url_map = {}
    
    try:
        # 查找所有"标盘明细"按钮
        detail_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '标盘明细')]")
        
        if not detail_buttons:
            print("⚠️  未找到'标盘明细'按钮")
            return url_map
        
        print(f"找到 {len(detail_buttons)} 个按钮，开始捕获前 {min(max_buttons, len(detail_buttons))} 个...")
        
        for idx in range(min(max_buttons, len(detail_buttons))):
            try:
                # 重新获取按钮（避免stale element）
                detail_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '标盘明细')]")
                if idx >= len(detail_buttons):
                    break
                
                btn = detail_buttons[idx]
                
                # 获取onclick属性来提取match_id
                onclick = btn.get_attribute('onclick') or ''
                match_id = None
                
                # 从onclick中提取match_id: openMatchDetails('34966406',...)
                match = re.search(r"openMatchDetails\('(\d+)'", onclick)
                if match:
                    match_id = match.group(1)
                
                if not match_id:
                    continue
                
                # 记录当前窗口
                original_windows = set(driver.window_handles)
                
                # 点击按钮
                try:
                    btn.click()
                except:
                    # 使用JS点击
                    driver.execute_script("arguments[0].click();", btn)
                
                # 等待新窗口
                time.sleep(1)
                new_windows = set(driver.window_handles) - original_windows
                
                if new_windows:
                    # 切换到新窗口
                    new_window = new_windows.pop()
                    driver.switch_to.window(new_window)
                    
                    # 获取真实URL
                    detail_url = driver.current_url
                    
                    if "matchDetails.php" in detail_url:
                        url_map[match_id] = detail_url
                        if (idx + 1) % 10 == 0:
                            print(f"  已捕获 {idx + 1} 个链接...")
                    
                    # 关闭新窗口
                    driver.close()
                    driver.switch_to.window(list(original_windows)[0])
                    
                    # 短暂延迟
                    time.sleep(0.3)
                    
            except Exception as e:
                # 静默处理错误，继续下一个
                try:
                    # 确保回到主窗口
                    main_window = list(driver.window_handles)[0]
                    driver.switch_to.window(main_window)
                except:
                    pass
                continue
        
        print(f"✅ 成功捕获 {len(url_map)} 个真实明细链接")
        
    except Exception as e:
        print(f"❌ 捕获链接时出错: {e}")
    
    return url_map


def capture_ou_detail_urls_from_buttons(driver, max_buttons: int = 50) -> Dict[str, Dict]:
    """
    通过点击'大小明细'按钮获取真实的大小球明细链接
    
    🔥 参照 capture_detail_urls_from_buttons 实现
    
    Args:
        driver: Selenium WebDriver实例
        max_buttons: 最多点击的按钮数量
        
    Returns:
        Dict[match_key, {'url': str, 'hdp': str}]: 比赛到大小球明细URL的映射
    """
    url_map = {}
    
    try:
        # 查找所有包含"大小明细"的按钮/链接
        # 按钮格式: "2.5大小明细" 或 "X.X大小明细"
        ou_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '大小明细')]")
        
        if not ou_buttons:
            # 尝试其他选择器
            ou_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '大小明细')]")
        
        if not ou_buttons:
            print("⚠️  未找到'大小明细'按钮")
            return url_map
        
        print(f"🏀 找到 {len(ou_buttons)} 个大小明细按钮，开始捕获前 {min(max_buttons, len(ou_buttons))} 个...")
        
        for idx in range(min(max_buttons, len(ou_buttons))):
            try:
                # 重新获取按钮（避免stale element）
                ou_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '大小明细')]")
                if not ou_buttons:
                    ou_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '大小明细')]")
                if idx >= len(ou_buttons):
                    break
                
                btn = ou_buttons[idx]
                btn_text = btn.text.strip()  # 如 "2.5大小明细"
                
                # 提取盘口值（如2.5）
                hdp_match = re.search(r'([\d.]+)大小明细', btn_text)
                hdp = hdp_match.group(1) if hdp_match else None
                
                # 获取onclick属性
                onclick = btn.get_attribute('onclick') or ''
                
                # 🔥 从onclick提取match_id（与标盘明细保持一致）
                match_id = None
                try:
                    # 查找同一行的标盘明细按钮来获取match_id
                    parent_row = btn.find_element(By.XPATH, "./ancestor::tr")
                    bp_btn = parent_row.find_element(By.XPATH, ".//li[contains(text(), '标盘明细')]")
                    onclick = bp_btn.get_attribute('onclick') or ''
                    match = re.search(r"openMatchDetails\('(\d+)'", onclick)
                    if match:
                        match_id = match.group(1)
                except:
                    pass
                
                if not match_id:
                    # 备用：尝试从大小球按钮的onclick提取
                    try:
                        ou_onclick = btn.get_attribute('onclick') or ''
                        match = re.search(r"'(\d{7,})'", ou_onclick)
                        if match:
                            match_id = match.group(1)
                    except:
                        pass
                
                if not match_id:
                    match_key = f"match_{idx}"
                else:
                    match_key = match_id
                
                # 记录当前窗口
                original_windows = set(driver.window_handles)
                
                # 点击按钮
                try:
                    btn.click()
                except:
                    # 使用JS点击
                    driver.execute_script("arguments[0].click();", btn)
                
                # 等待新窗口
                time.sleep(1)
                new_windows = set(driver.window_handles) - original_windows
                
                if new_windows:
                    # 切换到新窗口
                    new_window = new_windows.pop()
                    driver.switch_to.window(new_window)
                    
                    # 获取真实URL
                    detail_url = driver.current_url
                    
                    if "ouDetails.php" in detail_url:
                        url_map[match_key] = {
                            'url': detail_url,
                            'hdp': hdp,
                        }
                        if (idx + 1) % 10 == 0:
                            print(f"  🏀 已捕获 {idx + 1} 个大小球明细链接...")
                    
                    # 关闭新窗口
                    driver.close()
                    driver.switch_to.window(list(original_windows)[0])
                    
                    # 短暂延迟
                    time.sleep(0.3)
                    
            except Exception as e:
                # 静默处理错误，继续下一个
                try:
                    # 确保回到主窗口
                    main_window = list(driver.window_handles)[0]
                    driver.switch_to.window(main_window)
                except:
                    pass
                continue
        
        print(f"✅ 成功捕获 {len(url_map)} 个大小球明细链接")
        
    except Exception as e:
        print(f"❌ 捕获大小球链接时出错: {e}")
    
    return url_map



def capture_handicap_detail_urls_from_buttons(driver, max_buttons: int = 50) -> Dict[str, Dict]:
    """
    通过点击'让球指数'按钮获取真实的让球指数明细链接 (AisaDetails.php)
    
    Args:
        driver: Selenium WebDriver实例
        max_buttons: 最多点击的按钮数量
        
    Returns:
        Dict[match_id, {'url': str, 'hdp': str}]: match_id到让球指数明细URL的映射
    """
    url_map = {}
    
    try:
        # 查找所有包含"让球指数"或类似文本的按钮
        # 按钮格式可能是: "让球指数" 或 "-0.75让球" 或 "亚盘明细"
        hdp_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '让球')]")
        
        if not hdp_buttons:
            # 尝试其他选择器
            hdp_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '让球指数')]")
        
        if not hdp_buttons:
            # 尝试查找亚盘相关按钮
            hdp_buttons = driver.find_elements(By.XPATH, "//li[contains(@onclick, 'AisaDetails')]")
        
        if not hdp_buttons:
            print("⚠️  未找到'让球指数'按钮")
            return url_map
        
        print(f"🎯 找到 {len(hdp_buttons)} 个让球指数按钮，开始捕获前 {min(max_buttons, len(hdp_buttons))} 个...")
        
        for idx in range(min(max_buttons, len(hdp_buttons))):
            try:
                # 重新获取按钮（避免stale element）
                hdp_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '让球')]")
                if not hdp_buttons:
                    hdp_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '让球指数')]")
                if not hdp_buttons:
                    hdp_buttons = driver.find_elements(By.XPATH, "//li[contains(@onclick, 'AisaDetails')]")
                if idx >= len(hdp_buttons):
                    break
                
                btn = hdp_buttons[idx]
                btn_text = btn.text.strip()
                
                # 提取让球数（如 -0.75）
                hdp_match = re.search(r'(-?[\d.]+)让球', btn_text)
                hdp = hdp_match.group(1) if hdp_match else None
                
                # 获取match_id
                match_id = None
                try:
                    # 查找同一行的标盘明细按钮来获取match_id
                    parent_row = btn.find_element(By.XPATH, "./ancestor::tr")
                    bp_btn = parent_row.find_element(By.XPATH, ".//li[contains(text(), '标盘明细')]")
                    onclick = bp_btn.get_attribute('onclick') or ''
                    match = re.search(r"openMatchDetails\('(\d+)'", onclick)
                    if match:
                        match_id = match.group(1)
                except:
                    pass
                
                if not match_id:
                    # 备用：从按钮onclick提取
                    try:
                        onclick = btn.get_attribute('onclick') or ''
                        match = re.search(r"'(\d{7,})'", onclick)
                        if match:
                            match_id = match.group(1)
                    except:
                        pass
                
                if not match_id:
                    match_key = f"match_{idx}"
                else:
                    match_key = match_id
                
                # 记录当前窗口
                original_windows = set(driver.window_handles)
                
                # 点击按钮
                try:
                    btn.click()
                except:
                    driver.execute_script("arguments[0].click();", btn)
                
                # 等待新窗口
                time.sleep(1)
                new_windows = set(driver.window_handles) - original_windows
                
                if new_windows:
                    new_window = new_windows.pop()
                    driver.switch_to.window(new_window)
                    
                    detail_url = driver.current_url
                    
                    if "AisaDetails.php" in detail_url or "aisa" in detail_url.lower():
                        url_map[match_key] = {
                            'url': detail_url,
                            'hdp': hdp,
                        }
                        if (idx + 1) % 10 == 0:
                            print(f"  🎯 已捕获 {idx + 1} 个让球指数明细链接...")
                    
                    driver.close()
                    driver.switch_to.window(list(original_windows)[0])
                    time.sleep(0.3)
                    
            except Exception as e:
                try:
                    main_window = list(driver.window_handles)[0]
                    driver.switch_to.window(main_window)
                except:
                    pass
                continue
        
        print(f"✅ 成功捕获 {len(url_map)} 个让球指数明细链接")
        
    except Exception as e:
        print(f"❌ 捕获让球指数链接时出错: {e}")
    
    return url_map


def capture_correct_score_urls_from_buttons(driver, max_buttons: int = 50) -> Dict[str, Dict]:
    """
    通过点击'比分'按钮获取真实的比分明细链接 (CorrectDetails.php)
    
    Args:
        driver: Selenium WebDriver实例
        max_buttons: 最多点击的按钮数量
        
    Returns:
        Dict[match_id, {'url': str}]: match_id到比分明细URL的映射
    """
    url_map = {}
    
    try:
        # 查找所有包含"比分"的按钮
        # 按钮格式可能是: "比分" 或 "波胆" 或 "比分明细"
        cs_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '比分')]")
        
        if not cs_buttons:
            cs_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '波胆')]")
        
        if not cs_buttons:
            cs_buttons = driver.find_elements(By.XPATH, "//li[contains(@onclick, 'CorrectDetails')]")
        
        if not cs_buttons:
            print("⚠️  未找到'比分'按钮")
            return url_map
        
        print(f"📊 找到 {len(cs_buttons)} 个比分按钮，开始捕获前 {min(max_buttons, len(cs_buttons))} 个...")
        
        for idx in range(min(max_buttons, len(cs_buttons))):
            try:
                # 重新获取按钮
                cs_buttons = driver.find_elements(By.XPATH, "//li[contains(text(), '比分')]")
                if not cs_buttons:
                    cs_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '波胆')]")
                if not cs_buttons:
                    cs_buttons = driver.find_elements(By.XPATH, "//li[contains(@onclick, 'CorrectDetails')]")
                if idx >= len(cs_buttons):
                    break
                
                btn = cs_buttons[idx]
                
                # 获取match_id
                match_id = None
                try:
                    parent_row = btn.find_element(By.XPATH, "./ancestor::tr")
                    bp_btn = parent_row.find_element(By.XPATH, ".//li[contains(text(), '标盘明细')]")
                    onclick = bp_btn.get_attribute('onclick') or ''
                    match = re.search(r"openMatchDetails\('(\d+)'", onclick)
                    if match:
                        match_id = match.group(1)
                except:
                    pass
                
                if not match_id:
                    try:
                        onclick = btn.get_attribute('onclick') or ''
                        match = re.search(r"'(\d{7,})'", onclick)
                        if match:
                            match_id = match.group(1)
                    except:
                        pass
                
                if not match_id:
                    match_key = f"match_{idx}"
                else:
                    match_key = match_id
                
                original_windows = set(driver.window_handles)
                
                try:
                    btn.click()
                except:
                    driver.execute_script("arguments[0].click();", btn)
                
                time.sleep(1)
                new_windows = set(driver.window_handles) - original_windows
                
                if new_windows:
                    new_window = new_windows.pop()
                    driver.switch_to.window(new_window)
                    
                    detail_url = driver.current_url
                    
                    if "CorrectDetails.php" in detail_url or "correct" in detail_url.lower():
                        url_map[match_key] = {
                            'url': detail_url,
                        }
                        if (idx + 1) % 10 == 0:
                            print(f"  📊 已捕获 {idx + 1} 个比分明细链接...")
                    
                    driver.close()
                    driver.switch_to.window(list(original_windows)[0])
                    time.sleep(0.3)
                    
            except Exception as e:
                try:
                    main_window = list(driver.window_handles)[0]
                    driver.switch_to.window(main_window)
                except:
                    pass
                continue
        
        print(f"✅ 成功捕获 {len(url_map)} 个比分明细链接")
        
    except Exception as e:
        print(f"❌ 捕获比分链接时出错: {e}")
    
    return url_map


def capture_all_detail_urls(driver, max_buttons: int = 30) -> Dict[str, Dict]:
    """
    一次性捕获所有类型的明细链接（标盘、大小球、让球指数、比分）
    
    Args:
        driver: Selenium WebDriver实例
        max_buttons: 每种类型最多点击的按钮数量
        
    Returns:
        Dict[match_id, {
            'standard_url': str,
            'ou_url': str,
            'ou_hdp': str,
            'handicap_url': str,
            'handicap_hdp': str,
            'correct_score_url': str,
        }]
    """
    all_urls = {}
    
    print("\n" + "="*60)
    print("开始捕获所有类型的明细链接...")
    print("="*60)
    
    # 1. 捕获标盘明细
    print("\n[1/4] 捕获标盘明细...")
    standard_urls = capture_detail_urls_from_buttons(driver, max_buttons)
    for match_id, url in standard_urls.items():
        if match_id not in all_urls:
            all_urls[match_id] = {}
        all_urls[match_id]['standard_url'] = url
    
    # 2. 捕获大小球明细
    print("\n[2/4] 捕获大小球明细...")
    ou_urls = capture_ou_detail_urls_from_buttons(driver, max_buttons)
    for match_id, data in ou_urls.items():
        if match_id not in all_urls:
            all_urls[match_id] = {}
        all_urls[match_id]['ou_url'] = data.get('url')
        all_urls[match_id]['ou_hdp'] = data.get('hdp')
    
    # 3. 捕获让球指数明细
    print("\n[3/4] 捕获让球指数明细...")
    hdp_urls = capture_handicap_detail_urls_from_buttons(driver, max_buttons)
    for match_id, data in hdp_urls.items():
        if match_id not in all_urls:
            all_urls[match_id] = {}
        all_urls[match_id]['handicap_url'] = data.get('url')
        all_urls[match_id]['handicap_hdp'] = data.get('hdp')
    
    # 4. 捕获比分明细
    print("\n[4/4] 捕获比分明细...")
    cs_urls = capture_correct_score_urls_from_buttons(driver, max_buttons)
    for match_id, data in cs_urls.items():
        if match_id not in all_urls:
            all_urls[match_id] = {}
        all_urls[match_id]['correct_score_url'] = data.get('url')
    
    print("\n" + "="*60)
    print(f"捕获完成！共 {len(all_urls)} 场比赛")
    print("="*60)
    
    return all_urls
