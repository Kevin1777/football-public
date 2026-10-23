#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试500彩票网盘口数据获取
"""

import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置日志级别为INFO，查看详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

from services.lottery500_client import Lottery500Client

def test_handicap_fetch():
    """测试盘口数据获取"""
    
    print("=" * 80)
    print("测试500彩票网盘口数据获取")
    print("=" * 80)
    
    # 创建客户端
    client = Lottery500Client()
    
    # 测试数据：使用HTML中真实存在的比赛
    test_cases = [
        {
            "home": "坦皮科马德罗",
            "away": "哥达拿查拉大学",  # HTML中是"瓜达拉哈拉大学"
            "league": "墨西甲",
            "match_date": "2025-11-17",
            "match_time": "2025-11-17 10:00",
        },
    ]
    
    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"测试用例 {idx}: {test['home']} vs {test['away']}")
        print(f"{'=' * 80}")
        
        try:
            result = client.get_match_handicap(
                home_team=test["home"],
                away_team=test["away"],
                league=test["league"],
                match_date=test["match_date"],
                match_time=test["match_time"],
            )
            
            if result:
                print(f"✅ 成功获取盘口数据")
                print(f"结果: {result}")
            else:
                print(f"❌ 未获取到盘口数据")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 80}")
    print("测试完成")
    print(f"{'=' * 80}")
    
    # 提示查看debug_html目录
    debug_dir = Path(__file__).parent / "debug_html"
    print(f"\n请查看保存的HTML文件：{debug_dir}")
    
    if debug_dir.exists():
        html_files = list(debug_dir.glob("500_*.html"))
        if html_files:
            print(f"\n找到 {len(html_files)} 个HTML文件：")
            for f in sorted(html_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                size = f.stat().st_size
                print(f"  - {f.name} ({size} 字节)")

if __name__ == "__main__":
    test_handicap_fetch()
