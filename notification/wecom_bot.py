"""企业微信机器人消息推送"""
import requests
import logging
import json
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime

from utils.recommendation_formatter import format_recommendation_direction

logger = logging.getLogger(__name__)


class WeComNotifier:
    """企业微信机器人推送器"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        初始化企业微信机器人
        
        Args:
            webhook_url: 企业微信机器人Webhook地址
        """
        # 尝试多个可能的配置文件路径
        possible_paths = [
            Path(__file__).parent.parent / "config" / "wecom_config.json",
            Path(__file__).parent.parent / "wecom_config.json",
        ]
        
        config_file = None
        for p in possible_paths:
            if p.exists():
                config_file = p
                break
        
        # 优先使用参数，否则从配置文件读取
        if config_file and config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.webhook_url = webhook_url or config.get("webhook_url")
        else:
            self.webhook_url = webhook_url
    
    def send_recommendation(self, recommendation_data: Dict) -> bool:
        """
        发送推荐消息
        
        Args:
            recommendation_data: 推荐数据，包含match_info和recommendation
            
        Returns:
            是否发送成功
        """
        try:
            if not self.webhook_url:
                logger.warning("企业微信机器人未配置，跳过推送")
                return False
            
            # 构造消息
            message = self._format_markdown_message(recommendation_data)
            
            # 发送消息
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"发送企业微信消息失败: {e}")
            return False
    
    def _format_markdown_message(self, data: Dict) -> Dict:
        """格式化为Markdown消息"""
        match_info = data.get("match_info", {})
        recommendation = data.get("recommendation", {})
        
        # 获取推荐结果
        should_bet = recommendation.get("should_bet", False)
        confidence = recommendation.get("confidence", 0)
        reason = recommendation.get("reason", "")
        tier = recommendation.get("tier", "")
        # 🔥 修复：version在data顶层，不在recommendation内
        version = data.get("version") or recommendation.get("version", "V7")
        
        # 🔥 格式化推荐方向为 "主队+0.25" 格式（使用公共工具函数）
        home_team = match_info.get('home_team', '主队')
        away_team = match_info.get('away_team', '客队')
        direction = format_recommendation_direction(recommendation, home_team, away_team)
        
        # 盘口信息
        current_handicap_text = recommendation.get("current_handicap_text", "")
        handicap_trend = recommendation.get("handicap_trend", "")
        handicap_change = recommendation.get("handicap_change", 0)
        
        # 状态标识
        if should_bet:
            status_emoji = "✅"
            status_text = "**推荐下注**"
        else:
            status_emoji = "❌"
            status_text = "**不推荐**"
        
        # 置信度条
        confidence_percent = int(confidence * 100)
        confidence_bar = "🟩" * (confidence_percent // 10) + "⬜" * (10 - confidence_percent // 10)
        
        # 构造Markdown内容
        content_parts = [
            f"### {status_emoji} 比赛推荐 - {version}",
            "",
            f"**🏆 联赛：** {match_info.get('league', '未知联赛')}",
            f"**📅 时间：** {match_info.get('datetime', '未知时间')}",
            f"**🆚 对阵：** {home_team} vs {away_team}",
            "",
            f"**{status_text}**",
        ]
        
        if should_bet:
            content_parts.extend([
                f"**🎯 推荐方向：** <font color=\"info\">{direction}</font>",
                f"**💎 质量档位：** {tier}" if tier else "",
            ])
        else:
            # 不推荐时也显示推荐方向
            content_parts.extend([
                f"**🎯 推荐方向：** {direction}",
            ])
        
        content_parts.extend([
            f"**📊 置信度：** {confidence_percent}%",
            f"{confidence_bar}",
            "",
            f"**📈 盘口详情：**",
            f"> 即时盘口：{current_handicap_text}",
            f"> 盘口趋势：{handicap_trend} ({handicap_change:+.2f})",
            "",
            f"**💡 推荐理由：**",
            f"> {reason}",
        ])
        
        # 过滤空行
        content = "\n".join([line for line in content_parts if line or line == ""])
        
        # 构造企业微信Markdown消息格式
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        return message
    
    def _format_text_message(self, data: Dict) -> Dict:
        """格式化为纯文本消息（备选方案）"""
        match_info = data.get("match_info", {})
        recommendation = data.get("recommendation", {})
        
        should_bet = recommendation.get("should_bet", False)
        direction = format_recommendation_direction(
            recommendation,
            match_info.get('home_team', '主队'),
            match_info.get('away_team', '客队')
        )
        confidence = recommendation.get("confidence", 0)
        reason = recommendation.get("reason", "")
        # 🔥 修复：version在data顶层，不在recommendation内
        version = data.get("version") or recommendation.get("version", "V7")
        
        status = "✅ 推荐下注" if should_bet else "❌ 不推荐"
        
        # 构造文本内容
        content = f"""⚽ 比赛推荐 - {version}

🏆 联赛：{match_info.get('league', '未知联赛')}
📅 时间：{match_info.get('datetime', '未知时间')}
🆚 对阵：{match_info.get('home_team', '主队')} vs {match_info.get('away_team', '客队')}

{status}
🎯 推荐方向：{direction}
📊 置信度：{confidence*100:.1f}%

💡 理由：{reason}
"""
        
        # 构造企业微信文本消息格式
        message = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        return message
    
    def _send_message(self, message: Dict) -> bool:
        """发送消息到企业微信"""
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("errcode") == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信API返回错误: {result}")
                return False
                
        except Exception as e:
            logger.error(f"发送请求失败: {e}")
            return False
    
    def send_test_message(self) -> bool:
        """发送测试消息"""
        test_message = {
            "msgtype": "markdown",
            "markdown": {
                "content": "### 🤖 自动推荐系统\n\n**✅ 企业微信连接测试成功！**\n\n系统已就绪，将为您推送比赛推荐。"
            }
        }
        return self._send_message(test_message)
    
    def send_summary(self, summary_data: Dict) -> bool:
        """
        发送每日汇总消息
        
        Args:
            summary_data: 汇总数据 {
                'date': 日期,
                'total_matches': 总场次,
                'recommended': 推荐场次,
                'win_rate': 胜率,
                'roi': ROI
            }
        """
        try:
            if not self.webhook_url:
                logger.warning("企业微信机器人未配置，跳过推送")
                return False
            
            date = summary_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            total = summary_data.get('total_matches', 0)
            recommended = summary_data.get('recommended', 0)
            win_rate = summary_data.get('win_rate', 0)
            roi = summary_data.get('roi', 0)
            
            content = f"""### 📊 每日推荐汇总

**📅 日期：** {date}

**⚽ 比赛统计：**
> 总场次：{total}
> 推荐场次：{recommended}

**📈 收益表现：**
> 胜率：{win_rate:.1f}%
> ROI：{roi:+.1f}%

祝您投注顺利！🎯
"""
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
            
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"发送汇总消息失败: {e}")
            return False
    
    @staticmethod
    def create_config(webhook_url: str):
        """创建配置文件"""
        config_file = Path(__file__).parent.parent / "wecom_config.json"
        config = {
            "webhook_url": webhook_url
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"企业微信配置已保存到: {config_file}")
        return True


