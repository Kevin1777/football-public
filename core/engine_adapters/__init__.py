"""
推荐引擎适配器模块
统一管理不同的推荐引擎，提供标准化接口
"""

from .base import BaseEngineAdapter, StandardResult
from .x1_adapter import X1EngineAdapter

__all__ = [
    'BaseEngineAdapter',
    'StandardResult', 
    'X1EngineAdapter',
]
