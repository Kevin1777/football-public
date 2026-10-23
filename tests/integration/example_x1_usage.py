#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1 JSON推荐模型 - 使用示例

展示如何在实际项目中使用X1推荐引擎
"""

from pathlib import Path
from recommendation.x1_json_recommender import X1JSONRecommender


def example_1_basic_usage():
    """示例1: 基础使用 - 推荐单个比赛"""
    print("=" * 80)
    print("示例1: 基础使用")
    print("=" * 80)
    
    recommender = X1JSONRecommender()
    
    # 指定比赛JSON文件路径
    json_path = "data/2025/11/25/2025-11-25_欧联U19_曼彻斯特城U19_vs_勒沃库森U19_2300.json"
    
    # 生成推荐
    result = recommender.recommend(json_path)
    
    # 提取推荐结果
    rec = result.get('recommendation', {})
    
    if rec.get('direction') != 'none':
        print(f"✅ 推荐成功!")
        print(f"   方向: {rec['direction']}")
        print(f"   盘口: {rec['handicap']}")
        print(f"   置信度: {rec['confidence_pct']}")
        print(f"   理由: {rec['reason']}")
    else:
        print(f"❌ 不推荐: {result.get('meltdown', {}).get('reason', '未知原因')}")
    
    print()


def example_2_filter_high_confidence():
    """示例2: 筛选高置信度推荐"""
    print("=" * 80)
    print("示例2: 筛选高置信度推荐 (置信度 >= 0.85)")
    print("=" * 80)
    
    recommender = X1JSONRecommender()
    data_dir = Path("data/2025/11/25")
    
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    high_confidence_matches = []
    
    # 遍历所有比赛文件
    for json_file in data_dir.glob("2025-*.json"):
        result = recommender.recommend(str(json_file))
        rec = result.get('recommendation', {})
        
        # 只保留高置信度推荐
        if rec.get('confidence', 0) >= 0.85 and rec.get('direction') != 'none':
            high_confidence_matches.append({
                'file': json_file.name,
                'match': result.get('match_info', {}),
                'recommendation': rec
            })
    
    # 输出结果
    print(f"找到 {len(high_confidence_matches)} 个高置信度推荐:\n")
    
    for i, item in enumerate(high_confidence_matches, 1):
        match = item['match']
        rec = item['recommendation']
        
        print(f"{i}. {match.get('home', 'N/A')} vs {match.get('away', 'N/A')}")
        print(f"   联赛: {match.get('league', 'N/A')}")
        print(f"   推荐: {rec['handicap']}")
        print(f"   置信度: {rec['confidence_pct']}")
        print(f"   理由: {rec['reason']}")
        print()


def example_3_risk_analysis():
    """示例3: 风控分析 - 识别高风险比赛"""
    print("=" * 80)
    print("示例3: 风控分析 - 识别高风险比赛")
    print("=" * 80)
    
    recommender = X1JSONRecommender()
    data_dir = Path("data/2025/11/25")
    
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    risk_matches = []
    
    # 遍历所有比赛文件
    for json_file in data_dir.glob("2025-*.json"):
        result = recommender.recommend(str(json_file))
        risk_control = result.get('risk_control', {})
        
        # 检查是否有风控触发
        risk_flags = [key for key, value in risk_control.items() 
                      if value and key != 'messages']
        
        if risk_flags:
            risk_matches.append({
                'file': json_file.name,
                'match': result.get('match_info', {}),
                'risk_flags': risk_flags,
                'messages': risk_control.get('messages', [])
            })
    
    # 输出结果
    print(f"发现 {len(risk_matches)} 个风控触发的比赛:\n")
    
    for i, item in enumerate(risk_matches, 1):
        match = item['match']
        
        print(f"{i}. {match.get('home', 'N/A')} vs {match.get('away', 'N/A')}")
        print(f"   触发风控: {', '.join(item['risk_flags'])}")
        for msg in item['messages']:
            print(f"   - {msg}")
        print()


def example_4_sbre_detection():
    """示例4: SBRE反解检测"""
    print("=" * 80)
    print("示例4: SBRE反解检测 - 识别诱导盘")
    print("=" * 80)
    
    recommender = X1JSONRecommender()
    data_dir = Path("data/2025/11/25")
    
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    sbre_matches = []
    
    # 遍历所有比赛文件
    for json_file in data_dir.glob("2025-*.json"):
        result = recommender.recommend(str(json_file))
        sbre = result.get('sbre', {})
        
        # 检查SBRE是否触发
        if sbre.get('triggered'):
            sbre_matches.append({
                'file': json_file.name,
                'match': result.get('match_info', {}),
                'sbre': sbre,
                'funding_level': result.get('funding_level', {})
            })
    
    # 输出结果
    print(f"发现 {len(sbre_matches)} 个SBRE反解触发的比赛:\n")
    
    for i, item in enumerate(sbre_matches, 1):
        match = item['match']
        sbre = item['sbre']
        funding = item['funding_level']
        
        print(f"{i}. {match.get('home', 'N/A')} vs {match.get('away', 'N/A')}")
        print(f"   资金等级: {funding.get('level', 'N/A')}")
        print(f"   反解方向: {sbre['direction']}")
        print(f"   置信度: {sbre['confidence']:.2f}")
        print(f"   理由: {sbre['reason']}")
        print()


def example_5_custom_filter():
    """示例5: 自定义筛选条件"""
    print("=" * 80)
    print("示例5: 自定义筛选 - 主队强热 + 顺势结构 + 低风险")
    print("=" * 80)
    
    recommender = X1JSONRecommender()
    data_dir = Path("data/2025/11/25")
    
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    filtered_matches = []
    
    # 遍历所有比赛文件
    for json_file in data_dir.glob("2025-*.json"):
        result = recommender.recommend(str(json_file))
        
        scores = result.get('scores', {})
        flm = scores.get('FLM', {})
        spm = scores.get('SPM', {})
        dpi = scores.get('DPI', {})
        rec = result.get('recommendation', {})
        
        # 自定义筛选条件
        if (flm.get('level') == '强热支持' and
            spm.get('structure') == '顺势结构' and
            dpi.get('risk_level') == '低风险' and
            rec.get('direction') == 'home'):
            
            filtered_matches.append({
                'file': json_file.name,
                'match': result.get('match_info', {}),
                'scores': scores,
                'recommendation': rec
            })
    
    # 输出结果
    print(f"找到 {len(filtered_matches)} 个符合条件的比赛:\n")
    
    for i, item in enumerate(filtered_matches, 1):
        match = item['match']
        rec = item['recommendation']
        scores = item['scores']
        
        print(f"{i}. {match.get('home', 'N/A')} vs {match.get('away', 'N/A')}")
        print(f"   推荐: {rec['handicap']}")
        print(f"   置信度: {rec['confidence_pct']}")
        print(f"   FLM: {scores['FLM']['level']} ({scores['FLM']['home_pct']}%)")
        print(f"   SPM: {scores['SPM']['structure']}")
        print(f"   DPI: {scores['DPI']['risk_level']}")
        print()


def example_6_export_summary():
    """示例6: 导出推荐摘要"""
    print("=" * 80)
    print("示例6: 导出推荐摘要到CSV")
    print("=" * 80)
    
    import csv
    from pathlib import Path
    
    recommender = X1JSONRecommender()
    data_dir = Path("data/2025/11/25")
    
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    # 收集所有推荐结果
    results = []
    
    for json_file in data_dir.glob("2025-*.json"):
        result = recommender.recommend(str(json_file))
        
        match_info = result.get('match_info', {})
        rec = result.get('recommendation', {})
        scores = result.get('scores', {})
        funding = result.get('funding_level', {})
        
        results.append({
            'home': match_info.get('home', 'N/A'),
            'away': match_info.get('away', 'N/A'),
            'league': match_info.get('league', 'N/A'),
            'direction': rec.get('direction', 'none'),
            'handicap': rec.get('handicap', 'N/A'),
            'confidence': rec.get('confidence', 0),
            'funding_level': funding.get('level', 'N/A'),
            'flm_level': scores.get('FLM', {}).get('level', 'N/A'),
            'spm_structure': scores.get('SPM', {}).get('structure', 'N/A'),
            'dpi_risk': scores.get('DPI', {}).get('risk_level', 'N/A')
        })
    
    # 导出到CSV
    output_file = "x1_recommendations_summary.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['home', 'away', 'league', 'direction', 'handicap', 
                      'confidence', 'funding_level', 'flm_level', 
                      'spm_structure', 'dpi_risk']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✅ 成功导出 {len(results)} 条记录到 {output_file}")
    print()


def main():
    """主函数 - 运行所有示例"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "X1 JSON推荐模型 - 使用示例" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    examples = [
        ("基础使用", example_1_basic_usage),
        ("筛选高置信度推荐", example_2_filter_high_confidence),
        ("风控分析", example_3_risk_analysis),
        ("SBRE反解检测", example_4_sbre_detection),
        ("自定义筛选条件", example_5_custom_filter),
        ("导出推荐摘要", example_6_export_summary)
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{'─' * 80}")
        print(f"运行示例 {i}: {name}")
        print('─' * 80 + "\n")
        
        try:
            func()
        except Exception as e:
            print(f"❌ 示例执行失败: {e}")
        
        input("\n按Enter键继续下一个示例...")
    
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "所有示例运行完毕" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")


if __name__ == "__main__":
    # 运行所有示例
    main()
    
    # 或者单独运行某个示例
    # example_1_basic_usage()
    # example_2_filter_high_confidence()
    # example_3_risk_analysis()
    # example_4_sbre_detection()
    # example_5_custom_filter()
    # example_6_export_summary()
