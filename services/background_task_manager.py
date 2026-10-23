"""
后台任务管理器 - 支持采集任务在后台持续运行

功能：
- 启动后台采集任务（关闭页面后继续运行）
- 查询任务状态和进度
- 停止/暂停任务
- 任务日志记录
"""

import threading
import queue
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class TaskProgress:
    """任务进度"""
    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    current_item: str = ""
    
    # 🔥 时间追踪
    current_match_start_time: float = 0  # 当前比赛开始时间（时间戳）
    total_elapsed_seconds: float = 0  # 总耗时（秒）
    avg_time_per_match: float = 0  # 平均每场用时（秒）
    
    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0
        return round(self.processed / self.total * 100, 1)
    
    @property
    def current_match_elapsed(self) -> float:
        """当前比赛已用时（秒）"""
        if self.current_match_start_time > 0:
            import time
            return time.time() - self.current_match_start_time
        return 0
    
    @property
    def estimated_remaining_seconds(self) -> float:
        """预估剩余时间（秒）"""
        if self.avg_time_per_match > 0 and self.total > 0:
            remaining_matches = self.total - self.processed
            return remaining_matches * self.avg_time_per_match
        return 0


@dataclass
class BackgroundTask:
    """后台任务"""
    task_id: str
    task_type: str  # "collect", "backtest", etc.
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    # 控制标志
    _stop_flag: bool = field(default=False, repr=False)
    _pause_flag: bool = field(default=False, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": {
                "total": self.progress.total,
                "processed": self.progress.processed,
                "success": self.progress.success,
                "failed": self.progress.failed,
                "skipped": self.progress.skipped,
                "percentage": self.progress.percentage,
                "current_item": self.progress.current_item,
                # 🔥 时间信息
                "current_match_elapsed": round(self.progress.current_match_elapsed, 1),
                "avg_time_per_match": round(self.progress.avg_time_per_match, 1),
                "estimated_remaining_seconds": round(self.progress.estimated_remaining_seconds, 1),
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "logs_count": len(self.logs),
            "recent_logs": self.logs[-10:] if self.logs else [],  # 最近10条日志
        }
    
    def add_log(self, level: str, message: str):
        """添加日志"""
        self.logs.append({
            "time": datetime.now().isoformat(),
            "level": level,
            "message": message
        })
        # 限制日志数量
        if len(self.logs) > 1000:
            self.logs = self.logs[-500:]
    
    def should_stop(self) -> bool:
        """检查是否应该停止"""
        return self._stop_flag
    
    def should_pause(self) -> bool:
        """检查是否应该暂停"""
        return self._pause_flag


