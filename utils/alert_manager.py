"""
告警管理器
当系统出现严重错误时，自动发送告警到企业微信
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)


class AlertManager:
    """告警管理器"""
    
    def __init__(self, wecom_webhook: Optional[str] = None):
        """
        初始化告警管理器
        
        Args:
            wecom_webhook: 企业微信机器人Webhook地址
        """
        self.wecom_webhook = wecom_webhook
        self.alert_cooldown = {}  # {alert_type: last_alert_time}
        self.cooldown_minutes = 30  # 同类告警冷却期（分钟）
        
    def send_alert(self, alert_type: str, title: str, message: str, force: bool = False) -> bool:
        """
        发送告警
        
        Args:
            alert_type: 告警类型（用于冷却控制）
            title: 告警标题
            message: 告警内容
            force: 是否强制发送（忽略冷却期）
            
        Returns:
            是否发送成功
        """
        if not self.wecom_webhook:
            logger.warning("企业微信Webhook未配置，无法发送告警")
            return False
        
        # 检查冷却期
        if not force and alert_type in self.alert_cooldown:
            last_time = self.alert_cooldown[alert_type]
            if datetime.now() - last_time < timedelta(minutes=self.cooldown_minutes):
                logger.debug(f"告警 {alert_type} 在冷却期内，跳过发送")
                return False
        
        try:
            # 构造告警消息
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            content = f"""🚨 系统告警

**{title}**

⏰ 时间: {current_time}
📝 详情: {message}

---
_Football Analysis System_
"""
            
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            response = requests.post(
                self.wecom_webhook,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    logger.info(f"✅ 告警已发送: {title}")
                    self.alert_cooldown[alert_type] = datetime.now()
                    return True
                else:
                    logger.error(f"❌ 告警发送失败: {result.get('errmsg')}")
                    return False
            else:
                logger.error(f"❌ 告警发送失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 告警发送异常: {e}")
            return False
    
    def alert_login_failed(self, error_msg: str):
        """登录失败告警"""
        self.send_alert(
            alert_type="login_failed",
            title="自动登录失败",
            message=f"系统无法自动登录，需要手动干预。\n错误信息: {error_msg}"
        )
    
    def alert_data_collection_failed(self, error_msg: str):
        """数据采集失败告警"""
        self.send_alert(
            alert_type="data_collection_failed",
            title="数据采集失败",
            message=f"定时数据采集任务失败。\n错误信息: {error_msg}"
        )
    
    def alert_push_failed(self, match_info: str, error_msg: str):
        """推送失败告警"""
        self.send_alert(
            alert_type="push_failed",
            title="推送失败",
            message=f"比赛推送失败: {match_info}\n错误信息: {error_msg}"
        )
    
    def alert_system_error(self, component: str, error_msg: str):
        """系统错误告警"""
        self.send_alert(
            alert_type=f"system_error_{component}",
            title=f"系统组件异常: {component}",
            message=error_msg
        )
    
    def alert_disk_space_low(self, usage_percent: float):
        """磁盘空间不足告警"""
        self.send_alert(
            alert_type="disk_space_low",
            title="磁盘空间不足",
            message=f"当前磁盘使用率: {usage_percent}%\n建议清理日志或数据文件。"
        )
    
    def health_check_report(self, stats: Dict):
        """发送健康检查报告"""
        message = f"""
**系统运行正常**

📊 运行统计:
- 今日推送: {stats.get('today_push_count', 0)} 场
- 登录状态: {'✅ 正常' if stats.get('is_logged_in') else '❌ 未登录'}
- 日志大小: {stats.get('log_size_mb', 0)} MB
- 调度任务: {stats.get('scheduled_tasks', 0)} 场

_定期健康检查报告_
"""
        
        self.send_alert(
            alert_type="health_check",
            title="系统健康检查",
            message=message,
            force=False  # 健康检查也遵守冷却期
        )


# 创建全局实例
_alert_manager = None

def get_alert_manager(wecom_webhook: Optional[str] = None) -> AlertManager:
    """
    获取全局告警管理器实例
    
    Args:
        wecom_webhook: 企业微信Webhook地址
        
    Returns:
        AlertManager实例
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(wecom_webhook=wecom_webhook)
    return _alert_manager
