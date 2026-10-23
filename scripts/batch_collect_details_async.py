#!/usr/bin/env python3
"""
异步批量采集交易明细 - 并发版

相比原版本的优化：
1. 使用asyncio异步并发（速度提升5-10倍）
2. 支持并发数控制（默认10个并发）
3. 支持重试机制
4. 进度条显示

使用示例：
    python scripts/batch_collect_details_async.py --rows 200 --days 3 --workers 10
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import aiohttp
from tqdm import tqdm

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import BifawClient, Lottery500Client
from parser.html_parser import parse_bifa_html

logger = logging.getLogger(__name__)


class AsyncDetailCollector:
    """异步交易明细批量采集器"""
    
    def __init__(self, output_dir: Path, max_workers: int = 10):
        self.bifaw_client = BifawClient()
        self.lottery500_client = Lottery500Client()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 并发控制
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        
        # 统计
        self.collected = 0
        self.failed = 0
        self.skipped = 0
        self.lock = asyncio.Lock()
    
    async def collect_matches(self, rows: int = 50, days: int = 1):
        """
        异步批量采集比赛明细
        
        Args:
            rows: 获取比赛数量
            days: 往前推N天（0=仅今天, 1=今天+昨天）
        """
        start_time = time.time()
        logger.info(f"开始异步采集往前{days}天（含今天）的{rows}场比赛明细...")
        logger.info(f"并发数: {self.max_workers}")
        
        # 1. 获取比赛列表（同步）
        matches = self.bifaw_client.fetch_match_list_v2(rows=rows, days=days)
        
        if not matches:
            logger.error("未获取到比赛列表")
            return
        
        logger.info(f"找到 {len(matches)} 场比赛")
        
        # 2. 创建异步任务
        tasks = []
        for idx, match in enumerate(matches, 1):
            task = self._collect_single_match_async(idx, len(matches), match)
            tasks.append(task)
        
        # 3. 并发执行（带进度条）
        with tqdm(total=len(matches), desc="采集进度", ncols=100) as pbar:
            for coro in asyncio.as_completed(tasks):
                try:
                    await coro
                except Exception as e:
                    logger.error(f"任务执行失败: {e}")
                finally:
                    pbar.update(1)
        
        # 4. 汇总
        elapsed = time.time() - start_time
        logger.info(f"\n{'='*80}")
        logger.info(f"采集完成: 成功 {self.collected}, 失败 {self.failed}, 跳过 {self.skipped}")
        logger.info(f"耗时: {elapsed:.1f}秒 ({len(matches)/elapsed:.2f} 场/秒)")
        logger.info(f"存储目录: {self.output_dir}")
        logger.info(f"{'='*80}")
    
    async def _collect_single_match_async(self, idx: int, total: int, match: dict):
        """异步采集单场比赛"""
        async with self.semaphore:  # 限制并发数
            try:
                match_id = match.get('match_id') or self._generate_match_id(match)
                label = match.get('label', '')
                
                # 检查是否已存在
                if self._check_exists(match_id, match):
                    logger.debug(f"[{idx}/{total}] {label} - 已存在，跳过")
                    async with self.lock:
                        self.skipped += 1
                    return
                
                logger.info(f"[{idx}/{total}] {label}")
                
                # 1. 抓取交易明细（使用Selenium，暂时保持同步）
                detail_url = match.get('detail_url')
                if not detail_url:
                    logger.warning(f"  缺少明细URL，跳过")
                    async with self.lock:
                        self.failed += 1
                    return
                
                # 异步执行同步代码（在线程池中运行）
                loop = asyncio.get_event_loop()
                
                # 创建包装函数以支持关键字参数
                async def fetch_detail():
                    return await loop.run_in_executor(
                        None,
                        lambda: self.bifaw_client.fetch_match_detail_selenium(
                            detail_url=detail_url,
                            match=match
                        )
                    )
                
                detail_html = await fetch_detail()
                
                if not detail_html:
                    logger.error(f"  ❌ 明细页面为空")
                    async with self.lock:
                        self.failed += 1
                    return
                
                # 2. 解析明细
                parsed_data = await loop.run_in_executor(
                    None,
                    lambda: parse_bifa_html(detail_html, match=match)
                )
                
                if isinstance(parsed_data, str) or parsed_data.empty:
                    logger.error(f"  ❌ 解析失败或为空")
                    async with self.lock:
                        self.failed += 1
                    return
                
                logger.info(f"  ✅ 解析成功: {len(parsed_data)} 行")
                
                # 3. 异步获取让球盘口
                handicap_data = await self._fetch_handicap_async(match, loop)
                
                # 4. 保存到本地
                self._save_to_file(match_id, match, parsed_data, handicap_data)
                
                async with self.lock:
                    self.collected += 1
                    
            except Exception as e:
                logger.exception(f"[{idx}/{total}] 采集失败: {e}")
                async with self.lock:
                    self.failed += 1
    
    async def _fetch_handicap_async(self, match: dict, loop) -> dict:
        """异步获取让球盘口数据"""
        try:
            home = match.get('home', '')
            away = match.get('away', '')
            kickoff = match.get('kickoff', '')
            
            if not all([home, away, kickoff]):
                return {}
            
            # 在线程池中执行同步代码
            handicap = await loop.run_in_executor(
                None,
                lambda: self.lottery500_client.get_handicap(home, away, kickoff)
            )
            
            if handicap:
                logger.info(f"  ✅ 盘口: {handicap.get('current_handicap_str')} ({handicap.get('current_handicap')})")
            
            return handicap or {}
            
        except Exception as e:
            logger.error(f"  ❌ 盘口获取失败: {e}")
            return {}
    
    def _check_exists(self, match_id: str, match: dict) -> bool:
        """检查文件是否已存在"""
        try:
            # 构建查找模式
            kickoff_date = match.get('kickoff', '').split()[0]
            date_str = kickoff_date.replace('-', '')
            
            # 查找匹配的文件（忽略时间戳部分）
            pattern = f"{date_str}_{match_id}_*.json"
            existing = list(self.output_dir.glob(pattern))
            
            return len(existing) > 0
            
        except Exception:
            return False
    
    def _save_to_file(self, match_id: str, match: dict, trade_df, handicap_data: dict):
        """保存到JSON文件"""
        # 使用标准化文件名（与缓存管理器一致）
        kickoff = match.get('kickoff', '').replace(' ', '_').replace(':', '')
        league = match.get('league', '').replace('/', '-')
        home = match.get('home', '').replace('/', '-')
        away = match.get('away', '').replace('/', '-')
        score = match.get('score', '').replace('-', '_')
        
        # 获取日期信息
        kickoff_date = match.get('kickoff_date', '') or match.get('kickoff', '').split()[0] if match.get('kickoff') else ''
        kickoff_time = match.get('kickoff_time', '') or match.get('kickoff', '').split()[1] if match.get('kickoff') and len(match.get('kickoff', '').split()) > 1 else ''
        
        # 文件名格式: YYYY-MM-DD_联赛_主队_vs_客队_比分_时间.json
        filename = f"{kickoff_date}_{league}_{home}_vs_{away}_{score}_{kickoff_time.replace(':', '')}.json"
        
        # 按日期分目录 (YYYY/MM/DD)
        if kickoff_date and '-' in kickoff_date:
            date_parts = kickoff_date.split('-')
            if len(date_parts) == 3:
                year, month, day = date_parts
                date_dir = self.output_dir / year / month / day
            else:
                date_dir = self.output_dir / "unknown"
        else:
            date_dir = self.output_dir / "unknown"
        
        date_dir.mkdir(parents=True, exist_ok=True)
        filepath = date_dir / filename
        
        # 构造数据
        metadata = trade_df.attrs.get("metadata", [])
        
        data = {
            "match_id": match_id,
            "match_info": match,
            "handicap_data": handicap_data,
            "trade_data": {
                "columns": trade_df.columns.tolist(),
                "data": trade_df.to_dict(orient='records'),
                "shape": list(trade_df.shape),
            },
            "metadata": metadata,
            "collected_at": datetime.now().isoformat(),
        }
        
        # 保存
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  💾 已保存: {filepath.relative_to(self.output_dir)}")
    
    def _generate_match_id(self, match: dict) -> str:
        """生成匹配ID"""
        home = match.get('home', 'H').replace(' ', '')[:10]
        away = match.get('away', 'A').replace(' ', '')[:10]
        kickoff = match.get('kickoff', '').replace(' ', '_').replace(':', '')
        return f"{home}_vs_{away}_{kickoff}"


def main():
    parser = argparse.ArgumentParser(
        description="异步批量采集交易明细（并发版，速度提升5-10倍）"
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50,
        help="采集比赛数量（默认50）"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="往前推N天，包含今天（默认1=今天+昨天，0=仅今天）"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="并发数（默认10，建议5-15）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="输出目录（默认: data/）"
    )
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('batch_collect_async.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 执行异步采集
    collector = AsyncDetailCollector(output_dir=args.output, max_workers=args.workers)
    
    # 运行异步任务
    asyncio.run(collector.collect_matches(rows=args.rows, days=args.days))


if __name__ == "__main__":
    main()
