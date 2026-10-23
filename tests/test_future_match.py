#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试未来比赛（标盘场次）的盘口数据获取
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

from services.lottery500_client import Lottery500Client

def test_future_match():
    """测试未来比赛盘口获取"""
    
    print("=" * 80)
    print("测试未来比赛（标盘场次）盘口数据获取")
    print("=" * 80)
    
    # 创建客户端
    client = Lottery500Client()
    
    # 测试数据：使用今天或未来的比赛（从截图看到的真实比赛）
    tomorrow = (datetime.now() + timedelta(days=0)).strftime("%Y-%m-%d")
    
    test_cases = [
        {
            "home": "中乙",  # 从截图看到的
            "away": "升级附加",
            "league": "中青赛",
            "match_date": tomorrow,
            "match_time": f"{tomorrow} 14:30",
        },
    ]
    
    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"测试用例 {idx}: {test['home']} vs {test['away']}")
        print(f"日期: {test['match_date']}")
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
                print(f"提示：可能需要使用页面上真实存在的比赛进行测试")
                
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
            print(f"\n找到 {len(html_files)} 个HTML文件（最新5个）：")
            for f in sorted(html_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                size = f.stat().st_size
                print(f"  - {f.name} ({size} 字节)")

if __name__ == "__main__":
    test_future_match()
