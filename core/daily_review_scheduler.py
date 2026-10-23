#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日推荐审查定时任务

功能：
1. 每天中午12点自动审查前一天的推荐
2. 生成可视化报告
3. 推送到企业微信
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from recommendation_tracker import tracker
from daily_review_visualizer import generate_daily_report
from notification.wecom_notifier import WeComNotifier

logger = logging.getLogger(__name__)


class DailyReviewScheduler:
    """每日审查调度器"""
    
    def __init__(self, wecom_webhook: str = None):
        self.wecom_notifier = WeComNotifier(wecom_webhook) if wecom_webhook else None
    
    def run_daily_review(self, date: str = None):
        """
        运行每日审查
        
        Args:
            date: 要审查的日期（默认昨天）
        """
        if not date:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        logger.info("=" * 80)
        logger.info(f"🔍 开始每日推荐审查: {date}")
        logger.info("=" * 80)
        
        try:
            # 1. 审查推荐
            review_result = tracker.review_date(date)
            
            if review_result['total'] == 0:
                logger.info(f"⚠️ {date} 没有推荐需要审查")
                return
            
            # 2. 生成可视化报告
            report_path = generate_daily_report(date, review_result)
            logger.info(f"📊 可视化报告已生成: {report_path}")
            
            # 3. 推送到企业微信
            if self.wecom_notifier:
                self._send_review_notification(date, review_result, report_path)
            
            logger.info("=" * 80)
            logger.info(f"✅ 每日审查完成")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.exception(f"❌ 每日审查失败: {e}")
            if self.wecom_notifier:
                self._send_error_notification(date, str(e))
    
    def _send_review_notification(self, date: str, result: Dict, report_path: str):
        """发送审查结果通知"""
        try:
            # 准确率图标
            accuracy = result['accuracy']
            if accuracy >= 80:
                acc_icon = "🟢"
            elif accuracy >= 70:
                acc_icon = "🟡"
            else:
                acc_icon = "🔴"
            
            # 构建消息
            message = f"""## 📊 每日推荐审查报告

**日期**: {date}
**审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

### 📈 整体统计

- **推荐总数**: {result['total']}
- **已审查**: {result['reviewed']}
- **正确**: ✅ {result['correct']}
- **错误**: ❌ {result['wrong']}
- **走盘**: ⚖️ {result['draw']}

### 🎯 准确率

{acc_icon} **整体准确率**: {accuracy:.1f}% ({result['correct']}/{result['correct'] + result['wrong']})

🌟 **高置信度准确率**: {result.get('high_confidence_accuracy', 0):.1f}%

---

### 💡 表现评价

"""
            
            if accuracy >= 85:
                message += "🔥 **优秀**: 准确率超过85%，继续保持！\n"
            elif accuracy >= 75:
                message += "✅ **良好**: 准确率在合理范围内\n"
            elif accuracy >= 65:
                message += "⚠️ **一般**: 准确率略低，需要关注\n"
            else:
                message += "❌ **需改进**: 准确率偏低，建议检查策略\n"
            
            message += f"\n📄 详细报告: [点击查看]({report_path})"
            
            # 发送通知
            self.wecom_notifier.send_markdown(
                "每日推荐审查",
                message
            )
            
            logger.info("✅ 企业微信通知已发送")
            
        except Exception as e:
            logger.exception(f"❌ 发送通知失败: {e}")
    
    def _send_error_notification(self, date: str, error_msg: str):
        """发送错误通知"""
        try:
            message = f"""## ❌ 每日审查失败

**日期**: {date}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

**错误信息**:
```
{error_msg}
```

请检查系统日志。
"""
            
            self.wecom_notifier.send_markdown(
                "每日审查失败",
                message
            )
            
        except Exception as e:
            logger.exception(f"❌ 发送错误通知失败: {e}")


def schedule_daily_review(scheduler_app, wecom_webhook: str = None):
    """
    注册到APScheduler
    
    Args:
        scheduler_app: APScheduler实例
        wecom_webhook: 企业微信Webhook URL
    """
    from apscheduler.triggers.cron import CronTrigger
    
    review_scheduler = DailyReviewScheduler(wecom_webhook)
    
    # 每天中午12点执行
    scheduler_app.add_job(
        func=review_scheduler.run_daily_review,
        trigger=CronTrigger(hour=12, minute=0),
        id='daily_recommendation_review',
        name='每日推荐审查',
        replace_existing=True
    )
    
    logger.info("✅ 每日审查定时任务已注册（每天中午12:00）")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    # 命令行测试
    if len(sys.argv) > 1:
        test_date = sys.argv[1]
    else:
        test_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    scheduler = DailyReviewScheduler()
    scheduler.run_daily_review(test_date)
