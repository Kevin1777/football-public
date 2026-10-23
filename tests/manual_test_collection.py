import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录 to path
sys.path.append(str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager
from parser.html_parser import parse_bifa_html

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_collection_fix():
    logger.info("🚀 开始验证后台采集修复逻辑...")
    
    # 1. 初始化客户端
    bifaw_client = BifawClient()
    detail_cache_manager = DetailCacheManager(cache_dir="data")
    
    # 2. 获取比赛列表 (使用昨天的数据 2025-11-29)
    target_date = datetime(2025, 11, 29)
    logger.info(f"正在获取 {target_date.strftime('%Y-%m-%d')} 的比赛...")
    
    _, matches, _ = bifaw_client.fetch_finished_matches(target_date=target_date, rows=5) # 只取5场测试
    
    if not matches:
        logger.error("❌ 未找到比赛数据，无法测试")
        return
    
    logger.info(f"✅ 获取到 {len(matches)} 场比赛")
    
    # 3. 测试采集第一场
    match = matches[0]
    match_id = match.get('match_id')
    detail_url = match.get('detail_url')
    
    logger.info(f"正在测试采集比赛: {match.get('home_team')} vs {match.get('away_team')} (ID: {match_id})")
    logger.info(f"Detail URL: {detail_url}")
    
    if not detail_url:
        logger.error("❌ detail_url 为空")
        return

    try:
        # 4. 执行修复后的逻辑
        logger.info("1. 调用 fetch_match_detail_selenium ...")
        detail_html = bifaw_client.fetch_match_detail_selenium(detail_url=detail_url, timeout=30)
        
        logger.info(f"✅ 获取HTML成功，长度: {len(detail_html)}")
        
        if len(detail_html) < 100:
            logger.error("❌ HTML内容过短")
            return
            
        logger.info("2. 调用 parse_bifa_html ...")
        result = parse_bifa_html(detail_html)
        
        if isinstance(result, str):
            logger.error(f"❌ 解析失败: {result}")
            return
            
        trade_data = result
        metadata = trade_data.attrs.get('metadata', [])
        handicap_data = {} # parse_bifa_html 不返回 handicap_data
        
        if trade_data is None or trade_data.empty:
            logger.error("❌ 解析数据为空")
            return
            
        logger.info(f"✅ 解析成功: {len(trade_data)} 行交易数据")
        
        logger.info("3. 调用 save_detail ...")
        success = detail_cache_manager.save_detail(
            match_info=match,
            trade_data=trade_data,
            handicap_data=handicap_data,
            metadata=metadata,
            html_content=detail_html
        )
        
        if success:
            logger.info("✅✅✅ 验证成功！数据已保存到缓存。")
            
            # 验证缓存是否存在
            if detail_cache_manager.has_cache(match):
                logger.info("✅ has_cache() 验证通过")
            else:
                logger.error("❌ has_cache() 验证失败")
        else:
            logger.error("❌ save_detail 失败")
            
    except Exception as e:
        logger.exception(f"❌ 测试过程中发生异常: {e}")

if __name__ == "__main__":
    test_collection_fix()
