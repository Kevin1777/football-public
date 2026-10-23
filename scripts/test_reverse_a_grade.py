"""
测试反转A档假设

假设：FLM热度是反向指标
- A档（强热支持）准确率51.6%
- 如果反转推荐，准确率应该变成48.4%
- 如果准确率变高（>60%），说明FLM确实是反向指标！
"""

import sys
from pathlib import Path
import json
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from recommendation.handicap_engine_x1 import HandicapRecommendationEngineX1


def check_prediction_with_reverse(
    recommendation,
    home_score,
    away_score,
    handicap,
    reverse_a_grade=False
):
    """
    检查推荐是否正确，可选择反转A档
    """
    final_rec = recommendation.get('最终推荐', {})
    direction = final_rec.get('direction', '')
    should_bet = final_rec.get('should_bet', False)
    dpi = recommendation.get('评分等级', {}).get('DPI', '')
    
    if not should_bet or not direction:
        return None, "观望"
    
    # 判断实际结果
    home_with_handicap = home_score + handicap
    if home_with_handicap > away_score:
        actual_result = "主队赢盘"
    elif home_with_handicap < away_score:
        actual_result = "客队赢盘"
    else:
        actual_result = "走盘"
    
    # 判断推荐方向
    flm_score = recommendation.get('评分等级', {}).get('FLM', '')
    
    if "跟随" in direction and "盘口" in direction:
        if "主" in flm_score:
            predicted = "主队赢盘"
        elif "客" in flm_score:
            predicted = "客队赢盘"
        else:
            if handicap < 0:
                predicted = "主队赢盘"
            elif handicap > 0:
                predicted = "客队赢盘"
            else:
                predicted = "主队赢盘"
    elif "主队" in direction or "主" in direction:
        predicted = "主队赢盘"
    elif "客队" in direction or "客" in direction:
        predicted = "客队赢盘"
    else:
        return None, f"未识别方向: {direction}"
    
    # 🔥 反转A档推荐
    if reverse_a_grade and 'A档' in dpi:
        if predicted == "主队赢盘":
            predicted = "客队赢盘"
        elif predicted == "客队赢盘":
            predicted = "主队赢盘"
    
    is_correct = (predicted == actual_result)
    reason = f"推荐{predicted}, 实际{actual_result}, DPI={dpi}"
    
    return is_correct, reason


