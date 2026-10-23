#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
诊断批量回测准确率问题
自动化检查所有可能的原因
"""

import sys
import json
import requests
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("🔍 批量回测问题诊断")
print("=" * 80)
print()

# 1. 检查Flask是否在运行
print("1️⃣ 检查Flask应用状态...")
try:
    response = requests.get("http://localhost:5000/", timeout=3)
    print(f"   ✅ Flask应用正在运行 (状态码: {response.status_code})")
except Exception as e:
    print(f"   ❌ Flask应用未运行: {e}")
    print("   请先启动Flask应用: python app.py")
    sys.exit(1)
print()

# 2. 检查推荐引擎代码
print("2️⃣ 检查推荐引擎代码...")
x1_file = Path("recommendation/x1_json_recommender.py")
if x1_file.exists():
    content = x1_file.read_text(encoding='utf-8')
    
    # 检查dynamic_threshold
    if 'dynamic_threshold = self._calculate_dynamic_threshold' in content:
        print("   ✅ generate_recommendation方法已使用dynamic_threshold")
        
        # 查找具体位置
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'dynamic_threshold = self._calculate_dynamic_threshold' in line:
                print(f"      位置: 第{i}行")
                break
    else:
        print("   ❌ generate_recommendation方法未使用dynamic_threshold")
        print("      问题：代码可能未正确修改")
    
    # 检查日志输出
    if '📊 推荐决策: direction' in content and 'dynamic_threshold' in content:
        print("   ✅ 推荐决策日志包含dynamic_threshold")
    else:
        print("   ❌ 推荐决策日志不包含dynamic_threshold")
else:
    print("   ❌ 找不到x1_json_recommender.py")
print()

# 3. 模拟批量回测API调用
print("3️⃣ 模拟批量回测API调用...")
print("   准备测试数据...")

# 从data目录找一个真实的比赛
data_dir = Path("data")
test_files = list(data_dir.rglob("2025-11-25_*_*_*.json"))

if not test_files:
    print("   ⚠️  未找到2025-11-25的测试数据")
    test_files = list(data_dir.rglob("2025-*_*_*.json"))

if test_files:
    # 只取前3场
    test_files = test_files[:3]
    print(f"   找到 {len(test_files)} 场测试比赛")
    
    matches = []
    for f in test_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            match_info = data.get('match_info', {})
            score = match_info.get('score', '')
            
            if not score or '-' not in score:
                continue
            
            home_score, away_score = score.split('-')
            
            match = {
                'match_info': {
                    'home': match_info.get('home', ''),
                    'away': match_info.get('away', ''),
                    'league': match_info.get('league', ''),
                    'kickoff': match_info.get('kickoff', ''),
                    'label': match_info.get('label', ''),
                },
                'detail_url': match_info.get('detail_url', ''),
                'actual_score': (int(home_score), int(away_score)),
                'score_for_cache': score,
                'detail_params': match_info.get('detail_params'),
            }
            matches.append(match)
        except Exception as e:
            continue
    
    if matches:
        print(f"   ✅ 准备了 {len(matches)} 场测试数据")
        print()
        
        # 调用批量回测API
        print("   📡 调用批量回测API...")
        try:
            response = requests.post(
                "http://localhost:5000/api/backtest/batch",
                json={"matches": matches},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ API调用成功")
                print(f"      总场次: {result.get('total', 0)}")
                print(f"      成功: {result.get('success_count', 0)}")
                print(f"      失败: {result.get('failed', 0)}")
                
                # 分析结果
                results = result.get('results', [])
                recommended = 0
                correct = 0
                
                for r in results:
                    if r.get('success'):
                        validation = r.get('validation', {})
                        if validation.get('recommended'):
                            recommended += 1
                            if validation.get('is_correct'):
                                correct += 1
                
                if recommended > 0:
                    accuracy = correct / recommended * 100
                    print(f"      推荐场次: {recommended}")
                    print(f"      正确: {correct}")
                    print(f"      准确率: {accuracy:.1f}%")
                    
                    if accuracy < 50:
                        print()
                        print("   ❌ 准确率异常低！")
                        print("      可能原因：")
                        print("      1. 测试数据质量差")
                        print("      2. 推荐引擎仍在使用旧代码")
                        print("      3. 验证器计算错误")
                    else:
                        print()
                        print("   ✅ 准确率正常")
                else:
                    print(f"      ⚠️  没有推荐任何比赛")
                    
            else:
                print(f"   ❌ API调用失败: {response.status_code}")
                print(f"      {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ API调用异常: {e}")
    else:
        print("   ⚠️  没有有效的测试数据")
else:
    print("   ❌ data目录中没有找到任何比赛数据")
print()

# 4. 检查最近的批量回测日志
print("4️⃣ 检查批量回测日志...")
log_file = Path("logs/backtest_detail.log")
if log_file.exists():
    print(f"   ✅ 日志文件存在")
    print(f"      大小: {log_file.stat().st_size} bytes")
    print(f"      修改时间: {datetime.fromtimestamp(log_file.stat().st_mtime)}")
    
    # 读取最后50行
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        last_lines = lines[-50:] if len(lines) > 50 else lines
    
    # 查找推荐决策
    decision_count = 0
    has_dynamic = False
    threshold_values = []
    
    for line in last_lines:
        if '推荐决策' in line or '📊' in line:
            decision_count += 1
            if 'dynamic_threshold' in line:
                has_dynamic = True
                # 提取阈值
                import re
                match = re.search(r'dynamic_threshold=([\d.]+)', line)
                if match:
                    threshold_values.append(float(match.group(1)))
    
    print(f"      推荐决策日志: {decision_count}条")
    
    if has_dynamic:
        print(f"      ✅ 包含dynamic_threshold")
        if threshold_values:
            print(f"      阈值范围: {min(threshold_values):.2f} - {max(threshold_values):.2f}")
            print(f"      平均阈值: {sum(threshold_values)/len(threshold_values):.2f}")
    else:
        print(f"      ❌ 不包含dynamic_threshold")
        print(f"      问题：推荐引擎可能未使用修复后的代码")
else:
    print(f"   ❌ 日志文件不存在")
print()

# 5. 检查浏览器缓存问题
print("5️⃣ 前端缓存检查...")
print("   建议操作：")
print("   1. 在浏览器中按 Ctrl + Shift + Delete")
print("   2. 选择'缓存的图片和文件'")
print("   3. 点击'清除数据'")
print("   4. 或者按 Ctrl + F5 强制刷新")
print()

print("=" * 80)
print("🎯 诊断总结")
print("=" * 80)
print()

# 总结
issues = []

if 'dynamic_threshold = self._calculate_dynamic_threshold' not in x1_file.read_text(encoding='utf-8'):
    issues.append("❌ 代码未正确修改")

if not has_dynamic and decision_count > 0:
    issues.append("❌ 日志中没有dynamic_threshold（引擎未使用新代码）")

if issues:
    print("发现问题：")
    for issue in issues:
        print(f"  {issue}")
    print()
    print("建议修复：")
    print("  1. 重启Flask应用")
    print("  2. 清除浏览器缓存")
    print("  3. 重新进行批量回测")
else:
    print("✅ 所有检查通过")
    print()
    print("如果Web界面还是33.3%，请：")
    print("  1. 清除浏览器缓存（Ctrl+Shift+Delete）")
    print("  2. 强制刷新页面（Ctrl+F5）")
    print("  3. 重新点击'批量回测'按钮")
    print("  4. 等待1-2分钟看到新结果")

print()
print("=" * 80)
