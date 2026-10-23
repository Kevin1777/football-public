"""
四合一超级采集服务

整合标盘、大小球、让球、比分四种交易明细的采集
支持后台采集和日期区间采集
"""

import json
import logging
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import queue

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class SuperCollector:
    """
    四合一超级采集器
    
    采集内容：
    1. 标盘明细 - 胜平负交易数据
    2. 大小球明细 - 大小球交易数据  
    3. 让球指数明细 - 亚盘交易数据
    4. 比分明细 - 波胆交易数据
    5. 所有盘口列表 - 让球和大小球的所有盘口
    """
    
    def __init__(self, bifaw_client=None, selenium_helper=None):
        self.bifaw_client = bifaw_client
        self.selenium_helper = selenium_helper
        self._driver = None
        self._driver_lock = threading.Lock()
    
    def collect_match_super_detail(
        self,
        match: Dict,
        urls: Dict,
        driver: webdriver.Chrome = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        """
        采集单场比赛的四合一数据
        
        Args:
            match: 比赛信息
            urls: 各类明细URL字典
            driver: Selenium WebDriver实例
            progress_callback: 进度回调函数 (progress, message)
        
        Returns:
            四合一数据字典
        """
        from parser.html_parser import parse_bifa_html
        from parser.super_detail_parser import (
            parse_handicap_trade_html,
            parse_correct_score_html,
            create_super_json
        )
        
        result = {
            'standard_data': None,
            'ou_data': None,
            'handicap_data': None,
            'correct_score_data': None,
            'success': False,
            'error': None
        }
        
        own_driver = False
        if driver is None:
            driver = self._create_driver()
            own_driver = True
        
        try:
            match_id = match.get('match_id', 'unknown')
            
            # ========== 1. 采集标盘数据 ==========
            if urls.get('standard_url'):
                if progress_callback:
                    progress_callback(20, '正在获取标盘数据...')
                
                try:
                    standard_data = self._collect_standard_data(
                        driver, urls['standard_url'], match_id
                    )
                    if standard_data:
                        result['standard_data'] = standard_data
                        logger.info(f"  标盘数据: {standard_data.get('total_records', 0)}条")
                except Exception as e:
                    logger.warning(f"  标盘采集失败: {e}")
            
            # ========== 2. 采集大小球数据 ==========
            if urls.get('ou_url'):
                if progress_callback:
                    progress_callback(40, '正在获取大小球数据...')
                
                try:
                    ou_data = self._collect_trade_data(
                        driver, urls['ou_url'], 'ou', urls.get('ou_hdp')
                    )
                    if ou_data:
                        result['ou_data'] = ou_data
                        logger.info(f"  大小球数据: {len(ou_data.get('trade_records', []))}条")
                except Exception as e:
                    logger.warning(f"  大小球采集失败: {e}")
            
            # ========== 3. 采集让球数据 ==========
            if urls.get('handicap_url'):
                if progress_callback:
                    progress_callback(60, '正在获取让球数据...')
                
                try:
                    handicap_data = self._collect_trade_data(
                        driver, urls['handicap_url'], 'handicap', urls.get('handicap_hdp')
                    )
                    if handicap_data:
                        result['handicap_data'] = handicap_data
                        logger.info(f"  让球数据: {len(handicap_data.get('trade_records', []))}条")
                except Exception as e:
                    logger.warning(f"  让球采集失败: {e}")
            
            # ========== 4. 采集比分数据 ==========
            if urls.get('correct_score_url'):
                if progress_callback:
                    progress_callback(80, '正在获取比分数据...')
                
                try:
                    correct_score_data = self._collect_trade_data(
                        driver, urls['correct_score_url'], 'correct_score'
                    )
                    if correct_score_data:
                        result['correct_score_data'] = correct_score_data
                        logger.info(f"  比分数据: {len(correct_score_data.get('trade_records', []))}条")
                except Exception as e:
                    logger.warning(f"  比分采集失败: {e}")
            
            # ========== 5. 创建超级JSON ==========
            if progress_callback:
                progress_callback(90, '正在生成超级JSON...')
            
            # 构建match_info
            match_info = {
                'match_id': match_id,
                'date': match.get('date', ''),
                'home': match.get('home', ''),
                'away': match.get('away', ''),
                'league': match.get('league', ''),
                'kickoff': match.get('kickoff', ''),
                'score': match.get('score', ''),
                **urls  # 包含所有URL和盘口信息
            }
            
            super_json = create_super_json(
                match_info=match_info,
                standard_data=result['standard_data'],
                ou_data=result['ou_data'],
                handicap_data=result['handicap_data'],
                correct_score_data=result['correct_score_data'],
            )
            
            result['super_json'] = super_json
            result['success'] = True
            
            if progress_callback:
                progress_callback(100, '采集完成')
            
        except Exception as e:
            result['error'] = str(e)
            logger.exception(f"四合一采集失败: {e}")
        
        finally:
            if own_driver and driver:
                try:
                    driver.quit()
                except:
                    pass
        
        return result
    
    def _collect_standard_data(
        self, 
        driver: webdriver.Chrome, 
        url: str, 
        match_id: str
    ) -> Optional[Dict]:
        """采集标盘数据（含翻页）"""
        from parser.html_parser import parse_bifa_html
        
        driver.get(url)
        time.sleep(3)
        
        all_rows = []
        columns = []
        page = 1
        max_pages = 50
        
        while page <= max_pages:
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tr")) > 5
                )
                time.sleep(1)
            except:
                if page == 1:
                    logger.warning("标盘数据表格加载超时")
                break
            
            html = driver.page_source
            df = parse_bifa_html(html, {'match_id': match_id})
            
            if hasattr(df, 'to_dict') and len(df) > 0:
                if not columns:
                    columns = df.columns.tolist()
                page_rows = df.to_dict(orient="records")
                all_rows.extend(page_rows)
                logger.debug(f"  标盘第{page}页: {len(page_rows)}条")
            else:
                break
            
            # 翻页
            try:
                next_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                if next_link:
                    next_link.click()
                    time.sleep(2)
                    page += 1
                else:
                    break
            except:
                break
        
        if all_rows:
            return {
                "columns": columns,
                "data": all_rows,
                "total_records": len(all_rows)
            }
        return None
    
    def _collect_trade_data(
        self,
        driver: webdriver.Chrome,
        url: str,
        data_type: str,
        line_value: str = None
    ) -> Optional[Dict]:
        """采集交易数据（让球/大小球/比分，含翻页）"""
        from parser.super_detail_parser import (
            parse_handicap_trade_html,
            parse_correct_score_html
        )
        
        driver.get(url)
        time.sleep(3)
        
        all_records = []
        page = 1
        max_pages = 50
        
        while page <= max_pages:
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "#table_1 tr.item")) > 0
                )
                time.sleep(1)
            except:
                if page == 1:
                    logger.warning(f"{data_type}数据表格加载超时")
                break
            
            html = driver.page_source
            
            if data_type in ['handicap', 'ou']:
                page_data = parse_handicap_trade_html(html)
            else:
                page_data = parse_correct_score_html(html)
            
            records = page_data.get('trade_records', [])
            if not records:
                break
            
            all_records.extend(records)
            logger.debug(f"  {data_type}第{page}页: {len(records)}条")
            
            # 翻页
            try:
                next_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                if next_link:
                    next_link.click()
                    time.sleep(2)
                    page += 1
                else:
                    break
            except:
                break
        
        if all_records:
            result = {
                "trade_records": all_records,
                "summary": {
                    "total_records": len(all_records),
                    "first_time": all_records[-1].get("time") if all_records else None,
                    "last_time": all_records[0].get("time") if all_records else None,
                }
            }
            
            if data_type == 'ou':
                result['ou_line'] = line_value
            elif data_type == 'handicap':
                result['handicap_line'] = line_value
            
            return result
        return None
    
    def _create_driver(self) -> webdriver.Chrome:
        """创建WebDriver实例"""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=options)
        return driver
    
    def save_super_json(
        self,
        super_json: Dict,
        match: Dict,
        output_dir: Path = None
    ) -> Path:
        """保存超级JSON到文件"""
        if output_dir is None:
            kickoff = match.get('kickoff', '')
            if kickoff:
                try:
                    dt = datetime.strptime(kickoff, '%Y-%m-%d %H:%M')
                    output_dir = Path(__file__).parent.parent / "data" / dt.strftime('%Y/%m/%d')
                except:
                    output_dir = Path(__file__).parent.parent / "data" / "super_detail"
            else:
                output_dir = Path(__file__).parent.parent / "data" / "super_detail"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        kickoff = match.get('kickoff', '')
        league = match.get('league', '未知')
        home = match.get('home', '')
        away = match.get('away', '')
        
        if kickoff:
            try:
                dt = datetime.strptime(kickoff, '%Y-%m-%d %H:%M')
                date_str = dt.strftime('%Y%m%d')
                time_str = dt.strftime('%H%M')
            except:
                date_str = datetime.now().strftime('%Y%m%d')
                time_str = datetime.now().strftime('%H%M')
        else:
            date_str = datetime.now().strftime('%Y%m%d')
            time_str = datetime.now().strftime('%H%M')
        
        # 清理文件名
        safe_home = home.replace(' ', '_').replace('/', '_')
        safe_away = away.replace(' ', '_').replace('/', '_')
        safe_league = league.replace(' ', '_').replace('/', '_')
        
        filename = f"{date_str}_{time_str}_{safe_league}_{safe_home}_vs_{safe_away}.json"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(super_json, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 超级JSON已保存: {filepath}")
        return filepath


# 全局实例
_super_collector = None

def get_super_collector() -> SuperCollector:
    """获取全局SuperCollector实例"""
    global _super_collector
    if _super_collector is None:
        _super_collector = SuperCollector()
    return _super_collector
