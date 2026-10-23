"""
V5深度优化分析 - 找出失败案例的共同特征
目标：在V5基础上进一步提升
"""

import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

def load_v5_results():
    """加载V5回测结果"""
    result_file = Path('backtest_详细结果_20251123_133612.json')
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_failures(results):
    """深度分析失败案例"""
    
    print("\n" + "="*80)
    print("🔍 深度分析V5的失败案例")
    print("="*80)
    
    successes = []
    failures = []
    
    for result in results:
        if not result.get('success'):
            continue
        
        validation = result.get('validation', {})
        if not validation.get('recommended'):
            continue
        
        recommendation = result.get('recommendation', {})
        match_info = result.get('match_info', {})
        handicap_data = result.get('handicap_data', {})
        
        # 解析特征
        trade_rows = result.get('trade_data_rows', 0)
        confidence = recommendation.get('confidence', 0)
        profit = validation.get('profit', 0)
        
        initial_str = handicap_data.get('initial', 'None (0)')
        current_str = handicap_data.get('current', 'None (0)')
        
        try:
            initial = float(initial_str.split('(')[1].split(')')[0])
        except:
            initial = 0
        
        try:
            current = float(current_str.split('(')[1].split(')')[0])
        except:
            current = 0
        
        handicap_change = current - initial
        abs_handicap = abs(current)
        
        # 趋势
        if abs(handicap_change) < 0.01:
            trend = '稳盘'
        elif handicap_change <= -0.75:
            trend = '大升'
        elif handicap_change <= -0.25:
            trend = '中升'
        elif handicap_change < 0:
            trend = '小升'
        else:
            trend = '降盘'
        
        direction = recommendation.get('direction', '')
        league = match_info.get('league', '')
        
        feature = {
            'trade_rows': trade_rows,
            'confidence': confidence,
            'handicap_change': handicap_change,
            'abs_handicap': abs_handicap,
            'trend': trend,
            'direction': direction,
            'league': league,
            'profit': profit,
            'match': match_info.get('label', ''),
        }
        
        if profit > 0:
            successes.append(feature)
        else:
            failures.append(feature)
    
    print(f"\n成功案例: {len(successes)}场 ({len(successes)/(len(successes)+len(failures))*100:.1f}%)")
    print(f"失败案例: {len(failures)}场 ({len(failures)/(len(successes)+len(failures))*100:.1f}%)")
    
    # 转为DataFrame
    success_df = pd.DataFrame(successes)
    failure_df = pd.DataFrame(failures)
    
    return success_df, failure_df


def compare_success_failure(success_df, failure_df):
    """对比成功与失败的特征差异"""
    
    print("\n" + "="*80)
    print("📊 成功 vs 失败 特征对比")
    print("="*80)
    
    # 1. 成交量对比
    print(f"\n【成交量】")
    print(f"  成功平均: {success_df['trade_rows'].mean():.0f}行")
    print(f"  失败平均: {failure_df['trade_rows'].mean():.0f}行")
    print(f"  差异: {success_df['trade_rows'].mean() - failure_df['trade_rows'].mean():+.0f}行")
    
    # 2. 置信度对比
    print(f"\n【置信度】")
    print(f"  成功平均: {success_df['confidence'].mean()*100:.1f}%")
    print(f"  失败平均: {failure_df['confidence'].mean()*100:.1f}%")
    print(f"  差异: {(success_df['confidence'].mean() - failure_df['confidence'].mean())*100:+.1f}%")
    
    # 3. 盘口变化对比
    print(f"\n【盘口变化】")
    print(f"  成功平均: {success_df['handicap_change'].mean():.3f}")
    print(f"  失败平均: {failure_df['handicap_change'].mean():.3f}")
    
    # 4. 趋势分布
    print(f"\n【趋势分布】")
    print("成功案例:")
    for trend in ['大升', '中升', '小升', '稳盘', '降盘']:
        count = (success_df['trend'] == trend).sum()
        if count > 0:
            print(f"  {trend}: {count}场 ({count/len(success_df)*100:.1f}%)")
    
    print("失败案例:")
    for trend in ['大升', '中升', '小升', '稳盘', '降盘']:
        count = (failure_df['trend'] == trend).sum()
        if count > 0:
            print(f"  {trend}: {count}场 ({count/len(failure_df)*100:.1f}%)")
    
    # 5. 盘口大小分布
    print(f"\n【盘口大小分布】")
    print("成功案例:")
    for threshold in [0, 0.5, 1.0, 1.5, 2.0, 2.5]:
        count = (success_df['abs_handicap'] >= threshold).sum()
        if count > 0:
            print(f"  ≥{threshold}: {count}场")
    
    print("失败案例:")
    for threshold in [0, 0.5, 1.0, 1.5, 2.0, 2.5]:
        count = (failure_df['abs_handicap'] >= threshold).sum()
        if count > 0:
            print(f"  ≥{threshold}: {count}场")


