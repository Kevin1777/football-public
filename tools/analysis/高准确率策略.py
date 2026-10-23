"""
高准确率策略 - 70%+准确率，月度稳定

基于5759场历史数据验证
最后更新：2025-12-12

策略目标：对大部分低赔率比赛做出推荐，准确率70%以上

核心发现：
1. 70%准确率的核心条件是低赔率（<1.55）
2. 加入热指>20可以提升月度稳定性
3. 客胜需要更严格条件（<1.4）才能月度稳定

策略版本：
- 策略1(月度全稳): 847场(14.7%), 准确率76.9%, 月度✅✅✅
- 策略4(优化版): 916场(15.9%), 准确率75.3%, 月度✅✅✅
- 策略3(最大覆盖): 1252场(21.7%), 准确率71.2%, 月度✅✅⚠️
"""

def get_high_accuracy_recommendation(match_data, strategy='optimal'):
    """
    获取高准确率推荐
    
    Args:
        match_data: dict, 包含以下字段:
            - 主胜_欧赔 (oh): 主胜赔率
            - 客胜_欧赔 (oa): 客胜赔率
            - 热指_客 (ra): 客队热指
            - 热指_主 (rh): 主队热指
        strategy: str, 策略选择
            - 'stable': 月度全稳版（最保守）
            - 'optimal': 优化版（推荐）
            - 'coverage': 最大覆盖版
    
    Returns:
        dict or None: 推荐信息
    """
    # 提取指标
    oh = match_data.get('主胜_欧赔') or match_data.get('oh')
    oa = match_data.get('客胜_欧赔') or match_data.get('oa')
    ra = match_data.get('热指_客') or match_data.get('ra', 0)
    rh = match_data.get('热指_主') or match_data.get('rh', 0)
    
    if oh is None or oa is None:
        return None
    
    if strategy == 'stable':
        # 策略1：月度全稳版
        # 条件：主赔<1.5+客热>20 或 客赔<1.4
        # 覆盖14.7%, 准确率76.9%, 月度✅✅✅
        if oh < 1.5 and ra > 20:
            return {
                '方向': '主胜',
                '信号': '主赔<1.5+客热>20',
                '准确率': 75.1,
                '置信度': 'high',
                '策略': 'stable'
            }
        if oa < 1.4:
            return {
                '方向': '客胜',
                '信号': '客赔<1.4',
                '准确率': 81.9,
                '置信度': 'high',
                '策略': 'stable'
            }
    
    elif strategy == 'optimal':
        # 策略4：优化版（推荐）
        # 条件：主赔<1.55+客热>20 或 客赔<1.4
        # 覆盖15.9%, 准确率75.3%, 月度✅✅✅
        if oh < 1.55 and ra > 20:
            return {
                '方向': '主胜',
                '信号': '主赔<1.55+客热>20',
                '准确率': 73.3,
                '置信度': 'high',
                '策略': 'optimal'
            }
        if oa < 1.4:
            return {
                '方向': '客胜',
                '信号': '客赔<1.4',
                '准确率': 81.9,
                '置信度': 'high',
                '策略': 'optimal'
            }
    
    elif strategy == 'coverage':
        # 策略3：最大覆盖版
        # 条件：主赔<1.55 或 客赔<1.55
        # 覆盖21.7%, 准确率71.2%, 月度✅✅⚠️
        if oh < 1.55:
            return {
                '方向': '主胜',
                '信号': '主赔<1.55',
                '准确率': 71.6,
                '置信度': 'medium',
                '策略': 'coverage'
            }
        if oa < 1.55:
            return {
                '方向': '客胜',
                '信号': '客赔<1.55',
                '准确率': 70.5,
                '置信度': 'medium',
                '策略': 'coverage'
            }
    
    return None


def get_all_recommendations(match_data):
    """
    获取所有策略的推荐（用于对比）
    
    Returns:
        list: 所有匹配的推荐
    """
    results = []
    for strategy in ['stable', 'optimal', 'coverage']:
        rec = get_high_accuracy_recommendation(match_data, strategy)
        if rec:
            results.append(rec)
    return results


# 策略配置
STRATEGY_CONFIG = {
    'stable': {
        'name': '月度全稳版',
        'coverage': '14.7%',
        'accuracy': '76.9%',
        'monthly_stable': True,
        'signals': [
            {'direction': 'home', 'condition': 'oh<1.5 and ra>20', 'accuracy': 75.1},
            {'direction': 'away', 'condition': 'oa<1.4', 'accuracy': 81.9},
        ]
    },
    'optimal': {
        'name': '优化版',
        'coverage': '15.9%',
        'accuracy': '75.3%',
        'monthly_stable': True,
        'signals': [
            {'direction': 'home', 'condition': 'oh<1.55 and ra>20', 'accuracy': 73.3},
            {'direction': 'away', 'condition': 'oa<1.4', 'accuracy': 81.9},
        ]
    },
    'coverage': {
        'name': '最大覆盖版',
        'coverage': '21.7%',
        'accuracy': '71.2%',
        'monthly_stable': False,
        'signals': [
            {'direction': 'home', 'condition': 'oh<1.55', 'accuracy': 71.6},
            {'direction': 'away', 'condition': 'oa<1.55', 'accuracy': 70.5},
        ]
    }
}


if __name__ == '__main__':
    # 测试
    test_cases = [
        {'主胜_欧赔': 1.45, '客胜_欧赔': 2.8, '热指_客': 25, '热指_主': 15},
        {'主胜_欧赔': 2.5, '客胜_欧赔': 1.35, '热指_客': 10, '热指_主': 30},
        {'主胜_欧赔': 1.52, '客胜_欧赔': 2.5, '热指_客': 22, '热指_主': 18},
        {'主胜_欧赔': 2.0, '客胜_欧赔': 2.0, '热指_客': 20, '热指_主': 20},
    ]
    
    print("高准确率策略测试")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试{i}: 主赔={case['主胜_欧赔']}, 客赔={case['客胜_欧赔']}, 客热={case['热指_客']}")
        
        for strategy in ['stable', 'optimal', 'coverage']:
            rec = get_high_accuracy_recommendation(case, strategy)
            if rec:
                print(f"  {strategy}: {rec['方向']} ({rec['信号']}) 准确率{rec['准确率']}%")
            else:
                print(f"  {strategy}: 无推荐")
