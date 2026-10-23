"""
交易明细策略 V8 - 全赔率区间覆盖版

基于5759场历史数据验证
最后更新：2025-12-12

策略特点：
- 覆盖1.6-2.2和2.5+两个赔率区间
- 所有信号月度全稳
- 综合ROI约+20%

信号汇总：
【1.6-2.2区间】
- 客赔1.6-2.2+主热赢亏>30+庄怕主<-15：160场，准确率55.6%，ROI +7.2%
- 客赔1.6-2.2+主热赢亏>30+庄怕主<-10：169场，准确率55.0%，ROI +5.8%

【2.5+区间】
- 客赔2.8+客凯利<94：81场，准确率40.7%，ROI +37.6%
- 客赔2.5+客凯利<94+客量>40%：35场，准确率60%，ROI +70%
- 和量>48%+和凯利<96：300场，准确率39.7%，ROI +22%
- 主赔>2.0+客热>25：V7信号，ROI +22%
"""


def get_v8_recommendation(match_data):
    """
    获取V8策略推荐
    
    Args:
        match_data: dict, 包含交易明细数据
    
    Returns:
        dict or None: 推荐信息
    """
    # 提取指标
    oh = match_data.get('主胜_欧赔') or match_data.get('oh')
    oa = match_data.get('客胜_欧赔') or match_data.get('oa')
    od = match_data.get('和局_欧赔') or match_data.get('od', 3.0)
    
    ra = match_data.get('热指_客') or match_data.get('ra', 0)
    rh = match_data.get('热指_主') or match_data.get('rh', 0)
    
    ya = match_data.get('赢亏_客') or match_data.get('ya', 0)
    yh = match_data.get('赢亏_主') or match_data.get('yh', 0)
    
    ka = match_data.get('凯利_客') or match_data.get('ka', 100)
    kd = match_data.get('凯利_和') or match_data.get('kd', 100)
    
    dvp = match_data.get('和局成交占比') or match_data.get('dvp', 0)
    avp = match_data.get('客胜成交占比') or match_data.get('avp', 0)
    
    if oh is None or oa is None:
        return None
    
    # 计算衍生指标
    hfh = rh - yh  # 主热赢亏差
    hfa = ra - ya  # 客热赢亏差
    
    # ========== 2.5+区间信号（优先级最高，ROI最高） ==========
    
    # 信号1：客赔2.5+客凯利<94+客量>40%（ROI +70%）
    if oa >= 2.5 and ka < 94 and avp > 40:
        return {
            '方向': '客胜',
            '信号': '客赔2.5+客凯利<94+客量>40%',
            '准确率': 60.0,
            'ROI': 70.1,
            '层级': 'Tier1',
            '仓位': '2%'
        }
    
    # 信号2：客赔2.8+客凯利<94（ROI +37.6%）
    if oa >= 2.8 and ka < 94:
        return {
            '方向': '客胜',
            '信号': '客赔2.8+客凯利<94',
            '准确率': 40.7,
            'ROI': 37.6,
            '层级': 'Tier1',
            '仓位': '2%'
        }
    
    # 信号3：和量>48%+和凯利<96（ROI +22%）
    if dvp > 48 and kd < 96:
        return {
            '方向': '平局',
            '信号': '和量>48%+和凯利<96',
            '准确率': 39.7,
            'ROI': 22.0,
            '层级': 'Tier2',
            '仓位': '1-2%'
        }
    
    # 信号4：主赔>2.0+客热>25（V7信号，ROI +22%）
    if oh > 2.0 and ra > 25:
        return {
            '方向': '主胜',
            '信号': '主赔>2.0+客热>25',
            '准确率': 56.0,
            'ROI': 21.7,
            '层级': 'Tier2',
            '仓位': '1-2%'
        }
    
    # ========== 1.6-2.2区间信号（补充，ROI较低） ==========
    
    # 信号5：客赔1.6-2.2+主热赢亏>30+庄怕主<-15（ROI +7.2%）
    if 1.6 <= oa < 2.2 and hfh > 30 and yh < -15:
        return {
            '方向': '客胜',
            '信号': '客赔1.6-2.2+主热赢亏>30+庄怕主<-15',
            '准确率': 55.6,
            'ROI': 7.2,
            '层级': 'Tier3',
            '仓位': '1%'
        }
    
    # 信号6：客赔1.6-2.2+主热赢亏>30+庄怕主<-10（ROI +5.8%）
    if 1.6 <= oa < 2.2 and hfh > 30 and yh < -10:
        return {
            '方向': '客胜',
            '信号': '客赔1.6-2.2+主热赢亏>30+庄怕主<-10',
            '准确率': 55.0,
            'ROI': 5.8,
            '层级': 'Tier3',
            '仓位': '1%'
        }
    
    return None


# 策略配置
V8_SIGNALS = [
    {
        'name': '客赔2.5+客凯利<94+客量>40%',
        'direction': 'away',
        'count': 35,
        'accuracy': 60.0,
        'roi': 70.1,
        'tier': 1,
        'monthly_stable': True
    },
    {
        'name': '客赔2.8+客凯利<94',
        'direction': 'away',
        'count': 81,
        'accuracy': 40.7,
        'roi': 37.6,
        'tier': 1,
        'monthly_stable': True
    },
    {
        'name': '和量>48%+和凯利<96',
        'direction': 'draw',
        'count': 300,
        'accuracy': 39.7,
        'roi': 22.0,
        'tier': 2,
        'monthly_stable': True
    },
    {
        'name': '主赔>2.0+客热>25',
        'direction': 'home',
        'count': 75,
        'accuracy': 56.0,
        'roi': 21.7,
        'tier': 2,
        'monthly_stable': True
    },
    {
        'name': '客赔1.6-2.2+主热赢亏>30+庄怕主<-15',
        'direction': 'away',
        'count': 160,
        'accuracy': 55.6,
        'roi': 7.2,
        'tier': 3,
        'monthly_stable': True
    },
    {
        'name': '客赔1.6-2.2+主热赢亏>30+庄怕主<-10',
        'direction': 'away',
        'count': 169,
        'accuracy': 55.0,
        'roi': 5.8,
        'tier': 3,
        'monthly_stable': True
    },
]


if __name__ == '__main__':
    # 测试
    test_cases = [
        # 2.5+区间
        {'主胜_欧赔': 2.0, '客胜_欧赔': 3.0, '凯利_客': 93, '客胜成交占比': 45},
        {'主胜_欧赔': 1.8, '客胜_欧赔': 3.5, '凯利_客': 92, '客胜成交占比': 35},
        # 平局
        {'主胜_欧赔': 2.0, '客胜_欧赔': 2.5, '和局成交占比': 52, '凯利_和': 94},
        # 1.6-2.2区间
        {'主胜_欧赔': 2.5, '客胜_欧赔': 1.9, '热指_主': 35, '赢亏_主': -20},
    ]
    
    print("V8策略测试")
    print("=" * 60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试{i}: {case}")
        rec = get_v8_recommendation(case)
        if rec:
            print(f"  推荐: {rec['方向']} ({rec['信号']})")
            print(f"  准确率: {rec['准确率']}%, ROI: +{rec['ROI']}%, 仓位: {rec['仓位']}")
        else:
            print("  无推荐")