def load_and_analyze(data_dir, reverse_a=False):
    """加载数据并分析"""
    
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        if json_file.stem.startswith(('2025-', '2024-')) and json_file.stem.count('_') >= 4:
            json_files.append(json_file)
    
    engine = HandicapRecommendationEngineX1()
    
    results = {
        'total': 0,
        'a_grade': {'total': 0, 'correct': 0},
        'b_grade': {'total': 0, 'correct': 0},
        'all': {'total': 0, 'correct': 0}
    }
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            match_info = data.get('match_info', {})
            score = match_info.get('score')
            
            if not score:
                continue
            
            parts = score.split('-')
            home_score = int(parts[0])
            away_score = int(parts[1])
            
            trade_data = pd.DataFrame(data['trade_data']['data'])
            if trade_data.empty:
                continue
            
            # 生成推荐
            recommendation = engine.generate_recommendation(
                trade_data=trade_data,
                metadata=data.get('metadata', []),
                handicap_data=data.get('handicap_data', {})
            )
            
            # 获取盘口
            handicap_raw = data['handicap_data'].get('current_handicap', 0)
            handicap_str = data['handicap_data'].get('current_handicap_str', '')
            
            if handicap_raw != 0 and '受' not in handicap_str:
                handicap = -abs(handicap_raw)
            else:
                handicap = handicap_raw
            
            # 检查正确性
            is_correct, reason = check_prediction_with_reverse(
                recommendation, home_score, away_score, handicap, reverse_a
            )
            
            if is_correct is None:
                continue
            
            results['total'] += 1
            results['all']['total'] += 1
            if is_correct:
                results['all']['correct'] += 1
            
            # 分档统计
            dpi = recommendation.get('评分等级', {}).get('DPI', '')
            if 'A档' in dpi:
                results['a_grade']['total'] += 1
                if is_correct:
                    results['a_grade']['correct'] += 1
            elif 'B档' in dpi:
                results['b_grade']['total'] += 1
                if is_correct:
                    results['b_grade']['correct'] += 1
            
        except Exception as e:
            continue
    
    return results


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    print("\n" + "="*80)
    print("测试反转A档假设")
    print("="*80 + "\n")
    
    # 原始结果
    print("📊 原始推荐结果...")
    original = load_and_analyze(data_dir, reverse_a=False)
    
    print(f"\n整体准确率: {original['all']['correct']}/{original['all']['total']} = "
          f"{original['all']['correct']/original['all']['total']*100:.1f}%")
    
    if original['a_grade']['total'] > 0:
        a_acc = original['a_grade']['correct'] / original['a_grade']['total'] * 100
        print(f"A档准确率: {original['a_grade']['correct']}/{original['a_grade']['total']} = {a_acc:.1f}%")
    
    if original['b_grade']['total'] > 0:
        b_acc = original['b_grade']['correct'] / original['b_grade']['total'] * 100
        print(f"B档准确率: {original['b_grade']['correct']}/{original['b_grade']['total']} = {b_acc:.1f}%")
    
    # 反转A档结果
    print("\n" + "="*80)
    print("🔄 反转A档推荐...")
    print("="*80 + "\n")
    
    reversed_results = load_and_analyze(data_dir, reverse_a=True)
    
    print(f"\n整体准确率: {reversed_results['all']['correct']}/{reversed_results['all']['total']} = "
          f"{reversed_results['all']['correct']/reversed_results['all']['total']*100:.1f}%")
    
    if reversed_results['a_grade']['total'] > 0:
        a_acc_rev = reversed_results['a_grade']['correct'] / reversed_results['a_grade']['total'] * 100
        print(f"A档准确率（反转后）: {reversed_results['a_grade']['correct']}/{reversed_results['a_grade']['total']} = {a_acc_rev:.1f}%")
    
    if reversed_results['b_grade']['total'] > 0:
        b_acc_rev = reversed_results['b_grade']['correct'] / reversed_results['b_grade']['total'] * 100
        print(f"B档准确率（不变）: {reversed_results['b_grade']['correct']}/{reversed_results['b_grade']['total']} = {b_acc_rev:.1f}%")
    
    # 分析结果
    print("\n" + "="*80)
    print("📈 结论")
    print("="*80 + "\n")
    
    if original['a_grade']['total'] > 0:
        original_a = original['a_grade']['correct'] / original['a_grade']['total'] * 100
        reversed_a = reversed_results['a_grade']['correct'] / reversed_results['a_grade']['total'] * 100
        improvement = reversed_a - original_a
        
        print(f"A档准确率变化: {original_a:.1f}% → {reversed_a:.1f}% ({improvement:+.1f}%)")
        
        if reversed_a > 60:
            print("\n✅ 结论：FLM确实是反向指标！")
            print("   强热支持的方向反而容易输，应该反向操作！")
        elif improvement > 10:
            print("\n⚠️  结论：FLM有一定的反向性")
            print("   需要调整FLM的权重或逻辑")
        else:
            print("\n❌ 结论：反转无效")
            print("   问题可能不在FLM，而在其他模块")
    
    overall_original = original['all']['correct'] / original['all']['total'] * 100
    overall_reversed = reversed_results['all']['correct'] / reversed_results['all']['total'] * 100
    overall_improvement = overall_reversed - overall_original
    
    print(f"\n整体准确率变化: {overall_original:.1f}% → {overall_reversed:.1f}% ({overall_improvement:+.1f}%)")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
