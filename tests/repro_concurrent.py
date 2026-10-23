import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录 to path
sys.path.append(str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager
from parser.html_parser import parse_bifa_html

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量模拟 app.py
bifaw_client = BifawClient()
detail_cache_manager = DetailCacheManager(cache_dir="data")

def collect_single(match_info):
    match, idx = match_info
    match_id = match.get('match_id')
    
    try:
        # 模拟 app.py 中的逻辑
        detail_url = match.get('detail_url')
        if not detail_url:
            return {'status': 'failed', 'match_id': match_id, 'error': 'no_detail_url'}
        
        # 使用 fetch_match_detail_selenium
        # 注意：这里会创建新的 driver
        detail_html = bifaw_client.fetch_match_detail_selenium(detail_url=detail_url, timeout=30)
        
        if detail_html and len(detail_html) > 100:
            result = parse_bifa_html(detail_html)
            
            if isinstance(result, str):
                return {'status': 'failed', 'match_id': match_id, 'error': f'parse_failed: {result}'}
            
            trade_data = result
            metadata = trade_data.attrs.get('metadata', [])
            
            # 模拟保存
            # success = detail_cache_manager.save_detail(...)
            # 为了测试，我们只打印
            logger.info(f"Match {match_id}: Parsed {len(trade_data)} rows")
            return {'status': 'success', 'match_id': match_id}
        else:
            return {'status': 'failed', 'match_id': match_id, 'error': 'empty_html'}
            
    except Exception as e:
        logger.error(f"Match {match_id} FAILED: {type(e).__name__} - {e}")
        return {'status': 'failed', 'match_id': match_id, 'error': str(e)}

def test_concurrent_collection():
    logger.info("🚀 开始并发采集测试...")
    
    # 1. 获取比赛列表 (2025-11-28)
    target_date = datetime(2025, 11, 28)
    logger.info(f"正在获取 {target_date.strftime('%Y-%m-%d')} 的比赛...")
    
    _, matches, _ = bifaw_client.fetch_finished_matches(target_date=target_date, rows=10) # 测试10场
    
    if not matches:
        logger.error("❌ 未找到比赛数据")
        return
    
    logger.info(f"✅ 获取到 {len(matches)} 场比赛")
    
    # 2. 并发采集
    workers = 3
    logger.info(f"启动 {workers} 个并发线程...")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(collect_single, (m, i)): i for i, m in enumerate(matches)}
        
        for future in as_completed(futures):
            try:
                result = future.result()
                logger.info(f"Result: {result}")
            except Exception as e:
                logger.error(f"Future exception: {e}")

if __name__ == "__main__":
    test_concurrent_collection()
