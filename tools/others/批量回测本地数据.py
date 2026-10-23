"""
批量回测本地数据脚本
直接扫描data目录下的所有JSON文件，进行批量回测
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import sys
import pandas as pd

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'backtest_result_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 导入必要的模块
from backtest import BacktestEngine
from backtest.detail_cache_manager import DetailCacheManager
from recommendation.handicap_engine_x1 import HandicapRecommendationEngineX1
from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient

# 🔥 使用X1 JSON V4 Ultra超高准确率引擎（目标70%）
from recommendation.x1_json_recommender_v4_ultra import X1JSONRecommenderV4Ultra
USE_V4_ULTRA_ENGINE = True
logger.info("✅ 已加载X1 JSON V4 Ultra超高准确率引擎（目标70%）")


def scan_local_data(data_dir: str = "data") -> List[Dict]:
    """
    扫描本地data目录，收集所有已采集的比赛数据
    
    Returns:
        比赛列表
    """
    base_dir = Path(data_dir)
    matches = []
    
    logger.info(f"📂 开始扫描目录: {base_dir.absolute()}")
    
    # 遍历所有年份/月份/日期目录
    for year_dir in sorted(base_dir.glob("*")):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
            
        for month_dir in sorted(year_dir.glob("*")):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
                
            for day_dir in sorted(month_dir.glob("*")):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue
                
                # 扫描该日期下的所有JSON文件
                for json_file in day_dir.glob("*.json"):
                    # 跳过特殊文件
                    if json_file.name in ['完场回查.json', '盘口数据.json']:
                        continue
                    
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        match_info = data.get('match_info', {})
                        
                        # 必须有比分才能回测
                        score = match_info.get('score', '')
                        if not score or '-' not in score:
                            continue
                        
                        # 解析比分
                        try:
                            home_score, away_score = map(int, score.split('-'))
                        except:
                            logger.warning(f"  ⚠️  跳过（比分格式错误）: {json_file.name}")
                            continue
                        
                        # 构造回测所需的数据结构
                        match = {
                            'match_info': {
                                'home': match_info.get('home', match_info.get('home_team', '')),
                                'away': match_info.get('away', match_info.get('away_team', '')),
                                'league': match_info.get('league', ''),
                                'kickoff': match_info.get('kickoff', match_info.get('match_time', '')),
                                'label': match_info.get('label', ''),
                            },
                            'detail_url': match_info.get('detail_url', ''),
                            'actual_score': (home_score, away_score),
                            'score_for_cache': score,
                            'detail_params': match_info.get('detail_params'),
                            'file_path': str(json_file)
                        }
                        
                        matches.append(match)
                        
                    except Exception as e:
                        logger.warning(f"  ⚠️  读取文件失败: {json_file.name} - {e}")
                        continue
    
    logger.info(f"✅ 扫描完成，找到 {len(matches)} 场有效比赛数据")
    return matches


def print_statistics(results: List[Dict]):
    """打印回测统计结果"""
    
    total = len(results)
    success = sum(1 for r in results if r.get('success'))
    failed = total - success
    
    # 统计推荐情况
    recommended_count = 0
    win_count = 0
    half_win_count = 0
    half_lose_count = 0
    lose_count = 0
    total_profit = 0.0
    
    for result in results:
        if not result.get('success'):
            continue
            
        validation = result.get('validation', {})
        if validation.get('recommended'):
            recommended_count += 1
            result_type = validation.get('result', '')
            profit = validation.get('profit', 0.0)
            total_profit += profit
            
            # 根据result类型统计
            if result_type == 'WIN':
                win_count += 1
            elif result_type == 'HALF_WIN':
                half_win_count += 1
            elif result_type == 'HALF_LOSE':
                half_lose_count += 1
            elif result_type == 'LOSE':
                lose_count += 1
    
    # 盈利场次（全赢+半赢）
    profit_count = win_count + half_win_count
    # 亏损场次（全输+半输）
    loss_count = lose_count + half_lose_count
    # 盈利率
    profit_rate = (profit_count / recommended_count * 100) if recommended_count > 0 else 0
    
    print("\n" + "="*80)
    print("📊 回测统计结果")
    print("="*80)
    print(f"总比赛数: {total}")
    print(f"成功回测: {success}")
    print(f"失败回测: {failed}")
    print(f"\n推荐情况:")
    print(f"  发出推荐: {recommended_count} 场")
    print(f"  📈 盈利场次: {profit_count} 场 ({profit_rate:.2f}%)")
    print(f"     全赢: {win_count} 场")
    print(f"     半赢: {half_win_count} 场")
    print(f"  📉 亏损场次: {loss_count} 场")
    print(f"     全输: {lose_count} 场")
    print(f"     半输: {half_lose_count} 场")
    print(f"  💰 总盈亏: {total_profit:+.2f} 单位")
    print(f"  ⏸️  不推荐: {success - recommended_count} 场")
    print("="*80)
    
    # 分析推荐方向
    direction_stats = {}
    
    for result in results:
        if not result.get('success'):
            continue
            
        validation = result.get('validation', {})
        if not validation.get('recommended'):
            continue
            
        recommendation = result.get('recommendation', {})
        direction = recommendation.get('最终推荐', {}).get('direction', '未知')
        
        if direction not in direction_stats:
            direction_stats[direction] = {'total': 0, 'profit': 0, 'win': 0, 'lose': 0}
        
        direction_stats[direction]['total'] += 1
        profit = validation.get('profit', 0.0)
        direction_stats[direction]['profit'] += profit
        
        if profit > 0:
            direction_stats[direction]['win'] += 1
        elif profit < 0:
            direction_stats[direction]['lose'] += 1
    
    print("\n推荐方向统计:")
    for direction, stats in sorted(direction_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        if stats['total'] > 0:
            win_rate = stats['win'] / stats['total'] * 100
            avg_profit = stats['profit'] / stats['total']
            print(f"  {direction}: {stats['win']}/{stats['total']} 盈利 ({win_rate:.1f}%), 平均: {avg_profit:+.2f}")
    
    # 保存详细结果到文件
    result_file = f"backtest_详细结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'total': total,
                'success': success,
                'failed': failed,
                'recommended': recommended_count,
                'profit_count': profit_count,
                'loss_count': loss_count,
                'win': win_count,
                'half_win': half_win_count,
                'lose': lose_count,
                'half_lose': half_lose_count,
                'profit_rate': profit_rate,
                'total_profit': total_profit
            },
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细结果已保存至: {result_file}")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("🚀 批量回测本地数据")
    print("="*80 + "\n")
    
    # 1. 扫描本地数据
    matches = scan_local_data()
    
    if not matches:
        logger.error("❌ 未找到任何有效的比赛数据！")
        return
    
    # 2. 初始化回测引擎
    logger.info("\n📦 初始化回测引擎...")
    
    try:
        # 初始化必要的客户端
        lottery500_client = Lottery500Client()
        bifaw_client = BifawClient()
        detail_cache_manager = DetailCacheManager(cache_dir='data')
        
        # 🔥 使用X1 JSON V4 Ultra超高准确率引擎（目标70%）
        engine = X1JSONRecommenderV4Ultra()
        logger.info("✅ 使用X1 JSON V4 Ultra超高准确率引擎（目标70%）")
        
        backtest_engine = BacktestEngine(
            engine,
            lottery500_client,
            bifaw_client,
            detail_cache_manager
        )
        
        logger.info("✅ 回测引擎初始化成功")
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 执行批量回测
    logger.info(f"\n🔄 开始批量回测 {len(matches)} 场比赛...")
    logger.info("="*80 + "\n")
    
    try:
        result = backtest_engine.batch_backtest(matches)
        
        # 4. 打印统计结果
        print_statistics(result.get('results', []))
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断回测")
    except Exception as e:
        logger.error(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
