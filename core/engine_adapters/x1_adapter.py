"""
X1 JSON 推荐引擎适配器
封装现有的X1推荐引擎，提供标准化接口
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .base import BaseEngineAdapter, StandardResult

logger = logging.getLogger(__name__)


class X1EngineAdapter(BaseEngineAdapter):
    """
    X1 JSON 推荐引擎适配器
    封装现有的 X1JsonRecommendEngine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._engine = None
        self._confidence_threshold = config.get('confidence_threshold', 0.85) if config else 0.85
    
    @property
    def engine_name(self) -> str:
        return "X1 JSON推荐引擎"
    
    @property
    def engine_version(self) -> str:
        return "1.0"
    
    def initialize(self) -> bool:
        """初始化X1引擎"""
        try:
            from recommendation.x1_json_recommender import X1JSONRecommender
            self._engine = X1JSONRecommender()
            self._initialized = True
            logger.info(f"✅ {self.engine_name} 初始化成功")
            return True
        except ImportError as e:
            logger.warning(f"⚠️ {self.engine_name} 导入失败: {e}")
            self._initialized = False
            return False
        except Exception as e:
            logger.error(f"❌ {self.engine_name} 初始化失败: {e}")
            self._initialized = False
            return False
    
    def get_raw_engine(self):
        """获取原始引擎实例（兼容旧代码）"""
        return self._engine
    
    def recommend(self, match_file: str) -> StandardResult:
        """
        执行X1推荐分析
        
        Args:
            match_file: 比赛数据文件路径
            
        Returns:
            标准化推荐结果
        """
        result = StandardResult(engine=self.engine_name)
        
        if not self._initialized or not self._engine:
            result.reason = "引擎未初始化"
            return result
        
        try:
            # 调用X1引擎
            raw_result = self._engine.recommend(match_file)
            result.raw_result = raw_result
            
            # 检查是否熔断
            if raw_result.get('meltdown'):
                result.success = True
                result.meltdown = True
                result.meltdown_reason = raw_result['meltdown'].get('reason', '未知')
                result.reason = f"熔断: {result.meltdown_reason}"
                return result
            
            # 解析推荐结果
            rec = raw_result.get('recommendation', {})
            
            result.success = True
            result.direction = rec.get('direction', 'none')
            result.confidence = rec.get('confidence', 0)
            result.handicap = rec.get('handicap', '')
            result.reason = rec.get('reason', '')
            
            # 判断是否应该下注
            result.should_bet = (
                result.direction not in ['none', None] and 
                result.confidence >= self._confidence_threshold
            )
            
            # 保存详细信息
            result.details = {
                'scores': raw_result.get('scores', {}),
                'funding_level': raw_result.get('funding_level', {}),
                'risk_control': raw_result.get('risk_control', {}),
                'match_info': raw_result.get('match_info', {}),
            }
            
            return result
            
        except Exception as e:
            logger.error(f"X1推荐失败: {e}", exc_info=True)
            result.reason = f"推荐异常: {str(e)}"
            return result
