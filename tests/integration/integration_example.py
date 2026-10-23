"""
V2引擎集成示例 - 在app.py中使用新推荐引擎

方式1: 直接替换（推荐）
方式2: 双引擎对比
"""

# ============ 方式1: 直接使用V2引擎 ============

from recommendation import RecommendationEngineV2
import pandas as pd

# 初始化引擎
engine_v2 = RecommendationEngineV2()

# 假设你已经有了交易数据和盘口数据
def generate_recommendation_v2(trade_df: pd.DataFrame, match_info: dict, handicap_data: dict):
    """
    使用V2引擎生成推荐
    
    Args:
        trade_df: 交易明细DataFrame
        match_info: 比赛信息字典 {'league': '', 'home': '', 'away': '', 'kickoff': ''}
        handicap_data: 盘口数据字典 {'current_handicap': 0.5, 'current_handicap_str': '主-0.5'}
    """
    # 构造metadata格式
    metadata = [{
        'title_meta': match_info
    }]
    
    # 生成推荐
    result = engine_v2.generate_recommendation(
        trade_data=trade_df,
        metadata=metadata,
        handicap_data=handicap_data
    )
    
    # 提取关键信息
    recommendation = result.get('recommendation', {})
    scores = result.get('scores', {})
    risk = result.get('risk_assessment', {})
    
    # 格式化输出
    output = {
        'direction': recommendation.get('direction'),  # 'home' / 'away' / 'draw' / 'none'
        'confidence': recommendation.get('confidence'),  # 0-1
        'should_bet': recommendation.get('should_bet'),  # True/False
        'total_score': scores.get('total_score'),  # 0-100
        'risk_level': risk.get('risk_level'),  # 'low'/'medium'/'high'
        'reasons': recommendation.get('reason', []),  # 推荐理由列表
        'warnings': risk.get('warnings', []),  # 风险警告
        'signals': scores.get('signals', [])  # 关键信号
    }
    
    return output


# 使用示例
if __name__ == "__main__":
    # 模拟数据（实际使用时替换为真实数据）
    sample_trade_data = pd.DataFrame({
        '成交时间': ['11-21 12:00'],
        '总成交量': ['50000'],
        '主胜_已成交量': ['30000'],
        '和局_已成交量': ['5000'],
        '客胜_已成交量': ['15000'],
        '比例_主': [60],
        '比例_和': [10],
        '比例_客': [30],
        '主胜_欧赔': [2.0],
        '和局_欧赔': [3.2],
        '客胜_欧赔': [3.5],
        '凯利_主': [105],
        '凯利_和': [95],
        '凯利_客': [92]
    })
    
    sample_match_info = {
        'league': '英超',
        'home': '曼城',
        'away': '利物浦',
        'kickoff': '2025-11-22 20:00'
    }
    
    sample_handicap = {
        'current_handicap': -0.5,
        'current_handicap_str': '主-0.5'
    }
    
    # 生成推荐
    result = generate_recommendation_v2(
        sample_trade_data,
        sample_match_info,
        sample_handicap
    )
    
    print("=" * 60)
    print("V2引擎推荐结果")
    print("=" * 60)
    print(f"推荐方向: {result['direction']}")
    print(f"置信度: {result['confidence']:.1%}")
    print(f"建议下注: {'是' if result['should_bet'] else '否'}")
    print(f"综合评分: {result['total_score']:.1f}/100")
    print(f"风险等级: {result['risk_level']}")
    print(f"\n推荐理由:")
    for reason in result['reasons']:
        print(f"  - {reason}")
    if result['warnings']:
        print(f"\n⚠️ 警告:")
        for warning in result['warnings']:
            print(f"  {warning}")


# ============ 方式2: 双引擎对比 ============

from recommendation import HandicapRecommendationEngineX1, RecommendationEngineV2

def compare_engines(trade_df: pd.DataFrame, metadata: list, handicap_data: dict):
    """
    对比X1引擎和V2引擎的推荐结果
    """
    # X1引擎推荐
    engine_x1 = HandicapRecommendationEngineX1()
    result_x1 = engine_x1.generate_recommendation(trade_df, metadata, handicap_data)
    
    # V2引擎推荐
    engine_v2 = RecommendationEngineV2()
    result_v2 = engine_v2.generate_recommendation(trade_df, metadata, handicap_data)
    
    # 对比输出
    print("\n" + "=" * 80)
    print("双引擎对比")
    print("=" * 80)
    
    print("\n【X1引擎】")
    x1_rec = result_x1.get('最终推荐', {})
    print(f"  方向: {x1_rec.get('direction')}")
    print(f"  置信度: {x1_rec.get('confidence', 0):.1%}")
    print(f"  建议下注: {'是' if x1_rec.get('should_bet') else '否'}")
    
    print("\n【V2引擎】")
    v2_rec = result_v2.get('recommendation', {})
    v2_scores = result_v2.get('scores', {})
    print(f"  方向: {v2_rec.get('direction')}")
    print(f"  置信度: {v2_rec.get('confidence', 0):.1%}")
    print(f"  建议下注: {'是' if v2_rec.get('should_bet') else '否'}")
    print(f"  综合评分: {v2_scores.get('total_score', 0):.1f}/100")
    
    print("\n【一致性分析】")
    if x1_rec.get('direction') == v2_rec.get('direction'):
        print("  ✅ 两个引擎推荐方向一致")
    else:
        print(f"  ⚠️ 推荐方向不一致 (X1: {x1_rec.get('direction')}, V2: {v2_rec.get('direction')})")
    
    return result_x1, result_v2


# ============ 方式3: 在app.py中的路由集成 ============

"""
在app.py的推荐生成路由中添加V2引擎选项：

@app.route('/api/recommendation/v2', methods=['POST'])
def generate_recommendation_v2_route():
    try:
        data = request.json
        
        # 解析输入
        trade_df = pd.DataFrame(data['trade_data'])
        metadata = data['metadata']
        handicap_data = data.get('handicap_data', {})
        
        # 使用V2引擎
        engine_v2 = RecommendationEngineV2()
        result = engine_v2.generate_recommendation(
            trade_data=trade_df,
            metadata=metadata,
            handicap_data=handicap_data
        )
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
"""
