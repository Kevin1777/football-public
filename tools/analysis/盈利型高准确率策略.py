"""
盈利型高准确率策略 - 准确率76%+ROI正

基于5759场历史数据验证
最后更新：2025-12-12

核心发现：
高准确率（70%+）通常意味着低赔率，ROI难以为正
但发现了一个例外：主赔1.4-1.5+庄怕客<-5

策略表现：
- 主赔1.4-1.5+庄怕客<-5: 96场, 准确率76.0%, ROI +9.7%, 月度✅✅✅
- 主赔1.4-1.5+客热>20: 171场, 准确率73.7%, ROI +6.6%, 月度✅✅✅
- 客赔1.3-1.4: 86场, 准确率77.9%, ROI +5.3%, 月度✅✅⚠️
"""


def get_profitable_high_acc_recommendation(match_data, strategy='optimal'):
    """
    获取盈利型高准确率推荐
    
    Args:
        match_data: dict, 包含以下字段:
            - 主胜_欧赔 (oh): 主胜赔率
            - 客胜_欧赔 (oa): 客胜赔率
            - 热指_客 (ra): 客队热指
            - 赢亏_客 (ya): 庄家怕客胜（赢亏_客）
        strategy: str, 策略选择
            - 'optimal': 最优信号（准确率76%，ROI +9.7%）
            - 'extended': 扩展信号（更多覆盖）
    
    Returns:
        dict or None: 推荐信息
    """
    # 提取指标
    oh = match_data.get('主胜_欧赔') or match_data.get('oh')
    oa = match_data.get('客胜_欧赔') or match_data.get('oa')
    ra = match_data.get('热指_客') or match_data.get('ra', 0)
    ya = match_data.get('赢亏_客') or match_data.get('ya', 0)
    
    if oh is None or oa is None:
        return None
    
    if strategy == 'optimal':
        # 最优信号：主赔1.4-1.5+庄怕客<-5
        # 96场, 准确率76.0%, ROI +9.7%, 月度✅✅✅
        if 1.4 <= oh < 1.5 and ya < -5:
            return {
                '方向': '主胜',
                '信号': '主赔1.4-1.5+庄怕客<-5',
                '准确率': 76.0,
                'ROI': 9.7,
                '置信度': 'high',
                '策略': 'optimal'
            }
        # 客赔1.3-1.4
        # 86场, 准确率77.9%, ROI +5.3%
        if 1.3 <= oa < 1.4:
            return {
                '方向': '客胜',
                '信号': '客赔1.3-1.4',
                '准确率': 77.9,
                'ROI': 5.3,
                '置信度': 'high',
                '策略': 'optimal'
            }
    
    elif strategy == 'extended':
        # 扩展信号：主赔1.4-1.5+客热>20
        # 171场, 准确率73.7%, ROI +6.6%, 月度✅✅✅
        if 1.4 <= oh < 1.5 and ra > 20:
            return {
                '方向': '主胜',
                '信号': '主赔1.4-1.5+客热>20',
                '准确率': 73.7,
                'ROI': 6.6,
                '置信度': 'medium',
                '策略': 'extended'
            }
        # 客赔1.3-1.4
        if 1.3 <= oa < 1.4:
            return {
                '方向': '客胜',
                '信号': '客赔1.3-1.4',
                '准确率': 77.9,
                'ROI': 5.3,
                '置信度': 'high',
                '策略': 'extended'
            }
    
    return None


# 策略配置
STRATEGY_CONFIG = {
    'optimal': {
        'name': '最优信号',
        'coverage': '3.2%',
        'accuracy': '76.9%',
        'roi': '+7.6%',
        'monthly_stable': True,
        'signals': [
            {
                'direction': 'home',
                'condition': '1.4<=oh<1.5 and ya<-5',
                'accuracy': 76.0,
                'roi': 9.7,
                'count': 96
            },
            {
                'direction': 'away',
                'condition': '1.3<=oa<1.4',
                'accuracy': 77.9,
                'roi': 5.3,
                'count': 86
            },
        ]
    },
    'extended': {
        'name': '扩展信号',
        'coverage': '4.5%',
        'accuracy': '74.5%',
        'roi': '+6.0%',
        'monthly_stable': True,
        'signals': [
            {
                'direction': 'home',
                'condition': '1.4<=oh<1.5 and ra>20',
                'accuracy': 73.7,
                'roi': 6.6,
                'count': 171
            },
            {
                'direction': 'away',
                'condition': '1.3<=oa<1.4',
                'accuracy': 77.9,
                'roi': 5.3,
                'count': 86
            },
        ]
    }
}


if __name__ == '__main__':
    # 测试
    test_cases = [
        {'主胜_欧赔': 1.45, '客胜_欧赔': 2.8, '热指_客': 25, '赢亏_客': -10},
        {'主胜_欧赔': 2.5, '客胜_欧赔': 1.35, '热指_客': 10, '赢亏_客': 5},
        {'主胜_欧赔': 1.42, '客胜_欧赔': 2.5, '热指_客': 22, '赢亏_客': -3},
        {'主胜_欧赔': 2.0, '客胜_欧赔': 2.0, '热指_客': 20, '赢亏_客': 0},
    ]
    
    print("盈利型高准确率策略测试")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试{i}: 主赔={case['主胜_欧赔']}, 客赔={case['客胜_欧赔']}, 客热={case['热指_客']}, 庄怕客={case['赢亏_客']}")
        
        for strategy in ['optimal', 'extended']:
            rec = get_profitable_high_acc_recommendation(case, strategy)
            if rec:
                print(f"  {strategy}: {rec['方向']} ({rec['信号']}) 准确率{rec['准确率']}% ROI+{rec['ROI']}%")
            else:
                print(f"  {strategy}: 无推荐")
