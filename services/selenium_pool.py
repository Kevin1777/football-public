#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Selenium 浏览器池 - 用于加速并发抓取
复用浏览器实例，避免重复启动
"""

import logging
import threading
import time
from queue import Queue, Empty
from typing import Optional
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from utils.chrome_env import resolve_chrome_binary, resolve_chromedriver

logger = logging.getLogger(__name__)


class SeleniumPool:
    """Selenium 浏览器池，复用浏览器实例"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, pool_size: int = 3, headless: bool = True):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.pool_size = pool_size
        self.headless = headless
        self._pool: Queue = Queue()
        self._all_drivers: list = []
        self._create_lock = threading.Lock()
        self._cookies_injected = False
        self._cookies = None
        
        logger.info(f"初始化 Selenium 浏览器池，大小: {pool_size}")
    
    def _create_driver(self) -> webdriver.Chrome:
        """创建新的浏览器实例"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # 设置 Chrome 路径
        chrome_binary = resolve_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        
        # 设置 ChromeDriver 路径
        chromedriver_path = resolve_chromedriver()
        service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        
        return driver
    
    def set_cookies(self, cookies: list):
        """设置要注入的 cookies"""
        self._cookies = cookies
        self._cookies_injected = False
    
    def _inject_cookies(self, driver: webdriver.Chrome):
        """注入 cookies 到浏览器"""
        if not self._cookies:
            return
        
        try:
            # 先访问目标域名
            driver.get("https://www.bifaw.com/bifaw/index.php")
            time.sleep(1)
            
            # 注入 cookies
            for cookie in self._cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"注入 cookie 失败: {e}")
            
            # 刷新页面使 cookies 生效
            driver.refresh()
            time.sleep(1)
            
        except Exception as e:
            logger.warning(f"注入 cookies 失败: {e}")
    
    @contextmanager
    def get_driver(self):
        """获取一个浏览器实例（上下文管理器）"""
        driver = None
        
        try:
            # 尝试从池中获取
            try:
                driver = self._pool.get_nowait()
                logger.debug("从池中获取浏览器实例")
            except Empty:
                # 池为空，创建新实例
                with self._create_lock:
                    if len(self._all_drivers) < self.pool_size:
                        driver = self._create_driver()
                        self._all_drivers.append(driver)
                        
                        # 注入 cookies
                        if self._cookies:
                            self._inject_cookies(driver)
                        
                        logger.info(f"创建新浏览器实例，当前总数: {len(self._all_drivers)}")
                    else:
                        # 等待池中有可用实例
                        driver = self._pool.get(timeout=60)
            
            yield driver
            
        finally:
            if driver:
                try:
                    # 清理状态，关闭多余窗口
                    handles = driver.window_handles
                    if len(handles) > 1:
                        for handle in handles[1:]:
                            driver.switch_to.window(handle)
                            driver.close()
                        driver.switch_to.window(handles[0])
                    
                    # 归还到池中
                    self._pool.put(driver)
                    logger.debug("浏览器实例归还到池中")
                except Exception as e:
                    logger.warning(f"归还浏览器实例失败: {e}")
                    # 实例可能已损坏，从列表中移除
                    if driver in self._all_drivers:
                        self._all_drivers.remove(driver)
                    try:
                        driver.quit()
                    except:
                        pass
    
    def warmup(self, count: int = None):
        """预热浏览器池"""
        count = count or self.pool_size
        logger.info(f"预热浏览器池，创建 {count} 个实例...")
        
        for i in range(count):
            if len(self._all_drivers) >= self.pool_size:
                break
            
            try:
                driver = self._create_driver()
                self._all_drivers.append(driver)
                
                if self._cookies:
                    self._inject_cookies(driver)
                
                self._pool.put(driver)
                logger.info(f"预热完成 {i+1}/{count}")
            except Exception as e:
                logger.error(f"预热失败: {e}")
        
        logger.info(f"浏览器池预热完成，共 {len(self._all_drivers)} 个实例")
    
    def shutdown(self):
        """关闭所有浏览器实例"""
        logger.info("关闭浏览器池...")
        
        for driver in self._all_drivers:
            try:
                driver.quit()
            except:
                pass
        
        self._all_drivers.clear()
        
        # 清空队列
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except:
                pass
        
        logger.info("浏览器池已关闭")
    
    def __del__(self):
        self.shutdown()


# 全局单例
_pool_instance: Optional[SeleniumPool] = None


def get_selenium_pool(pool_size: int = 3, headless: bool = True) -> SeleniumPool:
    """获取全局浏览器池实例"""
    global _pool_instance
    
    if _pool_instance is None:
        _pool_instance = SeleniumPool(pool_size=pool_size, headless=headless)
    
    return _pool_instance
