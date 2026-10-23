"""推荐引擎模块

包含：
- X1JSONRecommender: X1 JSON数据推荐引擎
- VISFormatter: VIS格式化输出 (如果有)
"""

from .x1_json_recommender import X1JSONRecommender

__all__ = [
    'X1JSONRecommender'
]
