"""
采集日志管理器
实现日志持久化和多设备共享
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class LogManager:
    """采集日志管理器"""
    
    def __init__(self, log_dir: str = "logs", max_messages: int = 500):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录（可以是绝对路径或相对路径）
            max_messages: 内存中保留的最大消息数
        """
        # 🔥 智能处理绝对路径和相对路径
        log_path = Path(log_dir)
        if log_path.is_absolute():
            self.log_dir = log_path
        else:
            self.log_dir = log_path.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_messages = max_messages
        self.current_session_id = None
        self.messages = deque(maxlen=max_messages)  # 循环队列，自动淘汰旧消息
        
        logger.info(f"日志管理器已初始化，目录: {self.log_dir}")
    
    def start_session(self, session_id: str):
        """开始新会话"""
        self.current_session_id = session_id
        self.messages.clear()
        
        # 记录开始消息
        self.add_message({
            'type': 'session_start',
            'session_id': session_id,
            'message': f'开始采集会话: {session_id}',
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"开始日志会话: {session_id}")
    
    def add_message(self, message: Dict):
        """添加日志消息"""
        # 添加时间戳
        if 'timestamp' not in message:
            message['timestamp'] = datetime.now().isoformat()
        
        # 添加会话ID
        if 'session_id' not in message and self.current_session_id:
            message['session_id'] = self.current_session_id
        
        # 添加到内存队列
        self.messages.append(message)
        
        # 持久化到文件
        if self.current_session_id:
            self._save_to_file(message)
    
    def _save_to_file(self, message: Dict):
        """保存消息到文件"""
        if not self.current_session_id:
            return
        
        log_file = self.log_dir / f"session_{self.current_session_id}.log"
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存日志失败: {e}")
    
    def get_recent_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """获取最近的消息（优先内存，否则从文件读取最近会话）"""
        # 如果内存中有消息，返回内存中的
        if self.messages:
            if limit is None:
                return list(self.messages)
            return list(self.messages)[-limit:]
        
        # 🔥 内存为空时，尝试从最近的会话文件读取
        latest_session = self.get_latest_session_id()
        if latest_session:
            return self.get_session_messages(latest_session, limit=limit)
        
        return []
    
    def get_latest_session_id(self) -> Optional[str]:
        """获取最近的会话ID（从文件系统）"""
        try:
            log_files = sorted(self.log_dir.glob("session_*.log"), reverse=True)
            if log_files:
                # 从文件名提取 session_id: session_20251128_210725.log -> 20251128_210725
                filename = log_files[0].stem  # session_20251128_210725
                session_id = filename.replace("session_", "")
                return session_id
        except Exception as e:
            logger.error(f"获取最近会话ID失败: {e}")
        return None
    
    def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """获取指定会话的所有消息"""
        log_file = self.log_dir / f"session_{session_id}.log"
        
        if not log_file.exists():
            return []
        
        messages = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            messages.append(message)
                        except json.JSONDecodeError:
                            continue
            
            if limit:
                messages = messages[-limit:]
            
            return messages
        except Exception as e:
            logger.error(f"读取日志文件失败 {log_file}: {e}")
            return []
    
    def get_active_session_id(self) -> Optional[str]:
        """获取当前活动会话ID"""
        return self.current_session_id
    
    def end_session(self):
        """结束当前会话"""
        if self.current_session_id:
            self.add_message({
                'type': 'session_end',
                'session_id': self.current_session_id,
                'message': f'采集会话结束: {self.current_session_id}',
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"结束日志会话: {self.current_session_id}")
            self.current_session_id = None
    
    def cleanup_old_logs(self, days: int = 7):
        """清理旧日志文件"""
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        for log_file in self.log_dir.glob("session_*.log"):
            try:
                # 检查文件修改时间
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"清理日志文件失败 {log_file}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个旧日志文件")
