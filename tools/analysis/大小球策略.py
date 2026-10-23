"""
大小球交易明细策略

基于5634场历史数据验证
最后更新：2025-12-12

核心发现：
1. 小球信号ROI更高（+6%~+9%），大球信号ROI较低（+2%）
2. 低赔率（<1.9）是盈利的关键条件
3. 反向跟庄逻辑在大小球也有效：大球热指高→买小球

月度全稳信号：
1. 小球热指>60+小球赔率<1.9：417场，准确率63.8%，ROI +9.3% ✅✅✅
2. 庄怕小球<-20+小球赔率<1.9：546场，准确率63.9%，ROI +8.6% ✅✅✅
3. 小球必指>60+小球赔率<1.9：610场，准确率63.3%，ROI +6.2% ✅✅✅
"""


def get_ou_recommendation(match_data):
    """
    获取大小球推荐
    
    Args:
        match_data: dict, 包含大小球交易明细数据
            - under_idx: 小球热指
            - under_wl: 小球赢亏（庄家怕小球）
            - under_bifa: 小球必指
            - under_price: 小球赔率
            - over_idx: 大球热指
            - over_ratio: 大球成交占比
            - over_price: 大球赔率
    
    Returns:
        dict or None: 推荐信息
    """
    # 提取指标
    under_idx = match_data.get('小球热指') or match_data.get('under_idx', 50)
    under_wl = match_data.get('小球赢亏') or match_data.get('under_wl', 0)
    under_bifa = match_data.get('小球必指') or match_data.get('under_bifa', 50)
    under_price = match_data.get('小球赔率') or match_data.get('under_price', 2.0)
    
    over_idx = match_data.get('大球热指') or match_data.get('over_idx', 50)
    over_ratio = match_data.get('大球占比') or match_data.get('over_ratio', 50)
    over_price = match_data.get('大球赔率') or match_data.get('over_price', 2.0)
    
    # ========== 小球信号（月度全稳，ROI最高） ==========
    
    # 信号1：小球热指>60+小球赔率<1.9（ROI +9.3%）
    if under_idx > 60 and under_price < 1.9:
        return {
            '方向': '小球',
            '信号': '小球热指>60+小球赔率<1.9',
            '准确率': 63.8,
            'ROI': 9.3,
            '层级': 'Tier1',
            '仓位': '2%',
            '月度稳定': True
        }
    
    # 信号2：庄怕小球<-20+小球赔率<1.9（ROI +8.6%）
    if under_wl < -20 and under_price < 1.9:
        return {
            '方向': '小球',
            '信号': '庄怕小球<-20+小球赔率<1.9',
            '准确率': 63.9,
            'ROI': 8.6,
            '层级': 'Tier1',
            '仓位': '2%',
            '月度稳定': True
        }
    
    # 信号3：小球必指>60+小球赔率<1.9（ROI +6.2%）
    if under_bifa > 60 and under_price < 1.9:
        return {
            '方向': '小球',
            '信号': '小球必指>60+小球赔率<1.9',
            '准确率': 63.3,
            'ROI': 6.2,
            '层级': 'Tier2',
            '仓位': '1-2%',
            '月度稳定': True
        }
    
    # ========== 大球信号（ROI较低，月度不稳定） ==========
    
    # 信号4：大球占比>65%+大球赔率<1.8（ROI +2.2%）
    if over_ratio > 65 and over_price < 1.8:
        return {
            '方向': '大球',
            '信号': '大球占比>65%+大球赔率<1.8',
            '准确率': 66.0,
            'ROI': 2.2,
            '层级': 'Tier3',
            '仓位': '1%',
            '月度稳定': False
        }
    
    return None


# 策略配置
OU_SIGNALS = [
    {
        'name': '小球热指>60+小球赔率<1.9',
        'direction': 'under',
        'count': 417,
        'accuracy': 63.8,
        'roi': 9.3,
        'tier': 1,
        'monthly_stable': True,
        'monthly_detail': {'08': 11.7, '09': 4.5, '12': 13.2}
    },
    {
        'name': '庄怕小球<-20+小球赔率<1.9',
        'direction': 'under',
        'count': 546,
        'accuracy': 63.9,
        'roi': 8.6,
        'tier': 1,
        'monthly_stable': True,
        'monthly_detail': {'08': 11.2, '09': 4.0, '12': 11.7}
    },
    {
        'name': '小球必指>60+小球赔率<1.9',
        'direction': 'under',
        'count': 610,
        'accuracy': 63.3,
        'roi': 6.2,
        'tier': 2,
        'monthly_stable': True,
        'monthly_detail': {'08': 7.4, '09': 3.1, '12': 10.6}
    },
    {
        'name': '大球占比>65%+大球赔率<1.8',
        'direction': 'over',
        'count': 1332,
        'accuracy': 66.0,
        'roi': 2.2,
        'tier': 3,
        'monthly_stable': False,
        'monthly_detail': {'08': -2.1, '09': 7.1, '12': 5.4}
    },
]


if __name__ == '__main__':
    # 测试
    test_cases = [
        {'小球热指': 65, '小球赔率': 1.85, '小球赢亏': -15, '小球必指': 55},
        {'小球热指': 55, '小球赔率': 1.88, '小球赢亏': -25, '小球必指': 62},
        {'大球占比': 68, '大球赔率': 1.75, '大球热指': 70},
        {'小球热指': 50, '小球赔率': 2.0, '小球赢亏': 0, '小球必指': 50},
    ]
    
    print("大小球策略测试")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试{i}: {case}")
        rec = get_ou_recommendation(case)
        if rec:
            stable = '✅月度全稳' if rec['月度稳定'] else '⚠️月度不稳定'
            print(f"  推荐: {rec['方向']} ({rec['信号']})")
            print(f"  准确率: {rec['准确率']}%, ROI: +{rec['ROI']}%, {stable}")
        else:
            print("  无推荐")
