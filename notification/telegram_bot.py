"""Telegram消息推送"""
import requests
import logging
from typing import Dict, Optional
from pathlib import Path
import json

from utils.recommendation_formatter import format_recommendation_direction

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram消息推送器"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        初始化Telegram Bot
        
        Args:
            bot_token: Telegram Bot Token
            chat_id: 目标Chat ID
        """
        config_file = Path(__file__).parent.parent / "telegram_config.json"
        
        # 优先使用参数，否则从配置文件读取
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.bot_token = bot_token or config.get("bot_token")
                self.chat_id = chat_id or config.get("chat_id")
        else:
            self.bot_token = bot_token
            self.chat_id = chat_id
        
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def send_recommendation(self, recommendation_data: Dict) -> bool:
        """
        发送推荐消息
        
        Args:
            recommendation_data: 推荐数据，包含match_info和recommendation
            
        Returns:
            是否发送成功
        """
        try:
            if not self.bot_token or not self.chat_id:
                logger.warning("Telegram未配置，跳过推送")
                return False
            
            # 构造消息
            message = self._format_message(recommendation_data)
            
            # 发送消息
            return self._send_message(message)
            
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")
            return False
    
    def _format_message(self, data: Dict) -> str:
        """格式化推荐消息"""
        match_info = data.get("match_info", {})
        recommendation = data.get("recommendation", {})
        
        home_team = match_info.get('home_team') or match_info.get('home', '主队')
        away_team = match_info.get('away_team') or match_info.get('away', '客队')
        direction = format_recommendation_direction(recommendation, home_team, away_team)
        should_bet = recommendation.get("should_bet", False)
        confidence = recommendation.get("confidence", 0)
        reason = recommendation.get("reason", "")
        current_handicap_text = recommendation.get("current_handicap_text", "")
        
        status_text = "✅ 推荐下注" if should_bet else "⚠️ 暂不推荐"
        
        message_parts = [
            "⚽ <b>比赛推荐</b>",
            "",
            f"🏆 <b>{match_info.get('league', '未知联赛')}</b>",
            f"📅 {match_info.get('datetime', '未知时间')}",
            f"🆚 {home_team} vs {away_team}",
            "",
            f"{status_text}",
            f"🎯 <b>方向：{direction}</b>",
            f"🧮 盘口：{current_handicap_text or '暂无'}",
            f"📊 置信度: {confidence*100:.1f}%",
            "",
            f"💡 理由: {reason}",
        ]
        
        # 添加置信度条
        confidence_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
        message_parts.append(f"[{confidence_bar}]")
        
        return "\n".join(message_parts)
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """发送消息到Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                logger.info("Telegram消息发送成功")
                return True
            else:
                logger.error(f"Telegram API返回错误: {result}")
                return False
                
        except Exception as e:
            logger.error(f"发送请求失败: {e}")
            return False
    
    def send_test_message(self) -> bool:
        """发送测试消息"""
        test_message = "🤖 <b>自动推荐系统</b>\n\n✅ Telegram连接测试成功！"
        return self._send_message(test_message)
    
    @staticmethod
    def create_config(bot_token: str, chat_id: str):
        """创建配置文件"""
        config_file = Path(__file__).parent.parent / "telegram_config.json"
        config = {
            "bot_token": bot_token,
            "chat_id": chat_id
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Telegram配置已保存到: {config_file}")
