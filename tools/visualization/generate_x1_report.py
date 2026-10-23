#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1推荐模型 - 生成详细测试报告

功能：
1. 批量测试data目录中的所有比赛
2. 生成详细的测试报告（Markdown格式）
3. 统计各项指标
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from recommendation.x1_json_recommender import X1JSONRecommender

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def generate_report():
    """生成测试报告"""
    
    print("="*80)
    print("🎯 X1 JSON推荐模型 - 全数据测试报告生成")
    print("="*80)
    print()
    
    recommender = X1JSONRecommender()
    data_dir = Path("data")
    
    # 收集所有比赛JSON文件
    all_json_files = list(data_dir.rglob("2025-*.json"))
    
    print(f"📂 找到 {len(all_json_files)} 个比赛文件")
    print(f"⏳ 开始处理...")
    print()
    
    results = []
    success_count = 0
    meltdown_count = 0
    
    # 统计数据
    stats = {
        'total': len(all_json_files),
        'success': 0,
        'meltdown': 0,
        'home_rec': 0,
        'away_rec': 0,
        'none_rec': 0,
        'high_conf': 0,  # >= 0.85
        'mid_conf': 0,   # 0.60 - 0.85
        'low_conf': 0,   # < 0.60
        'funding_levels': {'L1': 0, 'L2': 0, 'L3': 0, 'L4': 0, 'L5': 0},
        'risk_flags': {'SmartSafe': 0, 'SS-Dagger': 0, 'LVC': 0, 'TPI': 0},
        'sbre_triggered': 0,
        'flm_levels': {},
        'spm_structures': {},
        'dpi_risks': {}
    }
    
    for i, json_file in enumerate(all_json_files, 1):
        if i % 10 == 0:
            print(f"  处理中... {i}/{len(all_json_files)}")
        
        result = recommender.recommend(str(json_file))
        
        # 判断是否熔断
        if result.get('meltdown'):
            meltdown_count += 1
            stats['meltdown'] += 1
            continue
        
        success_count += 1
        stats['success'] += 1
        
        # 提取信息
        rec = result.get('recommendation', {})
        direction = rec.get('direction', 'none')
        confidence = rec.get('confidence', 0)
        funding = result.get('funding_level', {})
        scores = result.get('scores', {})
        risk_control = result.get('risk_control', {})
        sbre = result.get('sbre', {})
        
        # 统计推荐方向
        if direction == 'home':
            stats['home_rec'] += 1
        elif direction == 'away':
            stats['away_rec'] += 1
        else:
            stats['none_rec'] += 1
        
        # 统计置信度
        if confidence >= 0.85:
            stats['high_conf'] += 1
        elif confidence >= 0.60:
            stats['mid_conf'] += 1
        else:
            stats['low_conf'] += 1
        
        # 统计资金等级
        level = funding.get('level', 'L1')
        stats['funding_levels'][level] += 1
        
        # 统计风控触发
        for flag in ['SmartSafe', 'SS-Dagger', 'LVC', 'TPI']:
            if risk_control.get(flag):
                stats['risk_flags'][flag] += 1
        
        # 统计SBRE
        if sbre.get('triggered'):
            stats['sbre_triggered'] += 1
        
        # 统计评分等级
        flm_level = scores.get('FLM', {}).get('level', 'unknown')
        spm_structure = scores.get('SPM', {}).get('structure', 'unknown')
        dpi_risk = scores.get('DPI', {}).get('risk_level', 'unknown')
        
        stats['flm_levels'][flm_level] = stats['flm_levels'].get(flm_level, 0) + 1
        stats['spm_structures'][spm_structure] = stats['spm_structures'].get(spm_structure, 0) + 1
        stats['dpi_risks'][dpi_risk] = stats['dpi_risks'].get(dpi_risk, 0) + 1
        
        # 保存结果
        results.append({
            'file': json_file.name,
            'match_info': result.get('match_info', {}),
            'recommendation': rec,
            'funding_level': funding,
            'scores': scores,
            'risk_control': risk_control,
            'sbre': sbre
        })
    
    print()
    print(f"✅ 处理完成！成功: {success_count}, 熔断: {meltdown_count}")
    print()
    
    # 生成Markdown报告
    report_file = "X1_测试报告.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# X1 JSON推荐模型 - 测试报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # 1. 总体统计
        f.write("## 📊 总体统计\n\n")
        f.write(f"- **测试比赛总数**: {stats['total']}\n")
        f.write(f"- **成功生成推荐**: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)\n")
        f.write(f"- **触发熔断**: {stats['meltdown']} ({stats['meltdown']/stats['total']*100:.1f}%)\n\n")
        
        # 2. 推荐方向分布
        f.write("## 🎯 推荐方向分布\n\n")
        f.write(f"| 方向 | 数量 | 占比 |\n")
        f.write(f"|------|------|------|\n")
        f.write(f"| 推荐主队 | {stats['home_rec']} | {stats['home_rec']/stats['success']*100:.1f}% |\n")
        f.write(f"| 推荐客队 | {stats['away_rec']} | {stats['away_rec']/stats['success']*100:.1f}% |\n")
        f.write(f"| 不推荐 | {stats['none_rec']} | {stats['none_rec']/stats['success']*100:.1f}% |\n\n")
        
        # 3. 置信度分布
        f.write("## 📈 置信度分布\n\n")
        f.write(f"| 等级 | 范围 | 数量 | 占比 |\n")
        f.write(f"|------|------|------|------|\n")
        f.write(f"| 🟢 高置信度 | ≥ 0.85 | {stats['high_conf']} | {stats['high_conf']/stats['success']*100:.1f}% |\n")
        f.write(f"| 🟡 中置信度 | 0.60-0.85 | {stats['mid_conf']} | {stats['mid_conf']/stats['success']*100:.1f}% |\n")
        f.write(f"| 🔴 低置信度 | < 0.60 | {stats['low_conf']} | {stats['low_conf']/stats['success']*100:.1f}% |\n\n")
        
        # 4. 资金等级分布
        f.write("## 💰 资金等级分布\n\n")
        f.write(f"| 等级 | 范围 | 数量 | 占比 |\n")
        f.write(f"|------|------|------|------|\n")
        for level in ['L1', 'L2', 'L3', 'L4', 'L5']:
            count = stats['funding_levels'][level]
            f.write(f"| {level} | {recommender.funding_levels[level][0]:,} - {recommender.funding_levels[level][1]:,} | {count} | {count/stats['success']*100:.1f}% |\n")
        f.write("\n")
        
        # 5. 评分模块分布
        f.write("## 🎯 FLM热度前线分布\n\n")
        f.write(f"| 等级 | 数量 | 占比 |\n")
        f.write(f"|------|------|------|\n")
        for level, count in sorted(stats['flm_levels'].items(), key=lambda x: -x[1]):
            f.write(f"| {level} | {count} | {count/stats['success']*100:.1f}% |\n")
        f.write("\n")
        
        f.write("## 🏗️ SPM结构承压分布\n\n")
        f.write(f"| 结构 | 数量 | 占比 |\n")
        f.write(f"|------|------|------|\n")
        for structure, count in sorted(stats['spm_structures'].items(), key=lambda x: -x[1]):
            f.write(f"| {structure} | {count} | {count/stats['success']*100:.1f}% |\n")
        f.write("\n")
        
        f.write("## ⚠️ DPI风险等级分布\n\n")
        f.write(f"| 风险等级 | 数量 | 占比 |\n")
        f.write(f"|----------|------|------|\n")
        for risk, count in sorted(stats['dpi_risks'].items(), key=lambda x: -x[1]):
            f.write(f"| {risk} | {count} | {count/stats['success']*100:.1f}% |\n")
        f.write("\n")
        
        # 6. 风控机制触发
        f.write("## 🚨 风控机制触发统计\n\n")
        f.write(f"| 风控机制 | 触发次数 | 占比 |\n")
        f.write(f"|----------|----------|------|\n")
        total_risk_triggers = sum(stats['risk_flags'].values())
        for flag, count in stats['risk_flags'].items():
            f.write(f"| {flag} | {count} | {count/stats['success']*100:.1f}% |\n")
        f.write(f"\n**总触发次数**: {total_risk_triggers}\n\n")
        
        # 7. SBRE反解
        f.write("## 🔄 SBRE反解机制\n\n")
        f.write(f"- **触发次数**: {stats['sbre_triggered']}\n")
        f.write(f"- **触发率**: {stats['sbre_triggered']/stats['success']*100:.1f}%\n\n")
        
        # 8. 高置信度推荐列表
        f.write("## 🌟 高置信度推荐列表 (≥ 0.85)\n\n")
        high_conf_results = [r for r in results if r['recommendation'].get('confidence', 0) >= 0.85]
        
        if high_conf_results:
            f.write(f"找到 {len(high_conf_results)} 个高置信度推荐:\n\n")
            for i, item in enumerate(high_conf_results[:20], 1):  # 只显示前20个
                match = item['match_info']
                rec = item['recommendation']
                f.write(f"{i}. **{match.get('home', 'N/A')} vs {match.get('away', 'N/A')}**\n")
                f.write(f"   - 联赛: {match.get('league', 'N/A')}\n")
                f.write(f"   - 推荐: {rec.get('handicap', 'N/A')}\n")
                f.write(f"   - 置信度: {rec.get('confidence_pct', 'N/A')}\n")
                f.write(f"   - 理由: {rec.get('reason', 'N/A')}\n\n")
        else:
            f.write("未找到高置信度推荐\n\n")
        
        # 9. 风险提示
        f.write("## ⚠️ 注意事项\n\n")
        f.write("1. **置信度解读**:\n")
        f.write("   - 🟢 高置信度 (≥0.85): 可考虑跟投\n")
        f.write("   - 🟡 中置信度 (0.60-0.85): 谨慎参考\n")
        f.write("   - 🔴 低置信度 (<0.60): 不建议跟投\n\n")
        f.write("2. **风控优先**: 任何风控触发的比赛，需要额外谨慎\n\n")
        f.write("3. **资金等级**: L1/L2资金等级的比赛，SBRE反解权重更高\n\n")
        f.write("4. **数据来源**: 全部基于data目录中的JSON文件，数据质量直接影响推荐效果\n\n")
        
        # 10. 总结
        f.write("## 📝 总结\n\n")
        f.write(f"本次测试共处理 {stats['total']} 场比赛，成功生成 {stats['success']} 个推荐。\n\n")
        
        rec_rate = (stats['home_rec'] + stats['away_rec']) / stats['success'] * 100 if stats['success'] > 0 else 0
        f.write(f"- **推荐率**: {rec_rate:.1f}% (有明确推荐方向)\n")
        f.write(f"- **高置信度占比**: {stats['high_conf']/stats['success']*100:.1f}%\n")
        f.write(f"- **风控触发率**: {total_risk_triggers/stats['success']*100:.1f}%\n\n")
        
        if stats['high_conf'] > 0:
            f.write("✅ **推荐使用策略**: 优先跟随高置信度推荐，注意风控提示\n\n")
        else:
            f.write("⚠️ **建议**: 当前数据中无高置信度推荐，建议优化数据源或调整阈值\n\n")
        
        f.write("---\n\n")
        f.write(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    print(f"✅ 报告已生成: {report_file}")
    print()
    
    # 同时生成JSON格式的详细结果
    json_file = "X1_测试详细结果.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'statistics': stats,
            'results': results[:100]  # 只保存前100个详细结果
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 详细结果已导出: {json_file}")
    print()
    
    return stats


if __name__ == "__main__":
    stats = generate_report()
    
    print("="*80)
    print("📊 快速统计")
    print("="*80)
    print(f"总计: {stats['total']} 场")
    print(f"成功: {stats['success']} 场 ({stats['success']/stats['total']*100:.1f}%)")
    print(f"熔断: {stats['meltdown']} 场 ({stats['meltdown']/stats['total']*100:.1f}%)")
    print(f"高置信度: {stats['high_conf']} 场")
    print("="*80)
