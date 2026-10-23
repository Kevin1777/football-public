#!/usr/bin/env python3
"""
批量采集交易明细并存储到本地

工作流程：
1. 从必发网获取比赛列表（支持完场回查）
2. 逐场抓取交易明细（UG-PDF）
3. 同时获取让球盘口数据
4. 保存为JSON文件到本地目录
5. 等比赛结束后，用 batch_backtest_from_local.py 进行回测

注意：
- days参数：0=仅今天, 1=今天+昨天, 2=今天+昨天+前天
- 完场比赛的明细可能已被清空（必发网限制）
- 建议在比赛进行中采集，或采集当天比赛
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import BifawClient, Lottery500Client
from parser.html_parser import parse_bifa_html

logger = logging.getLogger(__name__)


class DetailCollector:
    """交易明细批量采集器"""
    
    def __init__(self, output_dir: Path):
        self.bifaw_client = BifawClient()
        self.lottery500_client = Lottery500Client()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计
        self.collected = 0
        self.failed = 0
    
    def collect_matches(self, rows: int = 50, days: int = 1, delay: int = 3):
        """
        批量采集比赛明细
        
        Args:
            rows: 获取比赛数量
            days: 往前推N天（0=仅今天, 1=今天+昨天, 以此类推）
            delay: 请求间隔（秒）
        """
        logger.info(f"开始采集往前{days}天（含今天）的{rows}场比赛明细...")
        
        # 1. 获取比赛列表
        matches = self.bifaw_client.fetch_match_list_v2(rows=rows, days=days)
        
        if not matches:
            logger.error("未获取到比赛列表")
            return
        
        logger.info(f"找到 {len(matches)} 场比赛")
        
        # 2. 逐场采集
        for idx, match in enumerate(matches, 1):
            try:
                logger.info(f"\n[{idx}/{len(matches)}] {match.get('label')}")
                self._collect_single_match(match)
                
                # 请求间隔
                if idx < len(matches):
                    time.sleep(delay)
                    
            except KeyboardInterrupt:
                logger.warning("\n用户中断")
                break
            except Exception as e:
                logger.exception(f"采集失败: {e}")
                self.failed += 1
        
        # 3. 汇总
        logger.info(f"\n{'='*60}")
        logger.info(f"采集完成: 成功 {self.collected}, 失败 {self.failed}")
        logger.info(f"存储目录: {self.output_dir}")
        logger.info(f"{'='*60}")
    
    def _collect_single_match(self, match: dict):
        """采集单场比赛"""
        match_id = match.get('match_id') or self._generate_match_id(match)
        detail_url = match.get('detail_url')
        
        if not detail_url:
            logger.warning("缺少明细URL，跳过")
            self.failed += 1
            return
        
        # 1. 抓取交易明细
        logger.info(f"  抓取交易明细: {detail_url}")
        detail_html = self.bifaw_client.fetch_match_detail_selenium(
            detail_url=detail_url,
            match=match
        )
        
        if not detail_html:
            logger.error("  ❌ 明细页面为空")
            self.failed += 1
            return
        
        # 2. 解析明细
        logger.info("  解析交易明细...")
        parsed_data = parse_bifa_html(detail_html, match=match)
        
        if isinstance(parsed_data, str):  # 错误信息
            logger.error(f"  ❌ 解析失败: {parsed_data}")
            self.failed += 1
            return
        
        if parsed_data.empty:
            logger.error("  ❌ 解析结果为空")
            self.failed += 1
            return
        
        logger.info(f"  ✅ 解析成功: {len(parsed_data)} 行")
        
        # 3. 获取让球盘口
        logger.info("  获取让球盘口...")
        handicap_data = self._fetch_handicap(match)
        
        # 4. 保存到本地
        self._save_to_file(match_id, match, parsed_data, handicap_data)
        self.collected += 1
    
    def _fetch_handicap(self, match: dict) -> dict:
        """获取让球盘口数据"""
        try:
            home = match.get('home', '')
            away = match.get('away', '')
            kickoff = match.get('kickoff', '')
            
            if not all([home, away, kickoff]):
                logger.warning("  缺少盘口查询信息")
                return {}
            
            handicap = self.lottery500_client.get_handicap(home, away, kickoff)
            
            if handicap:
                logger.info(f"  ✅ 盘口: {handicap.get('current_handicap_str')} ({handicap.get('current_handicap')})")
            else:
                logger.warning("  ⚠️  未找到盘口数据")
            
            return handicap or {}
            
        except Exception as e:
            logger.error(f"  ❌ 盘口获取失败: {e}")
            return {}
    
    def _save_to_file(self, match_id: str, match: dict, trade_df, handicap_data: dict):
        """保存到JSON文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 文件名：日期_比赛ID.json
        kickoff_date = match.get('kickoff', '').split()[0].replace('-', '')
        filename = f"{kickoff_date}_{match_id}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # 构造数据
        metadata = trade_df.attrs.get("metadata", [])
        
        data = {
            "match_id": match_id,
            "match_info": match,
            "handicap_data": handicap_data,
            "trade_data": {
                "columns": trade_df.columns.tolist(),
                "data": trade_df.to_dict(orient='records'),
                "shape": trade_df.shape,
            },
            "metadata": metadata,
            "collected_at": datetime.now().isoformat(),
        }
        
        # 保存
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"  💾 已保存: {filepath.name}")
    
    def _generate_match_id(self, match: dict) -> str:
        """生成匹配ID"""
        home = match.get('home', 'H').replace(' ', '')[:10]
        away = match.get('away', 'A').replace(' ', '')[:10]
        kickoff = match.get('kickoff', '').replace(' ', '_').replace(':', '')
        return f"{home}_vs_{away}_{kickoff}"


def main():
    parser = argparse.ArgumentParser(
        description="批量采集交易明细并存储到本地，供后续回测使用"
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
        "--delay",
        type=int,
        default=3,
        help="请求间隔秒数（默认3秒）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "collected_details",
        help="输出目录（默认: collected_details/）"
    )
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('batch_collect.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 执行采集
    collector = DetailCollector(output_dir=args.output)
    collector.collect_matches(rows=args.rows, days=args.days, delay=args.delay)


if __name__ == "__main__":
    main()
