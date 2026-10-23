"""
系统健康检查器
定期检查系统各项指标，发现潜在问题
"""
import logging
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class HealthChecker:
    """系统健康检查器"""
    
    def __init__(self, data_dir: Path, log_dir: Path):
        """
        初始化健康检查器
        
        Args:
            data_dir: 数据目录
            log_dir: 日志目录
        """
        self.data_dir = data_dir
        self.log_dir = log_dir
        self.issues: List[Dict] = []
        
    def check_disk_space(self, min_free_gb: float = 5.0) -> bool:
        """
        检查磁盘空间
        
        Args:
            min_free_gb: 最小剩余空间（GB）
            
        Returns:
            是否正常
        """
        try:
            total, used, free = shutil.disk_usage(str(self.data_dir))
            
            free_gb = free / (1024**3)
            usage_percent = (used / total) * 100
            
            logger.info(f"💾 磁盘使用率: {usage_percent:.1f}% (剩余 {free_gb:.2f} GB)")
            
            if free_gb < min_free_gb:
                self.issues.append({
                    'level': 'warning',
                    'component': 'disk',
                    'message': f'磁盘空间不足，仅剩 {free_gb:.2f} GB'
                })
                return False
            
            if usage_percent > 90:
                self.issues.append({
                    'level': 'warning',
                    'component': 'disk',
                    'message': f'磁盘使用率过高: {usage_percent:.1f}%'
                })
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查磁盘空间失败: {e}")
            return False
    
    def check_log_size(self, max_size_mb: float = 100.0) -> bool:
        """
        检查日志文件大小
        
        Args:
            max_size_mb: 最大日志大小（MB）
            
        Returns:
            是否正常
        """
        try:
            current_log = self.log_dir / "football_current.log"
            
            if current_log.exists():
                size_mb = current_log.stat().st_size / (1024**2)
                logger.info(f"📝 当前日志大小: {size_mb:.2f} MB")
                
                if size_mb > max_size_mb:
                    self.issues.append({
                        'level': 'warning',
                        'component': 'log',
                        'message': f'日志文件过大: {size_mb:.2f} MB，建议手动轮转'
                    })
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查日志大小失败: {e}")
            return False
    
    def check_recent_data(self, max_age_hours: int = 24) -> bool:
        """
        检查最近是否有数据更新
        
        Args:
            max_age_hours: 最大数据年龄（小时）
            
        Returns:
            是否正常
        """
        try:
            today = datetime.now()
            date_path = self.data_dir / today.strftime('%Y/%m/%d')
            
            if not date_path.exists():
                # 今天可能还没有数据，尝试检查昨天的数据
                yesterday = today - timedelta(days=1)
                yesterday_path = self.data_dir / yesterday.strftime('%Y/%m/%d')
                
                if not yesterday_path.exists():
                    self.issues.append({
                        'level': 'error',
                        'component': 'data',
                        'message': f'今日数据目录不存在: {date_path.name}（昨日也无数据）'
                    })
                    return False
                else:
                    # 今天没有但昨天有，这是正常的
                    logger.info(f"📊 今日数据暂无，昨日数据存在: {yesterday_path.name}")
                    return True
            
            # 检查标盘数据文件
            biaopan_file = date_path / "标盘指数_latest.json"
            
            if not biaopan_file.exists():
                self.issues.append({
                    'level': 'error',
                    'component': 'data',
                    'message': '今日标盘数据不存在'
                })
                return False
            
            # 检查文件更新时间
            mtime = datetime.fromtimestamp(biaopan_file.stat().st_mtime)
            age_hours = (today - mtime).total_seconds() / 3600
            
            logger.info(f"📊 标盘数据更新: {age_hours:.1f} 小时前")
            
            if age_hours > max_age_hours:
                self.issues.append({
                    'level': 'warning',
                    'component': 'data',
                    'message': f'标盘数据已过期 {age_hours:.1f} 小时'
                })
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查数据更新失败: {e}")
            return False
    
    def check_scheduler_health(self, scheduler) -> bool:
        """
        检查调度器健康状态
        
        Args:
            scheduler: APScheduler实例
            
        Returns:
            是否正常
        """
        try:
            if not scheduler.running:
                self.issues.append({
                    'level': 'error',
                    'component': 'scheduler',
                    'message': '调度器未运行'
                })
                return False
            
            # 检查关键任务
            # 🔥 scan_and_schedule_matches 已暂停，改用 refresh_match_schedules
            critical_jobs = [
                'auto_collect_today',
                'refresh_match_schedules',
                'auto_keep_login'
            ]
            
            jobs = scheduler.get_jobs()
            job_ids = [job.id for job in jobs]
            
            missing_jobs = [job_id for job_id in critical_jobs if job_id not in job_ids]
            
            if missing_jobs:
                self.issues.append({
                    'level': 'error',
                    'component': 'scheduler',
                    'message': f'缺失关键任务: {", ".join(missing_jobs)}'
                })
                return False
            
            logger.info(f"⏰ 调度器正常，共 {len(jobs)} 个任务")
            return True
            
        except Exception as e:
            logger.error(f"检查调度器失败: {e}")
            return False
    
    def check_push_system(self, auto_push_system) -> bool:
        """
        检查推送系统健康状态
        
        Args:
            auto_push_system: AutoRecommendPushSystem实例
            
        Returns:
            是否正常
        """
        try:
            if auto_push_system is None:
                self.issues.append({
                    'level': 'error',
                    'component': 'push',
                    'message': '推送系统未初始化'
                })
                return False
            
            # 检查推送配置
            if not auto_push_system.use_wecom and not auto_push_system.use_telegram:
                self.issues.append({
                    'level': 'warning',
                    'component': 'push',
                    'message': '未配置任何推送渠道'
                })
                return False
            
            logger.info(f"📢 推送系统正常 (企微: {auto_push_system.use_wecom}, TG: {auto_push_system.use_telegram})")
            return True
            
        except Exception as e:
            logger.error(f"检查推送系统失败: {e}")
            return False
    
    def run_full_check(self, scheduler=None, auto_push_system=None) -> Dict:
        """
        运行完整的健康检查
        
        Args:
            scheduler: APScheduler实例
            auto_push_system: AutoRecommendPushSystem实例
            
        Returns:
            检查结果统计
        """
        logger.info("=" * 60)
        logger.info("🏥 开始系统健康检查")
        logger.info("=" * 60)
        
        self.issues = []
        
        # 执行各项检查
        checks = {
            'disk_space': self.check_disk_space(),
            'log_size': self.check_log_size(),
            'recent_data': self.check_recent_data(),
        }
        
        if scheduler:
            checks['scheduler'] = self.check_scheduler_health(scheduler)
        
        if auto_push_system:
            checks['push_system'] = self.check_push_system(auto_push_system)
        
        # 统计结果
        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        
        logger.info("=" * 60)
        logger.info(f"✅ 检查完成: {passed_checks}/{total_checks} 项通过")
        
        if self.issues:
            logger.warning(f"⚠️  发现 {len(self.issues)} 个问题:")
            for issue in self.issues:
                level_icon = "⚠️" if issue['level'] == 'warning' else "❌"
                logger.warning(f"  {level_icon} [{issue['component']}] {issue['message']}")
        else:
            logger.info("🎉 系统运行正常，无异常")
        
        logger.info("=" * 60)
        
        return {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'issues': self.issues,
            'all_passed': len(self.issues) == 0
        }
