"""
异步批量采集服务
用于加速Web界面的完场回查功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class AsyncBatchCollector:
    """异步批量采集器 - 用于Web界面加速"""
    
    def __init__(self, bifaw_client, lottery500_client, detail_cache_manager):
        self.bifaw_client = bifaw_client
        self.lottery500_client = lottery500_client
        self.detail_cache_manager = detail_cache_manager
        
    async def collect_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        rows: int = 200,
        workers: int = 8,
        filter_by_handicap: bool = True,
        skip_cached: bool = True
    ) -> Dict:
        """
        异步采集日期区间的比赛数据
        
        Args:
            start_date: 起始日期
            end_date: 结束日期
            rows: 每天最大比赛数
            workers: 并发数
            filter_by_handicap: 是否过滤有盘口的比赛
            skip_cached: 是否跳过已缓存的数据
        
        Returns:
            采集结果统计
        """
        total_days = (end_date - start_date).days + 1
        
        results = {
            'total_days': total_days,
            'total_matches': 0,
            'collected': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        # 控制并发数
        semaphore = asyncio.Semaphore(workers)
        
        async def collect_single_day(target_date: datetime):
            """采集单天数据"""
            async with semaphore:
                date_str = target_date.strftime("%Y-%m-%d")
                day_result = {
                    'date': date_str,
                    'matches': 0,
                    'collected': 0,
                    'failed': 0,
                    'skipped': 0,
                    'status': 'pending'
                }
                
                try:
                    # 获取比赛列表（同步调用，在线程池中执行）
                    loop = asyncio.get_event_loop()
                    page_html, matches, metadata = await loop.run_in_executor(
                        None,
                        lambda: self.bifaw_client.fetch_finished_matches(
                            target_date=target_date,
                            rows=rows
                        )
                    )
                    
                    if not matches:
                        day_result['status'] = 'no_data'
                        day_result['skipped'] = 1
                        results['skipped'] += 1
                        return day_result
                    
                    day_result['matches'] = len(matches)
                    results['total_matches'] += len(matches)
                    
                    # 如果需要过滤盘口，先获取盘口列表
                    if filter_by_handicap:
                        daily_handicaps = await loop.run_in_executor(
                            None,
                            lambda: self.lottery500_client.fetch_daily_handicaps(
                                date_str,
                                use_cache=False
                            )
                        )
                        
                        # 过滤有盘口的比赛
                        matches = self._filter_matches_with_handicap(matches, daily_handicaps)
                        day_result['matches'] = len(matches)
                    
                    # 并发采集每场比赛的明细
                    match_tasks = []
                    for match in matches:
                        task = self._collect_single_match(match, skip_cached, day_result)
                        match_tasks.append(task)
                    
                    # 等待所有比赛采集完成
                    await asyncio.gather(*match_tasks, return_exceptions=True)
                    
                    # 更新全局统计
                    results['collected'] += day_result['collected']
                    results['failed'] += day_result['failed']
                    results['skipped'] += day_result['skipped']
                    
                    day_result['status'] = 'completed'
                    
                except Exception as e:
                    logger.error(f"采集日期 {date_str} 失败: {e}")
                    day_result['status'] = 'failed'
                    day_result['error'] = str(e)
                    results['failed'] += 1
                
                return day_result
        
        # 创建所有日期的采集任务
        tasks = []
        current_date = start_date
        while current_date <= end_date:
            tasks.append(collect_single_day(current_date))
            current_date += timedelta(days=1)
        
        # 并发执行所有日期
        day_results = await asyncio.gather(*tasks)
        results['details'] = day_results
        
        return results
    
    async def _collect_single_match(
        self,
        match: Dict,
        skip_cached: bool,
        day_result: Dict
    ):
        """采集单场比赛的明细"""
        try:
            # 检查缓存
            if skip_cached:
                cached_data = self.detail_cache_manager.load_detail(match)
                if cached_data:
                    day_result['skipped'] += 1
                    return
            
            detail_url = match.get('detail_url')
            if not detail_url:
                day_result['skipped'] += 1
                return
            
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            
            # 抓取明细
            detail_html = await loop.run_in_executor(
                None,
                lambda: self.bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match
                )
            )
            
            if not detail_html:
                day_result['failed'] += 1
                return
            
            # 解析明细
            from parser.html_parser import parse_bifa_html
            parsed_data = await loop.run_in_executor(
                None,
                lambda: parse_bifa_html(detail_html, match=match)
            )
            
            if isinstance(parsed_data, str) or (hasattr(parsed_data, 'empty') and parsed_data.empty):
                day_result['failed'] += 1
                return
            
            # 获取盘口
            handicap_data = await loop.run_in_executor(
                None,
                lambda: self.lottery500_client.get_handicap(
                    match.get('home', ''),
                    match.get('away', ''),
                    match.get('kickoff', '')
                )
            )
            
            # 保存到缓存
            metadata = parsed_data.attrs.get("metadata", [])
            self.detail_cache_manager.save_detail(
                match_info=match,
                trade_data=parsed_data,
                handicap_data=handicap_data or {},
                metadata=metadata
            )
            
            day_result['collected'] += 1
            
        except Exception as e:
            logger.error(f"采集比赛失败: {match.get('label', 'unknown')} - {e}")
            day_result['failed'] += 1
    
    def _filter_matches_with_handicap(
        self,
        matches: List[Dict],
        daily_handicaps: List[Dict]
    ) -> List[Dict]:
        """过滤出有盘口的比赛"""
        if not daily_handicaps:
            return []
        
        # 构建盘口查找索引
        handicap_map = {}
        for h in daily_handicaps:
            home = self.lottery500_client._clean_team_name(h.get('home', ''))
            away = self.lottery500_client._clean_team_name(h.get('away', ''))
            time_str = h.get('time', '')[:5]
            
            key = f"{home}_{away}_{time_str}"
            handicap_map[key] = h
        
        # 过滤比赛
        filtered = []
        for match in matches:
            home = self.lottery500_client._clean_team_name(match.get('home', ''))
            away = self.lottery500_client._clean_team_name(match.get('away', ''))
            time = match.get('kickoff', '')
            time_str = time.split(' ')[1][:5] if ' ' in time else time[:5]
            
            key = f"{home}_{away}_{time_str}"
            if key in handicap_map:
                match['handicap_info'] = handicap_map[key]
                filtered.append(match)
        
        return filtered


async def run_async_collection(
    bifaw_client,
    lottery500_client,
    detail_cache_manager,
    start_date: datetime,
    end_date: datetime = None,
    **kwargs
) -> Dict:
    """
    运行异步采集任务的便捷函数
    
    可以在Flask路由中直接调用：
    
    ```python
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(
        run_async_collection(
            bifaw_client,
            lottery500_client,
            detail_cache_manager,
            start_date,
            workers=10
        )
    )
    loop.close()
    ```
    """
    if end_date is None:
        end_date = datetime.now()
    
    collector = AsyncBatchCollector(
        bifaw_client,
        lottery500_client,
        detail_cache_manager
    )
    
    return await collector.collect_date_range(
        start_date=start_date,
        end_date=end_date,
        **kwargs
    )
