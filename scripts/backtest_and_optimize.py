"""
回测分析与模型优化脚本

功能：
1. 加载所有带比分的历史数据
2. 对每场比赛生成推荐
3. 对比实际比分，计算准确率
4. 分析各项评分指标的有效性
5. 生成优化建议

使用方法：
python scripts/backtest_and_optimize.py [--output report.md]
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import pandas as pd
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.handicap_engine_x1 import HandicapRecommendationEngineX1


def load_match_data(json_file: Path) -> Optional[Dict]:
    """加载单场比赛数据"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        match_info = data.get('match_info', {})
        score = match_info.get('score')
        
        if not score:
            return None
        
        # 解析比分
        try:
            parts = score.split('-')
            home_score = int(parts[0])
            away_score = int(parts[1])
        except:
            return None
        
        # 提取trade_data
        trade_data_dict = data.get('trade_data', {})
        trade_data = pd.DataFrame(trade_data_dict.get('data', []))
        
        if trade_data.empty:
            return None
        
        return {
            'file': json_file.name,
            'match_info': match_info,
            'home_score': home_score,
            'away_score': away_score,
            'score': score,
            'trade_data': trade_data,
            'handicap_data': data.get('handicap_data', {}),
            'metadata': data.get('metadata', [])
        }
        
    except Exception as e:
        print(f"⚠️  加载失败 {json_file.name}: {e}")
        return None


def check_prediction_correct(
    recommendation: Dict,
    home_score: int,
    away_score: int,
    handicap: float
) -> Tuple[bool, str]:
    """
    检查推荐是否正确
    
    Returns:
        (是否正确, 说明)
    """
    # 🔥 修复：X1引擎返回的字段结构
    final_rec = recommendation.get('最终推荐', {})
    direction = final_rec.get('direction', '')
    should_bet = final_rec.get('should_bet', False)
    
    # 如果不应下注，视为观望
    if not should_bet or not direction:
        return None, "观望"
    
    # 计算让球结果（盘口已经是负数，如-1.5表示主队让球半）
    home_with_handicap = home_score + handicap
    
    # 判断实际结果
    if home_with_handicap > away_score:
        actual_result = "主队赢盘"
    elif home_with_handicap < away_score:
        actual_result = "客队赢盘"
    else:
        actual_result = "走盘"
    
    # 判断推荐方向
    # direction格式："主队让球"、"客队受让"、"谨慎跟随盘口"等
    
    # 🔥 修复：识别"跟随盘口"类推荐
    # "跟随盘口" = 跟随热度方向（FLM），不是跟随让球方！
    if "跟随" in direction and "盘口" in direction:
        # 获取FLM评分，判断热度支持哪一方
        flm_score = recommendation.get('评分等级', {}).get('FLM', '')
        
        if "主" in flm_score or "home" in flm_score.lower():
            # FLM支持主队
            predicted = "主队赢盘"
        elif "客" in flm_score or "away" in flm_score.lower():
            # FLM支持客队
            predicted = "客队赢盘"
        elif "均衡" in flm_score or "不明显" in flm_score:
            # 热度均衡，根据盘口判断（让球方通常是热门）
            if handicap < 0:  # 主队让球
                predicted = "主队赢盘"
            elif handicap > 0:  # 客队让球
                predicted = "客队赢盘"
            else:  # 平手盘
                predicted = "主队赢盘"  # 平手主队略占优
        else:
            # 无法判断FLM方向，按盘口判断
            if handicap < 0:
                predicted = "主队赢盘"
            elif handicap > 0:
                predicted = "客队赢盘"
            else:
                predicted = "主队赢盘"
    elif "主队" in direction and "让" in direction:
        predicted = "主队赢盘"
    elif "客队" in direction and "受让" in direction:
        predicted = "客队赢盘"
    elif "主" in direction or "home" in direction.lower():
        predicted = "主队赢盘"
    elif "客" in direction or "away" in direction.lower():
        predicted = "客队赢盘"
    else:
        return None, f"未识别方向: {direction}"
    
    is_correct = (predicted == actual_result)
    reason = f"推荐{predicted}, 实际{actual_result}, 比分{home_score}-{away_score}, 让球{handicap}"
    
    return is_correct, reason


