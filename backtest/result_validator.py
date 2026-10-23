"""
推荐结果验证器
验证推荐是否正确，计算盈亏
"""
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ResultValidator:
    """推荐结果验证器"""
    
    def __init__(self):
        # 水位默认值（如果没有实际水位）
        self.default_odds = 0.90
    
    def validate_recommendation(
        self,
        recommendation: Dict,
        actual_score: Tuple[int, int],
        actual_handicap: Optional[float] = None
    ) -> Dict:
        """
        验证推荐结果
        
        Args:
            recommendation: 推荐结果
            actual_score: 实际比分 (主队得分, 客队得分)
            actual_handicap: 实际让球数（用于验证）
            
        Returns:
            验证结果字典
        """
        try:
            final_rec = recommendation.get('最终推荐', {})
            
            # 如果不推荐下注，记录但不计算盈亏
            if not final_rec.get('should_bet'):
                return {
                    'validated': True,
                    'recommended': False,
                    'result': 'NO_BET',
                    'reason': final_rec.get('reason', 'N/A'),
                    'profit': 0.0,
                    'message': '未推荐下注'
                }
            
            # 提取推荐信息
            recommended_handicap = final_rec.get('handicap')
            direction = final_rec.get('direction', '')
            confidence = final_rec.get('confidence', 0)
            
            if recommended_handicap is None:
                return {
                    'validated': False,
                    'error': '推荐盘口数据缺失'
                }
            
            # 🔥 转换盘口为float（可能是字符串格式）
            try:
                if isinstance(recommended_handicap, str):
                    recommended_handicap = float(recommended_handicap)
                elif not isinstance(recommended_handicap, (int, float)):
                    raise ValueError(f"无效的盘口格式: {type(recommended_handicap)}")
            except (ValueError, TypeError) as e:
                return {
                    'validated': False,
                    'error': f'推荐盘口格式错误: {recommended_handicap} ({e})'
                }
            
            # 计算实际让球结果
            home_score, away_score = actual_score
            
            # 根据推荐的盘口计算结果
            result = self._calculate_handicap_result(
                home_score, 
                away_score, 
                recommended_handicap,
                direction
            )
            
            # 计算盈亏
            profit = self._calculate_profit(result, confidence)
            
            # 生成验证报告
            validation_result = {
                'validated': True,
                'recommended': True,
                'result': result,  # WIN / LOSE / HALF_WIN / HALF_LOSE / DRAW
                'profit': profit,
                'actual_score': f"{home_score}:{away_score}",
                'recommended_handicap': recommended_handicap,
                'recommended_direction': direction,
                'confidence': confidence,
                'message': self._generate_message(result, profit)
            }
            
            return validation_result
            
        except Exception as e:
            logger.exception("验证推荐结果失败")
            return {
                'validated': False,
                'error': str(e)
            }
    
    def _calculate_handicap_result(
        self,
        home_score: int,
        away_score: int,
        handicap: float,
        direction: str
    ) -> str:
        """
        计算让球盘口结果
        
        Args:
            home_score: 主队得分
            away_score: 客队得分
            handicap: 让球数（正数=主队让球，负数=主队受让）
            direction: 推荐方向
            
        Returns:
            结果：WIN / LOSE / HALF_WIN / HALF_LOSE / DRAW
        """
        # 计算让球后的比分
        # 如果推荐"客队受让"，实际是买客队+盘口
        # 如果推荐"主队让球"，实际是买主队-盘口
        
        # 判断推荐的是哪一方
        if "客队" in direction or "客" in direction:
            # 买客队
            # 客队实际得分 + abs(handicap)（因为是受让）
            effective_away = away_score - handicap  # handicap是负数时，相当于加分
            diff = effective_away - home_score
        else:
            # 买主队
            # 主队实际得分 - handicap（让球）
            effective_home = home_score + handicap  # handicap可能是负数
            diff = effective_home - away_score
        
        # 判断结果
        if abs(diff) < 0.01:
            return "DRAW"  # 走水
        elif diff > 0.25:
            return "WIN"  # 赢
        elif diff < -0.25:
            return "LOSE"  # 输
        elif 0 < diff <= 0.25:
            return "HALF_WIN"  # 赢半
        else:  # -0.25 <= diff < 0
            return "HALF_LOSE"  # 输半
    
    def _calculate_profit(self, result: str, confidence: float) -> float:
        """
        计算盈亏
        
        Args:
            result: 比赛结果
            confidence: 推荐置信度
            
        Returns:
            盈亏金额（以1为单位）
        """
        # 根据置信度决定下注金额（这里简化为1单位）
        stake = 1.0
        
        # 水位（简化为0.90）
        odds = self.default_odds
        
        if result == "WIN":
            return stake * odds  # 赢得水位金额
        elif result == "LOSE":
            return -stake  # 输掉本金
        elif result == "HALF_WIN":
            return stake * odds * 0.5  # 赢一半
        elif result == "HALF_LOSE":
            return -stake * 0.5  # 输一半
        elif result == "DRAW":
            return 0.0  # 走水，不输不赢
        else:
            return 0.0
    
    def _generate_message(self, result: str, profit: float) -> str:
        """生成验证消息"""
        messages = {
            "WIN": f"✅ 推荐正确（赢），盈利 {profit:+.2f}",
            "LOSE": f"❌ 推荐错误（输），亏损 {profit:+.2f}",
            "HALF_WIN": f"✅ 推荐半赢，盈利 {profit:+.2f}",
            "HALF_LOSE": f"❌ 推荐半输，亏损 {profit:+.2f}",
            "DRAW": "➖ 走水，不输不赢"
        }
        return messages.get(result, "未知结果")
    
    def calculate_statistics(self, results: list) -> Dict:
        """
        计算统计数据
        
        Args:
            results: 验证结果列表
            
        Returns:
            统计数据
        """
        stats = {
            'total': len(results),
            'recommended': 0,
            'win': 0,
            'lose': 0,
            'half_win': 0,
            'half_lose': 0,
            'draw': 0,
            'no_bet': 0,
            'total_profit': 0.0,
            'win_rate': 0.0,
            'roi': 0.0
        }
        
        for result in results:
            if not result.get('validated'):
                continue
            
            if not result.get('recommended'):
                stats['no_bet'] += 1
                continue
            
            stats['recommended'] += 1
            
            result_type = result.get('result', '')
            profit = result.get('profit', 0.0)
            
            stats['total_profit'] += profit
            
            if result_type == 'WIN':
                stats['win'] += 1
            elif result_type == 'LOSE':
                stats['lose'] += 1
            elif result_type == 'HALF_WIN':
                stats['half_win'] += 1
            elif result_type == 'HALF_LOSE':
                stats['half_lose'] += 1
            elif result_type == 'DRAW':
                stats['draw'] += 1
        
        # 计算胜率（赢+半赢）/ 推荐总数
        if stats['recommended'] > 0:
            win_count = stats['win'] + stats['half_win'] * 0.5
            stats['win_rate'] = (win_count / stats['recommended']) * 100
            
            # ROI = 总盈利 / 总投入
            total_stake = stats['recommended']  # 每场1单位
            stats['roi'] = (stats['total_profit'] / total_stake) * 100 if total_stake > 0 else 0
        
        return stats


# 模块导出
__all__ = ['ResultValidator']
