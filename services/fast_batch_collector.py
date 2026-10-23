#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速并发采集器 - 使用浏览器池加速抓取
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from services.selenium_pool import get_selenium_pool
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class FastBatchCollector:
    """快速并发采集器"""
    
    def __init__(
        self,
        bifaw_client,
        lottery500_client,
        detail_cache_manager,
        pool_size: int = 3,
        max_workers: int = 3
    ):
        self.bifaw_client = bifaw_client
        self.lottery500_client = lottery500_client
        self.detail_cache_manager = detail_cache_manager
        self.pool_size = pool_size
        self.max_workers = max_workers
        self._pool = None
    
    def _init_pool(self):
        """初始化浏览器池"""
        if self._pool is None:
            self._pool = get_selenium_pool(pool_size=self.pool_size, headless=True)
            
            # 注入 cookies
            try:
                cookies = self.bifaw_client._load_cookie_file()
                if cookies:
                    self._pool.set_cookies(cookies)
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {e}")
            
            # 预热
            self._pool.warmup(self.pool_size)
    
    def collect_date(
        self,
        target_date: datetime,
        rows: int = 200,
        skip_cached: bool = True,
        filter_by_handicap: bool = True
    ) -> Dict:
        """
        采集单天数据
        
        Args:
            target_date: 目标日期
            rows: 最大比赛数
            skip_cached: 是否跳过已缓存
            filter_by_handicap: 是否过滤有盘口的比赛
        
        Returns:
            采集结果统计
        """
        self._init_pool()
        
        date_str = target_date.strftime("%Y-%m-%d")
        results = {
            'date': date_str,
            'total': 0,
            'collected': 0,
            'failed': 0,
            'skipped': 0,
            'no_handicap': 0
        }
        
        start_time = time.time()
        
        # 1. 获取比赛列表
        logger.info(f"获取 {date_str} 的比赛列表...")
        page_html, matches, metadata = self.bifaw_client.fetch_finished_matches(
            target_date=target_date,
            rows=rows
        )
        
        if not matches:
            logger.warning(f"{date_str} 没有比赛数据")
            return results
        
        results['total'] = len(matches)
        logger.info(f"获取到 {len(matches)} 场比赛")
        
        # 2. 预获取盘口数据（批量）
        logger.info("预获取盘口数据...")
        handicap_cache = {}
        
        # 收集所有需要的日期
        dates_needed = set()
        for match in matches:
            kickoff = match.get('kickoff', '')
            if ' ' in kickoff:
                match_date = kickoff.split(' ')[0]
                dates_needed.add(match_date)
        
        # 批量获取每日盘口
        for d in dates_needed:
            daily = self.lottery500_client.fetch_daily_handicaps(d, use_cache=True)
            if daily:
                handicap_cache[d] = daily
        
        # 3. 过滤和准备任务
        tasks = []
        for match in matches:
            # 检查缓存
            if skip_cached:
                cached = self.detail_cache_manager.load_detail(match)
                if cached:
                    results['skipped'] += 1
                    continue
            
            # 获取盘口
            kickoff = match.get('kickoff', '')
            handicap = self.lottery500_client.get_handicap(
                home=match.get('home', ''),
                away=match.get('away', ''),
                kickoff=kickoff
            )
            
            # 检查是否是重要比赛（欧冠、欧联杯、五大联赛等）
            league = match.get('league', '').lower()
            is_important = any(x in league for x in [
                '欧冠', '欧联', '英超', '西甲', '德甲', '意甲', '法甲',
                '中超', '亚冠', '世界杯', '欧洲杯', '英联杯', '足总杯'
            ])
            
            if filter_by_handicap and not handicap and not is_important:
                results['no_handicap'] += 1
                continue
            
            tasks.append({
                'match': match,
                'handicap': handicap
            })
        
        logger.info(f"准备采集 {len(tasks)} 场比赛")
        
        # 4. 并发采集
        if tasks:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._collect_single, task): task
                    for task in tasks
                }
                
                for i, future in enumerate(as_completed(futures), 1):
                    task = futures[future]
                    match = task['match']
                    label = f"{match.get('home')} vs {match.get('away')}"
                    
                    try:
                        success = future.result()
                        if success:
                            results['collected'] += 1
                            logger.info(f"[{i}/{len(tasks)}] ✅ {label}")
                        else:
                            results['failed'] += 1
                            logger.warning(f"[{i}/{len(tasks)}] ❌ {label}")
                    except Exception as e:
                        results['failed'] += 1
                        logger.error(f"[{i}/{len(tasks)}] ❌ {label}: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"采集完成! 耗时: {elapsed:.1f}秒")
        logger.info(f"  成功: {results['collected']}, 失败: {results['failed']}, 跳过: {results['skipped']}, 无盘口: {results['no_handicap']}")
        
        return results
    
    def _collect_single(self, task: Dict) -> bool:
        """采集单场比赛"""
        match = task['match']
        handicap = task['handicap']
        
        detail_url = match.get('detail_url')
        if not detail_url:
            return False
        
        try:
            with self._pool.get_driver() as driver:
                # 访问明细页面
                driver.get(detail_url)
                
                # 等待数据加载
                try:
                    WebDriverWait(driver, 20).until(
                        lambda d: len(d.find_elements(By.TAG_NAME, "table")) > 3
                    )
                except:
                    pass
                
                # 滚动加载
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                
                # 获取 HTML
                html = driver.page_source
                
                if not html or len(html) < 1000:
                    return False
                
                # 解析数据
                from parser.html_parser import parse_bifa_html
                parsed_data = parse_bifa_html(html, match=match)
                
                if not hasattr(parsed_data, 'shape') or parsed_data.shape[0] == 0:
                    return False
                
                # 保存数据
                metadata = parsed_data.attrs.get('metadata', []) if hasattr(parsed_data, 'attrs') else []
                self.detail_cache_manager.save_detail(
                    match_info=match,
                    trade_data=parsed_data,
                    handicap_data=handicap or {},
                    metadata=metadata
                )
                
                return True
                
        except Exception as e:
            logger.error(f"采集失败: {e}")
            return False
    
    def collect_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> Dict:
        """采集日期范围"""
        results = {
            'total_days': 0,
            'total_matches': 0,
            'collected': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        current = start_date
        while current <= end_date:
            results['total_days'] += 1
            
            day_result = self.collect_date(current, **kwargs)
            results['total_matches'] += day_result['total']
            results['collected'] += day_result['collected']
            results['failed'] += day_result['failed']
            results['skipped'] += day_result['skipped']
            results['details'].append(day_result)
            
            current += timedelta(days=1)
        
        return results
    
    def shutdown(self):
        """关闭资源"""
        if self._pool:
            self._pool.shutdown()
