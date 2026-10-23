"""
推荐引擎管理器
统一管理所有推荐引擎，提供切换和对比功能
"""

import logging
from typing import Dict, Any, Optional, List, Type
from pathlib import Path

from .engine_adapters.base import BaseEngineAdapter, StandardResult
from .engine_adapters.x1_adapter import X1EngineAdapter

logger = logging.getLogger(__name__)


# 注册的引擎适配器
REGISTERED_ENGINES: Dict[str, Type[BaseEngineAdapter]] = {
    'x1': X1EngineAdapter,
    # 未来可以添加更多引擎:
    # 'ai_v2': AIv2EngineAdapter,
    # 'ensemble': EnsembleEngineAdapter,
}


class EngineManager:
    """
    推荐引擎管理器
    
    功能：
    1. 管理多个推荐引擎
    2. 提供统一的推荐接口
    3. 支持引擎切换
    4. 支持多引擎对比
    """
    
    _instance = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._engines: Dict[str, BaseEngineAdapter] = {}
        self._current_engine: str = 'x1'  # 默认使用X1引擎
        self._config: Dict[str, Any] = {}
        self._initialized = True
        
        logger.info("🔧 推荐引擎管理器初始化")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置管理器
        
        Args:
            config: 配置字典，例如：
                {
                    'default_engine': 'x1',
                    'engines': {
                        'x1': {'confidence_threshold': 0.85},
                    }
                }
        """
        self._config = config
        self._current_engine = config.get('default_engine', 'x1')
        logger.info(f"📋 引擎管理器配置更新，默认引擎: {self._current_engine}")
    
    def register_engine(self, name: str, adapter_class: Type[BaseEngineAdapter]) -> None:
        """
        注册新的引擎适配器
        
        Args:
            name: 引擎标识
            adapter_class: 适配器类
        """
        REGISTERED_ENGINES[name] = adapter_class
        logger.info(f"📝 注册引擎: {name}")
    
    def initialize_engine(self, engine_name: str) -> bool:
        """
        初始化指定引擎
        
        Args:
            engine_name: 引擎标识
            
        Returns:
            是否初始化成功
        """
        if engine_name in self._engines:
            return self._engines[engine_name].is_available()
        
        if engine_name not in REGISTERED_ENGINES:
            logger.error(f"❌ 未知引擎: {engine_name}")
            return False
        
        try:
            # 获取引擎配置
            engine_config = self._config.get('engines', {}).get(engine_name, {})
            
            # 创建并初始化引擎
            adapter_class = REGISTERED_ENGINES[engine_name]
            adapter = adapter_class(config=engine_config)
            
            if adapter.initialize():
                self._engines[engine_name] = adapter
                logger.info(f"✅ 引擎 {engine_name} 初始化成功")
                return True
            else:
                logger.warning(f"⚠️ 引擎 {engine_name} 初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 初始化引擎 {engine_name} 异常: {e}")
            return False
    
    def get_engine(self, engine_name: Optional[str] = None) -> Optional[BaseEngineAdapter]:
        """
        获取引擎实例
        
        Args:
            engine_name: 引擎标识，None则返回当前默认引擎
            
        Returns:
            引擎适配器实例
        """
        name = engine_name or self._current_engine
        
        # 如果引擎未初始化，尝试初始化
        if name not in self._engines:
            self.initialize_engine(name)
        
        return self._engines.get(name)
    
    def set_current_engine(self, engine_name: str) -> bool:
        """
        设置当前使用的引擎
        
        Args:
            engine_name: 引擎标识
            
        Returns:
            是否设置成功
        """
        if engine_name not in REGISTERED_ENGINES:
            logger.error(f"❌ 未知引擎: {engine_name}")
            return False
        
        self._current_engine = engine_name
        logger.info(f"🔄 切换当前引擎: {engine_name}")
        return True
    
    def recommend(self, match_file: str, engine_name: Optional[str] = None) -> StandardResult:
        """
        执行推荐分析（统一入口）
        
        Args:
            match_file: 比赛数据文件路径
            engine_name: 指定使用的引擎，None则使用当前默认引擎
            
        Returns:
            标准化推荐结果
        """
        engine = self.get_engine(engine_name)
        
        if not engine:
            result = StandardResult()
            result.reason = f"引擎不可用: {engine_name or self._current_engine}"
            return result
        
        return engine.recommend(match_file)
    
    def compare_engines(self, match_file: str, engine_names: Optional[List[str]] = None) -> Dict[str, StandardResult]:
        """
        使用多个引擎对比分析
        
        Args:
            match_file: 比赛数据文件路径
            engine_names: 要对比的引擎列表，None则使用所有可用引擎
            
        Returns:
            各引擎的推荐结果
        """
        names = engine_names or list(REGISTERED_ENGINES.keys())
        results = {}
        
        for name in names:
            engine = self.get_engine(name)
            if engine and engine.is_available():
                results[name] = engine.recommend(match_file)
        
        return results
    
    def get_available_engines(self) -> List[Dict[str, Any]]:
        """获取所有可用引擎信息"""
        engines_info = []
        
        for name in REGISTERED_ENGINES:
            engine = self.get_engine(name)
            if engine:
                info = engine.get_info()
                info['is_current'] = (name == self._current_engine)
                engines_info.append(info)
        
        return engines_info
    
    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        return {
            'current_engine': self._current_engine,
            'registered_engines': list(REGISTERED_ENGINES.keys()),
            'initialized_engines': list(self._engines.keys()),
            'engines': self.get_available_engines(),
        }


# 全局单例
engine_manager = EngineManager()


def get_engine_manager() -> EngineManager:
    """获取引擎管理器单例"""
    return engine_manager
