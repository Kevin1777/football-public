"""
优化推荐引擎（V2 - 集成820场回测优化）
基于盘口特征分析的结果，提供带有置信度的让球盘口推荐
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List

# 🔥 优化引擎版本控制
USE_V9_OPTIMIZATION = False
USE_V8_OPTIMIZATION = False
USE_V7_OPTIMIZATION = False
USE_V6_OPTIMIZATION = False
USE_V5_OPTIMIZATION = False
USE_V4_OPTIMIZATION = False
USE_V3_OPTIMIZATION = False
USE_V2_OPTIMIZATION = False

# V9联赛筛选版（开发中，暂时禁用）
# try:
#     from recommendation.V9联赛筛选配置 import (
#         V9_LEAGUE_FILTER_CONFIG,
#         should_recommend_v9
#     )
#     USE_V9_OPTIMIZATION = True
#     print("✅ 已加载V9联赛筛选配置（成交量≥80行+联赛质量筛选）")
# except ImportError:
#     pass

if not USE_V9_OPTIMIZATION:
    # V8增量版（备选方案，暂时禁用，优先使用V7）
    # try:
    #     from recommendation.V8增量配置 import (
    #         V8_INCREMENTAL_CONFIG,
    #         should_recommend_v8
    #     )
    #     USE_V8_OPTIMIZATION = True
    #     print("⚠️ 使用V8增量配置（成交量≥180行，目标85+场次）")
    # except ImportError:
    #     pass
    pass

if not USE_V9_OPTIMIZATION and not USE_V8_OPTIMIZATION:
    # V7简化版（修复档位匹配问题）
    try:
        from recommendation.V7简化配置 import (
            V7_SIMPLIFIED_CONFIG,
            should_recommend_v7
        )
        USE_V7_OPTIMIZATION = True
        print("✅ 已加载V7简化配置（69.44%准确率，32.4% ROI - 当前最优方案！）")
    except ImportError:
        pass

# V6也暂时禁用（场次比V5少）
# if not USE_V7_OPTIMIZATION:
#     try:
#         from recommendation.V6最佳平衡配置 import (
#             V6_BALANCE_CONFIG,
#             should_recommend_v6
#         )
#         USE_V6_OPTIMIZATION = True
#         print("⚠️ 使用V6最佳平衡配置（68.8%准确率+更多场次）")
#     except ImportError:
#         pass

if not USE_V8_OPTIMIZATION and not USE_V7_OPTIMIZATION and not USE_V6_OPTIMIZATION:
    try:
        from recommendation.V5成交额优先配置 import (
            V5_VOLUME_FIRST_CONFIG,
            should_recommend_v5
        )
        USE_V5_OPTIMIZATION = True
        print("⚠️ 使用V5成交额优先配置（63.83%准确率，22.8% ROI - 最佳平衡）")
    except ImportError:
        pass

if not USE_V8_OPTIMIZATION and not USE_V7_OPTIMIZATION and not USE_V6_OPTIMIZATION and not USE_V5_OPTIMIZATION:
    try:
        from recommendation.V4超高准确率配置 import (
            V4_ULTRA_PRECISION_CONFIG,
            should_recommend_v4
        )
        USE_V4_OPTIMIZATION = True
        print("⚠️ 使用V4超高准确率配置（目标70%+胜率）")
    except ImportError:
        pass

if not USE_V8_OPTIMIZATION and not USE_V7_OPTIMIZATION and not USE_V6_OPTIMIZATION and not USE_V5_OPTIMIZATION and not USE_V4_OPTIMIZATION:
    try:
        from recommendation.V3优化配置 import (
            V3_OPTIMIZED_CONFIG,
            V3_INSIGHTS,
            calculate_v3_confidence
        )
        USE_V3_OPTIMIZATION = True
        print("⚠️ 使用V3配置（82.4%黄金组合）")
    except ImportError:
        pass

if not USE_V8_OPTIMIZATION and not USE_V7_OPTIMIZATION and not USE_V6_OPTIMIZATION and not USE_V5_OPTIMIZATION and not USE_V4_OPTIMIZATION and not USE_V3_OPTIMIZATION:
    try:
        from recommendation.优化配置 import OPTIMIZED_CONFIG
        USE_V2_OPTIMIZATION = True
        print("⚠️ 使用V2配置")
    except:
        print("⚠️ 未找到优化配置，使用默认规则")

class OptimizedRecommendationEngine:
    """优化的推荐引擎"""
    
    def __init__(self):
        # 加载特征分析结果
        feature_file = Path(__file__).parent / "盘口特征分析结果.json"
        if feature_file.exists():
            with open(feature_file, 'r', encoding='utf-8') as f:
                self.features = json.load(f)
        else:
            self.features = {}
        
        # 基于分析结果的规则权重
        self.rules = {
            '升盘_主胜': {
                'weight': 5.0,  # 最高权重（60.4%准确率）
                'description': '升盘强烈信号，历史主胜率60.4%'
            },
            '降盘_客胜': {
                'weight': 3.0,  # 中等权重（41.0%准确率）
                'description': '降盘中等信号，历史客胜率41.0%'
            },
            '稳盘': {
                'weight': 1.0,  # 基础权重
                'description': '盘口稳定，需结合其他指标'
            },
            '水位变化': {
                'weight': 2.0,
                'description': '水位变化反映市场预期'
            },
            '成交额': {
                'weight': 1.5,
                'description': '成交额反映市场活跃度'
            }
        }
    
    def analyze_match(self, match_data: Dict, trade_data=None) -> Dict:
        """
        分析单场比赛并给出推荐
        
        Args:
            match_data: 比赛数据（包含handicap_data）
            trade_data: 交易明细数据（V5需要用于判断成交量）
        
        Returns:
            推荐结果
        """
        handicap_data = match_data.get('handicap_data', {})
        
        if not handicap_data or not handicap_data.get('initial_handicap_text'):
            return {
                'success': False,
                'message': '缺少盘口数据'
            }
        
        # 提取特征
        initial_handicap = handicap_data.get('initial_handicap', 0)
        current_handicap = handicap_data.get('current_handicap', 0)
        handicap_change = current_handicap - initial_handicap
        
        initial_home_odds = handicap_data.get('initial_home_odds', 0)
        initial_away_odds = handicap_data.get('initial_away_odds', 0)
        current_home_odds = handicap_data.get('current_home_odds', 0)
        current_away_odds = handicap_data.get('current_away_odds', 0)
        
        odds_change_home = current_home_odds - initial_home_odds
        odds_change_away = current_away_odds - initial_away_odds
        
        total_volume = match_data.get('total_volume', 0)
        
        # 判断盘口趋势
        if handicap_change < -0.01:
            trend = '升盘'
        elif handicap_change > 0.01:
            trend = '降盘'
        else:
            trend = '稳盘'
        
        # 计算各方向的信号强度
        home_score = 0
        away_score = 0
        signals = []
        
        # ==========================================
        # 规则1：盘口变化（最重要）
        # ==========================================
        if trend == '升盘':
            # 升盘 → 主胜信号（60.4%准确率）
            home_score += self.rules['升盘_主胜']['weight']
            signals.append({
                'factor': '盘口变化',
                'signal': '升盘',
                'direction': '主队',
                'confidence': '⭐⭐⭐⭐⭐ 非常强',
                'weight': self.rules['升盘_主胜']['weight'],
                'reason': '升盘强烈利好主队（历史主胜率60.4%）'
            })
        
        elif trend == '降盘':
            # 降盘 → 客胜信号（41.0%准确率）
            away_score += self.rules['降盘_客胜']['weight']
            signals.append({
                'factor': '盘口变化',
                'signal': '降盘',
                'direction': '客队',
                'confidence': '⭐⭐⭐ 中等',
                'weight': self.rules['降盘_客胜']['weight'],
                'reason': '降盘利好客队（历史客胜率41.0%）'
            })
        
        else:
            # 稳盘 → 需结合其他指标
            signals.append({
                'factor': '盘口变化',
                'signal': '稳盘',
                'direction': '不明确',
                'confidence': '⭐ 弱',
                'weight': self.rules['稳盘']['weight'],
                'reason': '盘口稳定，需结合水位等其他指标'
            })
        
        # ==========================================
        # 规则2：水位变化
        # ==========================================
        if abs(odds_change_home) > 0.05 or abs(odds_change_away) > 0.05:
            # 主队水位下降 → 市场看好主队
            if odds_change_home < -0.05:
                home_score += self.rules['水位变化']['weight']
                signals.append({
                    'factor': '水位变化',
                    'signal': f'主队水位降低{odds_change_home:.2f}',
                    'direction': '主队',
                    'confidence': '⭐⭐ 较强',
                    'weight': self.rules['水位变化']['weight'],
                    'reason': '主队水位下降，市场资金倾向主队'
                })
            
            # 客队水位下降 → 市场看好客队
            if odds_change_away < -0.05:
                away_score += self.rules['水位变化']['weight']
                signals.append({
                    'factor': '水位变化',
                    'signal': f'客队水位降低{odds_change_away:.2f}',
                    'direction': '客队',
                    'confidence': '⭐⭐ 较强',
                    'weight': self.rules['水位变化']['weight'],
                    'reason': '客队水位下降，市场资金倾向客队'
                })
        
        # ==========================================
        # 规则3：成交额（高成交额增加可信度）
        # ==========================================
        if total_volume > 15000:  # 根据分析结果的中位数
            confidence_bonus = 0.2
            signals.append({
                'factor': '成交额',
                'signal': f'高成交额{total_volume:.0f}',
                'direction': '增强可信度',
                'confidence': '⭐⭐ 辅助',
                'weight': self.rules['成交额']['weight'],
                'reason': f'成交额{total_volume:.0f}较高，市场活跃，信号更可靠'
            })
        else:
            confidence_bonus = 0
        
        # ==========================================
        # 生成最终推荐（具体让球盘口）
        # ==========================================
        
        # 获取即时盘口
        current_handicap_text = handicap_data.get('current_handicap_text', '')
        current_handicap_value = current_handicap
        
        # 判断推荐方向和具体盘口
        # 🔥 V2优化：降低信号强度阈值，从>2改为>=1（更宽松）
        if home_score > away_score and home_score >= 1.0:
            # 推荐主队
            if current_handicap_value < 0:
                # 主队让球
                recommendation = f'主队 {current_handicap_value:.2f}'
                bet_description = f'主队让{abs(current_handicap_value):.2f}球'
            else:
                # 主队受让
                recommendation = f'主队 +{current_handicap_value:.2f}'
                bet_description = f'主队受让{current_handicap_value:.2f}球'
            
            confidence = min(home_score / 10 + confidence_bonus, 1.0)
            should_bet = confidence > 0.4  # V2：降低初始阈值
        
        elif away_score > home_score and away_score >= 1.0:
            # 推荐客队
            if current_handicap_value > 0:
                # 客队让球（相当于主队受让）
                recommendation = f'客队 {abs(current_handicap_value):.2f}'
                bet_description = f'客队让{current_handicap_value:.2f}球'
            else:
                # 客队受让（相当于主队让球）
                recommendation = f'客队 +{abs(current_handicap_value):.2f}'
                bet_description = f'客队受让{abs(current_handicap_value):.2f}球'
            
            confidence = min(away_score / 10 + confidence_bonus, 1.0)
            should_bet = confidence > 0.35  # V2：客队阈值更低
        
        else:
            recommendation = '不推荐'
            bet_description = '信号不明确'
            confidence = 0
            should_bet = False
        
        # 生成推荐理由
        main_signals = [s for s in signals if s['weight'] >= 2.0]
        if main_signals:
            reason = ' + '.join([s['reason'] for s in main_signals])
        else:
            reason = '信号不明确，建议观望'
        
        # 🔥 V9联赛筛选优化：用联赛质量替代成交量限制
        original_confidence = confidence
        adjustment_reasons = []
        version = 'V9-LeagueFilter' if USE_V9_OPTIMIZATION else ('V8-Incremental' if USE_V8_OPTIMIZATION else ('V7-Simplified' if USE_V7_OPTIMIZATION else ('V6-BestBalance' if USE_V6_OPTIMIZATION else ('V5-VolumeFirst' if USE_V5_OPTIMIZATION else ('V4-UltraPrecision' if USE_V4_OPTIMIZATION else ('V3-Golden' if USE_V3_OPTIMIZATION else 'V2-Optimized'))))))
        
        if USE_V9_OPTIMIZATION:
            # V9策略：成交量≥80行 + 联赛质量筛选
            if isinstance(trade_data, pd.DataFrame) and len(trade_data) > 0:
                volume_rows = len(trade_data)
            else:
                volume_rows = 0
            
            # 获取联赛信息
            league = match_data.get('league', '') or match_data.get('competition', '')
            
            match_features = {
                'volume_rows': volume_rows,
                'handicap': current_handicap_value,
                'handicap_change': handicap_change,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
                'league': league,  # V9新增：传递联赛信息
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v9(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V9过滤：{'；'.join(reasons)}"
            else:
                # V9接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V8_OPTIMIZATION:
            # V8策略：成交量≥180行，增加场次
            if isinstance(trade_data, pd.DataFrame) and len(trade_data) > 0:
                volume_rows = len(trade_data)
            else:
                volume_rows = 0
            
            match_features = {
                'volume_rows': volume_rows,
                'handicap': current_handicap_value,
                'handicap_change': handicap_change,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v8(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V8过滤：{'；'.join(reasons)}"
            else:
                # V8接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V7_OPTIMIZATION:
            # V7简化策略：成交量≥200行
            if isinstance(trade_data, pd.DataFrame) and len(trade_data) > 0:
                volume_rows = len(trade_data)
            else:
                volume_rows = 0
            
            match_features = {
                'volume_rows': volume_rows,
                'handicap': current_handicap_value,
                'handicap_change': handicap_change,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v7(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V7过滤：{'；'.join(reasons)}"
            else:
                # V7接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V6_OPTIMIZATION:
            # V6策略：降低成交额门槛，扩大覆盖面，同时保持高准确率
            if isinstance(trade_data, pd.DataFrame) and len(trade_data) > 0:
                volume_rows = len(trade_data)
            else:
                volume_rows = 0
            
            match_features = {
                'volume_rows': volume_rows,
                'handicap_change': handicap_change,
                'trend': trend,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v6(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V6最佳平衡过滤：{'；'.join(reasons)}"
            else:
                # V6接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V5_OPTIMIZATION:
            # V5策略：成交额预筛选 + 精准特征
            # 计算交易数据行数
            if isinstance(trade_data, pd.DataFrame) and len(trade_data) > 0:
                volume_rows = len(trade_data)
            else:
                volume_rows = 0
            
            match_features = {
                'volume_rows': volume_rows,
                'handicap_change': handicap_change,
                'trend': trend,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v5(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V5成交额优先过滤：{'；'.join(reasons)}"
            else:
                # V5接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V4_OPTIMIZATION:
            # V4策略：极致精准，只接受最优组合
            match_features = {
                'handicap': current_handicap_value,
                'handicap_change': handicap_change,
                'is_home': '主队' in recommendation,
                'confidence': confidence,
                'trend': trend,
            }
            
            should_bet, confidence, tier, reasons = should_recommend_v4(match_features)
            adjustment_reasons = reasons
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V4超高准确率过滤：{'；'.join(reasons)}"
            else:
                # V4接受，添加档位信息
                reason = f"{tier} - " + reason if tier else reason
        
        elif USE_V3_OPTIMIZATION:
            # 使用V3的高级置信度计算
            match_features = {
                'handicap': current_handicap_value,
                'handicap_change': handicap_change,
                'trend': trend,
                'direction': recommendation,
            }
            
            confidence, adjustment_reasons = calculate_v3_confidence(confidence, match_features)
            
            # V3阈值：60%起步
            threshold = V3_OPTIMIZED_CONFIG['confidence_threshold']['minimum']
            should_bet = confidence >= threshold
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V3优化后置信度不足（{confidence*100:.1f}% < {threshold*100:.0f}%）"
        
        elif USE_V2_OPTIMIZATION:
            # V2逻辑保持不变
            config = OPTIMIZED_CONFIG
            abs_handicap = abs(current_handicap_value)
            
            if abs_handicap <= config['handicap_filter']['small_handicap_max']:
                bonus = config['confidence_adjustment']['bonus_conditions']['small_handicap']
                confidence += bonus
                adjustment_reasons.append(f"✅ 小盘口加成 +{bonus*100:.0f}%")
            elif config['handicap_filter']['avoid_medium']:
                min_h, max_h = config['handicap_filter']['medium_handicap_range']
                if min_h <= abs_handicap <= max_h:
                    penalty = config['confidence_adjustment']['penalty_conditions']['medium_handicap']
                    confidence += penalty
                    adjustment_reasons.append(f"⚠️ 中盘口惩罚 {penalty*100:.0f}%")
            
            if total_volume < config['volume_filter']['min_volume']:
                penalty = config['confidence_adjustment']['penalty_conditions']['very_low_volume']
                confidence += penalty
                adjustment_reasons.append(f"⚠️ 极低成交量 {penalty*100:.0f}%")
            elif total_volume >= 1000000:
                bonus = config['confidence_adjustment']['bonus_conditions']['high_volume']
                confidence += bonus
                adjustment_reasons.append(f"✅ 高成交量加成 +{bonus*100:.0f}%")
            
            if trend == '降盘' and config['trend_filter']['avoid_falling']:
                penalty = config['confidence_adjustment']['penalty_conditions']['falling_handicap']
                confidence += penalty
                adjustment_reasons.append(f"⚠️ 降盘惩罚 {penalty*100:.0f}%")
            
            confidence = max(0.0, min(1.0, confidence))
            threshold = config['confidence_adjustment']['base_threshold']
            should_bet = confidence >= threshold
            
            if not should_bet:
                recommendation = '不推荐'
                bet_description = '观望'
                reason = f"V2优化后置信度不足（{confidence*100:.1f}% < {threshold*100:.0f}%）"
        
        return {
            'success': True,
            'recommendation': recommendation,
            'bet_description': bet_description if should_bet else '观望',
            'current_handicap': current_handicap_value,
            'current_handicap_text': current_handicap_text,
            'should_bet': should_bet,
            'confidence': confidence,
            'original_confidence': original_confidence,
            'adjustment_reasons': adjustment_reasons,
            'home_score': home_score,
            'away_score': away_score,
            'handicap_trend': trend,
            'handicap_change': handicap_change,
            'signals': signals,
            'reason': reason,
            'version': version,
            'summary': f"{'✅ 推荐下注' if should_bet else '❌ 不推荐'}: {recommendation} (置信度{confidence*100:.0f}%)"
        }
    
    def format_recommendation(self, result: Dict, match_info: Dict) -> str:
        """格式化推荐结果为可读文本"""
        if not result['success']:
            return f"❌ {result['message']}"
        
        output = []
        output.append("=" * 80)
        output.append("【优化推荐结果】")
        output.append("=" * 80)
        output.append(f"比赛: {match_info.get('home_team')} vs {match_info.get('away_team')}")
        output.append(f"联赛: {match_info.get('league')}")
        output.append("")
        
        output.append(result['summary'])
        output.append(f"投注方向: {result['bet_description']}")
        output.append(f"即时盘口: {result['current_handicap_text']} ({result['current_handicap']:.2f})")
        output.append(f"置信度: {result['confidence']*100:.0f}%")
        output.append("")
        
        output.append("【信号分析】")
        for signal in result['signals']:
            confidence_stars = signal['confidence']
            output.append(f"  {confidence_stars} {signal['factor']}: {signal['signal']}")
            output.append(f"      → {signal['reason']}")
        
        output.append("")
        output.append("【盘口详情】")
        output.append(f"  趋势: {result['handicap_trend']} ({result['handicap_change']:+.2f})")
        output.append(f"  主队得分: {result['home_score']:.1f}")
        output.append(f"  客队得分: {result['away_score']:.1f}")
        output.append("")
        output.append(f"【综合评估】")
        output.append(f"  {result['reason']}")
        output.append("=" * 80)
        
        return "\n".join(output)


# 测试函数
def test_engine():
    """测试优化引擎"""
    print("测试优化推荐引擎...")
    print()
    
    # 加载一场比赛测试
    data_dir = Path(__file__).parent / "data" / "2025" / "11"
    json_files = list(data_dir.rglob("*.json"))
    json_files = [f for f in json_files if f.name not in ["盘口数据.json", "标盘指数_latest.json"]]
    
    if not json_files:
        print("没有找到测试数据")
        return
    
    engine = OptimizedRecommendationEngine()
    
    # 测试前3场比赛
    for i, json_file in enumerate(json_files[:3], 1):
        with open(json_file, 'r', encoding='utf-8') as f:
            match_data = json.load(f)
        
        match_info = match_data.get('match_info', {})
        result = engine.analyze_match(match_data)
        
        print(engine.format_recommendation(result, match_info))
        print()


if __name__ == '__main__':
    test_engine()
