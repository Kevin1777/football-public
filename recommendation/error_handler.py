"""
ErrorHandler - 异常处理和熔断机制

提供统一的异常处理和熔断返回机制。

Requirements: 8.3, 8.4, 8.5
"""

import logging
import functools
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# 版本信息
VERSION = "7.2.1"
BUILD_DATE = "2025-12-11"


@dataclass
class CircuitBreakerResult:
    """熔断结果"""
    direction: str = 'none'
    confidence: float = 0.0
    reason: str = '熔断保护'
    is_circuit_breaker: bool = True
    error_message: str = ''
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'direction': self.direction,
            'confidence': self.confidence,
            'reason': self.reason,
            'is_circuit_breaker': self.is_circuit_breaker,
            'error_message': self.error_message,
        }


class ErrorHandler:
    """
    异常处理器
    
    提供统一的异常捕获和熔断返回机制。
    """
    
    def __init__(self):
        """初始化异常处理器"""
        self.error_count = 0
        self.last_error_time: Optional[datetime] = None
        self.startup_logged = False

    def handle_exception(self, exception: Exception, context: str = '') -> Dict:
        """
        处理异常并返回熔断结果
        
        Args:
            exception: 捕获的异常
            context: 异常上下文描述
            
        Returns:
            熔断结果字典
        """
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        error_msg = f"{context}: {str(exception)}" if context else str(exception)
        logger.error(f"[熔断] {error_msg}")
        
        return CircuitBreakerResult(
            direction='none',
            confidence=0.0,
            reason=f'异常熔断: {context}' if context else '异常熔断',
            is_circuit_breaker=True,
            error_message=error_msg,
        ).to_dict()
    
    def create_fallback_result(self, reason: str = '降级处理') -> Dict:
        """
        创建降级结果
        
        Args:
            reason: 降级原因
            
        Returns:
            降级结果字典
        """
        logger.warning(f"[降级] {reason}")
        
        return CircuitBreakerResult(
            direction='none',
            confidence=0.0,
            reason=reason,
            is_circuit_breaker=True,
            error_message='',
        ).to_dict()
    
    def log_startup(self, data_source_status: Dict = None):
        """
        记录启动日志
        
        Args:
            data_source_status: 数据源状态字典
        """
        if self.startup_logged:
            return
        
        logger.info("=" * 60)
        logger.info(f"推荐引擎启动 - 版本: {VERSION}")
        logger.info(f"构建日期: {BUILD_DATE}")
        
        if data_source_status:
            logger.info("数据源状态:")
            for source, status in data_source_status.items():
                status_str = "✅ 正常" if status else "❌ 异常"
                logger.info(f"  - {source}: {status_str}")
        
        logger.info("=" * 60)
        self.startup_logged = True
    
    def get_version_info(self) -> Dict:
        """
        获取版本信息
        
        Returns:
            版本信息字典
        """
        return {
            'version': VERSION,
            'build_date': BUILD_DATE,
            'error_count': self.error_count,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
        }
    
    def reset_error_count(self):
        """重置错误计数"""
        self.error_count = 0
        self.last_error_time = None


def circuit_breaker(context: str = ''):
    """
    熔断装饰器
    
    捕获函数异常并返回熔断结果。
    
    Args:
        context: 异常上下文描述
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = ErrorHandler()
                return handler.handle_exception(e, context or func.__name__)
        return wrapper
    return decorator


def safe_get(data: Dict, key: str, default: Any = 0) -> Any:
    """
    安全获取字典值
    
    Args:
        data: 数据字典
        key: 键名
        default: 默认值
        
    Returns:
        获取的值或默认值
    """
    try:
        value = data.get(key, default)
        if value is None:
            return default
        return value
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全转换为浮点数
    
    Args:
        value: 要转换的值
        default: 默认值
        
    Returns:
        转换后的浮点数或默认值
    """
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
            if not value:
                return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全转换为整数
    
    Args:
        value: 要转换的值
        default: 默认值
        
    Returns:
        转换后的整数或默认值
    """
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


class HandicapFallback:
    """
    盘口数据降级处理
    
    当盘口数据获取失败时，提供降级处理逻辑。
    """
    
    @staticmethod
    def get_fallback_handicap(metrics: Dict) -> Dict:
        """
        获取降级盘口数据
        
        Args:
            metrics: 比赛指标
            
        Returns:
            降级盘口数据
        """
        logger.warning("[降级] 使用基础盘口数据")
        
        return {
            'handicap': 0.0,
            'handicap_home_odds': 1.90,
            'handicap_away_odds': 1.90,
        }
