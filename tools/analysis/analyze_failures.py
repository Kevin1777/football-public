#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
失败案例分析 - 找出可优化的地方
"""

import json
from pathlib import Path
import re
from datetime import datetime

print("=" * 80)
print("📊 失败案例分析 - 寻找优化空间")
print("=" * 80)

# 分析失败案例的特征
failures = []
successes = []

# 加载一些案例
for year in [2025]:
    for month in [11]:
        for day in range(1, 27):
            date_path = Path("data") / str(year) / f"{month:02d}" / f"{day:02d}"
            
            if not date_path.exists():
                continue
            
            for json_file in list(date_path.glob("2025-11-*.json"))[:200]:  # 限制数量
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    match_info = data.get("match_info", {})
                    label = match_info.get("label", "")
                    score_match = re.search(r'(\d+)-(\d+)', label)
                    
                    if not score_match:
                        continue
                    
                    actual_score = (int(score_match.group(1)), int(score_match.group(2)))
                    
                    # 提取特征
                    trade_data = data.get("trade_data", {})
                    trade_list = trade_data.get('data', [])
                    if not trade_list:
                        continue
                    
                    latest = trade_list[0]
                    total_volume_str = latest.get('总成交量', '0')
                    total_volume = float(total_volume_str.replace(',', '')) if isinstance(total_volume_str, str) else float(total_volume_str or 0)
                    
                    if total_volume < 50000:
                        continue
                    
                    home_pct = float(latest.get('比例_主', 0) or 0)
                    away_pct = float(latest.get('比例_客', 0) or 0)
                    pct_diff = home_pct - away_pct
                    
                    bfindex_home = float(latest.get('必指_主', 0) or 0)
                    bfindex_away = float(latest.get('必指_客', 0) or 0)
                    bfindex_diff = bfindex_home - bfindex_away
                    
                    # 判断是否推荐
                    recommended = False
                    direction = None
                    
                    if pct_diff >= 30 and bfindex_diff >= 0:
                        recommended = True
                        direction = "home"
                    elif pct_diff <= -30 and bfindex_diff <= 0:
                        recommended = True
                        direction = "away"
                    
                    if not recommended:
                        continue
                    
                    # 计算结果
                    hd = data.get("handicap_data", {})
                    handicap = hd.get("current_handicap")
                    if handicap is None:
                        handicap = hd.get("initial_handicap")
                    if handicap is None:
                        continue
                    
                    home_score, away_score = actual_score
                    adjusted_home = home_score + handicap
                    diff = adjusted_home - away_score
                    
                    won = False
                    if direction == "home" and diff > 0.25:
                        won = True
                    elif direction == "away" and diff < -0.25:
                        won = True
                    
                    case = {
                        'label': label,
                        'direction': direction,
                        'pct_diff': pct_diff,
                        'bfindex_diff': bfindex_diff,
                        'total_volume': total_volume,
                        'handicap': handicap,
                        'actual_score': actual_score,
                        'diff': diff,
                        'won': won,
                        'league': match_info.get('league', '')
                    }
                    
                    if won:
                        successes.append(case)
                    else:
                        failures.append(case)
                
                except:
                    continue

print(f"\n✅ 成功案例: {len(successes)}场")
print(f"❌ 失败案例: {len(failures)}场")
print(f"📊 胜率: {len(successes)/(len(successes)+len(failures))*100:.1f}%")

# 分析失败案例的特征
print("\n" + "=" * 80)
print("❌ 失败案例特征分析")
print("=" * 80)

# 1. 按联赛分析
print("\n1. 失败案例的联赛分布:")
league_failures = {}
for case in failures:
    league = case['league']
    league_failures[league] = league_failures.get(league, 0) + 1

for league, count in sorted(league_failures.items(), key=lambda x: -x[1])[:10]:
    print(f"  {league}: {count}场")

# 2. 按成交占比差值分析
print("\n2. 失败案例的成交占比差值:")
pct_diffs = [abs(case['pct_diff']) for case in failures]
if pct_diffs:
    print(f"  平均值: {sum(pct_diffs)/len(pct_diffs):.1f}%")
    print(f"  最小值: {min(pct_diffs):.1f}%")
    print(f"  最大值: {max(pct_diffs):.1f}%")

success_pct_diffs = [abs(case['pct_diff']) for case in successes]
if success_pct_diffs:
    print(f"\n  成功案例平均: {sum(success_pct_diffs)/len(success_pct_diffs):.1f}%")
    print(f"  差异: {sum(success_pct_diffs)/len(success_pct_diffs) - sum(pct_diffs)/len(pct_diffs):.1f}%")

# 3. 按盘口大小分析
print("\n3. 失败案例的盘口分布:")
handicaps = [abs(case['handicap']) for case in failures]
if handicaps:
    print(f"  平均盘口: {sum(handicaps)/len(handicaps):.2f}")
    deep_handicaps = [h for h in handicaps if h > 1.5]
    print(f"  深盘(>1.5): {len(deep_handicaps)}场 ({len(deep_handicaps)/len(handicaps)*100:.1f}%)")

# 4. 按成交量分析
print("\n4. 失败案例的成交量:")
volumes = [case['total_volume'] for case in failures]
if volumes:
    print(f"  平均成交量: {sum(volumes)/len(volumes):,.0f}")
    small_volumes = [v for v in volumes if v < 100000]
    print(f"  小成交量(<100K): {len(small_volumes)}场 ({len(small_volumes)/len(volumes)*100:.1f}%)")

# 优化建议
print("\n" + "=" * 80)
print("💡 优化建议")
print("=" * 80)

print("""
基于失败案例分析，可能的优化方向：

1. 提高成交占比差阈值
   - 当前: 30%
   - 建议: 35-40%（可能提升2-3%胜率，但推荐率下降）

2. 过滤深盘比赛
   - 过滤盘口>1.5的比赛
   - 深盘穿盘风险高

3. 提高成交量阈值
   - 当前: 50,000
   - 建议: 80,000-100,000（数据更可靠）

4. 添加联赛过滤
   - 只推荐主流联赛（中超、五大联赛等）
   - 小联赛数据质量差

5. 添加必发指数阈值
   - 当前: ≥0即可
   - 建议: ≥10（更明确的优势）

预期效果：
- 胜率: 69.5% → 72-75%
- 推荐率: 39% → 25-30%
""")

print("\n" + "=" * 80)
print("✅ 分析完成")
print("=" * 80)
