#!/usr/bin/env python3
"""
快速采集今日比赛数据
适用于服务器端快速采集，无需复杂配置
"""
import sys
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from services.bifaw_client import BifawClient
from services.lottery500_client import Lottery500Client
from backtest.detail_cache_manager import DetailCacheManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def collect_today_matches(delay=3):
    """
    采集今日比赛数据
    
    Args:
        delay: 请求间隔（秒）
    """
    print("=" * 80)
    print("🚀 快速采集今日比赛数据")
    print("=" * 80)
    
    # 初始化客户端
    bifaw_client = BifawClient()
    lottery500_client = Lottery500Client()
    cache_manager = DetailCacheManager()
    
    # 获取今天日期
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    print(f"\n📅 采集日期: {today_str}")
    print(f"⏰ 当前时间: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1. 获取比赛列表
        print(f"\n{'='*80}")
        print("【1】获取比赛列表")
        print(f"{'='*80}")
        
        # 从必发网获取比赛列表
        print(f"正在从必发网获取比赛列表...")
        matches = bifaw_client.get_match_list(rows=100, days=1)
        
        if not matches:
            print("❌ 未获取到比赛列表")
            print("\n可能的原因：")
            print("1. 需要登录必发网")
            print("2. 网络连接问题")
            print("3. 今天没有比赛")
            return False
        
        print(f"✅ 获取到 {len(matches)} 场比赛")
        
        # 2. 批量获取盘口数据
        print(f"\n{'='*80}")
        print("【2】批量获取盘口数据")
        print(f"{'='*80}")
        
        try:
            daily_handicaps = lottery500_client.get_daily_handicaps_batch(today_str, use_cache=False)
            
            if daily_handicaps:
                print(f"✅ 获取到 {len(daily_handicaps)} 场比赛的盘口数据")
                
                # 保存盘口数据
                lottery500_client.save_daily_handicap_json(today_str, daily_handicaps)
                print(f"✅ 已保存盘口数据")
            else:
                print("⚠️  未获取到盘口数据（可能今天没有盘口）")
        except Exception as e:
            logger.error(f"获取盘口数据失败: {e}")
            print("⚠️  跳过盘口数据采集")
        
        # 3. 采集交易明细
        print(f"\n{'='*80}")
        print("【3】采集交易明细")
        print(f"{'='*80}")
        
        success_count = 0
        failed_count = 0
        
        for i, match in enumerate(matches, 1):
            try:
                league = match.get('league', '')
                home = match.get('home', match.get('home_team', ''))
                away = match.get('away', match.get('away_team', ''))
                match_time = match.get('datetime', match.get('match_time', ''))
                score = match.get('score', '')
                
                print(f"\n[{i}/{len(matches)}] {league} | {home} vs {away}")
                print(f"  时间: {match_time}")
                
                # 检查缓存
                match_info = {
                    'league': league,
                    'home': home,
                    'away': away,
                    'kickoff': match_time,
                    'match_time': match_time,
                    'datetime': match_time,
                    'score': score
                }
                
                if cache_manager.has_cache(match_info):
                    print(f"  ✅ 已有缓存，跳过")
                    success_count += 1
                    continue
                
                # 获取交易明细
                print(f"  🔄 正在获取交易明细...")
                
                trade_data = bifaw_client.get_trade_detail(
                    home_team=home,
                    away_team=away,
                    match_time=match_time,
                    league=league
                )
                
                if trade_data is not None and not trade_data.empty:
                    rows = len(trade_data)
                    print(f"  ✅ 获取成功 ({rows}行)")
                    
                    # 保存到缓存
                    html_content = getattr(trade_data, 'attrs', {}).get('html_content', '')
                    metadata = getattr(trade_data, 'attrs', {}).get('metadata', [])
                    
                    cache_manager.save_detail(
                        match_info=match_info,
                        trade_data=trade_data,
                        handicap_data={},
                        metadata=metadata,
                        html_content=html_content
                    )
                    
                    success_count += 1
                else:
                    print(f"  ⚠️  未获取到数据")
                    failed_count += 1
                
                # 延迟
                if i < len(matches):
                    time.sleep(delay)
                
            except Exception as e:
                logger.error(f"  ❌ 采集失败: {e}")
                failed_count += 1
                time.sleep(delay)
        
        # 4. 总结
        print(f"\n{'='*80}")
        print("📊 采集完成")
        print(f"{'='*80}")
        print(f"总计: {len(matches)} 场")
        print(f"成功: {success_count} 场")
        print(f"失败: {failed_count} 场")
        print(f"成功率: {success_count/len(matches)*100:.1f}%")
        
        return True
        
    except Exception as e:
        logger.exception(f"采集失败: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='快速采集今日比赛数据')
    parser.add_argument('--delay', type=int, default=3, help='请求间隔秒数（默认3秒）')
    
    args = parser.parse_args()
    
    success = collect_today_matches(delay=args.delay)
    
    if success:
        print("\n✅ 采集完成！现在可以运行 auto_recommend_push.py")
    else:
        print("\n❌ 采集失败，请检查网络和登录状态")
    
    sys.exit(0 if success else 1)
