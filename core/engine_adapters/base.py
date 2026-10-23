"""
推荐引擎基础适配器
定义统一接口和标准结果格式
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StandardResult:
    """
    标准化推荐结果
    所有引擎适配器必须返回此格式
    """
    success: bool = False
    engine: str = "unknown"
    
    # 熔断信息
    meltdown: bool = False
    meltdown_reason: str = ""
    
    # 推荐信息
    direction: str = "none"  # home / away / none
    confidence: float = 0.0  # 0-1
    handicap: str = ""
    reason: str = ""
    should_bet: bool = False
    
    # 引擎特有的详细信息
    details: Dict[str, Any] = field(default_factory=dict)
    
    # 原始结果（调试用）
    raw_result: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'engine': self.engine,
            'meltdown': self.meltdown,
            'meltdown_reason': self.meltdown_reason,
            'recommendation': self.direction,
            'confidence': self.confidence,
            'handicap': self.handicap,
            'reason': self.reason,
            'should_bet': self.should_bet,
            'details': self.details,
        }
    
    def to_push_format(self) -> Dict[str, Any]:
        """转换为推送消息需要的格式（兼容旧代码）"""
        return {
            'success': self.success,
            'recommendation': self.direction,
            'should_bet': self.should_bet,
            'confidence': self.confidence,
            'reason': self.reason,
            'handicap': self.handicap,
            'meltdown': self.meltdown,
            'meltdown_reason': self.meltdown_reason,
            'scores': self.details.get('scores', {}),
            'funding_level': self.details.get('funding_level', {}),
            'risk_control': self.details.get('risk_control', {}),
            'x1_result': self.raw_result,
        }


class BaseEngineAdapter(ABC):
    """
    推荐引擎基础适配器
    所有引擎适配器必须继承此类
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器
        
        Args:
            config: 引擎配置
        """
        self.config = config or {}
        self._initialized = False
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """引擎名称"""
        pass
    
    @property
    @abstractmethod
    def engine_version(self) -> str:
        """引擎版本"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化引擎
        
        Returns:
            是否初始化成功
        """
        pass
    
    @abstractmethod
    def recommend(self, match_file: str) -> StandardResult:
        """
        执行推荐分析
        
        Args:
            match_file: 比赛数据文件路径
            
        Returns:
            标准化推荐结果
        """
        pass
    
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        return self._initialized
    
    def get_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            'name': self.engine_name,
            'version': self.engine_version,
            'available': self.is_available(),
            'config': {k: v for k, v in self.config.items() if not k.startswith('_')},
        }
