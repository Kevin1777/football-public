"""
采集进度管理器

功能：
1. 记录批量采集的进度，支持断点续传
2. 记录未采集成功的比赛列表
3. 提供进度恢复功能
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)


class ProgressManager:
    """采集进度管理器"""
    
    def __init__(self, progress_dir: str = "progress"):
        """
        初始化进度管理器
        
        Args:
            progress_dir: 进度文件保存目录
        """
        self.progress_dir = Path(__file__).parent.parent / progress_dir
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"进度管理目录: {self.progress_dir}")
    
    def _get_session_file(self, session_id: str) -> Path:
        """获取会话进度文件路径"""
        return self.progress_dir / f"session_{session_id}.json"
    
    def _get_failed_log_file(self, session_id: str) -> Path:
        """获取未采集成功比赛的日志文件路径"""
        return self.progress_dir / f"failed_{session_id}.json"
    
    def _safe_load_json(self, file_path: Path) -> Optional[Dict]:
        """
        安全加载 JSON 文件，处理损坏的文件
        
        如果文件包含多个 JSON 对象（Extra data 错误），
        尝试只读取第一个有效的 JSON 对象并修复文件
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 先尝试正常解析
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                if 'Extra data' in str(e):
                    # 文件包含多个 JSON 对象，尝试修复
                    logger.warning(f"⚠️ 检测到损坏的 JSON 文件: {file_path.name}，尝试修复...")
                    
                    # 方法1：尝试找到第一个完整的 JSON 对象
                    # JSON 对象以 { 开始，找到匹配的 }
                    brace_count = 0
                    end_pos = 0
                    in_string = False
                    escape = False
                    
                    for i, char in enumerate(content):
                        if escape:
                            escape = False
                            continue
                        if char == '\\':
                            escape = True
                            continue
                        if char == '"' and not escape:
                            in_string = not in_string
                            continue
                        if in_string:
                            continue
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    
                    if end_pos > 0:
                        first_json = content[:end_pos]
                        try:
                            data = json.loads(first_json)
                            
                            # 修复文件：只保留第一个有效的 JSON
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            logger.info(f"✅ 已修复损坏文件: {file_path.name}")
                            
                            return data
                        except:
                            pass
                    
                    logger.error(f"❌ 无法修复文件: {file_path.name}")
                    return None
                else:
                    logger.error(f"❌ JSON 解析错误 {file_path.name}: {e}")
                    return None
        except Exception as e:
            logger.error(f"❌ 读取文件失败 {file_path.name}: {e}")
            return None
    
    def create_session(self, start_date: str, end_date: str, total_matches: int, 
                      filter_by_handicap: bool = True, skip_cached: bool = True) -> str:
        """
        创建新的采集会话
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            total_matches: 总比赛数
            filter_by_handicap: 是否过滤盘口
            skip_cached: 是否跳过已缓存
            
        Returns:
            session_id: 会话ID
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        session_data = {
            "session_id": session_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_matches": total_matches,
            "filter_by_handicap": filter_by_handicap,
            "skip_cached": skip_cached,
            "created_at": datetime.now().isoformat(),
            "status": "running",  # running, paused, completed, failed
            "progress": {
                "processed": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "current_date": start_date,
                "current_match_index": 0,
            },
            "processed_matches": [],  # 已处理的比赛（用于去重）
            "failed_matches": [],     # 失败的比赛列表
        }
        
        session_file = self._get_session_file(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 创建采集会话: {session_id}")
        logger.info(f"   日期范围: {start_date} ~ {end_date}")
        logger.info(f"   总比赛数: {total_matches}")
        
        return session_id
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """
        加载会话进度
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据字典，如果不存在则返回None
        """
        session_file = self._get_session_file(session_id)
        
        if not session_file.exists():
            logger.warning(f"会话不存在: {session_id}")
            return None
        
        # 使用安全加载，自动修复损坏的文件
        session_data = self._safe_load_json(session_file)
        if session_data is None:
            return None
        
        logger.info(f"✅ 加载会话: {session_id}")
        logger.info(f"   状态: {session_data.get('status', 'unknown')}")
        logger.info(f"   进度: {session_data.get('progress', {}).get('processed', 0)}/{session_data.get('total_matches', 0)}")
        
        return session_data
    
    def update_progress(self, session_id: str, 
                       match_info: Dict,
                       status: str,  # 'success', 'failed', 'skipped'
                       current_date: str,
                       error_reason: str = None):
        """
        更新采集进度
        
        Args:
            session_id: 会话ID
            match_info: 比赛信息
            status: 状态 (success/failed/skipped)
            current_date: 当前处理日期
            error_reason: 失败原因（仅在status=failed时提供）
        """
        session_data = self.load_session(session_id)
        if not session_data:
            return
        
        # 生成比赛唯一标识
        match_key = self._generate_match_key(match_info)
        
        # 避免重复记录
        if match_key in session_data['processed_matches']:
            return
        
        # 更新进度
        session_data['progress']['processed'] += 1
        session_data['progress']['current_date'] = current_date
        session_data['processed_matches'].append(match_key)
        
        if status == 'success':
            session_data['progress']['success'] += 1
        elif status == 'failed':
            session_data['progress']['failed'] += 1
            # 记录失败的比赛
            failed_match = {
                'match_key': match_key,
                'match_label': match_info.get('label', ''),
                'date': current_date,
                'home': match_info.get('home', ''),
                'away': match_info.get('away', ''),
                'kickoff': match_info.get('kickoff', ''),
                'error_reason': error_reason or '未知错误',
                'failed_at': datetime.now().isoformat(),
            }
            session_data['failed_matches'].append(failed_match)
        elif status == 'skipped':
            session_data['progress']['skipped'] += 1
        
        # 保存更新
        session_file = self._get_session_file(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    
    def mark_completed(self, session_id: str):
        """标记会话完成"""
        session_data = self.load_session(session_id)
        if not session_data:
            return
        
        session_data['status'] = 'completed'
        session_data['completed_at'] = datetime.now().isoformat()
        
        session_file = self._get_session_file(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        # 导出失败日志
        # 导出失败日志
        if session_data.get('failed_matches'):
            self._export_failed_log(session_id, session_data['failed_matches'])
        
        logger.info(f"✅ 会话完成: {session_id}")
        if session_data.get('progress'):
            logger.info(f"   成功: {session_data['progress'].get('success', 0)}")
            logger.info(f"   失败: {session_data['progress'].get('failed', 0)}")
            logger.info(f"   跳过: {session_data['progress'].get('skipped', 0)}")
    
    def mark_paused(self, session_id: str):
        """标记会话暂停"""
        session_data = self.load_session(session_id)
        if not session_data:
            return
        
        session_data['status'] = 'paused'
        session_data['paused_at'] = datetime.now().isoformat()
        
        session_file = self._get_session_file(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"⏸️  会话暂停: {session_id}")
    
    def is_match_processed(self, session_id: str, match_info: Dict) -> bool:
        """
        检查比赛是否已处理
        
        Args:
            session_id: 会话ID
            match_info: 比赛信息
            
        Returns:
            True=已处理, False=未处理
        """
        session_data = self.load_session(session_id)
        if not session_data:
            return False
        
        match_key = self._generate_match_key(match_info)
        return match_key in session_data['processed_matches']
    
    def get_failed_matches(self, session_id: str) -> List[Dict]:
        """
        获取失败的比赛列表
        
        Args:
            session_id: 会话ID
            
        Returns:
            失败比赛列表
        """
        session_data = self.load_session(session_id)
        if not session_data:
            return []
        
        return session_data['failed_matches']
    
    def _export_failed_log(self, session_id: str, failed_matches: List[Dict]):
        """导出失败比赛日志到独立文件"""
        failed_log_file = self._get_failed_log_file(session_id)
        
        log_data = {
            "session_id": session_id,
            "exported_at": datetime.now().isoformat(),
            "total_failed": len(failed_matches),
            "failed_matches": failed_matches,
        }
        
        with open(failed_log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📋 已导出失败日志: {failed_log_file.name}")
        logger.info(f"   失败比赛数: {len(failed_matches)}")
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        获取会话信息（别名，调用load_session）
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据字典
        """
        return self.load_session(session_id)
    
    def update_session_status(self, session_id: str, status: str):
        """
        更新会话状态
        
        Args:
            session_id: 会话ID
            status: 新状态 (running/paused/completed/failed/recovering)
        """
        session_data = self.load_session(session_id)
        if not session_data:
            logger.error(f"会话 {session_id} 不存在")
            return
        
        session_data['status'] = status
        session_data['last_updated'] = datetime.now().isoformat()
        
        session_file = self._get_session_file(session_id)
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            logger.info(f"会话 {session_id} 状态已更新为: {status}")
        except Exception as e:
            logger.error(f"更新会话状态失败: {e}")
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """
        列出所有会话
        
        Args:
            limit: 最多返回数量
            
        Returns:
            会话列表
        """
        sessions = []
        
        session_files = list(self.progress_dir.glob("session_*.json"))
        session_files = sorted(session_files, reverse=True)
        logger.info(f"📂 扫描到 {len(session_files)} 个会话文件")
        
        for session_file in session_files:
            try:
                session_data = self._safe_load_json(session_file)
                if session_data is None:
                    continue
                
                # 🔥 使用 .get() 防止 KeyError
                sessions.append({
                    'session_id': session_data.get('session_id', session_file.stem.replace('session_', '')),
                    'start_date': session_data.get('start_date', 'N/A'),
                    'end_date': session_data.get('end_date', 'N/A'),
                    'total_matches': session_data.get('total_matches', 0),
                    'status': session_data.get('status', 'unknown'),
                    'progress': session_data.get('progress', {}),
                    'created_at': session_data.get('created_at', 'N/A'),
                })
                
                if len(sessions) >= limit:
                    break
            except Exception as e:
                # 🔥 记录错误而不是静默忽略
                logger.warning(f"读取会话文件失败 {session_file.name}: {e}")
                continue
        
        logger.info(f"📋 返回 {len(sessions)} 个会话")
        return sessions
    
    def _generate_match_key(self, match_info: Dict) -> str:
        """
        生成比赛唯一标识
        
        Args:
            match_info: 比赛信息
            
        Returns:
            比赛唯一标识字符串
        """
        home = match_info.get('home', match_info.get('home_team', ''))
        away = match_info.get('away', match_info.get('away_team', ''))
        kickoff = match_info.get('kickoff', match_info.get('match_time', ''))
        
        # 清理时间格式
        if ' ' in kickoff:
            date_part, time_part = kickoff.split(' ', 1)
            time_part = time_part.replace(':', '')[:4]  # HHMM
        else:
            date_part = kickoff
            time_part = ''
        
        return f"{date_part}_{home}_{away}_{time_part}"


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    manager = ProgressManager()
    
    # 创建会话
    session_id = manager.create_session(
        start_date="2025-11-01",
        end_date="2025-11-15",
        total_matches=100
    )
    
    # 模拟更新进度
    test_match = {
        'home': '测试主队',
        'away': '测试客队',
        'kickoff': '2025-11-01 20:00',
        'label': '测试比赛'
    }
    
    manager.update_progress(session_id, test_match, 'success', '2025-11-01')
    manager.update_progress(session_id, test_match, 'failed', '2025-11-01', error_reason='网络超时')
    
    # 列出会话
    sessions = manager.list_sessions()
    print(f"会话数量: {len(sessions)}")
