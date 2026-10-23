#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试推荐记录和审查系统

验证所有功能是否正常工作
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_recommendation_tracking():
    """测试推荐记录功能"""
    print("=" * 80)
    print("🧪 测试1: 推荐记录功能")
    print("=" * 80)
    
    try:
        from recommendation_tracker import tracker
        from recommendation.x1_json_recommender import X1JSONRecommender
        
        # 查找一个测试文件
        test_file = "data/2025/11/25/2025-11-25_欧联U19_曼彻斯特城U19_vs_勒沃库森U19_2300.json"
        
        if not Path(test_file).exists():
            print(f"⚠️ 测试文件不存在: {test_file}")
            return False
        
        # 生成推荐
        recommender = X1JSONRecommender()
        result = recommender.recommend(test_file)
        
        if result.get('meltdown'):
            print(f"⚠️ 推荐熔断: {result['meltdown']}")
            return False
        
        # 记录推荐
        result['json_file_path'] = test_file
        rec_id = tracker.record_recommendation(result)
        
        print(f"✅ 推荐已记录 ID={rec_id}")
        print(f"   比赛: {result['match_info']['home']} vs {result['match_info']['away']}")
        print(f"   推荐: {result['recommendation']['direction']}")
        print(f"   置信度: {result['recommendation']['confidence_pct']}")
        print()
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 测试失败: {e}")
        return False


def test_review_system():
    """测试审查系统"""
    print("=" * 80)
    print("🧪 测试2: 审查系统")
    print("=" * 80)
    
    try:
        from recommendation_tracker import tracker
        
        # 查看待审查列表
        pending = tracker.get_pending_reviews()
        print(f"📋 待审查推荐: {len(pending)}条")
        
        if pending:
            print(f"\n前5条:")
            for i, rec in enumerate(pending[:5], 1):
                print(f"  {i}. {rec['home_team']} vs {rec['away_team']}")
                print(f"     推荐: {rec['recommendation']}, 置信度: {rec['confidence']}")
                print(f"     比赛日期: {rec['match_date']}")
        
        print()
        
        # 测试审查（使用前一天）
        test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"🔍 测试审查日期: {test_date}")
        
        result = tracker.review_date(test_date)
        
        if result.get('total', 0) > 0:
            print(f"✅ 审查完成:")
            print(f"   总计: {result['total']}")
            print(f"   已审查: {result['reviewed']}")
            print(f"   正确: {result['correct']}")
            print(f"   错误: {result['wrong']}")
            print(f"   准确率: {result['accuracy']:.1f}%")
        else:
            print(f"⚠️ {test_date} 没有推荐需要审查")
        
        print()
        return True
        
    except Exception as e:
        logger.exception(f"❌ 测试失败: {e}")
        return False


def test_statistics():
    """测试统计功能"""
    print("=" * 80)
    print("🧪 测试3: 统计功能")
    print("=" * 80)
    
    try:
        from recommendation_tracker import tracker
        
        stats = tracker.get_statistics()
        
        print(f"📊 总体统计:")
        print(f"   总推荐数: {stats['total']}")
        print(f"   已审查: {stats['reviewed']}")
        print(f"   正确: {stats['correct']}")
        print(f"   错误: {stats['wrong']}")
        print(f"   准确率: {stats['accuracy']:.1f}%")
        print()
        
        print(f"📈 按置信度统计:")
        for level in ['high', 'mid', 'low']:
            level_stats = stats['by_confidence'][level]
            if level_stats['total'] > 0:
                print(f"   {level}: {level_stats['accuracy']:.1f}% ({level_stats['total']}场)")
        
        print()
        
        # 查看最近审查
        reviews = tracker.get_recent_reviews(7)
        if reviews:
            print(f"📅 最近7天审查:")
            for review in reviews:
                print(f"   {review['review_date']}: {review['accuracy']:.1f}% ({review['reviewed']}场)")
        
        print()
        return True
        
    except Exception as e:
        logger.exception(f"❌ 测试失败: {e}")
        return False


def test_visualizer():
    """测试可视化"""
    print("=" * 80)
    print("🧪 测试4: 可视化报告")
    print("=" * 80)
    
    try:
        from daily_review_visualizer import generate_daily_report
        
        # 使用测试数据
        test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
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
        
        print(f"🎨 生成测试报告: {test_date}")
        report_path = generate_daily_report(test_date, test_result)
        
        print(f"✅ 报告已生成: {report_path}")
        
        # 检查文件是否存在
        if Path(report_path).exists():
            print(f"✅ HTML文件已创建")
            
            # 检查图表
            report_dir = Path(report_path).parent
            charts = list(report_dir.glob('*.png'))
            print(f"✅ 生成了 {len(charts)} 张图表")
            for chart in charts:
                print(f"   - {chart.name}")
        else:
            print(f"⚠️ 报告文件不存在")
        
        print()
        return True
        
    except Exception as e:
        logger.exception(f"❌ 测试失败: {e}")
        return False


def test_api():
    """测试API接口"""
    print("=" * 80)
    print("🧪 测试5: API接口")
    print("=" * 80)
    
    try:
        import requests
        
        base_url = "http://127.0.0.1:5002"
        
        # 测试统计接口
        print("📡 测试 GET /api/x1/stats")
        response = requests.get(f"{base_url}/api/x1/stats", timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print(f"✅ 统计接口正常")
                live_stats = result['stats'].get('live', {})
                print(f"   实时统计: {live_stats.get('total', 0)}条推荐")
            else:
                print(f"⚠️ 接口返回失败")
        else:
            print(f"❌ 接口返回错误: {response.status_code}")
        
        print()
        
        # 测试历史接口
        print("📡 测试 GET /api/x1/review/history")
        response = requests.get(f"{base_url}/api/x1/review/history?days=7", timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print(f"✅ 历史接口正常")
                print(f"   返回 {len(result['reviews'])} 条历史")
            else:
                print(f"⚠️ 接口返回失败")
        else:
            print(f"❌ 接口返回错误: {response.status_code}")
        
        print()
        return True
        
    except requests.exceptions.ConnectionError:
        print("⚠️ 服务器未运行，跳过API测试")
        print("   请先启动服务: python app.py")
        print()
        return None
    except Exception as e:
        logger.exception(f"❌ 测试失败: {e}")
        return False


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "推荐记录和审查系统测试" + " " * 35 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    results = {}
    
    # 运行测试
    results['tracking'] = test_recommendation_tracking()
    results['review'] = test_review_system()
    results['statistics'] = test_statistics()
    results['visualizer'] = test_visualizer()
    results['api'] = test_api()
    
    # 总结
    print("=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for name, result in results.items():
        if result is True:
            status = "✅ 通过"
        elif result is False:
            status = "❌ 失败"
        else:
            status = "⏭️ 跳过"
        
        print(f"  {name:15s}: {status}")
    
    print()
    print(f"总计: {passed}/{len(results)} 通过")
    if skipped > 0:
        print(f"跳过: {skipped} 项")
    
    print("=" * 80)
    
    if failed == 0:
        print("✅ 所有测试通过！系统运行正常")
    else:
        print(f"⚠️ {failed} 个测试失败，请检查日志")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
