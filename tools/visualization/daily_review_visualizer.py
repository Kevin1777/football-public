#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日审查可视化报告生成器

功能：
1. 生成准确率图表
2. 生成HTML报告
3. 生成趋势分析
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
import matplotlib.pyplot as plt
import matplotlib
from recommendation_tracker import tracker

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

logger = logging.getLogger(__name__)


def generate_daily_report(date: str, review_result: Dict) -> str:
    """
    生成每日审查报告
    
    Args:
        date: 日期
        review_result: 审查结果
        
    Returns:
        报告文件路径
    """
    logger.info(f"📊 生成 {date} 的审查报告...")
    
    # 创建报告目录
    report_dir = Path("daily_reports") / date.replace('-', '')
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 生成图表
    chart_paths = _generate_charts(date, review_result, report_dir)
    
    # 2. 生成HTML报告
    html_path = _generate_html_report(date, review_result, chart_paths, report_dir)
    
    logger.info(f"✅ 报告已生成: {html_path}")
    
    return str(html_path)


def _generate_charts(date: str, result: Dict, output_dir: Path) -> Dict:
    """生成图表"""
    chart_paths = {}
    
    # 1. 准确率饼图
    plt.figure(figsize=(10, 6))
    labels = ['正确', '错误', '走盘']
    sizes = [result['correct'], result['wrong'], result['draw']]
    colors = ['#4CAF50', '#F44336', '#FFC107']
    explode = (0.1, 0, 0)
    
    plt.pie(sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', shadow=True, startangle=90)
    plt.title(f'{date} 推荐结果分布', fontsize=16, fontweight='bold')
    plt.axis('equal')
    
    pie_path = output_dir / 'accuracy_pie.png'
    plt.savefig(pie_path, dpi=300, bbox_inches='tight')
    plt.close()
    chart_paths['pie'] = pie_path
    
    # 2. 7天趋势图
    recent_reviews = tracker.get_recent_reviews(7)
    if recent_reviews:
        plt.figure(figsize=(12, 6))
        
        dates = [r['review_date'] for r in reversed(recent_reviews)]
        accuracies = [r['accuracy'] for r in reversed(recent_reviews)]
        high_conf_accs = [r.get('high_confidence_accuracy', 0) for r in reversed(recent_reviews)]
        
        plt.plot(dates, accuracies, marker='o', linewidth=2, label='整体准确率', color='#2196F3')
        plt.plot(dates, high_conf_accs, marker='s', linewidth=2, label='高置信度准确率', color='#4CAF50')
        
        plt.axhline(y=77.1, color='red', linestyle='--', alpha=0.5, label='历史整体均值 (77.1%)')
        plt.axhline(y=83.6, color='green', linestyle='--', alpha=0.5, label='历史高置信度均值 (83.6%)')
        
        plt.xlabel('日期', fontsize=12)
        plt.ylabel('准确率 (%)', fontsize=12)
        plt.title('近7天准确率趋势', fontsize=16, fontweight='bold')
        plt.xticks(rotation=45)
        plt.legend(fontsize=10)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        
        trend_path = output_dir / 'trend.png'
        plt.savefig(trend_path, dpi=300, bbox_inches='tight')
        plt.close()
        chart_paths['trend'] = trend_path
    
    # 3. 置信度对比柱状图
    stats = tracker.get_statistics()
    conf_stats = stats.get('by_confidence', {})
    
    if any(conf_stats.values()):
        plt.figure(figsize=(10, 6))
        
        levels = ['高置信度\n(≥0.85)', '中置信度\n(0.60-0.85)', '低置信度\n(<0.60)']
        accuracies = [
            conf_stats.get('high', {}).get('accuracy', 0),
            conf_stats.get('mid', {}).get('accuracy', 0),
            conf_stats.get('low', {}).get('accuracy', 0)
        ]
        totals = [
            conf_stats.get('high', {}).get('total', 0),
            conf_stats.get('mid', {}).get('total', 0),
            conf_stats.get('low', {}).get('total', 0)
        ]
        colors_bar = ['#4CAF50', '#FFC107', '#F44336']
        
        bars = plt.bar(levels, accuracies, color=colors_bar, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        for bar, acc, total in zip(bars, accuracies, totals):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{acc:.1f}%\n({total}场)',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        plt.ylabel('准确率 (%)', fontsize=12)
        plt.title('累计准确率 - 按置信度分析', fontsize=16, fontweight='bold')
        plt.ylim(0, 100)
        plt.grid(axis='y', alpha=0.3)
        
        conf_path = output_dir / 'confidence.png'
        plt.savefig(conf_path, dpi=300, bbox_inches='tight')
        plt.close()
        chart_paths['confidence'] = conf_path
    
    return chart_paths


def _generate_html_report(date: str, result: Dict, chart_paths: Dict, output_dir: Path) -> Path:
    """生成HTML报告"""
    
    stats = tracker.get_statistics()
    accuracy = result['accuracy']
    
    # 准确率评级
    if accuracy >= 85:
        rating = "🔥 优秀"
        rating_color = "#4CAF50"
    elif accuracy >= 75:
        rating = "✅ 良好"
        rating_color = "#FFC107"
    elif accuracy >= 65:
        rating = "⚠️ 一般"
        rating_color = "#FF9800"
    else:
        rating = "❌ 需改进"
        rating_color = "#F44336"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日推荐审查报告 - {date}</title>
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
            max-width: 1200px;
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
        
        .date {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
        }}
        
        .stat-card h3 {{
            font-size: 14px;
            margin-bottom: 10px;
            opacity: 0.9;
        }}
        
        .stat-card .value {{
            font-size: 42px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .rating-card {{
            background: {rating_color};
            color: white;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .rating-card h2 {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
        
        .rating-card p {{
            font-size: 24px;
            opacity: 0.9;
        }}
        
        .chart-section {{
            margin-bottom: 40px;
        }}
        
        .chart-section h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}
        
        .chart-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 10px;
        }}
        
        .summary {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 40px;
        }}
        
        .summary h2 {{
            color: #333;
            margin-bottom: 20px;
        }}
        
        .summary ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .summary li {{
            padding: 10px;
            margin-bottom: 10px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
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
        <h1>📊 每日推荐审查报告</h1>
        <p class="date">{date} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="rating-card">
            <h2>{rating}</h2>
            <p>当日准确率: {accuracy:.1f}%</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>推荐总数</h3>
                <div class="value">{result['total']}</div>
            </div>
            
            <div class="stat-card">
                <h3>已审查</h3>
                <div class="value">{result['reviewed']}</div>
            </div>
            
            <div class="stat-card">
                <h3>正确</h3>
                <div class="value">{result['correct']}</div>
            </div>
            
            <div class="stat-card">
                <h3>错误</h3>
                <div class="value">{result['wrong']}</div>
            </div>
            
            <div class="stat-card">
                <h3>走盘</h3>
                <div class="value">{result['draw']}</div>
            </div>
            
            <div class="stat-card">
                <h3>高置信度准确率</h3>
                <div class="value">{result.get('high_confidence_accuracy', 0):.1f}%</div>
            </div>
        </div>
        
        <div class="chart-section">
            <h2>📊 当日结果分布</h2>
            <div class="chart-container">
                <img src="{chart_paths.get('pie', '').name}" alt="结果分布">
            </div>
        </div>
        
        {f'''
        <div class="chart-section">
            <h2>📈 近7天准确率趋势</h2>
            <div class="chart-container">
                <img src="{chart_paths.get('trend', '').name}" alt="趋势图">
            </div>
        </div>
        ''' if 'trend' in chart_paths else ''}
        
        {f'''
        <div class="chart-section">
            <h2>📉 累计准确率 - 按置信度</h2>
            <div class="chart-container">
                <img src="{chart_paths.get('confidence', '').name}" alt="置信度对比">
            </div>
        </div>
        ''' if 'confidence' in chart_paths else ''}
        
        <div class="summary">
            <h2>💡 分析总结</h2>
            <ul>
                <li>📊 <strong>当日准确率</strong>: {accuracy:.1f}% ({result['correct']}/{result['correct'] + result['wrong']})</li>
                <li>🌟 <strong>高置信度准确率</strong>: {result.get('high_confidence_accuracy', 0):.1f}%</li>
                <li>📈 <strong>历史对比</strong>: 历史高置信度均值为83.6%</li>
                <li>🎯 <strong>累计统计</strong>: 总计{stats['reviewed']}场已审查，整体准确率{stats['accuracy']:.1f}%</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>X1 JSON推荐模型 | 版本: v1.0</p>
            <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
    
    html_path = output_dir / 'report.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_path


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # 测试
    if len(sys.argv) > 1:
        test_date = sys.argv[1]
    else:
        test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 模拟审查结果
    test_result = {
        'date': test_date,
        'total': 10,
        'reviewed': 10,
        'correct': 8,
        'wrong': 2,
        'draw': 0,
        'accuracy': 80.0,
        'high_confidence_accuracy': 85.0
    }
    
    report_path = generate_daily_report(test_date, test_result)
    print(f"✅ 报告已生成: {report_path}")
