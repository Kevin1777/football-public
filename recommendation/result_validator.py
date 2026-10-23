"""
ResultValidator - 推荐结果验证器
验证推荐结果是否正确，计算盈亏。
Requirements: 6.2
"""
import logging
from typing import Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class BetResult(Enum):
    WIN = 'win'
    HALF_WIN = 'half_win'
    DRAW = 'draw'
    HALF_LOSE = 'half_lose'
    LOSE = 'lose'

@dataclass
class ValidationResult:
    result: str
    profit: float
    is_correct: bool
    home_score: int = 0
    away_score: int = 0
    handicap: float = 0.0
    recommendation_direction: str = ''
    score_diff: int = 0
    adjusted_diff: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'result': self.result,
            'profit': self.profit,
            'is_correct': self.is_correct,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'handicap': self.handicap,
            'recommendation_direction': self.recommendation_direction,
            'score_diff': self.score_diff,
            'adjusted_diff': self.adjusted_diff,
        }

class ResultValidator:
    WIN_PROFIT = 1.0
    HALF_WIN_PROFIT = 0.5
    DRAW_PROFIT = 0.0
    HALF_LOSE_PROFIT = -0.5
    LOSE_PROFIT = -1.0

    def __init__(self):
        pass

    def validate(self, recommendation: Dict, actual_score: Tuple[int, int], handicap: float) -> Dict:
        direction = recommendation.get('direction', 'none')
        home_score, away_score = actual_score
        if direction == 'none':
            return ValidationResult(
                result='draw', profit=0.0, is_correct=False,
                home_score=home_score, away_score=away_score,
                handicap=handicap, recommendation_direction=direction,
            ).to_dict()
        score_diff = home_score - away_score
        if direction == 'home':
            adjusted_diff = score_diff + handicap
        else:
            adjusted_diff = -score_diff - handicap
        result, profit, is_correct = self._calculate_result(adjusted_diff)
        return ValidationResult(
            result=result, profit=profit, is_correct=is_correct,
            home_score=home_score, away_score=away_score,
            handicap=handicap, recommendation_direction=direction,
            score_diff=score_diff, adjusted_diff=adjusted_diff,
        ).to_dict()

    def _calculate_result(self, adjusted_diff: float) -> Tuple[str, float, bool]:
        adjusted_diff = round(adjusted_diff, 4)
        if adjusted_diff > 0.25:
            return BetResult.WIN.value, self.WIN_PROFIT, True
        elif adjusted_diff == 0.25:
            return BetResult.HALF_WIN.value, self.HALF_WIN_PROFIT, True
        elif adjusted_diff == 0 or abs(adjusted_diff) < 0.001:
            return BetResult.DRAW.value, self.DRAW_PROFIT, False
        elif adjusted_diff == -0.25:
            return BetResult.HALF_LOSE.value, self.HALF_LOSE_PROFIT, False
        else:
            return BetResult.LOSE.value, self.LOSE_PROFIT, False

    def validate_euro_bet(self, direction: str, home_score: int, away_score: int) -> Dict:
        score_diff = home_score - away_score
        if direction == 'home':
            if score_diff > 0:
                result, profit, is_correct = BetResult.WIN.value, self.WIN_PROFIT, True
            else:
                result, profit, is_correct = BetResult.LOSE.value, self.LOSE_PROFIT, False
        else:
            if score_diff < 0:
                result, profit, is_correct = BetResult.WIN.value, self.WIN_PROFIT, True
            else:
                result, profit, is_correct = BetResult.LOSE.value, self.LOSE_PROFIT, False
        return ValidationResult(
            result=result, profit=profit, is_correct=is_correct,
            home_score=home_score, away_score=away_score, handicap=0.0,
            recommendation_direction=direction, score_diff=score_diff,
            adjusted_diff=float(score_diff) if direction == 'home' else float(-score_diff),
        ).to_dict()

    def calculate_statistics(self, results: List[Dict]) -> Dict:
        if not results:
            return {'total': 0, 'win': 0, 'half_win': 0, 'draw': 0,
                    'half_lose': 0, 'lose': 0, 'win_rate': 0.0, 'roi': 0.0, 'total_profit': 0.0}
        total = len(results)
        win = sum(1 for r in results if r.get('result') == 'win')
        half_win = sum(1 for r in results if r.get('result') == 'half_win')
        draw = sum(1 for r in results if r.get('result') == 'draw')
        half_lose = sum(1 for r in results if r.get('result') == 'half_lose')
        lose = sum(1 for r in results if r.get('result') == 'lose')
        correct = sum(1 for r in results if r.get('is_correct', False))
        total_profit = sum(r.get('profit', 0) for r in results)
        win_rate = correct / total * 100 if total > 0 else 0.0
        roi = total_profit / total * 100 if total > 0 else 0.0
        return {'total': total, 'win': win, 'half_win': half_win, 'draw': draw,
                'half_lose': half_lose, 'lose': lose, 'correct': correct,
                'win_rate': win_rate, 'roi': roi, 'total_profit': total_profit}

def validate(recommendation: Dict, actual_score: Tuple[int, int], handicap: float) -> Dict:
    validator = ResultValidator()
    return validator.validate(recommendation, actual_score, handicap)
