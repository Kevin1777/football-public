"""
日志流处理器
捕获日志并推送到前端
"""
import logging
from collections import deque
from datetime import datetime

class LogStreamHandler(logging.Handler):
    """捕获日志消息并存储到队列"""
    
    def __init__(self, max_messages=100):
        super().__init__()
        self.messages = deque(maxlen=max_messages)
        self.enabled = False
    
    def emit(self, record):
        """处理日志记录"""
        if not self.enabled:
            return
        
        try:
            # 格式化日志
            msg = self.format(record)
            
            # 判断日志类型
            log_type = 'info'
            if record.levelno >= logging.ERROR:
                log_type = 'error'
            elif record.levelno >= logging.WARNING:
                log_type = 'warn'
            
            # 存储到队列
            self.messages.append({
                'type': 'log',
                'level': record.levelname,
                'log_type': log_type,
                'message': msg,
                'timestamp': datetime.now().isoformat()
            })
        except Exception:
            self.handleError(record)
    
    def start_capture(self):
        """开始捕获日志"""
        self.enabled = True
        self.messages.clear()
    
    def stop_capture(self):
        """停止捕获日志"""
        self.enabled = False
    
    def get_messages(self):
        """获取捕获的消息"""
        return list(self.messages)
    
    def clear(self):
        """清空消息"""
        self.messages.clear()


# 全局日志流处理器实例
_stream_handler = None

def get_stream_handler():
    """获取全局日志流处理器"""
    global _stream_handler
    if _stream_handler is None:
        _stream_handler = LogStreamHandler()
        
        # 设置格式化器
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        _stream_handler.setFormatter(formatter)
        
        # 添加到 root logger
        logger = logging.getLogger()
        logger.addHandler(_stream_handler)
    return _stream_handler
