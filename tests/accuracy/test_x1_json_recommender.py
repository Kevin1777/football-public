#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1 JSON推荐模型 - 测试脚本

功能：
1. 测试单个比赛JSON文件的推荐
2. 批量测试某个日期的所有比赛
3. 统计推荐结果分布
4. 验证模型输出格式
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from recommendation.x1_json_recommender import X1JSONRecommender

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class X1RecommenderTester:
    """X1推荐器测试工具"""
    
    def __init__(self, data_dir: str = "data"):
        self.recommender = X1JSONRecommender()
        self.data_dir = Path(data_dir)
        self.results = []
    
    def test_single_match(self, json_path: str):
        """测试单个比赛"""
        print("=" * 80)
        print("🎯 X1 JSON推荐模型 - 单个比赛测试")
        print("=" * 80)
        print(f"文件: {json_path}")
        print()
        
        result = self.recommender.recommend(json_path)
        
        # 美化输出
        self._print_result(result)
        
        return result
    
    def test_date_matches(self, date_str: str):
        """测试某一天的所有比赛"""
        print("=" * 80)
        print(f"🎯 X1 JSON推荐模型 - 批量测试 ({date_str})")
        print("=" * 80)
        print()
        
        # 构建日期路径
        year, month, day = date_str.split('-')
        date_path = self.data_dir / year / month / day
        
        if not date_path.exists():
            logger.error(f"日期路径不存在: {date_path}")
            return []
        
        # 查找所有比赛JSON文件（排除标盘指数）
        json_files = list(date_path.glob("2025-*.json"))
        
        if not json_files:
            logger.warning(f"未找到比赛文件: {date_path}")
            return []
        
        print(f"找到 {len(json_files)} 个比赛文件")
        print()
        
        results = []
        for i, json_file in enumerate(json_files, 1):
            print(f"[{i}/{len(json_files)}] 测试: {json_file.stem}")
            
            result = self.recommender.recommend(str(json_file))
            results.append({
                'file': json_file.name,
                'result': result
            })
            
            # 简要输出
            rec = result.get('recommendation', {})
            if rec.get('direction') != 'none':
                print(f"  ✅ 推荐: {rec.get('handicap', 'N/A')}")
                print(f"  📊 置信度: {rec.get('confidence_pct', 'N/A')}")
                print(f"  💡 理由: {rec.get('reason', 'N/A')}")
            else:
                meltdown = result.get('meltdown', {})
                print(f"  ❌ 熔断: {meltdown.get('type', 'N/A')} - {meltdown.get('reason', 'N/A')}")
            
            print()
        
        self.results = results
        self._print_statistics(results)
        
        return results
    
    def test_latest_matches(self, limit: int = 10):
        """测试最新的N场比赛"""
        print("=" * 80)
        print(f"🎯 X1 JSON推荐模型 - 最新{limit}场比赛测试")
        print("=" * 80)
        print()
        
        # 查找最新的JSON文件
        all_json_files = []
        for json_file in self.data_dir.rglob("2025-*.json"):
            all_json_files.append(json_file)
        
        # 按修改时间排序
        all_json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # 取前N个
        latest_files = all_json_files[:limit]
        
        if not latest_files:
            logger.warning("未找到任何比赛文件")
            return []
        
        print(f"找到 {len(latest_files)} 个最新比赛文件")
        print()
        
        results = []
        for i, json_file in enumerate(latest_files, 1):
            print(f"[{i}/{len(latest_files)}] 测试: {json_file.name}")
            
            result = self.recommender.recommend(str(json_file))
            results.append({
                'file': json_file.name,
                'result': result
            })
            
            # 简要输出
            rec = result.get('recommendation', {})
            if rec.get('direction') != 'none':
                print(f"  ✅ 推荐: {rec.get('handicap', 'N/A')}")
                print(f"  📊 置信度: {rec.get('confidence_pct', 'N/A')}")
            else:
                print(f"  ❌ 熔断")
            
            print()
        
        self.results = results
        self._print_statistics(results)
        
        return results
    
    def _print_result(self, result: Dict):
        """美化打印单个结果"""
        if 'meltdown' in result and result['meltdown']:
            print("❌ 推荐状态: 熔断")
            print(f"   类型: {result['meltdown'].get('type', 'N/A')}")
            print(f"   原因: {result['meltdown'].get('reason', 'N/A')}")
            return
        
        # 比赛信息
        match_info = result.get('match_info', {})
        print(f"🏆 比赛: {match_info.get('home', 'N/A')} vs {match_info.get('away', 'N/A')}")
        print(f"🎪 联赛: {match_info.get('league', 'N/A')}")
        print(f"⏰ 开赛: {match_info.get('kickoff', 'N/A')}")
        print()
        
        # 数据源
        data_source = result.get('data_source', {})
        print("📂 数据源:")
        for key, value in data_source.items():
            print(f"   {key}: {value}")
        print()
        
        # 资金等级
        funding = result.get('funding_level', {})
        print(f"💰 资金等级: {funding.get('level', 'N/A')} (总量: {funding.get('total_volume', 0):,})")
        print()
        
        # 评分
        scores = result.get('scores', {})
        print("📊 评分模块:")
        
        flm = scores.get('FLM', {})
        print(f"   FLM (热度前线): {flm.get('level', 'N/A')} | 置信度: {flm.get('confidence', 0):.2f}")
        print(f"       主: {flm.get('home_pct', 0)}% | 和: {flm.get('draw_pct', 0)}% | 客: {flm.get('away_pct', 0)}%")
        
        spm = scores.get('SPM', {})
        print(f"   SPM (结构承压): {spm.get('structure', 'N/A')} | 置信度: {spm.get('confidence', 0):.2f}")
        print(f"       盘口变化: {spm.get('handicap_change', 0):.2f} | 信号: {spm.get('handicap_signal', 'N/A')}")
        
        dpi = scores.get('DPI', {})
        print(f"   DPI (风险整合): {dpi.get('risk_level', 'N/A')} | 压强指数: {dpi.get('pressure_index', 0)}")
        print()
        
        # 风控
        risk_control = result.get('risk_control', {})
        risk_flags = [key for key, value in risk_control.items() if value and key != 'messages']
        if risk_flags:
            print(f"⚠️ 风控触发: {', '.join(risk_flags)}")
            for msg in risk_control.get('messages', []):
                print(f"   - {msg}")
            print()
        else:
            print("✅ 风控: 全部通过")
            print()
        
        # SBRE
        sbre = result.get('sbre', {})
        if sbre.get('triggered'):
            print(f"🔄 SBRE反解: 已触发")
            print(f"   反解方向: {sbre.get('direction', 'N/A')}")
            print(f"   置信度: {sbre.get('confidence', 0):.2f}")
            print(f"   理由: {sbre.get('reason', 'N/A')}")
            print()
        
        # 最终推荐
        rec = result.get('recommendation', {})
        print("=" * 80)
        print("🎯 最终推荐")
        print("=" * 80)
        if rec.get('direction') == 'none':
            print("❌ 不推荐（熔断或风险过高）")
        else:
            print(f"✅ 方向: {rec.get('direction', 'N/A').upper()}")
            print(f"🎲 盘口: {rec.get('handicap', 'N/A')}")
            print(f"📊 置信度: {rec.get('confidence_pct', 'N/A')}")
            print(f"💡 理由: {rec.get('reason', 'N/A')}")
        print()
        
        # 风险提示
        risk_notes = result.get('risk_notes', [])
        if risk_notes and risk_notes != ['无显著风险']:
            print("⚠️ 风险提示:")
            for note in risk_notes:
                print(f"   - {note}")
            print()
    
    def _print_statistics(self, results: List[Dict]):
        """打印统计信息"""
        print("=" * 80)
        print("📈 统计结果")
        print("=" * 80)
        
        total = len(results)
        if total == 0:
            print("无结果")
            return
        
        # 统计推荐方向
        home_count = sum(1 for r in results if r['result'].get('recommendation', {}).get('direction') == 'home')
        away_count = sum(1 for r in results if r['result'].get('recommendation', {}).get('direction') == 'away')
        none_count = sum(1 for r in results if r['result'].get('recommendation', {}).get('direction') == 'none')
        
        print(f"总计: {total} 场比赛")
        print(f"  推荐主队: {home_count} ({home_count/total*100:.1f}%)")
        print(f"  推荐客队: {away_count} ({away_count/total*100:.1f}%)")
        print(f"  不推荐: {none_count} ({none_count/total*100:.1f}%)")
        print()
        
        # 统计置信度分布
        confidences = [
            r['result'].get('recommendation', {}).get('confidence', 0)
            for r in results
            if r['result'].get('recommendation', {}).get('direction') != 'none'
        ]
        
        if confidences:
            high_conf = sum(1 for c in confidences if c >= 0.85)
            mid_conf = sum(1 for c in confidences if 0.60 <= c < 0.85)
            low_conf = sum(1 for c in confidences if c < 0.60)
            
            print("置信度分布:")
            print(f"  高置信度 (>=0.85): {high_conf}")
            print(f"  中置信度 (0.60-0.85): {mid_conf}")
            print(f"  低置信度 (<0.60): {low_conf}")
            print()
        
        # 统计风控触发
        risk_counts = {
            'SmartSafe': 0,
            'SS-Dagger': 0,
            'LVC': 0,
            'TPI': 0
        }
        
        for r in results:
            risk_control = r['result'].get('risk_control', {})
            for key in risk_counts.keys():
                if risk_control.get(key):
                    risk_counts[key] += 1
        
        print("风控触发统计:")
        for key, count in risk_counts.items():
            if count > 0:
                print(f"  {key}: {count} 次")
        print()
        
        # SBRE触发统计
        sbre_count = sum(1 for r in results if r['result'].get('sbre', {}).get('triggered'))
        if sbre_count > 0:
            print(f"SBRE反解触发: {sbre_count} 次")
            print()
    
    def export_results(self, output_file: str = "x1_test_results.json"):
        """导出测试结果"""
        if not self.results:
            logger.warning("没有结果可导出")
            return
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 结果已导出: {output_path}")


def main():
    """主测试函数"""
    import sys
    
    tester = X1RecommenderTester()
    
    if len(sys.argv) > 1:
        # 命令行参数指定测试文件
        json_path = sys.argv[1]
        tester.test_single_match(json_path)
    else:
        # 默认测试最新比赛
        print("未指定测试文件，测试最新10场比赛...")
        print()
        tester.test_latest_matches(limit=10)
        
        # 导出结果
        tester.export_results()


if __name__ == "__main__":
    main()
