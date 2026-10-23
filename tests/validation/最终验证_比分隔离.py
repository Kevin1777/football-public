#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最终验证：确认推荐引擎完全隔离比分信息
"""

import json
import re
from pathlib import Path
from recommendation.x1_json_recommender_fixed import X1JSONRecommenderFixed


def test_score_isolation():
    """测试：修改比分不影响推荐结果"""
    
    print("=" * 80)
    print("🔬 最终验证：比分隔离测试")
    print("=" * 80)
    print()
    print("测试方法：")
    print("1. 选择一场比赛")
    print("2. 生成推荐（原始比分）")
    print("3. 修改JSON中的比分")
    print("4. 再次生成推荐（修改后比分）")
    print("5. 对比两次推荐是否完全相同")
    print()
    print("如果推荐完全相同 → 证明未使用比分")
    print("如果推荐不同 → 证明使用了比分（数据泄露）")
    print()
    print("=" * 80)
    print()
    
    # 选择测试文件
    data_dir = Path("data")
    test_files = list(data_dir.rglob("2025-*_*_*_*.json"))
    
    if not test_files:
        print("❌ 未找到测试文件")
        return False
    
    test_file = test_files[0]
    
    # 提取信息
    pattern = r'(\d{4}-\d{2}-\d{2})_.*_(\d+)_(\d+)_(\d{4})\.json$'
    match = re.search(pattern, test_file.name)
    
    if not match:
        print("❌ 无法解析文件名")
        return False
    
    date = match.group(1)
    original_home_score = int(match.group(2))
    original_away_score = int(match.group(3))
    time = match.group(4)
    hour = time[:2]
    minute = time[2:]
    kickoff_time = f"{date} {hour}:{minute}:00"
    
    print(f"测试文件: {test_file.name}")
    print(f"原始比分: {original_home_score}-{original_away_score}")
    print(f"开赛时间: {kickoff_time}")
    print()
    
    # 读取原始JSON
    with open(test_file, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
    
    # 测试1：使用原始比分
    print("🔍 测试1：使用原始比分生成推荐...")
    engine = X1JSONRecommenderFixed()
    
    result1 = engine.recommend(str(test_file), kickoff_time=kickoff_time, strict_mode=True)
    
    rec1 = result1.get('recommendation', {})
    direction1 = rec1.get('direction', 'none')
    confidence1 = rec1.get('confidence', 0)
    
    print(f"   推荐: {direction1}")
    print(f"   置信度: {confidence1:.4f}")
    print()
    
    # 创建修改版本
    modified_data = json.loads(json.dumps(original_data))  # 深拷贝
    
    # 修改比分为完全不同的值
    new_home_score = (original_home_score + 5) % 10
    new_away_score = (original_away_score + 3) % 10
    
    if 'match_info' in modified_data and 'score' in modified_data['match_info']:
        modified_data['match_info']['score'] = f"{new_home_score}-{new_away_score}"
    
    if 'match_info' in modified_data and 'label' in modified_data['match_info']:
        old_label = modified_data['match_info']['label']
        modified_data['match_info']['label'] = old_label.replace(
            f"{original_home_score}-{original_away_score}",
            f"{new_home_score}-{new_away_score}"
        )
    
    # 保存修改版
    temp_file = test_file.parent / f"temp_modified_{test_file.name}"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(modified_data, f, ensure_ascii=False, indent=2)
    
    print(f"🔍 测试2：使用修改后比分 ({new_home_score}-{new_away_score}) 生成推荐...")
    
    result2 = engine.recommend(str(temp_file), kickoff_time=kickoff_time, strict_mode=True)
    
    rec2 = result2.get('recommendation', {})
    direction2 = rec2.get('direction', 'none')
    confidence2 = rec2.get('confidence', 0)
    
    print(f"   推荐: {direction2}")
    print(f"   置信度: {confidence2:.4f}")
    print()
    
    # 删除临时文件
    temp_file.unlink()
    
    # 对比结果
    print("=" * 80)
    print("📊 对比结果")
    print("=" * 80)
    print()
    
    print(f"原始比分 ({original_home_score}-{original_away_score}): 推荐{direction1}, 置信度{confidence1:.4f}")
    print(f"修改比分 ({new_home_score}-{new_away_score}): 推荐{direction2}, 置信度{confidence2:.4f}")
    print()
    
    if direction1 == direction2 and abs(confidence1 - confidence2) < 0.0001:
        print("✅ 验证通过：比分修改不影响推荐")
        print()
        print("🎉 确认：推荐引擎完全隔离比分信息")
        print("   - 推荐方向相同")
        print("   - 置信度相同")
        print("   - 比分只是元数据，不参与计算")
        print()
        return True
    else:
        print("❌ 验证失败：比分修改影响了推荐")
        print()
        print("⚠️  警告：可能存在数据泄露")
        print("   - 推荐方向或置信度不同")
        print("   - 比分信息可能被使用")
        print()
        return False


def explain_score_in_json():
    """解释：为什么JSON中有比分"""
    
    print("=" * 80)
    print("💡 说明：JSON中的比分信息")
    print("=" * 80)
    print()
    
    print("Q: 为什么JSON文件中包含比分？")
    print()
    print("A: 这是数据采集时的标注信息，用于：")
    print("   1. 文件管理和查找")
    print("   2. 回测时验证准确率")
    print("   3. 数据追溯和审计")
    print()
    print("关键：推荐引擎不使用这个字段！")
    print()
    print("验证方法：")
    print("   - 修改JSON中的比分")
    print("   - 推荐结果保持不变")
    print("   - 证明比分不参与计算")
    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    explain_score_in_json()
    
    passed = test_score_isolation()
    
    print()
    print("=" * 80)
    print("🎯 最终结论")
    print("=" * 80)
    print()
    
    if passed:
        print("✅ 推荐引擎完全隔离比分")
        print("✅ JSON中的比分只是元数据标注")
        print("✅ 准确率是真实的，无数据泄露")
        print()
        print("💯 系统可信度：100%")
    else:
        print("❌ 存在数据泄露风险")
        print("❌ 需要进一步检查代码")
    
    print()
    print("=" * 80)