# 测试函数
def test_wecom_bot():
    """测试企业微信机器人"""
    print("=" * 60)
    print("企业微信机器人测试")
    print("=" * 60)
    
    # 从配置读取
    notifier = WeComNotifier()
    
    if not notifier.webhook_url:
        print("\n请先配置企业微信机器人Webhook URL")
        webhook_url = input("请输入Webhook URL: ").strip()
        
        if webhook_url:
            WeComNotifier.create_config(webhook_url)
            notifier = WeComNotifier(webhook_url)
        else:
            print("❌ 未输入Webhook URL，退出测试")
            return
    
    # 发送测试消息
    print("\n1. 测试基本连接...")
    if notifier.send_test_message():
        print("✅ 基本连接测试通过")
    else:
        print("❌ 基本连接测试失败")
        return
    
    # 测试推荐消息
    print("\n2. 测试推荐消息...")
    test_recommendation = {
        "version": "X1-JSON-V1.0",  # 🔥 版本号在顶层
        "match_info": {
            "league": "英超",
            "datetime": "2025-11-23 22:00",
            "home_team": "曼城",
            "away_team": "利物浦"
        },
        "recommendation": {
            "should_bet": True,
            "bet_description": "主队 -1.5",
            "confidence": 0.75,
            "reason": "✅ 匹配⭐ 高质量\n✅ 成交量≥250行\n✅ 基础置信度≥75%\n✅ 最终置信度: 83.0%",
            "tier": "⭐ 高质量",
            "current_handicap_text": "-1.5",
            "handicap_trend": "升盘",
            "handicap_change": -0.25
        }
    }
    
    if notifier.send_recommendation(test_recommendation):
        print("✅ 推荐消息测试通过")
    else:
        print("❌ 推荐消息测试失败")
        return
    
    # 测试汇总消息
    print("\n3. 测试汇总消息...")
    test_summary = {
        "date": "2025-11-23",
        "total_matches": 15,
        "recommended": 5,
        "win_rate": 68.0,
        "roi": 32.5
    }
    
    if notifier.send_summary(test_summary):
        print("✅ 汇总消息测试通过")
    else:
        print("❌ 汇总消息测试失败")
    
    print("\n" + "=" * 60)
    print("测试完成！请检查企业微信群组收到的消息。")
    print("=" * 60)


if __name__ == "__main__":
    test_wecom_bot()
