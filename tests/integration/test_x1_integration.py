#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试X1 JSON推荐模型集成

测试所有新增的API接口
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5002"


def test_x1_recommend():
    """测试单个推荐接口"""
    print("=" * 80)
    print("🧪 测试1: 单个推荐接口")
    print("=" * 80)
    
    # 测试数据
    data = {
        "json_path": "data/2025/11/25/2025-11-25_欧联U19_曼彻斯特城U19_vs_勒沃库森U19_2300.json"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/x1/recommend", json=data)
        result = response.json()
        
        if result['success']:
            print("✅ 请求成功！")
            print()
            print(f"比赛: {result['match_info']['home']} vs {result['match_info']['away']}")
            print(f"联赛: {result['match_info']['league']}")
            print()
            
            rec = result['recommendation']
            print(f"📊 推荐结果:")
            print(f"   方向: {rec['direction']}")
            print(f"   盘口: {rec['handicap']}")
            print(f"   置信度: {rec['confidence_pct']}")
            print(f"   理由: {rec['reason']}")
            print()
            
            print(f"💰 资金等级: {result['funding_level']['level']}")
            print(f"   总成交量: {result['funding_level']['total_volume']:,}")
            print()
            
            scores = result['scores']
            print(f"📈 评分:")
            print(f"   FLM: {scores['FLM']['level']} (置信度: {scores['FLM']['confidence']:.2f})")
            print(f"   SPM: {scores['SPM']['structure']} (置信度: {scores['SPM']['confidence']:.2f})")
            print(f"   DPI: {scores['DPI']['risk_level']} (压强: {scores['DPI']['pressure_index']})")
            print()
        else:
            print(f"❌ 请求失败: {result.get('error', '未知错误')}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    print()


def test_batch_recommend():
    """测试批量推荐接口"""
    print("=" * 80)
    print("🧪 测试2: 批量推荐接口")
    print("=" * 80)
    
    data = {
        "date": "2025-11-25",
        "min_confidence": 0.85
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/x1/batch_recommend", json=data)
        result = response.json()
        
        if result['success']:
            print(f"✅ 请求成功！")
            print(f"   日期: {result['date']}")
            print(f"   找到 {result['total']} 个高置信度推荐")
            print()
            
            for i, item in enumerate(result['recommendations'][:5], 1):
                print(f"{i}. {item['match']}")
                print(f"   联赛: {item['league']}")
                rec = item['recommendation']
                print(f"   推荐: {rec['handicap']}")
                print(f"   置信度: {rec['confidence_pct']}")
                print()
        else:
            print(f"❌ 请求失败: {result.get('error', '未知错误')}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    print()


def test_stats():
    """测试统计信息接口"""
    print("=" * 80)
    print("🧪 测试3: 统计信息接口")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/x1/stats")
        result = response.json()
        
        if result['success']:
            print("✅ 请求成功！")
            print()
            
            stats = result['stats']
            print(f"📊 X1推荐模型统计:")
            print(f"   版本: {stats['version']}")
            print(f"   整体准确率: {stats['total_accuracy']}")
            print(f"   高置信度准确率: {stats['high_confidence_accuracy']}")
            print(f"   测试样本数: {stats['total_tested']}")
            print()
            
            print(f"🏆 Top联赛表现:")
            for i, league in enumerate(stats['top_leagues'][:5], 1):
                print(f"   {i}. {league['league']:15s} - {league['accuracy']:.1f}% ({league['samples']}场)")
            print()
            
            print(f"💡 推荐策略:")
            for name, strategy in stats['recommendation_strategy'].items():
                print(f"   {name}:")
                print(f"      最小置信度: {strategy['min_confidence']}")
                print(f"      预期准确率: {strategy['expected_accuracy']}")
                print(f"      说明: {strategy['description']}")
                print()
        else:
            print(f"❌ 请求失败: {result.get('error', '未知错误')}")
    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    
    print()


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "X1 JSON推荐模型集成测试" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    print("⚠️  请确保服务器正在运行: python app.py")
    print()
    
    input("按Enter键开始测试...")
    print()
    
    # 运行测试
    test_x1_recommend()
    test_batch_recommend()
    test_stats()
    
    print("=" * 80)
    print("✅ 所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
