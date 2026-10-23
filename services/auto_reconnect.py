"""
自动重连机制 - 处理账号被顶、网络错误等情况

功能：
1. 检测账号被顶（会话失效）
2. 自动重新登录
3. 重试失败的请求
4. 维持SSE连接稳定性
"""

import logging
import time
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class SessionExpiredException(Exception):
    """会话过期异常（账号被顶）"""
    pass


class NetworkErrorException(Exception):
    """网络错误异常"""
    pass


class AutoReconnectManager:
    """自动重连管理器"""
    
    def __init__(self, client):
        """
        Args:
            client: BifawClient 实例
        """
        self.client = client
        self.max_retries = 3
        self.retry_delay = 3  # 秒
        self.login_retry_limit = 2  # 重新登录次数限制
        
    def is_session_expired_error(self, error: Exception) -> bool:
        """
        判断是否是会话过期错误（账号被顶）
        
        常见特征：
        - "未登录" 或 "登录" 出现在错误信息中
        - "验证码" 出现（重定向到登录页）
        - 403/401 状态码
        - 页面包含登录表单
        """
        error_str = str(error).lower()
        
        # 关键词检测
        session_keywords = [
            '未登录', '登录', '验证码', 'login', 'captcha',
            '401', '403', 'unauthorized', 'forbidden',
            '会话', 'session', '过期', 'expired'
        ]
        
        for keyword in session_keywords:
            if keyword in error_str:
                logger.warning(f"检测到会话过期标志: {keyword}")
                return True
        
        return False
    
    def is_network_error(self, error: Exception) -> bool:
        """判断是否是网络错误"""
        error_str = str(error).lower()
        
        network_keywords = [
            'network error', 'connection', 'timeout',
            'remote end closed', 'connection aborted',
            'max retries', 'read timed out'
        ]
        
        for keyword in network_keywords:
            if keyword in error_str:
                return True
        
        return False
    
    def auto_relogin(self) -> bool:
        """
        自动重新登录
        
        Returns:
            True if 登录成功, False otherwise
        """
        logger.info("🔄 检测到会话失效，尝试自动重新登录...")
        
        try:
            # 清理旧的会话
            if hasattr(self.client, '_sessions'):
                self.client._sessions.clear()
            
            if hasattr(self.client, '_requests_cookie_cache'):
                self.client._requests_cookie_cache = None
            
            # 使用OCR自动登录
            if hasattr(self.client, '_auto_login_with_ocr'):
                success, message = self.client._auto_login_with_ocr(max_retries=self.login_retry_limit)
                
                if success:
                    logger.info(f"✅ 自动登录成功: {message}")
                    return True
                else:
                    logger.error(f"❌ 自动登录失败: {message}")
                    return False
            else:
                logger.error("❌ 客户端不支持自动登录")
                return False
                
        except Exception as e:
            logger.error(f"❌ 自动登录异常: {e}")
            return False
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        执行函数，失败时自动重试
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次执行的异常
        """
        last_exception = None
        login_attempted = False
        
        for attempt in range(self.max_retries):
            try:
                # 执行函数
                result = func(*args, **kwargs)
                
                # 成功，返回结果
                if attempt > 0:
                    logger.info(f"✅ 重试成功（尝试 {attempt + 1}/{self.max_retries}）")
                
                return result
                
            except Exception as e:
                last_exception = e
                error_msg = str(e)[:200]
                
                logger.warning(f"⚠️ 执行失败（尝试 {attempt + 1}/{self.max_retries}）: {error_msg}")
                
                # 判断错误类型
                if self.is_session_expired_error(e):
                    # 会话过期，尝试重新登录（只尝试一次）
                    if not login_attempted:
                        logger.info("🔐 检测到账号被顶，尝试重新登录...")
                        login_attempted = True
                        
                        if self.auto_relogin():
                            logger.info("✅ 重新登录成功，继续执行...")
                            # 不增加attempt，直接重试
                            time.sleep(1)
                            continue
                        else:
                            logger.error("❌ 重新登录失败，停止重试")
                            raise SessionExpiredException("账号被顶且重新登录失败") from e
                    else:
                        logger.error("❌ 已尝试重新登录但仍失败")
                        raise SessionExpiredException("重新登录后仍失败") from e
                
                elif self.is_network_error(e):
                    # 网络错误，等待后重试
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                        logger.info(f"⏳ 网络错误，等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise NetworkErrorException(f"网络错误，已重试{self.max_retries}次") from e
                
                else:
                    # 其他错误，直接抛出
                    if attempt < self.max_retries - 1:
                        logger.info(f"⏳ 等待 {self.retry_delay} 秒后重试...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise
        
        # 所有重试都失败
        logger.error(f"❌ 执行失败，已达最大重试次数 ({self.max_retries})")
        raise last_exception


def with_auto_retry(max_retries: int = 3):
    """
    装饰器：为函数添加自动重试功能
    
    使用方法：
    @with_auto_retry(max_retries=3)
    def fetch_data(self):
        # 你的代码
        pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 假设self是BifawClient实例
            if not hasattr(self, '_reconnect_manager'):
                self._reconnect_manager = AutoReconnectManager(self)
            
            return self._reconnect_manager.execute_with_retry(
                func, self, *args, **kwargs
            )
        
        return wrapper
    
    return decorator


# 全局单例
_reconnect_manager_cache = {}


def get_reconnect_manager(client) -> AutoReconnectManager:
    """获取重连管理器（单例模式）"""
    client_id = id(client)
    
    if client_id not in _reconnect_manager_cache:
        _reconnect_manager_cache[client_id] = AutoReconnectManager(client)
    
    return _reconnect_manager_cache[client_id]


__all__ = [
    'AutoReconnectManager',
    'SessionExpiredException',
    'NetworkErrorException',
    'with_auto_retry',
    'get_reconnect_manager'
]
