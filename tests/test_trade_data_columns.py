#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断交易明细数据列名问题
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

# 测试比赛
match_info = {
    "match_id": "2511176",
    "home": "里昂",
    "away": "巴黎圣日耳曼",
    "league": "法甲",
    "market_id": "1",
    "opentime": "2025-11-09 03:45:00"
}

print("=" * 80)
print("测试交易明细数据列名")
print("=" * 80)

client = BifawClient()

# 获取交易明细
print(f"\n获取交易明细: {match_info['home']} vs {match_info['away']}")

trade_data = client.fetch_trade_details(
    match_id=match_info['match_id'],
    market_id=match_info['market_id'],
    opentime=match_info['opentime']
)

if trade_data is not None and not trade_data.empty:
    print(f"\n✅ 成功获取交易明细")
    print(f"数据形状: {trade_data.shape}")
    print(f"\n列名列表:")
    for i, col in enumerate(trade_data.columns, 1):
        print(f"  {i}. {col}")
    
    print(f"\n前5行数据:")
    print(trade_data.head())
    
    print(f"\n数据类型:")
    print(trade_data.dtypes)
    
    # 检查是否有主/客/平相关的列
    print(f"\n包含'主'的列:")
    for col in trade_data.columns:
        if '主' in str(col):
            print(f"  - {col}")
    
    print(f"\n包含'客'的列:")
    for col in trade_data.columns:
        if '客' in str(col):
            print(f"  - {col}")
    
    print(f"\n包含'平'的列:")
    for col in trade_data.columns:
        if '平' in str(col):
            print(f"  - {col}")
    
    print(f"\n包含'成交'的列:")
    for col in trade_data.columns:
        if '成交' in str(col):
            print(f"  - {col}")
    
else:
    print(f"\n❌ 未获取到交易明细")

print(f"\n{'=' * 80}")
print("诊断完成")
print(f"{'=' * 80}")