def find_failure_patterns(failure_df):
    """找出失败案例的高频模式"""
    
    print("\n" + "="*80)
    print("⚠️  高风险模式识别（需要避开）")
    print("="*80)
    
    patterns = []
    
    # 模式1: 低成交量 + 特定盘口
    for vol_threshold in [150, 200, 250]:
        filtered = failure_df[failure_df['trade_rows'] < vol_threshold]
        if len(filtered) >= 3:
            ratio = len(filtered) / len(failure_df)
            patterns.append({
                'name': f'成交量<{vol_threshold}行',
                'count': len(filtered),
                'ratio': ratio,
            })
    
    # 模式2: 特定趋势
    for trend in failure_df['trend'].unique():
        filtered = failure_df[failure_df['trend'] == trend]
        if len(filtered) >= 3:
            ratio = len(filtered) / len(failure_df)
            patterns.append({
                'name': f'{trend}',
                'count': len(filtered),
                'ratio': ratio,
            })
    
    # 模式3: 低置信度
    for conf_threshold in [0.70, 0.75, 0.80]:
        filtered = failure_df[failure_df['confidence'] < conf_threshold]
        if len(filtered) >= 3:
            ratio = len(filtered) / len(failure_df)
            patterns.append({
                'name': f'置信度<{conf_threshold*100:.0f}%',
                'count': len(filtered),
                'ratio': ratio,
            })
    
    # 模式4: 大盘口
    for handicap_threshold in [2.0, 2.5, 3.0]:
        filtered = failure_df[failure_df['abs_handicap'] >= handicap_threshold]
        if len(filtered) >= 3:
            ratio = len(filtered) / len(failure_df)
            patterns.append({
                'name': f'盘口≥{handicap_threshold}',
                'count': len(filtered),
                'ratio': ratio,
            })
    
    # 排序
    patterns.sort(key=lambda x: x['ratio'], reverse=True)
    
    print(f"\n{'高风险模式':40} {'失败场次':>10} {'占失败比例':>12}")
    print("-" * 70)
    
    for p in patterns[:15]:
        symbol = "🚫" if p['ratio'] >= 0.5 else "⚠️"
        print(f"{symbol} {p['name']:38} {p['count']:>10}场 {p['ratio']*100:>11.1f}%")


def suggest_improvements(success_df, failure_df):
    """建议改进方案"""
    
    print("\n" + "="*80)
    print("💡 V7改进建议")
    print("="*80)
    
    improvements = []
    
    # 建议1: 提高成交量阈值
    success_avg_vol = success_df['trade_rows'].mean()
    failure_avg_vol = failure_df['trade_rows'].mean()
    
    if success_avg_vol > failure_avg_vol + 20:
        new_threshold = int((success_avg_vol + failure_avg_vol) / 2)
        improvements.append({
            'name': '提高成交量阈值',
            'current': 'V5: 100行',
            'suggested': f'V7: {new_threshold}行',
            'reason': f'成功案例平均{success_avg_vol:.0f}行，失败案例{failure_avg_vol:.0f}行',
        })
    
    # 建议2: 提高置信度阈值
    success_avg_conf = success_df['confidence'].mean()
    failure_avg_conf = failure_df['confidence'].mean()
    
    if success_avg_conf > failure_avg_conf + 0.05:
        new_threshold = (success_avg_conf + failure_avg_conf) / 2
        improvements.append({
            'name': '提高置信度阈值',
            'current': 'V5: 65%',
            'suggested': f'V7: {new_threshold*100:.0f}%',
            'reason': f'成功案例平均{success_avg_conf*100:.1f}%，失败案例{failure_avg_conf*100:.1f}%',
        })
    
    # 建议3: 避开高风险趋势
    failure_trends = failure_df['trend'].value_counts()
    success_trends = success_df['trend'].value_counts()
    
    for trend in failure_trends.index:
        if trend in failure_trends.index and trend in success_trends.index:
            failure_ratio = failure_trends[trend] / len(failure_df)
            success_ratio = success_trends[trend] / len(success_df)
            
            if failure_ratio > success_ratio + 0.1:
                improvements.append({
                    'name': f'避开{trend}',
                    'current': f'V5: 接受',
                    'suggested': f'V7: 拒绝或降权',
                    'reason': f'失败案例中{failure_ratio*100:.1f}%，成功案例中{success_ratio*100:.1f}%',
                })
    
    # 建议4: 避开大盘口
    failure_big = (failure_df['abs_handicap'] >= 2.0).sum()
    success_big = (success_df['abs_handicap'] >= 2.0).sum()
    
    if failure_big / len(failure_df) > success_big / len(success_df) + 0.1:
        improvements.append({
            'name': '限制大盘口',
            'current': 'V5: 无限制',
            'suggested': 'V7: 盘口<2.0或降权',
            'reason': f'大盘口在失败中占{failure_big/len(failure_df)*100:.1f}%',
        })
    
    print(f"\n建议改进:")
    for i, imp in enumerate(improvements, 1):
        print(f"\n{i}. {imp['name']}")
        print(f"   当前: {imp['current']}")
        print(f"   建议: {imp['suggested']}")
        print(f"   原因: {imp['reason']}")
    
    return improvements


