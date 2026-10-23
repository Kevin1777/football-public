"""
自动清理服务
定期清理超过指定天数的临时文件和调试文件
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class CleanupService:
    """自动清理服务"""
    
    # 清理配置：目录 -> (保留天数, 文件匹配模式)
    CLEANUP_CONFIG = {
        'debug_html': {
            'days': 3,
            'patterns': ['*.html', '*.png', '*.json'],
            'description': '调试快照'
        },
        'temp': {
            'days': 3,
            'patterns': ['*'],
            'description': '临时文件'
        },
        'logs': {
            'days': 7,
            'patterns': ['session_*.log'],
            'description': '会话日志'
        },
        'detail_cache': {
            'days': 7,
            'patterns': ['*.json'],
            'description': '详情缓存'
        },
        'backtest_results': {
            'days': 14,
            'patterns': ['*.json', '*.csv'],
            'description': '回测结果'
        },
    }
    
    # 根目录文件清理配置
    ROOT_FILE_PATTERNS = {
        'backtest_result_*.log': 7,       # 回测日志保留7天
        'backtest_详细结果_*.json': 7,     # 回测结果保留7天
        'batch_summary_*.json': 7,         # 批量摘要保留7天
        'batch_collect_async.log': 7,      # 异步采集日志保留7天
    }
    
    # 需要轮转的大日志文件（超过指定大小则截断）
    LOG_ROTATION_CONFIG = {
        'logs/app_full.log': 10 * 1024 * 1024,        # 10MB
        'logs/football_current.log': 10 * 1024 * 1024, # 10MB
        'logs/backtest_detail.log': 5 * 1024 * 1024,   # 5MB
    }
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or BASE_DIR
        self.stats = {
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': []
        }
    
    def cleanup_directory(self, dir_name: str, days: int, patterns: List[str]) -> Dict:
        """
        清理指定目录中超过指定天数的文件
        
        Args:
            dir_name: 目录名（相对于项目根目录）
            days: 保留天数
            patterns: 文件匹配模式列表
            
        Returns:
            清理统计
        """
        target_dir = self.base_dir / dir_name
        
        if not target_dir.exists():
            logger.warning(f"目录不存在: {target_dir}")
            return {'deleted': 0, 'bytes': 0}
        
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        deleted_bytes = 0
        
        for pattern in patterns:
            for file_path in target_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                    
                try:
                    # 检查文件修改时间
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        deleted_bytes += file_size
                except Exception as e:
                    self.stats['errors'].append(f"{file_path}: {e}")
                    logger.error(f"删除文件失败 {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"✅ {dir_name}/: 删除 {deleted_count} 个文件，释放 {self._format_size(deleted_bytes)}")
        
        return {'deleted': deleted_count, 'bytes': deleted_bytes}
    
    def cleanup_root_files(self) -> Dict:
        """清理根目录下的临时文件"""
        deleted_count = 0
        deleted_bytes = 0
        
        for pattern, days in self.ROOT_FILE_PATTERNS.items():
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for file_path in self.base_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                    
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        deleted_bytes += file_size
                        logger.info(f"🗑️ 删除: {file_path.name}")
                except Exception as e:
                    self.stats['errors'].append(f"{file_path}: {e}")
                    logger.error(f"删除文件失败 {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"✅ 根目录: 删除 {deleted_count} 个文件，释放 {self._format_size(deleted_bytes)}")
        
        return {'deleted': deleted_count, 'bytes': deleted_bytes}
    
    def run_cleanup(self, dry_run: bool = False) -> Dict:
        """
        执行全部清理任务
        
        Args:
            dry_run: 如果为 True，只统计不实际删除
            
        Returns:
            清理统计
        """
        logger.info("=" * 50)
        logger.info("🧹 开始自动清理任务")
        logger.info(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   模式: {'预览' if dry_run else '执行'}")
        logger.info("=" * 50)
        
        self.stats = {
            'files_deleted': 0,
            'bytes_freed': 0,
            'errors': [],
            'details': {}
        }
        
        # 清理配置目录
        for dir_name, config in self.CLEANUP_CONFIG.items():
            if dry_run:
                result = self._preview_cleanup(dir_name, config['days'], config['patterns'])
            else:
                result = self.cleanup_directory(dir_name, config['days'], config['patterns'])
            
            self.stats['files_deleted'] += result['deleted']
            self.stats['bytes_freed'] += result['bytes']
            self.stats['details'][dir_name] = result
        
        # 清理根目录文件
        if dry_run:
            result = self._preview_root_files()
        else:
            result = self.cleanup_root_files()
        
        self.stats['files_deleted'] += result['deleted']
        self.stats['bytes_freed'] += result['bytes']
        self.stats['details']['root_files'] = result
        
        # 轮转大日志文件
        if not dry_run:
            rotation_result = self.rotate_large_logs()
            self.stats['bytes_freed'] += rotation_result['bytes']
            self.stats['details']['log_rotation'] = rotation_result
        
        # 输出统计
        logger.info("=" * 50)
        logger.info(f"🧹 清理完成")
        logger.info(f"   删除文件: {self.stats['files_deleted']} 个")
        logger.info(f"   释放空间: {self._format_size(self.stats['bytes_freed'])}")
        if self.stats['errors']:
            logger.warning(f"   错误数: {len(self.stats['errors'])}")
        logger.info("=" * 50)
        
        return self.stats
    
    def _preview_cleanup(self, dir_name: str, days: int, patterns: List[str]) -> Dict:
        """预览要清理的文件（不实际删除）"""
        target_dir = self.base_dir / dir_name
        
        if not target_dir.exists():
            return {'deleted': 0, 'bytes': 0}
        
        cutoff_time = datetime.now() - timedelta(days=days)
        count = 0
        total_bytes = 0
        
        for pattern in patterns:
            for file_path in target_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        count += 1
                        total_bytes += file_path.stat().st_size
                except:
                    pass
        
        if count > 0:
            logger.info(f"📋 {dir_name}/: 将删除 {count} 个文件 ({self._format_size(total_bytes)})")
        
        return {'deleted': count, 'bytes': total_bytes}
    
    def _preview_root_files(self) -> Dict:
        """预览根目录要清理的文件"""
        count = 0
        total_bytes = 0
        
        for pattern, days in self.ROOT_FILE_PATTERNS.items():
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for file_path in self.base_dir.glob(pattern):
                if not file_path.is_file():
                    continue
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        count += 1
                        total_bytes += file_path.stat().st_size
                except:
                    pass
        
        if count > 0:
            logger.info(f"📋 根目录: 将删除 {count} 个文件 ({self._format_size(total_bytes)})")
        
        return {'deleted': count, 'bytes': total_bytes}
    
    def _format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    
    def rotate_large_logs(self) -> Dict:
        """轮转过大的日志文件（截断到指定大小）"""
        rotated_count = 0
        freed_bytes = 0
        
        for log_path, max_size in self.LOG_ROTATION_CONFIG.items():
            file_path = self.base_dir / log_path
            
            if not file_path.exists():
                continue
                
            try:
                current_size = file_path.stat().st_size
                if current_size > max_size:
                    # 保留最后 max_size 字节
                    with open(file_path, 'rb') as f:
                        f.seek(-max_size, 2)  # 从末尾往前 max_size 字节
                        # 找到下一个换行符，避免截断行
                        f.readline()
                        content = f.read()
                    
                    # 写回文件
                    with open(file_path, 'wb') as f:
                        f.write(b"[... old logs truncated ...]\n")
                        f.write(content)
                    
                    new_size = file_path.stat().st_size
                    freed = current_size - new_size
                    freed_bytes += freed
                    rotated_count += 1
                    logger.info(f"📜 轮转日志: {log_path} ({self._format_size(current_size)} -> {self._format_size(new_size)})")
            except Exception as e:
                self.stats['errors'].append(f"{file_path}: {e}")
                logger.error(f"轮转日志失败 {file_path}: {e}")
        
        if rotated_count > 0:
            logger.info(f"✅ 日志轮转: {rotated_count} 个文件，释放 {self._format_size(freed_bytes)}")
        
        return {'rotated': rotated_count, 'bytes': freed_bytes}
    
    def get_disk_usage(self) -> Dict:
        """获取各目录的磁盘使用情况"""
        usage = {}
        
        for dir_name in self.CLEANUP_CONFIG.keys():
            target_dir = self.base_dir / dir_name
            if target_dir.exists():
                total_size = 0
                file_count = 0
                for f in target_dir.rglob('*'):
                    if f.is_file():
                        total_size += f.stat().st_size
                        file_count += 1
                usage[dir_name] = {
                    'files': file_count,
                    'size': total_size,
                    'size_formatted': self._format_size(total_size)
                }
        
        # 添加大日志文件信息
        for log_path, max_size in self.LOG_ROTATION_CONFIG.items():
            file_path = self.base_dir / log_path
            if file_path.exists():
                size = file_path.stat().st_size
                usage[log_path] = {
                    'files': 1,
                    'size': size,
                    'size_formatted': self._format_size(size),
                    'max_size': self._format_size(max_size),
                    'needs_rotation': size > max_size
                }
        
        return usage


# 单例实例
cleanup_service = CleanupService()


def run_cleanup(dry_run: bool = False) -> Dict:
    """便捷函数：执行清理"""
    return cleanup_service.run_cleanup(dry_run=dry_run)


def preview_cleanup() -> Dict:
    """便捷函数：预览清理"""
    return cleanup_service.run_cleanup(dry_run=True)


def get_disk_usage() -> Dict:
    """便捷函数：获取磁盘使用情况"""
    return cleanup_service.get_disk_usage()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n📊 磁盘使用情况:")
    usage = get_disk_usage()
    for dir_name, info in usage.items():
        print(f"  {dir_name}/: {info['files']} 个文件, {info['size_formatted']}")
    
    print("\n📋 预览清理:")
    preview_cleanup()
    
    # 取消注释以下行执行实际清理
    # print("\n🧹 执行清理:")
    # run_cleanup()
