"""
自动恢复服务
定期检测和恢复中断的采集任务
"""
import logging
import threading
import time
from typing import Callable, Optional, Dict, List

from .auto_recovery_manager import AutoRecoveryManager
from .progress_manager import ProgressManager

logger = logging.getLogger(__name__)

class AutoRecoveryService:
    """自动恢复服务"""
    
    def __init__(self, progress_manager: ProgressManager, 
                 recovery_callback: Optional[Callable] = None):
        """
        初始化自动恢复服务
        
        Args:
            progress_manager: 进度管理器实例
            recovery_callback: 恢复回调函数，接收(session_id, start_date)参数
        """
        self.progress_manager = progress_manager
        self.recovery_manager = AutoRecoveryManager(progress_manager.progress_dir)
        self.recovery_callback = recovery_callback
        
        self.check_interval = 300  # 5分钟检查一次
        self.running = False
        self.thread = None
        
        logger.info("✅ 自动恢复服务已初始化")
    
    def start(self):
        """启动自动恢复服务"""
        if self.running:
            logger.warning("自动恢复服务已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("✅ 自动恢复服务已启动")
    
    def stop(self):
        """停止自动恢复服务"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("✅ 自动恢复服务已停止")
    
    def _run_loop(self):
        """运行检测循环"""
        logger.info(f"自动恢复服务开始运行，检测间隔: {self.check_interval}秒")
        
        while self.running:
            try:
                self._check_and_recover()
            except Exception as e:
                logger.exception(f"自动恢复检测异常: {e}")
            
            # 等待下次检测
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _check_and_recover(self):
        """检测并恢复中断的会话"""
        # 查找中断的会话
        interrupted_sessions = self.recovery_manager.find_interrupted_sessions()
        
        if not interrupted_sessions:
            logger.debug("未发现中断的会话")
            return
        
        logger.info(f"发现 {len(interrupted_sessions)} 个中断的会话")
        
        for session in interrupted_sessions:
            session_id = session.get('session_id')
            
            # 判断是否应该恢复
            if not self.recovery_manager.should_auto_recover(session):
                logger.debug(f"会话 {session_id} 不符合自动恢复条件")
                continue
            
            # 获取重试延迟
            retry_delay = self.recovery_manager.get_retry_delay(session_id)
            
            # 检查是否到了重试时间
            last_retry = session.get('last_retry_time')
            if last_retry:
                from datetime import datetime
                last_retry_time = datetime.fromisoformat(last_retry)
                if (datetime.now() - last_retry_time).total_seconds() < retry_delay:
                    logger.debug(f"会话 {session_id} 尚未到重试时间")
                    continue
            
            # 尝试恢复
            self._attempt_recovery(session)
    
    def _attempt_recovery(self, session: Dict):
        """尝试恢复会话"""
        session_id = session.get('session_id')
        start_date = session.get('start_date')
        
        logger.info(f"🔄 尝试自动恢复会话: {session_id}")
        
        try:
            # 标记重试
            self.recovery_manager.mark_retry(session_id)
            
            # 🔥 修复：不要将状态设为 'recovering'，而是保持 'paused' 或 'failed'
            # 这样前端才能正常恢复会话
            # self.progress_manager.update_session_status(session_id, 'recovering')
            
            # 记录重试时间
            from datetime import datetime
            retry_time = datetime.now().isoformat()
            
            # 调用恢复回调
            delay_seconds = 5
            logger.info(f"⏰ 延迟 {delay_seconds} 秒后尝试恢复会话: {session_id}")
            time.sleep(delay_seconds)
            session_file = self.progress_manager.progress_dir / f"session_{session_id}.json"
            if session_file.exists():
                import json
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                session_data['last_retry_time'] = retry_time
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            # 调用恢复回调
            if self.recovery_callback:
                logger.info(f"执行恢复回调: session_id={session_id}, start_date={start_date}")
                self.recovery_callback(session_id, start_date)
            else:
                logger.warning("未设置恢复回调函数，无法自动恢复")
            
            logger.info(f"✅ 会话 {session_id} 恢复请求已发送")
            
        except Exception as e:
            logger.exception(f"恢复会话 {session_id} 失败: {e}")
            self.progress_manager.update_session_status(session_id, 'failed')
    
    def manual_recover(self, session_id: str) -> bool:
        """手动触发恢复"""
        try:
            # 获取会话信息
            session = self.progress_manager.get_session(session_id)
            if not session:
                logger.error(f"会话 {session_id} 不存在")
                return False
            
            # 检查是否可以重试
            if not self.recovery_manager.can_retry(session_id):
                logger.error(f"会话 {session_id} 已达最大重试次数")
                return False
            
            # 尝试恢复
            self._attempt_recovery(session)
            return True
            
        except Exception as e:
            logger.exception(f"手动恢复失败: {e}")
            return False
    
    def get_recovery_status(self) -> Dict:
        """获取恢复服务状态"""
        interrupted = self.recovery_manager.find_interrupted_sessions()
        
        return {
            'running': self.running,
            'check_interval': self.check_interval,
            'interrupted_count': len(interrupted),
            'interrupted_sessions': [
                {
                    'session_id': s.get('session_id'),
                    'status': s.get('status'),
                    'recovery_info': self.recovery_manager.get_recovery_info(s.get('session_id'))
                }
                for s in interrupted
            ]
        }
