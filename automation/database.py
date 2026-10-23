"""数据库管理模块"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class MatchDatabase:
    """比赛数据库管理器"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "match_data.db"
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建比赛表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    match_id TEXT PRIMARY KEY,
                    league TEXT,
                    kickoff TEXT,
                    home_team TEXT,
                    away_team TEXT,
                    score TEXT,
                    detail_url TEXT,
                    collected_at TEXT,
                    match_type TEXT
                )
            ''')
            
            # 创建交易数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    data_json TEXT,
                    collected_at TEXT,
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
            ''')
            
            # 创建分析结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    recommendation_direction TEXT,
                    confidence REAL,
                    reason TEXT,
                    analysis_json TEXT,
                    analyzed_at TEXT,
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
            ''')
            
            # 创建推送记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT,
                    sent_at TEXT,
                    success INTEGER,
                    message TEXT,
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_match_data(self, match: Dict, trade_df: pd.DataFrame, analysis: Dict):
        """
        保存比赛数据
        
        Args:
            match: 比赛信息
            trade_df: 交易明细DataFrame
            analysis: 分析结果
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            match_id = match.get('match_id')
            now = datetime.now().isoformat()
            
            # 1. 保存比赛信息
            cursor.execute('''
                INSERT OR REPLACE INTO matches 
                (match_id, league, kickoff, home_team, away_team, score, detail_url, collected_at, match_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_id,
                match.get('league'),
                match.get('kickoff'),
                match.get('home'),
                match.get('away'),
                match.get('score'),
                match.get('detail_url'),
                now,
                match.get('type', 'unknown')
            ))
            
            # 2. 保存交易数据
            trade_json = trade_df.to_json(orient='records', force_ascii=False)
            cursor.execute('''
                INSERT INTO trade_data (match_id, data_json, collected_at)
                VALUES (?, ?, ?)
            ''', (match_id, trade_json, now))
            
            # 3. 保存分析结果
            recommendation = analysis.get('recommendation', {})
            cursor.execute('''
                INSERT INTO analysis_results 
                (match_id, recommendation_direction, confidence, reason, analysis_json, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                match_id,
                recommendation.get('direction'),
                recommendation.get('confidence', 0),
                recommendation.get('reason'),
                json.dumps(analysis, ensure_ascii=False),
                now
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"数据已保存: {match.get('label')}")
            
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def log_notification(self, match_id: str, success: bool, message: str = ""):
        """记录推送日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO notifications (match_id, sent_at, success, message)
                VALUES (?, ?, ?, ?)
            ''', (match_id, datetime.now().isoformat(), 1 if success else 0, message))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"记录推送日志失败: {e}")
    
    def get_historical_data(self, limit: int = 1000) -> list:
        """获取历史数据用于训练"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT m.*, a.analysis_json
                FROM matches m
                LEFT JOIN analysis_results a ON m.match_id = a.match_id
                WHERE m.score IS NOT NULL
                ORDER BY m.kickoff DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return rows
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 统计总比赛数
            cursor.execute('SELECT COUNT(*) FROM matches')
            total_matches = cursor.fetchone()[0]
            
            # 统计已完场比赛数
            cursor.execute('SELECT COUNT(*) FROM matches WHERE score IS NOT NULL')
            finished_matches = cursor.fetchone()[0]
            
            # 统计推送数
            cursor.execute('SELECT COUNT(*) FROM notifications WHERE success = 1')
            successful_notifications = cursor.fetchone()[0]
            
            # 统计推荐准确率（需要验证逻辑）
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN recommendation_direction = '主胜' AND score LIKE '%-%' THEN 1 ELSE 0 END) as correct
                FROM analysis_results a
                JOIN matches m ON a.match_id = m.match_id
                WHERE m.score IS NOT NULL AND a.recommendation_direction != '不推荐'
            ''')
            accuracy_data = cursor.fetchone()
            
            conn.close()
            
            return {
                "total_matches": total_matches,
                "finished_matches": finished_matches,
                "successful_notifications": successful_notifications,
                "recommendations_made": accuracy_data[0] if accuracy_data else 0,
                "database_path": str(self.db_path)
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
