#!/usr/bin/env python3
"""
从本地文件批量回测

前置条件：
1. 已运行 batch_collect_details.py 采集并保存了交易明细
2. 比赛已完场，可获取实际比分

工作流程：
1. 读取 collected_details/ 目录中的JSON文件
2. 从500彩票网查询实际比分
3. 调用推荐引擎生成推荐
4. 验证推荐结果并计算统计数据
5. 生成回测报告
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import Lottery500Client
from recommendation import HandicapRecommendationEngineX1, VISFormatter
from backtest.result_validator import ResultValidator
from backtest.report_formatter import format_batch_backtest_report

logger = logging.getLogger(__name__)


class LocalBacktester:
    """本地文件回测器"""
    
    def __init__(self, details_dir: Path):
        self.details_dir = details_dir
        self.lottery500_client = Lottery500Client()
        self.engine = HandicapRecommendationEngineX1()
        self.validator = ResultValidator()
        self.vis_formatter = VISFormatter()
        
        # 统计
        self.total = 0
        self.success = 0
        self.failed = 0
        self.results = []
    
    def backtest_all(self):
        """回测所有本地文件"""
        # 查找所有JSON文件
        json_files = list(self.details_dir.glob("*.json"))
        
        if not json_files:
            logger.error(f"未找到JSON文件: {self.details_dir}")
            return
        
        logger.info(f"找到 {len(json_files)} 个明细文件")
        self.total = len(json_files)
        
        # 逐个回测
        for idx, filepath in enumerate(json_files, 1):
            try:
                logger.info(f"\n[{idx}/{len(json_files)}] {filepath.name}")
                result = self._backtest_single_file(filepath)
                self.results.append(result)
                
                if result['success']:
                    self.success += 1
                else:
                    self.failed += 1
                    
            except Exception as e:
                logger.exception(f"回测失败: {e}")
                self.failed += 1
                self.results.append({
                    'success': False,
                    'error': str(e),
                    'file': filepath.name
                })
        
        # 生成报告
        self._generate_report()
    
    def _backtest_single_file(self, filepath: Path) -> Dict:
        """回测单个文件"""
        # 1. 读取本地文件
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        match_info = data.get('match_info', {})
        logger.info(f"  比赛: {match_info.get('label')}")
        
        # 2. 重建DataFrame
        trade_data_dict = data.get('trade_data', {})
        trade_df = pd.DataFrame(trade_data_dict.get('data', []))
        trade_df.attrs['metadata'] = data.get('metadata', [])
        
        if trade_df.empty:
            return {
                'success': False,
                'error': '交易数据为空',
                'match_info': match_info,
                'file': filepath.name
            }
        
        logger.info(f"  交易数据: {len(trade_df)} 行")
        
        # 3. 获取盘口数据
        handicap_data = data.get('handicap_data')
        
        if not handicap_data or not handicap_data.get('current_handicap'):
            logger.warning("  缺少盘口数据")
            return {
                'success': False,
                'error': '盘口数据缺失',
                'match_info': match_info,
                'file': filepath.name
            }
        
        logger.info(f"  盘口: {handicap_data.get('current_handicap_str')} ({handicap_data.get('current_handicap')})")
        
        # 4. 查询实际比分
        actual_score = self._fetch_actual_score(match_info)
        
        if not actual_score:
            logger.warning("  ⚠️  未查询到比分，可能比赛未结束")
            return {
                'success': False,
                'error': '比赛未完场或无比分',
                'match_info': match_info,
                'file': filepath.name
            }
        
        logger.info(f"  实际比分: {actual_score[0]}-{actual_score[1]}")
        
        # 5. 生成推荐
        logger.info("  生成推荐...")
        recommendation = self.engine.generate_recommendation(
            trade_data=trade_df,
            metadata=trade_df.attrs.get('metadata', []),
            handicap_data=handicap_data
        )
        
        # 6. 验证推荐
        logger.info("  验证推荐...")
        validation = self.validator.validate_recommendation(
            recommendation=recommendation,
            actual_score=actual_score,
            actual_handicap=handicap_data.get('current_handicap')
        )
        
        # 7. 输出结果
        if validation.get('validated'):
            result_type = validation.get('result', '')
            profit = validation.get('profit', 0)
            
            if validation.get('recommended'):
                logger.info(f"  ✅ 结果: {result_type}, 盈亏: {profit:+.2f}")
            else:
                logger.info(f"  ➖ 未推荐")
        
        return {
            'success': True,
            'match_info': match_info,
            'actual_score': actual_score,
            'recommendation': recommendation,
            'validation': validation,
            'file': filepath.name
        }
    
    def _fetch_actual_score(self, match_info: dict) -> Optional[Tuple[int, int]]:
        """查询实际比分"""
        try:
            home = match_info.get('home', '')
            away = match_info.get('away', '')
            kickoff = match_info.get('kickoff', '')
            
            if not all([home, away, kickoff]):
                return None
            
            # 使用500彩票网查询比分
            result = self.lottery500_client.get_match_result(home, away, kickoff)
            
            if result and result.get('score'):
                score_str = result['score']
                # 解析 "2-1" 格式
                parts = score_str.replace(':', '-').split('-')
                if len(parts) == 2:
                    return (int(parts[0].strip()), int(parts[1].strip()))
            
            return None
            
        except Exception as e:
            logger.error(f"  查询比分失败: {e}")
            return None
    
    def _generate_report(self):
        """生成回测报告"""
        logger.info(f"\n{'='*60}")
        logger.info("回测完成，生成报告...")
        logger.info(f"{'='*60}")
        
        # 统计
        statistics = self.validator.calculate_statistics(
            [r.get('validation', {}) for r in self.results if r.get('success')]
        )
        
        batch_result = {
            'total': self.total,
            'success': self.success,
            'failed': self.failed,
            'statistics': statistics,
            'results': self.results
        }
        
        # 格式化报告
        report = format_batch_backtest_report(batch_result)
        print(report)
        
        # 保存报告
        report_file = Path(__file__).parent.parent / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report, encoding='utf-8')
        logger.info(f"\n报告已保存: {report_file}")
        
        # 保存详细结果
        result_file = Path(__file__).parent.parent / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(batch_result, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"详细结果已保存: {result_file}")


def main():
    parser = argparse.ArgumentParser(
        description="从本地采集的明细文件批量回测"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent / "collected_details",
        help="明细文件目录（默认: collected_details/）"
    )
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('batch_backtest.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 执行回测
    if not args.input.exists():
        logger.error(f"目录不存在: {args.input}")
        logger.info("请先运行 batch_collect_details.py 采集明细")
        return
    
    backtester = LocalBacktester(details_dir=args.input)
    backtester.backtest_all()


if __name__ == "__main__":
    main()
