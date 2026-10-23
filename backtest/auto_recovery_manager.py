"""
自动恢复管理器
检测中断的采集任务并自动恢复
"""
import logging
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class AutoRecoveryManager:
    """自动恢复管理器"""
    
    def __init__(self, progress_dir: str = "progress"):
        self.progress_dir = Path(progress_dir)
        self.recovery_config_file = self.progress_dir / "recovery_config.json"
        self.max_retry_count = 3  # 最大重试次数
        self.retry_delay = 60  # 重试延迟（秒）
        
        # 加载恢复配置
        self.recovery_config = self._load_recovery_config()
        
        logger.info(f"✅ 自动恢复管理器已初始化")
    
    def _load_recovery_config(self) -> Dict:
        """加载恢复配置"""
        if self.recovery_config_file.exists():
            try:
                with open(self.recovery_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载恢复配置失败: {e}")
        
        return {
            'enabled': True,
            'auto_retry': True,
            'max_retries': 3,
            'retry_intervals': [60, 180, 300],  # 1分钟、3分钟、5分钟
            'recovery_sessions': {}  # {session_id: retry_count}
        }
    
    def _save_recovery_config(self):
        """保存恢复配置"""
        try:
            self.recovery_config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.recovery_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.recovery_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存恢复配置失败: {e}")
    
    def find_interrupted_sessions(self) -> List[Dict]:
        """查找中断的会话"""
        interrupted = []
        
        if not self.progress_dir.exists():
            return interrupted
        
        # 扫描所有会话文件
        for session_file in self.progress_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session = json.load(f)
                
                # 判断是否为中断会话
                if self._is_interrupted(session):
                    interrupted.append(session)
            
            except Exception as e:
                logger.error(f"读取会话文件失败 {session_file}: {e}")
        
        return interrupted
    
    def _is_interrupted(self, session: Dict) -> bool:
        """判断会话是否中断"""
        status = session.get('status', '')
        
        # 状态为running但超过30分钟未更新
        if status == 'running':
            last_update = session.get('last_updated')
            if last_update:
                last_time = datetime.fromisoformat(last_update)
                if datetime.now() - last_time > timedelta(minutes=30):
                    return True
        
        # 状态为paused
        if status == 'paused':
            return True
        
        return False
    
    def can_retry(self, session_id: str) -> bool:
        """判断是否可以重试"""
        retry_count = self.recovery_config['recovery_sessions'].get(session_id, 0)
        max_retries = self.recovery_config.get('max_retries', 3)
        
        return retry_count < max_retries
    
    def mark_retry(self, session_id: str):
        """标记重试"""
        if session_id not in self.recovery_config['recovery_sessions']:
            self.recovery_config['recovery_sessions'][session_id] = 0
        
        self.recovery_config['recovery_sessions'][session_id] += 1
        self._save_recovery_config()
        
        logger.info(f"会话 {session_id} 重试次数: {self.recovery_config['recovery_sessions'][session_id]}")
    
    def get_retry_delay(self, session_id: str) -> int:
        """获取重试延迟"""
        retry_count = self.recovery_config['recovery_sessions'].get(session_id, 0)
        intervals = self.recovery_config.get('retry_intervals', [60, 180, 300])
        
        if retry_count >= len(intervals):
            return intervals[-1]
        
        return intervals[retry_count]
    
    def reset_retry(self, session_id: str):
        """重置重试计数"""
        if session_id in self.recovery_config['recovery_sessions']:
            del self.recovery_config['recovery_sessions'][session_id]
            self._save_recovery_config()
    
    def should_auto_recover(self, session: Dict) -> bool:
        """判断是否应该自动恢复"""
        if not self.recovery_config.get('enabled', True):
            return False
        
        if not self.recovery_config.get('auto_retry', True):
            return False
        
        session_id = session.get('session_id')
        if not session_id:
            return False
        
        # 检查重试次数
        if not self.can_retry(session_id):
            logger.warning(f"会话 {session_id} 已达最大重试次数")
            return False
        
        return True
    
    def get_recovery_info(self, session_id: str) -> Dict:
        """获取恢复信息"""
        retry_count = self.recovery_config['recovery_sessions'].get(session_id, 0)
        max_retries = self.recovery_config.get('max_retries', 3)
        
        return {
            'session_id': session_id,
            'retry_count': retry_count,
            'max_retries': max_retries,
            'can_retry': retry_count < max_retries,
            'next_retry_delay': self.get_retry_delay(session_id)
        }
    
    def cleanup_old_recovery_records(self, days: int = 7):
        """清理旧的恢复记录"""
        # 只保留最近7天的重试记录
        # 这里简化处理，实际可以根据会话创建时间判断
        cleaned_count = 0
        
        for session_id in list(self.recovery_config['recovery_sessions'].keys()):
            # 检查会话文件是否存在
            session_file = self.progress_dir / f"session_{session_id}.json"
            if not session_file.exists():
                del self.recovery_config['recovery_sessions'][session_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self._save_recovery_config()
            logger.info(f"清理了 {cleaned_count} 条旧恢复记录")