def test_v7_strategy(success_df, failure_df):
    """测试V7策略"""
    
    print("\n" + "="*80)
    print("🧪 V7策略模拟测试")
    print("="*80)
    
    all_df = pd.concat([success_df, failure_df])
    all_df['is_success'] = [True] * len(success_df) + [False] * len(failure_df)
    
    # 策略1: 提高成交量到200
    filtered = all_df[all_df['trade_rows'] >= 200]
    if len(filtered) > 0:
        wr = filtered['is_success'].mean()
        print(f"\n策略1: 成交量≥200行")
        print(f"  场次: {len(filtered)} ({len(filtered)/len(all_df)*100:.1f}%)")
        print(f"  准确率: {wr*100:.1f}%")
        print(f"  vs V5: {(wr - all_df['is_success'].mean())*100:+.1f}%")
    
    # 策略2: 提高置信度到75%
    filtered = all_df[all_df['confidence'] >= 0.75]
    if len(filtered) > 0:
        wr = filtered['is_success'].mean()
        print(f"\n策略2: 置信度≥75%")
        print(f"  场次: {len(filtered)} ({len(filtered)/len(all_df)*100:.1f}%)")
        print(f"  准确率: {wr*100:.1f}%")
        print(f"  vs V5: {(wr - all_df['is_success'].mean())*100:+.1f}%")
    
    # 策略3: 组合 - 200行 + 75%置信
    filtered = all_df[(all_df['trade_rows'] >= 200) & (all_df['confidence'] >= 0.75)]
    if len(filtered) > 0:
        wr = filtered['is_success'].mean()
        print(f"\n策略3: 成交量≥200 + 置信度≥75%")
        print(f"  场次: {len(filtered)} ({len(filtered)/len(all_df)*100:.1f}%)")
        print(f"  准确率: {wr*100:.1f}%")
        print(f"  vs V5: {(wr - all_df['is_success'].mean())*100:+.1f}%")
    
    # 策略4: 避开大盘口
    filtered = all_df[all_df['abs_handicap'] < 2.0]
    if len(filtered) > 0:
        wr = filtered['is_success'].mean()
        print(f"\n策略4: 盘口<2.0")
        print(f"  场次: {len(filtered)} ({len(filtered)/len(all_df)*100:.1f}%)")
        print(f"  准确率: {wr*100:.1f}%")
        print(f"  vs V5: {(wr - all_df['is_success'].mean())*100:+.1f}%")
    
    # 策略5: 最优组合
    filtered = all_df[
        (all_df['trade_rows'] >= 200) & 
        (all_df['confidence'] >= 0.70) &
        (all_df['abs_handicap'] < 2.0)
    ]
    if len(filtered) > 0:
        wr = filtered['is_success'].mean()
        print(f"\n策略5: 🏆 最优组合（200行 + 70%置信 + 盘口<2.0）")
        print(f"  场次: {len(filtered)} ({len(filtered)/len(all_df)*100:.1f}%)")
        print(f"  准确率: {wr*100:.1f}%")
        print(f"  vs V5: {(wr - all_df['is_success'].mean())*100:+.1f}%")


def main():
    """主函数"""
    
    print("\n" + "="*80)
    print("🔬 V5深度优化分析 - 寻找提升空间")
    print("="*80)
    
    data = load_v5_results()
    results = data.get('results', [])
    
    print(f"\n共 {len(results)} 场比赛")
    
    # 分析成功与失败
    success_df, failure_df = analyze_failures(results)
    
    if len(success_df) == 0 or len(failure_df) == 0:
        print("\n❌ 数据不足")
        return
    
    # 对比特征
    compare_success_failure(success_df, failure_df)
    
    # 识别高风险模式
    find_failure_patterns(failure_df)
    
    # 提出改进建议
    improvements = suggest_improvements(success_df, failure_df)
    
    # 测试V7策略
    test_v7_strategy(success_df, failure_df)
    
    print("\n" + "="*80)
    print("✅ 分析完成！")
    print("="*80)


if __name__ == "__main__":
    main()
