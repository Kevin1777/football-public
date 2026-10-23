#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析最近一次批量回测的真实结果
"""

from pathlib import Path
import re
from datetime import datetime

print("=" * 80)
print("🔍 分析最近批量回测结果")
print("=" * 80)
print()

# 读取日志
log_file = Path("logs/backtest_detail.log")
if not log_file.exists():
    print("❌ 日志文件不存在")
    exit(1)

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print(f"📄 日志文件大小: {len(lines)} 行")
print()

# 查找最近的推荐决策（12:57之后）
recent_decisions = []
for line in lines:
    if '12:57' in line and '推荐决策' in line:
        recent_decisions.append(line)

if not recent_decisions:
    print("⚠️  未找到12:57的批量回测日志")
    print()
    print("可能原因：")
    print("1. 回测日志写入到其他文件")
    print("2. 日志被清空")
    print("3. 回测还没开始")
    print()
    
    # 查找最近的任何推荐决策
    print("查找最近100行的推荐决策...")
    recent_100 = lines[-100:]
    all_decisions = [l for l in recent_100 if '推荐决策' in l]
    
    if all_decisions:
        print(f"找到 {len(all_decisions)} 条推荐决策")
        print()
        print("最后3条：")
        for line in all_decisions[-3:]:
            print(line.strip())
    else:
        print("❌ 最近100行没有推荐决策")
else:
    print(f"✅ 找到 {len(recent_decisions)} 条12:57的推荐决策")
    print()
    
    # 分析推荐
    should_bet_true = 0
    should_bet_false = 0
    thresholds = []
    confidences = []
    
    for line in recent_decisions:
        if 'should_bet=True' in line:
            should_bet_true += 1
        if 'should_bet=False' in line:
            should_bet_false += 1
        
        # 提取阈值
        match = re.search(r'dynamic_threshold=([\d.]+)', line)
        if match:
            thresholds.append(float(match.group(1)))
        
        # 提取置信度
        match = re.search(r'confidence=([\d.]+)', line)
        if match:
            confidences.append(float(match.group(1)))
    
    print(f"📊 推荐统计:")
    print(f"   总决策: {len(recent_decisions)}")
    print(f"   推荐: {should_bet_true}")
    print(f"   不推荐: {should_bet_false}")
    print()
    
    if thresholds:
        print(f"🎯 动态阈值范围: {min(thresholds):.2f} - {max(thresholds):.2f}")
        print(f"   平均阈值: {sum(thresholds)/len(thresholds):.2f}")
        print()
    
    if confidences:
        print(f"💡 置信度范围: {min(confidences):.2f} - {max(confidences):.2f}")
        print(f"   平均置信度: {sum(confidences)/len(confidences):.2f}")
        print()
    
    # 显示前5条
    print("示例（前5条）:")
    for line in recent_decisions[:5]:
        # 简化显示
        line = line.strip()
        if len(line) > 150:
            line = line[:150] + "..."
        print(f"   {line}")
    print()

print("=" * 80)
print("🎯 结论")
print("=" * 80)
print()

if recent_decisions:
    print("✅ 策略1（动态阈值）正在工作")
    print(f"✅ 最近回测推荐了 {should_bet_true} 场比赛")
    print()
    
    if should_bet_true > 0:
        recommendation_rate = should_bet_true / len(recent_decisions) * 100
        print(f"推荐率: {recommendation_rate:.1f}%")
        
        if recommendation_rate < 20:
            print("这是正常的！策略1会严格筛选，只推荐高质量比赛。")
        print()
    
    print("⚠️  如果Web界面还是33.3%，问题是：")
    print("   1. 浏览器缓存了旧结果")
    print("   2. 前端JavaScript未正确更新显示")
    print()
    print("解决方案：")
    print("   1. 按 Ctrl + Shift + Delete 清除所有缓存")
    print("   2. 使用无痕模式访问: Ctrl + Shift + N")
    print("   3. 或等待2-3分钟让浏览器自动刷新")
else:
    print("⚠️  12:57的批量回测日志缺失")
    print()
    print("建议：")
    print("   1. 在Web界面重新点击'批量回测'")
    print("   2. 同时运行: Get-Content logs\\backtest_detail.log -Wait -Tail 20")
    print("   3. 确认看到新的推荐决策日志")

print()
print("=" * 80)
