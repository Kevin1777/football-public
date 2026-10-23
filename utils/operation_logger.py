"""
操作日志管理器
- 记录所有操作日志到文件
- 每48小时自动轮转
- 保留最近7天的日志
"""
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
import gzip
import shutil


class OperationLogger:
    """操作日志管理器"""
    
    def __init__(self, log_dir: str = "logs", app_name: str = "football"):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录
            app_name: 应用名称
        """
        self.log_dir = Path(log_dir)
        self.app_name = app_name
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志文件路径
        self.current_log_file = self.log_dir / f"{app_name}_current.log"
        self.archive_dir = self.log_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
        
        # 配置参数
        self.rotation_hours = 48  # 每48小时轮转
        self.keep_days = 7  # 保留7天
        
    def setup_logger(self, logger: logging.Logger, level=logging.INFO):
        """
        为指定的logger配置文件输出
        
        Args:
            logger: 要配置的logger
            level: 日志级别
        """
        # 移除已存在的文件handler（避免重复）
        for handler in logger.handlers[:]:
            if isinstance(handler, (logging.FileHandler, TimedRotatingFileHandler)):
                logger.removeHandler(handler)
        
        # 创建文件handler（每48小时轮转）
        file_handler = TimedRotatingFileHandler(
            filename=str(self.current_log_file),
            when='H',  # 按小时轮转
            interval=self.rotation_hours,  # 每48小时
            backupCount=0,  # 不使用默认备份机制，我们自己管理
            encoding='utf-8',
            delay=False
        )
        
        # 自定义轮转命名
        file_handler.namer = self._get_rotation_filename
        file_handler.rotator = self._rotate_and_compress
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        
        # 添加到logger
        logger.addHandler(file_handler)
        
        # 清理旧日志
        self._cleanup_old_logs()
        
        return file_handler
    
    def _get_rotation_filename(self, default_name: str) -> str:
        """
        自定义轮转文件名
        
        Args:
            default_name: 默认文件名
            
        Returns:
            新的文件名
        """
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_file = self.archive_dir / f"{self.app_name}_{timestamp}.log"
        return str(archive_file)
    
    def _rotate_and_compress(self, source: str, dest: str):
        """
        轮转并压缩日志文件
        
        Args:
            source: 源文件
            dest: 目标文件
        """
        try:
            # 移动文件到archive目录
            if os.path.exists(source):
                shutil.move(source, dest)
                
                # 压缩文件
                compressed_file = f"{dest}.gz"
                with open(dest, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # 删除未压缩的文件
                os.remove(dest)
                
                print(f"✅ 日志已轮转并压缩: {compressed_file}")
        except Exception as e:
            print(f"❌ 日志轮转失败: {e}")
    
    def _cleanup_old_logs(self):
        """清理超过保留期的日志文件"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.keep_days)
            
            removed_count = 0
            for log_file in self.archive_dir.glob(f"{self.app_name}_*.log*"):
                # 从文件名提取时间戳
                try:
                    filename = log_file.stem
                    if filename.endswith('.log'):
                        filename = filename[:-4]
                    
                    # 提取时间戳部分 (YYYYMMDD_HHMMSS)
                    timestamp_str = filename.split('_')[-2] + '_' + filename.split('_')[-1]
                    file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    
                    if file_time < cutoff_time:
                        log_file.unlink()
                        removed_count += 1
                except (ValueError, IndexError):
                    # 如果文件名格式不正确，跳过
                    continue
            
            if removed_count > 0:
                print(f"🧹 清理了 {removed_count} 个过期日志文件（超过{self.keep_days}天）")
                
        except Exception as e:
            print(f"❌ 清理旧日志失败: {e}")
    
    def get_current_log_content(self, lines: int = 500) -> str:
        """
        获取当前日志文件的最后N行内容
        
        Args:
            lines: 要读取的行数
            
        Returns:
            日志内容
        """
        try:
            if not self.current_log_file.exists():
                return "日志文件不存在"
            
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"读取日志失败: {e}"
    
    def get_log_stats(self) -> dict:
        """
        获取日志统计信息
        
        Returns:
            统计信息字典
        """
        try:
            stats = {
                'current_log_size': 0,
                'current_log_lines': 0,
                'archive_count': 0,
                'total_archive_size': 0,
                'oldest_archive': None,
                'newest_archive': None
            }
            
            # 当前日志信息
            if self.current_log_file.exists():
                stats['current_log_size'] = self.current_log_file.stat().st_size
                with open(self.current_log_file, 'r', encoding='utf-8') as f:
                    stats['current_log_lines'] = sum(1 for _ in f)
            
            # 归档日志信息
            archive_files = list(self.archive_dir.glob(f"{self.app_name}_*.log*"))
            stats['archive_count'] = len(archive_files)
            
            if archive_files:
                stats['total_archive_size'] = sum(f.stat().st_size for f in archive_files)
                
                # 找出最老和最新的归档
                archive_times = []
                for log_file in archive_files:
                    try:
                        filename = log_file.stem
                        if filename.endswith('.log'):
                            filename = filename[:-4]
                        timestamp_str = filename.split('_')[-2] + '_' + filename.split('_')[-1]
                        file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        archive_times.append(file_time)
                    except (ValueError, IndexError):
                        continue
                
                if archive_times:
                    stats['oldest_archive'] = min(archive_times).strftime('%Y-%m-%d %H:%M:%S')
                    stats['newest_archive'] = max(archive_times).strftime('%Y-%m-%d %H:%M:%S')
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def search_logs(self, keyword: str, max_results: int = 100) -> list:
        """
        在当前日志和归档中搜索关键字
        
        Args:
            keyword: 搜索关键字
            max_results: 最大结果数
            
        Returns:
            匹配的日志行列表
        """
        results = []
        
        try:
            # 搜索当前日志
            if self.current_log_file.exists():
                with open(self.current_log_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if keyword.lower() in line.lower():
                            results.append({
                                'file': 'current',
                                'line_num': line_num,
                                'content': line.strip()
                            })
                            if len(results) >= max_results:
                                return results
            
            # 搜索归档日志（从新到旧）
            archive_files = sorted(
                self.archive_dir.glob(f"{self.app_name}_*.log*"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            for archive_file in archive_files:
                if len(results) >= max_results:
                    break
                
                try:
                    # 如果是压缩文件
                    if archive_file.suffix == '.gz':
                        with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                            for line_num, line in enumerate(f, 1):
                                if keyword.lower() in line.lower():
                                    results.append({
                                        'file': archive_file.name,
                                        'line_num': line_num,
                                        'content': line.strip()
                                    })
                                    if len(results) >= max_results:
                                        break
                    else:
                        with open(archive_file, 'r', encoding='utf-8') as f:
                            for line_num, line in enumerate(f, 1):
                                if keyword.lower() in line.lower():
                                    results.append({
                                        'file': archive_file.name,
                                        'line_num': line_num,
                                        'content': line.strip()
                                    })
                                    if len(results) >= max_results:
                                        break
                except Exception as e:
                    continue
            
            return results
            
        except Exception as e:
            return [{'error': str(e)}]
    
    def force_rotate(self):
        """强制轮转当前日志"""
        try:
            if self.current_log_file.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_file = self.archive_dir / f"{self.app_name}_{timestamp}.log"
                
                # 复制当前日志到归档
                shutil.copy2(self.current_log_file, archive_file)
                
                # 压缩
                compressed_file = f"{archive_file}.gz"
                with open(archive_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.remove(archive_file)
                
                # 清空当前日志
                with open(self.current_log_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== 日志已于 {datetime.now()} 手动轮转 ===\n")
                
                print(f"✅ 日志已手动轮转: {compressed_file}")
                return True
        except Exception as e:
            print(f"❌ 手动轮转失败: {e}")
            return False


# 创建全局实例
_operation_logger = None

def get_operation_logger(log_dir: str = "logs", app_name: str = "football") -> OperationLogger:
    """
    获取全局操作日志管理器实例
    
    Args:
        log_dir: 日志目录
        app_name: 应用名称
        
    Returns:
        OperationLogger实例
    """
    global _operation_logger
    if _operation_logger is None:
        _operation_logger = OperationLogger(log_dir=log_dir, app_name=app_name)
    return _operation_logger
