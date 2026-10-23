#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速批量回测脚本 - 自动获取完场比赛并回测
适用场景：命令行快速测试，查看收益率

作者：AI System
日期：2025-11-22
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict


class QuickBatchTester:
    """快速批量回测工具"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        """初始化"""
        self.base_url = base_url
    
    def get_finished_matches(self, date: str, filter_by_handicap: bool = True) -> List[Dict]:
        """
        获取指定日期的完场比赛
        
        Args:
            date: 日期字符串 (YYYY-MM-DD)
            filter_by_handicap: 是否只返回有盘口的比赛
            
        Returns:
            比赛列表
        """
        print(f"\n{'='*80}")
        print(f"📅 获取 {date} 的完场比赛...")
        print(f"{'='*80}")
        
        params = {
            'date': date,
            'filter_by_handicap': '1' if filter_by_handicap else '0'
        }
        
        response = requests.get(
            f"{self.base_url}/api/bifaw/finished_matches",
            params=params
        )
        
        if response.status_code != 200:
            print(f"❌ 获取比赛失败: HTTP {response.status_code}")
            return []
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ 获取比赛失败: {data.get('message', '未知错误')}")
            return []
        
        matches = data.get('matches', [])
        print(f"✅ 找到 {len(matches)} 场完场比赛")
        
        return matches
    
    def batch_backtest(self, matches: List[Dict]) -> Dict:
        """
        批量回测
        
        Args:
            matches: 比赛列表
            
        Returns:
            回测结果
        """
        if not matches:
            print("⚠️  没有可回测的比赛")
            return {}
        
        print(f"\n{'='*80}")
        print(f"🚀 开始批量回测 {len(matches)} 场比赛...")
        print(f"{'='*80}\n")
        
        response = requests.post(
            f"{self.base_url}/api/backtest/batch",
            json={"matches": matches},
            timeout=300  # 5分钟超时
        )
        
        if response.status_code != 200:
            print(f"❌ 回测失败: HTTP {response.status_code}")
            return {}
        
        result = response.json()
        
        if not result.get('success'):
            print(f"❌ 回测失败: {result.get('message', '未知错误')}")
            return {}
        
        return result
    
    def print_results(self, result: Dict):
        """打印回测结果"""
        if not result:
            return
        
        stats = result.get('statistics', {})
        
        print(f"\n{'='*80}")
        print(f"📊 回测结果统计")
        print(f"{'='*80}\n")
        
        # 基本统计
        print(f"📋 总场次: {stats.get('total', 0)}")
        print(f"   推荐场次: {stats.get('recommended', 0)}")
        print(f"   未推荐: {stats.get('no_bet', 0)}")
        
        recommended = stats.get('recommended', 0)
        if recommended == 0:
            print("\n⚠️  系统未推荐任何比赛下注")
            return
        
        # 结果分布
        print(f"\n🎯 推荐结果分布:")
        print(f"   全赢: {stats.get('win', 0)} 场")
        print(f"   半赢: {stats.get('half_win', 0)} 场")
        print(f"   走水: {stats.get('draw', 0)} 场")
        print(f"   半输: {stats.get('half_lose', 0)} 场")
        print(f"   全输: {stats.get('lose', 0)} 场")
        
        # 关键指标
        win_rate = stats.get('win_rate', 0)
        total_profit = stats.get('total_profit', 0)
        roi = stats.get('roi', 0)
        
        print(f"\n💰 关键指标:")
        print(f"   胜率: {win_rate:.2f}%")
        print(f"   总盈亏: {total_profit:+.2f} 单位")
        print(f"   ROI: {roi:+.2f}%")
        
        # 评价
        print(f"\n🎓 性能评价:")
        if roi > 10:
            print(f"   ⭐⭐⭐ 非常优秀！ROI超过10%")
        elif roi > 5:
            print(f"   ⭐⭐ 良好！ROI在5-10%之间")
        elif roi > 0:
            print(f"   ⭐ 一般，ROI为正但需要提高")
        else:
            print(f"   ⚠️  亏损状态，需要优化策略")
        
        if win_rate > 60:
            print(f"   ✅ 胜率优秀（>60%）")
        elif win_rate > 50:
            print(f"   ✓ 胜率良好（50-60%）")
        else:
            print(f"   ⚠️  胜率偏低（<50%），需要优化")
        
        print(f"\n{'='*80}\n")
    
    def save_detailed_results(self, result: Dict, filename: str = None):
        """保存详细结果到JSON文件"""
        if not result:
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 详细结果已保存: {filename}")
    
    def test_single_date(self, date: str):
        """测试单个日期"""
        # 1. 获取完场比赛
        matches = self.get_finished_matches(date)
        
        if not matches:
            return
        
        # 2. 批量回测
        result = self.batch_backtest(matches)
        
        # 3. 打印结果
        self.print_results(result)
        
        # 4. 保存结果
        self.save_detailed_results(result)
    
    def test_date_range(self, days: int = 7):
        """测试最近N天"""
        print(f"\n{'='*80}")
        print(f"📅 测试最近 {days} 天的完场比赛")
        print(f"{'='*80}\n")
        
        all_stats = {
            'total_matches': 0,
            'total_recommended': 0,
            'total_win': 0,
            'total_profit': 0.0,
            'daily_results': []
        }
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i+1)).strftime("%Y-%m-%d")
            
            # 获取完场比赛
            matches = self.get_finished_matches(date)
            
            if not matches:
                continue
            
            # 批量回测
            result = self.batch_backtest(matches)
            
            if result.get('success'):
                stats = result.get('statistics', {})
                
                all_stats['total_matches'] += stats.get('total', 0)
                all_stats['total_recommended'] += stats.get('recommended', 0)
                all_stats['total_win'] += stats.get('win', 0) + stats.get('half_win', 0)
                all_stats['total_profit'] += stats.get('total_profit', 0)
                all_stats['daily_results'].append({
                    'date': date,
                    'stats': stats
                })
                
                print(f"\n📅 {date}: 推荐 {stats.get('recommended', 0)} 场, ROI {stats.get('roi', 0):+.2f}%")
        
        # 打印汇总结果
        print(f"\n{'='*80}")
        print(f"📊 汇总结果（最近{days}天）")
        print(f"{'='*80}\n")
        
        print(f"总测试场次: {all_stats['total_matches']}")
        print(f"总推荐场次: {all_stats['total_recommended']}")
        
        if all_stats['total_recommended'] > 0:
            overall_win_rate = (all_stats['total_win'] / all_stats['total_recommended']) * 100
            overall_roi = (all_stats['total_profit'] / all_stats['total_recommended']) * 100
            
            print(f"总胜率: {overall_win_rate:.2f}%")
            print(f"总盈亏: {all_stats['total_profit']:+.2f} 单位")
            print(f"总ROI: {overall_roi:+.2f}%")
        
        print(f"\n{'='*80}\n")
        
        # 保存汇总结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_summary_{days}days_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_stats, f, indent=2, ensure_ascii=False)
        print(f"💾 汇总结果已保存: {filename}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='快速批量回测工具')
    parser.add_argument('--date', type=str, help='测试日期 (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=7, help='测试最近N天 (默认7天)')
    parser.add_argument('--url', type=str, default='http://127.0.0.1:5001', 
                       help='服务器地址 (默认 http://127.0.0.1:5001)')
    
    args = parser.parse_args()
    
    tester = QuickBatchTester(base_url=args.url)
    
    if args.date:
        # 测试单个日期
        tester.test_single_date(args.date)
    else:
        # 测试最近N天
        tester.test_date_range(args.days)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║            🎯 快速批量回测工具 v1.0                          ║
║                                                              ║
║  功能：自动获取完场比赛数据并进行批量回测，查看收益率        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    print("使用方法:")
    print("  python quick_batch_test.py --date 2025-11-20     # 测试指定日期")
    print("  python quick_batch_test.py --days 7              # 测试最近7天")
    print("  python quick_batch_test.py                       # 默认测试最近7天")
    print()
    
    # 运行主函数
    main()
