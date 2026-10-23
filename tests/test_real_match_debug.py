#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient
from parser.html_parser import parse_bifa_html
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

# 里昂 vs 巴黎圣日耳曼
match_info = {
    "home": "里昂",
    "away": "巴黎圣日耳曼",
    "league": "法甲",
    "kickoff": "2025-11-10 03:45:00"
}

detail_url = "https://live.bf90.io/bifaw/sporttery.php?mid=2511176&marketid=1&opentime=2025-11-09%2003:45:00"

print("=" * 80)
print(f"测试: {match_info['home']} vs {match_info['away']}")
print("=" * 80)

client = BifawClient()

print("\n抓取交易明细...")
html = client.fetch_match_detail_selenium(
    detail_url=detail_url,
    match=match_info
)

if html:
    print(f"✅ HTML长度: {len(html)}")
    
    print("\n解析HTML...")
    trade_data = parse_bifa_html(html, match=match_info)
    
    if isinstance(trade_data, pd.DataFrame) and not trade_data.empty:
        print(f"✅ 解析成功: {trade_data.shape[0]} 行 x {trade_data.shape[1]} 列")
        
        print(f"\n📋 列名:")
        for i, col in enumerate(trade_data.columns, 1):
            print(f"  {i}. {col} ({trade_data[col].dtype})")
        
        print(f"\n📊 前5行:")
        print(trade_data.head())
        
        # 检查关键列
        print(f"\n🔍 包含'主'的列:")
        for col in trade_data.columns:
            if '主' in str(col):
                val = trade_data[col].sum() if pd.api.types.is_numeric_dtype(trade_data[col]) else 'NON-NUMERIC'
                print(f"  - {col}: {val}")
        
        print(f"\n🔍 包含'客'的列:")
        for col in trade_data.columns:
            if '客' in str(col):
                val = trade_data[col].sum() if pd.api.types.is_numeric_dtype(trade_data[col]) else 'NON-NUMERIC'
                print(f"  - {col}: {val}")
        
        print(f"\n🔍 包含'成交'的列:")
        for col in trade_data.columns:
            if '成交' in str(col):
                val = trade_data[col].sum() if pd.api.types.is_numeric_dtype(trade_data[col]) else 'NON-NUMERIC'
                print(f"  - {col}: {val}")
                
        print(f"\n🔍 包含'平'的列:")
        for col in trade_data.columns:
            if '平' in str(col):
                val = trade_data[col].sum() if pd.api.types.is_numeric_dtype(trade_data[col]) else 'NON-NUMERIC'
                print(f"  - {col}: {val}")
    else:
        print(f"❌ 解析失败: {trade_data}")
else:
    print("❌ HTML获取失败")

print(f"\n{'=' * 80}")
print("诊断完成")
print(f"{'=' * 80}")
