"""
后台采集服务 - 支持关闭网页后继续采集

功能：
1. 后台持续运行，不依赖前端连接
2. 自动检测登录失效并恢复
3. 登录恢复后从断点继续采集
4. 实时进度保存，支持服务重启后恢复
"""

import threading
import queue
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class CollectionStatus(Enum):
    """采集状态"""
    PENDING = "pending"          # 等待开始
    RUNNING = "running"          # 运行中
    PAUSED = "paused"            # 已暂停（可恢复）
    WAITING_LOGIN = "waiting_login"  # 等待登录恢复
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


@dataclass
class CollectionProgress:
    """采集进度"""
    total_days: int = 0
    total_matches: int = 0
    current_day: int = 0
    current_match: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    current_date: str = ""
    current_match_label: str = ""
    
    # 🔥 时间追踪
    current_match_start_time: float = 0  # 当前比赛开始时间（时间戳）
    total_elapsed_seconds: float = 0  # 总耗时（秒）
    avg_time_per_match: float = 0  # 平均每场用时（秒）
    
    # 已处理的比赛（用于断点续传）
    processed_matches: Dict[str, List[str]] = field(default_factory=dict)  # {date: [match_key1, match_key2, ...]}
    
    @property
    def processed(self) -> int:
        """实际处理的比赛数（不含跳过的，因为跳过的是已缓存的）"""
        return self.success + self.failed
    
    @property
    def percentage(self) -> float:
        """进度百分比：(成功+失败) / 总数"""
        if self.total_matches == 0:
            return 0
        return round(self.processed / self.total_matches * 100, 1)
    
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
        if self.avg_time_per_match > 0 and self.total_matches > 0:
            remaining_matches = self.total_matches - self.processed
            return remaining_matches * self.avg_time_per_match
        return 0
    
    def to_dict(self) -> Dict:
        return {
            "total_days": self.total_days,
            "total_matches": self.total_matches,
            "current_day": self.current_day,
            "current_match": self.current_match,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "processed": self.processed,
            "percentage": self.percentage,
            "current_date": self.current_date,
            "current_match_label": self.current_match_label,
            # 🔥 时间信息
            "current_match_elapsed": round(self.current_match_elapsed, 1),
            "avg_time_per_match": round(self.avg_time_per_match, 1),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 0),
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 1),
        }


@dataclass
class CollectionTask:
    """采集任务"""
    task_id: str
    start_date: str
    end_date: str
    filter_by_handicap: bool = True
    skip_cached: bool = True
    workers: int = 2  # 🔥 降低并发数避免被限流
    
    # 🔥 新增：四合一采集模式
    super_mode: bool = True  # 默认启用四合一采集
    
    status: CollectionStatus = CollectionStatus.PENDING
    progress: CollectionProgress = field(default_factory=CollectionProgress)
    
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    error: Optional[str] = None
    logs: List[Dict] = field(default_factory=list)
    
    # 控制标志
    _stop_flag: bool = field(default=False, repr=False)
    _pause_flag: bool = field(default=False, repr=False)
    
    # 登录恢复相关
    login_retry_count: int = 0
    max_login_retries: int = 5
    last_login_attempt: Optional[datetime] = None
    
    def add_log(self, level: str, message: str):
        """添加日志"""
        log_entry = {
            "time": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.logs.append(log_entry)
        
        # 限制日志数量
        if len(self.logs) > 2000:
            self.logs = self.logs[-1000:]
        
        # 同时输出到logger
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{self.task_id}] {message}")
    
    def should_stop(self) -> bool:
        return self._stop_flag
    
    def should_pause(self) -> bool:
        return self._pause_flag
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "filter_by_handicap": self.filter_by_handicap,
            "skip_cached": self.skip_cached,
            "workers": self.workers,
            "super_mode": self.super_mode,  # 🔥 新增
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "logs_count": len(self.logs),
            "recent_logs": self.logs[-20:] if self.logs else [],
            "login_retry_count": self.login_retry_count,
        }