def analyze_features(matches: List[Dict]) -> Dict:
    """分析各项特征的有效性"""
    
    features = {
        'FLM': defaultdict(lambda: {'correct': 0, 'total': 0}),
        'SPM': defaultdict(lambda: {'correct': 0, 'total': 0}),
        'DPI': defaultdict(lambda: {'correct': 0, 'total': 0}),
        'funding_level': defaultdict(lambda: {'correct': 0, 'total': 0}),
        'SBRE': {'triggered': 0, 'correct': 0, 'total': 0},
        'risk_checks': defaultdict(lambda: {'triggered': 0, 'correct': 0}),
    }
    
    for match in matches:
        rec = match.get('recommendation')
        is_correct = match.get('is_correct')
        
        if rec is None or is_correct is None:
            continue
        
        # FLM评分
        flm_score = rec.get('评分等级', {}).get('FLM', '')
        if flm_score:
            features['FLM'][flm_score]['total'] += 1
            if is_correct:
                features['FLM'][flm_score]['correct'] += 1
        
        # SPM评分
        spm_score = rec.get('评分等级', {}).get('SPM', '')
        if spm_score:
            features['SPM'][spm_score]['total'] += 1
            if is_correct:
                features['SPM'][spm_score]['correct'] += 1
        
        # DPI评分
        dpi_score = rec.get('评分等级', {}).get('DPI', '')
        
        # 🔥 调试：打印DPI值
        if len(matches) <= 10 and matches.index(match) < 3:
            print(f"[调试] 比赛{matches.index(match)+1} DPI: '{dpi_score}'")
        
        # 🔥 提取档位（A/B/C/D档）
        dpi_grade = ''
        if 'A档' in dpi_score:
            dpi_grade = 'A档'
        elif 'B档' in dpi_score:
            dpi_grade = 'B档'
        elif 'C档' in dpi_score:
            dpi_grade = 'C档'
        elif 'D档' in dpi_score:
            dpi_grade = 'D档'
        
        if dpi_grade:
            features['DPI'][dpi_grade]['total'] += 1
            if is_correct:
                features['DPI'][dpi_grade]['correct'] += 1
        
        # 资金等级
        funding_level = rec.get('资金等级', {}).get('level', '')
        if funding_level:
            features['funding_level'][funding_level]['total'] += 1
            if is_correct:
                features['funding_level'][funding_level]['correct'] += 1
        
        # SBRE机制
        sbre = rec.get('SBRE', {})
        if sbre.get('triggered'):
            features['SBRE']['triggered'] += 1
            features['SBRE']['total'] += 1
            if is_correct:
                features['SBRE']['correct'] += 1
        
        # 风控机制
        risk_control = rec.get('风控机制', {})
        for check_name, triggered in risk_control.items():
            if triggered and check_name != 'status':
                features['risk_checks'][check_name]['triggered'] += 1
                if is_correct:
                    features['risk_checks'][check_name]['correct'] += 1
    
    return features


