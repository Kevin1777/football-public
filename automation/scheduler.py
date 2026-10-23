"""自动化调度器"""
import time
import schedule
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import BifawClient
from parser.html_parser import parse_bifa_html
from recommendation.analyzer import MatchAnalyzer
from recommendation.predictor import MatchPredictor
from notification.telegram_bot import TelegramNotifier
from automation.database import MatchDatabase

logger = logging.getLogger(__name__)


class AutoScheduler:
    """自动化任务调度器"""
    
    def __init__(self):
        self.bifaw_client = BifawClient()
        self.analyzer = MatchAnalyzer()
        self.predictor = MatchPredictor()
        self.notifier = TelegramNotifier()
        self.database = MatchDatabase()
        
        self.running = False
        self.processed_matches = set()  # 避免重复推送
    
    def start(self):
        """启动调度器"""
        logger.info("🚀 自动调度器启动")
        self.running = True
        
        # 配置定时任务
        # 每小时检查即将开始的比赛
        schedule.every(1).hours.do(self.collect_upcoming_matches)
        
        # 每天凌晨3点采集前一天的完场数据
        schedule.every().day.at("03:00").do(self.collect_finished_matches)
        
        # 立即执行一次
        self.collect_upcoming_matches()
        
        # 循环执行
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                logger.info("收到停止信号")
                self.stop()
            except Exception as e:
                logger.error(f"调度器异常: {e}")
                time.sleep(60)
    
    def stop(self):
        """停止调度器"""
        logger.info("⏹️  自动调度器停止")
        self.running = False
    
    def collect_upcoming_matches(self):
        """采集即将开始的比赛"""
        try:
            logger.info("\n" + "="*60)
            logger.info("📡 开始采集即将开始的比赛...")
            logger.info("="*60)
            
            # 获取未来2天的比赛列表
            matches = self.bifaw_client.fetch_match_list_v2(rows=200, days=2)
            
            if not matches:
                logger.warning("未找到即将开始的比赛")
                return
            
            logger.info(f"找到 {len(matches)} 场比赛")
            
            # 筛选2小时内开始的比赛
            upcoming = self._filter_upcoming_matches(matches, hours=2)
            
            logger.info(f"其中 {len(upcoming)} 场即将在2小时内开始")
            
            # 处理每场比赛
            for match in upcoming:
                self._process_match(match)
            
            logger.info("✅ 即将开始的比赛采集完成\n")
            
        except Exception as e:
            logger.error(f"采集即将开始的比赛失败: {e}")
    
    def collect_finished_matches(self):
        """采集昨天的完场数据"""
        try:
            logger.info("\n" + "="*60)
            logger.info("📊 开始采集完场数据...")
            logger.info("="*60)
            
            yesterday = datetime.now() - timedelta(days=1)
            
            # 获取完场比赛
            finished_matches = self.bifaw_client.fetch_finished_matches(
                target_date=yesterday,
                rows=200
            )
            
            logger.info(f"找到 {len(finished_matches)} 场完场比赛")
            
            # 采集每场比赛的明细并存储
            for i, match in enumerate(finished_matches, 1):
                try:
                    logger.info(f"[{i}/{len(finished_matches)}] 采集: {match.get('label')}")
                    
                    # 获取交易明细
                    detail_html = self.bifaw_client.fetch_match_detail_selenium(
                        detail_url=match.get('detail_url'),
                        match=match
                    )
                    
                    # 解析数据
                    parsed_data = parse_bifa_html(detail_html)
                    
                    if parsed_data is not None and not parsed_data.empty:
                        # 分析数据
                        metadata = parsed_data.attrs.get("metadata", [])
                        analysis = self.analyzer.analyze_trade_data(parsed_data, metadata)
                        
                        # 存储到数据库
                        self.database.save_match_data(match, parsed_data, analysis)
                        logger.info(f"  ✅ 已保存")
                    else:
                        logger.warning(f"  ⚠️  解析失败")
                    
                    time.sleep(2)  # 避免请求过快
                    
                except Exception as e:
                    logger.error(f"  ❌ 处理失败: {e}")
                    continue
            
            logger.info("✅ 完场数据采集完成\n")
            
        except Exception as e:
            logger.error(f"采集完场数据失败: {e}")
    
    def _filter_upcoming_matches(self, matches: list, hours: int = 2) -> list:
        """筛选即将开始的比赛"""
        upcoming = []
        now = datetime.now()
        threshold = now + timedelta(hours=hours)
        
        for match in matches:
            kickoff_str = match.get('kickoff')
            if not kickoff_str:
                continue
            
            try:
                # 解析开球时间
                kickoff = datetime.strptime(kickoff_str, "%Y-%m-%d %H:%M")
                
                # 筛选条件：未来2小时内开始
                if now < kickoff <= threshold:
                    upcoming.append(match)
            except:
                continue
        
        return upcoming
    
    def _process_match(self, match: dict):
        """处理单场比赛"""
        try:
            match_id = match.get('match_id')
            
            # 避免重复处理
            if match_id in self.processed_matches:
                logger.info(f"跳过已处理的比赛: {match.get('label')}")
                return
            
            logger.info(f"\n处理比赛: {match.get('label')}")
            
            # 1. 获取交易明细
            detail_html = self.bifaw_client.fetch_match_detail_selenium(
                detail_url=match.get('detail_url'),
                match=match
            )
            
            # 2. 解析数据
            parsed_data = parse_bifa_html(detail_html)
            
            if parsed_data is None or parsed_data.empty:
                logger.warning("解析失败，跳过")
                return
            
            # 3. 分析数据
            metadata = parsed_data.attrs.get("metadata", [])
            analysis = self.analyzer.analyze_trade_data(parsed_data, metadata)
            
            # 4. 生成推荐
            prediction = self.predictor.predict(analysis)
            
            # 5. 推送推荐
            if prediction.get('direction') != '不推荐':
                recommendation_data = {
                    "match_info": analysis.get("match_info", {}),
                    "recommendation": prediction
                }
                
                success = self.notifier.send_recommendation(recommendation_data)
                
                if success:
                    logger.info("✅ 推荐已推送到Telegram")
                    self.processed_matches.add(match_id)
                else:
                    logger.warning("⚠️  推送失败")
            else:
                logger.info("📊 不满足推荐条件，跳过推送")
            
            # 6. 保存到数据库
            self.database.save_match_data(match, parsed_data, analysis)
            
        except Exception as e:
            logger.error(f"处理比赛失败: {e}")


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('automation.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 启动调度器
    scheduler = AutoScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