class BackgroundCollector:
    """后台采集器 - 支持关闭网页后继续采集"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        bifaw_client=None,
        lottery500_client=None,
        detail_cache_manager=None,
        log_manager=None
    ):
        if self._initialized:
            # 更新客户端引用（如果提供了新的）
            if bifaw_client:
                self.bifaw_client = bifaw_client
            if lottery500_client:
                self.lottery500_client = lottery500_client
            if detail_cache_manager:
                self.detail_cache_manager = detail_cache_manager
            if log_manager:
                self.log_manager = log_manager
            return
        
        self._initialized = True
        self.bifaw_client = bifaw_client
        self.lottery500_client = lottery500_client
        self.detail_cache_manager = detail_cache_manager
        self.log_manager = log_manager
        
        self._tasks: Dict[str, CollectionTask] = {}
        self._task_threads: Dict[str, threading.Thread] = {}
        self._current_task_id: Optional[str] = None
        
        # 任务持久化目录
        self._task_dir = Path(__file__).parent.parent / "data" / "collection_tasks"
        self._task_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载未完成的任务
        self._load_pending_tasks()
        
        # 登录检查间隔（秒）
        self._login_check_interval = 30
        
        # 🔥 自动恢复标志（延迟启动，等待依赖初始化完成）
        self._auto_resume_enabled = True
        self._auto_resume_delay = 30  # 服务启动后30秒自动恢复
        
        logger.info("✅ 后台采集器已初始化")
    
    def auto_resume_paused_tasks(self):
        """
        🔥 自动恢复暂停的任务（服务重启后调用）
        """
        if not self._auto_resume_enabled:
            return
        
        paused_tasks = [
            task for task in self._tasks.values()
            if task.status in [CollectionStatus.PAUSED, CollectionStatus.RUNNING]
            and task.progress.percentage < 100
        ]
        
        if not paused_tasks:
            logger.info("📋 没有需要恢复的采集任务")
            return
        
        # 按创建时间排序，恢复最新的一个
        paused_tasks.sort(key=lambda t: t.created_at, reverse=True)
        task_to_resume = paused_tasks[0]
        
        logger.info(f"🔄 自动恢复采集任务: {task_to_resume.task_id} (进度: {task_to_resume.progress.percentage}%)")
        
        # 重置状态
        task_to_resume._stop_flag = False
        task_to_resume._pause_flag = False
        task_to_resume.login_retry_count = 0
        
        # 启动任务
        if self.start_task(task_to_resume.task_id):
            logger.info(f"✅ 任务 {task_to_resume.task_id} 已自动恢复")
        else:
            logger.warning(f"⚠️ 任务 {task_to_resume.task_id} 恢复失败")
    
    def create_task(
        self,
        start_date: str,
        end_date: str,
        filter_by_handicap: bool = True,
        skip_cached: bool = True,
        workers: int = 2,  # 🔥 降低并发数避免被限流
        task_id: Optional[str] = None,
        super_mode: bool = True  # 🔥 新增：四合一采集模式
    ) -> CollectionTask:
        """创建采集任务"""
        if task_id is None:
            task_id = datetime.now().strftime("collect_%Y%m%d_%H%M%S")
        
        task = CollectionTask(
            task_id=task_id,
            start_date=start_date,
            end_date=end_date,
            filter_by_handicap=filter_by_handicap,
            skip_cached=skip_cached,
            workers=workers,
            super_mode=super_mode,  # 🔥 新增
        )
        
        self._tasks[task_id] = task
        self._save_task(task)
        
        mode_str = "四合一模式" if super_mode else "标准模式"
        task.add_log("INFO", f"创建采集任务: {start_date} ~ {end_date} ({mode_str})")
        return task
    
    def start_task(self, task_id: str) -> bool:
        """启动采集任务"""
        task = self._tasks.get(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        if task.status == CollectionStatus.RUNNING:
            logger.warning(f"任务已在运行: {task_id}")
            return False
        
        # 检查是否有其他任务在运行
        if self._current_task_id and self._current_task_id != task_id:
            running_task = self._tasks.get(self._current_task_id)
            if running_task and running_task.status == CollectionStatus.RUNNING:
                logger.warning(f"已有任务在运行: {self._current_task_id}")
                return False
        
        # 检查依赖
        if not self.bifaw_client or not self.lottery500_client or not self.detail_cache_manager:
            logger.error("缺少必要的客户端依赖")
            return False
        
        # 在新线程中运行任务
        thread = threading.Thread(
            target=self._run_task,
            args=(task,),
            daemon=True,
            name=f"collector_{task_id}"
        )
        thread.start()
        self._task_threads[task_id] = thread
        self._current_task_id = task_id
        
        task.add_log("INFO", "🚀 后台采集任务已启动")
        return True
    
    def stop_task(self, task_id: str) -> bool:
        """停止任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task._stop_flag = True
        task.add_log("WARNING", "收到停止信号")
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        task._pause_flag = True
        task.add_log("INFO", "收到暂停信号")
        return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status not in [CollectionStatus.PAUSED, CollectionStatus.WAITING_LOGIN, CollectionStatus.FAILED]:
            logger.warning(f"任务状态不允许恢复: {task.status}")
            return False
        
        task._pause_flag = False
        task._stop_flag = False
        task.login_retry_count = 0  # 重置登录重试计数
        
        return self.start_task(task_id)
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        # 如果任务正在运行，先停止
        if task.status == CollectionStatus.RUNNING:
            self.stop_task(task_id)
        
        # 删除任务文件
        try:
            task_file = self._task_dir / f"{task_id}.json"
            if task_file.exists():
                task_file.unlink()
        except Exception as e:
            logger.warning(f"删除任务文件失败: {e}")
        
        # 从内存中移除
        del self._tasks[task_id]
        
        # 如果是当前任务，清空引用
        if self._current_task_id == task_id:
            self._current_task_id = None
        
        logger.info(f"任务已删除: {task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[CollectionTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()
    
    def get_current_task(self) -> Optional[Dict]:
        """获取当前运行的任务"""
        if self._current_task_id:
            return self.get_task_status(self._current_task_id)
        return None
    
    def list_tasks(self, limit: int = 20) -> List[Dict]:
        """列出所有任务"""
        tasks = sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True
        )
        return [t.to_dict() for t in tasks[:limit]]

    
    def _run_task(self, task: CollectionTask):
        """运行采集任务（在后台线程中执行）"""
        task.status = CollectionStatus.RUNNING
        task.started_at = datetime.now()
        task._stop_flag = False
        task._pause_flag = False
        self._save_task(task)
        
        # 🔥 最大重试次数（整体任务级别）
        max_task_retries = 3
        task_retry_count = 0
        
        while task_retry_count < max_task_retries:
            try:
                task.add_log("INFO", f"开始采集: {task.start_date} ~ {task.end_date}")
                
                # 第一阶段：扫描比赛
                date_match_map = self._scan_matches(task)
                
                if task.should_stop():
                    task.status = CollectionStatus.CANCELLED
                    task.add_log("WARNING", "任务被取消")
                    return
                
                if not date_match_map:
                    task.status = CollectionStatus.COMPLETED
                    task.add_log("INFO", "无符合条件的比赛")
                    return
                
                # 计算总比赛数
                total_matches = sum(len(matches) for matches in date_match_map.values())
                task.progress.total_matches = total_matches
                task.progress.total_days = len(date_match_map)
                self._save_task(task)
                
                task.add_log("INFO", f"扫描完成: {task.progress.total_days}天, {total_matches}场比赛")
                
                # 第二阶段：采集明细
                self._collect_matches(task, date_match_map)
                
                # 完成
                if task.should_stop():
                    task.status = CollectionStatus.CANCELLED
                    task.add_log("WARNING", "任务被取消")
                elif task.should_pause():
                    task.status = CollectionStatus.PAUSED
                    task.add_log("INFO", "任务已暂停")
                else:
                    task.status = CollectionStatus.COMPLETED
                    task.add_log("INFO", f"✅ 采集完成: 成功{task.progress.success}, 失败{task.progress.failed}, 跳过{task.progress.skipped}")
                
                # 🔥 正常完成，退出重试循环
                break
                
            except Exception as e:
                task_retry_count += 1
                error_msg = str(e)
                task.add_log("ERROR", f"采集异常 (重试 {task_retry_count}/{max_task_retries}): {error_msg}")
                
                # 🔥 检测是否是登录问题
                if '登录' in error_msg or 'login' in error_msg.lower() or '验证码' in error_msg:
                    task.add_log("WARNING", "检测到登录问题，尝试自动恢复...")
                    if self._auto_restore_login(task):
                        task.add_log("INFO", "✅ 登录恢复成功，继续采集")
                        continue
                    else:
                        task.add_log("ERROR", "❌ 登录恢复失败")
                
                if task_retry_count >= max_task_retries:
                    task.status = CollectionStatus.FAILED
                    task.error = error_msg
                    task.add_log("ERROR", f"采集失败，已达最大重试次数: {error_msg}")
                    logger.exception(f"采集任务异常: {task.task_id}")
                    break  # 退出重试循环
                else:
                    task.add_log("INFO", f"等待30秒后重试...")
                    time.sleep(30)
        
        # 任务结束处理
        task.finished_at = datetime.now()
        self._save_task(task)
        
        if self._current_task_id == task.task_id:
            self._current_task_id = None
    
    def _scan_matches(self, task: CollectionTask) -> Dict[str, List[Dict]]:
        """扫描比赛列表"""
        date_match_map = {}
        
        start_date = datetime.strptime(task.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(task.end_date, "%Y-%m-%d")
        
        current_date = start_date
        day_idx = 0
        
        while current_date <= end_date:
            if task.should_stop():
                break
            
            day_idx += 1
            date_str = current_date.strftime("%Y-%m-%d")
            task.progress.current_date = date_str
            task.progress.current_day = day_idx
            
            task.add_log("INFO", f"扫描 {date_str} ({day_idx}/{task.progress.total_days or '?'})")
            
            try:
                # 获取比赛列表（带自动重试和登录恢复）
                matches = self._fetch_matches_with_retry(task, current_date)
                
                if not matches:
                    task.add_log("INFO", f"  {date_str}: 无比赛数据")
                    current_date += timedelta(days=1)
                    continue
                
                # 过滤有盘口的比赛
                if task.filter_by_handicap:
                    matches = self._filter_by_handicap(task, date_str, matches)
                
                if matches:
                    date_match_map[date_str] = matches
                    task.add_log("INFO", f"  {date_str}: {len(matches)}场比赛")
                
            except Exception as e:
                task.add_log("ERROR", f"扫描 {date_str} 失败: {e}")
            
            current_date += timedelta(days=1)
            self._save_task(task)
            time.sleep(0.3)  # 减少扫描间隔
        
        return date_match_map
    
    def _fetch_matches_with_retry(self, task: CollectionTask, target_date: datetime) -> List[Dict]:
        """获取比赛列表（带自动重试和登录恢复）"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 检查登录状态
                if not self._check_and_restore_login(task):
                    task.add_log("ERROR", "登录恢复失败，暂停采集")
                    task.status = CollectionStatus.WAITING_LOGIN
                    task._pause_flag = True
                    return []
                
                # 获取比赛列表
                page_html, matches, metadata = self.bifaw_client.fetch_finished_matches(
                    target_date=target_date,
                    rows=9999,
                    auto_retry=True
                )
                
                return matches or []
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # 检测登录失效
                if '登录' in error_msg or 'login' in error_msg or '验证码' in error_msg:
                    task.add_log("WARNING", f"检测到登录失效，尝试恢复... (尝试 {attempt + 1}/{max_retries})")
                    
                    if self._auto_restore_login(task):
                        task.add_log("INFO", "✅ 登录恢复成功，继续采集")
                        continue
                    else:
                        task.add_log("ERROR", "登录恢复失败")
                        raise
                
                # 其他错误
                if attempt < max_retries - 1:
                    task.add_log("WARNING", f"获取比赛失败，重试... ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(2)
                else:
                    raise
        
        return []
    
    def _check_and_restore_login(self, task: CollectionTask) -> bool:
        """检查登录状态，如果失效则自动恢复"""
        try:
            # 🔥 使用快速检查（不发送网络请求）
            if self.bifaw_client._check_login_status_quick():
                return True
            
            # 快速检查失败，进行详细验证
            status = self.bifaw_client.get_cookie_status(verify=False)
            
            if status and status.get('valid'):
                return True
            
            task.add_log("WARNING", "检测到登录状态失效，尝试自动恢复...")
            return self._auto_restore_login(task)
            
        except Exception as e:
            task.add_log("ERROR", f"检查登录状态失败: {e}")
            return self._auto_restore_login(task)
    
    def _auto_restore_login(self, task: CollectionTask) -> bool:
        """自动恢复登录"""
        if task.login_retry_count >= task.max_login_retries:
            task.add_log("ERROR", f"登录重试次数已达上限 ({task.max_login_retries})")
            return False
        
        task.login_retry_count += 1
        task.last_login_attempt = datetime.now()
        task.status = CollectionStatus.WAITING_LOGIN
        self._save_task(task)
        
        task.add_log("INFO", f"🔐 开始OCR自动登录 (第{task.login_retry_count}次)")
        
        try:
            # 调用OCR自动登录
            success, message = self.bifaw_client._auto_login_with_ocr(max_retries=10, force=True)
            
            if success:
                task.add_log("INFO", f"✅ 自动登录成功: {message}")
                task.status = CollectionStatus.RUNNING
                task.login_retry_count = 0  # 重置计数
                self._save_task(task)
                return True
            else:
                task.add_log("ERROR", f"❌ 自动登录失败: {message}")
                return False
                
        except Exception as e:
            task.add_log("ERROR", f"自动登录异常: {e}")
            return False
    
    def _filter_by_handicap(self, task: CollectionTask, date_str: str, matches: List[Dict]) -> List[Dict]:
        """
        过滤有盘口的比赛
        
        🔥 修复：不再严格过滤，而是尝试匹配盘口信息，匹配不上的比赛也保留
        这样可以确保跨日期比赛（如12月3日查询返回12月4日凌晨的比赛）不会被漏掉
        """
        try:
            daily_handicaps = self.lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
            
            if not daily_handicaps:
                task.add_log("WARNING", f"  {date_str}: 无盘口数据，使用原始比赛列表")
                return matches
            
            task.add_log("INFO", f"  {date_str}: 获取到 {len(daily_handicaps)} 条盘口数据")
            
            # 构建500.com盘口索引
            handicap_map = {}
            for match_key, handicap_data in daily_handicaps.items():
                home_500 = handicap_data['home_team']
                away_500 = handicap_data['away_team']
                time_500 = handicap_data['time'][:5]
                
                home_clean = self.lottery500_client._clean_team_name(home_500)
                away_clean = self.lottery500_client._clean_team_name(away_500)
                
                # 多种匹配键
                for key in [
                    f"{home_clean}_{away_clean}_{time_500}",
                    f"{home_500}_{away_500}_{time_500}",
                    f"{home_clean}_{away_clean}",
                ]:
                    handicap_map[key] = handicap_data
            
            # 🔥 遍历所有比赛，尝试匹配盘口，匹配不上也保留
            result_matches = []
            matched_count = 0
            
            for match in matches:
                home = match.get('home_team', '') or match.get('home', '')
                away = match.get('away_team', '') or match.get('away', '')
                match_time = match.get('match_time', '') or match.get('kickoff', '')
                
                home_clean = self.lottery500_client._clean_team_name(home)
                away_clean = self.lottery500_client._clean_team_name(away)
                
                if ' ' in str(match_time):
                    time_str = str(match_time).split(' ')[1][:5]
                else:
                    time_str = str(match_time)[:5] if match_time else ''
                
                # 尝试匹配盘口
                handicap_data = None
                for key in [
                    f"{home_clean}_{away_clean}_{time_str}",
                    f"{home}_{away}_{time_str}",
                    f"{home_clean}_{away_clean}",
                ]:
                    if key in handicap_map:
                        handicap_data = handicap_map[key]
                        break
                
                merged_match = match.copy()
                if handicap_data:
                    merged_match['handicap_preview'] = {
                        'handicap_str': handicap_data['current_handicap_str'],
                        'handicap': handicap_data['current_handicap'],
                        'fid': handicap_data['fid']
                    }
                    matched_count += 1
                
                result_matches.append(merged_match)
            
            task.add_log("INFO", f"  {date_str}: {len(result_matches)}场比赛，{matched_count}场有盘口匹配")
            return result_matches
            
        except Exception as e:
            task.add_log("ERROR", f"过滤盘口失败: {e}")
            return matches

    
    def _collect_matches(self, task: CollectionTask, date_match_map: Dict[str, List[Dict]]):
        """采集比赛明细"""
        from parser.html_parser import parse_bifa_html
        
        day_idx = 0
        
        for date_str, matches in date_match_map.items():
            if task.should_stop() or task.should_pause():
                break
            
            day_idx += 1
            task.progress.current_date = date_str
            task.progress.current_day = day_idx
            
            task.add_log("INFO", f"📅 采集 {date_str} ({day_idx}/{task.progress.total_days}): {len(matches)}场")
            
            # 获取已处理的比赛（断点续传）
            processed_keys = set(task.progress.processed_matches.get(date_str, []))
            
            # 筛选需要采集的比赛
            matches_to_collect = []
            matches_ou_only = []  # 🔥 只需补采大小球的比赛（仅非四合一模式使用）
            
            for match in matches:
                match_key = self._get_match_key(match)
                
                # 检查是否已处理（断点续传）
                if match_key in processed_keys:
                    task.progress.skipped += 1
                    continue
                
                # 🔥 四合一模式：不检查分开的缓存，直接采集
                if task.super_mode:
                    # 四合一模式下，检查是否有四合一格式的缓存
                    if task.skip_cached and self._has_super_cache(match, date_str):
                        task.progress.skipped += 1
                        self._mark_match_processed(task, date_str, match_key)
                        continue
                    matches_to_collect.append(match)
                else:
                    # 🔥 非四合一模式：检查缓存，分别检查标盘和大小球
                    if task.skip_cached:
                        has_bp = self.detail_cache_manager.has_cache(match)
                        has_ou = self.detail_cache_manager.has_ou_cache(match)
                        
                        if has_bp and has_ou:
                            # 两个都有，完全跳过
                            task.progress.skipped += 1
                            self._mark_match_processed(task, date_str, match_key)
                            continue
                        elif has_bp and not has_ou:
                            # 标盘有、大小球没有，只补采大小球
                            matches_ou_only.append(match)
                            continue
                    
                    matches_to_collect.append(match)
            
            # 🔥 处理只需补采大小球的比赛（仅非四合一模式）
            if matches_ou_only and not task.super_mode:
                task.add_log("INFO", f"  {date_str}: {len(matches_ou_only)}场需补采大小球")
                for match in matches_ou_only:
                    # 🔥 检查暂停/停止
                    if task.should_stop() or task.should_pause():
                        task.add_log("INFO", "  补采中断（暂停/停止）")
                        self._save_task(task)
                        break
                    
                    match_label = match.get('label') or f"{match.get('home', '')} vs {match.get('away', '')}"
                    try:
                        self._collect_ou_detail(task, match, date_str)
                        task.add_log("INFO", f"    ✅ 补采完成: {match_label}")
                        task.progress.success += 1
                    except Exception as e:
                        task.add_log("WARNING", f"    ❌ 补采失败 {match_label}: {e}")
                        task.progress.failed += 1
                    self._mark_match_processed(task, date_str, self._get_match_key(match))
                # 🔥 补采完成后保存任务状态
                self._save_task(task)
            
            # 🔥 再次检查暂停/停止（补采可能已中断）
            if task.should_stop() or task.should_pause():
                break
            
            if not matches_to_collect:
                task.add_log("INFO", f"  {date_str}: 全部跳过（已处理或已缓存）")
                continue
            
            # 并发采集
            self._collect_matches_concurrent(task, date_str, matches_to_collect)
            
            self._save_task(task)
    
    def _collect_matches_concurrent(self, task: CollectionTask, date_str: str, matches: List[Dict]):
        """并发采集比赛明细"""
        from parser.html_parser import parse_bifa_html
        
        progress_queue = queue.Queue()
        
        # 🔥 如果是四合一模式，使用SuperCollector
        if task.super_mode:
            self._collect_matches_super_mode(task, date_str, matches, progress_queue)
            return
        
        def collect_single(match: Dict, idx: int, retry_count: int = 0):
            """采集单场比赛（🔥 增加网络错误重试机制）"""
            match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
            match_key = self._get_match_key(match)
            max_retries = 2  # 最多重试2次
            
            try:
                # 检查登录状态
                if not self._check_and_restore_login(task):
                    progress_queue.put({
                        'type': 'failed',
                        'match_key': match_key,
                        'label': match_label,
                        'error': '登录恢复失败'
                    })
                    return
                
                # 获取明细URL
                detail_url = match.get('detail_url')
                if not detail_url:
                    progress_queue.put({
                        'type': 'failed',
                        'match_key': match_key,
                        'label': match_label,
                        'error': '无明细URL'
                    })
                    return
                
                # 获取明细HTML
                detail_html = self.bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match,
                    detail_params=match.get('detail_params')
                )
                
                if not detail_html:
                    progress_queue.put({
                        'type': 'failed',
                        'match_key': match_key,
                        'label': match_label,
                        'error': '获取明细失败'
                    })
                    return
                
                # 解析明细
                parsed_data = parse_bifa_html(detail_html, match=match)
                
                if isinstance(parsed_data, str) or (hasattr(parsed_data, 'empty') and parsed_data.empty):
                    progress_queue.put({
                        'type': 'failed',
                        'match_key': match_key,
                        'label': match_label,
                        'error': '解析明细失败'
                    })
                    return
                
                # 获取盘口数据（🔥 现在获取所有机构）
                handicap_data = None
                if match.get('handicap_preview'):
                    fid = match['handicap_preview']['fid']
                    handicap_data = {
                        'fid': fid,
                        'current_handicap_str': match['handicap_preview']['handicap_str'],
                        'current_handicap': match['handicap_preview']['handicap']
                    }
                    # 🔥 获取所有机构让球盘口数据
                    try:
                        asian_data = self.lottery500_client.fetch_asian_data(fid)
                        if asian_data:
                            handicap_data['all_companies'] = asian_data.get('all_companies', [])
                            handicap_data['aomen'] = asian_data.get('aomen', {})
                            handicap_data['huangguan'] = asian_data.get('huangguan', {})
                            handicap_data['bet365'] = asian_data.get('bet365', {})
                            handicap_data['avg_handicap'] = asian_data.get('avg_handicap')
                            handicap_data['handicap_up_count'] = asian_data.get('handicap_up_count')
                            handicap_data['handicap_down_count'] = asian_data.get('handicap_down_count')
                    except Exception as e:
                        logger.debug(f"获取所有机构盘口失败: {e}")
                
                # 保存到缓存
                metadata = parsed_data.attrs.get("metadata", []) if hasattr(parsed_data, 'attrs') else []
                success = self.detail_cache_manager.save_detail(
                    match_info=match,
                    trade_data=parsed_data,
                    handicap_data=handicap_data or {},
                    metadata=metadata,
                    html_content=detail_html
                )
                
                if success:
                    # 🔥 采集大小球明细（机构盘口 + 交易明细）
                    try:
                        self._collect_ou_detail(task, match, date_str)
                    except Exception as ou_err:
                        task.add_log("WARNING", f"    大小球明细采集失败: {ou_err}")
                    
                    progress_queue.put({
                        'type': 'success',
                        'match_key': match_key,
                        'label': match_label,
                        'rows': len(parsed_data)
                    })
                else:
                    progress_queue.put({
                        'type': 'failed',
                        'match_key': match_key,
                        'label': match_label,
                        'error': '保存失败'
                    })
                
            except Exception as e:
                error_msg = str(e)
                
                # 🔥 检测网络连接错误，自动重试
                network_errors = ['CONNECTION_CLOSED', 'ERR_CONNECTION', '意外终止', '连接被重置', 
                                  'ConnectionError', 'TimeoutError', 'connection reset', 'timed out']
                is_network_error = any(err.lower() in error_msg.lower() for err in network_errors)
                
                if is_network_error and retry_count < max_retries:
                    task.add_log("WARNING", f"    ⚠️ 网络错误，{retry_count + 1}/{max_retries}次重试: {match_label}")
                    time.sleep(3)  # 等待3秒后重试
                    return collect_single(match, idx, retry_count + 1)
                
                # 检测登录失效
                if '登录' in error_msg or 'login' in error_msg.lower():
                    # 尝试恢复登录
                    if self._auto_restore_login(task):
                        # 登录恢复成功，重新尝试
                        try:
                            return collect_single(match, idx, retry_count)
                        except:
                            pass
                
                progress_queue.put({
                    'type': 'failed',
                    'match_key': match_key,
                    'label': match_label,
                    'error': error_msg[:100]
                })
        
        # 使用线程池并发采集（🔥 增加请求间隔避免被限流）
        with ThreadPoolExecutor(max_workers=task.workers) as executor:
            futures = {}
            for idx, match in enumerate(matches):
                if task.should_stop() or task.should_pause():
                    break
                future = executor.submit(collect_single, match, idx)
                futures[future] = idx
                # 🔥 每提交一个任务后等待1秒，避免请求过于密集
                time.sleep(1.0)
            
            # 处理结果
            completed = 0
            total = len(matches)
            
            while completed < total:
                if task.should_stop() or task.should_pause():
                    # 取消未完成的任务
                    for future in futures:
                        future.cancel()
                    break
                
                try:
                    result = progress_queue.get(timeout=1)
                    completed += 1
                    
                    match_key = result.get('match_key')
                    match_label = result.get('label')
                    
                    if result['type'] == 'success':
                        task.progress.success += 1
                        task.add_log("INFO", f"  ✅ {match_label} ({result.get('rows', 0)}行)")
                    else:
                        task.progress.failed += 1
                        task.add_log("WARNING", f"  ❌ {match_label}: {result.get('error')}")
                    
                    # 标记已处理
                    self._mark_match_processed(task, date_str, match_key)
                    
                    # 更新进度
                    task.progress.current_match = completed
                    task.progress.current_match_label = match_label
                    
                    # 定期保存进度
                    if completed % 10 == 0:
                        self._save_task(task)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"处理采集结果失败: {e}")
        
        task.add_log("INFO", f"  {date_str} 完成: 成功{task.progress.success}, 失败{task.progress.failed}")
    
    def _collect_matches_super_mode(self, task: CollectionTask, date_str: str, matches: List[Dict], progress_queue: queue.Queue):
        """
        🔥 四合一模式采集比赛明细
        采集内容：标盘、大小球、让球指数、比分
        """
        from services.super_collector import SuperCollector
        from parser.super_detail_parser import create_super_json, save_super_json
        from parser.html_parser import parse_bifa_html
        from parser.super_detail_parser import parse_handicap_trade_html, parse_correct_score_html
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import json
        from pathlib import Path
        
        task.add_log("INFO", f"  🔥 四合一模式采集 {len(matches)} 场比赛")
        
        driver = None
        try:
            # 初始化浏览器
            driver = self.bifaw_client._init_driver(headless=True)
            self.bifaw_client._inject_cookies(driver)
            
            # 访问首页建立session
            driver.get("https://www.bifaw.com/bifaw/index.php")
            time.sleep(2)
            
            for idx, match in enumerate(matches):
                if task.should_stop() or task.should_pause():
                    break
                
                # 🔥 记录当前比赛开始时间
                import time as time_module
                match_start_time = time_module.time()
                task.progress.current_match_start_time = match_start_time
                
                match_label = match.get('label') or f"{match.get('home', '')} vs {match.get('away', '')}"
                match_key = self._get_match_key(match)
                home_team = match.get('home') or match.get('home_team') or ''
                away_team = match.get('away') or match.get('away_team') or ''
                
                # 🔥 验证必要字段
                if not home_team or not away_team:
                    task.add_log("WARNING", f"  [{idx+1}/{len(matches)}] ⚠️ 跳过：缺少队伍名称")
                    task.progress.failed += 1
                    continue
                
                task.progress.current_match = idx + 1
                task.progress.current_match_label = match_label
                task.add_log("INFO", f"  [{idx+1}/{len(matches)}] 采集: {match_label}")
                
                try:
                    # 收集所有URL
                    urls = {
                        'standard_url': match.get('detail_url'),
                    }
                    
                    # 🔥 获取实际开球日期（处理跨日比赛）
                    kickoff = match.get('kickoff', '') or match.get('match_time', '')
                    if kickoff and ' ' in str(kickoff):
                        actual_date = str(kickoff).split(' ')[0]  # 使用实际开球日期
                    else:
                        actual_date = date_str
                    
                    task.add_log("DEBUG", f"    查询日期: {date_str}, 实际开球日期: {actual_date}")
                    
                    # ========== 1. 访问让球回查页面获取让球URL ==========
                    aisa_url = f"https://www.bifaw.com/bifaw/result_aisa.php?rq={actual_date}"
                    driver.get(aisa_url)
                    time.sleep(3)
                    
                    # 设置日期并查询
                    try:
                        date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                        if date_input:
                            driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                            query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                            if query_btn:
                                query_btn.click()
                                time.sleep(5)
                    except:
                        pass
                    
                    # 获取让球盘口信息
                    handicap_info = self._get_handicap_info(driver, home_team, away_team)
                    if handicap_info.get('found'):
                        urls['handicap_all_lines'] = handicap_info.get('handicaps', [])
                        urls['handicap_main_line'] = handicap_info.get('mainLineHome')
                        urls['handicap_info'] = handicap_info  # 🔥 保存完整info用于后续采集
                    
                    # ========== 2. 访问大小球回查页面获取大小球URL ==========
                    ou_page_url = f"https://www.bifaw.com/bifaw/result_ou.php?rq={actual_date}"
                    driver.get(ou_page_url)
                    time.sleep(3)
                    
                    try:
                        date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                        if date_input:
                            driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                            query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                            if query_btn:
                                query_btn.click()
                                time.sleep(5)
                    except:
                        pass
                    
                    # 获取大小球盘口信息
                    ou_info = self._get_ou_info(driver, home_team, away_team)
                    if ou_info.get('found'):
                        urls['ou_all_lines'] = ou_info.get('lines', [])
                        urls['ou_main_line'] = ou_info.get('mainLine')
                        urls['ou_info'] = ou_info  # 🔥 保存完整info用于后续采集
                    
                    # ========== 3. 访问比分回查页面获取比分URL ==========
                    correct_page_url = f"https://www.bifaw.com/bifaw/result_correct.php?rq={actual_date}"
                    driver.get(correct_page_url)
                    time.sleep(3)
                    
                    try:
                        date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                        if date_input:
                            driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                            query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                            if query_btn:
                                query_btn.click()
                                time.sleep(5)
                    except:
                        pass
                    
                    # 获取比分URL
                    correct_url = self._get_correct_score_url(driver, home_team, away_team)
                    if correct_url:
                        urls['correct_score_url'] = correct_url
                    
                    # ========== 4. 采集各类数据 ==========
                    standard_data = None
                    ou_data_list = []  # 🔥 改为列表，存储多个盘口
                    handicap_data_list = []  # 🔥 改为列表，存储多个盘口
                    correct_score_data = None
                    
                    # 采集标盘数据
                    if urls.get('standard_url'):
                        standard_data = self._collect_standard_data_selenium(driver, urls['standard_url'], match)
                    
                    # ========== 🔥 采集大小球数据（全部盘口）==========
                    ou_info = urls.get('ou_info', {})
                    ou_lines = ou_info.get('lines', [])
                    ou_table_index = ou_info.get('tableIndex')
                    
                    if ou_lines and ou_table_index is not None:
                        # 重新访问大小球页面
                        ou_page_url = f"https://www.bifaw.com/bifaw/result_ou.php?rq={actual_date}"
                        driver.get(ou_page_url)
                        time.sleep(3)
                        try:
                            date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                            if date_input:
                                driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                                query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                                if query_btn:
                                    query_btn.click()
                                    time.sleep(5)
                        except:
                            pass
                        
                        # 采集所有大小球盘口
                        for line_info in ou_lines:
                            btn_index = line_info.get('btn_index')
                            line_value = line_info.get('line')
                            if btn_index is not None:
                                ou_url = self._click_btn_by_index_and_get_url(driver, ou_table_index, btn_index, 'ou')
                                if ou_url:
                                    ou_data = self._collect_trade_data_selenium(driver, ou_url, 'ou', line_value)
                                    if ou_data:
                                        ou_data['line'] = line_value
                                        ou_data_list.append(ou_data)
                                        task.add_log("INFO", f"      大小球盘口 {line_value}: {ou_data.get('total_records', 0)}条")
                                # 重新访问页面准备下一个盘口
                                driver.get(ou_page_url)
                                time.sleep(2)
                                try:
                                    date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                                    if date_input:
                                        driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                                        query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                                        if query_btn:
                                            query_btn.click()
                                            time.sleep(3)
                                except:
                                    pass
                    
                    # ========== 🔥 采集让球数据（主盘口 + 交易量前4）==========
                    handicap_info = urls.get('handicap_info', {})
                    handicap_lines = handicap_info.get('handicaps', [])
                    handicap_table_index = handicap_info.get('tableIndex')
                    
                    if handicap_lines and handicap_table_index is not None:
                        # 按交易量排序，选择前5个（包含主盘口）
                        sorted_lines = sorted(handicap_lines, key=lambda x: x.get('volume', 0) or 0, reverse=True)
                        # 确保主盘口在列表中
                        main_line = handicap_info.get('mainLine')
                        top_lines = []
                        main_included = False
                        for line in sorted_lines:
                            if line.get('hdp_away') == main_line:
                                top_lines.insert(0, line)  # 主盘口放第一个
                                main_included = True
                            elif len(top_lines) < 5:
                                top_lines.append(line)
                        # 如果主盘口不在前5，确保添加
                        if not main_included:
                            for line in handicap_lines:
                                if line.get('hdp_away') == main_line:
                                    top_lines.insert(0, line)
                                    if len(top_lines) > 5:
                                        top_lines = top_lines[:5]
                                    break
                        
                        # 重新访问让球页面
                        aisa_url = f"https://www.bifaw.com/bifaw/result_aisa.php?rq={actual_date}"
                        driver.get(aisa_url)
                        time.sleep(3)
                        try:
                            date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                            if date_input:
                                driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                                query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                                if query_btn:
                                    query_btn.click()
                                    time.sleep(5)
                        except:
                            pass
                        
                        # 采集选中的让球盘口
                        for line_info in top_lines:
                            btn_index = line_info.get('btn_index')
                            hdp_home = line_info.get('hdp_home')
                            hdp_away = line_info.get('hdp_away')
                            if btn_index is not None:
                                handicap_url = self._click_btn_by_index_and_get_url(driver, handicap_table_index, btn_index, 'handicap')
                                if handicap_url:
                                    handicap_data = self._collect_trade_data_selenium(driver, handicap_url, 'handicap', hdp_home)
                                    if handicap_data:
                                        handicap_data['handicap_line'] = hdp_home
                                        handicap_data['hdp_away'] = hdp_away
                                        handicap_data_list.append(handicap_data)
                                        task.add_log("INFO", f"      让球盘口 {hdp_home}: {handicap_data.get('total_records', 0)}条")
                                # 重新访问页面准备下一个盘口
                                driver.get(aisa_url)
                                time.sleep(2)
                                try:
                                    date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                                    if date_input:
                                        driver.execute_script(f"arguments[0].value = '{actual_date}';", date_input)
                                        query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                                        if query_btn:
                                            query_btn.click()
                                            time.sleep(3)
                                except:
                                    pass
                    
                    # 采集比分数据
                    if urls.get('correct_score_url'):
                        correct_score_data = self._collect_trade_data_selenium(driver, urls['correct_score_url'], 'correct_score')
                    
                    # ========== 5. 创建并保存超级JSON ==========
                    match_info = {
                        'match_id': match.get('match_id', ''),
                        'date': date_str,
                        'home': home_team,
                        'away': away_team,
                        'league': match.get('league', ''),
                        'kickoff': match.get('kickoff', ''),
                        'score': match.get('score', ''),
                        **{k: v for k, v in urls.items() if k not in ['ou_info', 'handicap_info']}
                    }
                    
                    super_json = create_super_json(
                        match_info=match_info,
                        standard_data=standard_data,
                        ou_data=ou_data_list[0] if ou_data_list else None,  # 主盘口数据
                        handicap_data=handicap_data_list[0] if handicap_data_list else None,  # 主盘口数据
                        correct_score_data=correct_score_data,
                        handicap_all_lines=urls.get('handicap_all_lines'),
                        ou_all_lines=urls.get('ou_all_lines'),
                        handicap_main_line=urls.get('handicap_main_line'),
                        ou_main_line=urls.get('ou_main_line'),
                    )
                    
                    # 🔥 添加多盘口交易明细数据
                    if len(ou_data_list) > 1:
                        super_json['ou_trade_all'] = ou_data_list  # 所有大小球盘口数据
                    if len(handicap_data_list) > 1:
                        super_json['handicap_trade_all'] = handicap_data_list  # 所有让球盘口数据（前5）
                    
                    # 🔥 更新数据摘要
                    if '_数据摘要' in super_json:
                        super_json['_数据摘要']['大小球']['采集盘口数'] = len(ou_data_list)
                        super_json['_数据摘要']['让球_亚盘']['采集盘口数'] = len(handicap_data_list)
                    
                    # 保存文件
                    kickoff = match.get('kickoff', '')
                    if kickoff and ' ' in kickoff:
                        kickoff_date = kickoff.split(' ')[0]
                        year, month, day = kickoff_date.split('-')
                    else:
                        year, month, day = date_str.split('-')
                    
                    if self.detail_cache_manager and hasattr(self.detail_cache_manager, 'cache_dir'):
                        base_dir = Path(self.detail_cache_manager.cache_dir)
                    else:
                        base_dir = Path(__file__).parent.parent / "data"
                    
                    save_dir = base_dir / year / month / day
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 生成文件名
                    kickoff_time = ''
                    if kickoff and ' ' in kickoff:
                        kickoff_time = kickoff.split(' ')[1].replace(':', '')[:4]
                    
                    league = (match.get('league') or '').replace('/', '_').replace(' ', '_')
                    home_clean = (home_team or '').replace('/', '_').replace(' ', '_')
                    away_clean = (away_team or '').replace('/', '_').replace(' ', '_')
                    score = (match.get('score') or '').replace('-', '_').replace(' ', '')
                    
                    filename = f"{year}{month}{day}_{kickoff_time}_{league}_{home_clean}_vs_{away_clean}"
                    if score:
                        filename += f"_{score}"
                    filename += ".json"
                    
                    filepath = save_dir / filename
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(super_json, f, ensure_ascii=False, indent=2)
                    
                    task.progress.success += 1
                    task.add_log("INFO", f"    ✅ 四合一采集完成: {filename}")
                    
                    # 🔥 更新时间统计
                    match_elapsed = time_module.time() - match_start_time
                    task.progress.total_elapsed_seconds += match_elapsed
                    # 计算平均用时（只统计成功的）
                    if task.progress.success > 0:
                        task.progress.avg_time_per_match = task.progress.total_elapsed_seconds / task.progress.success
                    task.add_log("DEBUG", f"    ⏱️ 本场用时: {match_elapsed:.1f}秒, 平均: {task.progress.avg_time_per_match:.1f}秒")
                    
                except Exception as e:
                    task.progress.failed += 1
                    task.add_log("WARNING", f"    ❌ 采集失败: {str(e)[:100]}")
                    
                    # 🔥 失败也要更新时间统计
                    match_elapsed = time_module.time() - match_start_time
                    task.progress.total_elapsed_seconds += match_elapsed
                    if task.progress.processed > 0:
                        task.progress.avg_time_per_match = task.progress.total_elapsed_seconds / task.progress.processed
                
                # 标记已处理
                self._mark_match_processed(task, date_str, match_key)
                
                # 定期保存进度
                if (idx + 1) % 5 == 0:
                    self._save_task(task)
                
                # 请求间隔
                time.sleep(1)
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        task.add_log("INFO", f"  {date_str} 四合一采集完成: 成功{task.progress.success}, 失败{task.progress.failed}")
    
    def _get_handicap_info(self, driver, home_team: str, away_team: str) -> Dict:
        """获取让球盘口信息（包含交易量用于排序）"""
        js_code = f"""
        var tables = document.querySelectorAll('table');
        var homeTeam = '{home_team}';
        var awayTeam = '{away_team}';
        var result = {{found: false, handicaps: [], mainLine: null, mainLineHome: null, tableIndex: null}};
        
        for (var t = 0; t < tables.length; t++) {{
            var table = tables[t];
            var tableText = table.innerText;
            
            if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                result.found = true;
                result.tableIndex = t;
                
                var btns = table.querySelectorAll('[onclick*="openAisaDetails"]');
                for (var i = 0; i < btns.length; i++) {{
                    var btn = btns[i];
                    var onclick = btn.getAttribute('onclick');
                    var match = onclick.match(/openAisaDetails\\('[^']+','[^']+','[^']+','[^']+','[^']+','([^']+)'/);
                    if (!match) continue;
                    
                    var hdpAway = match[1];
                    var row = btn.closest('tr');
                    if (!row) continue;
                    
                    var cells = row.querySelectorAll('td');
                    var hdpHome = null;
                    var sb = null;
                    var volume = 0;  // 🔥 新增：交易量
                    
                    for (var c = 0; c < Math.min(cells.length, 5); c++) {{
                        var cellText = cells[c].innerText.trim();
                        if (cellText.match(/^[+-]?\\d+(\\.\\d+)?$/) || cellText.match(/^[+-]?\\d+\\/\\d+$/)) {{
                            hdpHome = cellText;
                            break;
                        }}
                    }}
                    
                    // 🔥 查找SB值和交易量
                    for (var c = 5; c < cells.length; c++) {{
                        var cellText = cells[c].innerText.trim().replace(/,/g, '');
                        // 交易量通常是大数字（>1000）
                        if (cellText.match(/^\\d+$/) && parseInt(cellText) > 1000) {{
                            volume = parseInt(cellText);
                        }}
                        // SB值通常是小数（-5到5之间）
                        if (cellText.match(/^-?\\d+\\.\\d+$/) && parseFloat(cellText) < 10 && parseFloat(cellText) > -10) {{
                            var num = parseFloat(cellText);
                            if (Math.abs(num) < 5 && sb === null) {{
                                sb = cellText;
                            }}
                        }}
                    }}
                    
                    result.handicaps.push({{
                        hdp_away: hdpAway, 
                        hdp_home: hdpHome, 
                        sb: sb, 
                        volume: volume,  // 🔥 新增
                        is_main: sb !== null && sb !== '',
                        btn_index: i  // 🔥 新增：按钮索引
                    }});
                    
                    if (sb !== null && sb !== '' && result.mainLine === null) {{
                        result.mainLine = hdpAway;
                        result.mainLineHome = hdpHome;
                    }}
                }}
                break;
            }}
        }}
        return result;
        """
        try:
            return driver.execute_script(js_code) or {'found': False}
        except:
            return {'found': False}
    
    def _get_ou_info(self, driver, home_team: str, away_team: str) -> Dict:
        """获取大小球盘口信息（包含交易量和按钮索引）"""
        js_code = f"""
        var tables = document.querySelectorAll('table');
        var homeTeam = '{home_team}';
        var awayTeam = '{away_team}';
        var result = {{found: false, lines: [], mainLine: null, tableIndex: null}};
        
        for (var t = 0; t < tables.length; t++) {{
            var table = tables[t];
            var tableText = table.innerText;
            
            if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                result.found = true;
                result.tableIndex = t;
                
                var btns = table.querySelectorAll('[onclick*="openOuDetails"]');
                for (var i = 0; i < btns.length; i++) {{
                    var btn = btns[i];
                    var onclick = btn.getAttribute('onclick');
                    var match = onclick.match(/openOuDetails\\('[^']+','[^']+','[^']+','[^']+','[^']+','([^']+)'/);
                    if (!match) continue;
                    
                    var line = match[1];
                    var row = btn.closest('tr');
                    if (!row) continue;
                    
                    var cells = row.querySelectorAll('td');
                    var sb = null;
                    var volume = 0;  // 🔥 新增：交易量
                    
                    for (var c = 5; c < cells.length; c++) {{
                        var cellText = cells[c].innerText.trim().replace(/,/g, '');
                        // 交易量通常是大数字（>1000）
                        if (cellText.match(/^\\d+$/) && parseInt(cellText) > 1000) {{
                            volume = parseInt(cellText);
                        }}
                        // SB值通常是小数（-5到5之间）
                        if (cellText.match(/^-?\\d+\\.\\d+$/) && parseFloat(cellText) < 10 && parseFloat(cellText) > -10) {{
                            var num = parseFloat(cellText);
                            if (Math.abs(num) < 5 && sb === null) {{
                                sb = cellText;
                            }}
                        }}
                    }}
                    
                    result.lines.push({{
                        line: line, 
                        sb: sb, 
                        volume: volume,  // 🔥 新增
                        is_main: sb !== null && sb !== '',
                        btn_index: i  // 🔥 新增：按钮索引
                    }});
                    
                    if (sb !== null && sb !== '' && result.mainLine === null) {{
                        result.mainLine = line;
                    }}
                }}
                break;
            }}
        }}
        return result;
        """
        try:
            return driver.execute_script(js_code) or {'found': False}
        except:
            return {'found': False}
    
    def _get_correct_score_url(self, driver, home_team: str, away_team: str) -> Optional[str]:
        """获取比分URL"""
        js_code = f"""
        var tables = document.querySelectorAll('table');
        var homeTeam = '{home_team}';
        var awayTeam = '{away_team}';
        
        for (var t = 0; t < tables.length; t++) {{
            var table = tables[t];
            var tableText = table.innerText;
            
            if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                var btn = table.querySelector('[onclick*="openCorrectDetails"]');
                if (btn) {{
                    btn.click();
                    return {{found: true}};
                }}
            }}
        }}
        return {{found: false}};
        """
        try:
            result = driver.execute_script(js_code)
            if result and result.get('found'):
                time.sleep(2)
                windows = driver.window_handles
                if len(windows) > 1:
                    driver.switch_to.window(windows[-1])
                    url = driver.current_url
                    driver.close()
                    driver.switch_to.window(windows[0])
                    return url
        except:
            pass
        return None
    
    def _click_and_get_url(self, driver, info: Dict, data_type: str) -> Optional[str]:
        """点击按钮并获取URL"""
        table_index = info.get('tableIndex')
        if table_index is None:
            return None
        
        if data_type == 'handicap':
            main_value = info.get('mainLine')
            js_code = f"""
            var tables = document.querySelectorAll('table');
            var table = tables[{table_index}];
            var btns = table.querySelectorAll('[onclick*="openAisaDetails"]');
            for (var i = 0; i < btns.length; i++) {{
                var btn = btns[i];
                var onclick = btn.getAttribute('onclick');
                if (onclick.indexOf("'{main_value}'") !== -1) {{
                    btn.click();
                    return {{found: true}};
                }}
            }}
            return {{found: false}};
            """
        else:  # ou
            main_value = info.get('mainLine')
            js_code = f"""
            var tables = document.querySelectorAll('table');
            var table = tables[{table_index}];
            var btns = table.querySelectorAll('[onclick*="openOuDetails"]');
            for (var i = 0; i < btns.length; i++) {{
                var btn = btns[i];
                var onclick = btn.getAttribute('onclick');
                if (onclick.indexOf("'{main_value}'") !== -1) {{
                    btn.click();
                    return {{found: true}};
                }}
            }}
            return {{found: false}};
            """
        
        try:
            result = driver.execute_script(js_code)
            if result and result.get('found'):
                time.sleep(2)
                windows = driver.window_handles
                if len(windows) > 1:
                    driver.switch_to.window(windows[-1])
                    url = driver.current_url
                    driver.close()
                    driver.switch_to.window(windows[0])
                    return url
        except:
            pass
        return None
    
    def _click_btn_by_index_and_get_url(self, driver, table_index: int, btn_index: int, data_type: str) -> Optional[str]:
        """
        🔥 点击指定索引的按钮并获取URL
        
        Args:
            driver: Selenium driver
            table_index: 表格索引
            btn_index: 按钮索引
            data_type: 'handicap' 或 'ou'
        """
        if data_type == 'handicap':
            js_code = f"""
            var tables = document.querySelectorAll('table');
            var table = tables[{table_index}];
            var btns = table.querySelectorAll('[onclick*="openAisaDetails"]');
            if (btns.length > {btn_index}) {{
                btns[{btn_index}].click();
                return {{found: true}};
            }}
            return {{found: false}};
            """
        else:  # ou
            js_code = f"""
            var tables = document.querySelectorAll('table');
            var table = tables[{table_index}];
            var btns = table.querySelectorAll('[onclick*="openOuDetails"]');
            if (btns.length > {btn_index}) {{
                btns[{btn_index}].click();
                return {{found: true}};
            }}
            return {{found: false}};
            """
        
        try:
            result = driver.execute_script(js_code)
            if result and result.get('found'):
                time.sleep(2)
                windows = driver.window_handles
                if len(windows) > 1:
                    driver.switch_to.window(windows[-1])
                    url = driver.current_url
                    driver.close()
                    driver.switch_to.window(windows[0])
                    return url
        except:
            pass
        return None
    
    def _collect_standard_data_selenium(self, driver, url: str, match: Dict) -> Optional[Dict]:
        """使用Selenium采集标盘数据"""
        from parser.html_parser import parse_bifa_html
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        
        try:
            driver.get(url)
            time.sleep(3)
            
            all_rows = []
            columns = []
            page = 1
            max_pages = 50
            
            while page <= max_pages:
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tr")) > 5
                    )
                    time.sleep(1)
                except:
                    if page == 1:
                        logger.warning("标盘数据表格加载超时")
                    break
                
                html = driver.page_source
                df = parse_bifa_html(html, match)
                
                if hasattr(df, 'to_dict') and len(df) > 0:
                    if not columns:
                        columns = df.columns.tolist()
                    page_rows = df.to_dict(orient="records")
                    all_rows.extend(page_rows)
                else:
                    break
                
                try:
                    next_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                    if next_link:
                        next_link.click()
                        time.sleep(2)
                        page += 1
                    else:
                        break
                except:
                    break
            
            if all_rows:
                return {
                    "columns": columns,
                    "data": all_rows,
                    "total_records": len(all_rows)
                }
        except Exception as e:
            logger.warning(f"采集标盘数据失败: {e}")
        return None
    
    def _collect_trade_data_selenium(self, driver, url: str, data_type: str, line_value: str = None) -> Optional[Dict]:
        """使用Selenium采集交易数据（让球/大小球/比分）- 使用与标盘相同的格式"""
        from parser.super_detail_parser import parse_handicap_trade_html, parse_ou_trade_html, parse_correct_score_html
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        
        try:
            driver.get(url)
            time.sleep(3)
            
            all_records = []
            page = 1
            max_pages = 50
            columns = None
            
            while page <= max_pages:
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, "#table_1 tr.item")) > 0
                    )
                    time.sleep(1)
                except:
                    if page == 1:
                        logger.warning(f"{data_type}数据表格加载超时")
                    break
                
                html = driver.page_source
                
                # 🔥 根据数据类型选择不同的解析函数
                if data_type == 'handicap':
                    page_data = parse_handicap_trade_html(html)
                elif data_type == 'ou':
                    page_data = parse_ou_trade_html(html)
                else:
                    page_data = parse_correct_score_html(html)
                
                # 🔥 适配新格式：data 而不是 trade_records
                records = page_data.get('data', []) or page_data.get('trade_records', [])
                if not records:
                    break
                
                # 保存列名
                if columns is None and page_data.get('columns'):
                    columns = page_data.get('columns')
                
                all_records.extend(records)
                
                try:
                    next_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                    if next_link:
                        next_link.click()
                        time.sleep(2)
                        page += 1
                    else:
                        break
                except:
                    break
            
            if all_records:
                # 🔥 使用与标盘相同的格式
                result = {
                    "columns": columns or [],
                    "data": all_records,
                    "total_records": len(all_records)
                }
                
                if data_type == 'ou':
                    result['ou_line'] = line_value
                elif data_type == 'handicap':
                    result['handicap_line'] = line_value
                
                return result
        except Exception as e:
            logger.warning(f"采集{data_type}数据失败: {e}")
        return None
    
    def _has_super_cache(self, match: Dict, date_str: str) -> bool:
        """
        🔥 检查是否有四合一格式的缓存文件
        """
        from pathlib import Path
        
        try:
            # 提取比赛信息
            home = match.get('home', '') or match.get('home_team', '') or 'H'
            away = match.get('away', '') or match.get('away_team', '') or 'A'
            league = match.get('league', '') or match.get('league_name', '') or ''
            kickoff = match.get('kickoff', '') or match.get('match_time', '')
            score = match.get('score', '')
            
            # 清理特殊字符
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
                home = home.replace(char, '_')
                away = away.replace(char, '_')
                league = league.replace(char, '_')
            
            # 解析日期和时间
            if ' ' in str(kickoff):
                parts = str(kickoff).split(' ')
                kickoff_date = parts[0]
                kickoff_time = parts[1].replace(':', '')[:4]
            else:
                kickoff_date = date_str
                kickoff_time = str(kickoff).replace(':', '')[:4] if kickoff else ''
            
            # 构建文件路径
            if self.detail_cache_manager and hasattr(self.detail_cache_manager, 'cache_dir'):
                base_dir = Path(self.detail_cache_manager.cache_dir)
            else:
                base_dir = Path(__file__).parent.parent / "data"
            
            year, month, day = kickoff_date.split('-')
            save_dir = base_dir / year / month / day
            
            # 检查四合一格式的文件（不带 _大小球明细 后缀）
            score_clean = score.replace(' ', '').replace('-', '_') if score else ''
            score_suffix = f"_{score_clean}" if score_clean else ''
            
            # 尝试多种文件名格式
            possible_names = [
                f"{year}{month}{day}_{kickoff_time}_{league}_{home}_vs_{away}{score_suffix}.json",
                f"{kickoff_date}_{kickoff_time}_{league}_{home}_vs_{away}{score_suffix}.json",
            ]
            
            for filename in possible_names:
                filepath = save_dir / filename
                if filepath.exists():
                    # 检查文件内容是否是四合一格式
                    try:
                        import json
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # 四合一格式有 format: super_detail 或 version: 2.x
                        if data.get('format') == 'super_detail' or str(data.get('version', '')).startswith('2'):
                            return True
                    except:
                        pass
            
            return False
        except Exception as e:
            logger.debug(f"检查四合一缓存失败: {e}")
            return False
    
    def _get_match_key(self, match: Dict) -> str:
        """生成比赛唯一标识"""
        home = match.get('home', '') or match.get('home_team', '')
        away = match.get('away', '') or match.get('away_team', '')
        kickoff = match.get('kickoff', '') or match.get('match_time', '')
        return f"{home}_{away}_{kickoff}"
    
    def _mark_match_processed(self, task: CollectionTask, date_str: str, match_key: str):
        """标记比赛已处理"""
        if date_str not in task.progress.processed_matches:
            task.progress.processed_matches[date_str] = []
        if match_key not in task.progress.processed_matches[date_str]:
            task.progress.processed_matches[date_str].append(match_key)
    
    def _collect_ou_detail(self, task: CollectionTask, match: Dict, date_str: str):
        """
        采集大小球交易明细（直接从bifaw获取，SB列就是盘口）
        """
        import json
        from pathlib import Path
        from datetime import datetime
        
        # 提取比赛信息（与标盘 _generate_cache_key 完全一致）
        home = match.get('home', '') or match.get('home_team', '') or 'H'
        away = match.get('away', '') or match.get('away_team', '') or 'A'
        league = match.get('league', '') or match.get('league_name', '') or ''
        kickoff = match.get('kickoff', '') or match.get('match_time', '')
        score = match.get('score', '')
        
        # 🔥 清理特殊字符（与标盘保持一致）
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
            home = home.replace(char, '_')
            away = away.replace(char, '_')
            league = league.replace(char, '_')
        
        # 解析开赛时间和日期（与标盘 _generate_cache_key 保持一致）
        if ' ' in str(kickoff):
            parts = str(kickoff).split(' ')
            kickoff_date = parts[0]  # 🔥 使用实际开赛日期，而非查询日期
            kickoff_time = parts[1].replace(':', '')[:4]  # 🔥 统一格式：HHMM
        else:
            # 🔥 优先使用 kickoff_date，然后是 query_date，最后是 date_str
            kickoff_date = match.get('kickoff_date', '') or match.get('query_date', '') or date_str
            kickoff_time = str(kickoff).replace(':', '')[:4] if kickoff else ''
        
        # 🔥 直接获取bifaw大小球交易明细（SB列包含盘口信息）
        try:
            # 🔥 检查是否有预先捕获的大小球URL
            ou_url = match.get('ou_detail_url')
            if not ou_url:
                task.add_log("DEBUG", f"    ⚠️ 无预捕获的大小球URL，尝试构造...")
            
            match_for_detail = {'match_info': match}
            has_score = bool(score)
            
            result = self.bifaw_client.fetch_ou_trade_details_selenium(
                match_for_detail,
                timeout=30,
                is_finished=has_score
            )
            
            # 🔥 如果没有结果，记录警告
            if not result:
                task.add_log("DEBUG", f"    ⚠️ 大小球明细返回空")
                return
            
            # 🔥 不管有没有交易数据都保存（SB列=盘口信息保存在result中）
            if result:
                # 🔥 使用与标盘相同的保存目录（通过detail_cache_manager获取绝对路径）
                if self.detail_cache_manager and hasattr(self.detail_cache_manager, 'cache_dir'):
                    base_dir = Path(self.detail_cache_manager.cache_dir)
                else:
                    base_dir = Path(__file__).parent.parent / "data"
                
                # 🔥 使用实际开赛日期而非查询日期
                year, month, day = kickoff_date.split('-')
                save_dir = base_dir / year / month / day
                save_dir.mkdir(parents=True, exist_ok=True)
                
                # 🔥 文件命名统一格式（与标盘一致）：日期_时间_联赛_主队_vs_客队_比分_大小球明细.json
                # 比分格式：2-1 -> 2_1（与标盘一致）
                score_clean = score.replace(' ', '').replace('-', '_') if score else ''
                score_suffix = f"_{score_clean}" if score_clean else ''
                
                if league:
                    base_name = f"{kickoff_date}_{kickoff_time}_{league}_{home}_vs_{away}{score_suffix}"
                else:
                    base_name = f"{kickoff_date}_{kickoff_time}_{home}_vs_{away}{score_suffix}"
                
                filename = f"{base_name}_大小球明细.json"
                filepath = save_dir / filename
                
                # 🔥 构造完整的 match_info（便于后续读取和缓存检查）
                # 时间格式转换：0400 -> 04:00
                formatted_time = f"{kickoff_time[:2]}:{kickoff_time[2:4]}" if len(kickoff_time) >= 4 else kickoff_time
                full_kickoff = f"{kickoff_date} {formatted_time}"
                
                save_data = {
                    'match_info': {
                        'league': league,
                        'home': home,
                        'away': away,
                        'kickoff': full_kickoff,  # 🔥 完整的开赛时间
                        'kickoff_date': kickoff_date,
                        'kickoff_time': formatted_time,  # 🔥 格式化的时间 HH:MM
                        'date': kickoff_date,
                        'score': score
                    },
                    'ou_trade_detail': result,
                    'fetch_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                
                records = result.get('total_records', 0)
                task.add_log("INFO", f"    📊 大小球明细: {records}条" if records > 0 else "    📊 大小球明细已保存(无交易数据)")
        except Exception as e:
            task.add_log("WARNING", f"    ⚠️ 大小球明细失败: {str(e)[:100]}")
    
    def _save_task(self, task: CollectionTask):
        """保存任务到文件"""
        try:
            task_file = self._task_dir / f"{task.task_id}.json"
            
            # 准备保存的数据
            data = task.to_dict()
            data['processed_matches'] = task.progress.processed_matches
            
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
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
                    task = CollectionTask(
                        task_id=data['task_id'],
                        start_date=data['start_date'],
                        end_date=data['end_date'],
                        filter_by_handicap=data.get('filter_by_handicap', True),
                        skip_cached=data.get('skip_cached', True),
                        workers=data.get('workers', 3),
                        super_mode=data.get('super_mode', True),  # 🔥 恢复四合一模式
                    )
                    
                    # 恢复状态
                    task.status = CollectionStatus(data.get('status', 'pending'))
                    
                    # 恢复进度
                    progress_data = data.get('progress', {})
                    task.progress.total_days = progress_data.get('total_days', 0)
                    task.progress.total_matches = progress_data.get('total_matches', 0)
                    task.progress.success = progress_data.get('success', 0)
                    task.progress.failed = progress_data.get('failed', 0)
                    task.progress.skipped = progress_data.get('skipped', 0)
                    task.progress.processed_matches = data.get('processed_matches', {})
                    
                    # 恢复时间
                    if data.get('created_at'):
                        task.created_at = datetime.fromisoformat(data['created_at'])
                    if data.get('started_at'):
                        task.started_at = datetime.fromisoformat(data['started_at'])
                    
                    # 运行中的任务标记为暂停
                    if task.status == CollectionStatus.RUNNING:
                        task.status = CollectionStatus.PAUSED
                        task.add_log("WARNING", "服务重启，任务已暂停")
                    
                    self._tasks[task.task_id] = task
                    
                except Exception as e:
                    logger.warning(f"加载任务文件失败 {task_file}: {e}")
            
            logger.info(f"📂 加载了 {len(self._tasks)} 个历史采集任务")
            
        except Exception as e:
            logger.error(f"加载任务目录失败: {e}")


# 全局实例（延迟初始化）
_background_collector: Optional[BackgroundCollector] = None


def get_background_collector(
    bifaw_client=None,
    lottery500_client=None,
    detail_cache_manager=None,
    log_manager=None
) -> BackgroundCollector:
    """获取后台采集器实例"""
    global _background_collector
    
    if _background_collector is None:
        _background_collector = BackgroundCollector(
            bifaw_client=bifaw_client,
            lottery500_client=lottery500_client,
            detail_cache_manager=detail_cache_manager,
            log_manager=log_manager
        )
    elif bifaw_client or lottery500_client or detail_cache_manager or log_manager:
        # 更新依赖
        _background_collector.__init__(
            bifaw_client=bifaw_client,
            lottery500_client=lottery500_client,
            detail_cache_manager=detail_cache_manager,
            log_manager=log_manager
        )
    
    return _background_collector
