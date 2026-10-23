#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1推荐模型 - 可视化分析

功能：
1. 准确率柱状图
2. 置信度vs准确率折线图
3. 各联赛准确率对比
4. 推荐方向准确率对比
5. 生成HTML报告
"""

import json
import re
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib
from recommendation.x1_json_recommender import X1JSONRecommender

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 用黑体或微软雅黑
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def load_backtest_results():
    """加载回测结果"""
    with open("X1_准确率回测结果.json", 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_league_from_filename(filename: str) -> str:
    """从文件名提取联赛名称"""
    # 格式: 2025-09-18_联赛名_主队_vs_客队_比分_时间.json
    pattern = r'^\d{4}-\d{2}-\d{2}_([^_]+)_'
    match = re.match(pattern, filename)
    if match:
        return match.group(1)
    return "未知"

def analyze_by_league(results):
    """按联赛分析准确率"""
    league_stats = defaultdict(lambda: {
        'total': 0,
        'correct': 0,
        'wrong': 0,
        'draw': 0
    })
    
    for result in results:
        if result['is_draw']:
            continue  # 跳过平局
        
        league = extract_league_from_filename(result['file'])
        league_stats[league]['total'] += 1
        
        if result['is_correct']:
            league_stats[league]['correct'] += 1
        else:
            league_stats[league]['wrong'] += 1
    
    # 计算准确率并排序
    league_accuracy = []
    for league, stats in league_stats.items():
        if stats['total'] >= 5:  # 至少5场比赛
            accuracy = stats['correct'] / stats['total'] * 100
            league_accuracy.append({
                'league': league,
                'accuracy': accuracy,
                'total': stats['total'],
                'correct': stats['correct'],
                'wrong': stats['wrong']
            })
    
    # 按准确率排序
    league_accuracy.sort(key=lambda x: x['accuracy'], reverse=True)
    
    return league_accuracy

def create_visualizations(stats, results):
    """创建可视化图表"""
    
    # 创建图表目录
    output_dir = Path("visualization_output")
    output_dir.mkdir(exist_ok=True)
    
    # 1. 整体准确率饼图
    plt.figure(figsize=(10, 6))
    labels = ['正确', '错误', '走盘']
    sizes = [stats['correct'], stats['wrong'], stats['draw']]
    colors = ['#4CAF50', '#F44336', '#FFC107']
    explode = (0.1, 0, 0)
    
    plt.pie(sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', shadow=True, startangle=90)
    plt.title('X1推荐模型 - 整体结果分布', fontsize=16, fontweight='bold')
    plt.axis('equal')
    plt.savefig(output_dir / '1_整体分布.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. 按置信度的准确率柱状图
    plt.figure(figsize=(12, 7))
    confidence_levels = ['高置信度\n(≥0.85)', '中置信度\n(0.60-0.85)', '低置信度\n(<0.60)']
    
    high_stats = stats['by_confidence']['high']
    mid_stats = stats['by_confidence']['mid']
    low_stats = stats['by_confidence']['low']
    
    high_acc = high_stats['correct'] / (high_stats['correct'] + high_stats['wrong']) * 100 if (high_stats['correct'] + high_stats['wrong']) > 0 else 0
    mid_acc = mid_stats['correct'] / (mid_stats['correct'] + mid_stats['wrong']) * 100 if (mid_stats['correct'] + mid_stats['wrong']) > 0 else 0
    low_acc = low_stats['correct'] / (low_stats['correct'] + low_stats['wrong']) * 100 if (low_stats['correct'] + low_stats['wrong']) > 0 else 0
    
    accuracies = [high_acc, mid_acc, low_acc]
    colors_bar = ['#4CAF50', '#FFC107', '#F44336']
    
    bars = plt.bar(confidence_levels, accuracies, color=colors_bar, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    # 添加数值标签
    for i, (bar, acc) in enumerate(zip(bars, accuracies)):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{acc:.1f}%\n({[high_stats, mid_stats, low_stats][i]["total"]}场)',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    plt.ylabel('准确率 (%)', fontsize=14)
    plt.title('X1推荐模型 - 不同置信度准确率对比', fontsize=16, fontweight='bold')
    plt.ylim(0, 100)
    plt.grid(axis='y', alpha=0.3)
    plt.savefig(output_dir / '2_置信度准确率对比.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. 推荐方向准确率对比
    plt.figure(figsize=(10, 7))
    
    home_stats = stats['by_direction']['home']
    away_stats = stats['by_direction']['away']
    
    home_acc = home_stats['correct'] / (home_stats['correct'] + home_stats['wrong']) * 100
    away_acc = away_stats['correct'] / (away_stats['correct'] + away_stats['wrong']) * 100
    
    directions = ['主队推荐', '客队推荐']
    accuracies = [home_acc, away_acc]
    colors_dir = ['#2196F3', '#FF9800']
    
    bars = plt.bar(directions, accuracies, color=colors_dir, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    for bar, acc, stat in zip(bars, accuracies, [home_stats, away_stats]):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{acc:.1f}%\n({stat["total"]}场)',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    plt.ylabel('准确率 (%)', fontsize=14)
    plt.title('X1推荐模型 - 推荐方向准确率对比', fontsize=16, fontweight='bold')
    plt.ylim(0, 100)
    plt.grid(axis='y', alpha=0.3)
    plt.savefig(output_dir / '3_推荐方向对比.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. 各联赛准确率对比（Top 20）
    league_accuracy = analyze_by_league(results)
    
    if league_accuracy:
        top_20 = league_accuracy[:20]
        
        plt.figure(figsize=(14, 10))
        leagues = [item['league'] for item in top_20]
        accuracies = [item['accuracy'] for item in top_20]
        totals = [item['total'] for item in top_20]
        
        # 根据准确率设置颜色
        colors_league = ['#4CAF50' if acc >= 80 else '#FFC107' if acc >= 70 else '#F44336' for acc in accuracies]
        
        bars = plt.barh(leagues, accuracies, color=colors_league, alpha=0.8, edgecolor='black', linewidth=1)
        
        # 添加数值标签
        for i, (bar, acc, total) in enumerate(zip(bars, accuracies, totals)):
            width = bar.get_width()
            plt.text(width, bar.get_y() + bar.get_height()/2.,
                    f' {acc:.1f}% ({total}场)',
                    ha='left', va='center', fontsize=10)
        
        plt.xlabel('准确率 (%)', fontsize=12)
        plt.title('X1推荐模型 - Top 20联赛准确率排行', fontsize=16, fontweight='bold')
        plt.xlim(0, 100)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / '4_联赛准确率排行.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 5. 联赛准确率分布直方图
        plt.figure(figsize=(12, 7))
        all_accuracies = [item['accuracy'] for item in league_accuracy]
        
        plt.hist(all_accuracies, bins=15, color='#2196F3', alpha=0.7, edgecolor='black', linewidth=1.5)
        plt.axvline(x=77.1, color='red', linestyle='--', linewidth=2, label='整体准确率 (77.1%)')
        plt.axvline(x=83.6, color='green', linestyle='--', linewidth=2, label='高置信度 (83.6%)')
        
        plt.xlabel('准确率 (%)', fontsize=14)
        plt.ylabel('联赛数量', fontsize=14)
        plt.title('X1推荐模型 - 联赛准确率分布', fontsize=16, fontweight='bold')
        plt.legend(fontsize=12)
        plt.grid(axis='y', alpha=0.3)
        plt.savefig(output_dir / '5_联赛准确率分布.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 6. 置信度vs样本数对比
    plt.figure(figsize=(12, 7))
    
    conf_labels = ['高置信度', '中置信度', '低置信度']
    totals = [high_stats['total'], mid_stats['total'], low_stats['total']]
    corrects = [high_stats['correct'], mid_stats['correct'], low_stats['correct']]
    wrongs = [high_stats['wrong'], mid_stats['wrong'], low_stats['wrong']]
    
    x = range(len(conf_labels))
    width = 0.25
    
    plt.bar([i - width for i in x], totals, width, label='总数', color='#2196F3', alpha=0.8)
    plt.bar(x, corrects, width, label='正确', color='#4CAF50', alpha=0.8)
    plt.bar([i + width for i in x], wrongs, width, label='错误', color='#F44336', alpha=0.8)
    
    plt.xlabel('置信度等级', fontsize=14)
    plt.ylabel('比赛数量', fontsize=14)
    plt.title('X1推荐模型 - 置信度与结果分布', fontsize=16, fontweight='bold')
    plt.xticks(x, conf_labels)
    plt.legend(fontsize=12)
    plt.grid(axis='y', alpha=0.3)
    plt.savefig(output_dir / '6_置信度结果分布.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return league_accuracy

def generate_html_report(stats, league_accuracy):
    """生成HTML可视化报告"""
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X1推荐模型 - 可视化分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 36px;
        }}
        
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 40px;
            font-size: 16px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-card h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            opacity: 0.9;
        }}
        
        .stat-card .value {{
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-card .label {{
            font-size: 14px;
            opacity: 0.8;
        }}
        
        .chart-section {{
            margin-bottom: 50px;
        }}
        
        .chart-section h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            font-size: 24px;
        }}
        
        .chart-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .chart-container img {{
            width: 100%;
            height: auto;
            border-radius: 10px;
        }}
        
        .league-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .league-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: bold;
        }}
        
        .league-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .league-table tr:hover {{
            background: #f8f9fa;
        }}
        
        .accuracy-high {{
            color: #4CAF50;
            font-weight: bold;
        }}
        
        .accuracy-mid {{
            color: #FFC107;
            font-weight: bold;
        }}
        
        .accuracy-low {{
            color: #F44336;
            font-weight: bold;
        }}
        
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 X1推荐模型 - 可视化分析报告</h1>
        <p class="subtitle">基于1,552场历史比赛的准确率分析</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>整体准确率</h3>
                <div class="value">77.1%</div>
                <div class="label">612/794 正确</div>
            </div>
            
            <div class="stat-card">
                <h3>高置信度准确率</h3>
                <div class="value">83.6%</div>
                <div class="label">239/286 正确</div>
            </div>
            
            <div class="stat-card">
                <h3>中置信度准确率</h3>
                <div class="value">74.5%</div>
                <div class="label">373/501 正确</div>
            </div>
            
            <div class="stat-card">
                <h3>推荐覆盖率</h3>
                <div class="value">65.8%</div>
                <div class="label">1021/1552 场</div>
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📊 整体结果分布</h2>
            <div class="chart-container">
                <img src="visualization_output/1_整体分布.png" alt="整体分布">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📈 置信度准确率对比</h2>
            <div class="chart-container">
                <img src="visualization_output/2_置信度准确率对比.png" alt="置信度准确率对比">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>🎯 推荐方向准确率对比</h2>
            <div class="chart-container">
                <img src="visualization_output/3_推荐方向对比.png" alt="推荐方向对比">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>🏆 Top 20联赛准确率排行</h2>
            <div class="chart-container">
                <img src="visualization_output/4_联赛准确率排行.png" alt="联赛准确率排行">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📊 联赛准确率分布</h2>
            <div class="chart-container">
                <img src="visualization_output/5_联赛准确率分布.png" alt="联赛准确率分布">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📉 置信度与结果分布</h2>
            <div class="chart-container">
                <img src="visualization_output/6_置信度结果分布.png" alt="置信度结果分布">
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📋 联赛详细数据表</h2>
            <table class="league-table">
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>联赛</th>
                        <th>准确率</th>
                        <th>总场数</th>
                        <th>正确</th>
                        <th>错误</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for i, item in enumerate(league_accuracy[:30], 1):
        acc_class = 'accuracy-high' if item['accuracy'] >= 80 else 'accuracy-mid' if item['accuracy'] >= 70 else 'accuracy-low'
        html_content += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{item['league']}</td>
                        <td class="{acc_class}">{item['accuracy']:.1f}%</td>
                        <td>{item['total']}</td>
                        <td>{item['correct']}</td>
                        <td>{item['wrong']}</td>
                    </tr>
"""
    
    html_content += f"""
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>报告生成时间: 2025-11-25 22:40</p>
            <p>数据来源: X1 JSON推荐模型回测</p>
            <p>模型版本: X1-JSON-V1.0</p>
        </div>
    </div>
</body>
</html>
"""
    
    with open("X1_可视化报告.html", 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    print("=" * 80)
    print("🎨 X1推荐模型 - 可视化分析")
    print("=" * 80)
    print()
    
    # 加载数据
    print("📂 加载回测数据...")
    data = load_backtest_results()
    stats = data['statistics']
    results = data['results']
    
    print(f"✅ 加载完成！共 {len(results)} 条记录")
    print()
    
    # 生成图表
    print("📊 生成可视化图表...")
    league_accuracy = create_visualizations(stats, results)
    print(f"✅ 图表生成完成！保存在 visualization_output/ 目录")
    print()
    
    # 生成HTML报告
    print("📄 生成HTML报告...")
    generate_html_report(stats, league_accuracy)
    print("✅ HTML报告生成完成: X1_可视化报告.html")
    print()
    
    # 显示联赛统计
    print("=" * 80)
    print("🏆 联赛准确率 Top 10")
    print("=" * 80)
    for i, item in enumerate(league_accuracy[:10], 1):
        print(f"{i:2d}. {item['league']:20s} - {item['accuracy']:5.1f}% ({item['total']:3d}场)")
    
    print()
    print("=" * 80)
    print("✅ 所有可视化分析完成！")
    print()
    print("📁 生成的文件:")
    print("   - visualization_output/*.png (6张图表)")
    print("   - X1_可视化报告.html (完整HTML报告)")
    print()
    print("💡 使用浏览器打开 X1_可视化报告.html 查看完整报告")
    print("=" * 80)

if __name__ == "__main__":
    main()