def generate_report(matches: List[Dict], features: Dict, output_file: str):
    """生成优化报告"""
    
    total_matches = len(matches)
    with_recommendation = [m for m in matches if m.get('is_correct') is not None]
    observed = [m for m in matches if m.get('is_correct') is None and m.get('reason') == '观望']
    correct_matches = [m for m in with_recommendation if m.get('is_correct')]
    wrong_matches = [m for m in with_recommendation if not m.get('is_correct')]
    
    accuracy = len(correct_matches) / len(with_recommendation) * 100 if with_recommendation else 0
    
    report = f"""# 回测分析报告

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📊 整体统计

| 指标 | 数值 |
|-----|------|
| 总比赛数 | {total_matches} |
| 有推荐比赛 | {len(with_recommendation)} |
| 观望比赛 | {len(observed)} |
| 推荐正确 | {len(correct_matches)} |
| 推荐错误 | {len(wrong_matches)} |
| **准确率** | **{accuracy:.1f}%** |

---

## 🎯 分档准确率

### DPI风险评分

| 档位 | 推荐次数 | 正确次数 | 准确率 |
|-----|---------|---------|--------|
"""
    
    for dpi_grade in ['A档', 'B档', 'C档', 'D档']:
        grade_data = features['DPI'].get(dpi_grade, {'correct': 0, 'total': 0})
        if grade_data['total'] > 0:
            grade_acc = grade_data['correct'] / grade_data['total'] * 100
            report += f"| {dpi_grade} | {grade_data['total']} | {grade_data['correct']} | {grade_acc:.1f}% |\n"
    
    report += "\n### 资金等级\n\n| 等级 | 推荐次数 | 正确次数 | 准确率 |\n|-----|---------|---------|--------|\n"
    
    for level in ['L1', 'L2', 'L3', 'L4', 'L5']:
        level_data = features['funding_level'].get(level, {'correct': 0, 'total': 0})
        if level_data['total'] > 0:
            level_acc = level_data['correct'] / level_data['total'] * 100
            report += f"| {level} | {level_data['total']} | {level_data['correct']} | {level_acc:.1f}% |\n"
    
    report += f"\n---\n\n## 🔥 SBRE反打机制\n\n"
    
    sbre_data = features['SBRE']
    if sbre_data['triggered'] > 0:
        sbre_acc = sbre_data['correct'] / sbre_data['total'] * 100
        report += f"| 触发次数 | 正确次数 | 准确率 |\n"
        report += f"|---------|---------|--------|\n"
        report += f"| {sbre_data['triggered']} | {sbre_data['correct']} | {sbre_acc:.1f}% |\n\n"
    else:
        report += "未触发\n\n"
    
    report += f"---\n\n## ✅ 正确案例（全部{len(correct_matches)}场）\n\n"
    
    for i, match in enumerate(correct_matches, 1):
        rec = match['recommendation']
        final_rec = rec.get('最终推荐', {})
        report += f"### {i}. {match['match_info']['home']} vs {match['match_info']['away']}\n\n"
        report += f"- **比分**: {match['score']}\n"
        report += f"- **推荐**: {final_rec.get('direction', 'N/A')}\n"
        report += f"- **置信度**: {final_rec.get('confidence', 0):.1%}\n"
        report += f"- **盘口**: {match['handicap_data'].get('current_handicap_str', 'N/A')}\n"
        report += f"- **DPI**: {rec.get('评分等级', {}).get('DPI', 'N/A')}\n"
        report += f"- **FLM**: {rec.get('评分等级', {}).get('FLM', 'N/A')}\n"
        report += f"- **SPM**: {rec.get('评分等级', {}).get('SPM', 'N/A')}\n"
        report += f"- **资金等级**: {rec.get('资金等级', {}).get('level', 'N/A')}\n"
        report += f"- **SBRE**: {'触发' if rec.get('SBRE', {}).get('triggered') else '未触发'}\n\n"
    
    report += f"---\n\n## ❌ 错误案例（全部{len(wrong_matches)}场）\n\n"
    
    for i, match in enumerate(wrong_matches, 1):
        rec = match['recommendation']
        final_rec = rec.get('最终推荐', {})
        report += f"### {i}. {match['match_info']['home']} vs {match['match_info']['away']}\n\n"
        report += f"- **比分**: {match['score']}\n"
        report += f"- **推荐**: {final_rec.get('direction', 'N/A')}\n"
        report += f"- **置信度**: {final_rec.get('confidence', 0):.1%}\n"
        report += f"- **盘口**: {match['handicap_data'].get('current_handicap_str', 'N/A')}\n"
        report += f"- **实际结果**: {match.get('reason', 'N/A')}\n"
        report += f"- **DPI**: {rec.get('评分等级', {}).get('DPI', 'N/A')}\n"
        report += f"- **FLM**: {rec.get('评分等级', {}).get('FLM', 'N/A')}\n"
        report += f"- **SPM**: {rec.get('评分等级', {}).get('SPM', 'N/A')}\n"
        report += f"- **资金等级**: {rec.get('资金等级', {}).get('level', 'N/A')}\n"
        report += f"- **SBRE**: {'触发' if rec.get('SBRE', {}).get('triggered') else '未触发'}\n\n"
    
    report += "---\n\n## 💡 优化建议\n\n"
    
    # 分析DPI档位
    dpi_a = features['DPI'].get('A档', {'correct': 0, 'total': 0})
    dpi_d = features['DPI'].get('D档', {'correct': 0, 'total': 0})
    
    if dpi_a['total'] > 0:
        a_acc = dpi_a['correct'] / dpi_a['total'] * 100
        if a_acc >= 70:
            report += f"### ✅ A档表现优秀\n\nA档准确率 {a_acc:.1f}%，建议保持当前评分逻辑。\n\n"
        else:
            report += f"### ⚠️ A档需要优化\n\nA档准确率仅 {a_acc:.1f}%，建议调整FLM或SPM的评分标准。\n\n"
    
    if dpi_d['total'] > 0:
        d_acc = dpi_d['correct'] / dpi_d['total'] * 100
        report += f"### D档分析\n\nD档准确率 {d_acc:.1f}%。"
        if d_acc < 40:
            report += f" 建议增加D档的风控力度或直接观望。\n\n"
        else:
            report += f" D档推荐较少，符合预期。\n\n"
    
    # SBRE分析
    if sbre_data['triggered'] > 0:
        sbre_acc = sbre_data['correct'] / sbre_data['total'] * 100
        if sbre_acc >= 50:
            report += f"### ✅ SBRE机制有效\n\nSBRE准确率 {sbre_acc:.1f}%，反打机制有效。\n\n"
        else:
            report += f"### ⚠️ SBRE需要调整\n\nSBRE准确率仅 {sbre_acc:.1f}%，建议收紧触发条件。\n\n"
    
    report += "---\n\n## 📈 下一步行动\n\n"
    report += "1. 根据A/B档的准确率，调整置信度阈值（当前65%）\n"
    report += "2. 分析错误案例，找出共同特征\n"
    report += "3. 优化FLM/SPM的评分权重\n"
    report += "4. 测试不同的SBRE触发条件\n"
    
    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 报告已保存: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='回测分析与模型优化')
    parser.add_argument('--output', type=str, default='backtest_report.md', help='报告输出文件')
    parser.add_argument('--limit', type=int, default=None, help='限制分析数量')
    
    args = parser.parse_args()
    
    # 初始化
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    print(f"\n{'='*80}")
    print(f"回测分析与模型优化")
    print(f"{'='*80}\n")
    
    # 扫描带比分的文件
    print("📂 扫描数据文件...")
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        if json_file.stem.startswith(('2025-', '2024-')) and '_' in json_file.stem:
            # 检查是否包含比分格式（_数字_数字_）
            if json_file.stem.count('_') >= 4:  # 至少有比分部分
                json_files.append(json_file)
    
    print(f"✅ 找到 {len(json_files)} 个带比分的文件\n")
    
    if not json_files:
        print("❌ 没有找到带比分的数据文件")
        return
    
    if args.limit:
        json_files = json_files[:args.limit]
        print(f"🔍 限制分析: {len(json_files)} 个文件\n")
    
    # 初始化引擎
    engine = HandicapRecommendationEngineX1()
    
    # 加载数据并生成推荐
    print("🔄 加载数据并生成推荐...\n")
    matches = []
    
    for i, json_file in enumerate(json_files, 1):
        if i % 10 == 0:
            print(f"  进度: {i}/{len(json_files)}")
        
        match_data = load_match_data(json_file)
        if not match_data:
            continue
        
        # 生成推荐
        try:
            recommendation = engine.generate_recommendation(
                trade_data=match_data['trade_data'],
                metadata=match_data['metadata'],
                handicap_data=match_data['handicap_data']
            )
            
            # 🔥 调试：打印前3个推荐的详细信息
            if i <= 3:
                final_rec = recommendation.get('最终推荐', {})
                print(f"    推荐: {final_rec.get('direction', 'N/A')}")
                print(f"    置信度: {final_rec.get('confidence', 0):.1%}")
                print(f"    应下注: {final_rec.get('should_bet', False)}")
            
            # 🔥 修复：检查盘口描述，判断正负号
            handicap_raw = match_data['handicap_data'].get('current_handicap', 0)
            handicap_str = match_data['handicap_data'].get('current_handicap_str', '')
            
            # 如果盘口描述不包含"受"字，表示主队让球，需要转为负数
            if handicap_raw != 0 and '受' not in handicap_str:
                handicap = -abs(handicap_raw)  # 主队让球，用负数
            else:
                handicap = handicap_raw  # 客队让球或平手，用原值
            
            # 🔥 调试：打印盘口转换
            if i <= 3:
                print(f"    盘口: {handicap_str} ({handicap_raw} → {handicap})")
            
            is_correct, reason = check_prediction_correct(
                recommendation=recommendation,
                home_score=match_data['home_score'],
                away_score=match_data['away_score'],
                handicap=handicap
            )
            
            # 🔥 调试：打印前3个的判断结果
            if i <= 3:
                print(f"    判断: {reason}")
                print()
            
            match_data['recommendation'] = recommendation
            match_data['is_correct'] = is_correct
            match_data['reason'] = reason
            matches.append(match_data)
            
        except Exception as e:
            print(f"  ⚠️  推荐失败 {json_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ 成功分析 {len(matches)} 场比赛\n")
    
    # 分析特征
    print("📊 分析特征有效性...\n")
    features = analyze_features(matches)
    
    # 生成报告
    print("📝 生成报告...\n")
    generate_report(matches, features, args.output)
    
    # 打印简要统计
    with_rec = [m for m in matches if m.get('is_correct') is not None]
    correct = [m for m in with_rec if m.get('is_correct')]
    observed = [m for m in matches if m.get('is_correct') is None]
    
    print(f"\n{'='*80}")
    print(f"📊 回测结果")
    print(f"{'='*80}")
    print(f"总比赛数: {len(matches)}")
    print(f"有推荐: {len(with_rec)}")
    print(f"观望: {len(observed)}")
    
    if with_rec:
        correct_count = len(correct)
        wrong_count = len(with_rec) - correct_count
        accuracy = correct_count / len(with_rec) * 100
        print(f"推荐正确: {correct_count}")
        print(f"推荐错误: {wrong_count}")
        print(f"准确率: {accuracy:.1f}%")
    else:
        print("推荐正确: 0")
        print("推荐错误: 0")
        print("准确率: N/A（全部观望）")
    
    print(f"{'='*80}\n")
    
    # 🔥 调试：显示观望原因
    if observed:
        print("📋 观望比赛原因分析:")
        reason_count = {}
        for m in observed[:10]:  # 只显示前10个
            reason = m.get('reason', '未知')
            reason_count[reason] = reason_count.get(reason, 0) + 1
        
        for reason, count in reason_count.items():
            print(f"  - {reason}: {count}场")
        print()


if __name__ == "__main__":
    main()
