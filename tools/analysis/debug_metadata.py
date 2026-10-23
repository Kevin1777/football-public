"""调试metadata结构"""
import sys
sys.path.insert(0, 'd:\\MSM\\Cursor\\football')

from backtest import BacktestEngine
from backtest.detail_cache_manager import DetailCacheManager
from recommendation.x1_json_recommender_v4_ultra import X1JSONRecommenderV4Ultra
from services.lottery500_client import Lottery500Client
from services.bifaw_client import BifawClient
import pandas as pd
from pathlib import Path
import json

# 加载一个英超比赛数据
data_dir = Path("data")
epl_files = list(data_dir.rglob("*英超*.json"))

if epl_files:
    json_file = epl_files[0]
    print(f"测试文件: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    match_info = data.get('match_info', {})
    print(f"\nmatch_info结构:")
    print(json.dumps(match_info, indent=2, ensure_ascii=False))
    
    # 提取metadata（模拟回测引擎）
    metadata = match_info
    
    print(f"\nmetadata类型: {type(metadata)}")
    print(f"metadata内容:")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    # 测试V4引擎
    trade_data = pd.DataFrame(data.get('trade_data', {}).get('data', []))
    handicap_data = data.get('handicap_data', {})
    
    print(f"\ntrade_data行数: {len(trade_data)}")
    print(f"handicap_data: {handicap_data}")
    
    # 初始化引擎
    engine = X1JSONRecommenderV4Ultra()
    
    # 测试推荐
    result = engine.generate_recommendation(trade_data, metadata, handicap_data)
    
    print(f"\n推荐结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print("未找到英超比赛数据")
