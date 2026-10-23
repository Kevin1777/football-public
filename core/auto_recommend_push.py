"""
自动推荐和推送系统
基于现有推荐模型，自动进行推荐并通过企业微信/Telegram推送
"""
import sys
import logging
import json
import time
import schedule
from collections import Counter
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from recommendation.x1_json_recommender import X1JSONRecommender
from recommendation.vis_formatter import VISFormatter
from services.lottery500_client import Lottery500Client
from core.engine_manager import get_engine_manager, EngineManager
from notification.wecom_bot import WeComNotifier
from notification.telegram_bot import TelegramNotifier
from utils.recommendation_formatter import format_recommendation_direction
from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager
from parser.html_parser import parse_bifa_html

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_recommend_push.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoRecommendPushSystem:
    """自动推荐推送系统"""
    
    def __init__(self, use_wecom=True, use_telegram=False, hours_before=2, hours_window=3):
        """
        初始化系统
        
        Args:
            use_wecom: 是否使用企业微信推送
            use_telegram: 是否使用Telegram推送
            hours_before: 比赛开始前多少小时推送（默认2小时）
            hours_window: 推送时间窗口（默认3小时，即提前2-5小时内的比赛都会推送）
        """
        # 🔥 使用引擎管理器（支持未来切换引擎）
        self.engine_manager = get_engine_manager()
        self.engine = X1JSONRecommender()  # 保留兼容，实际使用engine_manager
        self.vis_formatter = VISFormatter()
        self.use_wecom = use_wecom
        self.use_telegram = use_telegram
        
        # 初始化通知器
        if use_wecom:
            self.wecom_notifier = WeComNotifier()
            if self.wecom_notifier.webhook_url:
                logger.info(f"✅ 企业微信推送已启用 (webhook: ...{self.wecom_notifier.webhook_url[-20:]})")
            else:
                logger.warning("⚠️ 企业微信webhook未配置，推送将失败")
        else:
            self.wecom_notifier = None
            
        if use_telegram:
            self.telegram_notifier = TelegramNotifier()
            logger.info("✅ Telegram推送已启用")
        else:
            self.telegram_notifier = None
        
        # 数据目录 (项目根目录下的 data)
        self.data_dir = Path(__file__).parent.parent / "data"
        
        # 初始化 500彩票网客户端（用于补充盘口数据）
        try:
            self.lottery500_client = Lottery500Client(data_dir=str(self.data_dir))
        except Exception as e:
            self.lottery500_client = None
            logger.warning(f"初始化Lottery500Client失败，无法自动补全盘口数据: {e}")
        
        # 🔥 初始化必发网客户端和缓存管理器（用于自动采集）
        try:
            self.bifaw_client = BifawClient()
            self.detail_cache_manager = DetailCacheManager(str(self.data_dir))
            logger.info("✅ 自动采集系统已初始化")
        except Exception as e:
            self.bifaw_client = None
            self.detail_cache_manager = None
            logger.warning(f"初始化自动采集系统失败: {e}")
        
        # 时间窗口设置
        self.hours_before = hours_before  # 提前多久推送
        self.hours_window = hours_window  # 时间窗口范围
        self.pre_match_tolerance_minutes = 2  # 赛前推荐容差（±2分钟）
        
        # 记录已推送的比赛（避免重复推送）
        self.pushed_matches = set()
        self.load_pushed_records()
        
        # 赛前推送记录（带时间戳，用于持久化）
        self.pre_match_pushed_matches: Dict[str, float] = {}
        self._load_pre_match_history()
        
        logger.info(f"⏰ 时间窗口设置：提前{hours_before}-{hours_before+hours_window}小时推送")
    
    def _normalize_team_name(self, name: str) -> str:
        """规范化队名，去掉中立场等后缀"""
        import re
        # 去掉 (中)、(主)、(客) 等后缀
        return re.sub(r'\s*\([中主客]\)\s*$', '', name).strip()

    def _load_pre_match_history(self):
        """加载赛前推送历史记录"""
        history_file = Path(__file__).parent / "pre_match_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 转换回字典，并清理超过24小时的旧记录
                    now_ts = datetime.now().timestamp()
                    self.pre_match_pushed_matches = {
                        k: v for k, v in data.items() 
                        if now_ts - v < 86400  # 只保留24小时内的
                    }
                logger.info(f"已加载 {len(self.pre_match_pushed_matches)} 条赛前推送历史")
            except Exception as e:
                logger.error(f"加载赛前推送历史失败: {e}")

    def _save_pre_match_history(self):
        """保存赛前推送历史记录"""
        history_file = Path(__file__).parent / "pre_match_history.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.pre_match_pushed_matches, f)
        except Exception as e:
            logger.error(f"保存赛前推送历史失败: {e}")
    
    def load_pushed_records(self):
        """加载已推送记录"""
        record_file = Path(__file__).parent / "pushed_matches.json"
        if record_file.exists():
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    self.pushed_matches = set(records)
                logger.info(f"已加载 {len(self.pushed_matches)} 条推送记录")
            except Exception as e:
                logger.error(f"加载推送记录失败: {e}")
    
    def save_pushed_records(self):
        """保存已推送记录"""
        record_file = Path(__file__).parent / "pushed_matches.json"
        try:
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.pushed_matches), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存推送记录失败: {e}")
    
    def get_match_id(self, match_info: Dict) -> str:
        """生成比赛唯一标识"""
        return f"{match_info.get('datetime', '')}_{match_info.get('home_team', '')}_{match_info.get('away_team', '')}"
    
    def parse_match_time(self, datetime_str: str) -> Optional[datetime]:
        """
        解析比赛时间字符串
        
        Args:
            datetime_str: 时间字符串，如 "2025-11-23 22:00" 或 "11-23 22:00"
            
        Returns:
            datetime对象或None
        """
        if not datetime_str:
            return None
        
        try:
            # 标准化输入：去掉首尾空格，并将全角冒号替换为半角冒号
            datetime_str = str(datetime_str).strip().replace('：', ':')
            
            # 尝试多种格式
            formats = [
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%m-%d %H:%M',
                '%Y/%m/%d %H:%M',
                '%H:%M',  # 仅时间（用于模拟“当前时间”）
            ]
            
            for fmt in formats:
                try:
                    match_time = datetime.strptime(datetime_str, fmt)
                    # 如果没有年份，添加当前年份
                    if match_time.year == 1900:
                        # 特殊处理纯时间格式（HH:MM）：用今天的日期 + 用户指定的时间
                        now = datetime.now()
                        match_time = now.replace(
                            hour=match_time.hour,
                            minute=match_time.minute,
                            second=0,
                            microsecond=0
                        )
                    return match_time
                except ValueError:
                    continue
            
            logger.warning(f"无法解析时间格式: {datetime_str}")
            return None
            
        except Exception as e:
            logger.error(f"解析时间失败 {datetime_str}: {e}")
            return None
    
    def is_match_in_time_window(self, match_info: Dict) -> tuple[bool, str]:
        """
        判断比赛是否在推送时间窗口内
        
        Args:
            match_info: 比赛信息
            
        Returns:
            (是否在窗口内, 原因说明)
        """
        datetime_str = match_info.get('datetime', '') or match_info.get('match_time', '')
        match_time = self.parse_match_time(datetime_str)
        
        if not match_time:
            return False, "无法解析比赛时间"
        
        now = datetime.now()
        time_diff = match_time - now
        hours_until_match = time_diff.total_seconds() / 3600
        
        # 比赛已开始或已结束
        if hours_until_match < 0:
            return False, f"比赛已开始（{abs(hours_until_match):.1f}小时前）"
        
        # 比赛太早（超出窗口）
        if hours_until_match > self.hours_before + self.hours_window:
            return False, f"比赛太早（{hours_until_match:.1f}小时后，窗口：{self.hours_before}-{self.hours_before+self.hours_window}小时）"
        
        # 比赛太晚（已过推送时间）
        if hours_until_match < self.hours_before:
            # 如果是临场模式（窗口小于1小时），允许更晚推送
            if self.hours_before < 1:
                # 临场模式：比赛还没开始就推送
                if hours_until_match > 0:
                    minutes_left = hours_until_match * 60
                    return True, f"🔥 临场推送（比赛{minutes_left:.0f}分钟后开始）"
                else:
                    return False, f"比赛已开始（{abs(hours_until_match)*60:.0f}分钟前）"
            else:
                # 常规模式：至少提前30分钟
                if hours_until_match > 0.5:
                    return True, f"⚠️ 比赛即将开始（{hours_until_match:.1f}小时后）"
                else:
                    return False, f"推送时间已过（仅剩{hours_until_match*60:.0f}分钟）"
        
        # 在时间窗口内
        if self.hours_before < 1:
            # 临场模式：显示分钟数
            minutes_left = hours_until_match * 60
            return True, f"🔥 在临场窗口内（比赛{minutes_left:.0f}分钟后开始）"
        else:
            # 常规模式：显示小时数
            return True, f"✅ 在推送窗口内（{hours_until_match:.1f}小时后开始）"
    
    def find_recent_matches(self, hours_ahead: int = 24) -> List[Path]:
        """
        查找即将开始的比赛数据文件
        
        Args:
            hours_ahead: 查找未来N小时内的比赛
            
        Returns:
            比赛数据文件路径列表
        """
        now = datetime.now()
        target_dates = [(now + timedelta(hours=h)).strftime('%Y/%m/%d') for h in range(0, hours_ahead + 24, 24)]
        
        match_files = []
        for date_str in target_dates:
            year, month, day = date_str.split('/')
            date_dir = self.data_dir / year / month / day
            
            if date_dir.exists():
                # 查找所有JSON文件（排除盘口数据和标盘指数）
                json_files = list(date_dir.glob("*.json"))
                json_files = [
                    f for f in json_files 
                    if f.name not in ["盘口数据.json", "标盘指数_latest.json"]
                    and not f.name.startswith(".")
                ]
                match_files.extend(json_files)
        
        return match_files
    
    def load_match_data(self, match_file: Path) -> Optional[Dict]:
        """加载比赛数据"""
        try:
            with open(match_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载比赛数据失败 {match_file}: {e}")
            return None
    
    def load_trade_data(self, match_file: Path) -> Optional[pd.DataFrame]:
        """
        加载交易明细数据（用于V5/V7等基于成交量的策略）
        
        Args:
            match_file: 比赛数据文件路径
            
        Returns:
            交易数据DataFrame或None
        """
        try:
            # 交易明细文件通常在同目录下，命名为 "比赛_交易明细.csv"
            trade_file = match_file.parent / f"{match_file.stem}_交易明细.csv"
            
            if trade_file.exists():
                return pd.read_csv(trade_file)
            else:
                # 如果没有交易明细，返回空DataFrame
                logger.debug(f"未找到交易明细文件: {trade_file}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"加载交易明细失败: {e}")
            return pd.DataFrame()
    
    def analyze_and_push(self, match_file: Path) -> bool:
        """
        分析比赛并推送推荐
        
        Args:
            match_file: 比赛数据文件路径
            
        Returns:
            是否成功推送
        """
        try:
            # 加载比赛数据
            match_data = self.load_match_data(match_file)
            if not match_data:
                return False
            
            match_data = self._ensure_handicap_data(match_data)
            
            # 🔥 先提取match_info，避免后续使用时未定义
            match_info = match_data.get('match_info', {})
            
            if not match_data.get('handicap_data'):
                logger.warning(f"⚠️ 盘口数据缺失，尝试分析但可靠性下降: {match_info.get('home_team')} vs {match_info.get('away_team')}")
            match_id = self.get_match_id(match_info)
            
            # 检查是否已推送
            if match_id in self.pushed_matches:
                logger.debug(f"比赛已推送，跳过: {match_id}")
                return False
            
            # ⏰ 检查比赛是否在时间窗口内
            in_window, time_reason = self.is_match_in_time_window(match_info)
            if not in_window:
                logger.debug(f"比赛不在时间窗口: {time_reason}")
                return False
            
            logger.info(f"⏰ {time_reason}")
            
            # 🔥 使用引擎管理器进行推荐分析
            logger.info(f"分析比赛: {match_info.get('home_team')} vs {match_info.get('away_team')}")
            
            # 使用引擎管理器（支持未来切换引擎）
            std_result = self.engine_manager.recommend(str(match_file))
            
            # 检查是否熔断
            if std_result.meltdown:
                logger.warning(f"推荐熔断: {std_result.meltdown_reason}")
                return False
            
            # 使用标准化结果格式
            analysis_result = std_result.to_push_format()
            
            # 🔥 修改：无论推荐与否都推送，只是标注推荐状态
            should_bet = analysis_result.get('should_bet', False)
            if should_bet:
                logger.info(f"✅ 推荐下注，准备推送")
            else:
                logger.info(f"⚠️ 不推荐下注，但仍推送分析结果")
            
            # 构造推送数据（使用X1 JSON格式）
            push_data = {
                "version": result.get("version", "X1-JSON-V1.0"),  # 🔥 传递版本号
                "match_info": match_info,
                "recommendation": analysis_result,
                "should_bet": should_bet,
                "x1_json_result": result  # 完整的X1 JSON结果
            }
            
            # 推送到企业微信
            wecom_success = False
            if self.wecom_notifier:
                try:
                    wecom_success = self.wecom_notifier.send_recommendation(push_data)
                    if wecom_success:
                        logger.info(f"✅ 企业微信推送成功")
                except Exception as e:
                    logger.error(f"企业微信推送失败: {e}")
            
            # 推送到Telegram
            telegram_success = False
            if self.telegram_notifier:
                try:
                    telegram_success = self.telegram_notifier.send_recommendation(push_data)
                    if telegram_success:
                        logger.info(f"✅ Telegram推送成功")
                except Exception as e:
                    logger.error(f"Telegram推送失败: {e}")
            
            # 记录已推送
            if wecom_success or telegram_success:
                self.pushed_matches.add(match_id)
                self.save_pushed_records()
                
                # 打印推送信息
                logger.info("=" * 60)
                logger.info(f"推荐: {analysis_result['recommendation']}")
                logger.info(f"置信度: {analysis_result['confidence']*100:.1f}%")
                logger.info(f"理由: {analysis_result['reason']}")
                logger.info("=" * 60)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"处理比赛时出错 {match_file}: {e}", exc_info=True)
            return False
    
    def scan_and_push(self):
        """扫描并推送所有符合条件的比赛"""
        logger.info("=" * 60)
        logger.info(f"开始扫描比赛 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # 查找未来24小时的比赛
        match_files = self.find_recent_matches(hours_ahead=24)
        logger.info(f"找到 {len(match_files)} 场比赛待分析")
        
        if not match_files:
            logger.info("暂无比赛数据")
            return
        
        # 分析并推送
        pushed_count = 0
        for match_file in match_files:
            if self.analyze_and_push(match_file):
                pushed_count += 1
                # 避免推送过快
                time.sleep(1)
        
        logger.info(f"本次扫描完成，成功推送 {pushed_count} 场比赛")
    
    def run_once(self):
        """执行一次扫描"""
        try:
            self.scan_and_push()
        except Exception as e:
            logger.error(f"扫描出错: {e}", exc_info=True)
    
    def hourly_broadcast(self, test_time: Optional[datetime] = None):
        """
        整点播报：提前1分钟播报下一小时的比赛
        
        例如：20:59 播报 21:00~22:00 的比赛
        
        Args:
            test_time: 可选的测试时间，用于测试特定小时的播报
        """
        try:
            now = test_time if test_time else datetime.now()
            # 🔥 改为播报下一小时：向上取整到下一个整点
            if now.minute == 0 and now.second == 0:
                # 如果刚好是整点，播报本小时
                hour_start = now.replace(minute=0, second=0, microsecond=0)
            else:
                # 否则播报下一小时（提前1分钟）
                hour_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            logger.info("=" * 60)
            logger.info(f"📢 整点播报 - {hour_start.strftime('%H:00')} (提前1分钟)")
            logger.info("=" * 60)
            
            matches_this_hour = []
            
            # 🔥 新逻辑：只播报同时有盘口和标盘数据的比赛
            # 步骤0：根据时段决定读取哪些日期的数据
            from datetime import timedelta as td
            
            # 🔥 改为根据 hour_start（播报的小时）判断日期范围
            broadcast_hour = hour_start.hour
            if 0 <= broadcast_hour < 6:
                # 凌晨时段：读取昨日和今日（相对于hour_start）
                logger.info("🌙 凌晨时段，读取昨日+今日标盘数据")
                dates_to_check = [
                    (hour_start - td(days=1)).strftime('%Y/%m/%d'),  # hour_start的前一天
                    hour_start.strftime('%Y/%m/%d')                   # hour_start当天
                ]
            else:
                # 其他时段：读取今日和明日（相对于hour_start）
                logger.info("☀️ 白天时段，读取今日+明日标盘数据")
                dates_to_check = [
                    hour_start.strftime('%Y/%m/%d'),                   # hour_start当天
                    (hour_start + td(days=1)).strftime('%Y/%m/%d')    # hour_start的后一天
                ]
            
            handicap_matches = {}  # {时间: {队名, 盘口信息}}
            
            for date_str in dates_to_check:
                year, month, day = date_str.split('/')
                handicap_file = self.data_dir / year / month / day / "盘口数据.json"
                
                if handicap_file.exists():
                    try:
                        with open(handicap_file, 'r', encoding='utf-8') as f:
                            handicap_data = json.load(f)
                        
                        for key, match in handicap_data.items():
                            time_str = match.get('time', '')
                            
                            if time_str:
                                try:
                                    match_datetime_str = f"{date_str.replace('/', '-')} {time_str}"
                                    match_time = datetime.strptime(match_datetime_str, '%Y-%m-%d %H:%M')
                                    
                                    # 只收集本小时内的比赛
                                    if hour_start <= match_time < hour_end:
                                        # 使用队名作为key进行匹配
                                        match_key = f"{match.get('home_team', '')}_{match.get('away_team', '')}"
                                        handicap_matches[match_key] = {
                                            'time': match_time,
                                            'home_team': match.get('home_team', ''),
                                            'away_team': match.get('away_team', ''),
                                            'handicap': match.get('current_handicap_str', ''),
                                            'league': None  # 待从标盘数据补充
                                        }
                                except ValueError:
                                    pass
                        
                        if len(handicap_matches) > 0:
                            logger.info(f"从 {date_str} 盘口数据找到 {len(handicap_matches)} 场本小时比赛")
                    except Exception as e:
                        logger.warning(f"读取 {date_str} 盘口数据失败: {e}")
            
            # 步骤2：读取标盘数据，筛选未开始的比赛，并与盘口数据做交集
            if len(handicap_matches) > 0:
                for date_str in dates_to_check:
                    year, month, day = date_str.split('/')
                    biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                    
                    if biaopan_file.exists():
                        try:
                            with open(biaopan_file, 'r', encoding='utf-8') as f:
                                biaopan_data = json.load(f)
                            
                            logger.info(f"📂 从 {date_str} 标盘指数文件读取到 {len(biaopan_data.get('matches', []))} 场比赛")
                            
                            for match in biaopan_data.get('matches', []):
                                kickoff_str = match.get('kickoff', '')
                                match_time = self.parse_match_time(kickoff_str)
                                
                                # 🔥 筛选条件：在本小时内（包括已开始和未开始的比赛）
                                if match_time and hour_start <= match_time < hour_end:
                                    # 尝试匹配队名（支持模糊匹配，去掉中立场等后缀）
                                    home = match.get('home', '')
                                    away = match.get('away', '')
                                    home_norm = self._normalize_team_name(home)
                                    away_norm = self._normalize_team_name(away)
                                    
                                    # 尝试精确匹配和模糊匹配
                                    match_key = f"{home}_{away}"
                                    match_key_norm = f"{home_norm}_{away_norm}"
                                    
                                    # 如果在盘口数据中存在，说明同时有盘口和标盘
                                    handicap_info = handicap_matches.get(match_key) or handicap_matches.get(match_key_norm)
                                    if handicap_info:
                                        # 判断比赛状态（用真实当前时间，而非test_time）
                                        real_now = datetime.now()
                                        status = "进行中" if match_time <= real_now else "未开始"
                                        
                                        matches_this_hour.append({
                                            'time': handicap_info['time'],
                                            'league': match.get('league', '未知联赛'),
                                            'home_team': home,
                                            'away_team': away,
                                            'datetime_str': handicap_info['time'].strftime('%H:%M'),
                                            'handicap': handicap_info['handicap'],
                                            'status': status  # 新增：比赛状态
                                        })
                                        logger.info(f"✅ 匹配成功: {home} vs {away} ({match_time.strftime('%H:%M')}) [{status}]")
                            
                            if len(matches_this_hour) > 0:
                                logger.info(f"从 {date_str} 标盘数据匹配到 {len(matches_this_hour)} 场（同时有盘口+标盘）")
                        except Exception as e:
                            logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
            
            # 方法2：从标盘指数文件读取（备用）
            if len(matches_this_hour) == 0:
                today = now.strftime('%Y/%m/%d')
                year, month, day = today.split('/')
                biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                
                if biaopan_file.exists():
                    try:
                        with open(biaopan_file, 'r', encoding='utf-8') as f:
                            biaopan_data = json.load(f)
                        
                        for match in biaopan_data.get('matches', []):
                            kickoff_str = match.get('kickoff', '')
                            match_time = self.parse_match_time(kickoff_str)
                            
                            if match_time and hour_start <= match_time < hour_end:
                                matches_this_hour.append({
                                    'time': match_time,
                                    'league': match.get('league', '未知联赛'),
                                    'home_team': match.get('home', ''),
                                    'away_team': match.get('away', ''),
                                    'datetime_str': match_time.strftime('%H:%M')
                                })
                        logger.info(f"从标盘指数文件找到 {len(matches_this_hour)} 场比赛")
                    except Exception as e:
                        logger.warning(f"读取标盘指数文件失败: {e}")
            
            # 方法2：从单个比赛文件读取（补充）
            if len(matches_this_hour) == 0:
                match_files = self.find_recent_matches(hours_ahead=24)
                
                for match_file in match_files:
                    match_data = self.load_match_data(match_file)
                    if not match_data:
                        continue
                    
                    match_info = match_data.get('match_info', {})
                    datetime_str = match_info.get('datetime', '') or match_info.get('match_time', '')
                    match_time = self.parse_match_time(datetime_str)
                    
                    if match_time and hour_start <= match_time < hour_end:
                        matches_this_hour.append({
                            'time': match_time,
                            'league': match_info.get('league', '未知联赛'),
                            'home_team': match_info.get('home_team', ''),
                            'away_team': match_info.get('away_team', ''),
                            'datetime_str': match_time.strftime('%H:%M')
                        })
                logger.info(f"从比赛文件找到 {len(matches_this_hour)} 场比赛")
            
            # 按时间排序
            matches_this_hour.sort(key=lambda x: x['time'])
            
            # 统计已开始和未开始的比赛
            started = sum(1 for m in matches_this_hour if m.get('status') == '进行中')
            upcoming = sum(1 for m in matches_this_hour if m.get('status') == '未开始')
            
            logger.info("=" * 60)
            logger.info(f"📊 整点播报统计")
            logger.info(f"   盘口数据: {len(handicap_matches)} 场")
            logger.info(f"   匹配成功: {len(matches_this_hour)} 场（同时有盘口+标盘）")
            logger.info(f"   进行中: {started} 场 | 未开始: {upcoming} 场")
            logger.info("=" * 60)
            
            # 推送播报
            if self.wecom_notifier:
                self._send_hourly_broadcast(matches_this_hour, hour_start, hour_end)
            
            if self.telegram_notifier:
                # TODO: 如果使用Telegram，也可以推送
                pass
                
        except Exception as e:
            logger.error(f"整点播报失败: {e}", exc_info=True)
    
    def _send_hourly_broadcast(self, matches: list, hour_start: datetime, hour_end: datetime):
        """发送整点播报到企业微信（市场概览看板版）"""
        try:
            # 1. 基础统计
            total_count = len(matches)
            
            # 2. 构造头部
            hour_str = hour_start.strftime('%H:00')
            next_hour_str = hour_end.strftime('%H:00')
            
            content = f"### 📢 整点市场概览（提前1分钟）\n"
            content += f"<font color=\"comment\">{hour_str} ~ {next_hour_str}</font>\n\n"
            
            if not matches:
                content += f"💤 **本小时暂无比赛**\n"
                content += f"<font color=\"comment\">系统持续监控中...</font>\n"
            else:
                # 3. 提取关键信息（盘口变化等）
                rising_count = 0
                falling_count = 0
                
                # 预处理列表，获取盘口趋势
                processed_matches = []
                for m in matches:
                    # 尝试获取盘口变化
                    trend = "稳"
                    arrow = ""
                    handicap_display = m.get('handicap', '')
                    
                    # 🔥 关键修复：如果盘口为空，尝试主动补全（无人值守模式的核心）
                    if not handicap_display or handicap_display == '未开盘':
                        try:
                            # 构造基础信息用于查询
                            match_info_for_query = {
                                'home_team': m['home_team'],
                                'away_team': m['away_team']
                            }
                            # 使用 _load_handicap_from_storage (它包含了在线拉取兜底逻辑)
                            handicap_data = self._load_handicap_from_storage(match_info_for_query, m['time'])
                            
                            if handicap_data:
                                handicap_display = handicap_data.get('current_handicap')
                                # 如果有文本描述，优先使用文本（如受平手/半球）
                                if handicap_data.get('current_handicap_str'):
                                     handicap_display = handicap_data.get('current_handicap_str')
                                     
                                logger.info(f"✅ 整点播报补全盘口: {m['home_team']} vs {m['away_team']} -> {handicap_display}")
                        except Exception as e:
                            logger.warning(f"补全盘口失败: {e}")
                    
                    if not handicap_display:
                        handicap_display = '未开盘'

                    processed_matches.append({
                        "time": m['time'].strftime('%H:%M'),
                        "league": m['league'],
                        "home": m['home_team'],
                        "away": m['away_team'],
                        "handicap": handicap_display,
                        "status": m.get('status', '未知'),  # 🔥 新增：比赛状态
                        "is_big_league": m['league'] in ["英超", "西甲", "德甲", "意甲", "法甲", "欧冠", "亚冠"]
                    })

                # 4. 市场概况区
                # 🔥 统计已开始和未开始的比赛
                started_count = sum(1 for m in processed_matches if m.get('status') == '进行中')
                upcoming_count = sum(1 for m in processed_matches if m.get('status') == '未开始')
                
                content += f"**📊 市场概况：** 共 **{total_count}** 场比赛"
                if started_count > 0 or upcoming_count > 0:
                    content += f" | ⚽{started_count}场进行中 | 🕐{upcoming_count}场未开始"
                content += "\n"
                content += f"<font color=\"comment\">{'─'*20}</font>\n\n"
                
                # 5. 比赛列表区
                content += f"**📋 重点场次关注：**\n"
                
                from utils.recommendation_formatter import _format_handicap_value
                
                for i, m in enumerate(processed_matches, 1):
                    # 联赛名称（保留前4个字，保持整齐）
                    league_tag = f"【{m['league'][:4]}】"
                    
                    # 盘口显示优化
                    h_val = m['handicap']
                    # 尝试格式化盘口数字（如果是数字的话）
                    try:
                        if isinstance(h_val, (int, float)):
                             h_str = _format_handicap_value(h_val)
                        else:
                             h_str = str(h_val)
                    except:
                        h_str = str(h_val)

                    # 构造单行
                    # 格式：15:30【英超】曼城 vs 利物浦 | 状态
                    line = f"**{m['time']}** {league_tag} {m['home']} vs {m['away']}"
                    
                    # 🔥 新增：比赛状态标记
                    status = m.get('status', '')
                    if status == '进行中':
                        status_tag = " <font color=\"warning\">⚽进行中</font>"
                    elif status == '未开始':
                        status_tag = " <font color=\"comment\">🕐未开始</font>"
                    else:
                        status_tag = ""
                    
                    # 如果是大联赛，加粗并加火
                    if m['is_big_league']:
                        line = f"🔥 {line}{status_tag}"
                    else:
                        line = f"{line}{status_tag}"
                    
                    content += f"{line}\n"
                    content += f"> 盘口：<font color=\"info\">{h_str}</font>\n"
                
                content += "\n"

            # 底部
            # 下次播报时间是 hour_end - 1分钟（即下一小时的59分）
            next_broadcast = (hour_end - timedelta(minutes=1)).strftime('%H:%M')
            content += f"<font color=\"comment\">{'─'*20}</font>\n"
            content += f"<font color=\"comment\">🤖 自动扫描中 | 下次播报 {next_broadcast}</font>"
            
            # 发送消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            if self.wecom_notifier._send_message(message):
                logger.info(f"✅ 整点播报推送成功（{len(matches)}场比赛）")
            else:
                logger.error("❌ 整点播报推送失败")
                
        except Exception as e:
            logger.error(f"发送整点播报失败: {e}", exc_info=True)
    
    def push_pre_match_recommendations(self, minutes_before: int = 5, test_time: Optional[datetime] = None, skip_finished_check: bool = False, auto_collect: bool = False):
        """
        赛前推荐推送：在比赛开始前N分钟推送推荐方向
        
        Args:
            minutes_before: 比赛开始前多少分钟推送（默认5分钟）
            test_time: 模拟时间（用于测试）
            skip_finished_check: 跳过已完场检查（用于强制测试）
            auto_collect: 是否自动采集缺失的数据（默认False，避免卡顿）
        """
        try:
            now = test_time if test_time else datetime.now()
            tolerance = self.pre_match_tolerance_minutes
            target_time_start = now + timedelta(minutes=max(minutes_before - tolerance, 0))
            target_time_end = now + timedelta(minutes=minutes_before + tolerance)
            
            logger.info("=" * 60)
            logger.info(f"🔔 赛前{minutes_before}分钟推荐推送 - {now.strftime('%H:%M')} (窗口 {target_time_start.strftime('%H:%M')}~{target_time_end.strftime('%H:%M')})")
            logger.info("=" * 60)
            self._cleanup_pre_match_cache(now)
            
            # 查找即将开始的比赛
            matches_to_push = []
            
            # 🔥 根据时段决定读取哪些日期的数据（与整点播报逻辑一致）
            target_hour = target_time_start.hour
            if 0 <= target_hour < 6:
                # 凌晨时段：读取昨日和今日
                logger.info("🌙 凌晨时段，读取昨日+今日数据")
                dates_to_check = [
                    (now - timedelta(days=1)).strftime('%Y/%m/%d'),
                    now.strftime('%Y/%m/%d')
                ]
            else:
                # 其他时段：读取今日和明日
                dates_to_check = [
                    now.strftime('%Y/%m/%d'),
                    (now + timedelta(days=1)).strftime('%Y/%m/%d')
                ]
            
            # 🔥 优先从标盘数据读取（有detail_url），再从盘口数据补充
            for date_str in dates_to_check:
                year, month, day = date_str.split('/')
                
                # 先加载标盘数据（获取detail_url）
                biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                biaopan_lookup = {}  # {home_away_time: match_data}
                if biaopan_file.exists():
                    try:
                        with open(biaopan_file, 'r', encoding='utf-8') as f:
                            biaopan_data = json.load(f)
                        for m in biaopan_data.get('matches', []):
                            key = f"{m.get('home', '')}_{m.get('away', '')}_{m.get('kickoff', '')}"
                            biaopan_lookup[key] = m
                    except:
                        pass
                
                handicap_file = self.data_dir / year / month / day / "盘口数据.json"
                
                if handicap_file.exists():
                    try:
                        with open(handicap_file, 'r', encoding='utf-8') as f:
                            handicap_data = json.load(f)
                        
                        count_before = len(matches_to_push)
                        for key, match in handicap_data.items():
                            time_str = match.get('time', '')
                            if time_str:
                                try:
                                    # 🔥 解析时间并处理跨日情况
                                    hour = int(time_str.split(':')[0])
                                    base_date = datetime.strptime(date_str.replace('/', '-'), '%Y-%m-%d')
                                    
                                    # 凌晨比赛(00:00~06:00)存储在前一天目录，实际日期需要+1天
                                    if hour < 6:
                                        actual_date = base_date + timedelta(days=1)
                                    else:
                                        actual_date = base_date
                                    
                                    match_datetime_str = f"{actual_date.strftime('%Y-%m-%d')} {time_str}"
                                    match_time = datetime.strptime(match_datetime_str, '%Y-%m-%d %H:%M')
                                    
                                    if target_time_start <= match_time <= target_time_end:
                                        # 🔥 用真实时间检查比赛是否已完场（除非强制测试模式）
                                        if not skip_finished_check:
                                            real_now = datetime.now()
                                            if match_time < real_now - timedelta(minutes=90):
                                                # 比赛已结束超过90分钟，跳过
                                                continue
                                        
                                        minutes_since_start = (now - match_time).total_seconds() / 60
                                        if match_time > now or minutes_since_start <= 10:
                                            home_team = match.get('home_team', '')
                                            away_team = match.get('away_team', '')
                                            
                                            # 🔥 从标盘数据获取detail_url
                                            lookup_key = f"{home_team}_{away_team}_{match_datetime_str}"
                                            biaopan_match = biaopan_lookup.get(lookup_key, {})
                                            
                                            # 合并数据
                                            merged_match = {**match}
                                            if biaopan_match.get('detail_url'):
                                                merged_match['detail_url'] = biaopan_match['detail_url']
                                            if biaopan_match.get('detail_params'):
                                                merged_match['detail_params'] = biaopan_match['detail_params']
                                            
                                            # 🔥 优先从标盘数据获取联赛名称
                                            league_name = biaopan_match.get('league') or match.get('league', '未知联赛')
                                            merged_match['league'] = league_name
                                            
                                            matches_to_push.append({
                                                'match_time': match_time,
                                                'league': league_name,
                                                'home_team': home_team,
                                                'away_team': away_team,
                                                'match_data': merged_match
                                            })
                                except ValueError:
                                    pass
                        
                        count_new = len(matches_to_push) - count_before
                        if count_new > 0:
                            logger.info(f"从 {date_str} 盘口数据找到 {count_new} 场窗口内比赛")
                    except Exception as e:
                        logger.warning(f"读取 {date_str} 盘口数据失败: {e}")
            
            # 🔥 如果盘口数据没找到，尝试从标盘指数读取
            if not matches_to_push:
                for date_str in dates_to_check:
                    year, month, day = date_str.split('/')
                    biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                    
                    if biaopan_file.exists():
                        try:
                            with open(biaopan_file, 'r', encoding='utf-8') as f:
                                biaopan_data = json.load(f)
                            
                            for match in biaopan_data.get('matches', []):
                                kickoff_str = match.get('kickoff', '')
                                match_time = self.parse_match_time(kickoff_str)
                                
                                if match_time and target_time_start <= match_time <= target_time_end:
                                    # 🔥 用真实时间检查比赛是否已完场（除非强制测试模式）
                                    if not skip_finished_check:
                                        real_now = datetime.now()
                                        if match_time < real_now - timedelta(minutes=90):
                                            continue
                                    
                                    minutes_since_start = (now - match_time).total_seconds() / 60
                                    if match_time > now or minutes_since_start <= 10:
                                        matches_to_push.append({
                                            'match_time': match_time,
                                            'league': match.get('league', '未知联赛'),
                                            'home_team': match.get('home', ''),
                                            'away_team': match.get('away', ''),
                                            'match_data': match
                                        })
                            
                            if matches_to_push:
                                logger.info(f"从 {date_str} 标盘数据找到 {len(matches_to_push)} 场窗口内比赛")
                        except Exception as e:
                            logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
            
            if not matches_to_push:
                logger.info(f"暂无{minutes_before}分钟后开始的比赛")
                return
            
            logger.info(f"找到 {len(matches_to_push)} 场比赛需要推送推荐")
            
            # 对每场比赛进行分析并推送
            for match_info in matches_to_push:
                try:
                    extended_match_info = {
                        'league': match_info['league'],
                        'home_team': match_info['home_team'],
                        'away_team': match_info['away_team'],
                        'datetime': match_info['match_time'].strftime('%Y-%m-%d %H:%M')
                    }
                    match_id = self.get_match_id(extended_match_info)

                    if match_id in self.pre_match_pushed_matches:
                        logger.info(f"⏭️ 赛前推送已发送，跳过重复: {match_info['home_team']} vs {match_info['away_team']}")
                        continue

                    # 🔥 尝试加载完整的比赛数据文件（X1 JSON格式）
                    match_file = self._find_match_file(match_info['home_team'], match_info['away_team'], match_info['match_time'])
                    
                    if not match_file:
                        if auto_collect:
                            # 🔥 自动采集比赛明细数据（可能较慢）
                            logger.info(f"📥 未找到数据文件，尝试自动采集...")
                            match_file = self._auto_collect_match(match_info, match_info.get('match_data', {}))
                            
                            if not match_file:
                                logger.warning(f"自动采集失败，跳过推送: {match_info['home_team']} vs {match_info['away_team']}")
                                continue
                        else:
                            logger.warning(f"⚠️ 未找到数据文件，跳过: {match_info['home_team']} vs {match_info['away_team']}（可用auto_collect=True开启自动采集）")
                            continue
                    
                    # 🔥 使用引擎管理器进行推荐分析
                    logger.info(f"分析比赛: {match_info['home_team']} vs {match_info['away_team']}")
                    std_result = self.engine_manager.recommend(str(match_file))
                    
                    # 检查是否熔断
                    if std_result.meltdown:
                        logger.warning(f"推荐熔断: {std_result.meltdown_reason}")
                        
                        # 🔥 熔断时也推送"不推荐"消息
                        meltdown_result = std_result.to_push_format()
                        self._send_pre_match_recommendation(match_info, meltdown_result, minutes_before)
                        
                        # 记录推送历史
                        self.pre_match_pushed_matches[match_id] = datetime.now().timestamp()
                        self._save_pre_match_history()
                        continue
                    
                    # 使用标准化结果格式
                    analysis_result = std_result.to_push_format()
                    
                    # 🔥 构造推送消息（使用X1 JSON格式）
                    self._send_pre_match_recommendation(match_info, analysis_result, minutes_before)
                    
                    # 记录并保存推送历史
                    self.pre_match_pushed_matches[match_id] = datetime.now().timestamp()
                    self._save_pre_match_history()
                    
                    # 避免推送过快
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"处理比赛推荐失败 {match_info['home_team']} vs {match_info['away_team']}: {e}", exc_info=True)
            
            logger.info(f"✅ 赛前{minutes_before}分钟推荐推送完成（{len(matches_to_push)}场比赛）")
            
        except Exception as e:
            logger.error(f"赛前推荐推送失败: {e}", exc_info=True)
    
    def _find_match_file(self, home_team: str, away_team: str, match_time: datetime) -> Optional[Path]:
        """查找比赛数据文件"""
        try:
            # 尝试从比赛时间推断日期
            date_str = match_time.strftime('%Y/%m/%d')
            year, month, day = date_str.split('/')
            date_dir = self.data_dir / year / month / day
            
            if not date_dir.exists():
                return None
            
            # 查找包含队名的JSON文件
            json_files = list(date_dir.glob("*.json"))
            for json_file in json_files:
                if json_file.name in ["盘口数据.json", "标盘指数_latest.json"]:
                    continue
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        match_info = data.get('match_info', {})
                        # 🔥 支持两种字段名格式
                        file_home = match_info.get('home_team') or match_info.get('home', '')
                        file_away = match_info.get('away_team') or match_info.get('away', '')
                        if file_home == home_team and file_away == away_team:
                            return json_file
                except:
                    continue
            
            return None
        except Exception as e:
            logger.debug(f"查找比赛文件失败: {e}")
            return None

    def _auto_collect_match(self, match_info: dict, match_data: dict) -> Optional[Path]:
        """
        自动采集比赛明细数据（四合一：标盘+让球+大小球+比分）
        
        Args:
            match_info: 包含home_team, away_team, match_time等
            match_data: 原始比赛数据（包含detail_url等）
            
        Returns:
            采集成功返回保存的文件路径，失败返回None
        """
        if not self.bifaw_client or not self.detail_cache_manager:
            logger.warning("自动采集系统未初始化，无法采集")
            return None
        
        try:
            detail_url = match_data.get('detail_url')
            if not detail_url:
                logger.warning(f"比赛缺少detail_url，无法采集: {match_info['home_team']} vs {match_info['away_team']}")
                return None
            
            logger.info(f"🔄 自动采集比赛明细（四合一）: {match_info['home_team']} vs {match_info['away_team']}")
            logger.info("=" * 80)
            
            # ========== 1. 抓取标盘明细页面 ==========
            logger.info("📊 步骤1/4: 采集标盘数据...")
            detail_html = self.bifaw_client.fetch_match_detail_selenium(
                detail_url=detail_url,
                match=match_data,
                detail_params=match_data.get('detail_params')
            )
            
            if not detail_html:
                logger.error(f"❌ 标盘明细页面抓取失败: {match_info['home_team']} vs {match_info['away_team']}")
                return None
            
            # 2. 解析标盘明细
            parsed_data = parse_bifa_html(detail_html)
            
            if isinstance(parsed_data, str):
                logger.error(f"❌ HTML解析失败: {parsed_data}")
                return None
            
            trade_df = parsed_data  # parse_bifa_html 返回 DataFrame
            
            if trade_df is None or trade_df.empty:
                logger.warning(f"⚠️  标盘交易数据为空: {match_info['home_team']} vs {match_info['away_team']}")
                return None
            
            logger.info(f"✅ 标盘数据采集成功: {len(trade_df)} 条记录")
            
            # ========== 2. 采集大小球数据 ==========
            logger.info("\n📊 步骤2/4: 采集大小球数据...")
            ou_trade_data = None
            try:
                # 🔥 使用 fetch_ou_trade_details_selenium 方法
                ou_result = self.bifaw_client.fetch_ou_trade_details_selenium(match_data)
                
                if ou_result and ou_result.get('trade_records'):
                    ou_trade_data = ou_result
                    logger.info(f"✅ 大小球数据采集成功: {len(ou_result.get('trade_records', []))} 条记录")
                else:
                    logger.warning("⚠️  大小球数据为空或采集失败")
            except Exception as e:
                logger.error(f"❌ 大小球数据采集失败: {e}")
            
            # ========== 3. 采集让球数据 ==========
            logger.info("\n📊 步骤3/4: 采集让球数据...")
            handicap_trade_data = None
            try:
                # 🔥 使用 fetch_asian_handicap 方法
                handicap_result = self.bifaw_client.fetch_asian_handicap(match_data)
                
                if handicap_result:
                    handicap_trade_data = handicap_result
                    logger.info(f"✅ 让球数据采集成功")
                else:
                    logger.warning("⚠️  让球数据为空或采集失败")
            except Exception as e:
                logger.error(f"❌ 让球数据采集失败: {e}")
            
            # ========== 4. 采集比分数据 ==========
            logger.info("\n📊 步骤4/4: 采集比分数据...")
            correct_score_data = None
            try:
                # 🔥 使用 _fetch_correct_score_detail 方法
                score_result = self.bifaw_client._fetch_correct_score_detail(match_data)
                
                if score_result:
                    correct_score_data = score_result
                    logger.info(f"✅ 比分数据采集成功")
                else:
                    logger.warning("⚠️  比分数据为空或采集失败")
            except Exception as e:
                logger.error(f"❌ 比分数据采集失败: {e}")
            
            logger.info("=" * 80)
            
            # ========== 5. 获取盘口数据（从500彩票网） ==========
            handicap_data = None
            if self.lottery500_client:
                try:
                    match_date = match_info['match_time'].strftime('%Y-%m-%d')
                    match_time_str = match_info['match_time'].strftime('%H:%M')
                    daily_data = self.lottery500_client.fetch_daily_handicaps(match_date)
                    if daily_data:
                        # 先获取基本盘口信息（包含fid）
                        basic_handicap = self.lottery500_client.find_handicap_from_daily_data(
                            daily_data, 
                            match_info['home_team'], 
                            match_info['away_team'],
                            match_time_str
                        )
                        if basic_handicap and basic_handicap.get('fid'):
                            fid = basic_handicap['fid']
                            logger.info(f"  📊 获取到fid: {fid}，正在获取详细盘口数据...")
                            
                            # 🔥 用fid获取详细盘口数据（包含all_companies）
                            detailed_handicap = self.lottery500_client.fetch_handicap_data(fid)
                            if detailed_handicap and detailed_handicap.get('all_companies'):
                                handicap_data = detailed_handicap
                                logger.info(f"  ✅ 获取到详细盘口: {len(detailed_handicap.get('all_companies', []))}家机构")
                            else:
                                # 详细数据获取失败，使用基本数据
                                handicap_data = basic_handicap
                                logger.info(f"  ⚠️ 详细盘口获取失败，使用基本数据: {basic_handicap.get('current_handicap_str', '')}")
                        elif basic_handicap:
                            handicap_data = basic_handicap
                            logger.info(f"  ✅ 获取到500彩票盘口: {basic_handicap.get('current_handicap_str', '')}")
                except Exception as e:
                    logger.warning(f"获取盘口数据失败: {e}")
            
            # 🔥 Fallback: 如果没有获取到盘口数据，使用标盘中的盘口预览
            if not handicap_data and match_data.get('handicap_preview'):
                handicap_data = match_data.get('handicap_preview')
                logger.info(f"  📊 使用标盘盘口数据: {handicap_data}")
            
            # ========== 6. 构建match对象用于保存 ==========
            league = match_info.get('league') or match_data.get('league', '未知联赛')
            logger.info(f"  📋 联赛信息: {league}")
            
            match_for_save = {
                'home': match_info['home_team'],
                'away': match_info['away_team'],
                'league': league,
                'kickoff': match_info['match_time'].strftime('%Y-%m-%d %H:%M'),
                'detail_url': detail_url,
                'match_id': match_data.get('match_id', ''),
            }
            
            # ========== 7. 保存到缓存（四合一数据） ==========
            # 🔥 将让球、大小球、比分数据合并到 ou_trade_data 参数中
            all_trade_data = {}
            if ou_trade_data:
                all_trade_data['ou_trade'] = ou_trade_data
            if handicap_trade_data:
                all_trade_data['handicap_trade'] = handicap_trade_data
            if correct_score_data:
                all_trade_data['correct_score_trade'] = correct_score_data
            
            save_success = self.detail_cache_manager.save_detail(
                match_info=match_for_save,
                trade_data=trade_df,
                handicap_data=handicap_data,
                ou_trade_data=all_trade_data  # 🔥 传入四合一数据
            )
            
            if save_success:
                # 🔥 保存成功后，查找实际文件路径
                saved_file = self._find_match_file(
                    match_info['home_team'], 
                    match_info['away_team'], 
                    match_info['match_time']
                )
                
                # 统计数据完整度
                data_count = 1  # 标盘数据
                if ou_trade_data:
                    data_count += 1
                if handicap_trade_data:
                    data_count += 1
                if correct_score_data:
                    data_count += 1
                
                logger.info(f"✅ 采集成功（{data_count}/4），已保存: {saved_file}")
                return saved_file
            else:
                logger.error("❌ 保存缓存失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ 自动采集失败: {e}", exc_info=True)
            return None

    def _cleanup_pre_match_cache(self, now: datetime):
        """清理过期的赛前推送记录，防止集合无限增长。"""
        # 使用时间戳进行比较，避免直接将 float 与 datetime 比较导致异常
        now_ts = now.timestamp()
        expiry_ts = now_ts - 6 * 3600  # 6小时以前的记录视为过期
        expired = [match_id for match_id, ts in self.pre_match_pushed_matches.items() if ts < expiry_ts]
        for match_id in expired:
            self.pre_match_pushed_matches.pop(match_id, None)

    def _load_handicap_from_storage(self, match_info: dict, match_time: datetime) -> Optional[dict]:
        """
        尝试从本地保存的盘口数据中加载指定比赛的盘口信息。
        优先读取比赛当日，如果是凌晨比赛，再尝试前一天。
        如果本地没有，尝试在线获取一次。
        """
        if not self.lottery500_client:
            return None

        candidates = [match_time]
        if match_time.hour < 6:
            candidates.insert(0, match_time - timedelta(days=1))

        for candidate in candidates:
            date_str = candidate.strftime('%Y-%m-%d')
            try:
                # 1. 尝试读缓存
                daily_data = self.lottery500_client.load_daily_handicap_json(date_str)
                
                # 2. 如果缓存没找到或为空，尝试在线拉取（仅限当天）
                is_today = date_str == datetime.now().strftime('%Y-%m-%d')
                if not daily_data and is_today:
                     logger.info(f"本地无 {date_str} 盘口缓存，尝试在线获取...")
                     daily_data = self.lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
                
                if not daily_data:
                    continue

                result = self.lottery500_client.find_handicap_from_daily_data(
                    daily_handicaps=daily_data,
                    home_team=match_info.get('home_team', ''),
                    away_team=match_info.get('away_team', ''),
                    match_time=match_time.strftime('%H:%M')
                )

                if result:
                    # 如果是在线获取的，顺便补全一下详细数据（初盘等）
                    if is_today and not result.get('handicap_change'):
                         try:
                             from app import enhance_handicap_with_initial_data
                             result = enhance_handicap_with_initial_data(result, self.lottery500_client, logger)
                         except ImportError:
                             pass
                             
                    logger.info(f"✅ 盘口数据补全成功: {match_info.get('home_team')} vs {match_info.get('away_team')} ({date_str})")
                    return result
            except Exception as e:
                logger.warning(f"读取盘口数据失败 ({date_str}): {e}")

        logger.debug(f"❌ 最终未找到盘口数据: {match_info.get('home_team')} vs {match_info.get('away_team')}")
        return None

    def _ensure_handicap_data(self, match_data: dict) -> dict:
        """
        如果比赛数据缺少handicap_data，尝试自动补全。
        """
        if match_data.get('handicap_data'):
            return match_data

        match_info = match_data.get('match_info', {})
        datetime_str = match_info.get('datetime') or match_info.get('match_time')
        match_time = self.parse_match_time(datetime_str) if datetime_str else None

        if match_time:
            fallback = self._load_handicap_from_storage(match_info, match_time)
            if fallback:
                # 🔧 兜底补全：部分比赛可能只有当前盘口，没有初盘等字段
                # 推荐引擎至少需要 initial_handicap_text 才不会直接中断
                try:
                    # 文本字段：优先使用已有字段
                    h_text = (
                        fallback.get('initial_handicap_text')
                        or fallback.get('current_handicap_text')
                        or fallback.get('current_handicap_str')
                        or fallback.get('handicap_str')
                    )

                    if h_text and not fallback.get('initial_handicap_text'):
                        fallback['initial_handicap_text'] = h_text
                    if h_text and not fallback.get('current_handicap_text'):
                        fallback['current_handicap_text'] = h_text

                    # 数值字段：如果只有一个盘口值，则视为初盘=即时盘
                    h_val = fallback.get('current_handicap')
                    if h_val is None:
                        h_val = fallback.get('initial_handicap')
                    if h_val is None:
                        h_val = fallback.get('handicap')

                    if h_val is not None:
                        fallback.setdefault('initial_handicap', h_val)
                        fallback.setdefault('current_handicap', h_val)

                    # 赔率字段缺失时保持为0，不影响主流程
                    for init_key, cur_key in [
                        ('initial_home_odds', 'current_home_odds'),
                        ('initial_away_odds', 'current_away_odds'),
                    ]:
                        if init_key not in fallback and cur_key in fallback:
                            fallback[init_key] = fallback.get(cur_key, 0)
                except Exception as e:
                    logger.debug(f"补全handicap_data失败: {e}")

                match_data['handicap_data'] = fallback
        else:
            logger.debug(f"无法解析比赛时间，跳过盘口补全: {match_info}")

        return match_data
    
    def _send_pre_match_recommendation(self, match_info: dict, analysis_result: dict, minutes_before: int):
        """发送赛前推荐消息（X1 JSON引擎版）"""
        try:
            match_time = match_info['match_time']
            home_team = match_info['home_team']
            away_team = match_info['away_team']
            league = match_info['league']
            
            # 🔥 获取X1 JSON分析细节
            x1_result = analysis_result.get('x1_result', {})
            scores = analysis_result.get('scores', {})
            funding = analysis_result.get('funding_level', {})
            risk_control = analysis_result.get('risk_control', {})
            
            # 2. 确定标题和颜色风格
            is_success = analysis_result.get('success', False)
            should_bet = analysis_result.get('should_bet', False)
            
            if should_bet:
                title = "🔥 X1 JSON推荐·赛前绝杀"
                title_color = "info"
                bet_icon = "✅"
            else:
                title = "🔔 X1 JSON分析·赛前报告"
                title_color = "comment"
                bet_icon = "👀"

            # 3. 构造富文本消息
            content = f"### {title}\n\n"
            content += f"🏆 **{league}** | {match_time.strftime('%H:%M')}\n"
            content += f"⚽ **{home_team} vs {away_team}**\n"
            content += f"<font color=\"comment\">{'─'*20}</font>\n\n"
            
            if is_success:
                confidence = analysis_result.get('confidence', 0)
                direction_map = {'home': '主队', 'away': '客队', 'none': '不推荐'}
                direction_text = direction_map.get(analysis_result.get('recommendation', 'none'), '不推荐')
                reason = analysis_result.get('reason', '')
                
                # 🔥 检查是否是熔断情况
                is_meltdown = analysis_result.get('meltdown', False)
                meltdown_reason = analysis_result.get('meltdown_reason', '')
                
                # --- 核心结论 ---
                if is_meltdown:
                    # 熔断情况的特殊显示
                    content += f"**🚫 熔断保护：** <font color=\"warning\">不推荐投注</font>\n"
                    content += f"**📋 熔断原因：** {meltdown_reason}\n\n"
                elif should_bet:
                    content += f"**{bet_icon} 重点推荐：**<font color=\"info\">**{direction_text}**</font>\n"
                    # 星级展示
                    stars = '⭐' * int(confidence * 5)
                    if confidence > 0.9: stars += '🔥'
                    content += f"**📊 置信指数：** {stars} ({confidence*100:.0f}%)\n"
                    content += f"**💰 盘口：** {analysis_result.get('handicap', 'N/A')}\n\n"
                else:
                    content += f"**{bet_icon} 分析结论：** <font color=\"warning\">观望 / 不推荐</font>\n"
                    content += f"**💭 倾向方向：** {direction_text}\n\n"

                # --- X1 JSON评分模块 ---
                if scores:
                    content += f"**🎯 X1评分：**\n"
                    
                    flm = scores.get('FLM', {})
                    if flm:
                        content += f"> FLM (热度): {flm.get('level', 'N/A')} ({flm.get('confidence', 0)*100:.0f}%)\n"
                    
                    spm = scores.get('SPM', {})
                    if spm:
                        content += f"> SPM (结构): {spm.get('structure', 'N/A')} ({spm.get('confidence', 0)*100:.0f}%)\n"
                    
                    dpi = scores.get('DPI', {})
                    if dpi:
                        content += f"> DPI (风险): {dpi.get('risk_level', 'N/A')} (压强{dpi.get('pressure_index', 0)})\n"
                    
                    content += "\n"
                
                # --- 资金等级 ---
                if funding:
                    content += f"**💵 资金等级：** {funding.get('level', 'N/A')} "
                    content += f"(成交量 {funding.get('total_volume', 0):,})\n\n"
                
                # --- 风控提示 ---
                if risk_control:
                    risk_triggered = any([
                        risk_control.get('SmartSafe'),
                        risk_control.get('SS-Dagger'),
                        risk_control.get('LVC'),
                        risk_control.get('TPI')
                    ])
                    
                    if risk_triggered:
                        content += f"**⚠️ 风控提示：**\n"
                        if risk_control.get('SmartSafe'):
                            content += f"> SmartSafe: 结构支撑缺失\n"
                        if risk_control.get('SS-Dagger'):
                            content += f"> SS-Dagger: 诱导盘识别\n"
                        if risk_control.get('LVC'):
                            content += f"> LVC: 凯利指数异常\n"
                        if risk_control.get('TPI'):
                            content += f"> TPI: 穿盘预警\n"
                        content += "\n"
                
                # --- 综合理由 ---
                if reason:
                    clean_reason = reason.replace(', ', '\n> ')
                    content += f"**📝 推荐理由：**\n> {clean_reason}\n\n"
                    
            else:
                # 分析失败的情况
                content += f"❌ **分析中断**\n"
                content += f"> 原因：{analysis_result.get('message', '未知错误')}\n\n"
            
            # 底部信息
            content += f"<font color=\"comment\">{'─'*20}</font>\n"
            content += f"<font color=\"comment\">⏰ 距离开赛还有 {minutes_before} 分钟</font>\n"
            content += f"<font color=\"comment\">🤖 数据来源: X1 JSON推荐引擎 (准确率83.6%)</font>"
            
            # 发送消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            success = False
            if self.wecom_notifier:
                success = self.wecom_notifier._send_message(message)
            
            if success:
                logger.info(f"✅ 赛前推荐推送成功: {home_team} vs {away_team}")
            else:
                logger.error(f"❌ 赛前推荐推送失败: {home_team} vs {away_team}")
                
        except Exception as e:
            logger.error(f"发送赛前推荐消息失败: {e}", exc_info=True)
    
    def push_pre_match_json_data(self, minutes_before: int = 15, test_time: Optional[datetime] = None):
        """
        赛前采集并推送JSON数据
        
        新功能：在比赛开始前N分钟开始采集数据，采集完成后直接推送JSON
        
        Args:
            minutes_before: 比赛开始前多少分钟开始采集（默认15分钟）
            test_time: 模拟时间（用于测试）
        """
        try:
            now = test_time if test_time else datetime.now()
            # 时间窗口：赛前10-20分钟（共10分钟窗口，确保5分钟执行间隔不会错过）
            tolerance = 5  # 容差5分钟
            target_time_start = now + timedelta(minutes=max(minutes_before - tolerance, 0))  # 赛前10分钟
            target_time_end = now + timedelta(minutes=minutes_before + tolerance)  # 赛前20分钟
            
            logger.info("=" * 60)
            logger.info(f"📥 赛前{minutes_before}分钟采集推送 - {now.strftime('%H:%M')} (窗口 {target_time_start.strftime('%H:%M')}~{target_time_end.strftime('%H:%M')})")
            logger.info("=" * 60)
            
            # 清理过期的推送记录
            self._cleanup_pre_match_cache(now)
            
            # 查找即将开始的比赛
            matches_to_collect = []
            
            # 根据时段决定读取哪些日期的数据
            target_hour = target_time_start.hour
            if 0 <= target_hour < 6:
                dates_to_check = [
                    (now - timedelta(days=1)).strftime('%Y/%m/%d'),
                    now.strftime('%Y/%m/%d')
                ]
            else:
                dates_to_check = [
                    now.strftime('%Y/%m/%d'),
                    (now + timedelta(days=1)).strftime('%Y/%m/%d')
                ]
            
            # 从标盘数据读取（获取detail_url）
            for date_str in dates_to_check:
                year, month, day = date_str.split('/')
                biaopan_file = self.data_dir / year / month / day / "标盘指数_latest.json"
                
                if biaopan_file.exists():
                    try:
                        with open(biaopan_file, 'r', encoding='utf-8') as f:
                            biaopan_data = json.load(f)
                        
                        for match in biaopan_data.get('matches', []):
                            kickoff_str = match.get('kickoff', '')
                            match_time = self.parse_match_time(kickoff_str)
                            
                            if match_time and target_time_start <= match_time <= target_time_end:
                                # 检查是否已经推送过
                                match_id = f"{match.get('home', '')}_{match.get('away', '')}_{match_time.strftime('%Y%m%d%H%M')}"
                                
                                if match_id in self.pre_match_pushed_matches:
                                    logger.info(f"⏭️ 已推送过，跳过: {match.get('home', '')} vs {match.get('away', '')}")
                                    continue
                                
                                # 必须有detail_url才能采集
                                if match.get('detail_url'):
                                    matches_to_collect.append({
                                        'match_time': match_time,
                                        'league': match.get('league', '未知联赛'),
                                        'home_team': match.get('home', ''),
                                        'away_team': match.get('away', ''),
                                        'match_data': match,
                                        'match_id': match_id
                                    })
                                    logger.info(f"✅ 找到待采集比赛: {match.get('home', '')} vs {match.get('away', '')} ({match_time.strftime('%H:%M')})")
                                else:
                                    logger.warning(f"⚠️ 比赛缺少detail_url，无法采集: {match.get('home', '')} vs {match.get('away', '')}")
                        
                    except Exception as e:
                        logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
            
            if not matches_to_collect:
                logger.info(f"暂无{minutes_before}分钟后开始的比赛需要采集")
                return
            
            logger.info(f"📊 找到 {len(matches_to_collect)} 场比赛需要采集并推送")
            
            # 对每场比赛进行采集并推送
            for match_info in matches_to_collect:
                try:
                    home_team = match_info['home_team']
                    away_team = match_info['away_team']
                    match_time = match_info['match_time']
                    match_id = match_info['match_id']
                    
                    logger.info(f"\n{'='*40}")
                    logger.info(f"🔄 开始采集: {home_team} vs {away_team}")
                    
                    # 1. 尝试查找已有的数据文件
                    match_file = self._find_match_file(home_team, away_team, match_time)
                    json_data = None
                    
                    if match_file:
                        # 已有数据文件，直接读取
                        logger.info(f"📂 找到已有数据文件: {match_file}")
                        try:
                            with open(match_file, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                        except Exception as e:
                            logger.warning(f"读取数据文件失败: {e}")
                    
                    if not json_data:
                        # 2. 自动采集数据
                        logger.info(f"📥 未找到数据文件，开始自动采集...")
                        match_file = self._auto_collect_match(match_info, match_info.get('match_data', {}))
                        
                        if match_file:
                            try:
                                with open(match_file, 'r', encoding='utf-8') as f:
                                    json_data = json.load(f)
                            except Exception as e:
                                logger.error(f"读取采集后的数据文件失败: {e}")
                                continue
                        else:
                            logger.error(f"❌ 采集失败，跳过推送: {home_team} vs {away_team}")
                            continue
                    
                    # 3. 推送JSON数据
                    if json_data:
                        logger.info(f"📤 开始推送JSON数据...")
                        success = self._send_json_data_notification(match_info, json_data, minutes_before)
                        
                        if success:
                            # 记录已推送
                            self.pre_match_pushed_matches[match_id] = datetime.now().timestamp()
                            self._save_pre_match_history()
                            logger.info(f"✅ 推送成功: {home_team} vs {away_team}")
                        else:
                            logger.error(f"❌ 推送失败: {home_team} vs {away_team}")
                    
                    # 避免请求过快
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"处理比赛失败 {match_info['home_team']} vs {match_info['away_team']}: {e}", exc_info=True)
            
            logger.info(f"\n✅ 赛前{minutes_before}分钟采集推送完成（{len(matches_to_collect)}场比赛）")
            
        except Exception as e:
            logger.error(f"赛前采集推送失败: {e}", exc_info=True)
    
    def _send_json_data_notification(self, match_info: dict, json_data: dict, minutes_before: int, json_file_path: str = None) -> bool:
        """
        推送采集到的JSON数据（保存文件并推送通知提醒用户来网站保存）
        
        Args:
            match_info: 比赛信息
            json_data: 采集到的完整JSON数据
            minutes_before: 距离开赛分钟数
            json_file_path: JSON文件保存路径（如果已保存）
            
        Returns:
            是否推送成功
        """
        try:
            match_time = match_info['match_time']
            home_team = match_info['home_team']
            away_team = match_info['away_team']
            league = match_info['league']
            
            # 1. 保存JSON文件
            # 生成文件名（去掉年份，格式：月日_时间_联赛_主队_vs_客队.json）
            date_str = match_time.strftime('%m%d')  # 只保留月日
            time_str = match_time.strftime('%H%M')
            safe_home = home_team.replace(' ', '_').replace('/', '_')
            safe_away = away_team.replace(' ', '_').replace('/', '_')
            safe_league = league.replace(' ', '_').replace('/', '_')
            
            # 保存到 data/push_json/ 目录（按年/月/日分类存储）
            push_dir = self.data_dir / "push_json" / match_time.strftime('%Y/%m/%d')
            push_dir.mkdir(parents=True, exist_ok=True)
            
            # 文件名格式：月日_时间_联赛_主队_vs_客队.json
            filename = f"{date_str}_{time_str}_{safe_league}_{safe_home}_vs_{safe_away}.json"
            json_file_path = push_dir / filename
            
            # 写入文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📂 JSON文件已保存: {json_file_path}")
            
            # 2. 获取网站地址（直接跳转到JSON提取页面）
            import os
            server_host = os.environ.get('SERVER_HOST', 'http://127.0.0.1:5001')
            website_url = f"{server_host}/#json"  # 直接跳转到JSON提取页面
            
            # 3. 构造推送消息（只做通知，引导用户到网站保存）
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
            file_size = len(json_str.encode('utf-8'))
            
            # 提取关键摘要信息
            handicap_data = json_data.get('handicap_data', {})
            trade_summary = json_data.get('trade_summary', {})
            
            content = f"### 📊 赛前数据采集完成\n\n"
            content += f"🏆 **{league}** | {match_time.strftime('%H:%M')}\n"
            content += f"⚽ **{home_team} vs {away_team}**\n"
            content += f"<font color=\"comment\">{'─'*20}</font>\n\n"
            
            # 盘口摘要
            if handicap_data:
                h_text = handicap_data.get('current_handicap_text', '') or handicap_data.get('initial_handicap_text', 'N/A')
                h_odds = f"{handicap_data.get('current_home_odds', 'N/A')}/{handicap_data.get('current_away_odds', 'N/A')}"
                content += f"**📈 即时盘口:** {h_text} ({h_odds})\n"
            
            # 交易摘要
            if trade_summary:
                total_vol = trade_summary.get('total_volume', 0)
                row_count = trade_summary.get('row_count', 0)
                content += f"**💰 交易数据:** {total_vol:,} 成交量 / {row_count} 笔\n\n"
            
            # 网站链接提醒
            content += f"<font color=\"comment\">{'─'*20}</font>\n"
            content += f"**📥 请到网站保存JSON：**\n"
            content += f"[👉 点击打开数据工作台]({website_url})\n\n"
            content += f"> 📁 文件: {filename}\n"
            content += f"> 📏 大小: {file_size:,} 字节\n"
            content += f"> ⏰ 距开赛: {minutes_before} 分钟\n"
            content += f"\n<font color=\"warning\">💡 进入网站后，点击【JSON提取】即可预览和下载</font>"
            
            # 发送消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            if self.wecom_notifier:
                return self.wecom_notifier._send_message(message)
            
            return False
            
        except Exception as e:
            logger.error(f"发送JSON数据通知失败: {e}", exc_info=True)
            return False

    def run_scheduler(self):
        """启动定时任务"""
        logger.info("🚀 自动推荐推送系统启动")
        logger.info(f"企业微信推送: {'✅ 已启用' if self.use_wecom else '❌ 未启用'}")
        logger.info(f"Telegram推送: {'✅ 已启用' if self.use_telegram else '❌ 未启用'}")
        logger.info("=" * 60)
        
        # 立即执行一次
        logger.info("执行初始扫描...")
        self.run_once()
        
        # 设置定时任务
        # 根据时间窗口选择扫描频率
        if self.hours_before < 1:
            # 临场模式：每5分钟扫描一次
            schedule.every(5).minutes.do(self.run_once)
            logger.info("⏰ 定时任务已设置:")
            logger.info("  - 🔥 临场模式：每5分钟扫描一次")
            logger.info("  - 确保不错过任何即将开始的比赛")
        else:
            # 常规模式：每小时执行一次
            schedule.every().hour.at(":00").do(self.run_once)
            
            # 每天早上9点、下午3点、晚上9点额外执行
            schedule.every().day.at("09:00").do(self.run_once)
            schedule.every().day.at("15:00").do(self.run_once)
            schedule.every().day.at("21:00").do(self.run_once)
            
            logger.info("⏰ 定时任务已设置:")
            logger.info("  - 每小时整点执行")
            logger.info("  - 每天 09:00、15:00、21:00 额外执行")
        
        logger.info("按 Ctrl+C 停止")
        logger.info("=" * 60)
        
        # 持续运行
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # 每30秒检查一次
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  系统已停止")


def setup_wecom():
    """配置企业微信机器人"""
    print("\n" + "="*60)
    print("📱 企业微信机器人配置")
    print("="*60)
    
    print("\n获取企业微信机器人Webhook URL的步骤：")
    print("1. 打开企业微信PC端或移动端")
    print("2. 进入要接收消息的群聊")
    print("3. 点击右上角 [···] > 群机器人 > 添加机器人")
    print("4. 设置机器人名称和头像")
    print("5. 复制Webhook地址（类似：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx）")
    
    webhook_url = input("\n请输入Webhook URL: ").strip()
    
    if not webhook_url:
        print("❌ 未输入Webhook URL，退出配置")
        return False
    
    # 保存配置
    if WeComNotifier.create_config(webhook_url):
        print("✅ 配置已保存")
    
    # 测试连接
    print("\n测试企业微信连接...")
    notifier = WeComNotifier(webhook_url)
    
    if notifier.send_test_message():
        print("✅ 企业微信配置成功！请检查群组收到测试消息。")
        return True
    else:
        print("❌ 企业微信测试失败，请检查配置")
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("⚽ 足球比赛自动推荐推送系统")
    print("="*60)
    
    # 检查配置
    wecom_config = Path(__file__).parent / "wecom_config.json"
    telegram_config = Path(__file__).parent / "telegram_config.json"
    
    has_wecom = wecom_config.exists()
    has_telegram = telegram_config.exists()
    
    print("\n当前配置状态：")
    print(f"  企业微信: {'✅ 已配置' if has_wecom else '❌ 未配置'}")
    print(f"  Telegram: {'✅ 已配置' if has_telegram else '❌ 未配置'}")
    
    if not has_wecom and not has_telegram:
        print("\n⚠️  未检测到任何推送配置")
        print("\n请选择：")
        print("1. 配置企业微信（推荐）")
        print("2. 配置Telegram")
        print("3. 跳过配置，稍后手动配置")
        
        choice = input("\n请输入选项 (1/2/3): ").strip()
        
        if choice == "1":
            setup_wecom()
            has_wecom = wecom_config.exists()
        elif choice == "2":
            # 调用main_automation.py中的setup_telegram
            from main_automation import setup_telegram
            setup_telegram()
            has_telegram = telegram_config.exists()
    
    # 启动系统
    if not has_wecom and not has_telegram:
        print("\n❌ 没有配置任何推送渠道，无法启动系统")
        print("请先配置企业微信或Telegram推送")
        return
    
    print("\n" + "="*60)
    print("⏰ 推送时间窗口设置")
    print("="*60)
    print("\n系统会在比赛开始前的特定时间窗口内推送推荐")
    
    # 时间窗口配置
    print("\n请选择推送时间窗口：")
    print("1. 🔥 临场推送（开赛前3-10分钟）⚡ 最新盘口")
    print("2. 📊 赛前推送（提前1-3小时）准备充分")
    print("3. 📈 早期推送（提前2-5小时）提前布局")
    print("4. 🎯 自定义时间窗口")
    
    time_choice = input("\n请输入选项 (1/2/3/4，默认1): ").strip() or "1"
    
    if time_choice == "1":
        # 临场推送：开赛前3-10分钟
        hours_before = 0.05  # 3分钟（0.05小时）
        hours_window = 0.12  # 窗口7分钟（总共3-10分钟）
        print("\n🔥 临场推送模式：开赛前3-10分钟推送")
        print("   ⚡ 最新盘口，最准确信息")
    elif time_choice == "2":
        # 赛前推送：提前1-3小时
        hours_before = 1
        hours_window = 2
        print("\n📊 赛前推送模式：提前1-3小时推送")
    elif time_choice == "3":
        # 早期推送：提前2-5小时
        hours_before = 2
        hours_window = 3
        print("\n📈 早期推送模式：提前2-5小时推送")
    elif time_choice == "4":
        try:
            print("\n提示：输入小时数，支持小数（如 0.05 = 3分钟，0.5 = 30分钟）")
            hours_before = float(input("提前多少小时开始推送（如 0.05 表示3分钟）: ").strip())
            hours_window = float(input("时间窗口范围（小时，如 0.12 表示7分钟）: ").strip())
            print(f"\n✅ 自定义窗口：提前{hours_before*60:.0f}-{(hours_before+hours_window)*60:.0f}分钟推送")
        except:
            print("⚠️  输入无效，使用临场推送模式")
            hours_before = 0.05
            hours_window = 0.12
    else:
        hours_before = 0.05
        hours_window = 0.12
    
    if hours_before < 1:
        print(f"   开赛前{hours_before*60:.0f}-{(hours_before+hours_window)*60:.0f}分钟推送")
    
    print("\n" + "="*60)
    print("系统即将启动")
    print("="*60)
    
    # 创建系统实例
    system = AutoRecommendPushSystem(
        use_wecom=has_wecom,
        use_telegram=has_telegram,
        hours_before=hours_before,
        hours_window=hours_window
    )
    
    print("\n选择运行模式：")
    print("1. 定时自动运行（推荐）")
    print("2. 立即执行一次")
    
    mode = input("\n请输入选项 (1/2): ").strip()
    
    if mode == "1":
        system.run_scheduler()
    else:
        system.run_once()
        print("\n执行完成！")


if __name__ == "__main__":
    main()