class BackgroundTaskManager:
    """后台任务管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._tasks: Dict[str, BackgroundTask] = {}
        self._task_threads: Dict[str, threading.Thread] = {}
        self._max_concurrent_tasks = 3
        self._task_handlers: Dict[str, Callable] = {}
        
        # 任务持久化目录
        self._task_dir = Path(__file__).parent.parent / "data" / "tasks"
        self._task_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载未完成的任务
        self._load_pending_tasks()
        
        logger.info("✅ 后台任务管理器已初始化")
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        logger.info(f"📝 注册任务处理器: {task_type}")
    
    def create_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> BackgroundTask:
        """创建新任务"""
        if task_id is None:
            task_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        
        task = BackgroundTask(
            task_id=task_id,
            task_type=task_type,
            params=params,
        )
        
        self._tasks[task_id] = task
        self._save_task(task)
        
        logger.info(f"📋 创建后台任务: {task_id} ({task_type})")
        return task
    
    def start_task(self, task_id: str) -> bool:
        """启动任务"""
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        if task.status == TaskStatus.RUNNING:
            logger.warning(f"任务已在运行: {task_id}")
            return False
        
        handler = self._task_handlers.get(task.task_type)
        if not handler:
            logger.error(f"未注册任务处理器: {task.task_type}")
            return False
        
        # 检查并发限制
        running_count = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        if running_count >= self._max_concurrent_tasks:
            logger.warning(f"达到最大并发任务数: {self._max_concurrent_tasks}")
            return False
        
        # 在新线程中运行任务
        thread = threading.Thread(
            target=self._run_task,
            args=(task, handler),
            daemon=True
        )
        thread.start()
        self._task_threads[task_id] = thread
        
        logger.info(f"🚀 启动后台任务: {task_id}")
        return True
    
    def _run_task(self, task: BackgroundTask, handler: Callable):
        """运行任务（在线程中执行）"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task._stop_flag = False
        task._pause_flag = False
        task.add_log("INFO", f"任务开始执行")
        self._save_task(task)
        
        try:
            # 调用任务处理器
            result = handler(task)
            
            if task._stop_flag:
                task.status = TaskStatus.CANCELLED
                task.add_log("WARNING", "任务被取消")
            else:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.add_log("INFO", f"任务完成: 成功{task.progress.success} 失败{task.progress.failed} 跳过{task.progress.skipped}")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.add_log("ERROR", f"任务失败: {e}")
            logger.exception(f"后台任务执行失败: {task.task_id}")
        finally:
            task.finished_at = datetime.now()
            self._save_task(task)
            logger.info(f"📋 任务结束: {task.task_id} ({task.status.value})")
    
    def stop_task(self, task_id: str) -> bool:
        """停止任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.RUNNING:
            return False
        
        task._stop_flag = True
        task.add_log("WARNING", "收到停止信号")
        logger.info(f"⏹️ 发送停止信号: {task_id}")
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.RUNNING:
            return False
        
        task._pause_flag = True
        task.status = TaskStatus.PAUSED
        task.add_log("INFO", "任务已暂停")
        self._save_task(task)
        logger.info(f"⏸️ 暂停任务: {task_id}")
        return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.PAUSED:
            return False
        
        return self.start_task(task_id)
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()
    
    def list_tasks(
        self,
        task_type: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = list(self._tasks.values())
        
        # 过滤
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return [t.to_dict() for t in tasks[:limit]]
    
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """获取运行中的任务"""
        return self.list_tasks(status=TaskStatus.RUNNING)
    
    def _save_task(self, task: BackgroundTask):
        """保存任务到文件"""
        try:
            task_file = self._task_dir / f"{task.task_id}.json"
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
    
    def _load_pending_tasks(self):
        """加载未完成的任务"""
        try:
            for task_file in self._task_dir.glob("*.json"):
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 重建任务对象
                    task = BackgroundTask(
                        task_id=data['task_id'],
                        task_type=data['task_type'],
                        status=TaskStatus(data['status']),
                        params=data.get('params', {}),
                    )
                    task.progress = TaskProgress(
                        total=data.get('progress', {}).get('total', 0),
                        processed=data.get('progress', {}).get('processed', 0),
                        success=data.get('progress', {}).get('success', 0),
                        failed=data.get('progress', {}).get('failed', 0),
                        skipped=data.get('progress', {}).get('skipped', 0),
                    )
                    
                    if data.get('created_at'):
                        task.created_at = datetime.fromisoformat(data['created_at'])
                    
                    # 运行中的任务标记为暂停（服务重启后）
                    if task.status == TaskStatus.RUNNING:
                        task.status = TaskStatus.PAUSED
                        task.add_log("WARNING", "服务重启，任务已暂停")
                    
                    self._tasks[task.task_id] = task
                    
                except Exception as e:
                    logger.warning(f"加载任务文件失败 {task_file}: {e}")
            
            logger.info(f"📂 加载了 {len(self._tasks)} 个历史任务")
        except Exception as e:
            logger.error(f"加载任务目录失败: {e}")
    
    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务"""
        cutoff = datetime.now().timestamp() - days * 86400
        removed = 0
        
        for task_id, task in list(self._tasks.items()):
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.finished_at and task.finished_at.timestamp() < cutoff:
                    del self._tasks[task_id]
                    task_file = self._task_dir / f"{task_id}.json"
                    if task_file.exists():
                        task_file.unlink()
                    removed += 1
        
        if removed > 0:
            logger.info(f"🗑️ 清理了 {removed} 个旧任务")
    
    def delete_task(self, task_id: str) -> bool:
        """删除指定任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        # 如果任务正在运行，先停止它
        if task.status == TaskStatus.RUNNING:
            self.stop_task(task_id)
            # 等待任务停止（最多3秒）
            for _ in range(30):
                if task.status != TaskStatus.RUNNING:
                    break
                time.sleep(0.1)
        
        # 删除任务
        del self._tasks[task_id]
        
        # 删除任务文件
        task_file = self._task_dir / f"{task_id}.json"
        if task_file.exists():
            task_file.unlink()
        
        logger.info(f"🗑️ 已删除任务: {task_id}")
        return True
    
    def delete_all_tasks(self, status_filter: Optional[TaskStatus] = None) -> int:
        """删除所有任务（可选按状态过滤）"""
        deleted_count = 0
        
        for task_id, task in list(self._tasks.items()):
            # 如果指定了状态过滤，只删除匹配的任务
            if status_filter and task.status != status_filter:
                continue
            
            # 不删除正在运行的任务（除非明确指定）
            if task.status == TaskStatus.RUNNING and status_filter != TaskStatus.RUNNING:
                continue
            
            if self.delete_task(task_id):
                deleted_count += 1
        
        logger.info(f"🗑️ 批量删除了 {deleted_count} 个任务")
        return deleted_count


# 全局实例
background_task_manager = BackgroundTaskManager()
