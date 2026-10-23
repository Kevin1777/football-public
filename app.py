import sys
import os
import threading  # 🔥 新增：用于后台执行刷新任务
import queue      # 🔥 新增：用于线程间通信
from datetime import datetime

# 🔥 禁用输出缓冲，让终端实时显示所有输出
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# 🔥 版本标识日志
print(f"\n{'='*50}")
print(f"🚀 Football Data Service v2.1.3 (FINAL FIX)")
print(f"🕒 Startup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*50}\n")
sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None

import base64
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# 加载环境变量（支持.env文件）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装python-dotenv，使用系统环境变量

import pandas as pd
from flask import Flask, jsonify, render_template, request, Response, stream_with_context, make_response
from werkzeug.utils import secure_filename

from parser.html_parser import HEADER_KEYWORDS, parse_bifa_html
from parser.pdf_parser import parse_bifa_pdf
from services.bifaw_client import BifawClient
from services.lottery500_client import Lottery500Client
from services.trade_report import generate_trade_report
from recommendation.x1_json_recommender import X1JSONRecommender  # 🔥 X1 JSON推荐引擎（统一引擎）
from recommendation.vis_formatter import VISFormatter  # VIS格式化输出
from rule_based_recommender import HybridRecommender  # 🎯 规则推荐系统
from backtest import BacktestEngine
from backtest.detail_cache_manager import DetailCacheManager
from backtest.progress_manager import ProgressManager
from backtest.auto_recovery_service import AutoRecoveryService
from backtest.log_manager import LogManager
from backtest.data_statistics import DataStatistics
from core.recommendation_tracker import RecommendationTracker
from utils.log_stream_handler import get_stream_handler
from services.cleanup_service import cleanup_service, run_cleanup, get_disk_usage
from services.background_task_manager import background_task_manager, TaskStatus
from services.background_collector import get_background_collector, CollectionStatus
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta

# 🔥 导入自动推送系统
try:
    from core.auto_recommend_push import AutoRecommendPushSystem
    from core.schedule_manager import MatchPushScheduleManager
    AUTO_PUSH_AVAILABLE = True
except ImportError as e:
    logging.warning(f"自动推送系统未加载: {e}")
    AUTO_PUSH_AVAILABLE = False

# 🔥 配置日志输出到控制台 + 文件（记录所有终端信息）
import sys
from logging.handlers import RotatingFileHandler

# 确保logs目录存在
Path("logs").mkdir(exist_ok=True)

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清除现有处理器
root_logger.handlers.clear()

# 1. 控制台处理器（终端输出）
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# 2. 文件处理器（保存所有日志到文件，包括批量回测）
file_handler = RotatingFileHandler(
    'logs/app_full.log',  # 完整日志文件
    maxBytes=50*1024*1024,  # 50MB
    backupCount=5,
    encoding='utf-8'  # 修复编码问题
)
file_handler.setLevel(logging.DEBUG)  # 文件记录DEBUG级别，更详细
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# 3. 批量回测专用日志文件
backtest_handler = RotatingFileHandler(
    'logs/backtest_detail.log',  # 批量回测详细日志
    maxBytes=50*1024*1024,
    backupCount=3,
    encoding='utf-8'
)
backtest_handler.setLevel(logging.DEBUG)
backtest_handler.setFormatter(file_formatter)
# 只给backtest和recommendation模块添加此处理器
logging.getLogger('backtest').addHandler(backtest_handler)
logging.getLogger('recommendation').addHandler(backtest_handler)

logging.info("✅ 日志系统已初始化：控制台 + app_full.log + backtest_detail.log")

# 🔥 配置操作日志（文件输出，48小时轮转）
from utils.operation_logger import get_operation_logger
operation_logger = get_operation_logger(log_dir="logs", app_name="football")

# 🔥 配置告警管理器和健康检查器
from utils.alert_manager import get_alert_manager
from utils.health_checker import HealthChecker
import os

# 企业微信Webhook（硬编码）
WECOM_WEBHOOK_URL = ""

alert_manager = get_alert_manager(
    wecom_webhook=os.getenv('WECOM_ALERT_WEBHOOK') or os.getenv('WECOM_WEBHOOK') or WECOM_WEBHOOK_URL
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {"pdf"}

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# 🔥 禁用模板缓存，确保每次都加载最新模板
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

@app.after_request
def add_no_cache_headers(response):
    """为HTML页面添加禁止缓存的响应头"""
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# 全局采集进度跟踪（用于前端实时查询）
collect_progress = {
    "active": False,
    "total": 0,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "skipped": 0,
    "data_cleared": 0,
    "current_match": "",
    "start_time": None,
    "error_details": [],  # 详细错误列表：[{"match": "比赛名", "reason": "错误原因", "timestamp": "时间"}]
    "match_details": [],  # 🆕 每场比赛详细状态: [{"match": "...", "status": "pending|collecting|success|failed|skipped", "message": "..."}]
    "eta_seconds": 0,     # 🆕 预计剩余时间
    "speed": 0,           # 🆕 采集速度（场/分钟）
}
collect_progress_lock = threading.Lock()

# 🔥 采集任务锁 - 防止多设备并发冲突
collection_lock = threading.Lock()
active_collection_session = None  # 当前正在运行的会话ID

bifaw_client = BifawClient()
# 🔥 使用绝对路径确保盘口数据保存到正确位置
from pathlib import Path
lottery500_client = Lottery500Client(data_dir=str(Path(__file__).parent / "data"))

# 🔥 统一推荐引擎：X1 JSON（准确率83.6%）
x1_json_recommender = X1JSONRecommender()
app.logger.info("✅ X1 JSON推荐引擎已加载（统一引擎 · 准确率83.6%）")

# VIS格式化器
vis_formatter = VISFormatter()

# 🎯 初始化规则推荐系统（比分反推规则库）
try:
    hybrid_recommender = HybridRecommender()
    app.logger.info("✅ 规则推荐系统已加载")
except Exception as e:
    hybrid_recommender = None
    app.logger.warning(f"⚠️ 规则推荐系统加载失败: {e}")

# 🔥 使用绝对路径确保在 Linux 服务器上也能正确读取 data 目录
detail_cache_manager = DetailCacheManager(cache_dir=str(BASE_DIR / "data"))
progress_manager = ProgressManager()
# 🔥 回测引擎使用 X1 JSON（通过兼容接口）
backtest_engine = BacktestEngine(x1_json_recommender, lottery500_client, bifaw_client, detail_cache_manager)

# 🔥 日志管理器 - 持久化采集日志，支持多设备查看# 初始化日志管理器
log_manager = LogManager(log_dir=str(BASE_DIR / "logs"), max_messages=500)

# 🔥 后台采集器 - 支持关闭网页后继续采集，自动恢复登录
background_collector = get_background_collector(
    bifaw_client=bifaw_client,
    lottery500_client=lottery500_client,
    detail_cache_manager=detail_cache_manager,
    log_manager=log_manager
)
app.logger.info("✅ 后台采集器已初始化（支持关闭网页后继续采集）")

# 🔥 自定义 LogHandler，将 Python logging 转发到 LogManager
class LogManagerHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # 映射日志级别
            msg_type = 'info'
            if record.levelno >= logging.ERROR:
                msg_type = 'error'
            elif record.levelno >= logging.WARNING:
                msg_type = 'warning'
            
            # 添加到 LogManager
            log_manager.add_message({
                'type': msg_type,
                'message': msg,
                'timestamp': datetime.fromtimestamp(record.created).isoformat()
            })
            # print(f"DEBUG: Log captured: {msg}")  # 调试用
        except Exception as e:
            print(f"LogManagerHandler Error: {e}")
            self.handleError(record)

# 🔥 将 LogManagerHandler 添加到关键服务的 logger
# 这样 services.bifaw_client 的日志就会出现在前端实时日志中
bifaw_logger = logging.getLogger("services.bifaw_client")
bifaw_handler = LogManagerHandler()
bifaw_handler.setFormatter(logging.Formatter('%(message)s'))  # 只显示消息内容，不重复时间戳
bifaw_logger.addHandler(bifaw_handler)
bifaw_logger.setLevel(logging.INFO)

# 也可以添加到其他关键 logger
scheduler_logger = logging.getLogger("apscheduler")
scheduler_logger.addHandler(bifaw_handler)

# 🔥 启动时自动开始一个专用session，彻底避免加载旧的会话历史
startup_session_id = f"system_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
log_manager.start_session(startup_session_id)
# start_session 已经会添加 session_start 消息，这里额外添加一条启动标记
log_manager.add_message({
    'type': 'info',
    'message': '🚀 Flask应用已启动，实时日志系统运行中',
})

# 📊 数据统计器 - 统计采集数据的日期、数量、大小
data_statistics = DataStatistics(data_dir=str(BASE_DIR / "data"))

# 🎯 推荐记录追踪器 - 记录推荐结果并定时审查准确率
recommendation_tracker = RecommendationTracker(
    db_path=str(BASE_DIR / "data" / "databases" / "recommendation_tracker.db")
)

# 🔥 自动恢复服务初始化（将在后面定义回调函数后启动）
auto_recovery_service = None

# 🔥 自动推送系统初始化（延迟到定时任务中启动）
auto_push_system = None
if AUTO_PUSH_AVAILABLE:
    try:
        # 🔥 初始化推送系统（临场推送模式：提前5分钟推送）
        auto_push_system = AutoRecommendPushSystem(
            use_wecom=True,      # 使用企业微信
            use_telegram=False,  # 可选：使用Telegram
            hours_before=5/60,   # 提前5分钟开始推送 (5分钟 = 5/60小时)
            hours_window=15/60   # 时间窗口15分钟（即提前5-20分钟内的比赛都推送）
        )
        app.logger.info("✅ 自动推送系统已初始化")
        
        # 🔥 初始化调度管理器
        schedule_manager = None  # 稍后在scheduler创建后初始化
        
    except Exception as e:
        app.logger.warning(f"自动推送系统初始化失败: {e}")
        auto_push_system = None
        schedule_manager = None

# 🔥 辅助函数：增强盘口数据（补充初盘和即时盘口）
def enhance_handicap_with_initial_data(handicap_data, lottery500_client, app_logger=None):
    """
    增强盘口数据：补充初盘和即时盘口的详细信息
    
    Args:
        handicap_data: 从find_handicap_from_daily_data获取的基础盘口数据
        lottery500_client: Lottery500Client实例
        app_logger: 日志记录器
    
    Returns:
        增强后的盘口数据（包含初盘、即时盘口、变化趋势等）
    """
    if not handicap_data or not handicap_data.get('fid'):
        return handicap_data
    
    fid = handicap_data['fid']
    
    try:
        if app_logger:
            app_logger.info(f"  📊 获取详细盘口数据（初盘+即时盘口）: fid={fid}")
        
        # 调用fetch_handicap_data获取详细数据
        detailed_handicap = lottery500_client.fetch_handicap_data(
            fid=fid,
            company_id="澳门"  # 使用名称匹配，更稳定（ID可能变化）
        )
        
        if detailed_handicap:
            # 合并详细数据
            handicap_data.update(detailed_handicap)
            
            # 计算盘口变化
            initial = detailed_handicap.get('initial_handicap', 0)
            current = detailed_handicap.get('current_handicap', 0)
            handicap_change = current - initial
            
            handicap_data['handicap_change'] = handicap_change
            
            # 判断变化趋势
            if handicap_change < -0.01:  # 容错小数精度
                handicap_data['handicap_trend'] = '升盘'
            elif handicap_change > 0.01:
                handicap_data['handicap_trend'] = '降盘'
            else:
                handicap_data['handicap_trend'] = '稳盘'
            
            # 计算水位变化
            handicap_data['odds_change'] = {
                'home': detailed_handicap.get('current_home_odds', 0) - detailed_handicap.get('initial_home_odds', 0),
                'away': detailed_handicap.get('current_away_odds', 0) - detailed_handicap.get('initial_away_odds', 0),
            }
            
            if app_logger:
                app_logger.info(f"  ✅ 初盘: {detailed_handicap.get('initial_handicap_text')} ({detailed_handicap.get('initial_home_odds')}/{detailed_handicap.get('initial_away_odds')})")
                app_logger.info(f"  ✅ 即时: {detailed_handicap.get('current_handicap_text')} ({detailed_handicap.get('current_home_odds')}/{detailed_handicap.get('current_away_odds')})")
                app_logger.info(f"  ✅ 变化: {handicap_data['handicap_trend']} ({handicap_change:+.2f})")
        else:
            if app_logger:
                app_logger.warning(f"  ⚠️  未能获取详细盘口数据")
    
    except Exception as e:
        if app_logger:
            app_logger.warning(f"  ⚠️  获取详细盘口数据失败: {e}")
    
    return handicap_data

# 全局限流器（防止429错误）
_handicap_api_lock = threading.Lock()
_handicap_api_last_request_time = 0
_HANDICAP_API_INTERVAL = 0.6  # 600ms间隔

# 🔥 定时任务：每天自动采集昨天的完场比赛
def auto_collect_yesterday_matches():
    """
    定时任务：每天凌晨3点自动采集昨天的完场比赛
    """
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"🤖 定时任务启动：自动采集 {yesterday} 的完场比赛")
        app.logger.info(f"{'='*80}\n")
        
        # 1. 获取昨天的完场比赛
        target_date = datetime.strptime(yesterday, "%Y-%m-%d")
        # 🔧 修复：fetch_finished_matches 返回元组 (page_html, matches, metadata)
        page_html, matches, metadata = bifaw_client.fetch_finished_matches(target_date=target_date, rows=9999)
        
        if not matches:
            app.logger.info(f"⚠️  {yesterday} 无完场比赛数据")
            return
        
        app.logger.info(f"📋 必发网返回: {len(matches)} 场比赛")
        
        # 2. 获取盘口并匹配
        daily_handicaps = lottery500_client.fetch_daily_handicaps(yesterday, use_cache=False)
        app.logger.info(f"🎯 500.com找到 {len(daily_handicaps)} 场有盘口的比赛")
        
        # 构建匹配索引
        bifaw_match_map = {}
        for match in matches:
            home = match.get('home_team', '') or match.get('home', '')
            away = match.get('away_team', '') or match.get('away', '')
            time = match.get('match_time', '') or match.get('kickoff', '')
            
            home_clean = lottery500_client._clean_team_name(home)
            away_clean = lottery500_client._clean_team_name(away)
            
            if ' ' in time:
                time_str = time.split(' ')[1][:5]
            else:
                time_str = time[:5] if time else ''
            
            key1 = f"{home_clean}_{away_clean}_{time_str}"
            key2 = f"{home}_{away}_{time_str}"
            bifaw_match_map[key1] = match
            bifaw_match_map[key2] = match
        
        # 匹配盘口
        matched_matches = []
        for match_key, handicap_data in daily_handicaps.items():
            home_500 = handicap_data['home_team']
            away_500 = handicap_data['away_team']
            time_500 = handicap_data['time'][:5]
            
            home_clean = lottery500_client._clean_team_name(home_500)
            away_clean = lottery500_client._clean_team_name(away_500)
            
            bifaw_match = None
            for key in [
                f"{home_clean}_{away_clean}_{time_500}",
                f"{home_500}_{away_500}_{time_500}",
            ]:
                if key in bifaw_match_map:
                    bifaw_match = bifaw_match_map[key]
                    break
            
            if bifaw_match:
                merged_match = bifaw_match.copy()
                merged_match['handicap_preview'] = {
                    'handicap_str': handicap_data['current_handicap_str'],
                    'handicap': handicap_data['current_handicap'],
                    'fid': handicap_data['fid']
                }
                matched_matches.append(merged_match)
        
        app.logger.info(f"✅ 匹配成功: {len(matched_matches)} 场（既有盘口又有明细）")
        
        if len(matched_matches) == 0:
            app.logger.info(f"⚠️  {yesterday} 无符合条件的比赛")
            return
        
        # 3. 逐场采集明细
        collected = 0
        failed = 0
        skipped = 0
        
        for idx, match in enumerate(matched_matches, 1):
            match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
            
            # 检查是否已有缓存
            if detail_cache_manager.has_cache(match):
                skipped += 1
                app.logger.info(f"  [{idx}/{len(matched_matches)}] ⏭️  跳过（已有缓存）: {match_label}")
                continue
            
            app.logger.info(f"  [{idx}/{len(matched_matches)}] 📡 采集: {match_label}")
            
            # 获取明细（带重试）
            for retry in range(2):
                try:
                    detail_url = match.get('detail_url')
                    if not detail_url:
                        failed += 1
                        break
                    
                    detail_html = bifaw_client.fetch_match_detail_selenium(
                        detail_url=detail_url,
                        match=match,
                        detail_params=match.get('detail_params')
                    )
                    
                    if not detail_html:
                        if retry < 1:
                            time_module.sleep(2)
                            continue
                        failed += 1
                        break
                    
                    parsed_data = parse_bifa_html(detail_html)
                    
                    if isinstance(parsed_data, str) or parsed_data.empty:
                        if retry < 1:
                            time_module.sleep(2)
                            continue
                        failed += 1
                        break
                    
                    handicap_data = None
                    if match.get('handicap_preview'):
                        handicap_data = {
                            'fid': match['handicap_preview']['fid'],
                            'current_handicap_str': match['handicap_preview']['handicap_str'],
                            'current_handicap': match['handicap_preview']['handicap']
                        }
                        # 🔥 增强盘口数据（补充初盘和即时盘的详细信息）
                        handicap_data = enhance_handicap_with_initial_data(handicap_data, lottery500_client, app.logger)
                    
                    metadata = parsed_data.attrs.get("metadata", [])
                    success = detail_cache_manager.save_detail(
                        match_info=match,
                        trade_data=parsed_data,
                        handicap_data=handicap_data,
                        metadata=metadata,
                        html_content=detail_html  # 保存HTML到data文件夹
                    )
                    
                    if success:
                        collected += 1
                        app.logger.info(f"    ✅ 成功: {len(parsed_data)} 行")
                        break
                    else:
                        if retry < 1:
                            time_module.sleep(2)
                            continue
                        failed += 1
                        break
                except Exception as e:
                    if retry < 1:
                        app.logger.warning(f"    ⚠️  采集异常，准备重试: {str(e)}")
                        time_module.sleep(2)
                    else:
                        app.logger.error(f"    ❌ 采集失败: {str(e)}")
                        failed += 1
                    break
            
            time_module.sleep(1)
        
        app.logger.info(f"\n✅ {yesterday} 定时采集完成")
        app.logger.info(f"  总比赛: {len(matched_matches)} 场")
        app.logger.info(f"  成功: {collected} 场")
        app.logger.info(f"  失败: {failed} 场")
        app.logger.info(f"  跳过: {skipped} 场")
        app.logger.info(f"{'='*80}\n")
        
    except Exception as e:
        app.logger.error(f"❌ 定时任务执行失败: {type(e).__name__}: {str(e)}")

# 🤖 自动保持登录状态（定时任务）
def auto_collect_today_matches():
    """
    🆕 后台定时任务：自动采集今天的比赛（包括未开始的）
    每天早上8点执行一次
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"🔄 [定时任务] 开始采集今日比赛: {today}")
        app.logger.info(f"{'='*80}\n")
        
        # 1. 获取今日比赛列表
        matches = bifaw_client.fetch_match_list_v2(rows=100, days=1, force_refresh=True)
        
        if not matches:
            app.logger.warning(f"⚠️ 未获取到今日比赛列表")
            return
        
        app.logger.info(f"📋 获取到 {len(matches)} 场今日比赛")
        
        # 2. 批量获取盘口数据
        try:
            daily_handicaps = lottery500_client.fetch_daily_handicaps(today, use_cache=False)
            if daily_handicaps:
                lottery500_client.save_daily_handicap_json(today, daily_handicaps)
                app.logger.info(f"✅ 已保存今日盘口数据: {len(daily_handicaps)} 场")
        except Exception as e:
            app.logger.error(f"⚠️ 获取盘口数据失败: {e}")
        
        # 3. 采集交易明细
        collected = 0
        skipped = 0
        failed = 0
        
        for i, match in enumerate(matches, 1):
            try:
                league = match.get('league', '')
                home = match.get('home', match.get('home_team', ''))
                away = match.get('away', match.get('away_team', ''))
                match_time = match.get('datetime', match.get('match_time', ''))
                score = match.get('score', '')
                
                # 检查缓存
                match_info = {
                    'league': league,
                    'home': home,
                    'away': away,
                    'kickoff': match_time,
                    'match_time': match_time,
                    'datetime': match_time,
                    'score': score
                }
                
                if detail_cache_manager.has_cache(match_info):
                    skipped += 1
                    continue
                
                app.logger.info(f"  [{i}/{len(matches)}] {league} | {home} vs {away}")
                
                # 获取交易明细
                trade_data = bifaw_client.get_trade_detail(
                    home_team=home,
                    away_team=away,
                    match_time=match_time,
                    league=league
                )
                
                if trade_data is not None and not trade_data.empty:
                    # 保存到缓存
                    html_content = getattr(trade_data, 'attrs', {}).get('html_content', '')
                    metadata = getattr(trade_data, 'attrs', {}).get('metadata', [])
                    
                    detail_cache_manager.save_detail(
                        match_info=match_info,
                        trade_data=trade_data,
                        handicap_data={},
                        metadata=metadata,
                        html_content=html_content
                    )
                    
                    collected += 1
                    app.logger.info(f"    ✅ 采集成功 ({len(trade_data)}行)")
                else:
                    failed += 1
                    app.logger.warning(f"    ⚠️ 未获取到数据")
                
                time_module.sleep(1)
                
            except Exception as e:
                app.logger.error(f"    ❌ 采集失败: {e}")
                failed += 1
                time_module.sleep(1)
        
        app.logger.info(f"\n✅ {today} 今日采集完成")
        app.logger.info(f"  总比赛: {len(matches)} 场")
        app.logger.info(f"  成功: {collected} 场")
        app.logger.info(f"  失败: {failed} 场")
        app.logger.info(f"  跳过: {skipped} 场")
        app.logger.info(f"{'='*80}\n")
        
        # 🚨 如果失败率过高，发送告警
        if len(matches) > 0 and failed / len(matches) > 0.5:
            alert_manager.alert_data_collection_failed(
                f"今日采集失败率过高: {failed}/{len(matches)} ({failed/len(matches)*100:.1f}%)"
            )
        
    except Exception as e:
        app.logger.error(f"❌ 今日采集任务执行失败: {type(e).__name__}: {str(e)}")
        # 🚨 发送告警
        alert_manager.alert_data_collection_failed(str(e))

def auto_keep_login():
    """
    后台定时任务：检查登录状态，如果未登录则自动重新登录
    每10分钟检查一次
    
    🔥 智能冷却期机制：
    - 手动登录后60分钟内不自动登录
    - 自动登录后15分钟内不重复登录
    - 这样可以避免在用户手动登录后立刻触发OCR自动登录覆盖session
    """
    try:
        # 🔥 检查登录冷却期：智能判断（手动60分钟，自动15分钟）
        if bifaw_client.is_login_recently():
            # 日志已经在 is_login_recently 中输出，这里不再重复
            return
        
        app.logger.info("🔄 [定时任务] 检查登录状态...")
        
        # 🔥 多重检测：避免误判
        login_valid = False
        try:
            # 检查1: 获取简单数据
            cookie_status = bifaw_client.get_cookie_status()
            if cookie_status and cookie_status.get('status') == 'online':
                # 检查2: 尝试获取场次列表
                matches = bifaw_client.fetch_match_list_v2(rows=1, days=1, force_refresh=False)
                if matches:
                    login_valid = True
                    app.logger.info("✅ [定时任务] 登录状态正常")
                    return
        except Exception as e:
            app.logger.warning(f"⚠️ [定时任务] 检测到登录可能失效: {e}")
        
        # 登录已失效，且不在冷却期内，尝试自动重新登录
        app.logger.info("🤖 [定时任务] 开始自动重新登录（OCR识别验证码）...")
        success, message = bifaw_client._auto_login_with_ocr(max_retries=5)
        
        if success:
            app.logger.info("✅ [定时任务] 自动重新登录成功！")
        else:
            app.logger.error(f"❌ [定时任务] 自动重新登录失败: {message}")
            # 🚨 发送告警
            alert_manager.alert_login_failed(message)
    
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 保持登录任务执行失败: {type(e).__name__}: {str(e)}")
        # 🚨 发送告警
        alert_manager.alert_login_failed(str(e))

def auto_recommend_and_push():
    """
    后台定时任务：自动分析比赛并推送推荐
    每10分钟执行一次，扫描即将开始的比赛（临场模式）
    """
    if not auto_push_system:
        app.logger.warning("⚠️ [定时任务] 自动推送系统未初始化，跳过")
        return
    
    try:
        app.logger.info("🔔 [定时任务] 开始扫描并推送比赛推荐...")
        auto_push_system.run_once()
        app.logger.info("✅ [定时任务] 推送扫描完成")
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 自动推送任务执行失败: {type(e).__name__}: {str(e)}")

def hourly_broadcast():
    """
    后台定时任务：整点播报（提前1分钟）
    每小时59分执行，播报下一小时内的所有比赛
    例如：20:59播报21:00~22:00的比赛
    """
    if not auto_push_system:
        app.logger.warning("⚠️ [定时任务] 自动推送系统未初始化，跳过整点播报")
        return
    
    try:
        app.logger.info("📢 [定时任务] 开始整点播报（提前1分钟）...")
        auto_push_system.hourly_broadcast()
        app.logger.info("✅ [定时任务] 整点播报完成")
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 整点播报执行失败: {type(e).__name__}: {str(e)}")


def pre_match_recommendation():
    """
    后台定时任务：赛前5分钟推荐推送
    每5分钟执行一次，检查是否有5分钟后开始的比赛，并推送推荐方向
    """
    if not auto_push_system:
        app.logger.warning("⚠️ [定时任务] 自动推送系统未初始化，跳过赛前推荐推送")
        return
    
    try:
        app.logger.info("🔔 [定时任务] 开始检查赛前5分钟推荐...")
        auto_push_system.push_pre_match_recommendations(minutes_before=5)
        app.logger.info("✅ [定时任务] 赛前推荐推送完成")
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 赛前推荐推送执行失败: {type(e).__name__}: {str(e)}")


# 🔥 初始化定时任务调度器
scheduler = BackgroundScheduler()

# 🔥 初始化调度管理器（在scheduler创建后）
if AUTO_PUSH_AVAILABLE and auto_push_system:
    try:
        schedule_manager = MatchPushScheduleManager(
            scheduler=scheduler,
            auto_push_system=auto_push_system,
            data_dir=BASE_DIR / 'data'
        )
        app.logger.info("✅ 推送调度管理器已初始化")
    except Exception as e:
        app.logger.warning(f"推送调度管理器初始化失败: {e}")
        schedule_manager = None
else:
    schedule_manager = None

# 🔥 初始化健康检查器
health_checker = HealthChecker(
    data_dir=BASE_DIR / 'data',
    log_dir=BASE_DIR / 'logs'
)

def system_health_check():
    """系统健康检查定时任务"""
    try:
        app.logger.info("🏥 [定时任务] 开始系统健康检查...")
        
        result = health_checker.run_full_check(
            scheduler=scheduler,
            auto_push_system=auto_push_system
        )
        
        # 如果发现问题，发送告警
        if not result['all_passed']:
            for issue in result['issues']:
                if issue['level'] == 'error':
                    alert_manager.alert_system_error(
                        component=issue['component'],
                        error_msg=issue['message']
                    )
                elif issue['level'] == 'warning':
                    # 警告级别的只记录日志，不发送告警（避免过度告警）
                    app.logger.warning(f"⚠️ [{issue['component']}] {issue['message']}")
        
        app.logger.info(f"✅ [定时任务] 健康检查完成: {result['passed_checks']}/{result['total_checks']} 项通过")
        
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 健康检查失败: {e}")


def auto_review_yesterday():
    """每日10点自动审查昨天的推荐"""
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        app.logger.info(f"🔍 [定时任务] 开始审查 {yesterday} 的推荐...")
        
        result = recommendation_tracker.review_date(yesterday)
        
        app.logger.info(f"✅ [定时任务] 审查完成: {result.get('reviewed', 0)}/{result.get('total', 0)}")
        app.logger.info(f"   准确率: {result.get('accuracy', 0):.1f}%")
        
    except Exception as e:
        app.logger.exception("自动审查推荐失败")


# 🆕 每天早上8点执行：自动采集今天的比赛（包括未开始的）
scheduler.add_job(
    func=auto_collect_today_matches,
    trigger=CronTrigger(hour=8, minute=0),
    id='auto_collect_today',
    name='自动采集今天的比赛',
    replace_existing=True
)

# 🔥 每天早上10点执行：扫描今日比赛并创建推送任务
# 🔥 暂停 schedule_manager 的调度（避免重复推送JSON和赛前报告）
# 只保留简单的JSON推送机制
# if schedule_manager:
#     def scan_and_schedule_matches():
#         """扫描今日比赛并创建推送任务"""
#         try:
#             app.logger.info("📅 [定时任务] 开始扫描并调度今日比赛推送...")
#             schedule_manager.scan_and_schedule_today_matches()
#             app.logger.info("✅ [定时任务] 调度完成")
#         except Exception as e:
#             app.logger.error(f"❌ [定时任务] 调度失败: {e}", exc_info=True)
#     
#     scheduler.add_job(
#         func=scan_and_schedule_matches,
#         trigger=CronTrigger(hour=10, minute=0),
#         id='scan_and_schedule_matches',
#         name='扫描并调度今日比赛推送',
#         replace_existing=True
#     )
#     
#     # 服务启动时也执行一次
#     scheduler.add_job(
#         func=scan_and_schedule_matches,
#         trigger='date',
#         run_date=datetime.now() + timedelta(seconds=10),  # 启动10秒后执行
#         id='scan_and_schedule_matches_startup',
#         name='启动时扫描比赛'
#     )

# 每天凌晨3点执行：自动采集昨天的完场比赛
scheduler.add_job(
    func=auto_collect_yesterday_matches,
    trigger=CronTrigger(hour=3, minute=0),
    id='auto_collect_yesterday',
    name='自动采集昨天的完场比赛',
    replace_existing=True
)

# 🤖 每10分钟执行：自动保持登录状态（降低频率，减少干扰）
scheduler.add_job(
    func=auto_keep_login,
    trigger='interval',
    minutes=10,  # 🔥 从5分钟改为10分钟
    id='auto_keep_login',
    name='自动保持登录状态',
    replace_existing=True,
    next_run_time=datetime.now() + timedelta(minutes=10)  # 首次执行在10分钟后
)

# 🔔 每10分钟执行：自动推送比赛推荐（临场模式）
# 🔥 如果启用了 schedule_manager，则由它负责精确调度，不需要这个轮询任务
if auto_push_system and not schedule_manager:
    scheduler.add_job(
        func=auto_recommend_and_push,
        trigger='interval',
        minutes=10,  # 每10分钟检查一次
        id='auto_recommend_push',
        name='自动推荐推送',
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=10)
    )

if auto_push_system:
    # 📢 每小时59分执行：整点播报（提前1分钟）
    # 🔥 暂停整点播报功能
    # scheduler.add_job(
    #     func=hourly_broadcast,
    #     trigger=CronTrigger(minute=59),  # 每小时的第59分钟执行（提前1分钟播报下一小时）
    #     id='hourly_broadcast',
    #     name='整点播报（提前1分钟）',
    #     replace_existing=True
    # )
    pass
    
    # 🔔 每5分钟执行：赛前5分钟推荐推送
    # 🔥 如果启用了 schedule_manager，则由它负责精确调度，不需要这个轮询任务
    if not schedule_manager:
        scheduler.add_job(
            func=pre_match_recommendation,
            trigger='interval',
            minutes=5,  # 每5分钟检查一次
            id='pre_match_recommendation',
            name='赛前5分钟推荐推送',
            replace_existing=True,
            next_run_time=datetime.now()  # 🔥 首次执行立即进行，避免错过比赛
        )

# 🏥 每小时执行：系统健康检查
scheduler.add_job(
    func=system_health_check,
    trigger='interval',
    hours=1,
    id='system_health_check',
    name='系统健康检查',
    replace_existing=True,
    next_run_time=datetime.now() + timedelta(minutes=5)  # 首次在启动5分钟后执行
)

# 📥 精确定时推送：根据可用场次创建定时任务
# 存储已创建的定时任务ID
scheduled_match_jobs = {}

# 🔥 推送状态记录（用于检查和补推送）
# push_status[match_id] = {'status': 'pending/success/failed', 'push_time': datetime, 'attempts': int}
push_status_records = {}

def schedule_match_push(match_info: dict):
    """为单场比赛创建精确的定时推送任务"""
    try:
        match_time = match_info.get('match_time')
        if isinstance(match_time, str):
            match_time = datetime.strptime(match_time, '%Y-%m-%d %H:%M')
        
        home_team = match_info.get('home_team', match_info.get('home', ''))
        away_team = match_info.get('away_team', match_info.get('away', ''))
        league = match_info.get('league', '未知')
        
        # 计算推送时间：赛前15分钟
        push_time = match_time - timedelta(minutes=15)
        
        # 如果推送时间已过
        now = datetime.now()
        if push_time <= now:
            # 如果比赛还没开始，立即推送（补推送）
            if now < match_time:
                app.logger.warning(f"⚠️ 推送时间已过但比赛未开始，立即推送: {home_team} vs {away_team}")
                # 设置为1秒后立即执行
                push_time = now + timedelta(seconds=1)
            else:
                app.logger.info(f"⏭️ 跳过已开赛: {home_team} vs {away_team}")
                return False
        
        # 生成唯一任务ID
        job_id = f"match_push_{match_time.strftime('%Y%m%d%H%M')}_{home_team}_{away_team}"
        
        # 检查是否已创建
        if job_id in scheduled_match_jobs:
            app.logger.debug(f"任务已存在: {job_id}")
            return False
        
        # 保存比赛信息到闭包
        _match_info = match_info.copy()
        _match_time = match_time
        _home_team = home_team
        _away_team = away_team
        _league = league
        _job_id = job_id
        
        # 创建定时任务
        def push_this_match():
            try:
                app.logger.info("=" * 50)
                app.logger.info(f"⏰ [精确推送] 触发: {_home_team} vs {_away_team}")
                app.logger.info(f"   开赛时间: {_match_time.strftime('%Y-%m-%d %H:%M')}")
                app.logger.info("=" * 50)
                
                if not auto_push_system:
                    app.logger.error("❌ auto_push_system 未初始化")
                    return
                
                # 直接采集这场比赛并推送
                import json
                
                # 1. 尝试自动采集
                app.logger.info(f"📥 开始采集: {_home_team} vs {_away_team}")
                app.logger.info(f"   detail_url: {_match_info.get('detail_url', 'N/A')[:50]}...")
                
                # 使用原始比赛数据（包含detail_url和detail_params）
                raw_match_data = _match_info.get('raw_match_data', _match_info)
                match_file = auto_push_system._auto_collect_match(_match_info, raw_match_data)
                
                if not match_file:
                    app.logger.error(f"❌ 采集失败: {_home_team} vs {_away_team}")
                    return
                
                app.logger.info(f"✅ 采集完成: {match_file}")
                
                # 2. 读取采集的JSON数据
                try:
                    with open(match_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                except Exception as e:
                    app.logger.error(f"❌ 读取JSON失败: {e}")
                    return
                
                # 🔥 添加标盘中的市场盘口数据
                if raw_match_data.get('handicap_preview'):
                    json_data['market_handicap'] = raw_match_data.get('handicap_preview')
                    app.logger.info(f"   添加市场盘口: {raw_match_data.get('handicap_preview')}")
                
                # 3. 推送通知
                app.logger.info(f"📤 开始推送通知...")
                
                push_match_info = {
                    'match_time': _match_time,
                    'home_team': _home_team,
                    'away_team': _away_team,
                    'league': _league
                }
                
                success = auto_push_system._send_json_data_notification(
                    match_info=push_match_info,
                    json_data=json_data,
                    minutes_before=15
                )
                
                # 🔥 记录推送状态
                if success:
                    app.logger.info(f"✅ 推送成功: {_home_team} vs {_away_team}")
                    push_status_records[_job_id] = {
                        'status': 'success',
                        'match_time': _match_time,
                        'push_time': datetime.now(),
                        'home_team': _home_team,
                        'away_team': _away_team,
                        'attempts': 1
                    }
                else:
                    app.logger.error(f"❌ 推送失败: {_home_team} vs {_away_team}")
                    push_status_records[_job_id] = {
                        'status': 'failed',
                        'match_time': _match_time,
                        'push_time': datetime.now(),
                        'home_team': _home_team,
                        'away_team': _away_team,
                        'match_info': _match_info,
                        'attempts': 1
                    }
                
                # 任务执行后从记录中移除
                scheduled_match_jobs.pop(_job_id, None)
                
            except Exception as e:
                app.logger.error(f"❌ 精确推送失败: {_home_team} vs {_away_team}: {e}", exc_info=True)
                # 记录失败状态
                push_status_records[_job_id] = {
                    'status': 'error',
                    'match_time': _match_time,
                    'push_time': datetime.now(),
                    'home_team': _home_team,
                    'away_team': _away_team,
                    'match_info': _match_info,
                    'error': str(e),
                    'attempts': 1
                }
        
        scheduler.add_job(
            func=push_this_match,
            trigger='date',
            run_date=push_time,
            id=job_id,
            name=f'赛前推送: {home_team} vs {away_team}',
            replace_existing=True
        )
        
        scheduled_match_jobs[job_id] = {
            'match_time': match_time,
            'push_time': push_time,
            'home_team': home_team,
            'away_team': away_team
        }
        
        app.logger.info(f"✅ 已创建定时任务: {home_team} vs {away_team} @ {push_time.strftime('%H:%M')} (开赛 {match_time.strftime('%H:%M')})")
        return True
        
    except Exception as e:
        app.logger.error(f"创建定时任务失败: {e}", exc_info=True)
        return False

def refresh_match_schedules():
    """刷新比赛定时任务：读取可用场次，为每场比赛创建精确的定时任务"""
    try:
        from pathlib import Path
        import json
        
        app.logger.info("=" * 50)
        app.logger.info(f"🔄 刷新比赛定时任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        app.logger.info("=" * 50)
        
        # 读取今天和明天的标盘数据
        data_dir = Path(__file__).parent / "data"
        now = datetime.now()
        dates_to_check = [
            now.strftime('%Y/%m/%d'),
            (now + timedelta(days=1)).strftime('%Y/%m/%d')
        ]
        
        new_jobs_count = 0
        
        for date_str in dates_to_check:
            year, month, day = date_str.split('/')
            biaopan_file = data_dir / year / month / day / "标盘指数_latest.json"
            
            if biaopan_file.exists():
                try:
                    with open(biaopan_file, 'r', encoding='utf-8') as f:
                        biaopan_data = json.load(f)
                    
                    for match in biaopan_data.get('matches', []):
                        kickoff_str = match.get('kickoff', '')
                        if not kickoff_str:
                            continue
                        
                        try:
                            match_time = datetime.strptime(kickoff_str, '%Y-%m-%d %H:%M')
                        except:
                            continue
                        
                        # 只处理未来24小时内的比赛
                        if match_time <= now or match_time > now + timedelta(hours=24):
                            continue
                        
                        # 必须有detail_url才能采集
                        if not match.get('detail_url'):
                            continue
                        
                        match_info = {
                            'match_time': match_time,
                            'home_team': match.get('home', ''),
                            'away_team': match.get('away', ''),
                            'league': match.get('league', '未知'),
                            'detail_url': match.get('detail_url'),
                            'detail_params': match.get('detail_params'),  # 采集需要
                            'raw_match_data': match  # 保存完整原始数据
                        }
                        
                        if schedule_match_push(match_info):
                            new_jobs_count += 1
                            
                except Exception as e:
                    app.logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
        
        app.logger.info(f"✅ 刷新完成: 新增 {new_jobs_count} 个定时任务，当前共 {len(scheduled_match_jobs)} 个")
        
        # 列出所有待执行的任务
        if scheduled_match_jobs:
            app.logger.info("📋 待执行的推送任务:")
            for job_id, info in sorted(scheduled_match_jobs.items(), key=lambda x: x[1]['push_time']):
                app.logger.info(f"   ⏰ {info['push_time'].strftime('%H:%M')} - {info['home_team']} vs {info['away_team']}")
        
    except Exception as e:
        app.logger.error(f"刷新比赛定时任务失败: {e}", exc_info=True)

# 每10分钟刷新一次比赛定时任务（赛前15分钟推送JSON）
scheduler.add_job(
    func=refresh_match_schedules,
    trigger='interval',
    minutes=10,
    id='refresh_match_schedules',
    name='刷新比赛定时任务',
    replace_existing=True,
    next_run_time=datetime.now() + timedelta(seconds=10)  # 启动10秒后首次执行
)
app.logger.info("✅ 注册定时任务: 刷新比赛定时任务（每10分钟执行）")

# API: 手动刷新比赛定时任务
@app.route("/api/push/refresh_schedules", methods=["POST"])
def api_refresh_match_schedules():
    """手动刷新比赛定时任务"""
    try:
        refresh_match_schedules()
        return jsonify({
            "success": True,
            "message": f"刷新完成，当前共 {len(scheduled_match_jobs)} 个待执行任务",
            "scheduled_jobs": [
                {
                    "home_team": info['home_team'],
                    "away_team": info['away_team'],
                    "match_time": info['match_time'].strftime('%Y-%m-%d %H:%M'),
                    "push_time": info['push_time'].strftime('%Y-%m-%d %H:%M')
                }
                for info in sorted(scheduled_match_jobs.values(), key=lambda x: x['push_time'])
            ]
        })
    except Exception as e:
        app.logger.exception("手动刷新比赛定时任务失败")
        return jsonify({"success": False, "error": str(e)}), 500

# 🔥 补推送检查任务
def check_and_retry_failed_pushes():
    """检查失败的推送并进行补推送，同时检测遗漏的推送"""
    try:
        from pathlib import Path
        import json
        
        now = datetime.now()
        app.logger.info("=" * 50)
        app.logger.info(f"🔍 检查推送状态 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        app.logger.info("=" * 50)
        
        retry_count = 0
        missed_count = 0
        
        # 🔥 第一步：检测遗漏的推送（应该推送但没有推送的比赛）
        app.logger.info("📋 检测遗漏的推送...")
        
        data_dir = Path(__file__).parent / "data"
        dates_to_check = [
            now.strftime('%Y/%m/%d'),
            (now + timedelta(days=1)).strftime('%Y/%m/%d')
        ]
        
        for date_str in dates_to_check:
            year, month, day = date_str.split('/')
            biaopan_file = data_dir / year / month / day / "标盘指数_latest.json"
            
            if not biaopan_file.exists():
                continue
            
            try:
                with open(biaopan_file, 'r', encoding='utf-8') as f:
                    biaopan_data = json.load(f)
                
                for match in biaopan_data.get('matches', []):
                    kickoff_str = match.get('kickoff', '')
                    if not kickoff_str:
                        continue
                    
                    try:
                        match_time = datetime.strptime(kickoff_str, '%Y-%m-%d %H:%M')
                    except:
                        continue
                    
                    # 必须有detail_url
                    if not match.get('detail_url'):
                        continue
                    
                    home_team = match.get('home', '')
                    away_team = match.get('away', '')
                    
                    # 计算推送时间（赛前15分钟）
                    push_time = match_time - timedelta(minutes=15)
                    
                    # 检查是否应该已经推送（推送时间已过，开赛后15分钟内仍可补推）
                    if push_time <= now < match_time + timedelta(minutes=15):
                        job_id = f"match_push_{match_time.strftime('%Y%m%d%H%M')}_{home_team}_{away_team}"
                        
                        # 检查是否已经推送过（成功或失败）
                        if job_id in push_status_records:
                            continue
                        
                        # 检查是否在待执行队列中
                        if job_id in scheduled_match_jobs:
                            continue
                        
                        # 🔥 发现遗漏！立即推送
                        app.logger.warning(f"⚠️ 发现遗漏推送: {home_team} vs {away_team} (应在 {push_time.strftime('%H:%M')} 推送)")
                        
                        match_info = {
                            'match_time': match_time,
                            'home_team': home_team,
                            'away_team': away_team,
                            'league': match.get('league', '未知'),
                            'detail_url': match.get('detail_url'),
                            'raw_match_data': match
                        }
                        
                        # 尝试补推送
                        try:
                            raw_match_data = match
                            match_file = auto_push_system._auto_collect_match(match_info, raw_match_data)
                            
                            if match_file:
                                with open(match_file, 'r', encoding='utf-8') as f:
                                    json_data = json.load(f)
                                
                                if raw_match_data.get('handicap_preview'):
                                    json_data['market_handicap'] = raw_match_data.get('handicap_preview')
                                
                                push_match_info = {
                                    'match_time': match_time,
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    'league': match.get('league', '未知')
                                }
                                
                                success = auto_push_system._send_json_data_notification(
                                    match_info=push_match_info,
                                    json_data=json_data,
                                    minutes_before=int((match_time - now).total_seconds() / 60)
                                )
                                
                                if success:
                                    app.logger.info(f"✅ 遗漏补推送成功: {home_team} vs {away_team}")
                                    push_status_records[job_id] = {
                                        'status': 'success',
                                        'match_time': match_time,
                                        'push_time': now,
                                        'home_team': home_team,
                                        'away_team': away_team,
                                        'attempts': 1,
                                        'type': 'missed_recovery'
                                    }
                                    missed_count += 1
                                else:
                                    app.logger.error(f"❌ 遗漏补推送失败: {home_team} vs {away_team}")
                                    push_status_records[job_id] = {
                                        'status': 'failed',
                                        'match_time': match_time,
                                        'push_time': now,
                                        'home_team': home_team,
                                        'away_team': away_team,
                                        'match_info': match_info,
                                        'attempts': 1,
                                        'type': 'missed_recovery'
                                    }
                            else:
                                app.logger.error(f"❌ 遗漏补推送采集失败: {home_team} vs {away_team}")
                                
                        except Exception as e:
                            app.logger.error(f"❌ 遗漏补推送异常: {e}")
                        
            except Exception as e:
                app.logger.warning(f"读取 {date_str} 标盘数据失败: {e}")
        
        app.logger.info(f"📋 遗漏检测完成: 补推送 {missed_count} 场")
        
        # 🔥 第二步：检查失败的推送并重试
        app.logger.info("📋 检查失败的推送...")
        
        for job_id, record in list(push_status_records.items()):
            status = record.get('status')
            match_time = record.get('match_time')
            attempts = record.get('attempts', 0)
            
            # 只处理失败或错误的推送
            if status not in ['failed', 'error']:
                continue
            
            # 最多重试3次
            if attempts >= 3:
                app.logger.info(f"⏭️ 跳过（已重试3次）: {record.get('home_team')} vs {record.get('away_team')}")
                continue
            
            # 只补推送开赛前的比赛（开赛后不再推送）
            if match_time and match_time <= now:
                app.logger.info(f"⏭️ 跳过（已开赛）: {record.get('home_team')} vs {record.get('away_team')}")
                continue
            
            # 尝试补推送
            app.logger.info(f"🔄 补推送: {record.get('home_team')} vs {record.get('away_team')} (第{attempts+1}次)")
            
            match_info = record.get('match_info')
            if not match_info:
                continue
            
            try:
                import json
                
                raw_match_data = match_info.get('raw_match_data', match_info)
                match_file = auto_push_system._auto_collect_match(match_info, raw_match_data)
                
                if not match_file:
                    app.logger.error(f"❌ 补推送采集失败")
                    record['attempts'] = attempts + 1
                    continue
                
                with open(match_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                if raw_match_data.get('handicap_preview'):
                    json_data['market_handicap'] = raw_match_data.get('handicap_preview')
                
                push_match_info = {
                    'match_time': match_info['match_time'],
                    'home_team': match_info['home_team'],
                    'away_team': match_info['away_team'],
                    'league': match_info.get('league', '未知')
                }
                
                success = auto_push_system._send_json_data_notification(
                    match_info=push_match_info,
                    json_data=json_data,
                    minutes_before=15
                )
                
                if success:
                    app.logger.info(f"✅ 补推送成功: {record.get('home_team')} vs {record.get('away_team')}")
                    record['status'] = 'success'
                    record['attempts'] = attempts + 1
                    retry_count += 1
                else:
                    app.logger.error(f"❌ 补推送失败")
                    record['attempts'] = attempts + 1
                    
            except Exception as e:
                app.logger.error(f"❌ 补推送异常: {e}")
                record['attempts'] = attempts + 1
        
        # 清理过期记录（开赛后2小时）
        for job_id, record in list(push_status_records.items()):
            match_time = record.get('match_time')
            if match_time and match_time < now - timedelta(hours=2):
                push_status_records.pop(job_id, None)
        
        app.logger.info(f"✅ 检查完成: 补推送 {retry_count} 场，当前记录 {len(push_status_records)} 条")
        
    except Exception as e:
        app.logger.error(f"补推送检查失败: {e}", exc_info=True)

# 每5分钟检查一次推送状态
scheduler.add_job(
    func=check_and_retry_failed_pushes,
    trigger='interval',
    minutes=5,
    id='check_push_status',
    name='检查推送状态并补推送',
    replace_existing=True,
    next_run_time=datetime.now() + timedelta(minutes=2)  # 启动2分钟后首次执行
)
app.logger.info("✅ 注册定时任务: 检查推送状态并补推送（每5分钟执行）")

# API: 查看推送状态
@app.route("/api/push/status", methods=["GET"])
def api_push_status():
    """查看推送状态记录"""
    return jsonify({
        "success": True,
        "total": len(push_status_records),
        "records": [
            {
                "job_id": job_id,
                "status": record.get('status'),
                "home_team": record.get('home_team'),
                "away_team": record.get('away_team'),
                "match_time": record.get('match_time').strftime('%Y-%m-%d %H:%M') if record.get('match_time') else None,
                "push_time": record.get('push_time').strftime('%Y-%m-%d %H:%M:%S') if record.get('push_time') else None,
                "attempts": record.get('attempts', 0)
            }
            for job_id, record in push_status_records.items()
        ]
    })

# API: 手动触发补推送
@app.route("/api/push/retry_failed", methods=["POST"])
def api_retry_failed_pushes():
    """手动触发补推送检查"""
    try:
        check_and_retry_failed_pushes()
        return jsonify({"success": True, "message": "补推送检查已执行"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# API: 查看当前待执行的推送任务
@app.route("/api/push/scheduled_jobs", methods=["GET"])
def api_scheduled_jobs():
    """查看当前待执行的推送任务"""
    return jsonify({
        "success": True,
        "total": len(scheduled_match_jobs),
        "jobs": [
            {
                "job_id": job_id,
                "home_team": info['home_team'],
                "away_team": info['away_team'],
                "match_time": info['match_time'].strftime('%Y-%m-%d %H:%M'),
                "push_time": info['push_time'].strftime('%Y-%m-%d %H:%M')
            }
            for job_id, info in sorted(scheduled_match_jobs.items(), key=lambda x: x[1]['push_time'])
        ]
    })

# 🔥 辅助函数：编码大小球URL参数
def _encode_ou_params(params: dict) -> str:
    """将大小球参数编码为base64格式的getuid"""
    import base64
    from urllib.parse import quote
    # 格式: tmiid=X&opentime=X&marketid=X&home_sid=X&away_sid=X&hdp=X&fff=X&teammsg=...
    # teammsg可以为空或包含球队信息
    param_str = (
        f"tmiid={params['matchid']}&opentime={params['kickoff']}"
        f"&marketid={params['eventid']}&home_sid={params['homeid']}"
        f"&away_sid={params['awayid']}&hdp={params['hdp']}&fff={params['type']}&teammsg="
    )
    return base64.b64encode(param_str.encode()).decode()

# 🔥 辅助函数：编码让球URL参数
def _encode_handicap_params(params: dict, home_team: str = '', away_team: str = '', league: str = '') -> str:
    """将让球参数编码为base64格式的getuid"""
    import base64
    from urllib.parse import quote
    # teammsg格式: 联赛@主队@客队@比分&  (注意末尾有&，@不编码)
    # 先对各部分单独编码，保留@不编码
    league_enc = quote(league, safe='')
    home_enc = quote(home_team, safe='')
    away_enc = quote(away_team, safe='')
    teammsg = f"{league_enc}@{home_enc}@{away_enc}@&"
    
    param_str = (
        f"tmiid={params['matchid']}&marketid={params['eventid']}"
        f"&home_sid={params['homeid']}&away_sid={params['awayid']}"
        f"&opentime={params['kickoff']}&hdp={params['hdp']}&fff={params['type']}&teammsg={teammsg}"
    )
    return base64.b64encode(param_str.encode()).decode()

# 🔥 辅助函数：编码比分URL参数
def _encode_correct_params(params: dict, home_team: str = '', away_team: str = '', league: str = '') -> str:
    """将比分参数编码为base64格式的getuid"""
    import base64
    from urllib.parse import quote
    # teammsg格式: 联赛@主队@客队@比分&  (注意末尾有&，@不编码)
    league_enc = quote(league, safe='')
    home_enc = quote(home_team, safe='')
    away_enc = quote(away_team, safe='')
    teammsg = f"{league_enc}@{home_enc}@{away_enc}@&"
    
    param_str = (
        f"tmiid={params['matchid']}&marketid={params['eventid']}"
        f"&opentime={params['kickoff']}&fff={params['type']}&teammsg={teammsg}"
    )
    return base64.b64encode(param_str.encode()).decode()

# 🔥 采集任务进度跟踪
import uuid
import threading
json_collect_tasks = {}  # task_id -> {status, progress, message, result}

def run_json_collect_task(task_id: str, match: dict, match_info: dict, match_time):
    """后台运行采集任务 - 🔥 使用四合一super_detail格式，精确匹配match_id"""
    import json as json_module
    import requests as req_lib
    from parser.super_detail_parser import (
        parse_handicap_trade_html,
        parse_correct_score_html,
        create_super_json,
    )
    from parser.html_parser import parse_bifa_html
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    try:
        home_team = match_info['home_team']
        away_team = match_info['away_team']
        detail_url = match.get('detail_url', '')
        match_id = str(match.get('match_id', ''))
        
        app.logger.info(f"🔥 开始采集四合一JSON: {home_team} vs {away_team}, match_id={match_id}")
        
        # 更新进度: 开始采集
        json_collect_tasks[task_id] = {
            'status': 'running',
            'progress': 5,
            'message': '正在初始化浏览器...',
            'result': None
        }
        
        # 获取比赛日期 - 对于凌晨的比赛（00:00-06:00），使用前一天的日期
        # 因为完场回查页面按"比赛日"分组，凌晨的比赛属于前一天的比赛日
        query_date = match_time
        if match_time.hour < 6:  # 凌晨6点前的比赛属于前一天
            from datetime import timedelta
            query_date = match_time - timedelta(days=1)
        date_str_query = f"{query_date.year}-{query_date.month}-{query_date.day}"
        app.logger.info(f"📅 比赛时间: {match_time}, 查询日期: {date_str_query}")
        
        # 判断比赛是否已经开始（用于决定从哪个页面获取URL）
        is_match_started = datetime.now() > match_time
        app.logger.info(f"📅 比赛状态: {'已开始/完场' if is_match_started else '未开始'}")
        
        # 初始化URLs字典，使用传入的detail_url作为标盘URL
        urls = {
            'standard_url': detail_url,  # 直接使用传入的detail_url
        }
        
        driver = None
        cookies = {}
        
        try:
            # 初始化Selenium
            driver = bifaw_client._init_driver(headless=False)
            bifaw_client._inject_cookies(driver)
            
            json_collect_tasks[task_id]['progress'] = 10
            json_collect_tasks[task_id]['message'] = '正在访问必发网...'
            
            # 访问首页建立session
            driver.get("https://www.bifaw.com/bifaw/index.php")
            time_module.sleep(2)
            
            # ========== 根据比赛状态选择不同的获取方式 ==========
            if is_match_started:
                # 已开始/完场的比赛：需要分别访问三个回查页面获取URL
                # - result_aisa.php: 让球回查（只有让球按钮）
                # - result_ou.php: 大小球回查（只有大小球按钮）
                # - result_correct.php: 比分回查（只有比分按钮）
                
                # ========== 1. 访问让球回查页面获取让球URL ==========
                json_collect_tasks[task_id]['progress'] = 15
                json_collect_tasks[task_id]['message'] = '正在访问让球回查页面...'
                
                aisa_url = f"https://www.bifaw.com/bifaw/result_aisa.php?rq={date_str_query}"
                driver.get(aisa_url)
                time_module.sleep(3)
                
                # 设置日期并查询
                try:
                    date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                    if date_input:
                        driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                        query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                        if query_btn:
                            query_btn.click()
                            time_module.sleep(5)
                except:
                    pass
                
                # 等待页面加载
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: home_team in d.page_source or away_team in d.page_source
                    )
                except:
                    app.logger.warning(f"让球回查页面未找到比赛: {home_team} vs {away_team}")
                
                # 🔥 获取所有盘口信息，找到SB有数据的主盘口
                js_get_all_handicaps = f"""
                var tables = document.querySelectorAll('table');
                var homeTeam = '{home_team}';
                var awayTeam = '{away_team}';
                var result = {{found: false, handicaps: [], mainLine: null, mainLineHome: null}};
                
                for (var t = 0; t < tables.length; t++) {{
                    var table = tables[t];
                    var tableText = table.innerText;
                    
                    if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                        result.found = true;
                        result.tableIndex = t;
                        
                        // 遍历所有带有openAisaDetails的按钮
                        var btns = table.querySelectorAll('[onclick*="openAisaDetails"]');
                        for (var i = 0; i < btns.length; i++) {{
                            var btn = btns[i];
                            var onclick = btn.getAttribute('onclick');
                            var match = onclick.match(/openAisaDetails\\('[^']+','[^']+','[^']+','[^']+','[^']+','([^']+)'/);
                            if (!match) continue;
                            
                            var hdpAway = match[1];  // 客队让球视角
                            
                            // 找到按钮所在的行
                            var row = btn.closest('tr');
                            if (!row) continue;
                            
                            // 从行中提取主队视角的盘口值（第2列，索引1）
                            var cells = row.querySelectorAll('td');
                            var hdpHome = null;
                            var sb = null;
                            var volume = null;
                            
                            // 查找主队盘口值（通常在前几列，格式如 +1.25 或 -0.5）
                            for (var c = 0; c < Math.min(cells.length, 5); c++) {{
                                var cellText = cells[c].innerText.trim();
                                if (cellText.match(/^[+-]?\\d+(\\.\\d+)?$/) || cellText.match(/^[+-]?\\d+\\/\\d+$/)) {{
                                    hdpHome = cellText;
                                    break;
                                }}
                            }}
                            
                            // 查找SB值（通常在第13列附近）
                            for (var c = 10; c < cells.length; c++) {{
                                var cellText = cells[c].innerText.trim();
                                // SB值通常是小数，如 0.90, 1.08
                                if (cellText.match(/^-?\\d+\\.\\d+$/) && parseFloat(cellText) < 10 && parseFloat(cellText) > -10) {{
                                    // 检查是否是SB列（不是成交量等大数字）
                                    var num = parseFloat(cellText);
                                    if (Math.abs(num) < 5) {{
                                        sb = cellText;
                                        break;
                                    }}
                                }}
                            }}
                            
                            // 查找成交量
                            for (var c = 0; c < cells.length; c++) {{
                                var cellText = cells[c].innerText.trim().replace(/,/g, '');
                                if (cellText.match(/^\\d+$/) && parseInt(cellText) > 1000) {{
                                    volume = parseInt(cellText);
                                    break;
                                }}
                            }}
                            
                            var hdpInfo = {{
                                hdp_away: hdpAway,
                                hdp_home: hdpHome,
                                sb: sb,
                                volume: volume,
                                is_main: sb !== null && sb !== ''
                            }};
                            result.handicaps.push(hdpInfo);
                            
                            // 如果SB有值，这是主盘口
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
                handicap_info = driver.execute_script(js_get_all_handicaps)
                app.logger.info(f"让球盘口信息: 找到{len(handicap_info.get('handicaps', []))}个盘口, 主盘口={handicap_info.get('mainLineHome')}")
                
                # 保存所有盘口信息
                urls['handicap_all_lines'] = handicap_info.get('handicaps', [])
                urls['handicap_main_line'] = handicap_info.get('mainLineHome')  # 主队视角
                urls['handicap_main_line_away'] = handicap_info.get('mainLine')  # 客队视角（用于点击按钮）
                
                if handicap_info.get('found') and handicap_info.get('mainLine'):
                    table_index = handicap_info.get('tableIndex')
                    main_hdp = handicap_info.get('mainLine')
                    
                    # 点击主盘口的按钮
                    try:
                        js_click_main_aisa = f"""
                        var tables = document.querySelectorAll('table');
                        var table = tables[{table_index}];
                        var btns = table.querySelectorAll('[onclick*="openAisaDetails"]');
                        for (var i = 0; i < btns.length; i++) {{
                            var btn = btns[i];
                            var onclick = btn.getAttribute('onclick');
                            if (onclick.indexOf("'{main_hdp}'") !== -1) {{
                                btn.click();
                                return {{found: true, hdp: '{main_hdp}'}};
                            }}
                        }}
                        return {{found: false}};
                        """
                        aisa_result = driver.execute_script(js_click_main_aisa)
                        app.logger.info(f"让球主盘口按钮点击结果: {aisa_result}")
                        
                        if aisa_result and aisa_result.get('found'):
                            time_module.sleep(2)
                            windows = driver.window_handles
                            if len(windows) > 1:
                                driver.switch_to.window(windows[-1])
                                urls['handicap_url'] = driver.current_url
                                urls['handicap_hdp'] = handicap_info.get('mainLineHome', '')  # 使用主队视角
                                app.logger.info(f"✅ 获取到让球主盘口URL (主队视角: {urls['handicap_hdp']})")
                                driver.close()
                                driver.switch_to.window(windows[0])
                    except Exception as e:
                        app.logger.warning(f"获取让球URL失败: {e}")
                
                # ========== 2. 访问大小球回查页面获取大小球URL ==========
                json_collect_tasks[task_id]['progress'] = 20
                json_collect_tasks[task_id]['message'] = '正在访问大小球回查页面...'
                
                ou_page_url = f"https://www.bifaw.com/bifaw/result_ou.php?rq={date_str_query}"
                driver.get(ou_page_url)
                time_module.sleep(3)
                
                # 设置日期并查询
                try:
                    date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                    if date_input:
                        driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                        query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                        if query_btn:
                            query_btn.click()
                            time_module.sleep(5)
                except:
                    pass
                
                # 🔥 获取所有大小球盘口信息，找到SB有数据的主盘口
                js_get_all_ou = f"""
                var tables = document.querySelectorAll('table');
                var homeTeam = '{home_team}';
                var awayTeam = '{away_team}';
                var result = {{found: false, lines: [], mainLine: null}};
                
                for (var t = 0; t < tables.length; t++) {{
                    var table = tables[t];
                    var tableText = table.innerText;
                    
                    if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                        result.found = true;
                        result.tableIndex = t;
                        
                        // 遍历所有带有openOuDetails的按钮
                        var btns = table.querySelectorAll('[onclick*="openOuDetails"]');
                        for (var i = 0; i < btns.length; i++) {{
                            var btn = btns[i];
                            var onclick = btn.getAttribute('onclick');
                            var match = onclick.match(/openOuDetails\\('[^']+','[^']+','[^']+','[^']+','[^']+','([^']+)'/);
                            if (!match) continue;
                            
                            var line = match[1];
                            
                            // 找到按钮所在的行
                            var row = btn.closest('tr');
                            if (!row) continue;
                            
                            var cells = row.querySelectorAll('td');
                            var sb = null;
                            var volume = null;
                            
                            // 查找SB值（通常在后面的列）
                            for (var c = 10; c < cells.length; c++) {{
                                var cellText = cells[c].innerText.trim();
                                if (cellText.match(/^-?\\d+\\.\\d+$/) && parseFloat(cellText) < 10 && parseFloat(cellText) > -10) {{
                                    var num = parseFloat(cellText);
                                    if (Math.abs(num) < 5) {{
                                        sb = cellText;
                                        break;
                                    }}
                                }}
                            }}
                            
                            // 查找成交量
                            for (var c = 0; c < cells.length; c++) {{
                                var cellText = cells[c].innerText.trim().replace(/,/g, '');
                                if (cellText.match(/^\\d+$/) && parseInt(cellText) > 1000) {{
                                    volume = parseInt(cellText);
                                    break;
                                }}
                            }}
                            
                            var lineInfo = {{
                                line: line,
                                sb: sb,
                                volume: volume,
                                is_main: sb !== null && sb !== ''
                            }};
                            result.lines.push(lineInfo);
                            
                            // 如果SB有值，这是主盘口
                            if (sb !== null && sb !== '' && result.mainLine === null) {{
                                result.mainLine = line;
                            }}
                        }}
                        break;
                    }}
                }}
                return result;
                """
                ou_info = driver.execute_script(js_get_all_ou)
                app.logger.info(f"大小球盘口信息: 找到{len(ou_info.get('lines', []))}个盘口, 主盘口={ou_info.get('mainLine')}")
                
                # 保存所有盘口信息
                urls['ou_all_lines'] = ou_info.get('lines', [])
                urls['ou_main_line'] = ou_info.get('mainLine')
                
                if ou_info.get('found') and ou_info.get('mainLine'):
                    table_index = ou_info.get('tableIndex')
                    main_line = ou_info.get('mainLine')
                    
                    # 点击主盘口的按钮
                    try:
                        js_click_main_ou = f"""
                        var tables = document.querySelectorAll('table');
                        var table = tables[{table_index}];
                        var btns = table.querySelectorAll('[onclick*="openOuDetails"]');
                        for (var i = 0; i < btns.length; i++) {{
                            var btn = btns[i];
                            var onclick = btn.getAttribute('onclick');
                            if (onclick.indexOf("'{main_line}'") !== -1) {{
                                btn.click();
                                return {{found: true, line: '{main_line}'}};
                            }}
                        }}
                        return {{found: false}};
                        """
                        ou_result = driver.execute_script(js_click_main_ou)
                        app.logger.info(f"大小球主盘口按钮点击结果: {ou_result}")
                        
                        if ou_result and ou_result.get('found'):
                            time_module.sleep(2)
                            windows = driver.window_handles
                            if len(windows) > 1:
                                driver.switch_to.window(windows[-1])
                                urls['ou_url'] = driver.current_url
                                urls['ou_hdp'] = main_line
                                app.logger.info(f"✅ 获取到大小球主盘口URL (盘口: {main_line})")
                                driver.close()
                                driver.switch_to.window(windows[0])
                    except Exception as e:
                        app.logger.warning(f"获取大小球URL失败: {e}")
                
                # ========== 3. 访问比分回查页面获取比分URL ==========
                json_collect_tasks[task_id]['progress'] = 25
                json_collect_tasks[task_id]['message'] = '正在访问比分回查页面...'
                
                correct_page_url = f"https://www.bifaw.com/bifaw/result_correct.php?rq={date_str_query}"
                driver.get(correct_page_url)
                time_module.sleep(3)
                
                # 设置日期并查询
                try:
                    date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate")
                    if date_input:
                        driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                        query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                        if query_btn:
                            query_btn.click()
                            time_module.sleep(5)
                except:
                    pass
                
                # 查找比赛表格并获取比分URL
                js_find_match_correct = f"""
                var tables = document.querySelectorAll('table');
                var homeTeam = '{home_team}';
                var awayTeam = '{away_team}';
                
                for (var t = 0; t < tables.length; t++) {{
                    var table = tables[t];
                    var tableText = table.innerText;
                    
                    if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                        return {{found: true, tableIndex: t}};
                    }}
                }}
                return {{found: false}};
                """
                match_result = driver.execute_script(js_find_match_correct)
                app.logger.info(f"比分回查页面查找比赛表格结果: {match_result}")
                
                if match_result and match_result.get('found'):
                    table_index = match_result.get('tableIndex')
                    
                    try:
                        js_click_correct = f"""
                        var tables = document.querySelectorAll('table');
                        var table = tables[{table_index}];
                        var btn = table.querySelector('[onclick*="openCorrectDetails"]');
                        if (btn) {{
                            btn.click();
                            return {{found: true}};
                        }}
                        return {{found: false}};
                        """
                        correct_result = driver.execute_script(js_click_correct)
                        app.logger.info(f"比分按钮点击结果: {correct_result}")
                        
                        if correct_result and correct_result.get('found'):
                            time_module.sleep(2)
                            windows = driver.window_handles
                            if len(windows) > 1:
                                driver.switch_to.window(windows[-1])
                                urls['correct_score_url'] = driver.current_url
                                app.logger.info(f"✅ 获取到比分URL")
                                driver.close()
                                driver.switch_to.window(windows[0])
                    except Exception as e:
                        app.logger.warning(f"获取比分URL失败: {e}")
            
            else:
                # ========== 未开始的比赛：从标盘首页获取URL ==========
                # 标盘首页(index.php)包含标盘和大小球按钮
                # 让球页面(index_aisa.php)只显示有让球盘口的比赛
                json_collect_tasks[task_id]['progress'] = 15
                json_collect_tasks[task_id]['message'] = '正在从标盘首页获取URL...'
                
                # 访问标盘首页（已经在首页了，但确保刷新）
                driver.get("https://www.bifaw.com/bifaw/index.php")
                time_module.sleep(3)
                
                # 从标盘首页获取大小球URL
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: home_team in d.page_source or away_team in d.page_source
                    )
                    
                    # 点击大小球明细按钮 (openOuDetails)
                    js_click_ou = f"""
                    var tables = document.querySelectorAll('table');
                    var homeTeam = '{home_team}';
                    var awayTeam = '{away_team}';
                    
                    for (var t = 0; t < tables.length; t++) {{
                        var table = tables[t];
                        var tableText = table.innerText;
                        
                        if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                            // 查找大小球明细按钮
                            var allElements = table.querySelectorAll('[onclick]');
                            for (var i = 0; i < allElements.length; i++) {{
                                var el = allElements[i];
                                var onclick = el.getAttribute('onclick') || '';
                                if (onclick.indexOf('openOuDetails') !== -1) {{
                                    var match = onclick.match(/openOuDetails\\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\\)/);
                                    if (match) {{
                                        el.click();
                                        return {{found: true, hdp: match[6]}};
                                    }}
                                }}
                            }}
                            return {{found: false, reason: 'no openOuDetails button'}};
                        }}
                    }}
                    return {{found: false, reason: 'match not found'}};
                    """
                    ou_result = driver.execute_script(js_click_ou)
                    app.logger.info(f"标盘首页大小球按钮点击结果: {ou_result}")
                    
                    if ou_result and ou_result.get('found'):
                        time_module.sleep(2)
                        windows = driver.window_handles
                        if len(windows) > 1:
                            driver.switch_to.window(windows[-1])
                            urls['ou_url'] = driver.current_url
                            urls['ou_hdp'] = ou_result.get('hdp', '')
                            app.logger.info(f"✅ 获取到大小球URL (hdp={ou_result.get('hdp', '')})")
                            driver.close()
                            driver.switch_to.window(windows[0])
                except Exception as e:
                    app.logger.warning(f"从标盘首页获取大小球URL失败: {e}")
                
                # 尝试从让球即时盘口页面获取让球URL（可能没有）
                json_collect_tasks[task_id]['progress'] = 25
                json_collect_tasks[task_id]['message'] = '正在获取让球URL...'
                
                aisa_page_url = "https://www.bifaw.com/bifaw/index_aisa.php"
                driver.get(aisa_page_url)
                time_module.sleep(3)
                
                try:
                    # 检查页面是否包含目标比赛（让球页面可能没有这场比赛）
                    page_source = driver.page_source
                    if home_team in page_source and away_team in page_source:
                        js_find_aisa = f"""
                        var tables = document.querySelectorAll('table');
                        var homeTeam = '{home_team}';
                        var awayTeam = '{away_team}';
                        
                        for (var t = 0; t < tables.length; t++) {{
                            var table = tables[t];
                            var tableText = table.innerText;
                            
                            if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                                var allElements = table.querySelectorAll('[onclick]');
                                for (var i = 0; i < allElements.length; i++) {{
                                    var el = allElements[i];
                                    var onclick = el.getAttribute('onclick') || '';
                                    if (onclick.indexOf('openAisaDetails') !== -1) {{
                                        var match = onclick.match(/openAisaDetails\\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\\)/);
                                        if (match) {{
                                            el.click();
                                            return {{found: true, hdp: match[6]}};
                                        }}
                                    }}
                                }}
                                return {{found: false, reason: 'no openAisaDetails button'}};
                            }}
                        }}
                        return {{found: false, reason: 'match not found'}};
                        """
                        aisa_result = driver.execute_script(js_find_aisa)
                        app.logger.info(f"让球页面按钮点击结果: {aisa_result}")
                        
                        if aisa_result and aisa_result.get('found'):
                            time_module.sleep(2)
                            windows = driver.window_handles
                            if len(windows) > 1:
                                driver.switch_to.window(windows[-1])
                                urls['handicap_url'] = driver.current_url
                                urls['handicap_hdp'] = aisa_result.get('hdp', '')
                                app.logger.info(f"✅ 获取到让球URL (hdp={aisa_result.get('hdp', '')})")
                                driver.close()
                                driver.switch_to.window(windows[0])
                    else:
                        app.logger.info(f"让球即时盘口页面没有该比赛: {home_team} vs {away_team}")
                except Exception as e:
                    app.logger.warning(f"从让球页面获取URL失败: {e}")
                
                # 🔥 从比分即时盘口页面获取比分URL
                json_collect_tasks[task_id]['progress'] = 30
                json_collect_tasks[task_id]['message'] = '正在获取比分URL...'
                
                correct_page_url = "https://www.bifaw.com/bifaw/index_correct.php"
                driver.get(correct_page_url)
                time_module.sleep(3)
                
                try:
                    page_source = driver.page_source
                    if home_team in page_source and away_team in page_source:
                        js_find_correct = f"""
                        var tables = document.querySelectorAll('table');
                        var homeTeam = '{home_team}';
                        var awayTeam = '{away_team}';
                        
                        for (var t = 0; t < tables.length; t++) {{
                            var table = tables[t];
                            var tableText = table.innerText;
                            
                            if (tableText.indexOf(homeTeam) !== -1 && tableText.indexOf(awayTeam) !== -1) {{
                                var allElements = table.querySelectorAll('[onclick]');
                                for (var i = 0; i < allElements.length; i++) {{
                                    var el = allElements[i];
                                    var onclick = el.getAttribute('onclick') || '';
                                    if (onclick.indexOf('openCorrectDetails') !== -1) {{
                                        el.click();
                                        return {{found: true}};
                                    }}
                                }}
                                return {{found: false, reason: 'no openCorrectDetails button'}};
                            }}
                        }}
                        return {{found: false, reason: 'match not found'}};
                        """
                        correct_result = driver.execute_script(js_find_correct)
                        app.logger.info(f"比分页面按钮点击结果: {correct_result}")
                        
                        if correct_result and correct_result.get('found'):
                            time_module.sleep(2)
                            windows = driver.window_handles
                            if len(windows) > 1:
                                driver.switch_to.window(windows[-1])
                                urls['correct_score_url'] = driver.current_url
                                app.logger.info(f"✅ 获取到比分URL")
                                driver.close()
                                driver.switch_to.window(windows[0])
                    else:
                        app.logger.info(f"比分即时盘口页面没有该比赛: {home_team} vs {away_team}")
                except Exception as e:
                    app.logger.warning(f"从比分页面获取URL失败: {e}")
            
            # 获取cookies用于requests
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            
            # 打印获取到的所有URL
            app.logger.info(f"📋 获取到的URL汇总:")
            app.logger.info(f"   标盘: {'✅' if urls.get('standard_url') else '❌'}")
            app.logger.info(f"   大小球: {'✅ hdp=' + str(urls.get('ou_hdp', '')) if urls.get('ou_url') else '❌'}")
            app.logger.info(f"   让球: {'✅ hdp=' + str(urls.get('handicap_hdp', '')) if urls.get('handicap_url') else '❌'}")
            app.logger.info(f"   比分: {'✅' if urls.get('correct_score_url') else '❌'}")
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        # 检查是否有标盘URL
        if not urls.get('standard_url'):
            json_collect_tasks[task_id] = {
                'status': 'error',
                'progress': 100,
                'message': f'缺少标盘URL: {home_team} vs {away_team}',
                'result': None
            }
            return
        
        json_collect_tasks[task_id]['progress'] = 45
        json_collect_tasks[task_id]['message'] = '正在获取交易明细数据...'
        
        standard_data = None
        ou_data = None
        handicap_data = None
        correct_score_data = None
        
        # 🔥🔥🔥 所有数据都用Selenium获取（页面都是JavaScript动态加载的）🔥🔥🔥
        driver2 = None
        try:
            driver2 = bifaw_client._init_driver(headless=False)
            bifaw_client._inject_cookies(driver2)
            
            # 🔥 辅助函数：获取所有分页数据（标盘/大小球）
            def collect_all_pages_bifa(driver, data_type="standard"):
                """收集标盘/大小球所有分页的数据"""
                all_rows = []
                page = 1
                max_pages = 50
                
                while page <= max_pages:
                    # 等待数据加载 - 标盘/大小球的表格结构不同
                    try:
                        WebDriverWait(driver, 10).until(
                            lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tr")) > 5
                        )
                        time_module.sleep(1)
                    except:
                        if page == 1:
                            app.logger.warning(f"{data_type}数据表格加载超时")
                        break
                    
                    # 解析当前页数据
                    html = driver.page_source
                    df = parse_bifa_html(html, {'match_id': match_id})
                    
                    if isinstance(df, pd.DataFrame) and len(df) > 0:
                        page_rows = df.to_dict(orient="records")
                        all_rows.extend(page_rows)
                        app.logger.info(f"  {data_type}第{page}页: {len(page_rows)}条记录，累计: {len(all_rows)}条")
                    else:
                        if page == 1:
                            app.logger.warning(f"{data_type}第1页解析失败: {df if isinstance(df, str) else '无数据'}")
                        break
                    
                    # 检查是否有下一页
                    try:
                        next_page_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                        if next_page_link:
                            next_page_link.click()
                            time_module.sleep(2)
                            page += 1
                        else:
                            break
                    except:
                        break
                
                return all_rows
            
            # 🔥 辅助函数：获取所有分页数据（让球/大小球/比分）
            def collect_all_pages(driver, data_type="handicap"):
                """收集让球/大小球/比分所有分页的数据"""
                all_records = []
                page = 1
                max_pages = 50  # 最多翻50页，防止死循环
                
                while page <= max_pages:
                    # 等待数据加载
                    try:
                        WebDriverWait(driver, 10).until(
                            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#table_1 tr.item")) > 0
                        )
                        time_module.sleep(1)
                    except:
                        if page == 1:
                            app.logger.warning(f"{data_type}数据表格加载超时")
                        break
                    
                    # 解析当前页数据
                    html = driver.page_source
                    if data_type == "handicap" or data_type == "ou":
                        # 让球和大小球使用相同的解析器
                        page_data = parse_handicap_trade_html(html)
                    else:
                        page_data = parse_correct_score_html(html)
                    
                    records = page_data.get('trade_records', [])
                    if not records:
                        break
                    
                    all_records.extend(records)
                    app.logger.info(f"  第{page}页: {len(records)}条记录，累计: {len(all_records)}条")
                    
                    # 检查是否有下一页
                    try:
                        next_page_link = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                        if next_page_link:
                            next_page_link.click()
                            time_module.sleep(2)
                            page += 1
                        else:
                            break
                    except:
                        # 没有下一页了
                        break
                
                return all_records
            
            # ========== 1. 获取标盘数据（含翻页）==========
            if urls.get('standard_url'):
                try:
                    json_collect_tasks[task_id]['progress'] = 50
                    json_collect_tasks[task_id]['message'] = '正在获取标盘数据（含翻页）...'
                    
                    driver2.get(urls['standard_url'])
                    time_module.sleep(3)
                    
                    # 收集所有分页数据
                    all_standard_rows = collect_all_pages_bifa(driver2, "标盘")
                    
                    if all_standard_rows:
                        # 获取列名
                        html = driver2.page_source
                        df_temp = parse_bifa_html(html, {'match_id': match_id})
                        columns = df_temp.columns.tolist() if isinstance(df_temp, pd.DataFrame) else []
                        
                        standard_data = {
                            "columns": columns,
                            "data": all_standard_rows,
                            "total_records": len(all_standard_rows)
                        }
                    app.logger.info(f"标盘数据总计: {len(all_standard_rows) if all_standard_rows else 0}条记录")
                    
                except Exception as e:
                    app.logger.warning(f"获取标盘数据失败: {e}")
            
            # ========== 2. 获取大小球数据（含翻页）==========
            # 🔥 大小球页面结构和让球页面一样，使用相同的解析器
            if urls.get('ou_url'):
                try:
                    json_collect_tasks[task_id]['progress'] = 60
                    json_collect_tasks[task_id]['message'] = '正在获取大小球数据（含翻页）...'
                    
                    driver2.get(urls['ou_url'])
                    time_module.sleep(3)
                    
                    # 使用让球解析器（大小球页面结构相同）
                    all_ou_records = collect_all_pages(driver2, "ou")
                    
                    if all_ou_records:
                        ou_data = {
                            "ou_line": urls.get('ou_hdp'),
                            "trade_records": all_ou_records,
                            "summary": {
                                "total_records": len(all_ou_records),
                                "first_time": all_ou_records[-1].get("time") if all_ou_records else None,
                                "last_time": all_ou_records[0].get("time") if all_ou_records else None,
                            }
                        }
                    app.logger.info(f"大小球数据总计: {len(all_ou_records) if all_ou_records else 0}条记录")
                    
                except Exception as e:
                    app.logger.warning(f"获取大小球数据失败: {e}")
            
            # ========== 3. 获取让球指数数据（含翻页）==========
            if urls.get('handicap_url'):
                try:
                    json_collect_tasks[task_id]['progress'] = 70
                    json_collect_tasks[task_id]['message'] = '正在获取让球数据（含翻页）...'
                    
                    driver2.get(urls['handicap_url'])
                    time_module.sleep(3)
                    
                    # 收集所有分页数据
                    all_handicap_records = collect_all_pages(driver2, "handicap")
                    
                    if all_handicap_records:
                        handicap_data = {
                            "handicap_line": urls.get('handicap_hdp'),
                            "trade_records": all_handicap_records,
                            "summary": {
                                "total_records": len(all_handicap_records),
                                "first_time": all_handicap_records[-1].get("time") if all_handicap_records else None,
                                "last_time": all_handicap_records[0].get("time") if all_handicap_records else None,
                            }
                        }
                    app.logger.info(f"让球数据总计: {len(all_handicap_records)}条记录")
                    
                except Exception as e:
                    app.logger.warning(f"获取让球数据失败: {e}")
            
            # 获取比分数据（含翻页）
            if urls.get('correct_score_url'):
                try:
                    json_collect_tasks[task_id]['progress'] = 80
                    json_collect_tasks[task_id]['message'] = '正在获取比分数据（含翻页）...'
                    
                    driver2.get(urls['correct_score_url'])
                    time_module.sleep(3)
                    
                    # 收集所有分页数据
                    all_correct_records = collect_all_pages(driver2, "correct_score")
                    
                    if all_correct_records:
                        correct_score_data = {
                            "score_lines": [],
                            "trade_records": all_correct_records,
                            "summary": {
                                "total_records": len(all_correct_records),
                                "first_time": all_correct_records[-1].get("time") if all_correct_records else None,
                                "last_time": all_correct_records[0].get("time") if all_correct_records else None,
                            }
                        }
                    app.logger.info(f"比分数据总计: {len(all_correct_records)}条记录")
                    
                except Exception as e:
                    app.logger.warning(f"获取比分数据失败: {e}")
        
        finally:
            if driver2:
                try:
                    driver2.quit()
                except:
                    pass
        
        json_collect_tasks[task_id]['progress'] = 90
        json_collect_tasks[task_id]['message'] = '正在保存JSON文件...'
        
        # 创建超级JSON
        super_json = create_super_json(
            match_info={
                'match_id': match_id, 
                'date': date_str_query,
                'home': home_team,
                'away': away_team,
                'league': match.get('league', '未知'),
                'kickoff': match_time.strftime('%Y-%m-%d %H:%M'),
                **urls
            },
            standard_data=standard_data,
            ou_data=ou_data,
            handicap_data=handicap_data,
            correct_score_data=correct_score_data,
            # 🔥 新增：传递所有盘口信息
            handicap_all_lines=urls.get('handicap_all_lines'),
            ou_all_lines=urls.get('ou_all_lines'),
            handicap_main_line=urls.get('handicap_main_line'),
            ou_main_line=urls.get('ou_main_line'),
        )
        
        # 保存到 push_json 目录
        push_dir = Path(__file__).parent / "data" / "push_json" / match_time.strftime('%Y/%m/%d')
        push_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = match_time.strftime('%Y%m%d')
        time_str = match_time.strftime('%H%M')
        safe_home = home_team.replace(' ', '_').replace('/', '_')
        safe_away = away_team.replace(' ', '_').replace('/', '_')
        safe_league = match.get('league', '未知').replace(' ', '_').replace('/', '_')
        
        filename = f"{date_str}_{time_str}_{safe_league}_{safe_home}_vs_{safe_away}.json"
        json_file_path = push_dir / filename
        
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json_module.dump(super_json, f, ensure_ascii=False, indent=2)
        
        # 完成
        json_collect_tasks[task_id] = {
            'status': 'done',
            'progress': 100,
            'message': '保存成功！（四合一格式）',
            'result': {
                'filename': filename,
                'path': str(json_file_path)
            }
        }
        
        app.logger.info(f"✅ 四合一JSON采集完成: {filename}")
        
    except Exception as e:
        app.logger.exception(f"采集任务失败: {e}")
        json_collect_tasks[task_id] = {
            'status': 'error',
            'progress': 100,
            'message': f'采集失败: {str(e)}',
            'result': None
        }

# API: 启动采集任务
@app.route("/api/push/collect_json_async", methods=["POST"])
def api_collect_json_async():
    """异步采集比赛数据，返回任务ID用于轮询进度"""
    try:
        data = request.get_json(force=True) or {}
        match = data.get('match', {})
        
        if not match:
            return jsonify({"success": False, "error": "未提供比赛信息"}), 400
        
        home_team = match.get('home', '')
        away_team = match.get('away', '')
        kickoff = match.get('kickoff', '')
        detail_url = match.get('detail_url', '')
        
        if not home_team or not away_team:
            return jsonify({"success": False, "error": "比赛信息不完整"}), 400
        
        if not detail_url:
            return jsonify({"success": False, "error": "缺少detail_url，无法采集"}), 400
        
        if not auto_push_system:
            return jsonify({"success": False, "error": "推送系统未初始化"}), 500
        
        # 解析比赛时间
        try:
            match_time = datetime.strptime(kickoff, '%Y-%m-%d %H:%M')
        except:
            match_time = datetime.now()
        
        # 构造match_info
        match_info = {
            'match_time': match_time,
            'home_team': home_team,
            'away_team': away_team,
            'league': match.get('league', '未知'),
            'detail_url': detail_url
        }
        
        # 创建任务
        task_id = str(uuid.uuid4())[:8]
        json_collect_tasks[task_id] = {
            'status': 'starting',
            'progress': 0,
            'message': '准备采集...',
            'result': None
        }
        
        # 启动后台线程
        thread = threading.Thread(
            target=run_json_collect_task,
            args=(task_id, match, match_info, match_time)
        )
        thread.daemon = True
        thread.start()
        
        app.logger.info(f"💾 启动采集任务: {task_id} - {home_team} vs {away_team}")
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "采集任务已启动"
        })
        
    except Exception as e:
        app.logger.exception("启动采集任务失败")
        return jsonify({"success": False, "error": str(e)}), 500

# API: 查询JSON采集进度
@app.route("/api/push/collect_progress/<task_id>", methods=["GET"])
def api_json_collect_progress(task_id):
    """查询JSON采集任务进度"""
    task = json_collect_tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task['status'],
        "progress": task['progress'],
        "message": task['message'],
        "result": task['result']
    })

# API: 手动采集并保存JSON（同步版本，保留兼容）
@app.route("/api/push/collect_and_save_json", methods=["POST"])
def api_collect_and_save_json():
    """手动采集比赛数据并保存为JSON文件（同步版本）"""
    import json as json_module
    
    try:
        data = request.get_json(force=True) or {}
        match = data.get('match', {})
        
        if not match:
            return jsonify({"success": False, "error": "未提供比赛信息"}), 400
        
        home_team = match.get('home', '')
        away_team = match.get('away', '')
        kickoff = match.get('kickoff', '')
        detail_url = match.get('detail_url', '')
        
        if not home_team or not away_team:
            return jsonify({"success": False, "error": "比赛信息不完整"}), 400
        
        if not detail_url:
            return jsonify({"success": False, "error": "缺少detail_url，无法采集"}), 400
        
        app.logger.info(f"💾 手动采集JSON: {home_team} vs {away_team}")
        
        if not auto_push_system:
            return jsonify({"success": False, "error": "推送系统未初始化"}), 500
        
        # 解析比赛时间
        try:
            match_time = datetime.strptime(kickoff, '%Y-%m-%d %H:%M')
        except:
            match_time = datetime.now()
        
        # 构造match_info
        match_info = {
            'match_time': match_time,
            'home_team': home_team,
            'away_team': away_team,
            'league': match.get('league', '未知'),
            'detail_url': detail_url
        }
        
        # 采集数据
        match_file = auto_push_system._auto_collect_match(match_info, match)
        
        if not match_file:
            return jsonify({"success": False, "error": "采集失败，请检查登录状态"}), 500
        
        app.logger.info(f"✅ 采集完成: {match_file}")
        
        # 读取采集的JSON数据
        with open(match_file, 'r', encoding='utf-8') as f:
            json_data = json_module.load(f)
        
        # 🔥 添加标盘中的市场盘口数据
        if match.get('handicap_preview'):
            json_data['market_handicap'] = match.get('handicap_preview')
            app.logger.info(f"   添加市场盘口: {match.get('handicap_preview')}")
        
        # 保存到 push_json 目录
        push_dir = Path(__file__).parent / "data" / "push_json" / match_time.strftime('%Y/%m/%d')
        push_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = match_time.strftime('%Y%m%d')
        time_str = match_time.strftime('%H%M')
        safe_home = home_team.replace(' ', '_').replace('/', '_')
        safe_away = away_team.replace(' ', '_').replace('/', '_')
        safe_league = match.get('league', '未知').replace(' ', '_').replace('/', '_')
        
        filename = f"{date_str}_{time_str}_{safe_league}_{safe_home}_vs_{safe_away}.json"
        json_file_path = push_dir / filename
        
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json_module.dump(json_data, f, ensure_ascii=False, indent=2)
        
        app.logger.info(f"💾 JSON已保存: {json_file_path}")
        
        return jsonify({
            "success": True,
            "message": "JSON保存成功",
            "filename": filename,
            "path": str(json_file_path)
        })
        
    except Exception as e:
        app.logger.exception("手动采集JSON失败")
        return jsonify({"success": False, "error": str(e)}), 500

# 🎯 每天10点执行：自动审查昨天的推荐结果
scheduler.add_job(
    func=auto_review_yesterday,
    trigger=CronTrigger(hour=10, minute=0),
    id='auto_review_yesterday',
    name='自动审查昨日推荐',
    replace_existing=True
)

# 🧹 每天凌晨4点执行：自动清理过期文件
def auto_cleanup_files():
    """自动清理过期的调试文件和临时文件"""
    try:
        app.logger.info("🧹 [定时任务] 开始自动清理过期文件...")
        result = run_cleanup(dry_run=False)
        app.logger.info(f"🧹 [定时任务] 清理完成: 删除 {result['files_deleted']} 个文件, 释放 {result['bytes_freed'] / 1024 / 1024:.1f} MB")
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 自动清理失败: {e}", exc_info=True)

scheduler.add_job(
    func=auto_cleanup_files,
    trigger=CronTrigger(hour=4, minute=0),
    id='auto_cleanup_files',
    name='自动清理过期文件',
    replace_existing=True
)

# 🗑️ 每天凌晨4点执行：清理24小时前的JSON文件
def auto_cleanup_json_files():
    """清理24小时前的JSON文件"""
    try:
        from pathlib import Path
        
        app.logger.info("🧹 [定时任务] 开始清理过期JSON文件...")
        
        json_dir = Path(__file__).parent / "data" / "push_json"
        if not json_dir.exists():
            app.logger.info("   JSON目录不存在，跳过清理")
            return
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        deleted_count = 0
        
        for json_file in json_dir.rglob("*.json"):
            try:
                mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                if mtime < cutoff_time:
                    json_file.unlink()
                    deleted_count += 1
                    app.logger.info(f"   🗑️ 已删除: {json_file.name}")
            except Exception as e:
                app.logger.warning(f"   删除文件失败 {json_file}: {e}")
        
        # 清理空目录
        for dir_path in sorted(json_dir.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                except:
                    pass
        
        app.logger.info(f"✅ [定时任务] JSON文件清理完成，删除了 {deleted_count} 个文件")
        
    except Exception as e:
        app.logger.error(f"❌ [定时任务] 清理JSON文件失败: {e}", exc_info=True)

scheduler.add_job(
    func=auto_cleanup_json_files,
    trigger=CronTrigger(hour=4, minute=30),  # 凌晨4:30执行，避免与其他清理任务冲突
    id='auto_cleanup_json_files',
    name='清理过期JSON文件',
    replace_existing=True
)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _format_dataframe_result(df: pd.DataFrame, label: str) -> dict:
    table_html = df.to_html(classes="data", header=True, index=False, justify="left")
    row_count, col_count = df.shape
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    csv_base64 = base64.b64encode(csv_bytes).decode("ascii")

    metadata = df.attrs.get("metadata", [])
    report_payload = generate_trade_report(df, metadata)
    report_text = report_payload["text"]
    report_base64 = base64.b64encode(report_text.encode("utf-8-sig")).decode("ascii")

    return {
        "table_html": table_html,
        "row_count": row_count,
        "col_count": col_count,
        "metadata": metadata,
        "csv_data": csv_base64,
        "report_text": report_text,
        "report_data": report_base64,
        "label": label,
    }


@app.route("/")
@app.route("/collect")
def index():
    """主页面 - 采集控制台（新版统一界面）"""
    status = bifaw_client.get_cookie_status()
    response = make_response(render_template("index_new.html", cookie_status=status))
    # 强制禁止浏览器缓存
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route("/old")
def index_old():
    """旧版采集控制台（已合并到数据工作台）"""
    status = bifaw_client.get_cookie_status()
    response = make_response(render_template("index_new.html", cookie_status=status))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route("/backtest")
def backtest_page():
    """批量回测（已合并到数据工作台）"""
    status = bifaw_client.get_cookie_status()
    return render_template("index_new.html", cookie_status=status)


@app.route("/data-manager")
def data_manager_page():
    """📊 数据管理/分析页面"""
    return render_template("data_manager.html")


@app.route("/pdf")
def pdf_page():
    """PDF解析页面"""
    cookie_status = bifaw_client.get_cookie_status()
    return render_template("index.html", cookie_status=cookie_status)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "pdf_file" not in request.files:
        return render_template(
            "index.html",
            error="没有找到文件部分",
            cookie_status=bifaw_client.get_cookie_status(),
        )

    file = request.files["pdf_file"]

    if not file or file.filename == "":
        return render_template(
            "index.html",
            error="没有选择文件",
            cookie_status=bifaw_client.get_cookie_status(),
        )

    if not allowed_file(file.filename):
        return render_template(
            "index.html",
            error="只允许上传 .pdf 文件",
            cookie_status=bifaw_client.get_cookie_status(),
        )

    filename = secure_filename(file.filename)
    file_path = UPLOAD_FOLDER / filename
    file.save(file_path)

    result = parse_bifa_pdf(str(file_path))

    if isinstance(result, pd.DataFrame) and not result.empty:
        payload = _format_dataframe_result(result, file.filename)
        return render_template(
            "index.html",
            table_html=payload["table_html"],
            file_name=file.filename,
            row_count=payload["row_count"],
            col_count=payload["col_count"],
            metadata_json=json.dumps(payload["metadata"], ensure_ascii=False),
            csv_data=payload["csv_data"],
            report_text=payload["report_text"],
            report_data=payload["report_data"],
            cookie_status=bifaw_client.get_cookie_status(),
        )

    error_msg = str(result) if isinstance(result, str) else "未能从PDF中提取到任何数据。"
    return render_template(
        "index.html",
        error=error_msg,
        cookie_status=bifaw_client.get_cookie_status(),
    )


@app.route("/api/bifaw/status")
def api_bifaw_status():
    verify = request.args.get('verify', 'false').lower() == 'true'
    return jsonify(bifaw_client.get_cookie_status(verify=verify))


@app.route("/api/bifaw/captcha", methods=["POST"])
def api_bifaw_captcha():
    try:
        session_id, captcha_b64 = bifaw_client.fetch_captcha()
        return jsonify({"success": True, "session_id": session_id, "captcha": captcha_b64})
    except Exception as exc:
        app.logger.exception("获取验证码失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/bifaw/login", methods=["POST"])
def api_bifaw_login():
    data = request.get_json(force=True)
    session_id = data.get("session_id")
    captcha_text = data.get("captcha", "")

    if not session_id:
        return jsonify({"success": False, "message": "缺少 session_id"}), 400

    ok, payload = bifaw_client.submit_captcha(session_id, captcha_text)
    if ok:
        # 🔥 登录成功，触发后台数据刷新
        app.logger.info("✅ 手动登录成功，触发后台数据刷新...")
        threading.Thread(target=auto_collect_today_matches, daemon=True).start()
        return jsonify({"success": True, "message": payload.get("message", "登录成功")})

    response = {"success": False, "message": payload.get("message", "登录失败")}
    if payload.get("captcha"):
        response["captcha"] = payload["captcha"]
    return jsonify(response)


@app.route("/api/bifaw/auto_login_ocr", methods=["POST"])
def api_bifaw_auto_login_ocr():
    """
    OCR自动登录接口
    页面加载时自动调用，尝试使用百度OCR自动识别验证码并登录
    返回详细日志供前端显示
    """
    logs = []  # 收集日志
    
    try:
        logs.append("🤖 收到OCR自动登录请求")
        app.logger.info("🤖 收到OCR自动登录请求")
        
        # 🔥 使用自定义日志处理器收集日志
        import logging
        from io import StringIO
        
        # 创建字符串流来捕获日志
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        
        # 添加临时处理器
        logger = logging.getLogger('services.bifaw_client')
        logger.addHandler(handler)
        
        try:
            # 尝试OCR自动登录（彩色倾斜验证码识别率约70-80%）
            logs.append("⏳ 正在尝试OCR自动登录（最多5次重试）...")
            success, message = bifaw_client._auto_login_with_ocr(max_retries=5)
            
            # 获取捕获的日志
            log_content = log_stream.getvalue()
            for line in log_content.split('\n'):
                if line.strip():
                    logs.append(line.strip())
            
            if success:
                logs.append("✅ OCR自动登录成功！")
                app.logger.info("✅ OCR自动登录成功")
                
                # 🔥 登录成功，触发后台数据刷新
                app.logger.info("✅ OCR登录成功，触发后台数据刷新...")
                threading.Thread(target=auto_collect_today_matches, daemon=True).start()
                logs.append("🔄 已触发后台数据刷新")
                
                return jsonify({
                    "success": True, 
                    "message": message,
                    "logs": logs,
                    "cookie_status": bifaw_client.get_cookie_status()
                })
            else:
                logs.append(f"⚠️ OCR自动登录失败: {message}")
                logs.append("💡 提示：请手动点击「获取验证码」完成登录")
                app.logger.warning(f"⚠️ OCR自动登录失败: {message}")
                return jsonify({
                    "success": False, 
                    "message": message,
                    "logs": logs
                })
        finally:
            # 移除临时处理器
            logger.removeHandler(handler)
            handler.close()
    
    except Exception as exc:
        logs.append(f"❌ 自动登录异常: {str(exc)}")
        app.logger.exception("OCR自动登录异常")
        return jsonify({
            "success": False, 
            "message": f"自动登录异常: {str(exc)}",
            "logs": logs
        }), 500


@app.route("/api/bifaw/auto_login_ocr_stream", methods=["POST"])
def api_bifaw_auto_login_ocr_stream():
    """OCR 自动登录（SSE 实时日志版）

    - 使用全局 LogStreamHandler 捕获后端日志
    - 通过 SSE 将日志实时推送到前端
    - 结束时返回 success / failed 状态事件
    """
    from utils.log_stream_handler import get_stream_handler
    import json as _json

    def generate():
        log_stream = get_stream_handler()

        # 开启日志捕获
        log_stream.start_capture()

        # 辅助函数：推送并记录日志消息
        def send_log_message(message: str, level: str = "info"):
            # 直接用 app.logger 记录，让 LogStreamHandler 捕获
            if level == "error":
                app.logger.error(message)
            elif level == "warn":
                app.logger.warning(message)
            else:
                app.logger.info(message)

        try:
            # 起始提示
            send_log_message("🤖 收到 OCR 自动登录请求")
            send_log_message("⏳ 正在尝试 OCR 自动登录（最多 5 次重试）...")

            # 先推送当前已有日志（主要是上面两条）
            for msg in log_stream.get_messages():
                yield f"data: {_json.dumps(msg, ensure_ascii=False)}\n\n"
            log_stream.clear()

            # 真正执行 OCR 自动登录
            success, message = bifaw_client._auto_login_with_ocr(max_retries=5)

            # 循环推送过程中产生的日志
            backend_logs = log_stream.get_messages()
            log_stream.clear()
            for msg in backend_logs:
                yield f"data: {_json.dumps(msg, ensure_ascii=False)}\n\n"

            # 最终状态事件
            final_event = {
                "type": "ocr_login_result",
                "success": bool(success),
                "message": message,
            }
            yield f"data: {_json.dumps(final_event, ensure_ascii=False)}\n\n"

        except Exception as exc:
            error_msg = f"OCR 自动登录异常: {exc}"
            app.logger.exception(error_msg)

            backend_logs = log_stream.get_messages()
            log_stream.clear()
            for msg in backend_logs:
                yield f"data: {_json.dumps(msg, ensure_ascii=False)}\n\n"

            final_event = {
                "type": "ocr_login_result",
                "success": False,
                "message": error_msg,
            }
            yield f"data: {_json.dumps(final_event, ensure_ascii=False)}\n\n"

        finally:
            # 结束捕获，但不清空历史，这样其他终端仍可通过 /api/collect/logs 看到日志
            log_stream.stop_capture()

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/bifaw/download", methods=["POST"])
def api_bifaw_download():
    data = request.get_json(force=True)
    url = data.get("url")
    filename = data.get("filename")

    if not url:
        return jsonify({"success": False, "message": "请提供下载链接。"}), 400

    try:
        file_path = bifaw_client.download_file(url, filename)
        parse_result = parse_bifa_pdf(str(file_path))

        if isinstance(parse_result, pd.DataFrame) and not parse_result.empty:
            payload = _format_dataframe_result(parse_result, str(file_path))
            return jsonify(
                {
                    "success": True,
                    "message": f"已下载并解析：{file_path}",
                    "file_path": str(file_path),
                    **payload,
                }
            )

        error_msg = (
            parse_result if isinstance(parse_result, str) else "未能从PDF中提取到任何数据。"
        )
        return jsonify(
            {
                "success": False,
                "message": error_msg,
                "file_path": str(file_path),
            }
        )
    except Exception as exc:
        app.logger.exception("下载或解析 PDF 失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/bifaw/scrape", methods=["POST"])
def api_bifaw_scrape():
    data = request.get_json(force=True)
    url = data.get("url")
    label = data.get("label")

    if not url:
        return jsonify({"success": False, "message": "请提供要抓取的页面 URL。"}), 400

    try:
        html = bifaw_client.fetch_dynamic_page_html(url, wait_text=HEADER_KEYWORDS)
        parse_result = parse_bifa_html(html)

        if isinstance(parse_result, pd.DataFrame) and not parse_result.empty:
            payload = _format_dataframe_result(parse_result, label or url)
            return jsonify(
                {
                    "success": True,
                    "message": "网页解析成功。",
                    "table_html": payload["table_html"],
                    "row_count": payload["row_count"],
                    "col_count": payload["col_count"],
                    "metadata": payload["metadata"],
                    "csv_data": payload["csv_data"],
                    "report_text": payload["report_text"],
                    "report_data": payload["report_data"],
                    "label": payload["label"],
                }
            )

        error_msg = parse_result if isinstance(parse_result, str) else "未解析到数据。"
        return jsonify({"success": False, "message": error_msg})
    except Exception as exc:
        app.logger.exception("网页抓取失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/bifaw/match_detail", methods=["POST"])
def api_bifaw_match_detail():
    data = request.get_json(force=True) or {}
    detail_url = data.get("detail_url")
    match_info = data.get("match") or {}
    detail_params = data.get("detail_params") or match_info.get("detail_params")
    label = data.get("label") or match_info.get("label") or detail_url
    use_selenium = data.get("use_selenium", True)  # 默认使用Selenium方法

    if not detail_url and not match_info:
        return jsonify({"success": False, "message": "请提供 detail_url 或比赛参数。"}), 400

    try:
        parse_result = None
        
        # 调试：打印match_info内容
        app.logger.info(f"[明细抓取] match_info类型: {type(match_info)}")
        if isinstance(match_info, dict):
            app.logger.info(f"[明细抓取] match_info内容: league={match_info.get('league')}, home={match_info.get('home')}, away={match_info.get('away')}, kickoff={match_info.get('kickoff')}")
        
        if use_selenium:
            # 使用Selenium方法抓取，支持新窗口和自动截图
            html = bifaw_client.fetch_match_detail_selenium(
                detail_url=detail_url,
                match=match_info if isinstance(match_info, dict) else None,
                detail_params=detail_params if isinstance(detail_params, dict) else None,
            )
            # 传入match_info以便解析器使用比赛元数据
            parse_result = parse_bifa_html(html, match=match_info if isinstance(match_info, dict) else None)
        else:
            # 使用原有的requests方法（备用）
            response = bifaw_client.fetch_match_detail_response(
                detail_url=detail_url,
                match=match_info if isinstance(match_info, dict) else None,
                detail_params=detail_params if isinstance(detail_params, dict) else None,
            )
            content_type = (response.headers.get("Content-Type") or "").lower()

            if "pdf" in content_type or (detail_url or "").lower().endswith(".pdf"):
                tmp_path: Optional[Path] = None
                try:
                    with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as tmp_file:
                        tmp_file.write(response.content)
                        tmp_path = Path(tmp_file.name)
                    parse_result = parse_bifa_pdf(str(tmp_path))
                finally:
                    if tmp_path and tmp_path.exists():
                        try:
                            tmp_path.unlink()
                        except OSError:
                            pass
            else:
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.apparent_encoding or "utf-8"
                parse_result = parse_bifa_html(response.text, match=match_info if isinstance(match_info, dict) else None)

        if isinstance(parse_result, pd.DataFrame) and not parse_result.empty:
            payload = _format_dataframe_result(parse_result, label or "match_detail")
            return jsonify(
                {
                    "success": True,
                    "message": "标盘明细抓取成功（已自动保存截图到debug目录）。",
                    "table_html": payload["table_html"],
                    "row_count": payload["row_count"],
                    "col_count": payload["col_count"],
                    "metadata": payload["metadata"],
                    "csv_data": payload["csv_data"],
                    "report_text": payload["report_text"],
                    "report_data": payload["report_data"],
                    "label": payload["label"],
                }
            )

        error_msg = parse_result if isinstance(parse_result, str) else "未解析到明细数据。"
        return jsonify({"success": False, "message": error_msg})
    except Exception as exc:
        app.logger.exception("标盘明细抓取失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/bifaw/matches")
def api_bifaw_matches():
    """
    获取标盘明细比赛列表
    
    新增功能：
    1. 捕获真实的matchDetails.php链接（替换sporttery.php）
    2. 批量获取并保存盘口数据到本地
    3. 默认按盘口过滤，只显示500.com有让球盘口的比赛
    4. 支持查询未来比赛（未开始的比赛）
    
    参数：
    - days: 查询过去多少天（默认2天）
    - future_days: 查询未来多少天（默认0天，不查未来）
    - rows: 每天查询多少场比赛（默认9999，实际无限制）
    - filter_by_handicap: 是否按盘口过滤（默认0=关闭，SB有数据的就是主盘口）
    - refresh: 是否强制刷新缓存（默认0=使用缓存）
    """
    refresh = request.args.get("refresh") == "1"
    rows = int(request.args.get("rows", "9999") or 9999)
    days = int(request.args.get("days", "1") or 1)  # 🔥 默认1天（只查今天）
    future_days = int(request.args.get("future_days", "0") or 0)  # 🔥 新增：查询未来天数
    # 🔥 默认关闭盘口过滤，SB有数据的就是主盘口
    filter_by_handicap = request.args.get("filter_by_handicap", "0") == "1"
    matches: List[Dict[str, object]] = []
    
    try:
        matches = bifaw_client.fetch_match_list_v2(rows=rows, days=days, future_days=future_days, force_refresh=refresh)
    except Exception as exc:
        app.logger.warning("serveodds 获取场次失败，将回退到页面解析：%s", exc)
    if not matches:
        try:
            # fetch_match_list 内部已包含链接捕获，无需重复
            matches = bifaw_client.fetch_match_list(force_refresh=refresh)
        except Exception as exc:
            app.logger.exception("获取场次列表失败")
            return jsonify({"success": False, "message": str(exc)}), 500
    
    # 🔥 重要：替换sporttery.php为matchDetails.php（真实完整数据链接）
    # 检查是否需要替换（有sporttery.php链接才需要）
    need_replace = any('sporttery.php' in match.get('detail_url', '') for match in matches)
    
    if matches and need_replace:
        # 使用已有的fetch_match_list函数（内部已包含链接捕获逻辑）
        try:
            app.logger.info(f"\n{'='*80}")
            app.logger.info(f"🔗 替换sporttery.php为matchDetails.php（完整数据链接）")
            app.logger.info(f"{'='*80}")
            
            # 调用fetch_match_list获取真实链接（会自动使用缓存，60秒有效）
            matches_with_real_url = bifaw_client.fetch_match_list(force_refresh=refresh, capture_real_urls=True)
            
            if matches_with_real_url:
                # 构建映射：主队_客队 -> detail_url
                real_url_map = {}
                for m in matches_with_real_url:
                    key = f"{m.get('home')}_{m.get('away')}"
                    if 'matchDetails.php' in m.get('detail_url', ''):
                        real_url_map[key] = m.get('detail_url')
                
                # 替换原有比赛列表中的链接
                replaced_count = 0
                for match in matches:
                    match_key = f"{match.get('home')}_{match.get('away')}"
                    if match_key in real_url_map:
                        old_url = match.get('detail_url', '')
                        match['detail_url'] = real_url_map[match_key]
                        if 'sporttery.php' in old_url:
                            replaced_count += 1
                            app.logger.info(f"  ✓ 已替换: {match.get('home')} vs {match.get('away')}")
                
                if replaced_count > 0:
                    app.logger.info(f"\n✅ 共替换 {replaced_count} 个链接（sporttery.php → matchDetails.php）")
                else:
                    app.logger.warning(f"⚠️  未找到可替换的链接（可能都是matchDetails.php）")
            
            app.logger.info(f"{'='*80}\n")
        
        except Exception as e:
            app.logger.warning(f"链接替换失败（将使用原有链接）: {e}")
    
    # 🔥 新增：批量获取并保存盘口数据
    if matches:
        try:
            from datetime import datetime, timedelta
            from pathlib import Path
            import json
            
            app.logger.info(f"\n{'='*80}")
            app.logger.info(f"🎯 批量获取盘口数据（用于后续生成推荐）")
            app.logger.info(f"{'='*80}")
            
            # 按日期分组
            matches_by_date = {}
            for match in matches:
                kickoff = match.get('kickoff', '')
                if kickoff and ' ' in kickoff:
                    match_date = kickoff.split(' ')[0]
                    if match_date not in matches_by_date:
                        matches_by_date[match_date] = []
                    matches_by_date[match_date].append(match)
            
            # 🔥 为每个日期批量获取盘口数据（按年/月/日目录结构保存）
            total_saved = 0
            for match_date, date_matches in matches_by_date.items():
                app.logger.info(f"  📥 获取 {match_date} 的盘口数据（{len(date_matches)}场比赛）...")
                
                try:
                    # 🔥 智能日期判断：凌晨0-8点的比赛也需要获取前一天的盘口数据
                    dates_to_fetch = [match_date]
                    
                    # 检查是否有凌晨比赛
                    has_early_morning = any(
                        ' ' in m.get('kickoff', '') and 
                        0 <= int(m.get('kickoff', '').split(' ')[1].split(':')[0]) < 8
                        for m in date_matches
                    )
                    
                    if has_early_morning:
                        from datetime import datetime as dt_class, timedelta
                        current_date = dt_class.strptime(match_date, '%Y-%m-%d')
                        previous_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
                        dates_to_fetch = [previous_date, match_date]
                        app.logger.info(f"  ⏰ 检测到凌晨比赛，将获取 {previous_date} 和 {match_date} 的盘口")
                    
                    # 获取所有需要的日期的盘口数据
                    for fetch_date in dates_to_fetch:
                        date_parts = fetch_date.split('-')
                        year, month, day = date_parts[0], date_parts[1], date_parts[2]
                        
                        # 构建目录路径
                        handicaps_dir = BASE_DIR / "data" / year / month / day
                        handicaps_dir.mkdir(parents=True, exist_ok=True)
                        
                        # 🔥 获取盘口数据（使用use_cache=False强制重新抓取）
                        daily_handicaps = lottery500_client.fetch_daily_handicaps(fetch_date, use_cache=False)
                        
                        if daily_handicaps:
                            app.logger.info(f"  ✅ {fetch_date}: 获取并保存 {len(daily_handicaps)} 场盘口数据")
                            app.logger.info(f"     保存路径: data/{year}/{month}/{day}/盘口数据.json")
                            total_saved += len(daily_handicaps)
                        else:
                            app.logger.warning(f"  ⚠️  {fetch_date}: 未获取到盘口数据")
                
                except Exception as e:
                    app.logger.warning(f"  ⚠️  {match_date}: 盘口数据获取失败 - {e}")
            
            if total_saved > 0:
                app.logger.info(f"\n✅ 盘口数据预加载完成！共保存 {total_saved} 场比赛的盘口数据")
            app.logger.info(f"{'='*80}\n")
        
        except Exception as e:
            app.logger.warning(f"盘口数据预加载失败（不影响比赛列表）: {e}")
    
    # 🔥 盘口匹配：为所有比赛匹配盘口数据（无论是否过滤）
    filtered_matches = matches
    filtered_count = 0
    
    if matches:  # 🔥 改为始终获取盘口，不再判断 filter_by_handicap
        app.logger.info(f"\n{'='*80}")
        if filter_by_handicap:
            app.logger.info(f"🎯 盘口匹配模式：匹配盘口并过滤（只显示有盘口的比赛）")
        else:
            app.logger.info(f"🎯 盘口匹配模式：匹配盘口但不过滤（显示所有比赛）")
        app.logger.info(f"{'='*80}")
        
        try:
            # 按日期分组过滤
            final_matches = []
            matches_by_date = {}
            
            # 先按日期分组
            for match in matches:
                kickoff = match.get('kickoff', '')
                if kickoff and ' ' in kickoff:
                    match_date = kickoff.split(' ')[0]
                    if match_date not in matches_by_date:
                        matches_by_date[match_date] = []
                    matches_by_date[match_date].append(match)
            
            # 对每个日期进行盘口匹配
            for match_date, date_matches in matches_by_date.items():
                app.logger.info(f"\n📅 处理 {match_date} 的比赛...")
                
                try:
                    # 🔥 智能日期判断：凌晨0-8点的比赛优先从前一天查找盘口
                    search_dates = [match_date]  # 默认使用比赛当天
                    
                    # 检查是否有凌晨比赛（0-8点）
                    has_early_morning_match = False
                    for match in date_matches:
                        kickoff = match.get('kickoff', '')
                        if ' ' in kickoff:
                            time_part = kickoff.split(' ')[1]  # HH:MM
                            hour = int(time_part.split(':')[0])
                            if 0 <= hour < 8:
                                has_early_morning_match = True
                                break
                    
                    # 如果有凌晨比赛，优先尝试前一天的盘口数据
                    if has_early_morning_match:
                        from datetime import datetime as dt_class, timedelta
                        current_date = dt_class.strptime(match_date, '%Y-%m-%d')
                        previous_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
                        search_dates = [previous_date, match_date]  # 先查前一天，再查当天
                        app.logger.info(f"  ⏰ 检测到凌晨比赛，将从 {previous_date} 和 {match_date} 查找盘口")
                    
                    # 按顺序尝试获取盘口数据
                    daily_handicaps = {}
                    for search_date in search_dates:
                        app.logger.info(f"  🔍 正在获取 {search_date} 的盘口数据...")
                        temp_handicaps = lottery500_client.fetch_daily_handicaps(search_date, use_cache=True)
                        
                        if temp_handicaps:
                            app.logger.info(f"  ✅ 从 {search_date} 获取到 {len(temp_handicaps)} 场盘口数据")
                            daily_handicaps.update(temp_handicaps)  # 合并盘口数据
                        else:
                            app.logger.info(f"  ℹ️  {search_date}: 未获取到盘口数据")
                    
                    app.logger.info(f"  📊 合并结果: {len(daily_handicaps)} 场盘口数据")
                    
                    if not daily_handicaps:
                        app.logger.warning(f"  ⚠️  {match_date}: 所有尝试均未获取到盘口数据")
                        # 🔥 即使没有盘口数据，也要处理这些比赛（如果不过滤）
                        if not filter_by_handicap:
                            app.logger.info(f"  ℹ️  非过滤模式：添加 {len(date_matches)} 场比赛（无盘口信息）")
                            for match in date_matches:
                                final_matches.append(match)
                        continue
                    
                    app.logger.info(f"  ✅ 500.com找到 {len(daily_handicaps)} 场有盘口的比赛")
                    
                    # 为每场比赛匹配盘口
                    matched_count = 0
                    
                    # 🔥 调试：打印前几个盘口和比赛样例
                    if len(daily_handicaps) > 0 and len(date_matches) > 0:
                        first_handicap = list(daily_handicaps.values())[0]
                        first_match = date_matches[0]
                        app.logger.info(f"  🔍 盘口样例: {first_handicap.get('home_team')} vs {first_handicap.get('away_team')}")
                        app.logger.info(f"  🔍 比赛样例: {first_match.get('home')} vs {first_match.get('away')}")
                    
                    for match in date_matches:
                        home = match.get('home', '')
                        away = match.get('away', '')
                        kickoff_time = match.get('kickoff', '').split(' ')[1] if ' ' in match.get('kickoff', '') else ''
                        
                        # 尝试精确匹配
                        handicap_match = None
                        # 🔥 daily_handicaps 是字典，需要遍历 .values()
                        for h in daily_handicaps.values():
                            # 500.com 返回的字段是 home_team 和 away_team
                            h_home = h.get('home_team', h.get('home', ''))
                            h_away = h.get('away_team', h.get('away', ''))
                            
                            if h_home == home and h_away == away:
                                # 如果有时间，进一步验证
                                if kickoff_time:
                                    h_time = h.get('time', '')
                                    if h_time and h_time == kickoff_time:
                                        handicap_match = h
                                        break
                                else:
                                    handicap_match = h
                                    break
                        
                        # 如果精确匹配失败，尝试模糊匹配
                        if not handicap_match:
                            from services.lottery500_client import similarity_ratio
                            best_score = 0
                            best_match = None
                            
                            # 🔥 daily_handicaps 是字典，需要遍历 .values()
                            for h in daily_handicaps.values():
                                # 500.com 返回的字段是 home_team 和 away_team
                                h_home = h.get('home_team', h.get('home', ''))
                                h_away = h.get('away_team', h.get('away', ''))
                                
                                # 计算队名相似度
                                home_sim = similarity_ratio(home, h_home)
                                away_sim = similarity_ratio(away, h_away)
                                avg_sim = (home_sim + away_sim) / 2
                                
                                if avg_sim > best_score and avg_sim >= 0.7:  # 相似度阈值70%
                                    best_score = avg_sim
                                    best_match = h
                            
                            if best_match:
                                handicap_match = best_match
                                best_home = best_match.get('home_team', best_match.get('home', ''))
                                best_away = best_match.get('away_team', best_match.get('away', ''))
                                app.logger.info(f"    🔗 模糊匹配: {home} vs {away} → {best_home} vs {best_away} (相似度: {best_score:.1%})")
                        
                        # 🔥 为所有比赛设置盘口信息
                        if handicap_match:
                            # 找到盘口，设置 handicap_preview
                            handicap_str = handicap_match.get('current_handicap_str', handicap_match.get('handicap_str', ''))
                            handicap_value = handicap_match.get('current_handicap', handicap_match.get('handicap', 0))
                            
                            match['handicap_preview'] = {
                                'handicap': handicap_value,
                                'handicap_str': handicap_str if handicap_str else f"O{handicap_value if handicap_value else '无'}",
                                'home': handicap_match.get('home_team', handicap_match.get('home', '')),
                                'away': handicap_match.get('away_team', handicap_match.get('away', ''))
                            }
                            # 保留原字段以兼容
                            match['handicap'] = handicap_value
                            match['handicap_home'] = handicap_match.get('home_team', handicap_match.get('home', ''))
                            match['handicap_away'] = handicap_match.get('away_team', handicap_match.get('away', ''))
                            matched_count += 1
                        
                        # 🔥 尝试从缓存读取总交易额
                        try:
                            cached = detail_cache_manager.load_detail(match)
                            if cached:
                                trade_df, _, _ = cached
                                if not trade_df.empty:
                                    latest_record = trade_df.iloc[0]
                                    total_vol_str = latest_record.get('总成交量', '0')
                                    total_vol = float(str(total_vol_str).replace(',', ''))
                                    match['total_volume'] = total_vol
                        except:
                            pass
                        
                        # 🔥 根据 filter_by_handicap 决定是否添加
                        if filter_by_handicap:
                            # 过滤模式：只添加有盘口的比赛
                            if handicap_match:
                                final_matches.append(match)
                        else:
                            # 非过滤模式：添加所有比赛（无论是否有盘口）
                            final_matches.append(match)
                    
                    if filter_by_handicap:
                        app.logger.info(f"  ✅ {match_date}: 匹配到 {matched_count}/{len(date_matches)} 场有盘口的比赛（过滤模式）")
                    else:
                        app.logger.info(f"  ✅ {match_date}: 处理 {len(date_matches)} 场比赛，{matched_count} 场有盘口，{len(date_matches)-matched_count} 场无盘口")
                    
                    # 🔥 调试：打印前几场比赛的盘口信息
                    if matched_count > 0 and len(final_matches) > 0:
                        sample_match = final_matches[-1]  # 最后一场匹配的比赛
                        if 'handicap_preview' in sample_match:
                            app.logger.info(f"     示例盘口: {sample_match.get('home')} vs {sample_match.get('away')} - {sample_match['handicap_preview'].get('handicap_str')}")
                    
                    filtered_count += matched_count
                
                except Exception as e:
                    app.logger.warning(f"  ⚠️  {match_date}: 盘口匹配失败 - {e}")
            
            filtered_matches = final_matches
            
            if filter_by_handicap:
                # 过滤模式：显示过滤结果
                if filtered_count > 0:
                    app.logger.info(f"\n✅ 盘口过滤完成：保留 {filtered_count}/{len(matches)} 场有盘口的比赛")
                else:
                    app.logger.warning(f"\n⚠️  未找到有盘口的比赛")
            else:
                # 非过滤模式：显示匹配结果
                app.logger.info(f"\n✅ 盘口匹配完成：共 {len(final_matches)} 场比赛，其中 {filtered_count} 场有盘口数据")
            
            app.logger.info(f"{'='*80}\n")
        
        except Exception as e:
            app.logger.error(f"盘口过滤失败（返回所有比赛）: {e}")
            filtered_matches = matches
    
    # 🆕 保存标盘场次快照
    try:
        import os
        import json
        from datetime import datetime
        
        # 保存今天和明天的快照
        save_dates = set()
        for match in filtered_matches:
            kickoff = match.get('kickoff', '')
            if kickoff and ' ' in kickoff:
                match_date = kickoff.split(' ')[0]
                save_dates.add(match_date)
        
        for date_str in save_dates:
            year, month, day = date_str.split('-')
            save_dir = BASE_DIR / 'data' / year / month / day
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 筛选该日期的比赛
            date_matches = [m for m in filtered_matches if date_str in m.get('kickoff', '')]
            
            # 生成时间戳
            now = datetime.now()
            timestamp = now.strftime('%H:%M')
            
            # 保存快照（带时间戳）
            snapshot_file = save_dir / f'标盘指数_{timestamp}.json'
            snapshot_data = {
                'query_date': date_str,
                'crawl_time': now.isoformat(),
                'snapshot_type': 'auto',
                'total_matches': len(date_matches),
                'filter_enabled': filter_by_handicap,
                'matches': date_matches
            }
            
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
            
            # 同时保存到 latest.json（覆盖）
            latest_file = save_dir / '标盘指数_latest.json'
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
            
            app.logger.info(f"✅ 已保存标盘快照: {date_str} ({len(date_matches)}场) -> {timestamp}")
    
    except Exception as save_error:
        app.logger.warning(f"保存标盘快照失败: {save_error}")
    
    return jsonify({
        "success": True,
        "matches": filtered_matches,
        "count": len(filtered_matches),
        "original_count": len(matches),
        "total_count": len(matches),  # 🔥 添加此字段以匹配前端期望
        "filtered": filter_by_handicap,
        "filtered_count": filtered_count,
        "filter_enabled": filter_by_handicap
    })


@app.route("/api/bifaw/matches_from_biaopan")
def api_bifaw_matches_from_biaopan():
    """
    🆕 直接从本地盘口数据文件读取比赛列表（绕过必发网API）
    
    优点：
    - 不依赖必发网API
    - 不需要队名匹配
    - 显示所有有盘口的比赛（包括凌晨比赛）
    """
    from datetime import datetime
    import json
    
    try:
        # 读取昨天、今天和明天的盘口数据文件（凌晨比赛可能在昨天的文件中）
        now = datetime.now()
        dates = [
            (now - timedelta(days=1)).strftime("%Y/%m/%d"),  # 昨天
            now.strftime("%Y/%m/%d"),                         # 今天
            (now + timedelta(days=1)).strftime("%Y/%m/%d")    # 明天
        ]
        
        all_matches = []
        
        for date_str in dates:
            year, month, day = date_str.split('/')
            # 🔥 改为读取盘口数据文件
            handicap_file = BASE_DIR / 'data' / year / month / day / "盘口数据.json"
            
            if handicap_file.exists():
                try:
                    with open(handicap_file, 'r', encoding='utf-8') as f:
                        handicap_data = json.load(f)
                    
                    app.logger.info(f"📂 从 {date_str} 盘口数据文件读取到 {len(handicap_data)} 场比赛")
                    
                    # 转换为前端期望的格式，并过滤出未来的比赛
                    for key, match in handicap_data.items():
                        time_str = match.get('time', '')
                        
                        # 🔥 构造完整时间并过滤未来比赛
                        if time_str:
                            try:
                                match_datetime_str = f"{date_str.replace('/', '-')} {time_str}"
                                kickoff_time = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M")
                                
                                # 只保留未来30分钟内或更晚开始的比赛
                                if kickoff_time > now - timedelta(minutes=30):
                                    fid = match.get('fid', '')
                                    home = match.get('home_team', '')
                                    away = match.get('away_team', '')
                                    
                                    all_matches.append({
                                        'match_id': fid,
                                        'league': '未知联赛',  # 盘口数据没有联赛信息
                                        'kickoff': match_datetime_str,
                                        'home': home,
                                        'away': away,
                                        'label': f"{match_datetime_str} {home} vs {away}",
                                        'detail_url': '',  # 需要从必发网获取
                                        'type': '1',
                                        'oddstype': '1',
                                        'subtype': '12',
                                        'detail_params': {},
                                        'handicap_preview': {
                                            'handicap_str': match.get('current_handicap_str', ''),
                                            'handicap': match.get('current_handicap', 0)
                                        }
                                    })
                            except ValueError:
                                pass  # 时间解析失败，跳过
                    
                except Exception as e:
                    app.logger.warning(f"读取 {date_str} 盘口数据文件失败: {e}")
        
        # 按时间排序
        all_matches.sort(key=lambda x: x['kickoff'])
        
        app.logger.info(f"✅ 共从盘口数据文件读取到 {len(all_matches)} 场未来比赛")
        
        return jsonify({
            "success": True,
            "matches": all_matches,
            "count": len(all_matches),
            "total_count": len(all_matches),
            "filtered": False,
            "filtered_count": len(all_matches),
            "filter_enabled": False,
            "source": "盘口数据文件"
        })
        
    except Exception as exc:
        app.logger.exception("从盘口数据文件读取失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/bifaw/finished_matches", methods=["POST"])
def api_bifaw_finished_matches():
    """
    获取指定日期的已完场比赛列表
    
    新增功能：可以按盘口数据过滤，只返回500.com有让球盘口的比赛
    """
    from datetime import datetime
    import sys
    
    # 🔥 强制刷新输出缓冲区并立即输出
    import sys
    import time
    
    sys.stdout.write(f"\n{'#'*80}\n")
    sys.stdout.write(f"# 收到查询完场比赛请求 - {time.strftime('%H:%M:%S')}\n")
    sys.stdout.write(f"{'#'*80}\n")
    sys.stdout.flush()
    
    data = request.get_json(force=True) or {}
    date_str = data.get("date")  # 格式: YYYY-MM-DD
    rows = int(data.get("rows", 9999) or 9999)
    filter_by_handicap = data.get("filter_by_handicap", False)  # 是否按盘口过滤
    
    sys.stdout.write(f"请求参数: date={date_str}, rows={rows}, filter_by_handicap={filter_by_handicap}\n")
    sys.stdout.flush()
    
    if not date_str:
        return jsonify({"success": False, "message": "请提供查询日期（格式：YYYY-MM-DD）"}), 400
    
    try:
        # 解析日期字符串
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "message": "日期格式错误，请使用 YYYY-MM-DD 格式"}), 400
    
    try:
        # 1. 获取必发网的完场比赛
        import sys
        print(f"\n{'='*80}")
        print(f"[完场回查] 查询日期: {date_str}")
        print(f"{'='*80}")
        sys.stdout.flush()
        
        try:
            print(f"开始调用 bifaw_client.fetch_finished_matches...")
            sys.stdout.flush()
            
            # 🔧 修复：fetch_finished_matches 返回元组 (page_html, matches, metadata)
            page_html, matches, metadata = bifaw_client.fetch_finished_matches(target_date=target_date, rows=rows)
            
            print(f"✅ 必发网返回: {len(matches)} 场比赛")
            sys.stdout.flush()
            app.logger.info(f"完场回查：{date_str} 返回 {len(matches)} 场比赛")
        except Exception as e:
            print(f"❌ 必发网API请求失败: {type(e).__name__} - {str(e)}")
            sys.stdout.flush()
            raise Exception(f"必发网API请求失败: {str(e)}") from e
        
        # 如果没有数据，返回更详细的提示
        if not matches:
            return jsonify({
                "success": False,
                "message": f"未找到 {date_str} 的完场比赛数据。可能原因：1) 该日期没有比赛 2) 登录状态失效，请重新登录 3) 网站数据暂未更新",
                "matches": [],
                "date": date_str,
                "count": 0,
                "filtered_count": 0,
            })
        
        # 2. 如果开启盘口过滤，显示所有有盘口和明细的比赛
        filtered_matches = matches
        filtered_count = 0
        
        if filter_by_handicap:
            import sys
            print(f"\n🎯 开启盘口过滤，反转匹配逻辑：从500.com盘口列表出发...")
            sys.stdout.flush()
            app.logger.info(f"🎯 开启盘口过滤，反转匹配逻辑：从500.com盘口列表出发...")
            
            # 🔥 反转逻辑：从500.com获取所有有盘口的比赛作为主列表
            try:
                print(f"开始调用 lottery500_client.fetch_daily_handicaps...")
                sys.stdout.flush()
                
                # 🔥 强制实时获取，不使用缓存
                daily_handicaps = lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
                
                print(f"  ✅ 500.com找到 {len(daily_handicaps)} 场有盘口的比赛")
                sys.stdout.flush()
                app.logger.info(f"  ✅ 500.com找到 {len(daily_handicaps)} 场有盘口的比赛")
            except Exception as e:
                print(f"❌ 500.com盘口数据获取失败: {type(e).__name__} - {str(e)}")
                sys.stdout.flush()
                raise Exception(f"500.com盘口数据获取失败: {str(e)}") from e
            
            # 构建必发网比赛的快速查找字典（用于反向匹配）
            print(f"\n📝 构建必发网比赛查找索引...")
            sys.stdout.flush()
            
            bifaw_match_map = {}
            for idx, match in enumerate(matches, 1):
                home = match.get('home_team', '') or match.get('home', '')
                away = match.get('away_team', '') or match.get('away', '')
                time = match.get('match_time', '') or match.get('kickoff', '')
                
                # 清理队名用于匹配
                home_clean = lottery500_client._clean_team_name(home)
                away_clean = lottery500_client._clean_team_name(away)
                
                # 提取时间（HH:MM）
                if ' ' in time:
                    time_str = time.split(' ')[1][:5]
                else:
                    time_str = time[:5] if time else ''
                
                # 构建多种可能的key
                key1 = f"{home_clean}_{away_clean}_{time_str}"
                key2 = f"{home}_{away}_{time_str}"
                
                bifaw_match_map[key1] = match
                bifaw_match_map[key2] = match
                
                if idx % 20 == 0:
                    print(f"  处理中... {idx}/{len(matches)}")
                    sys.stdout.flush()
            
            print(f"  ✅ 索引构建完成：{len(matches)} 场比赛 → {len(bifaw_match_map)} 个匹配key")
            sys.stdout.flush()
            app.logger.info(f"  📋 必发网返回 {len(matches)} 场比赛，构建了 {len(bifaw_match_map)} 个匹配key")
            
            if daily_handicaps:
                # 🔥 遍历500.com的盘口列表，为每场比赛尝试找到必发网的明细
                filtered_matches = []
                
                total_handicaps = len(daily_handicaps)
                print(f"\n🔄 开始匹配盘口和明细，总计 {total_handicaps} 场...")
                
                for idx, (match_key, handicap_data) in enumerate(daily_handicaps.items(), 1):
                    home_500 = handicap_data['home_team']
                    away_500 = handicap_data['away_team']
                    time_500 = handicap_data['time'][:5]  # HH:MM
                    
                    # 清理队名用于匹配
                    home_clean = lottery500_client._clean_team_name(home_500)
                    away_clean = lottery500_client._clean_team_name(away_500)
                    
                    # 尝试多种key匹配必发网的比赛
                    bifaw_match = None
                    for key in [
                        f"{home_clean}_{away_clean}_{time_500}",
                        f"{home_500}_{away_500}_{time_500}",
                    ]:
                        if key in bifaw_match_map:
                            bifaw_match = bifaw_match_map[key]
                            break
                    
                    # 如果没有精确匹配，尝试模糊匹配（允许时间±15分钟误差）
                    if not bifaw_match:
                        from services.lottery500_client import similarity_ratio
                        best_score = 0
                        
                        for match in matches:
                            home_bifaw = match.get('home_team', '') or match.get('home', '')
                            away_bifaw = match.get('away_team', '') or match.get('away', '')
                            time_bifaw = match.get('match_time', '') or match.get('kickoff', '')
                            
                            # 提取时间
                            if ' ' in time_bifaw:
                                time_bifaw_str = time_bifaw.split(' ')[1][:5]
                            else:
                                time_bifaw_str = time_bifaw[:5] if time_bifaw else ''
                            
                            # 计算时间差（分钟）
                            try:
                                h1, m1 = map(int, time_500.split(':'))
                                h2, m2 = map(int, time_bifaw_str.split(':'))
                                time_diff = abs((h1 * 60 + m1) - (h2 * 60 + m2))
                            except:
                                time_diff = 999
                            
                            # 时间必须接近（±15分钟）
                            if time_diff > 15:
                                continue
                            
                            # 计算队名相似度
                            home_sim = similarity_ratio(home_clean, lottery500_client._clean_team_name(home_bifaw))
                            away_sim = similarity_ratio(away_clean, lottery500_client._clean_team_name(away_bifaw))
                            
                            score = home_sim * 50 + away_sim * 50
                            if time_diff == 0:
                                score += 50
                            
                            if score > best_score and score >= 60:
                                best_score = score
                                bifaw_match = match
                    
                    # 如果找到了必发网的明细，添加到结果列表
                    if bifaw_match:
                        # 构造一个合并的比赛数据
                        merged_match = bifaw_match.copy()
                        merged_match['handicap_preview'] = {
                            'handicap_str': handicap_data['current_handicap_str'],
                            'handicap': handicap_data['current_handicap'],
                            'fid': handicap_data['fid']
                        }
                        
                        # 🔥 调试：打印匹配详情
                        bifaw_home = bifaw_match.get('home_team', '') or bifaw_match.get('home', '')
                        bifaw_away = bifaw_match.get('away_team', '') or bifaw_match.get('away', '')
                        print(f"  🔗 匹配详情: 500.com「{home_500} vs {away_500}」→ 必发网「{bifaw_home} vs {bifaw_away}」盘口={handicap_data['current_handicap_str']}({handicap_data['current_handicap']})")
                        sys.stdout.flush()
                        
                        # 🔥 尝试从缓存读取总交易额
                        try:
                            cached = detail_cache_manager.load_detail(bifaw_match)
                            if cached:
                                trade_df, _, _ = cached
                                if not trade_df.empty:
                                    latest_record = trade_df.iloc[0]
                                    total_vol_str = latest_record.get('总成交量', '0')
                                    total_vol = float(str(total_vol_str).replace(',', ''))
                                    merged_match['total_volume'] = total_vol
                        except:
                            pass
                        
                        filtered_matches.append(merged_match)
                        filtered_count += 1
                        print(f"  ✅ [{idx}/{total_handicaps}] {time_500} {home_500} vs {away_500} (盘口: {handicap_data['current_handicap_str']}) - 匹配成功")
                        sys.stdout.flush()
                    else:
                        print(f"  ⚠️  [{idx}/{total_handicaps}] {time_500} {home_500} vs {away_500} - 未找到必发网明细")
                        sys.stdout.flush()
                
                print(f"  ✅ 匹配完成：500.com {len(daily_handicaps)}场 → 成功匹配 {filtered_count} 场（既有盘口又有明细）")
                print(f"{'='*80}\n")
                app.logger.info(f"  ✅ 匹配完成：500.com {len(daily_handicaps)}场 → 成功匹配 {filtered_count} 场（既有盘口又有明细）")
        
        # 🆕 统计总交易额覆盖率（数据已经包含在比赛中）
        matches_to_save = filtered_matches if filter_by_handicap else matches
        total_with_volume = sum(1 for m in matches_to_save if 'total_volume' in m and m['total_volume'] > 0)
        
        if total_with_volume > 0:
            print(f"\n💰 总交易额数据: {total_with_volume}/{len(matches_to_save)} 场比赛")
            sys.stdout.flush()
            app.logger.info(f"✅ 总交易额数据覆盖率: {total_with_volume}/{len(matches_to_save)} 场比赛")
        
        # 🆕 保存完场回查页面和数据
        try:
            import os
            import json
            
            # 🔧 修复：使用 BASE_DIR 确保路径正确
            # 创建日期目录（基于 app.py 所在目录）
            save_dir = BASE_DIR / "data" / str(target_date.year) / f"{target_date.month:02d}" / f"{target_date.day:02d}"
            save_dir.mkdir(parents=True, exist_ok=True)
            save_dir = str(save_dir)  # 转换为字符串以兼容后续代码
            
            print(f"\n💾 保存完场回查页面...")
            print(f"  📂 保存目录: {os.path.abspath(save_dir)}")
            sys.stdout.flush()
            
            # 🔧 调试：检查page_html的值
            print(f"  🔍 page_html类型: {type(page_html)}")
            print(f"  🔍 page_html长度: {len(page_html) if page_html else 0}")
            sys.stdout.flush()
            
            # 1. 保存完场回查HTML
            if page_html:
                html_path = os.path.join(save_dir, "完场回查.html")
                abs_html_path = os.path.abspath(html_path)
                
                print(f"  📝 准备写入: {abs_html_path}")
                sys.stdout.flush()
                
                # 🔥 已禁用备份功能，直接覆盖旧文件
                
                try:
                    with open(html_path, 'w', encoding='utf-8') as f:
                        # 如果是JSON响应，包装成HTML
                        if page_html.strip().startswith('{') or page_html.strip().startswith('['):
                            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>完场回查 - {date_str}</title>
</head>
<body>
    <h1>完场回查数据</h1>
    <p>查询日期: {date_str}</p>
    <pre>{page_html}</pre>
</body>
</html>"""
                            f.write(html_content)
                        else:
                            f.write(page_html)
                    
                    # 验证文件是否真的被写入
                    if os.path.exists(html_path):
                        file_size = os.path.getsize(html_path)
                        print(f"  ✅ 完场回查.html 已保存（{file_size} 字节）")
                        print(f"     文件位置: {abs_html_path}")
                    else:
                        print(f"  ❌ 文件写入失败：文件不存在")
                    sys.stdout.flush()
                    
                except Exception as write_error:
                    print(f"  ❌ 写入HTML文件失败: {write_error}")
                    import traceback
                    print(traceback.format_exc())
                    sys.stdout.flush()
            else:
                print(f"  ⚠️  page_html为空，跳过HTML保存")
                sys.stdout.flush()
            
            # 2. 保存完场回查JSON
            json_data = {
                'query_date': date_str,
                'crawl_time': datetime.now().isoformat(),
                'total_matches': len(matches),
                'filtered_matches': len(filtered_matches),
                'filter_enabled': filter_by_handicap,
                'metadata': metadata,
                'matches': filtered_matches if filter_by_handicap else matches
            }
            
            json_path = os.path.join(save_dir, "完场回查.json")
            abs_json_path = os.path.abspath(json_path)
            
            print(f"  📝 准备写入JSON: {abs_json_path}")
            sys.stdout.flush()
            
            try:
                # 🔥 已禁用备份功能，直接覆盖旧文件
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                
                # 验证文件是否真的被写入
                if os.path.exists(json_path):
                    file_size = os.path.getsize(json_path)
                    print(f"  ✅ 完场回查.json 已保存（{file_size} 字节）")
                    print(f"     文件位置: {abs_json_path}")
                else:
                    print(f"  ❌ JSON文件写入失败：文件不存在")
                sys.stdout.flush()
                
            except Exception as json_error:
                print(f"  ❌ 写入JSON文件失败: {json_error}")
                import traceback
                print(traceback.format_exc())
                sys.stdout.flush()
            
            print(f"  📂 最终保存位置: {os.path.abspath(save_dir)}")
            print(f"{'='*80}\n")
            sys.stdout.flush()
            
            app.logger.info(f"✅ 完场回查页面已保存: {save_dir}")
            
        except Exception as save_error:
            print(f"  ⚠️  保存完场回查页面失败: {save_error}")
            import traceback
            print(f"完整错误堆栈:")
            print(traceback.format_exc())
            sys.stdout.flush()
            app.logger.warning(f"保存完场回查页面失败: {save_error}")
        
        # 🔥 新增：检查每场比赛是否已有本地JSON数据
        print(f"\n🔍 检查本地数据缓存...")
        sys.stdout.flush()
        
        for match in filtered_matches:
            try:
                # 检查是否有缓存
                has_cache = detail_cache_manager.has_cache(match)
                match['has_local_data'] = has_cache
                
                if has_cache:
                    # 尝试读取缓存以获取更多信息
                    try:
                        cached = detail_cache_manager.load_detail(match)
                        if cached:
                            trade_df, handicap_data, metadata = cached
                            match['local_data_rows'] = len(trade_df) if isinstance(trade_df, pd.DataFrame) else 0
                            match['has_handicap_data'] = bool(handicap_data)
                    except:
                        pass
            except:
                match['has_local_data'] = False
        
        local_data_count = sum(1 for m in filtered_matches if m.get('has_local_data'))
        print(f"  ✅ 已缓存数据: {local_data_count}/{len(filtered_matches)} 场比赛")
        sys.stdout.flush()
        app.logger.info(f"  ✅ 本地数据覆盖率: {local_data_count}/{len(filtered_matches)} 场比赛")
        
        return jsonify({
            "success": True,
            "matches": filtered_matches,
            "date": date_str,
            "count": len(filtered_matches),
            "original_count": len(matches) if filter_by_handicap else None,
            "filtered": filter_by_handicap,
            "filtered_count": filtered_count if filter_by_handicap else None,
            "local_data_count": local_data_count,  # 🔥 新增：已缓存数据数量
        })
    except Exception as exc:
        import traceback
        error_traceback = traceback.format_exc()
        
        # 详细的错误日志
        print(f"\n{'='*80}")
        print(f"❌ 获取完场比赛列表失败")
        print(f"{'='*80}")
        print(f"错误类型: {type(exc).__name__}")
        print(f"错误信息: {str(exc)}")
        print(f"\n完整堆栈跟踪:")
        print(error_traceback)
        print(f"{'='*80}\n")
        
        app.logger.exception("获取完场比赛列表失败")
        
        # 返回更详细的错误信息
        error_message = f"请求失败：\n类型: {type(exc).__name__}\n详情: {str(exc)}\n\n请检查：\n1. 网络连接是否正常\n2. 必发网登录状态\n3. 后端终端查看完整错误信息"
        return jsonify({
            "success": False, 
            "message": error_message,
            "error_type": type(exc).__name__,
            "error_detail": str(exc)
        }), 500


@app.route("/api/handicap/search", methods=["POST"])
def api_handicap_search():
    """
    搜索比赛并返回500彩票网的比赛ID
    
    请求参数:
    {
        "home_team": "主队名称",
        "away_team": "客队名称",
        "league": "联赛名称（可选）",
        "match_date": "比赛日期 YYYY-MM-DD（可选）"
    }
    """
    data = request.get_json(force=True) or {}
    home_team = data.get("home_team")
    away_team = data.get("away_team")
    league = data.get("league")
    match_date = data.get("match_date")
    
    if not home_team or not away_team:
        return jsonify({"success": False, "message": "请提供主队和客队名称"}), 400
    
    try:
        fid = lottery500_client.search_match_by_teams(
            home_team=home_team,
            away_team=away_team,
            league=league,
            match_date=match_date
        )
        
        if fid:
            return jsonify({
                "success": True,
                "fid": fid,
                "message": f"找到比赛ID: {fid}"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"未找到比赛: {home_team} vs {away_team}"
            })
    except Exception as exc:
        app.logger.exception("搜索比赛失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/handicap/data", methods=["POST"])
def api_handicap_data():
    """
    获取指定比赛的让球盘口数据
    
    请求参数:
    {
        "fid": "比赛ID",
        "company_id": "博彩公司ID（可选，默认5=澳门盘）"
    }
    
    博彩公司ID或名称:
    - "澳门": 澳门盘（推荐，名称匹配更稳定）
    - "Bet365": Bet365
    - "立博": 立博
    - "皇冠": 皇冠
    - 也支持ID: "5", "3", "4"等（但ID可能因比赛而异）
    """
    data = request.get_json(force=True) or {}
    fid = data.get("fid")
    company_id = data.get("company_id", "澳门")  # 默认使用澳门盘（名称匹配）
    
    if not fid:
        return jsonify({"success": False, "message": "请提供比赛ID (fid)"}), 400
    
    try:
        handicap_data = lottery500_client.fetch_handicap_data(fid, company_id)
        
        if handicap_data:
            return jsonify({
                "success": True,
                "data": handicap_data,
                "message": "盘口数据获取成功"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"未获取到盘口数据: fid={fid}"
            })
    except Exception as exc:
        app.logger.exception("获取盘口数据失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/handicap/match", methods=["POST"])
def api_handicap_match():
    """
    一站式获取比赛的让球盘口数据（自动搜索+获取）
    
    请求参数:
    {
        "home_team": "主队名称",
        "away_team": "客队名称",
        "league": "联赛名称（可选）",
        "match_date": "比赛日期 YYYY-MM-DD（可选）",
        "company_id": "博彩公司名称或ID（可选，默认'澳门'）"
    }
    
    返回示例:
    {
        "success": true,
        "data": {
            "home_team": "曼联",
            "away_team": "利物浦",
            "initial_handicap": -0.5,  // 初盘让球数（负数表示主队受让）
            "current_handicap": -0.25, // 即时盘让球数
            "initial_home_odds": 0.95, // 初盘主队水位
            "initial_away_odds": 0.85, // 初盘客队水位
            "current_home_odds": 0.90,
            "current_away_odds": 0.90,
            "history": [...]  // 历史盘口变化
        }
    }
    """
    data = request.get_json(force=True) or {}
    home_team = data.get("home_team")
    away_team = data.get("away_team")
    league = data.get("league")
    match_date = data.get("match_date")
    match_time = data.get("match_time")
    company_id = data.get("company_id", "澳门")  # 默认使用澳门盘（名称匹配）
    
    if not home_team or not away_team:
        return jsonify({"success": False, "message": "请提供主队和客队名称"}), 400
    
    try:
        # 全局限流保护（防止429错误）
        global _handicap_api_last_request_time
        with _handicap_api_lock:
            current_time = time_module.time()
            elapsed = current_time - _handicap_api_last_request_time
            if elapsed < _HANDICAP_API_INTERVAL:
                wait_time = _HANDICAP_API_INTERVAL - elapsed
                app.logger.debug(f"限流等待 {wait_time:.2f}s")
                time_module.sleep(wait_time)
            
            _handicap_api_last_request_time = time_module.time()
            
            handicap_data = lottery500_client.get_match_handicap(
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_date=match_date,
                match_time=match_time,
                company_id=company_id
            )
        
        if handicap_data:
            return jsonify({
                "success": True,
                "data": handicap_data,
                "message": "盘口数据获取成功"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"未找到或无法获取比赛盘口数据: {home_team} vs {away_team}"
            })
    except Exception as exc:
        app.logger.exception("获取盘口数据失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/handicap/batch", methods=["POST"])
def api_handicap_batch():
    """
    批量获取多场比赛的让球盘口数据
    
    请求参数:
    {
        "matches": [
            {
                "home_team": "主队名称",
                "away_team": "客队名称",
                "league": "联赛名称（可选）",
                "match_date": "比赛日期（可选）"
            },
            ...
        ],
        "company_id": "博彩公司ID（可选，默认5=澳门盘）"
    }
    """
    data = request.get_json(force=True) or {}
    matches = data.get("matches", [])
    company_id = data.get("company_id", "澳门")  # 默认使用澳门盘（名称匹配）
    
    if not matches or not isinstance(matches, list):
        return jsonify({"success": False, "message": "请提供比赛列表"}), 400
    
    results = []
    errors = []
    
    for i, match in enumerate(matches):
        home_team = match.get("home_team")
        away_team = match.get("away_team")
        league = match.get("league")
        match_date = match.get("match_date")
        
        if not home_team or not away_team:
            errors.append({
                "index": i,
                "message": "缺少主队或客队名称",
                "match": match
            })
            continue
        
        try:
            handicap_data = lottery500_client.get_match_handicap(
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_date=match_date,
                company_id=company_id
            )
            
            if handicap_data:
                results.append({
                    "index": i,
                    "success": True,
                    "data": handicap_data
                })
            else:
                errors.append({
                    "index": i,
                    "message": f"未找到比赛: {home_team} vs {away_team}",
                    "match": match
                })
        except Exception as exc:
            app.logger.exception(f"批量获取第{i}场比赛失败")
            errors.append({
                "index": i,
                "message": str(exc),
                "match": match
            })
    
    return jsonify({
        "success": True,
        "total": len(matches),
        "success_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors
    })


@app.route("/api/backtest/single", methods=["POST"])
def api_backtest_single():
    """
    单场比赛回测
    
    请求参数:
    {
        "match": {
            "home": "主队名称",
            "away": "客队名称",
            "league": "联赛名称",
            "kickoff": "开赛时间"
        },
        "detail_url": "明细页面URL",
        "actual_score": [主队得分, 客队得分],
        "detail_params": {...}  // 可选
    }
    
    返回:
    {
        "success": true,
        "match_info": {...},
        "recommendation": {...},
        "validation": {
            "result": "WIN/LOSE/DRAW/HALF_WIN/HALF_LOSE",
            "profit": 0.9,
            "message": "推荐正确"
        },
        "backtest_report": "..."  // 格式化的回测报告
    }
    """
    data = request.get_json(force=True) or {}
    match_info = data.get("match", {})
    detail_url = data.get("detail_url")
    actual_score = data.get("actual_score")
    detail_params = data.get("detail_params")
    
    if not match_info:
        return jsonify({"success": False, "message": "请提供比赛信息"}), 400
    
    if not detail_url:
        return jsonify({"success": False, "message": "请提供明细URL"}), 400
    
    if not actual_score or len(actual_score) != 2:
        return jsonify({"success": False, "message": "请提供实际比分 [主队, 客队]"}), 400
    
    try:
        # 执行回测
        result = backtest_engine.backtest_single_match(
            match_info=match_info,
            detail_url=detail_url,
            actual_score=tuple(actual_score),
            detail_params=detail_params
        )
        
        # 生成回测报告
        if result.get('success'):
            from backtest.report_formatter import format_backtest_report
            result['backtest_report'] = format_backtest_report(result)
        
        return jsonify(result)
        
    except Exception as exc:
        app.logger.exception("回测失败")
        return jsonify({
            "success": False,
            "message": str(exc),
            "error_type": "EXCEPTION"
        }), 500


@app.route("/api/recommendation/generate", methods=["POST"])
def api_generate_recommendation():
    """
    生成让球盘口推荐（X1全侦破版）
    
    请求参数:
    {
        "match": {
            "home": "主队名称",
            "away": "客队名称",
            "league": "联赛名称",
            "kickoff": "开赛时间"
        },
        "detail_url": "明细页面URL（用于获取交易明细）",
        "detail_params": "明细参数（可选）",
        "format": "vis" | "telegram" | "both" （默认both）
    }
    
    返回：
    {
        "success": true,
        "recommendation": {...},  // 原始推荐数据
        "vis_output": "...",      // VIS-E01格式输出
        "telegram_message": "..." // Telegram格式消息
    }
    """
    data = request.get_json(force=True) or {}
    match_info = data.get("match", {})
    detail_url = data.get("detail_url")
    detail_params = data.get("detail_params")
    output_format = data.get("format", "both")
    
    if not match_info:
        return jsonify({"success": False, "message": "请提供比赛信息"}), 400
    
    try:
        import concurrent.futures
        
        app.logger.info(f"🎯 正在生成推荐：{match_info.get('home')} vs {match_info.get('away')}")
        
        # 🔥 1. 先检查本地缓存（与完场回查逻辑一致）
        trade_data = None
        handicap_data = None
        metadata = []
        
        if detail_cache_manager.has_cache(match_info):
            app.logger.info("✅ 发现本地缓存，直接使用")
            try:
                cached = detail_cache_manager.load_detail(match_info)
                if cached:
                    # 🔥 修正：load_detail 返回的是元组 (trade_df, handicap_data, metadata)
                    trade_data, handicap_data, metadata = cached
                    app.logger.info(f"  📂 缓存数据：{len(trade_data)}行，盘口={'✓' if handicap_data else '✗'}")
            except Exception as e:
                app.logger.warning(f"⚠️  缓存加载失败：{e}，将重新抓取")
                trade_data = None
        
        # 🔥 2. 如果没有缓存，抓取数据
        if trade_data is None:
            app.logger.info("📡 从网络抓取数据（将保存到本地缓存）")
            
            # 准备盘口查询参数
            kickoff = match_info.get("kickoff", "")
            match_date = kickoff.split()[0] if kickoff else None
            
            # 定义抓取函数
            def fetch_trade_detail():
                """抓取交易明细"""
                app.logger.info("  → 线程1: 开始抓取交易明细...")
                html = bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match_info if isinstance(match_info, dict) else None,
                    detail_params=detail_params if isinstance(detail_params, dict) else None,
                )
                trade_data = parse_bifa_html(html, match=match_info if isinstance(match_info, dict) else None)
                app.logger.info(f"  ✓ 线程1: 交易明细抓取完成（{len(trade_data) if isinstance(trade_data, pd.DataFrame) else 0}行）")
                # 🔥 返回元组：(trade_data, html) 以便后续保存HTML
                return (trade_data, html)
            
            def fetch_handicap():
                """获取盘口数据（优先从本地文件读取，找不到才实时查询）"""
                app.logger.info("  → 线程2: 开始获取盘口数据...")
                
                # 🔥 1. 优先从本地盘口文件读取（按年/月/日目录结构）
                if match_date:
                    from pathlib import Path
                    from datetime import datetime, timedelta
                    import json
                    
                    # 🔥 解析日期，构建路径：data/YYYY/MM/DD/盘口数据.json
                    date_parts = match_date.split('-')  # ['2025', '11', '21']
                    if len(date_parts) == 3:
                        # 🔥 凌晨比赛的盘口可能在前一天，需要同时查询当天和前一天
                        match_dt = datetime.strptime(match_date, "%Y-%m-%d")
                        
                        # 提取比赛时间（HH:MM）
                        match_hour = 0
                        if ' ' in kickoff:
                            try:
                                time_str = kickoff.split(' ')[1][:5]  # "HH:MM"
                                match_hour = int(time_str.split(':')[0])
                            except:
                                pass
                        
                        # 🔥 如果是凌晨比赛（00:00-05:59），优先查前一天的盘口数据
                        search_dates = [match_dt]
                        if 0 <= match_hour < 6:
                            prev_day = match_dt - timedelta(days=1)
                            search_dates = [prev_day, match_dt]  # 先查前一天，再查当天
                            app.logger.info(f"  🌙 凌晨比赛，将查询两天的盘口数据: {prev_day.strftime('%Y-%m-%d')} 和 {match_dt.strftime('%Y-%m-%d')}")
                        
                        result = None
                        for search_dt in search_dates:
                            year = str(search_dt.year)
                            month = str(search_dt.month).zfill(2)
                            day = str(search_dt.day).zfill(2)
                            
                            handicap_file = BASE_DIR / "data" / year / month / day / "盘口数据.json"
                            
                            # 🔥 兼容旧文件名
                            if not handicap_file.exists():
                                legacy_file = BASE_DIR / "data" / year / month / day / "handicaps.json"
                                if legacy_file.exists():
                                    handicap_file = legacy_file
                            
                            if handicap_file.exists():
                                try:
                                    app.logger.info(f"  📂 尝试从本地文件读取: {year}/{month}/{day}/{handicap_file.name}")
                                    with open(handicap_file, 'r', encoding='utf-8') as f:
                                        daily_handicaps = json.load(f)
                                    
                                    # 从本地数据中查找匹配的盘口
                                    result = lottery500_client.find_handicap_from_daily_data(
                                        daily_handicaps=daily_handicaps,
                                        home_team=match_info.get("home"),
                                        away_team=match_info.get("away"),
                                        match_time=kickoff
                                    )
                                    
                                    if result:
                                        app.logger.info(f"  ✅ 从本地文件找到盘口数据: {year}-{month}-{day}")
                                        # 🔥 增强盘口数据（补充初盘和即时盘口）
                                        result = enhance_handicap_with_initial_data(result, lottery500_client, app.logger)
                                        app.logger.info(f"  ✓ 线程2: 盘口数据获取完成（成功-本地）")
                                        return result
                                    else:
                                        app.logger.info(f"  ⚠️  {year}-{month}-{day} 文件中未找到匹配的盘口")
                                
                                except Exception as e:
                                    app.logger.warning(f"  ⚠️  读取 {year}-{month}-{day} 盘口文件失败: {e}")
                        
                        if not result:
                            app.logger.info(f"  ⚠️  本地文件中未找到匹配的盘口，将批量获取")
                    else:
                        app.logger.warning(f"  ⚠️  日期格式错误: {match_date}")
                
                # 🔥 2. 本地没有，批量获取（凌晨比赛查前一天）
                app.logger.info("  🌐 批量获取并保存盘口数据...")
                try:
                    # 🔥 凌晨比赛优先查前一天
                    fetch_date = match_date
                    if match_date and match_hour < 6:
                        from datetime import datetime, timedelta
                        match_dt = datetime.strptime(match_date, "%Y-%m-%d")
                        prev_day = match_dt - timedelta(days=1)
                        fetch_date = prev_day.strftime("%Y-%m-%d")
                        app.logger.info(f"  🌙 凌晨比赛，查询前一天的盘口: {fetch_date}")
                    
                    # 🔥 调用fetch_daily_handicaps批量获取（会自动保存HTML和JSON）
                    daily_handicaps = lottery500_client.fetch_daily_handicaps(
                        match_date=fetch_date,
                        use_cache=False  # 强制重新获取
                    )
                    
                    app.logger.info(f"  ✅ 批量获取成功：{len(daily_handicaps)}场比赛")
                    fetch_dt = datetime.strptime(fetch_date, "%Y-%m-%d") if fetch_date else match_dt
                    app.logger.info(f"  💾 已保存到: data/{fetch_dt.year}/{str(fetch_dt.month).zfill(2)}/{str(fetch_dt.day).zfill(2)}/盘口数据.html 和 盘口数据.json")
                    
                    # 从批量数据中查找匹配的盘口
                    result = lottery500_client.find_handicap_from_daily_data(
                        daily_handicaps=daily_handicaps,
                        home_team=match_info.get("home"),
                        away_team=match_info.get("away"),
                        match_time=kickoff
                    )
                    
                    if not result:
                        app.logger.warning("  ⚠️  批量数据中未找到匹配的盘口")
                    else:
                        # 🔥 增强盘口数据（补充初盘和即时盘口）
                        result = enhance_handicap_with_initial_data(result, lottery500_client, app.logger)
                        app.logger.info(f"  ✓ 线程2: 盘口数据获取完成（成功-批量查询）")
                        return result
                    
                except Exception as e:
                    app.logger.error(f"  ❌ 批量获取盘口失败: {e}")
                
                # 🔥 3. 降级方案：单个查询（批量失败或未找到匹配时）
                app.logger.info("  🔄 降级为单个查询...")
                try:
                    result = lottery500_client.get_match_handicap(
                        home_team=match_info.get("home"),
                        away_team=match_info.get("away"),
                        league=match_info.get("league"),
                        match_date=match_date,
                        match_time=kickoff
                    )
                    
                    if result:
                        # 🔥 增强盘口数据（补充初盘和即时盘口）
                        result = enhance_handicap_with_initial_data(result, lottery500_client, app.logger)
                    app.logger.info(f"  ✓ 线程2: 盘口数据获取完成（{'成功-单个查询' if result else '失败'}）")
                    return result
                    
                except Exception as e:
                    app.logger.error(f"  ❌ 单个查询也失败: {e}")
                    app.logger.info(f"  ✓ 线程2: 盘口数据获取完成（失败）")
                    return None
            
            def fetch_ou_trade_detail():
                """获取大小球交易明细（仅实时比赛有效）"""
                app.logger.info("  → 线程3: 开始获取大小球明细...")
                try:
                    # 检查是否有raw.ou数据
                    raw_ou = match_info.get('raw', {}).get('ou', [])
                    if not raw_ou:
                        app.logger.info("  ✓ 线程3: 无大小球数据（跳过）")
                        return None
                    
                    ou_data = bifaw_client.fetch_ou_trade_details_selenium(
                        match={'match_info': match_info},
                        timeout=30
                    )
                    if ou_data:
                        app.logger.info(f"  ✓ 线程3: 大小球明细获取完成（{ou_data.get('total_records', 0)}条）")
                    else:
                        app.logger.info("  ✓ 线程3: 大小球明细为空（可能是完场比赛）")
                    return ou_data
                except Exception as e:
                    app.logger.warning(f"  ⚠️ 线程3: 大小球明细获取失败: {e}")
                    return None
            
            # 并行执行（使用线程池）
            html_content = None  # 用于保存原始HTML
            ou_trade_data = None  # 大小球交易明细
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_trade = executor.submit(fetch_trade_detail)
                future_handicap = executor.submit(fetch_handicap)
                future_ou = executor.submit(fetch_ou_trade_detail)
                
                # 等待所有任务完成
                trade_result = future_trade.result()
                # 🔥 解包：fetch_trade_detail 现在返回 (trade_data, html)
                if isinstance(trade_result, tuple) and len(trade_result) == 2:
                    trade_data, html_content = trade_result
                else:
                    trade_data = trade_result
                    html_content = None
                
                handicap_data = future_handicap.result()
                ou_trade_data = future_ou.result()
            
            app.logger.info("✅ 网络数据获取完成")
            
            # 🔥 3. 立即保存到本地缓存（包括HTML和大小球明细！）
            if isinstance(trade_data, pd.DataFrame) and not trade_data.empty:
                try:
                    metadata = trade_data.attrs.get("metadata", [])
                    success = detail_cache_manager.save_detail(
                        match_info=match_info,
                        trade_data=trade_data,
                        handicap_data=handicap_data,
                        metadata=metadata,
                        html_content=html_content,
                        ou_trade_data=ou_trade_data  # 🔥 传递大小球明细
                    )
                    if success:
                        ou_info = f"，大小球明细{ou_trade_data.get('total_records', 0)}条" if ou_trade_data else ""
                        app.logger.info(f"💾 数据已保存到本地缓存{ou_info}")
                    else:
                        app.logger.warning("⚠️  缓存保存失败")
                except Exception as e:
                    app.logger.warning(f"⚠️  缓存保存失败：{e}")
        
        # 🔥 4. 检查数据有效性
        if not isinstance(trade_data, pd.DataFrame) or trade_data.empty:
            error_msg = trade_data if isinstance(trade_data, str) else "未解析到明细数据"
            return jsonify({
                "success": False,
                "message": f"交易明细解析失败: {error_msg}"
            }), 500
        
        # 确保metadata已获取
        if not metadata:
            metadata = trade_data.attrs.get("metadata", [])
        
        # 🔥 5. 生成推荐（统一逻辑）
        app.logger.info("📊 生成推荐...")
        
        # 🔥 优先尝试使用X1 JSON推荐引擎（如果JSON文件存在）
        x1_json_result = None
        try:
            # 尝试查找对应的JSON文件
            kickoff = match_info.get("kickoff", "")
            if kickoff and " " in kickoff:
                match_date = kickoff.split()[0]
                year, month, day = match_date.split('-')
                
                # 构建可能的JSON文件路径
                from pathlib import Path
                data_dir = Path("data") / year / month / day
                
                if data_dir.exists():
                    home = match_info.get('home', '')
                    away = match_info.get('away', '')
                    
                    # 查找匹配的JSON文件
                    for json_file in data_dir.glob('2025-*.json'):
                        if home in json_file.name and away in json_file.name:
                            app.logger.info(f"🎯 找到JSON文件，使用X1 JSON推荐引擎: {json_file.name}")
                            x1_json_result = x1_json_recommender.recommend(str(json_file))
                            
                            # 🔥 记录推荐到数据库
                            if not x1_json_result.get('meltdown') and x1_json_result.get('recommendation', {}).get('direction') != 'none':
                                try:
                                    from recommendation_tracker import tracker
                                    x1_json_result['json_file_path'] = str(json_file)
                                    rec_id = tracker.record_recommendation(x1_json_result)
                                    app.logger.info(f"✅ 推荐已记录到数据库 ID={rec_id}")
                                except Exception as e:
                                    app.logger.warning(f"⚠️ 记录推荐失败: {e}")
                            
                            break
        except Exception as e:
            app.logger.warning(f"⚠️ X1 JSON推荐引擎失败: {e}")
        
        # 如果X1 JSON成功且未熔断，使用它的结果
        if x1_json_result and not x1_json_result.get('meltdown'):
            app.logger.info("✅ 使用 X1 JSON 推荐引擎结果（准确率83.6%）")
            
            # 转换为统一格式
            rec = x1_json_result.get('recommendation', {})
            recommendation = {
                'direction': rec.get('direction', 'none'),
                'should_bet': rec.get('direction') not in ['none', None],
                'confidence': rec.get('confidence', 0),
                'reason': rec.get('reason', ''),
                'handicap': rec.get('handicap', ''),
                'engine': 'x1_json',
                'x1_json_scores': x1_json_result.get('scores'),
                'x1_json_funding': x1_json_result.get('funding_level'),
                'x1_json_risk': x1_json_result.get('risk_control')
            }
        else:
            # 🔥 使用 X1 JSON 引擎的兼容接口（实时采集场景）
            app.logger.info("📊 使用 X1 JSON 引擎兼容接口（实时采集）")
            recommendation = x1_json_recommender.generate_recommendation(
                trade_data=trade_data,
                metadata=metadata,
                handicap_data=handicap_data
            )
            # 🔥 不覆盖engine字段，保留generate_recommendation返回的'x1_json'以使用正确的格式化器
        
        # 🎯 规则验证与混合推荐（比分反推规则库）
        rule_verification = None
        if hybrid_recommender and len(trade_data) > 0:
            try:
                app.logger.info("🔍 应用规则推荐系统...")
                
                # 提取特征用于规则匹配
                last_record = trade_data.iloc[0] if len(trade_data) > 0 else {}
                
                features = {
                    # 成交量特征
                    'home_volume_pct': float(last_record.get('比例_主', 0)) if '比例_主' in last_record else 0,
                    'away_volume_pct': float(last_record.get('比例_客', 0)) if '比例_客' in last_record else 0,
                    'draw_volume_pct': float(last_record.get('比例_和', 0)) if '比例_和' in last_record else 0,
                    'total_volume': float(str(last_record.get('总成交量', 0)).replace(',', '')) if '总成交量' in last_record else 0,
                    
                    # 赔率特征
                    'home_odds': float(last_record.get('主胜_欧赔', 0)) if '主胜_欧赔' in last_record else 0,
                    'away_odds': float(last_record.get('客胜_欧赔', 0)) if '客胜_欧赔' in last_record else 0,
                    'draw_odds': float(last_record.get('和局_欧赔', 0)) if '和局_欧赔' in last_record else 0,
                    
                    # 凯利指数（转换为异常值）
                    'kelly_home_anomaly': float(last_record.get('凯利_主', 100)) / 100.0 - 1.0 if '凯利_主' in last_record else 0,
                    'kelly_away_anomaly': float(last_record.get('凯利_客', 100)) / 100.0 - 1.0 if '凯利_客' in last_record else 0,
                    
                    # 盘口特征
                    'handicap_current': float(handicap_data.get('current_handicap', 0)) if handicap_data else 0,
                    'handicap_initial': float(handicap_data.get('initial_handicap', 0)) if handicap_data else 0,
                }
                
                # 计算衍生特征
                features['handicap_change'] = features['handicap_current'] - features['handicap_initial']
                features['concentration'] = max(
                    features['home_volume_pct'],
                    features['away_volume_pct'],
                    features['draw_volume_pct']
                ) / 100.0
                
                # 转换推荐格式用于混合推荐
                model_score = {
                    'recommendation': recommendation.get('direction', 'none'),
                    'confidence': recommendation.get('confidence', 0),
                    'reason': recommendation.get('reason', ''),
                    'total_score': recommendation.get('score', 0)
                }
                
                # 应用混合推荐
                final_result = hybrid_recommender.recommend(features, model_score)
                
                # 记录规则验证结果
                rule_verification = {
                    'matched_rules': final_result.get('rule_details', {}).get('matched_rules', []),
                    'rule_recommendation': final_result.get('rule_details', {}).get('recommendation', 'none'),
                    'rule_confidence': final_result.get('rule_details', {}).get('confidence', 0),
                    'rule_reason': final_result.get('rule_details', {}).get('reason', ''),
                    'final_recommendation': final_result.get('recommendation', 'none'),
                    'final_confidence': final_result.get('confidence', 0),
                    'source': final_result.get('source', 'model')  # rule/model/hybrid
                }
                
                # 如果规则推荐置信度更高，更新主推荐
                if final_result.get('source') in ['rule', 'hybrid']:
                    app.logger.info(f"✅ 规则系统影响推荐: {final_result['source']}")
                    recommendation['original_direction'] = recommendation.get('direction')
                    recommendation['original_confidence'] = recommendation.get('confidence')
                    recommendation['direction'] = final_result['recommendation']
                    recommendation['confidence'] = final_result['confidence']
                    recommendation['reason'] = f"[{final_result['source'].upper()}] {final_result['reason']}"
                    
                app.logger.info(f"🎯 规则验证完成: {len(rule_verification['matched_rules'])} 条规则匹配")
                
            except Exception as e:
                app.logger.warning(f"⚠️ 规则验证失败: {e}")
                rule_verification = {'error': str(e)}
        
        # 4. 准备交易明细统计信息
        trade_data_info = {
            "row_count": len(trade_data),
            "col_count": len(trade_data.columns),
            "columns": list(trade_data.columns),  # 记录实际列名用于调试
            "time_range": None,
            "total_volume": None,
            "preview": [],
            "sample_row": {}  # 添加样例行数据
        }
        
        # 提取第一行数据作为样例
        if len(trade_data) > 0:
            sample_row = {}
            for col in trade_data.columns[:10]:  # 只取前10列避免数据过多
                try:
                    sample_row[col] = str(trade_data[col].iloc[0])
                except:
                    sample_row[col] = "N/A"
            trade_data_info["sample_row"] = sample_row
            app.logger.info(f"第一行样例数据: {sample_row}")
        
        # 简化的列名查找（信任解析器已经给出正确的列名）
        time_col = None
        odds_col = None
        volume_col = None
        
        # 记录所有可能的列用于调试
        all_time_cols = []
        all_odds_cols = []
        all_volume_cols = []
        
        for col in trade_data.columns:
            col_str = str(col)
            col_lower = col_str.lower()
            
            # 时间列：优先"成交时间"
            if '时间' in col_str or 'time' in col_lower:
                all_time_cols.append(col_str)
                if not time_col:
                    if '成交时间' == col_str:  # 精确匹配优先
                        time_col = col_str
                    elif '时间' in col_str:
                        time_col = col_str
            
            # 赔率列：匹配多种关键字（赔率、价格、欧赔、价位等）
            if any(kw in col_str for kw in ['赔率', '价格', '欧赔', '价位', '赔']) or 'odds' in col_lower or 'price' in col_lower:
                if '成交量' not in col_str and '挂买' not in col_str and '挂卖' not in col_str and '方式' not in col_str:
                    all_odds_cols.append(col_str)
                    if not odds_col:
                        # 优先选择"主胜"的赔率列
                        if '主胜' in col_str:
                            odds_col = col_str
                        elif not odds_col:
                            odds_col = col_str
            
            # 成交量列：精确匹配"成交量"，或第一个包含"成交量"的
            if '成交量' in col_str:
                all_volume_cols.append(col_str)
                if not volume_col:
                    # 优先无前缀的
                    if col_str in ('成交量', '现成交量', '总成交量'):
                        volume_col = col_str
                    # 否则取第一个（可能是"客胜_现成交量"等）
                    elif not volume_col:
                        volume_col = col_str
        
        app.logger.info(f"候选列 - 时间: {all_time_cols}, 赔率: {all_odds_cols}, 成交量: {all_volume_cols}")
        
        app.logger.info(f"识别到的列：时间={time_col}, 赔率={odds_col}, 成交量={volume_col}")
        
        # 提取时间范围
        if time_col and len(trade_data) > 0:
            try:
                first_time = trade_data[time_col].iloc[0]
                last_time = trade_data[time_col].iloc[-1]
                trade_data_info["time_range"] = f"{first_time} ~ {last_time}"
            except:
                pass
        
        # 提取总成交量
        if volume_col:
            try:
                series = trade_data[volume_col]

                # 对于「总成交量」这类累计列，取数值最大值；否则按列求和
                def _to_number(value):
                    try:
                        if pd.isna(value):
                            return None
                        return float(str(value).replace(",", ""))
                    except Exception:
                        return None

                if "总" in str(volume_col):
                    numeric_series = series.map(_to_number).dropna()
                    total = float(numeric_series.max() or 0.0)
                else:
                    if pd.api.types.is_numeric_dtype(series):
                        total = float(series.sum())
                    else:
                        total = float(series.map(lambda v: _to_number(v) or 0.0).sum())

                trade_data_info["total_volume"] = f"{total:,.0f}"
            except Exception:
                pass
        
        # 提取前5行预览
        if len(trade_data) > 0:
            for idx in range(min(5, len(trade_data))):
                row_data = {
                    "time": str(trade_data[time_col].iloc[idx]) if time_col else 'N/A',
                    "odds": str(trade_data[odds_col].iloc[idx]) if odds_col else 'N/A',
                    "volume": str(trade_data[volume_col].iloc[idx]) if volume_col else 'N/A'
                }
                trade_data_info["preview"].append(row_data)
        
        # 5. 准备盘口数据信息
        handicap_info = None
        if handicap_data:
            handicap_info = {
                "initial_handicap": handicap_data.get('initial_handicap', 'N/A'),
                "initial_handicap_str": handicap_data.get('initial_handicap_str', 'N/A'),
                "current_handicap": handicap_data.get('current_handicap', 'N/A'),
                "current_handicap_str": handicap_data.get('current_handicap_str', 'N/A')
            }
        
        # 6. 格式化输出
        response = {
            "success": True,
            "recommendation": recommendation,
            "trade_data_info": trade_data_info,
            "handicap_info": handicap_info
        }
        
        # 🎯 添加规则验证信息
        if rule_verification:
            response["rule_verification"] = rule_verification
        
        if output_format in ["vis", "both"]:
            response["vis_output"] = vis_formatter.format_output(recommendation)
        
        if output_format in ["telegram", "both"]:
            response["telegram_message"] = vis_formatter.format_telegram_message(recommendation)
        
        return jsonify(response)
        
    except Exception as exc:
        app.logger.exception("生成推荐失败")
        return jsonify({
            "success": False,
            "message": str(exc),
            "error_type": "EXCEPTION"
        }), 500


@app.route("/api/cache/list", methods=["GET"])
def api_cache_list():
    """列出本地明细缓存（可按日期过滤，支持限制数量）"""
    try:
        date_filter = request.args.get("date")  # YYYY-MM-DD
        limit = request.args.get("limit", type=int) or 200
        caches = detail_cache_manager.list_all_caches()

        # 过滤日期
        if date_filter:
            caches = [c for c in caches if c.get("date") == date_filter]

        # 按日期和缓存时间排序（新的在前）
        def _sort_key(c):
            return (
                c.get("date") or "",
                c.get("cached_at") or "",
            )

        caches.sort(key=_sort_key, reverse=True)

        total = len(caches)
        if total > limit:
            caches = caches[:limit]

        # 去掉文件物理路径，仅保留对前端有用的信息
        simplified = []
        for c in caches:
            simplified.append({
                "date": c.get("date"),
                "filename": c.get("filename"),
                "cache_key": c.get("cache_key"),
                "match_label": c.get("match_label"),
                "cached_at": c.get("cached_at"),
                "rows": c.get("rows"),
                "file_size": c.get("file_size"),
            })

        return jsonify({
            "success": True,
            "total": total,
            "returned": len(simplified),
            "items": simplified,
        })
    except Exception as exc:
        app.logger.exception("列出缓存失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/cache/overview", methods=["GET"])
def api_cache_overview_simple():
    """获取缓存概览统计（用于首页仪表盘）"""
    try:
        caches = detail_cache_manager.list_all_caches()
        total_matches = len(caches)
        return jsonify({
            "success": True,
            "total_matches": total_matches
        })
    except Exception as exc:
        app.logger.exception("获取缓存概览失败")
        return jsonify({"success": False, "message": str(exc), "total_matches": 0}), 500


@app.route("/api/cache/delete", methods=["POST"])
def api_cache_delete():
    """删除指定缓存（支持单个或多个 cache_key）"""
    data = request.get_json(force=True) or {}
    cache_key = data.get("cache_key")
    cache_keys = data.get("cache_keys")

    try:
        deleted = []
        failed = []

        keys = []
        if cache_key:
            keys.append(cache_key)
        if isinstance(cache_keys, list):
            keys.extend([k for k in cache_keys if isinstance(k, str)])

        if not keys:
            return jsonify({"success": False, "message": "请提供 cache_key 或 cache_keys"}), 400

        for key in keys:
            try:
                ok = detail_cache_manager.delete_by_cache_key(key)
                if ok:
                    deleted.append(key)
                else:
                    failed.append(key)
            except Exception:
                failed.append(key)

        return jsonify({
            "success": True,
            "deleted": deleted,
            "failed": failed,
        })
    except Exception as exc:
        app.logger.exception("删除缓存失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """清空所有本地明细缓存（不影响盘口缓存）"""
    try:
        deleted_count = detail_cache_manager.clear_all_caches()
        return jsonify({"success": True, "deleted_count": deleted_count})
    except Exception as exc:
        app.logger.exception("清空缓存失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/analysis/cache_overview", methods=["GET"])
def api_cache_overview():
    """简单数据分析：按日期统计缓存文件数量和行数"""
    try:
        caches = detail_cache_manager.list_all_caches()
        by_date = {}
        for c in caches:
            date = c.get("date") or "未知日期"
            info = by_date.setdefault(date, {"files": 0, "rows": 0, "size": 0})
            info["files"] += 1
            info["rows"] += c.get("rows", 0)
            info["size"] += c.get("file_size", 0)

        # 转为列表并按日期排序
        overview = []
        for date, info in by_date.items():
            overview.append({
                "date": date,
                "files": info["files"],
                "rows": info["rows"],
                "size_bytes": info["size"],
                "size_mb": round(info["size"] / 1024 / 1024, 2),
            })

        overview.sort(key=lambda x: x["date"], reverse=True)

        return jsonify({"success": True, "overview": overview})
    except Exception as exc:
        app.logger.exception("生成缓存概览失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/detail/collect", methods=["POST"])
def api_collect_details():
    """
    批量采集明细到本地缓存
    
    请求参数:
    {
        "start_date": "2025-11-01",  // 开始日期（必填）
        "rows": 100,                  // 每天获取的比赛数量（可选，默认100）
        "force": false                // 是否强制重新采集（可选，默认false）
    }
    
    说明：
    - 采集从 start_date 至今的所有比赛
    - 例如：start_date=2025-11-01，今天是11-19，则采集这19天的比赛
    - 建议采集最近7天内的比赛，时间过长的比赛明细已被清空
    """
    try:
        from datetime import datetime, timedelta
        
        data = request.get_json(force=True) or {}
        start_date_str = data.get("start_date")
        rows = data.get("rows", 100)
        force = data.get("force", False)
        
        if not start_date_str:
            return jsonify({"success": False, "message": "请提供开始日期（start_date）"}), 400
        
        # 解析开始日期
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except:
            return jsonify({"success": False, "message": "日期格式错误，应为 YYYY-MM-DD"}), 400
        
        # 计算到今天的天数
        today = datetime.now()
        days_diff = (today - start_date).days + 1  # 包含开始日期当天
        
        if days_diff <= 0:
            return jsonify({"success": False, "message": "开始日期不能晚于今天"}), 400
        
        if days_diff > 30:
            return jsonify({"success": False, "message": "日期范围不能超过30天，建议采集最近7天"}), 400
        
        app.logger.info(f"开始采集明细: {start_date_str} 至今（共{days_diff}天，每天最多{rows}场）")
        
        # 获取比赛列表（从开始日期到今天）
        app.logger.info(f"📋 步骤1：获取比赛列表（从 {start_date_str} 至今，共{days_diff}天）...")
        app.logger.info(f"⏳ 正在获取比赛列表，请稍候...")
        
        matches = bifaw_client.fetch_match_list_v2(rows=rows, days=days_diff)
        
        if not matches:
            return jsonify({"success": False, "message": "未找到比赛"}), 404
        
        app.logger.info(f"✅ 找到 {len(matches)} 场比赛")
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"📦 步骤2：开始逐场采集明细（串行处理，每场间隔2秒）")
        app.logger.info(f"{'='*80}\n")
        
        # 统计
        total = len(matches)
        collected = 0
        skipped = 0
        failed = 0
        results = []
        
        # 逐场采集（串行处理，每场立即保存）
        import time
        import sys
        
        for idx, match in enumerate(matches, 1):
            match_label = match.get('label', '未知比赛')
            
            # 输出进度并立即刷新
            progress_msg = f"\n{'='*80}\n[{idx}/{total}] 🔍 开始采集: {match_label}\n{'='*80}"
            app.logger.info(progress_msg)
            print(progress_msg, flush=True)  # 立即输出到控制台
            
            try:
                # 检查是否已有缓存
                if not force and detail_cache_manager.has_cache(match):
                    skip_msg = f"  ⏭️  已有缓存，跳过"
                    app.logger.info(skip_msg)
                    print(skip_msg, flush=True)
                    
                    skipped += 1
                    results.append({
                        "match": match_label,
                        "status": "skipped",
                        "message": "已有缓存",
                        "index": idx
                    })
                    continue
                
                # 1. 获取交易明细
                detail_url = match.get('detail_url')
                if not detail_url:
                    app.logger.warning(f"  ⚠️  缺少明细URL")
                    failed += 1
                    results.append({
                        "match": match_label,
                        "status": "failed",
                        "message": "缺少明细URL",
                        "error_type": "missing_url",
                        "index": idx
                    })
                    continue
                
                fetch_msg = f"  📡 步骤1/4: 抓取明细页面（这可能需要10-20秒）..."
                app.logger.info(fetch_msg)
                print(fetch_msg, flush=True)
                
                detail_html = bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match,
                    detail_params=match.get('detail_params')
                )
                
                print(f"  ✅ 页面抓取完成，HTML长度: {len(detail_html) if detail_html else 0}", flush=True)
                
                # 保存HTML文件到debug_html目录
                try:
                    import os
                    from pathlib import Path
                    import re
                    
                    project_root = Path(__file__).parent
                    debug_dir = project_root / "debug_html"
                    debug_dir.mkdir(exist_ok=True)
                    
                    # 提取比赛信息
                    kickoff = match.get('kickoff', '')
                    league = match.get('league', '未知联赛')
                    home = match.get('home', '未知主队')
                    away = match.get('away', '未知客队')
                    
                    # 清理文件名中的非法字符
                    def safe_filename(s):
                        s = re.sub(r'[<>:"/\\|?*]', '_', s)
                        s = s.replace(' ', '_')
                        return s[:30]
                    
                    # 格式化时间
                    if kickoff:
                        try:
                            time_part = kickoff.replace(' ', '_').replace(':', '-')
                            if len(time_part) > 16:
                                time_part = time_part[5:]  # 去掉年份
                        except:
                            time_part = "未知时间"
                    else:
                        time_part = "未知时间"
                    
                    # 构造文件名
                    filename = f"collect_{time_part}_{safe_filename(league)}_{safe_filename(home)}_vs_{safe_filename(away)}.html"
                    html_path = debug_dir / filename
                    
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(detail_html)
                    
                    app.logger.info(f"  💾 已保存HTML: {filename}")
                    print(f"  💾 已保存HTML: {filename}", flush=True)
                    
                except Exception as e:
                    app.logger.warning(f"  ⚠️ 保存HTML失败: {e}")
                
                if not detail_html:
                    app.logger.error(f"  ❌ 明细页面为空")
                    failed += 1
                    results.append({
                        "match": match_label,
                        "status": "failed",
                        "message": "明细页面为空",
                        "error_type": "empty_html",
                        "index": idx
                    })
                    continue
                
                # 2. 解析明细
                parse_msg = f"  🔧 步骤2/4: 解析明细数据..."
                app.logger.info(parse_msg)
                print(parse_msg, flush=True)
                
                parsed_data = parse_bifa_html(detail_html, match=match)
                print(f"  ✅ 解析完成", flush=True)
                
                # 判断解析结果
                if isinstance(parsed_data, str):  # 错误信息
                    error_msg = parsed_data
                    
                    # 判断是否是"数据已清空"（完场比赛常见）
                    if "未能从网页表格中识别有效数据" in error_msg:
                        app.logger.warning(f"  ⚠️  完场比赛明细已被清空（必发网限制）")
                        failed += 1
                        results.append({
                            "match": match_label,
                            "status": "failed",
                            "message": "完场比赛明细已清空",
                            "error_type": "data_cleared",
                            "index": idx,
                            "detail": "必发网对完场比赛不提供历史交易明细"
                        })
                    else:
                        app.logger.error(f"  ❌ 解析失败: {error_msg}")
                        failed += 1
                        results.append({
                            "match": match_label,
                            "status": "failed",
                            "message": f"解析失败: {error_msg}",
                            "error_type": "parse_error",
                            "index": idx
                        })
                    continue
                
                if parsed_data.empty:
                    app.logger.warning(f"  ⚠️  解析结果为空")
                    failed += 1
                    results.append({
                        "match": match_label,
                        "status": "failed",
                        "message": "解析结果为空",
                        "error_type": "empty_data",
                        "index": idx
                    })
                    continue
                
                # 3. 获取盘口
                handicap_msg = f"  🎯 步骤3/4: 获取让球盘口..."
                app.logger.info(handicap_msg)
                print(handicap_msg, flush=True)
                
                handicap_data = None
                try:
                    home = match.get('home', '')
                    away = match.get('away', '')
                    kickoff = match.get('kickoff', '')
                    league = match.get('league', '')
                    
                    if all([home, away, kickoff]):
                        # 传递联赛信息帮助匹配
                        handicap_data = lottery500_client.get_handicap(home, away, kickoff, league)
                        if handicap_data:
                            handicap_str = f"{handicap_data.get('current_handicap_str')} ({handicap_data.get('current_handicap')})"
                            app.logger.info(f"  ✅ 盘口: {handicap_str}")
                            print(f"  ✅ 盘口获取成功: {handicap_str}", flush=True)
                        else:
                            app.logger.warning(f"  ⚠️  未找到盘口数据（500.com可能无此比赛）")
                            print(f"  ⚠️  未获取到盘口数据（这不会影响明细保存）", flush=True)
                    else:
                        app.logger.warning(f"  ⚠️  比赛信息不完整，跳过盘口获取")
                except Exception as e:
                    app.logger.warning(f"  ⚠️  盘口获取失败: {e}")
                    print(f"  ⚠️  盘口获取失败: {e}（这不会影响明细保存）", flush=True)
                
                # 4. 立即保存到缓存
                save_msg = f"  💾 步骤4/4: 保存到本地缓存..."
                app.logger.info(save_msg)
                print(save_msg, flush=True)
                
                metadata = parsed_data.attrs.get("metadata", [])
                success = detail_cache_manager.save_detail(
                    match_info=match,
                    trade_data=parsed_data,
                    handicap_data=handicap_data,
                    metadata=metadata
                )
                
                if success:
                    collected += 1
                    success_msg = f"  ✅ 采集成功: {len(parsed_data)} 行数据已保存到本地"
                    app.logger.info(success_msg)
                    print(success_msg, flush=True)
                    
                    results.append({
                        "match": match_label,
                        "status": "success",
                        "rows": len(parsed_data),
                        "index": idx,
                        "handicap": handicap_data.get('current_handicap_str') if handicap_data else None
                    })
                else:
                    failed += 1
                    error_msg = f"  ❌ 保存失败"
                    app.logger.error(error_msg)
                    print(error_msg, flush=True)
                    
                    results.append({
                        "match": match_label,
                        "status": "failed",
                        "message": "保存失败",
                        "error_type": "save_error",
                        "index": idx
                    })
                
                # 请求间隔（避免被封IP）
                if idx < total:
                    wait_msg = f"  ⏱️  等待 2 秒后继续下一场..."
                    app.logger.info(wait_msg)
                    print(wait_msg, flush=True)
                    time.sleep(2)
                    print(f"  ⏩ 继续下一场\n", flush=True)
                
            except KeyboardInterrupt:
                app.logger.warning(f"\n⚠️  用户中断采集")
                break
                
            except Exception as e:
                app.logger.exception(f"  ❌ 采集异常: {e}")
                failed += 1
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": str(e),
                    "error_type": "exception",
                    "index": idx
                })
        
        # 统计错误类型
        data_cleared_count = len([r for r in results if r.get('error_type') == 'data_cleared'])
        real_errors_count = failed - data_cleared_count
        
        # 返回结果
        return jsonify({
            "success": True,
            "total": total,
            "collected": collected,
            "skipped": skipped,
            "failed": failed,
            "data_cleared": data_cleared_count,  # 完场比赛明细已清空的数量
            "real_errors": real_errors_count,    # 真实错误数量
            "results": results,
            "cache_stats": detail_cache_manager.get_statistics(),
            "summary": f"成功采集 {collected} 场，跳过 {skipped} 场，完场已清空 {data_cleared_count} 场，真实错误 {real_errors_count} 场"
        })
        
    except Exception as exc:
        app.logger.exception("批量采集失败")
        return jsonify({"success": False, "message": str(exc)}), 500

@app.route("/api/matches/list", methods=["GET"])
def api_matches_list():
    """
    获取指定日期的比赛列表
    """
    try:
        date_str = request.args.get("date")
        if not date_str:
            return jsonify({"success": False, "message": "请提供日期参数"}), 400
        
        # 解析日期
        from datetime import datetime, timedelta
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now()
        
        # 收集比赛列表
        matches = []
        
        # 从目标日期到今天
        current_date = target_date
        date_count = 0
        while current_date <= today:
            date_path = Path("data") / str(current_date.year) / f"{current_date.month:02d}" / f"{current_date.day:02d}"
            
            if date_path.exists():
                date_matches = 0
                # 遍历该日期目录下的JSON文件
                for json_file in date_path.glob("*.json"):
                    # 跳过非比赛文件
                    if json_file.stem.startswith("标盘指数") or json_file.name.startswith("盘口数据"):
                        continue
                    
                    # 只读取比赛JSON文件（文件名格式：2025-11-23_联赛_主队_vs_客队_时间.json）
                    if not json_file.stem.startswith("2025-"):
                        continue
                    
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        match_info = data.get("match_info", {})
                        if match_info:  # 只要有match_info就可以
                            # 提取比分（如果有）
                            label = match_info.get("label", "")
                            score_match = re.search(r'(\d+)-(\d+)', label) if label else None
                            actual_score = (0, 0)
                            score_for_cache = ""
                            
                            if score_match:
                                actual_score = (int(score_match.group(1)), int(score_match.group(2)))
                                score_for_cache = f"{score_match.group(1)}-{score_match.group(2)}"
                            
                            matches.append({
                                "match_info": match_info,
                                "detail_url": "",  # 本地数据不需要URL
                                "actual_score": actual_score,
                                "score_for_cache": score_for_cache,
                                "detail_params": {
                                    "home": match_info.get("home"),
                                    "away": match_info.get("away"),
                                    "league": match_info.get("league"),
                                    "kickoff": match_info.get("kickoff")
                                }
                            })
                            date_matches += 1
                    except Exception as e:
                        app.logger.warning(f"读取比赛文件失败: {json_file.name}, {e}")
                        continue
                
                if date_matches > 0:
                    app.logger.info(f"  {current_date.strftime('%Y-%m-%d')}: 读取 {date_matches} 场比赛")
                    date_count += 1
            
            current_date += timedelta(days=1)
        
        app.logger.info(f"找到 {len(matches)} 场比赛（从 {date_str} 至今，扫描了 {date_count} 天）")
        
        return jsonify({
            "success": True,
            "matches": matches,
            "total": len(matches),
            "date_range": f"{date_str} 至 {today.strftime('%Y-%m-%d')}"
        })
        
    except Exception as exc:
        app.logger.exception("获取比赛列表失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/backtest/batch", methods=["POST"])
def api_backtest_batch():
    """
    批量回测接口
    """
    try:
        data = request.get_json(force=True) or {}
        matches = data.get("matches", [])
        
        if not matches:
            return jsonify({"success": False, "message": "请提供比赛列表"}), 400
        
        app.logger.info(f"开始批量回测 {len(matches)} 场比赛")
        
        # 执行批量回测
        result = backtest_engine.batch_backtest(matches)
        
        return jsonify({
            "success": True,
            "total": result.get("total", 0),
            "success_count": result.get("success", 0),
            "failed": result.get("failed", 0),
            "statistics": result.get("statistics", {}),
            "results": result.get("results", [])
        })
        
    except Exception as exc:
        app.logger.exception("批量回测失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/collect/progress", methods=["GET"])
def api_collect_progress():
    """查询当前批量采集的实时进度"""
    with collect_progress_lock:
        return jsonify(collect_progress.copy())


@app.route("/api/collect/batch", methods=["POST"])
def api_collect_batch():
    """
    批量采集明细（纯采集，不回测）
    
    请求参数:
    {
        "matches": [
            {
                "home": "主队",
                "away": "客队",
                "league": "联赛",
                "kickoff": "2025-11-10 08:30",
                "detail_url": "...",
                "detail_params": {...},
                "label": "...",
                "score": "2-1"
            },
            ...
        ]
    }
    """
    try:
        data = request.get_json(force=True) or {}
        matches = data.get('matches', [])
        
        if not matches:
            return jsonify({"success": False, "message": "请提供比赛列表"}), 400
        
        # 🔥 初始化进度跟踪（增强版 - 每场比赛状态）
        match_details = []
        for m in matches:
            match_label = m.get('label') or f"{m.get('home')} vs {m.get('away')}"
            match_details.append({
                "match": match_label,
                "league": m.get('league', ''),
                "kickoff": m.get('kickoff', ''),
                "status": "pending",  # pending|collecting|success|failed|skipped
                "message": "等待采集",
                "start_time": None,
                "end_time": None,
            })
        
        with collect_progress_lock:
            collect_progress.update({
                "active": True,
                "total": len(matches),
                "processed": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "data_cleared": 0,
                "current_match": "",
                "start_time": datetime.now().isoformat(),
                "error_details": [],
                "match_details": match_details,  # 🆕 每场比赛状态
                "eta_seconds": len(matches) * 8,  # 预估每场8秒
                "speed": 0,
            })
        
        app.logger.info(f"开始批量采集 {len(matches)} 场比赛的明细（含盘口）")
        
        total = len(matches)
        collected = 0
        failed = 0
        detail_success = 0
        handicap_success = 0
        results = []
        
        # 🚀 优化：先批量获取当天所有比赛的盘口数据（只请求一次500.com）
        daily_handicaps_cache = {}
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"🚀 步骤0: 批量获取盘口数据（优化：一次请求获取全天数据）")
        app.logger.info(f"{'='*80}")
        
        # 按日期分组比赛
        matches_by_date = {}
        for match in matches:
            kickoff = match.get('kickoff', '')
            if ' ' in kickoff:
                match_date = kickoff.split(' ')[0]
            else:
                match_date = kickoff
            
            if match_date not in matches_by_date:
                matches_by_date[match_date] = []
            matches_by_date[match_date].append(match)
        
        # 对每个日期，一次性获取全天盘口数据
        for match_date, date_matches in matches_by_date.items():
            app.logger.info(f"  📥 获取 {match_date} 的盘口数据（{len(date_matches)}场比赛）...")
            daily_handicaps = lottery500_client.fetch_daily_handicaps(match_date)
            daily_handicaps_cache[match_date] = daily_handicaps
            app.logger.info(f"  ✅ {match_date}: 获取到 {len(daily_handicaps)} 场比赛的盘口数据")
        
        app.logger.info(f"\n✅ 盘口数据预加载完成！共 {sum(len(h) for h in daily_handicaps_cache.values())} 场比赛")
        app.logger.info(f"{'='*80}\n")
        
        # 🆕 辅助函数：更新单场比赛状态
        def update_match_status(match_idx, status, message):
            with collect_progress_lock:
                if match_idx < len(collect_progress["match_details"]):
                    collect_progress["match_details"][match_idx]["status"] = status
                    collect_progress["match_details"][match_idx]["message"] = message
                    if status == "collecting":
                        collect_progress["match_details"][match_idx]["start_time"] = datetime.now().isoformat()
                    elif status in ["success", "failed", "skipped"]:
                        collect_progress["match_details"][match_idx]["end_time"] = datetime.now().isoformat()
        
        # 🆕 计算采集速度和ETA
        collect_start_time = datetime.now()
        
        for idx, match in enumerate(matches, 1):
            match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
            match_idx = idx - 1  # 0-based index
            
            # 🔥 更新当前处理的比赛状态为"采集中"
            update_match_status(match_idx, "collecting", "正在采集...")
            with collect_progress_lock:
                collect_progress["current_match"] = match_label
                # 计算速度和ETA
                elapsed = (datetime.now() - collect_start_time).total_seconds()
                if elapsed > 0 and idx > 1:
                    speed = (idx - 1) / (elapsed / 60)  # 场/分钟
                    remaining = total - idx + 1
                    eta = remaining * (elapsed / (idx - 1))
                    collect_progress["speed"] = round(speed, 1)
                    collect_progress["eta_seconds"] = int(eta)
            
            # 🔥 清晰的进度显示
            progress_percent = int((idx / total) * 100)
            app.logger.info(f"\n{'='*80}")
            app.logger.info(f"📊 进度: [{idx}/{total}] ({progress_percent}%) - 已完成 {collected} 场，失败 {failed} 场")
            app.logger.info(f"⚽ 正在采集: {match_label}")
            app.logger.info(f"{'='*80}")
            
            # 🔥 检查缓存（已采集成功的直接跳过，避免重复采集）
            if detail_cache_manager.has_cache(match):
                app.logger.info(f"  ⏭️  已有缓存，跳过采集")
                collected += 1
                update_match_status(match_idx, "skipped", "已有缓存")
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["success"] += 1
                    collect_progress["skipped"] += 1
                results.append({
                    "match": match_label,
                    "status": "skipped",
                    "message": "已有缓存"
                })
                continue
            
            # 1. 获取交易明细
            detail_url = match.get('detail_url')
            if not detail_url:
                error_reason = "缺少明细URL"
                app.logger.warning(f"  ⚠️  {error_reason}")
                failed += 1
                update_match_status(match_idx, "failed", error_reason)
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["failed"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_reason,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": error_reason
                })
                continue
            
            app.logger.info(f"  📡 抓取明细页面...")
            
            detail_html = bifaw_client.fetch_match_detail_selenium(
                detail_url=detail_url,
                match=match,
                detail_params=match.get('detail_params')
            )
            
            if not detail_html:
                error_reason = "明细页面抓取失败（网络超时或必发网拒绝）"
                app.logger.error(f"  ❌ {error_reason}")
                failed += 1
                update_match_status(match_idx, "failed", error_reason)
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["failed"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_reason,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": error_reason
                })
                continue
            
            # 2. 解析明细
            app.logger.info(f"  📋 解析交易明细...")
            parsed_data = parse_bifa_html(detail_html)
            
            if isinstance(parsed_data, str):
                error_reason = f"HTML解析失败: {parsed_data}"
                app.logger.error(f"  ❌ {error_reason}")
                failed += 1
                update_match_status(match_idx, "failed", error_reason)
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["failed"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_reason,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": error_reason
                })
                continue
            
            if parsed_data.empty:
                error_reason = "解析结果为空（可能是完场后数据已被必发网清空）"
                app.logger.warning(f"  ⚠️  {error_reason}")
                failed += 1
                update_match_status(match_idx, "failed", error_reason)
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["failed"] += 1
                    collect_progress["data_cleared"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_reason,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": error_reason
                })
                continue
            
            detail_success += 1
            app.logger.info(f"  ✅ 明细解析成功: {len(parsed_data)} 行")
            
            # 3. 获取盘口（从预加载的缓存中查找，无需网络请求）
            app.logger.info(f"  🎯 匹配让球盘口（从本地缓存）...")
            
            handicap_data = None
            try:
                home = match.get('home', '')
                away = match.get('away', '')
                kickoff = match.get('kickoff', '')
                
                if all([home, away, kickoff]):
                    # 提取日期
                    match_date = kickoff.split(' ')[0] if ' ' in kickoff else kickoff
                    
                    # 从预加载的缓存中查找
                    if match_date in daily_handicaps_cache:
                        daily_handicaps = daily_handicaps_cache[match_date]
                        matched = lottery500_client.find_handicap_from_daily_data(
                            daily_handicaps=daily_handicaps,
                            home_team=home,
                            away_team=away,
                            match_time=kickoff
                        )
                        
                        if matched:
                            # 转换为标准格式
                            handicap_data = {
                                'fid': matched['fid'],
                                'current_handicap_str': matched['current_handicap_str'],
                                'current_handicap': matched['current_handicap']
                            }
                            # 🔥 增强盘口数据：获取澳门的初盘和即时盘详细数据
                            handicap_data = enhance_handicap_with_initial_data(handicap_data, lottery500_client, app.logger)
                            handicap_str = f"{handicap_data.get('current_handicap_str')} ({handicap_data.get('current_handicap')})"
                            app.logger.info(f"  ✅ 盘口: {handicap_str}")
                            handicap_success += 1
                        else:
                            app.logger.warning(f"  ⚠️  未找到盘口数据（队名或时间不匹配）")
                    else:
                        app.logger.warning(f"  ⚠️  {match_date} 的盘口数据未预加载")
            except Exception as e:
                app.logger.warning(f"  ⚠️  盘口匹配失败: {e}")
            
            # 4. 保存到缓存
            app.logger.info(f"  💾 保存到本地缓存...")
            
            metadata = parsed_data.attrs.get("metadata", [])
            success = detail_cache_manager.save_detail(
                match_info=match,
                trade_data=parsed_data,
                handicap_data=handicap_data,
                metadata=metadata
            )
            
            if success:
                collected += 1
                app.logger.info(f"  ✅ 采集成功: {len(parsed_data)} 行数据已保存")
                
                # 🔥 更新成功进度和状态
                update_match_status(match_idx, "success", f"成功 - {len(parsed_data)}行")
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["success"] += 1
                
                results.append({
                    "match": match_label,
                    "status": "success",
                    "rows": len(parsed_data),
                    "handicap": handicap_data.get('current_handicap_str') if handicap_data else None
                })
            else:
                error_reason = "保存到本地缓存失败（可能是磁盘空间不足或权限问题）"
                failed += 1
                app.logger.error(f"  ❌ {error_reason}")
                
                # 🔥 更新失败进度和状态
                update_match_status(match_idx, "failed", error_reason)
                with collect_progress_lock:
                    collect_progress["processed"] = idx
                    collect_progress["failed"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_reason,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                
                results.append({
                    "match": match_label,
                    "status": "failed",
                    "message": error_reason
                })
            
            # 延迟1秒，避免对必发网请求过快（盘口数据已预加载，无需等待）
            if idx < total:
                time_module.sleep(1)
        
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"✅ 批量采集完成")
        app.logger.info(f"  总计: {total} 场")
        app.logger.info(f"  成功: {collected} 场")
        app.logger.info(f"  失败: {failed} 场")
        app.logger.info(f"  明细采集成功: {detail_success} 场")
        app.logger.info(f"  盘口采集成功: {handicap_success} 场")
        
        # 🔥 输出错误详情总结
        if failed > 0:
            with collect_progress_lock:
                error_details = collect_progress.get("error_details", [])
            if error_details:
                app.logger.info(f"\n❌ 失败详情 ({len(error_details)} 场):")
                for idx, err in enumerate(error_details, 1):
                    app.logger.error(f"  {idx}. [{err['timestamp']}] {err['match']}")
                    app.logger.error(f"     原因: {err['reason']}")
                app.logger.info(f"\n💡 提示: 失败的比赛不会自动重试，原因:")
                app.logger.info(f"  - 网络错误: 必发网可能临时拒绝访问，需要稍后手动重试")
                app.logger.info(f"  - 数据已清空: 完场比赛的交易明细会在24-48小时后被必发网删除")
                app.logger.info(f"  - 解析错误: 页面结构变化，需要更新解析逻辑")
        
        app.logger.info(f"{'='*80}\n")
        
        # 🔥 标记采集完成
        with collect_progress_lock:
            collect_progress["active"] = False
            collect_progress["current_match"] = "已完成"
        
        return jsonify({
            "success": True,
            "total": total,
            "success_count": collected,
            "failed": failed,
            "statistics": {
                "detail_success": detail_success,
                "handicap_success": handicap_success
            },
            "results": results
        })
        
    except Exception as exc:
        app.logger.exception("批量采集失败")
        # 🔥 异常时也要标记完成
        with collect_progress_lock:
            collect_progress["active"] = False
            collect_progress["current_match"] = "异常中断"
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/collect/batch_concurrent", methods=["POST"])
def api_collect_batch_concurrent():
    """
    🚀 并发批量采集（加速版）
    
    使用线程池并发采集，速度提升3-5倍
    
    请求参数:
    {
        "matches": [...],
        "workers": 3  // 并发数，默认3，最大5
    }
    """
    try:
        data = request.get_json(force=True) or {}
        matches = data.get('matches', [])
        workers = min(int(data.get('workers', 3)), 5)  # 最大5并发，避免触发反爬
        
        if not matches:
            return jsonify({"success": False, "message": "请提供比赛列表"}), 400
        
        # 初始化进度跟踪
        match_details = []
        for m in matches:
            match_label = m.get('label') or f"{m.get('home')} vs {m.get('away')}"
            match_details.append({
                "match": match_label,
                "league": m.get('league', ''),
                "kickoff": m.get('kickoff', ''),
                "status": "pending",
                "message": "等待采集",
                "start_time": None,
                "end_time": None,
            })
        
        with collect_progress_lock:
            collect_progress.update({
                "active": True,
                "total": len(matches),
                "processed": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "data_cleared": 0,
                "current_match": "",
                "start_time": datetime.now().isoformat(),
                "error_details": [],
                "match_details": match_details,
                "eta_seconds": len(matches) * 5 / workers,  # 并发预估
                "speed": 0,
            })
        
        app.logger.info(f"🚀 开始并发采集 {len(matches)} 场比赛（{workers}并发）")
        
        # 预加载盘口数据
        daily_handicaps_cache = {}
        matches_by_date = {}
        for match in matches:
            kickoff = match.get('kickoff', '')
            match_date = kickoff.split(' ')[0] if ' ' in kickoff else kickoff
            if match_date not in matches_by_date:
                matches_by_date[match_date] = []
            matches_by_date[match_date].append(match)
        
        for match_date, date_matches in matches_by_date.items():
            daily_handicaps = lottery500_client.fetch_daily_handicaps(match_date)
            daily_handicaps_cache[match_date] = daily_handicaps
            app.logger.info(f"  ✅ {match_date}: 预加载 {len(daily_handicaps)} 场盘口")
        
        # 线程安全的结果收集
        results = []
        results_lock = threading.Lock()
        processed_count = [0]  # 使用列表以便在闭包中修改
        success_count = [0]
        failed_count = [0]
        collect_start_time = datetime.now()
        
        def collect_single_match(idx, match):
            """采集单场比赛（线程任务）"""
            match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
            match_idx = idx
            
            try:
                # 更新状态为采集中
                with collect_progress_lock:
                    if match_idx < len(collect_progress["match_details"]):
                        collect_progress["match_details"][match_idx]["status"] = "collecting"
                        collect_progress["match_details"][match_idx]["message"] = "正在采集..."
                        collect_progress["match_details"][match_idx]["start_time"] = datetime.now().isoformat()
                        collect_progress["current_match"] = match_label
                
                # 检查缓存
                if detail_cache_manager.has_cache(match):
                    with collect_progress_lock:
                        if match_idx < len(collect_progress["match_details"]):
                            collect_progress["match_details"][match_idx]["status"] = "skipped"
                            collect_progress["match_details"][match_idx]["message"] = "已有缓存"
                            collect_progress["match_details"][match_idx]["end_time"] = datetime.now().isoformat()
                        collect_progress["skipped"] += 1
                        collect_progress["success"] += 1
                        processed_count[0] += 1
                        collect_progress["processed"] = processed_count[0]
                    with results_lock:
                        results.append({"match": match_label, "status": "skipped"})
                        success_count[0] += 1
                    return
                
                # 获取明细
                detail_url = match.get('detail_url')
                if not detail_url:
                    raise Exception("缺少明细URL")
                
                detail_html = bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match,
                    detail_params=match.get('detail_params')
                )
                
                if not detail_html:
                    raise Exception("明细抓取失败")
                
                # 解析
                parsed_data = parse_bifa_html(detail_html)
                if isinstance(parsed_data, str) or parsed_data.empty:
                    raise Exception("解析失败或数据为空")
                
                # 获取盘口
                kickoff = match.get('kickoff', '')
                match_date = kickoff.split(' ')[0] if ' ' in kickoff else kickoff
                daily_handicaps = daily_handicaps_cache.get(match_date, {})
                handicap_data = lottery500_client.match_handicap(
                    home=match.get('home', ''),
                    away=match.get('away', ''),
                    kickoff=kickoff,
                    daily_handicaps=daily_handicaps
                )
                
                # 🔥 增强盘口数据：获取澳门的初盘和即时盘详细数据
                if handicap_data:
                    handicap_data = enhance_handicap_with_initial_data(handicap_data, lottery500_client, app.logger)
                
                # 保存
                metadata = parsed_data.attrs.get("metadata", [])
                success = detail_cache_manager.save_detail(
                    match_info=match,
                    trade_data=parsed_data,
                    handicap_data=handicap_data,
                    metadata=metadata
                )
                
                if success:
                    with collect_progress_lock:
                        if match_idx < len(collect_progress["match_details"]):
                            collect_progress["match_details"][match_idx]["status"] = "success"
                            collect_progress["match_details"][match_idx]["message"] = f"成功 - {len(parsed_data)}行"
                            collect_progress["match_details"][match_idx]["end_time"] = datetime.now().isoformat()
                        collect_progress["success"] += 1
                        processed_count[0] += 1
                        collect_progress["processed"] = processed_count[0]
                        # 更新速度和ETA
                        elapsed = (datetime.now() - collect_start_time).total_seconds()
                        if elapsed > 0:
                            speed = processed_count[0] / (elapsed / 60)
                            remaining = len(matches) - processed_count[0]
                            eta = remaining * (elapsed / processed_count[0]) if processed_count[0] > 0 else 0
                            collect_progress["speed"] = round(speed, 1)
                            collect_progress["eta_seconds"] = int(eta)
                    with results_lock:
                        results.append({"match": match_label, "status": "success", "rows": len(parsed_data)})
                        success_count[0] += 1
                else:
                    raise Exception("保存失败")
                    
            except Exception as e:
                error_msg = str(e)[:50]
                with collect_progress_lock:
                    if match_idx < len(collect_progress["match_details"]):
                        collect_progress["match_details"][match_idx]["status"] = "failed"
                        collect_progress["match_details"][match_idx]["message"] = error_msg
                        collect_progress["match_details"][match_idx]["end_time"] = datetime.now().isoformat()
                    collect_progress["failed"] += 1
                    collect_progress["error_details"].append({
                        "match": match_label,
                        "reason": error_msg,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    processed_count[0] += 1
                    collect_progress["processed"] = processed_count[0]
                with results_lock:
                    results.append({"match": match_label, "status": "failed", "message": error_msg})
                    failed_count[0] += 1
        
        # 使用线程池并发执行
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(collect_single_match, idx, match): idx 
                      for idx, match in enumerate(matches)}
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    app.logger.error(f"并发任务异常: {e}")
        
        # 完成
        with collect_progress_lock:
            collect_progress["active"] = False
            collect_progress["current_match"] = "已完成"
        
        app.logger.info(f"✅ 并发采集完成: 成功{success_count[0]} 失败{failed_count[0]} / 共{len(matches)}场")
        
        return jsonify({
            "success": True,
            "total": len(matches),
            "success_count": success_count[0],
            "failed": failed_count[0],
            "workers": workers,
            "results": results
        })
        
    except Exception as exc:
        app.logger.exception("并发采集失败")
        with collect_progress_lock:
            collect_progress["active"] = False
            collect_progress["current_match"] = "异常中断"
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/collect/batch_range", methods=["POST"])
def api_collect_batch_range():
    """
    日期区间批量采集明细（Phase 2）
    
    从起始日期到今天，逐日采集完场比赛明细
    
    请求参数:
    {
        "start_date": "2025-11-01",
        "filter_by_handicap": true,
        "rows": 9999,  // 每天查询的比赛数量，默认9999（实际无限制）
        "skip_cached": true  // 是否跳过已有缓存
    }
    """
    from datetime import datetime, timedelta
    import sys
    
    # 🔥 立即输出日志，用于诊断
    app.logger.info("=" * 80)
    app.logger.info("🚀 收到日期区间采集请求")
    app.logger.info("=" * 80)
    sys.stdout.flush()
    
    try:
        data = request.get_json(force=True) or {}
        start_date_str = data.get('start_date')
        filter_by_handicap = data.get('filter_by_handicap', False)  # 🔥 默认关闭
        rows = int(data.get('rows', 9999) or 9999)
        skip_cached = data.get('skip_cached', True)
        
        if not start_date_str:
            return jsonify({"success": False, "message": "请提供起始日期（格式：YYYY-MM-DD）"}), 400
        
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "message": "日期格式错误，请使用 YYYY-MM-DD 格式"}), 400
        
        # 计算到今天的天数
        today = datetime.now()
        if start_date > today:
            return jsonify({"success": False, "message": "起始日期不能晚于今天"}), 400
        
        total_days = (today - start_date).days + 1
        
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"🚀 开始日期区间批量采集")
        app.logger.info(f"  起始日期: {start_date_str}")
        app.logger.info(f"  结束日期: {today.strftime('%Y-%m-%d')}")
        app.logger.info(f"  总天数: {total_days} 天")
        app.logger.info(f"  盘口过滤: {'开启' if filter_by_handicap else '关闭'}")
        app.logger.info(f"  跳过缓存: {'是' if skip_cached else '否'}")
        app.logger.info(f"{'='*80}\n")
        
        # 🔥 第一阶段：快速扫描，统计每天的比赛场次
        app.logger.info(f"\n{'#'*80}")
        app.logger.info(f"📊 第一阶段：快速扫描各天比赛场次")
        app.logger.info(f"{'#'*80}\n")
        
        # 检查必发客户端状态
        app.logger.info(f"✓ 必发网客户端状态检查...")
        try:
            # 测试一下客户端是否正常
            app.logger.info(f"✓ 500彩票客户端状态检查...")
        except Exception as e:
            app.logger.error(f"❌ 客户端初始化检查失败: {e}")
        
        date_match_map = {}  # {date_str: matches_list}
        total_matches_to_collect = 0
        scan_current_date = start_date
        scan_day_idx = 0
        
        app.logger.info(f"✓ 开始扫描，预计扫描 {total_days} 天...\n")
        
        while scan_current_date <= today:
            scan_day_idx += 1
            date_str = scan_current_date.strftime("%Y-%m-%d")
            
            try:
                app.logger.info(f"  [{scan_day_idx}/{total_days}] 扫描 {date_str}...")
                
                # 获取完场比赛
                # 🔧 修复：fetch_finished_matches 返回元组 (page_html, matches, metadata)
                page_html, matches, metadata = bifaw_client.fetch_finished_matches(target_date=scan_current_date, rows=rows)
                
                if not matches:
                    app.logger.info(f"    ⚠️  无完场比赛数据")
                    date_match_map[date_str] = []
                    scan_current_date += timedelta(days=1)
                    continue
                
                # 如果开启盘口过滤，匹配盘口
                if filter_by_handicap:
                    daily_handicaps = lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
                    
                    # 构建匹配索引
                    bifaw_match_map = {}
                    for match in matches:
                        home = match.get('home_team', '') or match.get('home', '')
                        away = match.get('away_team', '') or match.get('away', '')
                        time = match.get('match_time', '') or match.get('kickoff', '')
                        
                        home_clean = lottery500_client._clean_team_name(home)
                        away_clean = lottery500_client._clean_team_name(away)
                        
                        if ' ' in time:
                            time_str = time.split(' ')[1][:5]
                        else:
                            time_str = time[:5] if time else ''
                        
                        key1 = f"{home_clean}_{away_clean}_{time_str}"
                        key2 = f"{home}_{away}_{time_str}"
                        bifaw_match_map[key1] = match
                        bifaw_match_map[key2] = match
                    
                    # 匹配盘口
                    filtered_matches = []
                    for match_key, handicap_data in daily_handicaps.items():
                        home_500 = handicap_data['home_team']
                        away_500 = handicap_data['away_team']
                        time_500 = handicap_data['time'][:5]
                        
                        home_clean = lottery500_client._clean_team_name(home_500)
                        away_clean = lottery500_client._clean_team_name(away_500)
                        
                        bifaw_match = None
                        for key in [
                            f"{home_clean}_{away_clean}_{time_500}",
                            f"{home_500}_{away_500}_{time_500}",
                        ]:
                            if key in bifaw_match_map:
                                bifaw_match = bifaw_match_map[key]
                                break
                        
                        if bifaw_match:
                            merged_match = bifaw_match.copy()
                            merged_match['handicap_preview'] = {
                                'handicap_str': handicap_data['current_handicap_str'],
                                'handicap': handicap_data['current_handicap'],
                                'fid': handicap_data['fid']
                            }
                            filtered_matches.append(merged_match)
                    
                    date_match_map[date_str] = filtered_matches
                    app.logger.info(f"    ✅ {len(filtered_matches)} 场（有盘口+明细）")
                else:
                    date_match_map[date_str] = matches
                    app.logger.info(f"    ✅ {len(matches)} 场")
                
                total_matches_to_collect += len(date_match_map[date_str])
                
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                app.logger.error(f"    ❌ 扫描失败: {type(e).__name__}: {str(e)}")
                app.logger.error(f"    详细错误:\n{error_detail[:500]}")
                date_match_map[date_str] = []
            
            scan_current_date += timedelta(days=1)
            time_module.sleep(1)  # 增加延迟，避免请求过快
        
        app.logger.info(f"\n✅ 扫描完成！")
        app.logger.info(f"  总天数: {total_days} 天")
        app.logger.info(f"  总比赛: {total_matches_to_collect} 场")
        app.logger.info(f"{'='*80}\n")
        
        if total_matches_to_collect == 0:
            return jsonify({
                "success": True,
                "message": "所选日期区间内无符合条件的比赛",
                "total_days": total_days,
                "total_matches": 0,
                "total_collected": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "daily_results": []
            })
        
        # 🔥 第二阶段：按场次进行采集
        app.logger.info(f"\n{'#'*80}")
        app.logger.info(f"🚀 第二阶段：开始逐场采集明细")
        app.logger.info(f"{'#'*80}\n")
        
        # 统计
        daily_results = []
        total_collected = 0
        total_failed = 0
        total_skipped = 0
        match_idx = 0  # 当前采集到第几场
        
        # 逐日采集
        day_idx = 0
        
        for date_str, matches in date_match_map.items():
            day_idx += 1
            
            if len(matches) == 0:
                daily_results.append({
                    "date": date_str,
                    "matches": 0,
                    "collected": 0,
                    "failed": 0,
                    "skipped": 0,
                    "error": "无符合条件的比赛"
                })
                continue
            
            app.logger.info(f"\n{'#'*80}")
            app.logger.info(f"📅 [{day_idx}/{total_days}] 日期: {date_str} - 共 {len(matches)} 场")
            app.logger.info(f"{'#'*80}")
            
            # 采集统计
            day_result = {
                "date": date_str,
                "matches": len(matches),
                "collected": 0,
                "failed": 0,
                "skipped": 0,
                "error": None
            }
            
            collected = 0
            failed = 0
            skipped = 0
            
            retry_count = 0
            max_retries = 1
            
            try:
                # 逐场采集明细
                for idx, match in enumerate(matches, 1):
                    match_idx += 1
                    match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
                    
                    # 🔥 显示场次进度
                    progress_percent = int((match_idx / total_matches_to_collect) * 100)
                    app.logger.info(f"\n  ⚽ [{match_idx}/{total_matches_to_collect}] ({progress_percent}%) - {match_label}")
                    
                    # 检查是否已有缓存
                    if skip_cached and detail_cache_manager.has_cache(match):
                        skipped += 1
                        app.logger.info(f"    ⏭️  跳过（已有缓存）")
                        continue
                    
                    # 获取明细（带重试）
                    detail_success_flag = False
                    for retry in range(max_retries + 1):
                        try:
                            if retry > 0:
                                app.logger.info(f"    🔄 重试第 {retry} 次...")
                            
                            detail_url = match.get('detail_url')
                            if not detail_url:
                                app.logger.warning(f"    ❌ 缺少明细URL")
                                break
                            
                            detail_html = bifaw_client.fetch_match_detail_selenium(
                                detail_url=detail_url,
                                match=match,
                                detail_params=match.get('detail_params')
                            )
                            
                            if not detail_html:
                                if retry < max_retries:
                                    time_module.sleep(2)
                                    continue
                                app.logger.error(f"    ❌ 明细页面抓取失败")
                                break
                            
                            parsed_data = parse_bifa_html(detail_html)
                            
                            if isinstance(parsed_data, str) or parsed_data.empty:
                                if retry < max_retries:
                                    time_module.sleep(2)
                                    continue
                                app.logger.error(f"    ❌ 解析失败")
                                break
                            
                            # 获取盘口
                            handicap_data = None
                            if match.get('handicap_preview'):
                                handicap_data = {
                                    'fid': match['handicap_preview']['fid'],
                                    'current_handicap_str': match['handicap_preview']['handicap_str'],
                                    'current_handicap': match['handicap_preview']['handicap']
                                }
                            
                            # 保存
                            metadata = parsed_data.attrs.get("metadata", [])
                            success = detail_cache_manager.save_detail(
                                match_info=match,
                                trade_data=parsed_data,
                                handicap_data=handicap_data,
                                metadata=metadata
                            )
                            
                            if success:
                                collected += 1
                                app.logger.info(f"    ✅ 成功: {len(parsed_data)} 行")
                                detail_success_flag = True
                                break
                            else:
                                if retry < max_retries:
                                    time_module.sleep(2)
                                    continue
                                app.logger.error(f"    ❌ 保存失败")
                                break
                        except Exception as e:
                            if retry < max_retries:
                                app.logger.warning(f"    ⚠️  采集异常，准备重试: {str(e)}")
                                time_module.sleep(2)
                            else:
                                app.logger.error(f"    ❌ 采集失败（已重试{max_retries}次）: {str(e)}")
                            break
                    
                    if not detail_success_flag and match_idx > 0:
                        failed += 1
                    
                    # 延迟
                    time_module.sleep(1)
                
                day_result["collected"] = collected
                day_result["failed"] = failed
                day_result["skipped"] = skipped
                
                total_collected += collected
                total_failed += failed
                total_skipped += skipped
                
                app.logger.info(f"\n  ✅ {date_str} 完成: 成功 {collected} / 失败 {failed} / 跳过 {skipped} (共{len(matches)}场)")
                
            except Exception as e:
                app.logger.error(f"  ❌ {date_str} 处理失败: {str(e)}")
                day_result["error"] = str(e)
            
            daily_results.append(day_result)
        
        # 汇总
        app.logger.info(f"\n{'='*80}")
        app.logger.info(f"✅ 日期区间批量采集完成")
        app.logger.info(f"  总天数: {total_days} 天")
        app.logger.info(f"  总比赛: {total_matches_to_collect} 场")
        app.logger.info(f"  成功: {total_collected} 场")
        app.logger.info(f"  失败: {total_failed} 场")
        app.logger.info(f"  跳过: {total_skipped} 场")
        app.logger.info(f"{'='*80}\n")
        
        return jsonify({
            "success": True,
            "total_days": total_days,
            "total_matches": total_matches_to_collect,
            "total_collected": total_collected,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "daily_results": daily_results
        })
        
    except Exception as exc:
        import traceback
        error_traceback = traceback.format_exc()
        
        # 🔥 详细的错误日志
        app.logger.error("=" * 80)
        app.logger.error("❌ 日期区间批量采集失败")
        app.logger.error("=" * 80)
        app.logger.error(f"错误类型: {type(exc).__name__}")
        app.logger.error(f"错误信息: {str(exc)}")
        app.logger.error(f"\n完整堆栈跟踪:\n{error_traceback}")
        app.logger.error("=" * 80)
        
        return jsonify({
            "success": False, 
            "message": f"{type(exc).__name__}: {str(exc)}",
            "error_type": type(exc).__name__,
            "traceback": error_traceback[:500]  # 前500字符
        }), 500


def _collect_single_match_worker(match, match_idx, total_matches, date_str, progress_queue, worker_session_id):
    """
    采集单场比赛的工作函数（可复用）
    
    Args:
        match: 比赛信息字典
        match_idx: 当前比赛索引
        total_matches: 总比赛数
        date_str: 日期字符串
        progress_queue: 进度队列（可选）
        worker_session_id: 会话ID
    """
    import time
    
    match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
    match_start_time = time.time()
    
    def send_progress(msg_type, **kwargs):
        """发送进度消息到队列"""
        if progress_queue:
            kwargs['type'] = msg_type
            kwargs['label'] = match_label
            kwargs['current'] = match_idx
            kwargs['total'] = total_matches
            progress_queue.put(kwargs)
    
    try:
        # 推送开始采集
        send_progress('match_start')
        
        # 采集明细（带重试）
        detail_success_flag = False
        error_detail = None
        
        for retry in range(2):  # 重试1次
            try:
                # 显示重试提示
                if retry > 0:
                    send_progress('match_step', step=f'🔄 第{retry+1}次尝试...', step_num=0, total_steps=4)
                
                detail_url = match.get('detail_url')
                if not detail_url:
                    error_detail = "缺少明细URL"
                    break
                
                # 步骤1：抓取明细
                detail_html = bifaw_client.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match,
                    detail_params=match.get('detail_params')
                )
                
                if not detail_html:
                    error_detail = "页面抓取失败"
                    if retry < 1:
                        send_progress('match_step', step='⚠️ 页面抓取失败，准备重试...', step_num=0, total_steps=4)
                        time.sleep(2)
                        continue
                    break
                
                # 步骤2：解析数据
                parsed_data = parse_bifa_html(detail_html)
                
                if isinstance(parsed_data, str):
                    error_detail = parsed_data
                    if "未能从网页表格中识别有效数据" in parsed_data:
                        error_detail = "数据已清空（必发网已删除完场比赛明细）"
                        send_progress('match_failed', error=error_detail)
                        return {'status': 'failed', 'error': error_detail, 'data_cleared': True}
                    if retry < 1:
                        send_progress('match_step', step='⚠️ 数据解析失败，准备重试...', step_num=0, total_steps=4)
                        time.sleep(2)
                        continue
                    break
                elif parsed_data.empty:
                    error_detail = "解析结果为空"
                    if retry < 1:
                        send_progress('match_step', step='⚠️ 解析结果为空，准备重试...', step_num=0, total_steps=4)
                        time.sleep(2)
                        continue
                    break
                
                # 步骤3：获取盘口数据
                handicap_data = None
                if match.get('handicap_preview'):
                    handicap_data = {
                        'fid': match['handicap_preview']['fid'],
                        'current_handicap_str': match['handicap_preview']['handicap_str'],
                        'current_handicap': match['handicap_preview']['handicap']
                    }
                    try:
                        handicap_data = enhance_handicap_with_initial_data(handicap_data, lottery500_client, app.logger)
                    except Exception as h_err:
                        app.logger.warning(f"  ⚠️ 盘口数据获取失败: {h_err}")
                
                # 步骤4：保存数据
                metadata = parsed_data.attrs.get("metadata", [])
                success = detail_cache_manager.save_detail(
                    match_info=match,
                    trade_data=parsed_data,
                    handicap_data=handicap_data,
                    metadata=metadata,
                    html_content=detail_html
                )
                
                if success:
                    detail_success_flag = True
                    # 记录成功到进度
                    if worker_session_id:
                        progress_manager.update_progress(worker_session_id, match, 'success', date_str)
                    # 计算采集耗时
                    elapsed = time.time() - match_start_time
                    send_progress('match_success', rows=len(parsed_data), elapsed=round(elapsed, 1))
                    return {'status': 'success', 'rows': len(parsed_data)}
                else:
                    error_detail = "数据保存失败"
                    if retry < 1:
                        send_progress('match_step', step='⚠️ 数据保存失败，准备重试...', step_num=4, total_steps=4)
                        time.sleep(2)
                        continue
                    break
                        
            except Exception as e:
                error_detail = f"异常: {str(e)}"
                if retry < 1:
                    send_progress('match_step', step=f'❌ 出错: {str(e)[:50]}...', step_num=0, total_steps=4)
                    time.sleep(2)
                else:
                    send_progress('match_error', error=str(e))
                break
        
        # 如果到这里还没有成功
        if not detail_success_flag:
            final_error = error_detail or "明细抓取或保存失败"
            if worker_session_id:
                progress_manager.update_progress(worker_session_id, match, 'failed', date_str, final_error)
            send_progress('match_failed', error=final_error)
            return {'status': 'failed', 'error': final_error}
    
    except Exception as e:
        error_msg = f"工作线程异常: {str(e)}"
        app.logger.error(f"采集线程错误 {match_label}: {error_msg}")
        send_progress('match_failed', error=error_msg)
        return {'status': 'error', 'error': error_msg}


@app.route("/api/collect/batch_range_stream", methods=["GET", "POST"])
def api_collect_batch_range_stream():
    """
    日期区间批量采集明细（SSE 流式版本）
    实时推送进度到前端
    支持断点续传：如果提供 resume_session_id，则恢复之前中断的采集
    
    🔒 采集互斥：同一时间只允许一个采集任务运行
    
    支持GET和POST两种方式：
    - GET: 使用query参数（用于EventSource）
    - POST: 使用JSON body（用于fetch）
    """
    from datetime import datetime, timedelta
    
    global active_collection_session
    
    # 🔥 支持GET和POST两种方式获取参数
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # 默认结束日期为昨天
    
    if request.method == 'GET':
        # EventSource使用GET + query参数
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date') or yesterday_str  # 🆕 默认昨天
        filter_by_handicap = request.args.get('filter_by_handicap', 'false').lower() in ('true', '1')  # 🔥 默认关闭
        rows = int(request.args.get('rows', 9999))
        skip_cached = request.args.get('skip_cached', 'true').lower() == 'true'
        resume_session_id = request.args.get('resume_session_id')
        workers = min(int(request.args.get('workers', 1)), 5)  # 并发数，默认1，最大5
    else:
        # fetch使用POST + JSON body
        data = request.get_json(force=True) or {}
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date') or yesterday_str  # 🆕 默认昨天
        filter_by_handicap = data.get('filter_by_handicap', False)  # 🔥 默认关闭
        rows = int(data.get('rows', 9999) or 9999)
        skip_cached = data.get('skip_cached', True)
        resume_session_id = data.get('resume_session_id')  # 断点续传：提供会话ID
        workers = min(int(data.get('workers', 1)), 5)  # 并发数
    
    def generate():
        """生成 SSE 事件流"""
        global active_collection_session
        session_id = None
        session_data = None
        
        # 从外部作用域获取参数（避免闭包问题）
        _start_date_str = start_date_str
        _end_date_str = end_date_str
        _filter_by_handicap = filter_by_handicap
        _rows = rows
        _skip_cached = skip_cached
        _resume_session_id = resume_session_id
        _workers = workers  # 🆕 并发数
        
        # 使用全局工作函数
        # from concurrent.futures import ThreadPoolExecutor, as_completed
        # import queue
        # import time as time_module_perf
        
        # 定义工作函数：采集单场比赛 (已移至全局 _collect_single_match_worker)
        
        # 获取日志流处理器
        log_stream = get_stream_handler()
        
        # 辅助函数：发送消息并记录日志
        def send_message(msg_dict):
            log_manager.add_message(msg_dict)
            return f"data: {json.dumps(msg_dict)}\n\n"
        
        # 📝 辅助函数：推送捕获的后端日志（非生成器版本）
        def get_and_clear_backend_logs():
            """获取并清空后端日志"""
            messages = log_stream.get_messages()
            log_stream.clear()
            return messages
        
        # 🔒 检查是否有正在运行的采集任务
        if not collection_lock.acquire(blocking=False):
            # 无法获取锁，说明有任务正在运行
            if active_collection_session:
                yield send_message({'type': 'error', 'message': f'采集任务正在运行中（会话: {active_collection_session}），请稍后重试或查看历史会话'})
            else:
                yield send_message({'type': 'error', 'message': '采集任务正在运行中，请稍后重试'})
            return
        
        # 🎯 启动日志捕获
        log_stream.start_capture()
        
        try:
            # 🔥 尝试恢复会话
            if _resume_session_id:
                session_data = progress_manager.load_session(_resume_session_id)
                # 🔥 修复：允许恢复 'recovering' 状态的会话
                if session_data and session_data['status'] in ['running', 'paused', 'recovering', 'failed']:
                    session_id = _resume_session_id
                    
                    app.logger.info(f"DEBUG: 尝试恢复会话 {session_id}. 当前参数: start={_start_date_str}, end={_end_date_str}")
                    
                    # 🔥 从会话恢复参数
                    if not _start_date_str:
                        _start_date_str = session_data.get('start_date')
                        # yield f"data: {json.dumps({'type': 'info', 'message': f'DEBUG: 从会话恢复 start_date: {_start_date_str}'})}\n\n"
                    if not _end_date_str:
                        _end_date_str = session_data.get('end_date')
                    
                    # 强制确保 start_date 存在
                    if not _start_date_str and session_data.get('start_date'):
                         _start_date_str = session_data.get('start_date')

                    # filter_by_handicap 也可以恢复，但要注意类型转换
                    if 'filter_by_handicap' in session_data:
                        _filter_by_handicap = session_data['filter_by_handicap']
                    
                    print(f"DEBUG: 恢复后参数: start={_start_date_str}, end={_end_date_str}")
                    
                    # 🔥 立即将状态更新为 'running'，避免卡在 recovering
                    progress_manager.update_session_status(session_id, 'running')
                    
                    yield f"data: {json.dumps({'type': 'resume', 'message': f'恢复会话: {session_id}', 'session_id': session_id})}\n\n"
                    # 发送调试信息到前端
                    yield f"data: {json.dumps({'type': 'info', 'message': f'恢复参数: start={_start_date_str}'})}\n\n"
                    app.logger.info(f"🔄 恢复采集会话: {session_id}，状态: {session_data['status']} → running")
                else:
                    if session_data:
                        status = session_data.get('status', 'unknown')
                        yield f"data: {json.dumps({'type': 'warning', 'message': f'会话状态为 {status}，无法恢复，创建新会话'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'warning', 'message': '会话不存在，创建新会话'})}\n\n"
                    session_id = None
            
            # 无论是否恢复，都发送开始事件，确保前端显示进度条
            yield f"data: {json.dumps({'type': 'start', 'message': '开始日期区间采集', 'session_id': session_id})}\n\n"
            
            if not _start_date_str:
                yield f"data: {json.dumps({'type': 'error', 'message': '请提供起始日期'})}\n\n"
                return
            
            try:
                start_date = datetime.strptime(_start_date_str, "%Y-%m-%d")
            except ValueError:
                yield f"data: {json.dumps({'type': 'error', 'message': '起始日期格式错误'})}\n\n"
                return
            
            # 🔥 处理结束日期
            if _end_date_str:
                try:
                    end_date = datetime.strptime(_end_date_str, "%Y-%m-%d")
                except ValueError:
                    yield f"data: {json.dumps({'type': 'error', 'message': '结束日期格式错误'})}\n\n"
                    return
            else:
                end_date = datetime.now()
                _end_date_str = end_date.strftime("%Y-%m-%d")
            
            # 验证日期范围
            if start_date > end_date:
                yield f"data: {json.dumps({'type': 'error', 'message': '起始日期不能晚于结束日期'})}\n\n"
                return
            
            total_days = (end_date - start_date).days + 1
            
            # 🔥 调试日志
            app.logger.info(f"📅 扫描参数: start_date={_start_date_str}, end_date={_end_date_str}, total_days={total_days}")
            app.logger.info(f"📊 过滤设置: filter_by_handicap={_filter_by_handicap}, rows={_rows}")
            
            # 🔥 第一阶段：扫描
            yield f"data: {json.dumps({'type': 'phase', 'phase': 1, 'message': f'第一阶段：扫描 {total_days} 天'})}\n\n"
            
            date_match_map = {}
            total_matches_to_collect = 0
            scan_current_date = start_date
            scan_day_idx = 0
            
            while scan_current_date <= end_date:
                scan_day_idx += 1
                date_str = scan_current_date.strftime("%Y-%m-%d")
                
                # 推送扫描进度
                # yield f"data: {json.dumps({'type': 'scan', 'day': scan_day_idx, 'total_days': total_days, 'date': date_str})}\n\n"
                yield send_message({'type': 'scan', 'day': scan_day_idx, 'total_days': total_days, 'date': date_str})
                
                # 🔥 添加可见的日志消息 (持久化)
                yield send_message({'type': 'info', 'message': f'正在扫描日期: {date_str} ({scan_day_idx}/{total_days})'})
                    
                    # 捕获网络异常（支持自动重连）
                try:
                    app.logger.info(f"🔍 正在扫描 {date_str} ({scan_day_idx}/{total_days})")
                    
                    # 🔥 使用自动重试功能（账号被顶时会自动重新登录）
                    # 🔧 修复：fetch_finished_matches 返回元组 (page_html, matches, metadata)
                    page_html, matches, metadata = bifaw_client.fetch_finished_matches(
                        target_date=scan_current_date, 
                        rows=_rows,
                        auto_retry=True  # 启用自动重连
                    )
                    
                    app.logger.info(f"  ✅ 获取到 {len(matches) if matches else 0} 场原始比赛")
                    
                    # 📝 推送后端日志（包括登录验证码等信息）
                    backend_logs = get_and_clear_backend_logs()
                    for log_msg in backend_logs:
                        yield send_message(log_msg)
                        
                except Exception as net_err:
                    error_type = type(net_err).__name__
                    error_msg = str(net_err)[:200]
                    
                    app.logger.error(f"获取比赛列表失败 {date_str}: [{error_type}] {error_msg}")
                    
                    # 🔥 推送详细错误信息
                    yield f"data: {json.dumps({'type': 'scan_error', 'date': date_str, 'error': error_msg, 'error_type': error_type})}\n\n"
                    
                    # 🔥 如果是会话过期，推送特殊提示
                    if 'session' in error_msg.lower() or '登录' in error_msg:
                        yield f"data: {json.dumps({'type': 'warning', 'message': '⚠️ 检测到账号被顶，已尝试自动重新登录。如果问题持续，请检查账号状态。'})}\n\n"
                    
                    date_match_map[date_str] = []
                    scan_current_date += timedelta(days=1)
                    continue
                
                if not matches:
                    app.logger.info(f"  ⚠️  {date_str} 无比赛数据")
                    date_match_map[date_str] = []
                    scan_current_date += timedelta(days=1)
                    continue
                
                if _filter_by_handicap:
                    try:
                        daily_handicaps = lottery500_client.fetch_daily_handicaps(date_str, use_cache=False)
                    except Exception as handicap_err:
                        app.logger.error(f"获取盘口数据失败 {date_str}: {handicap_err}")
                        yield f"data: {json.dumps({'type': 'handicap_error', 'date': date_str, 'error': str(handicap_err)})}\n\n"
                        # 盘口获取失败，使用原始比赛列表（不过滤）
                        date_match_map[date_str] = matches
                        scan_current_date += timedelta(days=1)
                        continue
                    
                    bifaw_match_map = {}
                    # 🔥 调试：打印第一个 match 的关键字段 (输出到SSE)
                    if matches:
                        m = matches[0]
                        debug_msg = f"match[0]: home={m.get('home')!r}, away={m.get('away')!r}, kickoff={m.get('kickoff')!r}"
                        yield f"data: {json.dumps({'type': 'debug', 'msg': debug_msg})}\n\n"
                        app.logger.info(f"  🔍 {debug_msg}")
                    
                    for match in matches:
                        home = match.get('home_team', '') or match.get('home', '')
                        away = match.get('away_team', '') or match.get('away', '')
                        time = match.get('match_time', '') or match.get('kickoff', '') or match.get('kickoff_time', '')
                        
                        home_clean = lottery500_client._clean_team_name(home)
                        away_clean = lottery500_client._clean_team_name(away)
                        
                        # 🔥 支持多种时间格式
                        if ' ' in str(time):
                            time_str = str(time).split(' ')[1][:5]
                        elif ':' in str(time):
                            time_str = str(time)[:5]
                        else:
                            time_str = str(time)[:5] if time else ''
                        
                        key1 = f"{home_clean}_{away_clean}_{time_str}"
                        key2 = f"{home}_{away}_{time_str}"
                        # 🔥 额外增加不含时间的 key 作为备用匹配
                        key3 = f"{home_clean}_{away_clean}"
                        key4 = f"{home}_{away}"
                        bifaw_match_map[key1] = match
                        bifaw_match_map[key2] = match
                        bifaw_match_map[key3] = match
                        bifaw_match_map[key4] = match
                    
                    filtered_matches = []
                    app.logger.info(f"  📊 必发比赛Map大小: {len(bifaw_match_map)}")
                    app.logger.info(f"  📊 盘口数据条数: {len(daily_handicaps)}")
                    
                    # 🔥 调试：显示前3个必发比赛 key (输出到SSE)
                    sample_bifaw_keys = list(bifaw_match_map.keys())[:8]
                    yield f"data: {json.dumps({'type': 'debug', 'msg': f'必发keys: {sample_bifaw_keys}'})}\n\n"
                    
                    # 🔥 调试：显示前3个盘口数据 key (输出到SSE)
                    sample_handicap = list(daily_handicaps.items())[:3]
                    for idx, (match_key, hd) in enumerate(sample_handicap):
                        home_500 = hd['home_team']
                        away_500 = hd['away_team']
                        time_500 = hd['time'][:5]
                        home_c = lottery500_client._clean_team_name(home_500)
                        away_c = lottery500_client._clean_team_name(away_500)
                        yield f"data: {json.dumps({'type': 'debug', 'msg': f'盘口[{idx}]: {home_500} vs {away_500} {time_500} -> key: {home_c}_{away_c}_{time_500}'})}\n\n"
                    
                    for match_key, handicap_data in daily_handicaps.items():
                        home_500 = handicap_data['home_team']
                        away_500 = handicap_data['away_team']
                        time_500 = handicap_data['time'][:5]
                        
                        home_clean = lottery500_client._clean_team_name(home_500)
                        away_clean = lottery500_client._clean_team_name(away_500)
                        
                        bifaw_match = None
                        # 🔥 扩展匹配 key 列表，增加备用匹配
                        candidate_keys = [
                            f"{home_clean}_{away_clean}_{time_500}",
                            f"{home_500}_{away_500}_{time_500}",
                            f"{home_clean}_{away_clean}",  # 不含时间
                            f"{home_500}_{away_500}",      # 不含时间
                        ]
                        for key in candidate_keys:
                            if key in bifaw_match_map:
                                bifaw_match = bifaw_match_map[key]
                                app.logger.debug(f"    ✅ 匹配成功: {key}")
                                break
                        
                        if bifaw_match:
                            merged_match = bifaw_match.copy()
                            merged_match['handicap_preview'] = {
                                'handicap_str': handicap_data['current_handicap_str'],
                                'handicap': handicap_data['current_handicap'],
                                'fid': handicap_data['fid']
                            }
                            filtered_matches.append(merged_match)
                        else:
                            app.logger.debug(f"    ❌ 无法匹配: {home_500} vs {away_500} {time_500}")
                    
                    # 🔥 修复：如果盘口匹配后为0，使用原始必发比赛（不丢弃）
                    if len(filtered_matches) == 0:
                        app.logger.warning(f"  ⚠️ 盘口匹配为0，使用原始必发比赛: {len(matches)} 场")
                        yield f"data: {json.dumps({'type': 'warning', 'message': f'盘口数据与必发比赛无交集，使用原始{len(matches)}场比赛'})}\n\n"
                        date_match_map[date_str] = matches
                        match_count = len(matches)
                    else:
                        date_match_map[date_str] = filtered_matches
                        match_count = len(filtered_matches)
                    app.logger.info(f"  🎯 盘口过滤后: {match_count} 场")
                else:
                    date_match_map[date_str] = matches
                    match_count = len(matches)
                    app.logger.info(f"  📊 不过滤: {match_count} 场")
                
                
                total_matches_to_collect += match_count
                
                # 推送每天的扫描结果
                yield f"data: {json.dumps({'type': 'scan_result', 'date': date_str, 'matches': match_count})}\n\n"
            
                scan_current_date += timedelta(days=1)
                
                # 发送心跳，防止连接超时
                yield f": heartbeat\n\n"
                time_module.sleep(1)
            
            # 扫描完成
            app.logger.info(f"✅ 扫描完成！总天数: {total_days}, 总比赛: {total_matches_to_collect}")
            app.logger.info(f"📋 各天比赛数: {[(k, len(v)) for k, v in date_match_map.items() if v]}")
            
            yield f"data: {json.dumps({'type': 'scan_complete', 'total_days': total_days, 'total_matches': total_matches_to_collect})}\n\n"
            
            if total_matches_to_collect == 0:
                app.logger.warning(f"⚠️ 无符合条件的比赛！请检查日期和过滤条件")
                yield f"data: {json.dumps({'type': 'complete', 'message': '无符合条件的比赛', 'total_collected': 0, 'total_failed': 0, 'total_skipped': 0})}\n\n"
                return
            
            # 🔥 创建或恢复采集会话
            if not session_id:
                session_id = progress_manager.create_session(
                    start_date=_start_date_str,
                    end_date=_end_date_str,
                    total_matches=total_matches_to_collect,
                    filter_by_handicap=_filter_by_handicap,
                    skip_cached=_skip_cached
                )
                yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id})}\n\n"
                app.logger.info(f"📝 创建采集会话: {session_id}")
            
            # 🔒 设置当前活动会话
            active_collection_session = session_id
            app.logger.info(f"🔒 已锁定采集任务，会话: {session_id}")
            
            # 📝 启动日志会话
            log_manager.start_session(session_id)
            
            # 🔥 第二阶段：采集
            msg = {'type': 'phase', 'phase': 2, 'message': f'第二阶段：采集 {total_matches_to_collect} 场', 'session_id': session_id}
            log_manager.add_message(msg)
            yield f"data: {json.dumps(msg)}\n\n"
            
            total_collected = 0
            total_failed = 0
            total_skipped = 0
            match_idx = 0
            day_idx = 0
            
            for date_str, matches in date_match_map.items():
                day_idx += 1
                
                if len(matches) == 0:
                    continue
                
                # 推送当天开始采集
                yield f"data: {json.dumps({'type': 'day_start', 'day': day_idx, 'total_days': total_days, 'date': date_str, 'matches': len(matches)})}\n\n"
                
                collected = 0
                failed = 0
                skipped = 0
                
                # 🔥🔥🔥 并发采集模式：使用线程池 + 消息队列 🔥🔥🔥
                
                # 1. 先筛选需要采集的比赛
                matches_to_collect = []
                for idx, match in enumerate(matches, 1):
                    match_idx += 1
                    match_label = match.get('label') or f"{match.get('home')} vs {match.get('away')}"
                    
                    # 检查是否已处理（断点续传）
                    if session_id and progress_manager.is_match_processed(session_id, match):
                        skipped += 1
                        total_skipped += 1
                        app.logger.info(f"⏭️  已处理过（断点续传）: {match_label}")
                        yield f"data: {json.dumps({'type': 'match_skip', 'label': match_label, 'reason': '已处理'})}\n\n"
                        continue
                    
                    # 检查缓存
                    if _skip_cached and detail_cache_manager.has_cache(match):
                        skipped += 1
                        total_skipped += 1
                        if session_id:
                            progress_manager.update_progress(session_id, match, 'skipped', date_str)
                        app.logger.info(f"⏭️  跳过已缓存: {match_label}")
                        yield f"data: {json.dumps({'type': 'match_skip', 'label': match_label, 'reason': '已缓存'})}\n\n"
                        continue
                    
                    matches_to_collect.append(match)
                
                if not matches_to_collect:
                    app.logger.info(f"  ℹ️  {date_str}: 无需采集（全部跳过）")
                    continue
                
                app.logger.info(f"  🚀 {date_str}: 开始采集 {len(matches_to_collect)} 场比赛（{_workers}线程）")
                
                # 2. 创建线程池和消息队列
                progress_queue = queue.Queue()
                max_workers = _workers  # 🆕 使用传入的并发数
                
                # 3. 提交所有任务到线程池
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    for match_idx, match in enumerate(matches_to_collect):
                        # 提交任务到线程池
                        future = executor.submit(
                            _collect_single_match_worker,  # 使用全局函数
                            match, 
                            match_idx, 
                            total_matches_to_collect, 
                            date_str, 
                            progress_queue, 
                            session_id
                        )
                        futures[future] = match_idx
                    
                    # 4. 从队列读取进度并实时推送
                    completed_count = 0
                    total_to_collect = len(matches_to_collect)
                    
                    # 🔥 发送初始进度，确保进度条立即显示
                    actual_processed = total_collected + total_failed + total_skipped
                    progress_percent = min(100, int((actual_processed / total_matches_to_collect) * 100)) if total_matches_to_collect > 0 else 0
                    yield f"data: {json.dumps({'type': 'match_progress', 'current': actual_processed, 'total': total_matches_to_collect, 'percent': progress_percent})}\\n\\n"
                    
                    while completed_count < total_to_collect:
                        try:
                            # 尝试从队列获取消息（非阻塞，超时0.1秒）
                            progress_msg = progress_queue.get(timeout=0.1)
                            
                            # 推送进度消息
                            yield f"data: {json.dumps(progress_msg)}\n\n"
                            
                            # 更新统计
                            msg_type = progress_msg.get('type')
                            if msg_type == 'match_success':
                                collected += 1
                                total_collected += 1
                                completed_count += 1
                            elif msg_type == 'match_failed':
                                failed += 1
                                total_failed += 1
                                completed_count += 1
                            
                            # 推送总体进度（使用实际已处理数）
                            actual_processed = total_collected + total_failed + total_skipped
                            progress_percent = min(100, int((actual_processed / total_matches_to_collect) * 100)) if total_matches_to_collect > 0 else 0
                            
                            # 1. 原有的 match_progress
                            yield f"data: {json.dumps({'type': 'match_progress', 'current': actual_processed, 'total': total_matches_to_collect, 'percent': progress_percent})}\\n\\n"
                            
                            # 2. 🔥 新增：通用 progress 事件（尝试修复进度条）
                            yield f"data: {json.dumps({'type': 'progress', 'current': actual_processed, 'total': total_matches_to_collect, 'percent': progress_percent})}\\n\\n"
                            
                            # 3. 🔥 新增：在实时日志中显示进度（用户要求）
                            # 使用 app.logger 确保能被 LogManager 捕获并显示在前端日志面板
                            app.logger.info(f"📊 采集进度: {actual_processed}/{total_matches_to_collect} ({progress_percent}%)")
                            
                        except queue.Empty:
                            # 队列空，继续等待
                            continue
                        except Exception as e:
                            app.logger.error(f"处理进度消息失败: {e}")
                            continue
                    
                    # 5. 确保所有线程完成
                    app.logger.info(f"  ⏳ 等待所有线程完成...")
                    for future in as_completed(futures):
                        try:
                            result = future.result(timeout=5)
                            app.logger.debug(f"  线程完成: {result}")
                        except Exception as e:
                            match = futures[future]
                            match_label = match.get('label', 'unknown')
                            app.logger.error(f"  线程异常 {match_label}: {e}")
                
                app.logger.info(f"  ✅ {date_str}: 并发采集完成 (成功{collected}, 失败{failed})")
                
                # 推送当天完成
                yield f"data: {json.dumps({'type': 'day_complete', 'date': date_str, 'collected': collected, 'failed': failed, 'skipped': skipped, 'total': len(matches)})}\n\n"
            
            # 🔥 标记会话完成
            if session_id:
                progress_manager.mark_completed(session_id)
                failed_matches = progress_manager.get_failed_matches(session_id)
                app.logger.info(f"✅ 会话完成: {session_id}")
                if failed_matches:
                    app.logger.info(f"📋 未采集成功的比赛数: {len(failed_matches)}")
                    app.logger.info(f"📋 详细日志已保存至: progress/failed_{session_id}.json")
            
            # 全部完成
            yield f"data: {json.dumps({'type': 'complete', 'total_days': total_days, 'total_matches': total_matches_to_collect, 'total_collected': total_collected, 'total_failed': total_failed, 'total_skipped': total_skipped, 'session_id': session_id})}\n\n"
            
        except GeneratorExit:
            # 客户端断开连接
            app.logger.warning("⚠️  SSE客户端断开连接")
            # 🔥 标记会话暂停（可恢复）
            if session_id:
                progress_manager.mark_paused(session_id)
                app.logger.info(f"⏸️  会话已暂停，可使用 session_id={session_id} 恢复")
        except Exception as exc:
            app.logger.exception(f"SSE流异常: {exc}")
            error_type = type(exc).__name__
            error_msg = str(exc)
            
            # 特殊处理网络错误
            if 'network' in error_msg.lower() or 'connection' in error_msg.lower():
                error_msg = "网络连接异常，请检查网络或稍后重试"
            
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': f'{error_type}: {error_msg}'})}\n\n"
            except:
                pass  # 如果连接已断开，忽略发送错误
        finally:
            # 🔒 释放采集锁
            active_collection_session = None
            collection_lock.release()
            app.logger.info("🔓 采集锁已释放")
            
            # 🎯 停止日志捕获
            log_stream.stop_capture()
            
            # 📝 结束日志会话
            if session_id:
                log_manager.end_session()
    
    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 禁用nginx缓冲
    response.headers['Connection'] = 'keep-alive'  # 保持连接
    return response


@app.route("/api/collect/status", methods=["GET"])
def api_collect_status():
    """查询当前采集状态"""
    global active_collection_session
    
    is_collecting = collection_lock.locked()
    
    return jsonify({
        "success": True,
        "is_collecting": is_collecting,
        "active_session": active_collection_session,
        "message": f"正在采集（会话: {active_collection_session}）" if is_collecting else "空闲"
    })


@app.route("/api/collect/logs", methods=["GET"])
def api_collect_logs():
    """获取采集日志历史"""
    try:
        session_id = request.args.get('session_id')
        limit = request.args.get('limit', type=int, default=100)
        since = request.args.get('since')  # 🔥 新增：只获取此时间之后的消息
        
        if session_id:
            # 获取指定会话的日志
            messages = log_manager.get_session_messages(session_id, limit=limit)
        else:
            # 获取最近的日志（优先内存，否则从文件读取）
            messages = log_manager.get_recent_messages(limit=limit)
        
        # 🔥 如果指定了 since，过滤出新的消息
        if since:
            try:
                # 简单字符串比较即可（ISO格式支持）
                messages = [m for m in messages if m.get('timestamp', '') > since]
            except:
                pass

        # 🔥 获取会话ID：优先活动会话，否则获取最近的会话
        active_session = log_manager.get_active_session_id()
        if not active_session:
            active_session = log_manager.get_latest_session_id()
        
        return jsonify({
            "success": True,
            "messages": messages,
            "count": len(messages),
            "active_session": active_session,
            "is_running": log_manager.get_active_session_id() is not None  # 🔥 区分是否正在运行
        })
    except Exception as e:
        app.logger.exception("获取日志失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/collect/sessions", methods=["GET"])
def api_collect_sessions():
    """获取历史采集会话列表"""
    try:
        limit = request.args.get('limit', type=int, default=20)
        sessions = progress_manager.list_sessions(limit=limit)
        
        # 🔥 调试信息
        debug_info = {
            "progress_dir": str(progress_manager.progress_dir),
            "dir_exists": progress_manager.progress_dir.exists(),
            "session_files": [f.name for f in progress_manager.progress_dir.glob("session_*.json")] if progress_manager.progress_dir.exists() else []
        }
        
        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "debug": debug_info
        })
    except Exception as e:
        app.logger.exception("获取会话列表失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/collect/session/<session_id>", methods=["GET"])
def api_collect_session_detail(session_id):
    """获取指定会话的详细信息"""
    try:
        session = progress_manager.get_session(session_id)
        if not session:
            return jsonify({"success": False, "message": "会话不存在"}), 404
        
        return jsonify({
            "success": True,
            "session": session
        })
    except Exception as e:
        app.logger.exception("获取会话详情失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/data/statistics/summary", methods=["GET"])
def api_data_statistics_summary():
    """获取数据统计摘要（按日期）"""
    try:
        summary = data_statistics.get_daily_summary()
        return jsonify({
            "success": True,
            "data": summary,
            "count": len(summary)
        })
    except Exception as e:
        app.logger.exception("获取数据统计失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/data/statistics/date/<date>", methods=["GET"])
def api_data_statistics_date(date):
    """获取指定日期的详细信息"""
    try:
        details = data_statistics.get_date_details(date)
        return jsonify({
            "success": True,
            "data": details
        })
    except Exception as e:
        app.logger.exception(f"获取日期详情失败: {date}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/data/statistics/tree", methods=["GET"])
def api_data_statistics_tree():
    """获取数据树形结构"""
    try:
        tree = data_statistics.get_tree_structure()
        return jsonify({
            "success": True,
            "data": tree
        })
    except Exception as e:
        app.logger.exception("获取数据树形结构失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/progress/sessions", methods=["GET"])
def api_progress_sessions():
    """获取所有采集会话列表"""
    try:
        limit = request.args.get('limit', type=int, default=20)
        sessions = progress_manager.list_sessions(limit=limit)
        
        # 🔥 调试信息：返回 progress 目录路径和文件列表
        debug_info = {
            "progress_dir": str(progress_manager.progress_dir),
            "dir_exists": progress_manager.progress_dir.exists(),
            "session_files": [f.name for f in progress_manager.progress_dir.glob("session_*.json")] if progress_manager.progress_dir.exists() else []
        }
        
        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "debug": debug_info  # 🔥 临时调试，确认后可删除
        })
    except Exception as exc:
        app.logger.exception("获取会话列表失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/progress/session/<session_id>", methods=["GET"])
def api_progress_session_detail(session_id):
    """获取指定会话的详细信息"""
    try:
        session_data = progress_manager.load_session(session_id)
        if not session_data:
            return jsonify({"success": False, "message": "会话不存在"}), 404
        
        return jsonify({
            "success": True,
            "session": session_data
        })
    except Exception as exc:
        app.logger.exception("获取会话详情失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/sessions/<session_id>/stop", methods=["POST"])
def api_stop_session(session_id):
    """停止指定会话"""
    try:
        global active_collection_session
        
        # 检查会话是否存在
        session_data = progress_manager.load_session(session_id)
        if not session_data:
            return jsonify({"success": False, "error": "会话不存在"}), 404
        
        # 检查会话状态
        if session_data.get('status') != 'running':
            return jsonify({"success": False, "error": f"会话状态为 {session_data.get('status')}，无法停止"}), 400
        
        # 更新会话状态为 paused
        progress_manager.update_session_status(session_id, 'paused')
        
        # 清除活动会话标记
        if active_collection_session == session_id:
            active_collection_session = None
            app.logger.info(f"🛑 已清除活动会话标记: {session_id}")
        
        app.logger.info(f"✅ 已停止会话: {session_id}")
        
        return jsonify({
            "success": True,
            "message": f"会话 {session_id} 已停止"
        })
        
    except Exception as exc:
        app.logger.exception(f"停止会话失败: {session_id}")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """删除指定会话"""
    try:
        from pathlib import Path
        
        force = request.args.get('force', '0') == '1'
        
        # 检查会话是否存在
        session_data = progress_manager.load_session(session_id)
        if not session_data:
            return jsonify({"success": False, "error": "会话不存在"}), 404
        
        # 检查会话状态（允许强制删除）
        if session_data.get('status') == 'running' and not force:
            return jsonify({"success": False, "error": "会话状态为进行中，请确认强制删除", "need_force": True}), 400
        
        # 删除会话文件
        session_file = progress_manager.progress_dir / f"session_{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            app.logger.info(f"✅ 已删除会话: {session_id}")
        
        # 删除关联的日志文件
        log_file = Path("logs") / f"session_{session_id}.log"
        if log_file.exists():
            log_file.unlink()
            app.logger.info(f"✅ 已删除会话日志: {session_id}")
        
        return jsonify({
            "success": True,
            "message": f"会话 {session_id} 已删除"
        })
        
    except Exception as exc:
        app.logger.exception(f"删除会话失败: {session_id}")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/progress/recovery/status", methods=["GET"])
def api_recovery_status():
    """获取自动恢复服务状态"""
    try:
        if not auto_recovery_service:
            return jsonify({
                "success": False,
                "message": "自动恢复服务未启动"
            })
        
        status = auto_recovery_service.get_recovery_status()
        return jsonify({
            "success": True,
            **status
        })
    except Exception as e:
        app.logger.exception("获取恢复状态失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/progress/recovery/manual/<session_id>", methods=["POST"])
def api_manual_recovery(session_id: str):
    """手动触发恢复"""
    try:
        if not auto_recovery_service:
            return jsonify({
                "success": False,
                "message": "自动恢复服务未启动"
            })
        
        result = auto_recovery_service.manual_recover(session_id)
        
        if result:
            return jsonify({
                "success": True,
                "message": f"已触发会话 {session_id} 的恢复"
            })
        else:
            return jsonify({
                "success": False,
                "message": "恢复触发失败，请检查会话ID或重试次数"
            })
    except Exception as e:
        app.logger.exception("手动恢复失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/progress/session/<session_id>/failed", methods=["GET"])
def api_progress_session_failed(session_id: str):
    """获取指定会话的失败比赛列表"""
    try:
        failed_matches = progress_manager.get_failed_matches(session_id)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "failed_count": len(failed_matches),
            "failed_matches": failed_matches
        })
    except Exception as exc:
        app.logger.exception("获取失败比赛列表失败")
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/scheduler/status", methods=["GET"])
def api_scheduler_status():
    """获取定时任务状态"""
    try:
        # 🔥 检测 scheduler_worker.py 进程是否在运行
        import subprocess
        worker_running = False
        try:
            # Linux/Mac
            result = subprocess.run(
                ['pgrep', '-f', 'scheduler_worker.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            worker_running = result.returncode == 0
        except FileNotFoundError:
            # Windows - 使用 tasklist
            try:
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq python*'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                worker_running = 'scheduler_worker' in result.stdout
            except:
                pass
        except:
            pass
        
        # 如果 worker 进程在运行，或者内置 scheduler 在运行，都算运行中
        is_running = worker_running or scheduler.running
        
        jobs = scheduler.get_jobs()
        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return jsonify({
            "success": True,
            "running": is_running,
            "worker_running": worker_running,
            "scheduler_running": scheduler.running,
            "jobs": job_list
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 磁盘清理 API ====================

@app.route("/api/cleanup/status", methods=["GET"])
def api_cleanup_status():
    """获取磁盘使用情况"""
    try:
        usage = get_disk_usage()
        total_size = sum(d['size'] for d in usage.values())
        total_files = sum(d['files'] for d in usage.values())
        
        return jsonify({
            "success": True,
            "usage": usage,
            "total_files": total_files,
            "total_size": total_size,
            "total_size_formatted": f"{total_size / 1024 / 1024:.1f} MB"
        })
    except Exception as e:
        app.logger.exception("获取磁盘使用情况失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/cleanup/preview", methods=["GET"])
def api_cleanup_preview():
    """预览将要清理的文件"""
    try:
        result = cleanup_service.run_cleanup(dry_run=True)
        return jsonify({
            "success": True,
            "files_to_delete": result['files_deleted'],
            "bytes_to_free": result['bytes_freed'],
            "bytes_formatted": f"{result['bytes_freed'] / 1024 / 1024:.1f} MB",
            "details": result.get('details', {})
        })
    except Exception as e:
        app.logger.exception("预览清理失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/cleanup/run", methods=["POST"])
def api_cleanup_run():
    """执行清理"""
    try:
        app.logger.info("🧹 手动触发清理任务")
        result = run_cleanup(dry_run=False)
        return jsonify({
            "success": True,
            "files_deleted": result['files_deleted'],
            "bytes_freed": result['bytes_freed'],
            "bytes_formatted": f"{result['bytes_freed'] / 1024 / 1024:.1f} MB",
            "details": result.get('details', {}),
            "errors": result.get('errors', [])
        })
    except Exception as e:
        app.logger.exception("执行清理失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/scheduler/trigger/<job_id>", methods=["POST"])
def api_scheduler_trigger(job_id):
    """手动触发定时任务"""
    try:
        app.logger.info(f"🔧 手动触发定时任务: {job_id}")
        
        if job_id == 'auto_collect_yesterday':
            # 在新线程中执行，避免阻塞
            thread = threading.Thread(target=auto_collect_yesterday_matches)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"已触发任务: 自动采集昨天的完场比赛，请查看后端日志"
            })
        elif job_id == 'auto_keep_login':
            thread = threading.Thread(target=auto_keep_login)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"已触发任务: 检查并保持登录状态，请查看后端日志"
            })
        elif job_id == 'auto_recommend_push':
            thread = threading.Thread(target=auto_recommend_and_push)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"已触发任务: 自动推送比赛推荐，请查看后端日志"
            })
        elif job_id == 'hourly_broadcast':
            thread = threading.Thread(target=hourly_broadcast)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"已触发任务: 整点播报，请查看后端日志"
            })
        elif job_id == 'pre_match_recommendation':
            thread = threading.Thread(target=pre_match_recommendation)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "success": True,
                "message": f"已触发任务: 赛前5分钟推荐推送，请查看后端日志"
            })
        else:
            return jsonify({"success": False, "message": "未知的任务ID"}), 400
            
    except Exception as e:
        app.logger.exception("手动触发任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


# ========================================
# 🎯 推荐记录追踪 API
# ========================================

@app.route("/api/tracker/statistics", methods=["GET"])
def api_tracker_statistics():
    """获取推荐追踪总体统计"""
    try:
        stats = recommendation_tracker.get_statistics()
        return jsonify({
            "success": True,
            **stats
        })
    except Exception as e:
        app.logger.exception("获取推荐统计失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/tracker/recent", methods=["GET"])
def api_tracker_recent():
    """获取最近N天的审查统计"""
    try:
        days = request.args.get("days", 30, type=int)
        reviews = recommendation_tracker.get_recent_reviews(days)
        return jsonify({
            "success": True,
            "reviews": reviews
        })
    except Exception as e:
        app.logger.exception("获取最近审查统计失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/tracker/review", methods=["POST"])
def api_tracker_review():
    """手动触发审查指定日期的推荐"""
    try:
        data = request.get_json(force=True) or {}
        date = data.get("date")
        
        if not date:
            # 默认审查昨天
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        result = recommendation_tracker.review_date(date)
        return jsonify({
            "success": True,
            **result
        })
    except Exception as e:
        app.logger.exception("审查推荐失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/tracker/pending", methods=["GET"])
def api_tracker_pending():
    """获取待审查的推荐"""
    try:
        before_date = request.args.get("before_date")
        pending = recommendation_tracker.get_pending_reviews(before_date)
        return jsonify({
            "success": True,
            "count": len(pending),
            "recommendations": pending
        })
    except Exception as e:
        app.logger.exception("获取待审查推荐失败")
        return jsonify({"success": False, "message": str(e)}), 500


def run_background_recovery(session_id):
    """
    后台运行恢复任务
    """
    from datetime import datetime, timedelta
    import time
    
    app.logger.info(f"🔄 开始后台恢复任务: session_id={session_id}")
    
    try:
        # 1. 加载会话
        session_data = progress_manager.load_session(session_id)
        if not session_data:
            app.logger.error(f"❌ 会话 {session_id} 不存在，无法恢复")
            return
        
        # 更新状态为运行中
        progress_manager.update_session_status(session_id, 'running')
        
        start_date_str = session_data.get('start_date')
        end_date_str = session_data.get('end_date')
        filter_by_handicap = session_data.get('filter_by_handicap', True)
        
        if not start_date_str:
            app.logger.error("❌ 会话缺少起始日期")
            return
            
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") if end_date_str else datetime.now()
        
        current_date = start_date
        total_collected = 0
        total_failed = 0
        
        # 2. 逐日扫描和采集
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            app.logger.info(f"🔍 [恢复] 扫描日期: {date_str}")
            
            try:
                # 获取比赛
                page_html, matches, metadata = bifaw_client.fetch_finished_matches(
                    target_date=current_date, 
                    rows=9999,
                    auto_retry=True
                )
                
                if not matches:
                    app.logger.info(f"    无比赛数据")
                    current_date += timedelta(days=1)
                    continue
                
                # 过滤盘口
                matches_to_collect = []
                if filter_by_handicap:
                    daily_handicaps = lottery500_client.fetch_daily_handicaps(date_str, use_cache=True)
                    
                    for match in matches:
                        # 尝试匹配盘口
                        home = match.get('home_team', '') or match.get('home', '')
                        away = match.get('away_team', '') or match.get('away', '')
                        kickoff = match.get('match_time', '') or match.get('kickoff', '')
                        
                        matched = lottery500_client.find_handicap_from_daily_data(
                            daily_handicaps=daily_handicaps,
                            home_team=home,
                            away_team=away,
                            match_time=kickoff
                        )
                        
                        if matched:
                            match['handicap_preview'] = {
                                'fid': matched['fid'],
                                'handicap_str': matched['current_handicap_str'],
                                'handicap': matched['current_handicap']
                            }
                            matches_to_collect.append(match)
                else:
                    matches_to_collect = matches
                
                app.logger.info(f"    需采集: {len(matches_to_collect)} 场")
                
                # 逐场采集
                for idx, match in enumerate(matches_to_collect):
                    # 检查缓存
                    if detail_cache_manager.has_cache(match):
                        continue
                    
                    # 采集
                    result = _collect_single_match_worker(
                        match=match,
                        match_idx=idx,
                        total_matches=len(matches_to_collect),
                        date_str=date_str,
                        progress_queue=None,  # 后台任务不需要实时队列
                        worker_session_id=session_id
                    )
                    
                    if result['status'] == 'success':
                        total_collected += 1
                    else:
                        total_failed += 1
                    
                    time.sleep(1)  # 避免过快
                    
            except Exception as e:
                app.logger.error(f"❌ [恢复] 处理日期 {date_str} 失败: {e}")
            
            current_date += timedelta(days=1)
        
        # 完成
        progress_manager.mark_completed(session_id)
        app.logger.info(f"✅ 后台恢复任务完成: 成功 {total_collected}, 失败 {total_failed}")
        
    except Exception as e:
        app.logger.exception(f"❌ 后台恢复任务异常: {e}")
        progress_manager.update_session_status(session_id, 'failed')


def auto_recovery_callback(session_id: str, start_date: str):
    """
    自动恢复回调函数
    当检测到中断的会话时，自动触发恢复
    """
    app.logger.info(f"🔄 [自动恢复] 触发恢复: session_id={session_id}, start_date={start_date}")
    
    # 在新线程中运行恢复任务，避免阻塞
    import threading
    recovery_thread = threading.Thread(
        target=run_background_recovery,
        args=(session_id,),
        daemon=True
    )
    recovery_thread.start()
    app.logger.info(f"✅ [自动恢复] 后台恢复线程已启动")


@app.route("/api/push/test", methods=["POST"])
def api_test_push():
    """
    测试推送功能
    支持企业微信和Telegram推送
    """
    try:
        data = request.get_json(force=True) or {}
        push_type = data.get("type", "wecom")  # wecom 或 telegram
        
        # 构造测试推荐数据
        test_data = {
            "match_info": {
                "league": "测试联赛",
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "home_team": "测试主队",
                "away_team": "测试客队"
            },
            "recommendation": {
                "should_bet": True,
                "recommendation": "主队 -1.5",  # 🔥 添加recommendation字段，用于格式化
                "bet_description": "主队让1.5球",
                "confidence": 0.75,
                "reason": "这是一条测试推荐消息\n✅ 成交量≥250行\n✅ 升盘利好主队\n✅ 置信度≥75%",
                "tier": "⭐ 高质量",
                "version": "V7-Simplified",
                "current_handicap": -1.5,  # 🔥 添加current_handicap字段，用于格式化
                "current_handicap_text": "-1.5",
                "handicap_trend": "升盘",
                "handicap_change": -0.25
            }
        }
        
        results = []
        
        # 企业微信推送
        if push_type in ["wecom", "all"]:
            try:
                from notification.wecom_bot import WeComNotifier
                wecom_notifier = WeComNotifier()
                
                if wecom_notifier.webhook_url:
                    success = wecom_notifier.send_recommendation(test_data)
                    results.append({
                        "channel": "企业微信",
                        "success": success,
                        "message": "推送成功" if success else "推送失败"
                    })
                else:
                    results.append({
                        "channel": "企业微信",
                        "success": False,
                        "message": "未配置Webhook URL"
                    })
            except Exception as e:
                app.logger.error(f"企业微信测试推送失败: {e}")
                results.append({
                    "channel": "企业微信",
                    "success": False,
                    "message": str(e)
                })
        
        # Telegram推送
        if push_type in ["telegram", "all"]:
            try:
                from notification.telegram_bot import TelegramNotifier
                telegram_notifier = TelegramNotifier()
                
                if telegram_notifier.bot_token and telegram_notifier.chat_id:
                    success = telegram_notifier.send_recommendation(test_data)
                    results.append({
                        "channel": "Telegram",
                        "success": success,
                        "message": "推送成功" if success else "推送失败"
                    })
                else:
                    results.append({
                        "channel": "Telegram",
                        "success": False,
                        "message": "未配置Bot Token或Chat ID"
                    })
            except Exception as e:
                app.logger.error(f"Telegram测试推送失败: {e}")
                results.append({
                    "channel": "Telegram",
                    "success": False,
                    "message": str(e)
                })
        
        # 检查是否有成功的推送
        success_count = sum(1 for r in results if r["success"])
        
        return jsonify({
            "success": success_count > 0,
            "results": results,
            "message": f"共测试 {len(results)} 个渠道，成功 {success_count} 个"
        })
        
    except Exception as e:
        app.logger.exception("测试推送失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/test_all_functions", methods=["POST"])
def api_test_all_push_functions():
    """
    完整推送功能测试（集成test_all_push.py）
    测试所有推送类型：告警、比赛推荐、整点播报、赛前提醒、错误通知
    """
    try:
        import time
        
        app.logger.info("🧪 开始完整推送功能测试...")
        
        results = []
        
        # 测试1: 告警推送
        app.logger.info("测试1: 告警推送")
        try:
            success = alert_manager.send_alert(
                alert_type="test_all_functions_alert",
                title="【测试1】告警推送测试",
                message="这是告警推送测试消息，用于验证系统异常时能否正常推送告警。\n\n测试项目：告警系统",
                force=True
            )
            results.append({
                "name": "告警推送",
                "success": success,
                "status": "通过" if success else "失败"
            })
            time.sleep(2)
        except Exception as e:
            results.append({"name": "告警推送", "success": False, "status": f"异常: {str(e)}"})
        
        # 测试2: 企业微信基础推送
        app.logger.info("测试2: 企业微信基础推送")
        try:
            import requests
            webhook = os.getenv('WECOM_WEBHOOK') or os.getenv('WECOM_ALERT_WEBHOOK')
            if webhook:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": f"""# 【测试2】企业微信推送测试

⏰ **测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 测试内容
- ✅ Markdown格式支持
- ✅ 文本格式化
- ✅ 表情符号显示

## 测试状态
**状态**: 正常
**测试项目**: 企业微信基础推送

---
_Football Analysis System_
"""
                    }
                }
                response = requests.post(webhook, json=payload, timeout=10)
                success = response.status_code == 200 and response.json().get('errcode') == 0
                results.append({
                    "name": "企业微信基础推送",
                    "success": success,
                    "status": "通过" if success else "失败"
                })
            else:
                results.append({"name": "企业微信基础推送", "success": False, "status": "未配置Webhook"})
            time.sleep(2)
        except Exception as e:
            results.append({"name": "企业微信基础推送", "success": False, "status": f"异常: {str(e)}"})
        
        # 测试3: 比赛推荐格式
        app.logger.info("测试3: 比赛推荐格式")
        try:
            from notification.wecom_bot import WeComNotifier
            wecom_notifier = WeComNotifier()
            test_data = {
                "version": "X1-JSON-V1.0",
                "match_info": {
                    "league": "英超",
                    "datetime": datetime.now().strftime('%Y-%m-%d %H:%M'),
                    "home_team": "曼联",
                    "away_team": "曼城"
                },
                "recommendation": {
                    "should_bet": True,
                    "bet_description": "主队 -1.5",
                    "confidence": 0.75,
                    "reason": "✅ 匹配⭐ 高质量\n✅ 成交量≥250行\n✅ 置信度≥75%",
                    "tier": "⭐ 高质量",
                    "current_handicap_text": "-1.5",
                    "handicap_trend": "升盘",
                    "handicap_change": -0.25
                }
            }
            success = wecom_notifier.send_recommendation(test_data)
            results.append({
                "name": "比赛推荐格式",
                "success": success,
                "status": "通过" if success else "失败"
            })
            time.sleep(2)
        except Exception as e:
            results.append({"name": "比赛推荐格式", "success": False, "status": f"异常: {str(e)}"})
        
        # 测试4: 整点播报格式（简化版）
        app.logger.info("测试4: 整点播报格式")
        try:
            webhook = os.getenv('WECOM_WEBHOOK') or os.getenv('WECOM_ALERT_WEBHOOK')
            if webhook:
                now = datetime.now()
                hour = now.hour
                next_hour = (hour + 1) % 24
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": f"""# 【测试4】{next_hour}:00 整点播报

## 📊 比赛概况
- 📅 时段: {next_hour}:00 - {(next_hour+1)%24}:00
- ⚽ 比赛总数: 3 场（测试）

---
⏰ 播报时间: {now.strftime('%H:%M:%S')}
"""
                    }
                }
                response = requests.post(webhook, json=payload, timeout=10)
                success = response.status_code == 200 and response.json().get('errcode') == 0
                results.append({
                    "name": "整点播报格式",
                    "success": success,
                    "status": "通过" if success else "失败"
                })
            else:
                results.append({"name": "整点播报格式", "success": False, "status": "未配置Webhook"})
            time.sleep(2)
        except Exception as e:
            results.append({"name": "整点播报格式", "success": False, "status": f"异常: {str(e)}"})
        
        # 测试5: 赛前提醒格式
        app.logger.info("测试5: 赛前提醒格式")
        try:
            webhook = os.getenv('WECOM_WEBHOOK') or os.getenv('WECOM_ALERT_WEBHOOK')
            if webhook:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": f"""# 【测试5】⏰ 赛前5分钟提醒

## ⚽ 比赛即将开始
**联赛**: 欧冠
**对阵**: 拜仁 vs 巴黎圣日耳曼
**开始时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**距离开始**: 5分钟（测试）

---
⚠️ 请注意关注比赛动态
"""
                    }
                }
                response = requests.post(webhook, json=payload, timeout=10)
                success = response.status_code == 200 and response.json().get('errcode') == 0
                results.append({
                    "name": "赛前提醒格式",
                    "success": success,
                    "status": "通过" if success else "失败"
                })
            else:
                results.append({"name": "赛前提醒格式", "success": False, "status": "未配置Webhook"})
            time.sleep(2)
        except Exception as e:
            results.append({"name": "赛前提醒格式", "success": False, "status": f"异常: {str(e)}"})
        
        # 测试6: 错误通知格式
        app.logger.info("测试6: 错误通知格式")
        try:
            test_cases = [
                ("登录失败", "模拟登录失败场景"),
                ("数据采集失败", "模拟数据采集失败场景"),
            ]
            sub_success = 0
            for i, (title, msg) in enumerate(test_cases, 1):
                try:
                    success = alert_manager.send_alert(
                        alert_type=f"test_error_{i}",
                        title=f"【测试6.{i}】{title}",
                        message=msg,
                        force=True
                    )
                    if success:
                        sub_success += 1
                    time.sleep(1)
                except:
                    pass
            
            success = sub_success == len(test_cases)
            results.append({
                "name": "错误通知格式",
                "success": success,
                "status": f"通过 ({sub_success}/{len(test_cases)})" if success else f"部分失败 ({sub_success}/{len(test_cases)})"
            })
        except Exception as e:
            results.append({"name": "错误通知格式", "success": False, "status": f"异常: {str(e)}"})
        
        # 统计结果
        passed = sum(1 for r in results if r["success"])
        total = len(results)
        
        app.logger.info(f"✅ 完整测试完成: {passed}/{total} 通过")
        
        return jsonify({
            "success": passed == total,
            "passed": passed,
            "total": total,
            "results": results,
            "message": f"完整测试完成: {passed}/{total} 项通过"
        })
        
    except Exception as e:
        app.logger.exception("完整推送测试失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/scheduled_tasks", methods=["GET"])
def api_get_scheduled_tasks():
    """
    获取已调度的推送任务列表
    """
    try:
        if not schedule_manager:
            return jsonify({
                "success": False,
                "message": "调度管理器未初始化"
            }), 400
        
        tasks = schedule_manager.get_scheduled_tasks()
        
        return jsonify({
            "success": True,
            "total": len(tasks),
            "tasks": tasks
        })
        
    except Exception as e:
        app.logger.exception("获取调度任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


# ========== 🔧 推荐引擎管理 API ==========

@app.route("/api/engine/status", methods=["GET"])
def api_engine_status():
    """获取推荐引擎状态"""
    try:
        from core.engine_manager import get_engine_manager
        manager = get_engine_manager()
        return jsonify({
            "success": True,
            "status": manager.get_status()
        })
    except Exception as e:
        app.logger.exception("获取引擎状态失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/engine/switch", methods=["POST"])
def api_switch_engine():
    """切换推荐引擎"""
    try:
        from core.engine_manager import get_engine_manager
        data = request.get_json() or {}
        engine_name = data.get("engine")
        
        if not engine_name:
            return jsonify({"success": False, "message": "请指定引擎名称"}), 400
        
        manager = get_engine_manager()
        if manager.set_current_engine(engine_name):
            return jsonify({
                "success": True,
                "message": f"已切换到引擎: {engine_name}",
                "current_engine": engine_name
            })
        else:
            return jsonify({"success": False, "message": f"未知引擎: {engine_name}"}), 400
    except Exception as e:
        app.logger.exception("切换引擎失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/engine/test", methods=["POST"])
def api_test_engine():
    """测试推荐引擎"""
    try:
        from core.engine_manager import get_engine_manager
        data = request.get_json() or {}
        match_file = data.get("match_file")
        engine_name = data.get("engine")  # 可选，不指定则使用当前引擎
        
        if not match_file:
            return jsonify({"success": False, "message": "请指定比赛文件路径"}), 400
        
        manager = get_engine_manager()
        result = manager.recommend(match_file, engine_name)
        
        return jsonify({
            "success": True,
            "engine": result.engine,
            "result": result.to_dict()
        })
    except Exception as e:
        app.logger.exception("测试引擎失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/rescan_matches", methods=["POST"])
def api_rescan_matches():
    """
    手动触发重新扫描今日比赛并创建推送任务
    """
    try:
        if not schedule_manager:
            return jsonify({
                "success": False,
                "message": "调度管理器未初始化"
            }), 400
        
        app.logger.info("📅 手动触发扫描并调度今日比赛推送...")
        schedule_manager.scan_and_schedule_today_matches()
        
        tasks = schedule_manager.get_scheduled_tasks()
        
        return jsonify({
            "success": True,
            "message": f"扫描完成，已调度 {len(tasks)} 场比赛的推送任务",
            "tasks": tasks
        })
        
    except Exception as e:
        app.logger.exception("重新扫描比赛失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/logs/view", methods=["GET"])
def api_view_logs():
    """
    查看最近的日志内容
    """
    try:
        lines = request.args.get('lines', 500, type=int)
        content = operation_logger.get_current_log_content(lines=lines)
        
        return jsonify({
            "success": True,
            "lines": lines,
            "content": content
        })
    except Exception as e:
        app.logger.exception("查看日志失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/logs/stats", methods=["GET"])
def api_log_stats():
    """
    获取日志统计信息
    """
    try:
        stats = operation_logger.get_log_stats()
        
        # 格式化大小显示
        if 'current_log_size' in stats:
            stats['current_log_size_mb'] = round(stats['current_log_size'] / 1024 / 1024, 2)
        if 'total_archive_size' in stats:
            stats['total_archive_size_mb'] = round(stats['total_archive_size'] / 1024 / 1024, 2)
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        app.logger.exception("获取日志统计失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/logs/search", methods=["POST"])
def api_search_logs():
    """
    搜索日志内容
    """
    try:
        data = request.get_json(force=True) or {}
        keyword = data.get('keyword', '')
        max_results = data.get('max_results', 100)
        
        if not keyword:
            return jsonify({
                "success": False,
                "message": "请提供搜索关键字"
            }), 400
        
        results = operation_logger.search_logs(keyword, max_results)
        
        return jsonify({
            "success": True,
            "keyword": keyword,
            "total": len(results),
            "results": results
        })
    except Exception as e:
        app.logger.exception("搜索日志失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/logs/rotate", methods=["POST"])
def api_rotate_logs():
    """
    手动触发日志轮转
    """
    try:
        app.logger.info("📝 手动触发日志轮转...")
        success = operation_logger.force_rotate()
        
        if success:
            return jsonify({
                "success": True,
                "message": "日志已成功轮转"
            })
        else:
            return jsonify({
                "success": False,
                "message": "日志轮转失败"
            }), 500
    except Exception as e:
        app.logger.exception("日志轮转失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/test_hourly_broadcast", methods=["POST"])
def api_test_hourly_broadcast():
    """
    测试整点播报功能
    会播报当前小时或指定小时内的比赛
    """
    from datetime import datetime as dt_class
    
    try:
        if not auto_push_system:
            return jsonify({
                "success": False,
                "message": "自动推送系统未初始化"
            }), 400
        
        data = request.get_json(force=True) or {}
        test_hour = data.get("hour")  # 可选：指定测试哪个小时（0-23）
        
        app.logger.info(f"📢 手动触发整点播报测试（小时：{test_hour if test_hour is not None else '当前'}）")
        
        # 如果指定了小时，创建测试时间
        if test_hour is not None:
            # 创建指定小时的时间
            test_time = dt_class.now().replace(hour=int(test_hour), minute=0, second=0, microsecond=0)
            auto_push_system.hourly_broadcast(test_time=test_time)
        else:
            # 使用当前时间
            auto_push_system.hourly_broadcast()
        
        return jsonify({
            "success": True,
            "message": f"整点播报已触发（小时：{test_hour if test_hour is not None else dt_class.now().hour}）",
            "note": "请检查企业微信群消息。即使该小时没有比赛，也会推送状态播报。"
        })
        
    except Exception as e:
        app.logger.exception("测试整点播报失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/test_pre_match", methods=["POST"])
def api_test_pre_match():
    from datetime import datetime as dt_class
    
    try:
        if not auto_push_system:
            return jsonify({
                "success": False,
                "message": "自动推送系统未初始化"
            }), 400
        
        data = request.get_json(force=True) or {}
        minutes_before = data.get("minutes_before", 5)
        try:
            minutes_before = int(minutes_before)
        except (TypeError, ValueError):
            minutes_before = 5
        
        time_str = data.get("time")
        test_time = None
        
        if time_str:
            try:
                parsed = auto_push_system.parse_match_time(time_str)
            except Exception:
                parsed = None
            
            if parsed:
                test_time = parsed
            else:
                try:
                    today_str = dt_class.now().strftime("%Y-%m-%d")
                    test_time = dt_class.strptime(f"{today_str} {time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    test_time = None
        
        if test_time:
            time_desc = test_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_desc = "当前时间"
        
        # 🔥 强制模式：跳过已完场检查，用于测试推送功能
        force_test = data.get("force", False)
        # 🔥 自动采集模式：自动采集缺失数据（可能较慢）
        auto_collect = data.get("auto_collect", False)
        
        app.logger.info(f"🔔 手动触发赛前推荐测试（minutes_before={minutes_before}，time={time_desc}，force={force_test}，auto_collect={auto_collect}）")
        
        auto_push_system.push_pre_match_recommendations(
            minutes_before=minutes_before,
            test_time=test_time,
            skip_finished_check=force_test,
            auto_collect=auto_collect
        )
        
        return jsonify({
            "success": True,
            "message": "赛前推荐测试已触发",
            "minutes_before": minutes_before,
            "time_used": time_desc
        })
    except Exception as e:
        app.logger.exception("测试赛前推荐推送失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/test_pre_match_json_collect", methods=["POST"])
def api_test_pre_match_json_collect():
    """
    测试赛前采集并推送JSON功能
    
    在比赛开始前N分钟采集数据，采集完成后推送JSON
    
    参数:
        minutes_before: 提前多少分钟采集（默认15）
        time: 可选，模拟时间（格式 HH:MM 或 YYYY-MM-DD HH:MM）
    """
    from datetime import datetime as dt_class
    
    try:
        if not auto_push_system:
            return jsonify({
                "success": False,
                "message": "自动推送系统未初始化"
            }), 400
        
        data = request.get_json(force=True) or {}
        minutes_before = data.get("minutes_before", 15)
        try:
            minutes_before = int(minutes_before)
        except (TypeError, ValueError):
            minutes_before = 15
        
        time_str = data.get("time")
        test_time = None
        
        if time_str:
            try:
                parsed = auto_push_system.parse_match_time(time_str)
            except Exception:
                parsed = None
            
            if parsed:
                test_time = parsed
            else:
                try:
                    today_str = dt_class.now().strftime("%Y-%m-%d")
                    test_time = dt_class.strptime(f"{today_str} {time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    test_time = None
        
        if test_time:
            time_desc = test_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_desc = "当前时间"
        
        app.logger.info(f"📥 手动触发赛前采集推送测试（minutes_before={minutes_before}，time={time_desc}）")
        
        auto_push_system.push_pre_match_json_data(
            minutes_before=minutes_before,
            test_time=test_time
        )
        
        return jsonify({
            "success": True,
            "message": "赛前采集推送测试已触发",
            "minutes_before": minutes_before,
            "time_used": time_desc,
            "note": "系统将采集距开赛约15分钟的比赛数据，采集完成后推送JSON。请检查企业微信群消息。"
        })
    except Exception as e:
        app.logger.exception("测试赛前采集推送失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/push/test_json_download", methods=["POST"])
def api_test_json_download():
    """
    测试JSON下载链接推送（不依赖实际比赛数据）
    直接发送一个测试JSON文件并推送下载链接
    """
    from datetime import datetime as dt_class, timedelta
    import json
    import os
    
    try:
        if not auto_push_system:
            return jsonify({
                "success": False,
                "message": "自动推送系统未初始化"
            }), 400
        
        # 构造测试数据
        now = dt_class.now()
        mock_match_info = {
            'match_time': now + timedelta(minutes=15),
            'home_team': '曼城',
            'away_team': '利物浦',
            'league': '英超'
        }
        
        mock_json_data = {
            'match_info': {
                'home_team': '曼城',
                'away_team': '利物浦',
                'league': '英超',
                'datetime': (now + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M'),
                'match_id': '12345678'
            },
            'handicap_data': {
                'initial_handicap': -0.25,
                'initial_handicap_text': '主让平手/半球',
                'initial_home_odds': 0.92,
                'initial_away_odds': 0.92,
                'current_handicap': -0.25,
                'current_handicap_text': '主让平手/半球',
                'current_home_odds': 0.88,
                'current_away_odds': 0.96
            },
            'trade_summary': {
                'total_volume': 125000,
                'home_volume': 65000,
                'away_volume': 60000,
                'row_count': 1234
            },
            'trade_data': [
                {'time': '15:30:00', 'side': 'home', 'odds': 0.88, 'volume': 5000},
                {'time': '15:29:30', 'side': 'away', 'odds': 0.96, 'volume': 3000}
            ],
            'collection_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'test'
        }
        
        app.logger.info("📥 测试JSON下载链接推送...")
        
        success = auto_push_system._send_json_data_notification(
            match_info=mock_match_info,
            json_data=mock_json_data,
            minutes_before=15
        )
        
        return jsonify({
            "success": success,
            "message": "测试推送已发送" if success else "推送失败"
        })
        
    except Exception as e:
        app.logger.exception("测试JSON推送失败")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# 📥 JSON文件接口
# ============================================================

@app.route("/api/json/list", methods=["GET"])
def api_json_list():
    """
    获取赛前采集的JSON文件列表
    """
    import os
    import json
    from datetime import datetime
    
    try:
        data_dir = Path(__file__).parent / "data" / "push_json"
        files = []
        
        if data_dir.exists():
            # 遍历所有JSON文件
            for json_file in data_dir.rglob("*.json"):
                try:
                    # 获取文件信息
                    stat = json_file.stat()
                    relative_path = json_file.relative_to(Path(__file__).parent / "data")
                    
                    # 从目录路径获取年份（push_json/2025/12/11/xxx.json）
                    path_parts = json_file.relative_to(data_dir).parts
                    year_from_path = path_parts[0] if len(path_parts) > 0 else str(datetime.now().year)
                    
                    # 尝试解析文件名获取比赛信息
                    # 新格式: 1210_1627_英超_曼城_vs_利物浦.json (月日_时间_联赛_主队_vs_客队)
                    # 旧格式: 20251210_1627_英超_曼城_vs_利物浦.json (年月日_时间_联赛_主队_vs_客队)
                    filename = json_file.stem
                    parts = filename.split('_')
                    
                    match_info = {
                        'filename': json_file.name,
                        'path': str(relative_path).replace('\\', '/'),
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                    }
                    
                    # 尝试从文件名解析信息
                    if len(parts) >= 6:
                        date_str = parts[0]  # 1210 或 20251210
                        time_str = parts[1]  # 1627
                        league = parts[2]    # 英超
                        home_team = parts[3] # 曼城
                        # vs
                        away_team = '_'.join(parts[5:])  # 利物浦
                        
                        try:
                            # 判断是新格式（4位月日）还是旧格式（8位年月日）
                            if len(date_str) == 4:
                                # 新格式：从目录路径获取年份
                                full_date_str = f"{year_from_path}{date_str}{time_str}"
                                match_time = datetime.strptime(full_date_str, "%Y%m%d%H%M")
                            else:
                                # 旧格式：直接解析
                                match_time = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M")
                            match_info['match_time'] = match_time.strftime('%m-%d %H:%M')  # 显示时也去掉年份
                        except:
                            pass
                        
                        match_info['league'] = league
                        match_info['home_team'] = home_team
                        match_info['away_team'] = away_team
                    
                    files.append(match_info)
                    
                except Exception as e:
                    app.logger.warning(f"解析JSON文件信息失败 {json_file}: {e}")
        
        # 按创建时间倒序排列
        files.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            "success": True,
            "files": files,
            "total": len(files)
        })
        
    except Exception as e:
        app.logger.exception("获取JSON文件列表失败")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/json/delete", methods=["POST"])
def api_json_delete():
    """
    删除指定的JSON文件
    """
    try:
        data = request.get_json(force=True) or {}
        filepath = data.get('path', '')
        
        if not filepath:
            return jsonify({"success": False, "error": "未指定文件路径"}), 400
        
        # 安全检查：确保路径在 data 目录内
        data_dir = Path(__file__).parent / "data"
        full_path = (data_dir / filepath).resolve()
        
        # 验证路径安全性
        if not str(full_path).startswith(str(data_dir.resolve())):
            return jsonify({"success": False, "error": "非法路径"}), 403
        
        if not full_path.exists():
            return jsonify({"success": False, "error": "文件不存在"}), 404
        
        if not full_path.suffix == '.json':
            return jsonify({"success": False, "error": "只能删除JSON文件"}), 400
        
        # 删除文件
        full_path.unlink()
        app.logger.info(f"🗑️ 已删除JSON文件: {filepath}")
        
        return jsonify({
            "success": True,
            "message": "文件已删除"
        })
        
    except Exception as e:
        app.logger.exception("删除JSON文件失败")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download/json/<path:filepath>", methods=["GET"])
def api_download_json(filepath):
    """
    下载或预览JSON文件
    
    路径格式: /api/download/json/push_json/2025/12/10/xxx.json
    参数: ?preview=true 返回JSON数据用于预览
    """
    from flask import send_file
    import os
    import json as json_module
    
    try:
        # 构建完整路径（相对于data目录）
        data_dir = Path(__file__).parent / "data"
        full_path = data_dir / filepath
        
        # 安全检查：确保路径在data目录内
        try:
            full_path.resolve().relative_to(data_dir.resolve())
        except ValueError:
            return jsonify({"error": "非法路径"}), 403
        
        if not full_path.exists():
            return jsonify({"error": "文件不存在"}), 404
        
        if not full_path.suffix.lower() == '.json':
            return jsonify({"error": "只支持JSON文件下载"}), 400
        
        # 检查是否为预览模式
        preview = request.args.get('preview', 'false').lower() == 'true'
        
        if preview:
            # 预览模式：返回JSON数据
            with open(full_path, 'r', encoding='utf-8') as f:
                json_data = json_module.load(f)
            return jsonify(json_data)
        else:
            # 下载模式：返回文件下载（iOS 兼容）
            # 使用 application/octet-stream 强制下载，避免 iOS Safari 预览
            response = send_file(
                full_path,
                mimetype='application/octet-stream',  # 强制下载
                as_attachment=True,
                download_name=full_path.name
            )
            # 添加额外的响应头确保下载
            response.headers['Content-Type'] = 'application/octet-stream'
            response.headers['Content-Disposition'] = f'attachment; filename="{full_path.name}"'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        
    except Exception as e:
        app.logger.exception("下载JSON文件失败")
        return jsonify({"error": str(e)}), 500


# ============================================================
# 🚀 后台任务 API（支持关闭页面后继续运行）
# ============================================================

def _background_collect_handler(task):
    """后台采集任务处理器"""
    from datetime import datetime, timedelta
    
    params = task.params
    start_date_str = params.get('start_date')
    end_date_str = params.get('end_date')
    filter_by_handicap = params.get('filter_by_handicap', True)
    skip_cached = params.get('skip_cached', True)
    workers = params.get('workers', 3)
    
    # 解析日期
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now() - timedelta(days=1)
    
    task.add_log("INFO", f"开始采集: {start_date_str} ~ {end_date_str}")
    
    # 检查登录状态
    task.add_log("INFO", "检查必发登录状态...")
    try:
        status = bifaw_client.get_cookie_status()
        if status.get('exists'):
            task.add_log("SUCCESS", f"✅ 已登录必发: {status.get('message', '')}")
        else:
            task.add_log("WARNING", "⚠️ 未登录，尝试自动登录...")
            # 检查 OCR 是否可用
            if hasattr(bifaw_client, 'ocr_enabled') and bifaw_client.ocr_enabled:
                task.add_log("INFO", "🔄 本地 OCR 已启用，正在自动识别验证码...")
                success, msg = bifaw_client._auto_login_with_ocr(max_retries=20)
                if success:
                    task.add_log("SUCCESS", "✅ 自动登录成功")
                else:
                    task.add_log("ERROR", f"❌ 自动登录失败: {msg}")
            else:
                task.add_log("ERROR", "❌ 本地 OCR 未启用，需要手动登录！")
                task.add_log("ERROR", "请在网页端点击【快捷登录】手动完成验证码登录")
    except Exception as e:
        task.add_log("WARNING", f"检查登录状态失败: {str(e)}")
    
    # 扫描阶段
    task.add_log("INFO", "阶段1: 扫描比赛...")
    all_matches = []
    current_date = start_date
    
    while current_date <= end_date:
        if task.should_stop():
            task.add_log("WARNING", "任务被用户停止")
            return {"cancelled": True}
        
        date_str = current_date.strftime('%Y-%m-%d')
        task.progress.current_item = f"扫描 {date_str}"
        
        try:
            task.add_log("INFO", f"  正在扫描 {date_str}...")
            _, matches, _ = bifaw_client.fetch_finished_matches(
                target_date=current_date,
                rows=9999,
                auto_retry=True
            )
            task.add_log("INFO", f"  {date_str}: 原始数据返回 {len(matches) if matches else 0} 场")
            if matches:
                for m in matches:
                    m['query_date'] = date_str
                all_matches.extend(matches)
                task.add_log("INFO", f"  {date_str}: {len(matches)} 场（累计 {len(all_matches)} 场）")
        except Exception as e:
            task.add_log("WARNING", f"  {date_str}: 获取失败 - {str(e)[:100]}")
            import traceback
            task.add_log("ERROR", f"详细错误: {traceback.format_exc()[:500]}")
        
        current_date += timedelta(days=1)
    
    task.progress.total = len(all_matches)
    task.add_log("INFO", f"✅ 扫描完成，共 {len(all_matches)} 场比赛")
    
    if len(all_matches) == 0:
        task.add_log("WARNING", "⚠️ 无比赛数据，可能原因：")
        task.add_log("WARNING", "  1. 日期范围内没有已完场比赛")
        task.add_log("WARNING", "  2. fetch_finished_matches 返回空列表")
        task.add_log("WARNING", "  3. 网络请求失败")
        return {"total": 0, "success": 0, "failed": 0}
    
    # 创建采集会话
    task.add_log("INFO", f"正在创建采集会话...")
    session_id = progress_manager.create_session(
        start_date=start_date_str,
        end_date=end_date_str,
        total_matches=len(all_matches),
        filter_by_handicap=filter_by_handicap,
        skip_cached=skip_cached
    )
    task.add_log("INFO", f"✅ 会话ID: {session_id}")
    
    # 采集阶段
    task.add_log("INFO", f"阶段2: 并发采集 ({workers}并发)...")
    task.add_log("INFO", f"开始处理 {len(all_matches)} 场比赛...")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def collect_single(match_info):
        match, idx = match_info
        match_id = match.get('match_id')
        # 🔥 DEBUG LOG
        if idx < 5:
            app.logger.info(f"DEBUG: Processing match {match_id} (idx={idx})")

        if not match_id:
            return {'status': 'skipped', 'match_id': None}
        
        try:
            # 检查缓存
            if skip_cached:
                # 使用 DetailCacheManager 的正确API
                if detail_cache_manager.has_cache(match):
                    return {'status': 'skipped', 'match_id': match_id}
            
            # 采集明细
            detail_url = match.get('detail_url')
            if not detail_url:
                error_msg = f"Match {match_id}: detail_url为空"
                app.logger.error(f"DEBUG ERROR: {error_msg}") # 🔥 Force log
                if idx < 3:  # 只记录前3个详细错误
                    task.add_log("ERROR", error_msg)
                return {'status': 'failed', 'match_id': match_id, 'error': 'no_detail_url'}
            
            # 使用 fetch_match_detail_selenium 正确方法
            detail_html = bifaw_client.fetch_match_detail_selenium(detail_url=detail_url, timeout=30)
            
            if detail_html and len(detail_html) > 100:  # 确保HTML有内容
                # 解析HTML并保存
                result = parse_bifa_html(detail_html)
                
                if isinstance(result, str):
                    error_msg = f"Match {match_id}: 解析HTML失败 - {result}"
                    app.logger.error(f"DEBUG ERROR: {error_msg}") # 🔥 Force log
                    if idx < 3:
                        task.add_log("ERROR", error_msg)
                    return {'status': 'failed', 'match_id': match_id, 'error': 'parse_failed'}
                
                trade_data = result
                handicap_data = {}
                metadata = trade_data.attrs.get('metadata', [])
                
                if trade_data is not None and not trade_data.empty:
                    # 使用 save_detail 保存完整数据
                    try:
                        success = detail_cache_manager.save_detail(
                            match_info=match,
                            trade_data=trade_data,
                            handicap_data=handicap_data,
                            metadata=metadata,
                            html_content=detail_html
                        )
                        if success:
                            if idx < 3:  # 只记录前3个成功案例
                                task.add_log("DEBUG", f"Match {match_id}: 成功采集 {len(trade_data)}行数据")
                            return {'status': 'success', 'match_id': match_id}
                        else:
                            error_msg = f"Match {match_id}: save_detail failed (check logs)"
                            app.logger.error(f"DEBUG ERROR: {error_msg}") 
                            task.add_log("ERROR", error_msg) # 🔥 Show in UI
                            return {'status': 'failed', 'match_id': match_id, 'error': 'save_detail_failed'}
                    except Exception as e:
                        error_msg = f"Match {match_id}: save_detail exception: {e}"
                        app.logger.error(error_msg)
                        task.add_log("ERROR", error_msg) # 🔥 Show in UI
                        return {'status': 'failed', 'match_id': match_id, 'error': str(e)}
                else:
                    error_msg = f"Match {match_id}: 解析后数据为空"
                    app.logger.error(f"DEBUG ERROR: {error_msg}") # 🔥 Force log
                    if idx < 3:
                        task.add_log("ERROR", error_msg)
                    return {'status': 'failed', 'match_id': match_id, 'error': 'empty_data'}
            else:
                error_msg = f"Match {match_id}: HTML为空或太短 (len={len(detail_html) if detail_html else 0})"
                app.logger.error(f"DEBUG ERROR: {error_msg}") # 🔥 Force log
                if idx < 3:
                    task.add_log("ERROR", error_msg)
                return {'status': 'failed', 'match_id': match_id, 'error': 'empty_html'}
            
        except Exception as e:
            error_msg = f"Match {match_id}: {type(e).__name__} - {str(e)[:200]}"
            app.logger.error(f"DEBUG EXCEPTION: {error_msg}") # 🔥 Force log
            import traceback
            app.logger.error(traceback.format_exc()) # 🔥 Log traceback
            if idx < 5:  # 记录前5个异常
                task.add_log("ERROR", error_msg)
            return {'status': 'failed', 'match_id': match_id, 'error': str(e)[:100]}
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(collect_single, (m, i)): i for i, m in enumerate(all_matches)}
        
        for future in as_completed(futures):
            if task.should_stop():
                executor.shutdown(wait=False, cancel_futures=True)
                progress_manager.update_session_status(session_id, 'paused')
                return {"cancelled": True, "session_id": session_id}
            
            result = future.result()
            task.progress.processed += 1
            
            # 🔥 Update ProgressManager
            try:
                match_idx = futures[future] # Get original index
                match_info = all_matches[match_idx]
                current_date_str = match_info.get('query_date', datetime.now().strftime('%Y-%m-%d'))
                
                progress_manager.update_progress(
                    session_id=session_id,
                    match_info=match_info,
                    status=result['status'],
                    current_date=current_date_str,
                    error_reason=result.get('error')
                )
            except Exception as e:
                app.logger.error(f"Failed to update progress manager: {e}")

            if result['status'] == 'success':
                task.progress.success += 1
            elif result['status'] == 'failed':
                task.progress.failed += 1
            elif result['status'] == 'skipped':
                task.progress.skipped += 1
            
            # 每50个输出一次进度
            if task.progress.processed % 50 == 0:
                task.add_log("INFO", f"进度: {task.progress.processed}/{task.progress.total} ({task.progress.percentage}%)")
    
    # 完成
    progress_manager.update_session_status(session_id, 'completed')
    task.add_log("INFO", f"采集完成！成功:{task.progress.success} 失败:{task.progress.failed} 跳过:{task.progress.skipped}")
    
    return {
        "session_id": session_id,
        "total": task.progress.total,
        "success": task.progress.success,
        "failed": task.progress.failed,
        "skipped": task.progress.skipped
    }


# 注册采集任务处理器
background_task_manager.register_handler("collect", _background_collect_handler)


@app.route("/api/tasks/collect/start", methods=["POST"])
def api_start_background_collect():
    """启动后台采集任务"""
    try:
        data = request.get_json() or {}
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        filter_by_handicap = data.get('filter_by_handicap', True)
        skip_cached = data.get('skip_cached', True)
        workers = data.get('workers', 3)
        
        if not start_date:
            return jsonify({"success": False, "message": "缺少 start_date 参数"}), 400
        
        # 创建任务
        task = background_task_manager.create_task(
            task_type="collect",
            params={
                "start_date": start_date,
                "end_date": end_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "filter_by_handicap": filter_by_handicap,
                "skip_cached": skip_cached,
                "workers": workers,
            }
        )
        
        # 启动任务
        if background_task_manager.start_task(task.task_id):
            app.logger.info(f"🚀 后台采集任务已启动: {task.task_id}")
            return jsonify({
                "success": True,
                "message": "后台采集任务已启动",
                "task_id": task.task_id
            })
        else:
            return jsonify({"success": False, "message": "启动任务失败"}), 500
            
    except Exception as e:
        app.logger.exception("启动后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/tasks/<task_id>/status", methods=["GET"])
def api_get_task_status(task_id):
    """获取任务状态"""
    status = background_task_manager.get_task_status(task_id)
    if status:
        return jsonify({"success": True, "task": status})
    return jsonify({"success": False, "message": "任务不存在"}), 404


@app.route("/api/tasks/<task_id>/stop", methods=["POST"])
def api_stop_task(task_id):
    """停止任务"""
    if background_task_manager.stop_task(task_id):
        return jsonify({"success": True, "message": "已发送停止信号"})
    return jsonify({"success": False, "message": "无法停止任务"}), 400


@app.route("/api/tasks/<task_id>/logs", methods=["GET"])
def api_get_task_logs(task_id):
    """获取任务日志"""
    task = background_task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "任务不存在"}), 404
    
    offset = request.args.get('offset', type=int, default=0)
    limit = request.args.get('limit', type=int, default=100)
    
    logs = task.logs[offset:offset + limit]
    return jsonify({
        "success": True,
        "logs": logs,
        "total": len(task.logs),
        "has_more": offset + limit < len(task.logs)
    })


@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    """列出所有任务"""
    task_type = request.args.get('type')
    status_str = request.args.get('status')
    limit = request.args.get('limit', type=int, default=20)
    
    status = TaskStatus(status_str) if status_str else None
    tasks = background_task_manager.list_tasks(task_type=task_type, status=status, limit=limit)
    
    return jsonify({
        "success": True,
        "tasks": tasks,
        "count": len(tasks)
    })


@app.route("/api/tasks/running", methods=["GET"])
def api_get_running_tasks():
    """获取运行中的任务"""
    tasks = background_task_manager.get_running_tasks()
    return jsonify({
        "success": True,
        "tasks": tasks,
        "count": len(tasks)
    })


# ============================================================
# 🔥 后台采集API - 支持关闭网页后继续采集
# ============================================================

@app.route("/api/background_collect/start", methods=["POST"])
def api_background_collect_start():
    """
    启动后台采集任务
    
    关闭网页后采集会继续运行，登录失效时自动恢复
    
    请求参数:
    - start_date: 起始日期 (必填, 格式: YYYY-MM-DD)
    - end_date: 结束日期 (可选, 默认昨天)
    - filter_by_handicap: 是否只采集有盘口的比赛 (可选, 默认true)
    - skip_cached: 是否跳过已缓存的比赛 (可选, 默认true)
    - workers: 并发数 (可选, 默认2, 最大5)
    - super_mode: 是否启用四合一采集模式 (可选, 默认true)
    """
    try:
        data = request.get_json() or {}
        
        start_date = data.get('start_date')
        if not start_date:
            return jsonify({"success": False, "message": "请提供起始日期 start_date"}), 400
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = data.get('end_date') or yesterday
        filter_by_handicap = data.get('filter_by_handicap', True)
        skip_cached = data.get('skip_cached', True)
        workers = min(int(data.get('workers', 2)), 5)  # 🔥 降低默认并发数到2避免被限流，最大5
        super_mode = data.get('super_mode', True)  # 🔥 新增：四合一采集模式
        
        # 检查是否有任务在运行
        current_task = background_collector.get_current_task()
        if current_task and current_task.get('status') == 'running':
            return jsonify({
                "success": False,
                "message": f"已有采集任务在运行: {current_task.get('task_id')}",
                "current_task": current_task
            }), 409
        
        # 创建任务
        task = background_collector.create_task(
            start_date=start_date,
            end_date=end_date,
            filter_by_handicap=filter_by_handicap,
            skip_cached=skip_cached,
            workers=workers,
            super_mode=super_mode  # 🔥 新增
        )
        
        mode_str = "四合一模式" if super_mode else "标准模式"
        
        # 启动任务
        if background_collector.start_task(task.task_id):
            app.logger.info(f"🚀 后台采集任务已启动: {task.task_id} ({mode_str})")
            return jsonify({
                "success": True,
                "message": f"后台采集任务已启动（{mode_str}），关闭网页后采集会继续运行",
                "task_id": task.task_id,
                "task": task.to_dict()
            })
        else:
            return jsonify({"success": False, "message": "启动任务失败"}), 500
            
    except Exception as e:
        app.logger.exception("启动后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/status", methods=["GET"])
def api_background_collect_status():
    """
    获取当前后台采集任务状态
    
    返回当前运行的任务信息，包括进度、日志等
    """
    try:
        task_id = request.args.get('task_id')
        
        if task_id:
            # 获取指定任务
            task_status = background_collector.get_task_status(task_id)
            if not task_status:
                return jsonify({"success": False, "message": "任务不存在"}), 404
            return jsonify({"success": True, "task": task_status})
        else:
            # 获取当前任务
            current_task = background_collector.get_current_task()
            return jsonify({
                "success": True,
                "has_running_task": current_task is not None and current_task.get('status') == 'running',
                "current_task": current_task
            })
            
    except Exception as e:
        app.logger.exception("获取后台采集状态失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/stop", methods=["POST"])
def api_background_collect_stop():
    """停止后台采集任务"""
    try:
        data = request.get_json() or {}
        task_id = data.get('task_id')
        
        if not task_id:
            # 停止当前任务
            current_task = background_collector.get_current_task()
            if current_task:
                task_id = current_task.get('task_id')
            else:
                return jsonify({"success": False, "message": "没有正在运行的任务"}), 404
        
        if background_collector.stop_task(task_id):
            return jsonify({"success": True, "message": "已发送停止信号"})
        return jsonify({"success": False, "message": "无法停止任务"}), 400
        
    except Exception as e:
        app.logger.exception("停止后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/pause", methods=["POST"])
def api_background_collect_pause():
    """暂停后台采集任务"""
    try:
        data = request.get_json() or {}
        task_id = data.get('task_id')
        
        if not task_id:
            current_task = background_collector.get_current_task()
            if current_task:
                task_id = current_task.get('task_id')
            else:
                return jsonify({"success": False, "message": "没有正在运行的任务"}), 404
        
        if background_collector.pause_task(task_id):
            return jsonify({"success": True, "message": "任务已暂停，可以稍后恢复"})
        return jsonify({"success": False, "message": "无法暂停任务"}), 400
        
    except Exception as e:
        app.logger.exception("暂停后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/resume", methods=["POST"])
def api_background_collect_resume():
    """
    恢复后台采集任务
    
    从断点继续采集，已处理的比赛会自动跳过
    """
    try:
        data = request.get_json() or {}
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({"success": False, "message": "请提供 task_id"}), 400
        
        if background_collector.resume_task(task_id):
            task_status = background_collector.get_task_status(task_id)
            return jsonify({
                "success": True,
                "message": "任务已恢复，从断点继续采集",
                "task": task_status
            })
        return jsonify({"success": False, "message": "无法恢复任务"}), 400
        
    except Exception as e:
        app.logger.exception("恢复后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/list", methods=["GET"])
def api_background_collect_list():
    """列出所有后台采集任务"""
    try:
        limit = request.args.get('limit', type=int, default=20)
        tasks = background_collector.list_tasks(limit=limit)
        
        return jsonify({
            "success": True,
            "tasks": tasks,
            "count": len(tasks)
        })
        
    except Exception as e:
        app.logger.exception("列出后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/delete", methods=["DELETE"])
def api_background_collect_delete():
    """删除后台采集任务"""
    try:
        task_id = request.args.get('task_id')
        
        if not task_id:
            return jsonify({"success": False, "message": "请提供 task_id"}), 400
        
        # 检查任务是否存在
        task = background_collector.get_task(task_id)
        if not task:
            return jsonify({"success": False, "message": "任务不存在"}), 404
        
        # 如果任务正在运行，先停止
        if task.status.value == 'running':
            background_collector.stop_task(task_id)
        
        # 删除任务
        if background_collector.delete_task(task_id):
            return jsonify({"success": True, "message": "任务已删除"})
        return jsonify({"success": False, "message": "无法删除任务"}), 400
        
    except Exception as e:
        app.logger.exception("删除后台采集任务失败")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/background_collect/logs", methods=["GET"])
def api_background_collect_logs():
    """获取后台采集任务日志"""
    try:
        task_id = request.args.get('task_id')
        
        if not task_id:
            current_task = background_collector.get_current_task()
            if current_task:
                task_id = current_task.get('task_id')
            else:
                return jsonify({"success": False, "message": "请提供 task_id"}), 400
        
        task = background_collector.get_task(task_id)
        if not task:
            return jsonify({"success": False, "message": "任务不存在"}), 404
        
        offset = request.args.get('offset', type=int, default=0)
        limit = request.args.get('limit', type=int, default=100)
        
        logs = task.logs[offset:offset + limit]
        return jsonify({
            "success": True,
            "logs": logs,
            "total": len(task.logs),
            "has_more": offset + limit < len(task.logs)
        })
        
    except Exception as e:
        app.logger.exception("获取后台采集日志失败")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================================
# 🔥 超级明细采集 API - 整合标盘、大小球、让球指数、比分数据
# ============================================================================

@app.route("/api/super_detail/collect", methods=["POST"])
def api_collect_super_detail():
    """
    采集超级明细数据（包含让球指数和比分）
    
    请求参数:
    {
        "date": "2025-01-07",  // 可选，默认昨天
        "max_matches": 5       // 可选，最多采集几场，默认5
    }
    
    返回:
    {
        "success": true,
        "data": {
            "match_id": {...超级JSON数据...}
        },
        "summary": {
            "total": 5,
            "success": 3,
            "failed": 2
        }
    }
    """
    from services.selenium_helper import capture_all_detail_urls
    from parser.super_detail_parser import (
        parse_handicap_trade_html,
        parse_correct_score_html,
        create_super_json,
        save_super_json,
    )
    from urllib.parse import urljoin
    import requests as req_lib
    
    try:
        data = request.get_json(force=True) or {}
        date_str = data.get("date")
        max_matches = data.get("max_matches", 5)
        
        # 解析日期
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            target_date = datetime.now() - timedelta(days=1)
        
        date_str = f"{target_date.year}-{target_date.month}-{target_date.day}"
        app.logger.info(f"[超级明细] 开始采集 {date_str} 的数据，最多 {max_matches} 场")
        
        results = {}
        summary = {"total": 0, "success": 0, "failed": 0, "errors": []}
        
        driver = None
        try:
            # 初始化浏览器
            driver = bifaw_client._init_driver(headless=True)
            bifaw_client._inject_cookies(driver)
            
            # 访问首页建立session
            index_url = "https://www.bifaw.com/bifaw/index.php"
            driver.get(index_url)
            time_module.sleep(2)
            
            # 访问完场回查页面
            result_url = f"https://www.bifaw.com/bifaw/result.php?rq={date_str}"
            app.logger.info(f"[超级明细] 访问完场回查: {result_url}")
            driver.get(result_url)
            time_module.sleep(3)
            
            # 捕获所有类型的明细链接
            app.logger.info(f"[超级明细] 开始捕获明细链接...")
            all_urls = capture_all_detail_urls(driver, max_buttons=max_matches)
            
            app.logger.info(f"[超级明细] 捕获到 {len(all_urls)} 场比赛的链接")
            
            if not all_urls:
                return jsonify({
                    "success": False,
                    "message": f"未找到 {date_str} 的比赛数据，请确认日期是否正确",
                    "data": {},
                    "summary": summary
                })
            
            # 获取cookies用于requests
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            
            # 关闭浏览器
            driver.quit()
            driver = None
            
            # 创建requests session
            session = req_lib.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.bifaw.com/'
            })
            session.cookies.update(cookies)
            
            # 遍历每场比赛，获取详细数据
            for match_id, urls in all_urls.items():
                summary["total"] += 1
                
                try:
                    app.logger.info(f"[超级明细] 处理比赛 {match_id}...")
                    
                    handicap_data = None
                    correct_score_data = None
                    
                    # 获取让球指数数据
                    if urls.get('handicap_url'):
                        try:
                            resp = session.get(urls['handicap_url'], timeout=30)
                            resp.encoding = 'utf-8'
                            handicap_data = parse_handicap_trade_html(resp.text)
                            app.logger.info(f"  让球指数记录: {len(handicap_data.get('trade_records', []))}")
                        except Exception as e:
                            app.logger.warning(f"  获取让球指数失败: {e}")
                    
                    # 获取比分数据
                    if urls.get('correct_score_url'):
                        try:
                            resp = session.get(urls['correct_score_url'], timeout=30)
                            resp.encoding = 'utf-8'
                            correct_score_data = parse_correct_score_html(resp.text)
                            app.logger.info(f"  比分记录: {len(correct_score_data.get('trade_records', []))}")
                        except Exception as e:
                            app.logger.warning(f"  获取比分数据失败: {e}")
                    
                    # 创建超级JSON
                    super_json = create_super_json(
                        match_info={'match_id': match_id, 'date': date_str, **urls},
                        handicap_data=handicap_data,
                        correct_score_data=correct_score_data,
                        # 🔥 新增：传递所有盘口信息
                        handicap_all_lines=urls.get('handicap_all_lines'),
                        ou_all_lines=urls.get('ou_all_lines'),
                        handicap_main_line=urls.get('handicap_main_line'),
                        ou_main_line=urls.get('ou_main_line'),
                    )
                    
                    # 保存到文件
                    output_dir = Path(__file__).parent / "data" / "super_detail" / date_str.replace('-', '')
                    output_dir.mkdir(parents=True, exist_ok=True)
                    filepath = output_dir / f"match_{match_id}.json"
                    save_super_json(super_json, filepath)
                    
                    results[match_id] = super_json
                    summary["success"] += 1
                    
                except Exception as e:
                    app.logger.error(f"  处理比赛 {match_id} 失败: {e}")
                    summary["failed"] += 1
                    summary["errors"].append({"match_id": match_id, "error": str(e)})
            
            return jsonify({
                "success": True,
                "message": f"采集完成: {summary['success']}/{summary['total']} 成功",
                "data": results,
                "summary": summary
            })
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                    
    except Exception as e:
        app.logger.exception("超级明细采集失败")
        return jsonify({
            "success": False,
            "message": str(e),
            "data": {},
            "summary": {"total": 0, "success": 0, "failed": 0}
        }), 500


@app.route("/api/super_detail/test", methods=["GET"])
def api_test_super_detail():
    """
    测试超级明细采集（采集1场比赛的完整数据）
    包含：标盘、大小球、让球指数、比分
    
    GET /api/super_detail/test?date=2025-01-07
    """
    from services.selenium_helper import capture_all_detail_urls
    from parser.super_detail_parser import (
        parse_handicap_trade_html,
        parse_correct_score_html,
        create_super_json,
        save_super_json,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import requests as req_lib
    
    try:
        date_str = request.args.get('date')
        
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            target_date = datetime.now() - timedelta(days=1)
        
        date_str_query = f"{target_date.year}-{target_date.month}-{target_date.day}"
        app.logger.info(f"[超级明细测试] 日期: {date_str_query}")
        
        driver = None
        try:
            driver = bifaw_client._init_driver(headless=False)
            bifaw_client._inject_cookies(driver)
            
            # 先访问首页建立session
            index_url = "https://www.bifaw.com/bifaw/index.php"
            app.logger.info(f"[超级明细测试] 访问首页: {index_url}")
            driver.get(index_url)
            time_module.sleep(2)
            
            # 访问完场回查页面获取标盘和大小球URL
            try:
                result_link = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'result.php')]"))
                )
                app.logger.info("[超级明细测试] 找到完场回查链接，点击进入...")
                result_link.click()
                time_module.sleep(3)
            except Exception as e:
                result_url = f"https://www.bifaw.com/bifaw/result.php?rq={date_str_query}"
                app.logger.info(f"[超级明细测试] 直接访问: {result_url}")
                driver.get(result_url)
                time_module.sleep(2)
            
            # 等待页面加载
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: "标盘明细" in d.page_source or "完场回查" in d.page_source
                )
                app.logger.info("[超级明细测试] 页面加载完成")
            except:
                app.logger.warning("[超级明细测试] 页面加载等待超时")
            
            # 设置查询日期
            try:
                date_input = None
                for selector in ["#matchdate", "#rq", "input[name='matchdate']", "input[name='rq']"]:
                    try:
                        date_input = driver.find_element(By.CSS_SELECTOR, selector)
                        if date_input:
                            app.logger.info(f"[超级明细测试] 找到日期输入框: {selector}")
                            break
                    except:
                        continue
                
                if date_input:
                    driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                    app.logger.info(f"[超级明细测试] 日期设置: {date_str_query}")
                    
                    query_clicked = False
                    for by, sel in [
                        (By.XPATH, "//input[@value='查询']"),
                        (By.CSS_SELECTOR, "input[value='查询']"),
                    ]:
                        try:
                            query_btn = driver.find_element(by, sel)
                            if query_btn and query_btn.is_enabled():
                                query_btn.click()
                                app.logger.info(f"[超级明细测试] 已点击查询按钮")
                                query_clicked = True
                                time_module.sleep(5)
                                break
                        except:
                            continue
            except Exception as e:
                app.logger.warning(f"[超级明细测试] 设置日期失败: {e}")
            
            time_module.sleep(2)
            
            # 捕获标盘和大小球URL
            app.logger.info("[超级明细测试] 捕获标盘和大小球URL...")
            all_urls = capture_all_detail_urls(driver, max_buttons=1)
            
            if not all_urls:
                return jsonify({
                    "success": False,
                    "message": f"未找到 {date_str_query} 的比赛",
                    "page_title": driver.title,
                    "current_url": driver.current_url
                })
            
            match_id, urls = list(all_urls.items())[0]
            app.logger.info(f"[超级明细测试] 获取到比赛: {match_id}")
            
            # 创建调试目录
            debug_dir = Path(__file__).parent / "debug_html"
            debug_dir.mkdir(exist_ok=True)
            
            # ========== 访问让球回查页面获取让球URL ==========
            app.logger.info("[超级明细测试] 访问让球回查页面...")
            aisa_url = f"https://www.bifaw.com/bifaw/result_aisa.php?rq={date_str_query}"
            driver.get(aisa_url)
            time_module.sleep(3)
            
            # 保存让球页面HTML用于调试
            try:
                (debug_dir / f"aisa_page_{date_str_query.replace('-','')}.html").write_text(
                    driver.page_source, encoding='utf-8'
                )
                app.logger.info(f"[超级明细测试] 已保存让球页面HTML")
            except:
                pass
            
            # 设置日期并查询
            try:
                date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate, input[name='matchdate']")
                if date_input:
                    driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                    app.logger.info(f"[超级明细测试] 让球页面日期设置: {date_str_query}")
                    query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                    if query_btn:
                        query_btn.click()
                        app.logger.info(f"[超级明细测试] 让球页面已点击查询")
                        time_module.sleep(5)
            except Exception as e:
                app.logger.warning(f"[超级明细测试] 让球页面设置日期失败: {e}")
            
            # 保存查询后的让球页面HTML
            try:
                (debug_dir / f"aisa_page_after_query_{date_str_query.replace('-','')}.html").write_text(
                    driver.page_source, encoding='utf-8'
                )
            except:
                pass
            
            # 查找让球明细按钮并获取URL
            # 🔥 让球页面的按钮是 <dt onclick="openAisaDetails(...)"><a>交易明细</a></dt>
            try:
                # 🔥 等待页面数据加载完成
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: "openAisaDetails" in d.page_source or "交易明细" in d.page_source
                    )
                    app.logger.info("[超级明细测试] 让球页面数据已加载")
                except Exception as wait_e:
                    app.logger.warning(f"[超级明细测试] 让球页面数据加载等待超时: {wait_e}")
                
                # 额外等待确保DOM完全渲染
                time_module.sleep(3)
                
                # 检查页面源码
                page_source = driver.page_source
                has_aisa_details = 'openAisaDetails' in page_source
                app.logger.info(f"[超级明细测试] 页面包含openAisaDetails: {has_aisa_details}")
                
                # 🔥 使用JavaScript直接提取onclick参数并构造URL
                if has_aisa_details:
                    js_extract = """
                    var elements = document.querySelectorAll('[onclick*="openAisaDetails"]');
                    if (elements.length > 0) {
                        var onclick = elements[0].getAttribute('onclick');
                        // 解析 openAisaDetails('35105507','252247102','1767816900','56299','48351','-0.75','4')
                        var match = onclick.match(/openAisaDetails\\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\\)/);
                        if (match) {
                            return {
                                found: true,
                                count: elements.length,
                                matchid: match[1],
                                eventid: match[2],
                                kickoff: match[3],
                                homeid: match[4],
                                awayid: match[5],
                                hdp: match[6],
                                type: match[7]
                            };
                        }
                    }
                    return {found: false, count: elements.length};
                    """
                    js_result = driver.execute_script(js_extract)
                    app.logger.info(f"[超级明细测试] JS提取让球参数: {js_result}")
                    
                    if js_result and js_result.get('found'):
                        # 构造让球明细URL
                        hdp_detail_url = (
                            f"https://www.bifaw.com/bifaw/aisa_details.php?"
                            f"matchid={js_result['matchid']}&eventid={js_result['eventid']}"
                            f"&kickoff={js_result['kickoff']}&homeid={js_result['homeid']}"
                            f"&awayid={js_result['awayid']}&hdp={js_result['hdp']}&type={js_result['type']}"
                        )
                        urls['handicap_url'] = hdp_detail_url
                        app.logger.info(f"[超级明细测试] 获取让球URL: {hdp_detail_url[:80]}...")
                    else:
                        app.logger.warning(f"[超级明细测试] JS未能提取让球参数")
                else:
                    app.logger.warning("[超级明细测试] 页面不包含openAisaDetails")
            except Exception as e:
                app.logger.warning(f"[超级明细测试] 获取让球URL失败: {e}")
            
            # ========== 访问比分回查页面获取比分URL ==========
            app.logger.info("[超级明细测试] 访问比分回查页面...")
            correct_url = f"https://www.bifaw.com/bifaw/result_correct.php?rq={date_str_query}"
            driver.get(correct_url)
            time_module.sleep(3)
            
            # 保存比分页面HTML用于调试
            try:
                (debug_dir / f"correct_page_{date_str_query.replace('-','')}.html").write_text(
                    driver.page_source, encoding='utf-8'
                )
                app.logger.info(f"[超级明细测试] 已保存比分页面HTML")
            except:
                pass
            
            # 设置日期并查询
            try:
                date_input = driver.find_element(By.CSS_SELECTOR, "#matchdate, input[name='matchdate']")
                if date_input:
                    driver.execute_script(f"arguments[0].value = '{date_str_query}';", date_input)
                    app.logger.info(f"[超级明细测试] 比分页面日期设置: {date_str_query}")
                    query_btn = driver.find_element(By.CSS_SELECTOR, "input[value='查询']")
                    if query_btn:
                        query_btn.click()
                        app.logger.info(f"[超级明细测试] 比分页面已点击查询")
                        time_module.sleep(5)
            except Exception as e:
                app.logger.warning(f"[超级明细测试] 比分页面设置日期失败: {e}")
            
            # 保存查询后的比分页面HTML
            try:
                (debug_dir / f"correct_page_after_query_{date_str_query.replace('-','')}.html").write_text(
                    driver.page_source, encoding='utf-8'
                )
            except:
                pass
            
            # 查找比分明细按钮并获取URL
            # 🔥 比分页面的按钮是 <a onclick="openCorrectDetails(...)">明细</a>
            try:
                # 等待页面完全加载
                try:
                    WebDriverWait(driver, 15).until(
                        lambda d: "openCorrectDetails" in d.page_source or "明细" in d.page_source
                    )
                    app.logger.info("[超级明细测试] 比分页面数据已加载")
                except Exception as wait_e:
                    app.logger.warning(f"[超级明细测试] 比分页面数据加载等待超时: {wait_e}")
                
                # 额外等待确保DOM完全渲染
                time_module.sleep(3)
                
                # 打印页面源码中是否包含关键字
                page_source = driver.page_source
                has_correct_details = 'openCorrectDetails' in page_source
                app.logger.info(f"[超级明细测试] 页面包含openCorrectDetails: {has_correct_details}")
                
                # 🔥 使用JavaScript直接提取onclick参数并构造URL
                if has_correct_details:
                    js_extract = """
                    var elements = document.querySelectorAll('[onclick*="openCorrectDetails"]');
                    if (elements.length > 0) {
                        var onclick = elements[0].getAttribute('onclick');
                        // 解析 openCorrectDetails('35105510','252247019','1767816900','4') - 只有4个参数
                        var match = onclick.match(/openCorrectDetails\\('([^']+)','([^']+)','([^']+)','([^']+)'\\)/);
                        if (match) {
                            return {
                                found: true,
                                count: elements.length,
                                matchid: match[1],
                                eventid: match[2],
                                kickoff: match[3],
                                type: match[4]
                            };
                        }
                    }
                    return {found: false, count: elements.length};
                    """
                    js_result = driver.execute_script(js_extract)
                    app.logger.info(f"[超级明细测试] JS提取比分参数: {js_result}")
                    
                    if js_result and js_result.get('found'):
                        # 构造比分明细URL - 只需要4个参数
                        cs_detail_url = (
                            f"https://www.bifaw.com/bifaw/correct_details.php?"
                            f"matchid={js_result['matchid']}&eventid={js_result['eventid']}"
                            f"&kickoff={js_result['kickoff']}&type={js_result['type']}"
                        )
                        urls['correct_score_url'] = cs_detail_url
                        app.logger.info(f"[超级明细测试] 获取比分URL: {cs_detail_url[:80]}...")
                    else:
                        app.logger.warning(f"[超级明细测试] JS未能提取比分参数")
                else:
                    app.logger.warning("[超级明细测试] 页面不包含openCorrectDetails")
            except Exception as e:
                app.logger.warning(f"[超级明细测试] 获取比分URL失败: {e}")
            
            # 获取cookies用于requests
            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
            driver.quit()
            driver = None
            
            # 使用requests获取HTML并解析
            session = req_lib.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.bifaw.com/'
            })
            session.cookies.update(cookies)
            
            debug_dir = Path(__file__).parent / "debug_html"
            debug_dir.mkdir(exist_ok=True)
            
            standard_data = None
            ou_data = None
            handicap_data = None
            correct_score_data = None
            
            # 获取标盘数据
            if urls.get('standard_url'):
                try:
                    app.logger.info(f"[超级明细测试] 获取标盘数据...")
                    resp = session.get(urls['standard_url'], timeout=30)
                    resp.encoding = 'utf-8'
                    (debug_dir / f"standard_{match_id}.html").write_text(resp.text, encoding='utf-8')
                    # 使用现有的解析器
                    from parser.html_parser import parse_bifa_html
                    df = parse_bifa_html(resp.text, {'match_id': match_id})
                    if isinstance(df, pd.DataFrame) and len(df) > 0:
                        standard_data = {
                            "columns": df.columns.tolist(),
                            "data": df.to_dict(orient="records"),
                            "total_records": len(df)
                        }
                        app.logger.info(f"   标盘记录数: {len(df)}")
                except Exception as e:
                    app.logger.warning(f"   获取标盘数据失败: {e}")
            
            # 获取大小球数据
            if urls.get('ou_url'):
                try:
                    app.logger.info(f"[超级明细测试] 获取大小球数据...")
                    resp = session.get(urls['ou_url'], timeout=30)
                    resp.encoding = 'utf-8'
                    (debug_dir / f"ou_{match_id}.html").write_text(resp.text, encoding='utf-8')
                    from parser.html_parser import parse_bifa_html
                    df = parse_bifa_html(resp.text, {'match_id': match_id})
                    if isinstance(df, pd.DataFrame) and len(df) > 0:
                        ou_data = {
                            "ou_line": urls.get('ou_hdp'),
                            "columns": df.columns.tolist(),
                            "data": df.to_dict(orient="records"),
                            "total_records": len(df)
                        }
                        app.logger.info(f"   大小球记录数: {len(df)}")
                except Exception as e:
                    app.logger.warning(f"   获取大小球数据失败: {e}")
            
            # 获取让球指数数据
            if urls.get('handicap_url'):
                try:
                    app.logger.info(f"[超级明细测试] 获取让球指数数据...")
                    resp = session.get(urls['handicap_url'], timeout=30)
                    resp.encoding = 'utf-8'
                    (debug_dir / f"handicap_{match_id}.html").write_text(resp.text, encoding='utf-8')
                    handicap_data = parse_handicap_trade_html(resp.text)
                    app.logger.info(f"   让球指数记录数: {len(handicap_data.get('trade_records', []))}")
                except Exception as e:
                    app.logger.warning(f"   获取让球指数数据失败: {e}")
            
            # 获取比分数据
            if urls.get('correct_score_url'):
                try:
                    app.logger.info(f"[超级明细测试] 获取比分数据...")
                    resp = session.get(urls['correct_score_url'], timeout=30)
                    resp.encoding = 'utf-8'
                    (debug_dir / f"correct_score_{match_id}.html").write_text(resp.text, encoding='utf-8')
                    correct_score_data = parse_correct_score_html(resp.text)
                    app.logger.info(f"   比分记录数: {len(correct_score_data.get('trade_records', []))}")
                except Exception as e:
                    app.logger.warning(f"   获取比分数据失败: {e}")
            
            # 创建超级JSON
            super_json = create_super_json(
                match_info={'match_id': match_id, 'date': date_str_query, **urls},
                standard_data=standard_data,
                ou_data=ou_data,
                handicap_data=handicap_data,
                correct_score_data=correct_score_data,
                # 🔥 新增：传递所有盘口信息
                handicap_all_lines=urls.get('handicap_all_lines'),
                ou_all_lines=urls.get('ou_all_lines'),
                handicap_main_line=urls.get('handicap_main_line'),
                ou_main_line=urls.get('ou_main_line'),
            )
            
            # 保存到文件
            output_dir = Path(__file__).parent / "data" / "super_detail" / date_str_query.replace('-', '')
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / f"match_{match_id}.json"
            save_super_json(super_json, filepath)
            
            return jsonify({
                "success": True,
                "match_id": match_id,
                "urls": urls,
                "super_json": super_json,
                "saved_to": str(filepath)
            })
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                    
    except Exception as e:
        app.logger.exception("超级明细测试失败")
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    # 🔥 注册X1 JSON推荐路由
    try:
        from api_x1_json_recommendation import register_x1_json_routes
        register_x1_json_routes(app)
        app.logger.info("🎯 X1 JSON推荐API已注册")
        app.logger.info("   - POST /api/x1/recommend - 单个推荐")
        app.logger.info("   - POST /api/x1/batch_recommend - 批量推荐")
        app.logger.info("   - GET /api/x1/stats - 统计信息")
        app.logger.info("   - POST /api/x1/review/trigger - 触发审查")
        app.logger.info("   - GET /api/x1/review/history - 审查历史")
        app.logger.info("   - GET /api/x1/review/pending - 待审查列表")
    except Exception as e:
        app.logger.warning(f"⚠️ X1 JSON推荐API注册失败: {e}")
    
    # 🔥 注册每日审查定时任务
    try:
        from daily_review_scheduler import schedule_daily_review
        # 获取企业微信Webhook
        import os
        wecom_webhook = os.getenv('WECOM_WEBHOOK') or os.getenv('WECOM_ALERT_WEBHOOK')
        if not wecom_webhook:
            wecom_webhook = ""
        
        schedule_daily_review(scheduler, wecom_webhook)
        app.logger.info("⏰ 每日审查定时任务已注册（每天中午12:00）")
    except Exception as e:
        app.logger.warning(f"⚠️ 每日审查定时任务注册失败: {e}")
    
    # 🔥 配置日志文件输出
    operation_logger.setup_logger(app.logger, level=logging.INFO)
    
    # 也为其他模块配置文件输出
    for logger_name in ['auto_recommend_push', 'services.bifaw_client', 'services.lottery500_client']:
        module_logger = logging.getLogger(logger_name)
        operation_logger.setup_logger(module_logger, level=logging.INFO)
    
    app.logger.info("="*80)
    app.logger.info("🚀 Football Analysis System - 启动中")
    app.logger.info("="*80)
    app.logger.info(f"📝 操作日志已启用")
    app.logger.info(f"   日志目录: {operation_logger.log_dir}")
    app.logger.info(f"   轮转周期: {operation_logger.rotation_hours}小时")
    app.logger.info(f"   保留天数: {operation_logger.keep_days}天")
    app.logger.info("="*80)
    app.logger.info(f"🚨 告警系统已启用")
    alert_webhook = alert_manager.wecom_webhook
    if alert_webhook:
        app.logger.info(f"   企微Webhook: {alert_webhook[:50]}...")
        app.logger.info(f"   告警冷却期: {alert_manager.cooldown_minutes}分钟")
    else:
        app.logger.warning(f"   ⚠️  未配置WECOM_ALERT_WEBHOOK环境变量，告警将无法发送")
    app.logger.info("="*80)
    
    # 🔥 输出路径信息，方便验证配置
    app.logger.info("="*80)
    app.logger.info("📂 工作目录配置")
    app.logger.info("="*80)
    app.logger.info(f"  项目根目录: {BASE_DIR}")
    app.logger.info(f"  数据目录: {BASE_DIR / 'data'}")
    app.logger.info(f"  日志目录: {BASE_DIR / 'logs'}")
    app.logger.info(f"  缓存管理器目录: {detail_cache_manager.cache_dir}")
    app.logger.info(f"  500彩票数据目录: {lottery500_client.data_dir}")
    app.logger.info("="*80)
    
    # 🔥 启动定时任务调度器（测试时可禁用）
    import os
    # 🔥 调度器控制：服务器默认启用，本地测试可设置 DISABLE_SCHEDULER=true 禁用
    _disable_scheduler = os.getenv('DISABLE_SCHEDULER', 'false').lower() == 'true'  # 默认启用
    if not _disable_scheduler:
        scheduler.start()
        app.logger.info("✅ 定时任务调度器已启动")
    else:
        app.logger.warning("⚠️ 定时任务调度器已禁用（设置了 DISABLE_SCHEDULER=true）")
    app.logger.info("")
    app.logger.info("🤖 本地OCR自动登录已启用（ddddocr，无API限制）")
    app.logger.info("")
    app.logger.info(f"  - 每天早上8点自动采集今天的比赛（包括未开始的）")
    app.logger.info(f"  - 每天凌晨3点自动采集昨天的完场比赛")
    app.logger.info(f"  - 每10分钟自动检查并保持登录状态")
    app.logger.info(f"  - 🏥 每小时进行系统健康检查（磁盘、日志、数据、调度器等）")
    if auto_push_system:
        minutes_before = int(auto_push_system.hours_before * 60)
        minutes_window_end = int((auto_push_system.hours_before + auto_push_system.hours_window) * 60)
        app.logger.info(f"  - 🔔 每10分钟扫描一次，临场推送（提前{minutes_before}-{minutes_window_end}分钟）")
        app.logger.info(f"  - 📢 每小时59分播报（提前1分钟播报下一小时比赛，例如20:59播报21:00~22:00）")
        
        if schedule_manager:
            app.logger.info(f"  - 📅 每天10点扫描比赛并创建推送任务（精确到点推送，不会遗漏）")
            app.logger.info(f"  - 🔔 服务启动时自动扫描一次，为今日未开始的比赛创建推送任务")
        else:
            app.logger.info(f"  - 🔔 每5分钟检查赛前5分钟推荐推送（包含推荐方向，不推荐也会说明）")
        
        app.logger.info(f"     企业微信: {'✅' if auto_push_system.use_wecom else '❌'} | Telegram: {'✅' if auto_push_system.use_telegram else '❌'}")
    else:
        app.logger.warning(f"  - ⚠️ 自动推送系统未启用")
    
    # 🔥 启动自动恢复服务
    auto_recovery_service = AutoRecoveryService(
        progress_manager=progress_manager,
        recovery_callback=auto_recovery_callback
    )
    if not _disable_scheduler:
        auto_recovery_service.start()
        app.logger.info("✅ 自动恢复服务已启动")
    else:
        app.logger.warning("⚠️ 自动恢复服务已禁用")
    app.logger.info(f"  - 每5分钟检测一次中断的采集任务")
    app.logger.info(f"  - 自动尝试恢复中断的会话（最多3次）")
    
    # 🔥 服务启动时执行自动清理（清理超过3天的调试文件等）
    try:
        app.logger.info("🧹 执行启动清理...")
        cleanup_result = run_cleanup(dry_run=False)
        if cleanup_result.get('files_deleted', 0) > 0:
            app.logger.info(f"  ✅ 清理完成: 删除 {cleanup_result['files_deleted']} 个文件, 释放 {cleanup_result['bytes_freed'] / 1024 / 1024:.2f} MB")
        else:
            app.logger.info("  ✅ 无需清理（没有过期文件）")
    except Exception as e:
        app.logger.warning(f"  ⚠️ 自动清理失败: {e}")
    
    # 🔥 服务启动后自动恢复后台采集任务
    def delayed_auto_resume():
        """延迟自动恢复后台采集任务"""
        import time
        time.sleep(30)  # 等待30秒，确保所有依赖初始化完成
        try:
            background_collector.auto_resume_paused_tasks()
        except Exception as e:
            app.logger.error(f"自动恢复后台采集任务失败: {e}")
    
    if not _disable_scheduler:
        resume_thread = threading.Thread(target=delayed_auto_resume, daemon=True)
        resume_thread.start()
        app.logger.info("🔄 后台采集任务将在30秒后自动恢复（如有未完成的任务）")
    
    try:
        # 🔥 禁用自动重载，避免Windows上的套接字错误
        # 如需重载，手动重启即可
        # 🔥 生产环境：host="0.0.0.0" 允许外部访问，debug=False
        import os
        host = os.getenv('FLASK_HOST', '0.0.0.0')  # 默认允许外部访问
        port = int(os.getenv('FLASK_PORT', '5001'))  # 默认端口改为5001
        debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        
        app.logger.info(f"🚀 服务器启动配置: {host}:{port} (debug={debug})")
        app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
    finally:
        # 关闭调度器
        if scheduler.running:
            scheduler.shutdown()
            app.logger.info("✅ 定时任务调度器已关闭")
        
        # 关闭自动恢复服务
        if auto_recovery_service:
            auto_recovery_service.stop()
            app.logger.info("✅ 自动恢复服务已关闭")

