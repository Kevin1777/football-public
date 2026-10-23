"""
动态推送调度管理器
每天自动扫描比赛，为每场比赛创建精确的推送任务
🔥 优化：赛前5分钟并行采集+即时推送，确保数据新鲜度
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# 🔥 并行采集线程池（最多同时采集3场比赛）
COLLECT_THREAD_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="collect_")


class MatchPushScheduleManager:
    """比赛推送调度管理器"""
    
    def __init__(self, scheduler: BackgroundScheduler, auto_push_system, data_dir: Path):
        """
        初始化调度管理器
        
        Args:
            scheduler: APScheduler调度器实例
            auto_push_system: 自动推送系统实例
            data_dir: 数据目录路径
        """
        self.scheduler = scheduler
        self.auto_push_system = auto_push_system
        self.data_dir = data_dir
        self.scheduled_tasks: Dict[str, dict] = {}  # {match_id: task_info}
        
    def scan_and_schedule_today_matches(self, scan_date: Optional[datetime] = None):
        """
        扫描今日和明日的所有比赛，为每场比赛创建推送任务
        
        Args:
            scan_date: 扫描日期，默认为今天
        """
        try:
            target_date = scan_date if scan_date else datetime.now()
            
            logger.info("=" * 60)
            logger.info(f"📅 开始扫描并调度比赛推送任务")
            logger.info("=" * 60)
            
            # 扫描今天和明天的数据
            dates_to_scan = [
                target_date,
                target_date + timedelta(days=1)
            ]
            
            all_matches = []
            
            for scan_dt in dates_to_scan:
                date_str = scan_dt.strftime('%Y/%m/%d')
                year, month, day = date_str.split('/')
                biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                
                if biaopan_file.exists():
                    try:
                        with open(biaopan_file, 'r', encoding='utf-8') as f:
                            biaopan_data = json.load(f)
                        matches = biaopan_data.get('matches', [])
                        all_matches.extend(matches)
                        logger.info(f"📂 从 {date_str} 加载 {len(matches)} 场比赛")
                    except Exception as e:
                        logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
                else:
                    logger.info(f"📂 {date_str} 暂无标盘数据文件")
            
            if not all_matches:
                logger.warning("⚠️ 没有找到任何比赛数据")
                return
            
            matches = all_matches
            logger.info(f"📊 找到 {len(matches)} 场比赛")
            
            scheduled_count = 0
            skipped_count = 0
            
            for match in matches:
                kickoff_str = match.get('kickoff', '')
                match_time = self._parse_match_time(kickoff_str)
                
                if not match_time:
                    logger.warning(f"⚠️ 无法解析比赛时间: {kickoff_str}")
                    continue
                
                # 检查比赛是否已经开始
                now = datetime.now()
                if match_time <= now:
                    logger.debug(f"⏭️ 比赛已开始，跳过: {match.get('home')} vs {match.get('away')} ({kickoff_str})")
                    skipped_count += 1
                    continue
                
                # 为比赛创建推送任务
                if self._schedule_match_push(match, match_time):
                    scheduled_count += 1
                else:
                    skipped_count += 1
            
            # 🔥 智能调度：对同时开始的比赛进行分组，创建批量任务
            self._schedule_batch_tasks()
            
            logger.info("=" * 60)
            logger.info(f"✅ 调度完成: 成功 {scheduled_count} 场 | 跳过 {skipped_count} 场")
            logger.info(f"📋 当前待推送任务: {len(self.scheduled_tasks)} 场")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 扫描并调度比赛失败: {e}", exc_info=True)
    
    def _schedule_batch_tasks(self):
        """
        🔥 智能批量调度：对同一时间开始的比赛进行分组
        使用线程池并行采集，确保所有比赛都能及时完成
        """
        # 按推送时间分组
        push_time_groups = {}
        for match_id, task_info in self.scheduled_tasks.items():
            push_time = task_info['push_time']
            push_time_key = push_time.strftime('%Y-%m-%d %H:%M')
            if push_time_key not in push_time_groups:
                push_time_groups[push_time_key] = []
            push_time_groups[push_time_key].append(match_id)
        
        # 统计同时开始的比赛
        for push_time_key, match_ids in push_time_groups.items():
            if len(match_ids) > 1:
                logger.info(f"📊 {push_time_key} 有 {len(match_ids)} 场比赛同时推送（将并行采集）")
    
    def _schedule_match_push(self, match: dict, match_time: datetime) -> bool:
        """
        为单场比赛创建推送任务
        
        Args:
            match: 比赛数据
            match_time: 比赛开始时间
            
        Returns:
            是否成功创建任务
        """
        try:
            home_team = match.get('home', '')
            away_team = match.get('away', '')
            league = match.get('league', '')
            match_id = match.get('match_id', f"{home_team}_{away_team}_{match_time.strftime('%Y%m%d%H%M')}")
            
            # 检查是否已经调度过
            if match_id in self.scheduled_tasks:
                logger.debug(f"⏭️ 任务已存在，跳过: {home_team} vs {away_team}")
                return False
            
            # 🔥 优化：只在赛前5分钟触发，采集+推送一体化执行
            push_time = match_time - timedelta(minutes=5)
            
            now = datetime.now()
            
            # 检查推送时间是否已经过了
            if push_time <= now:
                logger.debug(f"⏭️ 推送时间已过，跳过: {home_team} vs {away_team} (推送时间 {push_time.strftime('%H:%M')})")
                return False
            
            # 🔥 创建采集+推送任务（赛前5分钟，先采集最新数据再推送）
            job_id = f"pre_match_{match_id}"
            
            # 使用APScheduler的date trigger（一次性任务）
            self.scheduler.add_job(
                func=self._execute_collect_and_push,
                trigger='date',
                run_date=push_time,
                args=[match, match_time],
                id=job_id,
                name=f"赛前推送: {home_team} vs {away_team}",
                replace_existing=True
            )
            
            # 记录任务信息
            self.scheduled_tasks[match_id] = {
                'job_id': job_id,
                'home_team': home_team,
                'away_team': away_team,
                'league': league,
                'match_time': match_time,
                'push_time': push_time,
                'status': 'scheduled'
            }
            
            logger.info(f"✅ 已调度: {home_team} vs {away_team}")
            logger.info(f"   比赛时间: {match_time.strftime('%Y-%m-%d %H:%M')}")
            logger.info(f"   采集推送: {push_time.strftime('%Y-%m-%d %H:%M')} (赛前5分钟)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建推送任务失败: {e}", exc_info=True)
            return False
    
    def _execute_collect_and_push(self, match: dict, match_time: datetime):
        """
        🔥 赛前5分钟：采集最新数据 + 即时推送（一体化执行）
        确保推荐使用的是最新几分钟内的数据
        
        Args:
            match: 比赛数据
            match_time: 比赛开始时间
        """
        try:
            home_team = match.get('home', '')
            away_team = match.get('away', '')
            league = match.get('league', '未知联赛')
            match_id = match.get('match_id', f"{home_team}_{away_team}_{match_time.strftime('%Y%m%d%H%M')}")
            
            logger.info("=" * 60)
            logger.info(f"🔥 赛前5分钟采集推送: {home_team} vs {away_team}")
            logger.info(f"   联赛: {league} | 比赛时间: {match_time.strftime('%H:%M')}")
            logger.info("=" * 60)
            
            # 构造比赛信息
            match_info = {
                'match_time': match_time,
                'league': league,
                'home_team': home_team,
                'away_team': away_team,
                'match_data': match
            }
            
            # 🔥 步骤1: 采集最新数据（使用线程池，确保数据新鲜）
            logger.info(f"📥 步骤1: 采集最新交易明细...")
            
            # 提交采集任务到线程池
            future = COLLECT_THREAD_POOL.submit(
                self.auto_push_system._auto_collect_match, 
                match_info, 
                match
            )
            try:
                # 等待采集完成（最多60秒）
                match_file = future.result(timeout=60)
            except Exception as e:
                logger.warning(f"采集超时或失败: {e}")
                match_file = None
            
            if not match_file:
                # 尝试使用已有的缓存数据
                match_file = self.auto_push_system._find_match_file(home_team, away_team, match_time)
                if match_file:
                    logger.warning(f"⚠️ 采集失败，使用缓存数据: {match_file}")
                else:
                    logger.error(f"❌ 无数据可用，跳过推送: {home_team} vs {away_team}")
                    return
            else:
                logger.info(f"✅ 采集成功，数据已更新")
            
            # 🔥 步骤2: 使用引擎管理器进行推荐分析
            # 🔥 暂停赛前推荐报告功能
            # logger.info(f"🎯 步骤2: 推荐分析...")
            # std_result = self.auto_push_system.engine_manager.recommend(str(match_file))
            
            # 🔥 步骤3: 发送推送
            # 🔥 暂停赛前推荐报告功能
            # logger.info(f"📤 步骤3: 发送推送...")
            
            # 使用标准化结果格式发送推送
            # analysis_result = std_result.to_push_format()
            
            # if std_result.meltdown:
            #     logger.warning(f"推荐熔断: {std_result.meltdown_reason}")
            
            # self.auto_push_system._send_pre_match_recommendation(match_info, analysis_result, minutes_before=5)
            
            # 记录推送历史
            extended_match_info = {
                'league': league,
                'home_team': home_team,
                'away_team': away_team,
                'datetime': match_time.strftime('%Y-%m-%d %H:%M')
            }
            match_id_hash = self.auto_push_system.get_match_id(extended_match_info)
            self.auto_push_system.pre_match_pushed_matches[match_id_hash] = datetime.now().timestamp()
            self.auto_push_system._save_pre_match_history()
            
            # 更新任务状态
            if match_id in self.scheduled_tasks:
                self.scheduled_tasks[match_id]['status'] = 'completed'
            
            logger.info(f"✅ 采集推送完成: {home_team} vs {away_team}")
            
        except Exception as e:
            logger.error(f"❌ 采集推送失败: {e}", exc_info=True)

    def _execute_match_collect(self, match: dict, match_time: datetime):
        """
        执行比赛数据采集（已弃用，保留兼容）
        
        Args:
            match: 比赛数据
            match_time: 比赛开始时间
        """
        try:
            home_team = match.get('home', '')
            away_team = match.get('away', '')
            
            logger.info("=" * 60)
            logger.info(f"📥 执行赛前采集: {home_team} vs {away_team}")
            logger.info(f"   比赛时间: {match_time.strftime('%H:%M')}")
            logger.info("=" * 60)
            
            # 构造比赛信息
            match_info = {
                'match_time': match_time,
                'league': match.get('league', '未知联赛'),
                'home_team': home_team,
                'away_team': away_team,
                'match_data': match
            }
            
            # 检查是否已有数据
            existing_file = self.auto_push_system._find_match_file(home_team, away_team, match_time)
            if existing_file:
                logger.info(f"✅ 已有数据文件，跳过采集: {existing_file}")
                return
            
            # 调用自动采集
            result = self.auto_push_system._auto_collect_match(match_info, match)
            
            if result:
                logger.info(f"✅ 采集成功: {home_team} vs {away_team}")
            else:
                logger.warning(f"⚠️ 采集失败: {home_team} vs {away_team}")
                
        except Exception as e:
            logger.error(f"❌ 执行采集失败: {e}", exc_info=True)

    def _execute_match_push(self, match: dict, match_time: datetime):
        """
        执行比赛推送（赛前5分钟，由定时任务调用）
        
        Args:
            match: 比赛数据
            match_time: 比赛开始时间
        """
        try:
            home_team = match.get('home', '')
            away_team = match.get('away', '')
            match_id = match.get('match_id', f"{home_team}_{away_team}_{match_time.strftime('%Y%m%d%H%M')}")
            
            logger.info("=" * 60)
            logger.info(f"🔔 执行赛前推送: {home_team} vs {away_team}")
            logger.info(f"   比赛时间: {match_time.strftime('%H:%M')}")
            logger.info("=" * 60)
            
            # 构造比赛信息
            match_info = {
                'match_time': match_time,
                'league': match.get('league', '未知联赛'),
                'home_team': home_team,
                'away_team': away_team,
                'match_data': match
            }
            
            # 尝试加载完整的比赛数据文件
            match_file = self.auto_push_system._find_match_file(home_team, away_team, match_time)
            
            if match_file:
                match_data = self.auto_push_system.load_match_data(match_file)
                trade_data = self.auto_push_system.load_trade_data(match_file)
            else:
                # 如果没有找到文件，使用标盘数据构造基础信息
                match_data = {
                    'match_info': {
                        'league': match_info['league'],
                        'home_team': home_team,
                        'away_team': away_team,
                        'datetime': match_time.strftime('%Y-%m-%d %H:%M')
                    }
                }
                trade_data = None
            
            # 确保盘口数据
            match_data = self.auto_push_system._ensure_handicap_data(match_data)
            
            # 分析比赛
            result = self.auto_push_system.engine.analyze_match(match_data, trade_data)
            
            # 发送推送
            self.auto_push_system._send_pre_match_recommendation(match_info, result, minutes_before=5)
            
            # 更新任务状态
            if match_id in self.scheduled_tasks:
                self.scheduled_tasks[match_id]['status'] = 'completed'
                self.scheduled_tasks[match_id]['push_time_actual'] = datetime.now()
            
            # 记录到历史（避免重复推送）
            extended_match_info = {
                'league': match_info['league'],
                'home_team': home_team,
                'away_team': away_team,
                'datetime': match_time.strftime('%Y-%m-%d %H:%M')
            }
            match_id_hash = self.auto_push_system.get_match_id(extended_match_info)
            self.auto_push_system.pre_match_pushed_matches[match_id_hash] = datetime.now().timestamp()
            self.auto_push_system._save_pre_match_history()
            
            logger.info(f"✅ 推送完成: {home_team} vs {away_team}")
            
        except Exception as e:
            logger.error(f"❌ 执行推送失败: {e}", exc_info=True)
            
            # 更新任务状态
            match_id = match.get('match_id', f"{home_team}_{away_team}_{match_time.strftime('%Y%m%d%H%M')}")
            if match_id in self.scheduled_tasks:
                self.scheduled_tasks[match_id]['status'] = 'failed'
                self.scheduled_tasks[match_id]['error'] = str(e)
    
    def _parse_match_time(self, datetime_str: str) -> Optional[datetime]:
        """
        解析比赛时间字符串
        
        Args:
            datetime_str: 时间字符串
            
        Returns:
            datetime对象或None
        """
        if not datetime_str:
            return None
        
        try:
            datetime_str = str(datetime_str).strip().replace('：', ':')
            
            formats = [
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%m-%d %H:%M',
                '%Y/%m/%d %H:%M',
            ]
            
            for fmt in formats:
                try:
                    match_time = datetime.strptime(datetime_str, fmt)
                    if match_time.year == 1900:
                        now = datetime.now()
                        match_time = match_time.replace(year=now.year)
                    return match_time
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"解析时间失败 {datetime_str}: {e}")
            return None
    
    def get_scheduled_tasks(self) -> List[dict]:
        """
        获取所有已调度的任务列表
        
        Returns:
            任务列表
        """
        tasks = []
        for match_id, task_info in self.scheduled_tasks.items():
            tasks.append({
                'match_id': match_id,
                'home_team': task_info['home_team'],
                'away_team': task_info['away_team'],
                'league': task_info['league'],
                'match_time': task_info['match_time'].strftime('%Y-%m-%d %H:%M'),
                'push_time': task_info['push_time'].strftime('%Y-%m-%d %H:%M'),
                'status': task_info['status']
            })
        
        # 按推送时间排序
        tasks.sort(key=lambda x: x['push_time'])
        return tasks
    
    def clear_old_tasks(self):
        """清理已完成或失败的旧任务"""
        now = datetime.now()
        to_remove = []
        
        for match_id, task_info in self.scheduled_tasks.items():
            # 如果比赛时间已经过了，删除任务记录
            if task_info['match_time'] < now:
                to_remove.append(match_id)
        
        for match_id in to_remove:
            del self.scheduled_tasks[match_id]
        
        if to_remove:
            logger.info(f"🧹 清理了 {len(to_remove)} 个旧任务记录")
