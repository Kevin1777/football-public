"""测试V4对list格式metadata的处理"""
import sys
sys.path.insert(0, 'd:\\MSM\\Cursor\\football')

from recommendation.x1_json_recommender_v4_ultra import X1JSONRecommenderV4Ultra
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
    
    # 从缓存数据中提取metadata（list格式）
    metadata_from_cache = data.get('metadata', [])
    print(f"\nmetadata_from_cache: {metadata_from_cache}")
    print(f"类型: {type(metadata_from_cache)}")
    
    # 如果没有metadata字段，手动构造
    if not metadata_from_cache:
        metadata_from_cache = [
            match_info.get('league', ''),
            match_info.get('home', ''),
            match_info.get('away', '')
        ]
        print(f"\n手动构造metadata: {metadata_from_cache}")
    
    # 测试V4引擎
    trade_data = pd.DataFrame(data.get('trade_data', {}).get('data', []))
    handicap_data = data.get('handicap_data', {})
    
    # 初始化引擎
    engine = X1JSONRecommenderV4Ultra()
    
    # 使用list格式metadata测试
    print(f"\n使用list格式metadata测试:")
    result = engine.generate_recommendation(trade_data, metadata_from_cache, handicap_data)
    
    print(f"\n推荐结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print("未找到英超比赛数据")
