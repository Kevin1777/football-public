#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
X1推荐记录和审查系统

功能：
1. 记录每次推荐的详细信息
2. 定时审查推荐准确率
3. 生成可视化报告
4. 推送审查结果
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class RecommendationTracker:
    """推荐记录追踪器"""
    
    @staticmethod
    def calculate_handicap_result(home_score: int, away_score: int, 
                                   handicap: float, direction: str) -> str:
        """
        计算亚盘结果
        
        Args:
            home_score: 主队进球
            away_score: 客队进球
            handicap: 盘口值（从主队角度，负数=主让，正数=主受）
            direction: 推荐方向 'home' 或 'away'
        
        Returns:
            'win' - 全赢
            'half_win' - 赢半
            'push' - 走水
            'half_lose' - 输半
            'lose' - 全输
        """
        # 计算让球后的比分差
        adjusted_diff = (home_score - away_score) + handicap
        
        if direction == 'home':
            # 推荐主队，主队让球后需要赢
            if adjusted_diff > 0.25:
                return 'win'
            elif adjusted_diff > 0:
                return 'half_win'
            elif adjusted_diff == 0:
                return 'push'
            elif adjusted_diff >= -0.25:
                return 'half_lose'
            else:
                return 'lose'
        else:  # direction == 'away'
            # 推荐客队，主队让球后需要输（客队赢）
            if adjusted_diff < -0.25:
                return 'win'
            elif adjusted_diff < 0:
                return 'half_win'
            elif adjusted_diff == 0:
                return 'push'
            elif adjusted_diff <= 0.25:
                return 'half_lose'
            else:
                return 'lose'
    
    def __init__(self, db_path: str = "recommendation_tracker.db"):
        self.db_path = db_path
        # 🔥 确保数据库目录存在
        from pathlib import Path
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 推荐记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommend_time TEXT NOT NULL,
                    match_date TEXT NOT NULL,
                    match_time TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    league TEXT,
                    recommendation TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    confidence_level TEXT,
                    handicap TEXT,
                    funding_level TEXT,
                    flm_level TEXT,
                    spm_structure TEXT,
                    dpi_risk TEXT,
                    risk_flags TEXT,
                    sbre_triggered INTEGER DEFAULT 0,
                    json_file_path TEXT,
                    actual_home_score INTEGER,
                    actual_away_score INTEGER,
                    actual_result TEXT,
                    is_correct INTEGER,
                    reviewed INTEGER DEFAULT 0,
                    review_time TEXT,
                    notes TEXT
                )
            """)
            
            # 每日审查统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_date TEXT NOT NULL UNIQUE,
                    total_recommendations INTEGER,
                    reviewed INTEGER,
                    correct INTEGER,
                    wrong INTEGER,
                    draw INTEGER,
                    accuracy REAL,
                    high_confidence_accuracy REAL,
                    report_generated INTEGER DEFAULT 0,
                    report_path TEXT,
                    pushed INTEGER DEFAULT 0,
                    push_time TEXT
                )
            """)
            
            conn.commit()
            
            # 迁移：添加新的亚盘相关字段（如果不存在）
            self._migrate_add_handicap_fields(cursor, conn)
            
            logger.info("✅ 推荐追踪数据库初始化完成")
    
    def _migrate_add_handicap_fields(self, cursor, conn):
        """迁移：添加亚盘相关字段"""
        # 检查并添加 handicap_value 字段
        cursor.execute("PRAGMA table_info(recommendations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        new_columns = [
            ("handicap_value", "REAL"),      # 盘口数值
            ("direction", "TEXT"),            # 推荐方向 'home' 或 'away'
            ("handicap_result", "TEXT"),      # 亚盘结果
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE recommendations ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ 添加字段: {col_name}")
        
        # 检查并添加 daily_reviews 表的新字段
        cursor.execute("PRAGMA table_info(daily_reviews)")
        daily_columns = [row[1] for row in cursor.fetchall()]
        
        daily_new_columns = [
            ("win_count", "INTEGER DEFAULT 0"),
            ("half_win_count", "INTEGER DEFAULT 0"),
            ("push_count", "INTEGER DEFAULT 0"),
            ("half_lose_count", "INTEGER DEFAULT 0"),
            ("lose_count", "INTEGER DEFAULT 0"),
            ("accuracy_strict", "REAL"),
            ("accuracy_with_push", "REAL"),
        ]
        
        for col_name, col_type in daily_new_columns:
            if col_name not in daily_columns:
                cursor.execute(f"ALTER TABLE daily_reviews ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ 添加字段: {col_name}")
        
        conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def record_recommendation(self, recommendation_data: Dict) -> int:
        """
        记录推荐
        
        Args:
            recommendation_data: 推荐数据字典
            
        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 提取数据
            match_info = recommendation_data.get('match_info', {})
            rec = recommendation_data.get('recommendation', {})
            scores = recommendation_data.get('scores', {})
            funding = recommendation_data.get('funding_level', {})
            risk_control = recommendation_data.get('risk_control', {})
            sbre = recommendation_data.get('sbre', {})
            
            # 解析日期时间
            kickoff = match_info.get('kickoff', '')
            if ' ' in kickoff:
                match_date, match_time = kickoff.split(' ', 1)
            else:
                match_date = kickoff
                match_time = ''
            
            # 置信度等级
            confidence = rec.get('confidence', 0)
            if confidence >= 0.85:
                conf_level = 'high'
            elif confidence >= 0.60:
                conf_level = 'mid'
            else:
                conf_level = 'low'
            
            # 风控标记
            risk_flags_list = [k for k, v in risk_control.items() if v and k != 'messages']
            risk_flags_str = ','.join(risk_flags_list) if risk_flags_list else 'none'
            
            # 提取盘口数值
            handicap_str = rec.get('handicap', '')
            handicap_value = None
            if handicap_str:
                try:
                    # 尝试解析盘口数值，如 "-0.5", "+1", "0"
                    handicap_value = float(handicap_str.replace('+', ''))
                except (ValueError, AttributeError):
                    pass
            
            # 提取方向
            direction = rec.get('direction', 'none')
            
            cursor.execute("""
                INSERT INTO recommendations (
                    recommend_time, match_date, match_time,
                    home_team, away_team, league,
                    recommendation, confidence, confidence_level,
                    handicap, handicap_value, direction,
                    funding_level,
                    flm_level, spm_structure, dpi_risk,
                    risk_flags, sbre_triggered, json_file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                match_date,
                match_time,
                match_info.get('home', ''),
                match_info.get('away', ''),
                match_info.get('league', ''),
                rec.get('formatted', direction),  # 使用格式化字符串作为显示
                confidence,
                conf_level,
                handicap_str,
                handicap_value,
                direction,
                funding.get('level', ''),
                scores.get('FLM', {}).get('level', ''),
                scores.get('SPM', {}).get('structure', ''),
                scores.get('DPI', {}).get('risk_level', ''),
                risk_flags_str,
                1 if sbre.get('triggered') else 0,
                recommendation_data.get('json_file_path', '')
            ))
            
            rec_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"✅ 推荐已记录 ID={rec_id}: {match_info.get('home')} vs {match_info.get('away')}")
            
            return rec_id
    
    def get_pending_reviews(self, before_date: str = None) -> List[Dict]:
        """
        获取待审查的推荐
        
        Args:
            before_date: 在此日期之前的推荐（默认昨天）
            
        Returns:
            待审查推荐列表
        """
        if not before_date:
            before_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM recommendations
                WHERE reviewed = 0
                AND match_date <= ?
                AND recommendation != 'none'
                ORDER BY match_date, match_time
            """, (before_date,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def update_review(self, rec_id: int, actual_home_score: int, actual_away_score: int):
        """
        更新审查结果（使用亚盘计算逻辑）
        
        Args:
            rec_id: 推荐ID
            actual_home_score: 实际主队得分
            actual_away_score: 实际客队得分
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取推荐信息（包括盘口和方向）
            cursor.execute("""
                SELECT recommendation, handicap_value, direction 
                FROM recommendations WHERE id = ?
            """, (rec_id,))
            row = cursor.fetchone()
            if not row:
                return
            
            direction = row['direction']
            handicap_value = row['handicap_value']
            
            # 判断实际比分结果（用于显示）
            if actual_home_score > actual_away_score:
                actual_result = 'home'
            elif actual_away_score > actual_home_score:
                actual_result = 'away'
            else:
                actual_result = 'draw'
            
            # 使用亚盘计算逻辑判断结果
            handicap_result = None
            is_correct = 0
            
            if direction in ('home', 'away') and handicap_value is not None:
                handicap_result = self.calculate_handicap_result(
                    actual_home_score, actual_away_score, handicap_value, direction
                )
                # win 和 half_win 算正确
                is_correct = 1 if handicap_result in ('win', 'half_win') else 0
            
            # 更新数据库
            cursor.execute("""
                UPDATE recommendations
                SET actual_home_score = ?,
                    actual_away_score = ?,
                    actual_result = ?,
                    handicap_result = ?,
                    is_correct = ?,
                    reviewed = 1,
                    review_time = ?
                WHERE id = ?
            """, (
                actual_home_score,
                actual_away_score,
                actual_result,
                handicap_result,
                is_correct,
                datetime.now().isoformat(),
                rec_id
            ))
            
            conn.commit()
            
            result_text = "✅ 正确" if is_correct else "❌ 错误"
            result_detail = f"亚盘结果:{handicap_result}" if handicap_result else f"比分结果:{actual_result}"
            logger.info(f"{result_text}: {rec_id} - 方向{direction}, {result_detail}")
    
    def review_date(self, date: str) -> Dict:
        """
        审查某一天的所有推荐
        
        Args:
            date: 日期 (YYYY-MM-DD)
            
        Returns:
            审查统计结果
        """
        logger.info(f"🔍 开始审查 {date} 的推荐...")
        
        # 获取该日期的所有推荐
        pending = self.get_pending_reviews(date)
        
        if not pending:
            logger.info(f"⚠️ {date} 没有待审查的推荐")
            return {
                'date': date,
                'total': 0,
                'message': '没有待审查的推荐'
            }
        
        logger.info(f"📋 找到 {len(pending)} 条待审查推荐")
        
        reviewed_count = 0
        # 亚盘五种结果统计
        stats = {
            'win': 0,
            'half_win': 0,
            'push': 0,
            'half_lose': 0,
            'lose': 0,
            'no_handicap': 0  # 没有盘口数据的
        }
        
        # 逐个审查
        for rec in pending:
            # 尝试从JSON文件名提取比分
            json_path = rec.get('json_file_path', '')
            if json_path:
                score = self._extract_score_from_filename(Path(json_path).name)
                if score:
                    home_score, away_score = score
                    self.update_review(rec['id'], home_score, away_score)
                    reviewed_count += 1
        
        # 从数据库获取审查后的统计
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT handicap_result, COUNT(*) as cnt
                FROM recommendations
                WHERE match_date = ? AND reviewed = 1 AND direction IN ('home', 'away')
                GROUP BY handicap_result
            """, (date,))
            
            for row in cursor.fetchall():
                result = row['handicap_result']
                if result in stats:
                    stats[result] = row['cnt']
                elif result is None:
                    stats['no_handicap'] = row['cnt']
        
        # 计算两种准确率
        total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
        total_with_push = total_decided + stats['push']
        
        wins = stats['win'] + stats['half_win']
        accuracy_strict = wins / total_decided * 100 if total_decided > 0 else 0
        accuracy_with_push = (wins + stats['push']) / total_with_push * 100 if total_with_push > 0 else 0
        
        # 计算高置信度准确率
        high_conf_stats = self._get_confidence_stats(date, 'high')
        
        # 保存每日统计
        self._save_daily_review_v2(
            date, len(pending), reviewed_count, stats,
            accuracy_strict, accuracy_with_push, high_conf_stats['accuracy_strict']
        )
        
        logger.info(f"✅ 审查完成: {reviewed_count}/{len(pending)} 已审查")
        logger.info(f"   全赢/赢半/走水/输半/全输: {stats['win']}/{stats['half_win']}/{stats['push']}/{stats['half_lose']}/{stats['lose']}")
        logger.info(f"   准确率（不含走水）: {accuracy_strict:.1f}%")
        logger.info(f"   准确率（含走水）: {accuracy_with_push:.1f}%")
        
        return {
            'date': date,
            'total': len(pending),
            'reviewed': reviewed_count,
            'win': stats['win'],
            'half_win': stats['half_win'],
            'push': stats['push'],
            'half_lose': stats['half_lose'],
            'lose': stats['lose'],
            'accuracy_strict': accuracy_strict,
            'accuracy_with_push': accuracy_with_push,
            'high_confidence_accuracy': high_conf_stats['accuracy_strict'],
            'high_confidence_total': high_conf_stats['total']
        }
    
    def _extract_score_from_filename(self, filename: str) -> Optional[tuple]:
        """从文件名提取比分"""
        import re
        pattern = r'_(\d+)_(\d+)_\d{4}\.json$'
        match = re.search(pattern, filename)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None
    
    def _get_confidence_stats(self, date: str, confidence_level: str) -> Dict:
        """获取特定置信度等级的亚盘统计"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT handicap_result, COUNT(*) as cnt
                FROM recommendations
                WHERE match_date = ?
                AND confidence_level = ?
                AND reviewed = 1
                AND direction IN ('home', 'away')
                GROUP BY handicap_result
            """, (date, confidence_level))
            
            stats = {'win': 0, 'half_win': 0, 'push': 0, 'half_lose': 0, 'lose': 0}
            for row in cursor.fetchall():
                result = row['handicap_result']
                if result in stats:
                    stats[result] = row['cnt']
            
            total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
            total_with_push = total_decided + stats['push']
            wins = stats['win'] + stats['half_win']
            
            accuracy_strict = wins / total_decided * 100 if total_decided > 0 else 0
            accuracy_with_push = (wins + stats['push']) / total_with_push * 100 if total_with_push > 0 else 0
            
            return {
                'total': total_with_push,
                **stats,
                'accuracy_strict': accuracy_strict,
                'accuracy_with_push': accuracy_with_push
            }
    
    def _save_daily_review_v2(self, date: str, total: int, reviewed: int,
                              stats: Dict, accuracy_strict: float, 
                              accuracy_with_push: float, high_conf_accuracy: float):
        """保存每日审查统计（亚盘版本）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_reviews (
                    review_date, total_recommendations, reviewed,
                    win_count, half_win_count, push_count, half_lose_count, lose_count,
                    accuracy_strict, accuracy_with_push, high_confidence_accuracy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, total, reviewed,
                stats['win'], stats['half_win'], stats['push'], 
                stats['half_lose'], stats['lose'],
                accuracy_strict, accuracy_with_push, high_conf_accuracy
            ))
            
            conn.commit()
    
    def _save_daily_review(self, date: str, total: int, reviewed: int,
                          correct: int, wrong: int, draw: int,
                          accuracy: float, high_conf_accuracy: float):
        """保存每日审查统计（旧版本，保留兼容）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_reviews (
                    review_date, total_recommendations, reviewed,
                    correct, wrong, draw, accuracy, high_confidence_accuracy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, total, reviewed,
                correct, wrong, draw,
                accuracy, high_conf_accuracy
            ))
            
            conn.commit()
    
    def get_recent_reviews(self, days: int = 7) -> List[Dict]:
        """获取最近N天的审查统计"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM daily_reviews
                ORDER BY review_date DESC
                LIMIT ?
            """, (days,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def delete_all_recommendations(self) -> Dict:
        """
        删除所有推荐记录
        
        Returns:
            删除结果统计
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取删除前的统计
            cursor.execute("SELECT COUNT(*) as total FROM recommendations")
            total_recs = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM daily_reviews")
            total_reviews = cursor.fetchone()['total']
            
            # 删除所有推荐记录
            cursor.execute("DELETE FROM recommendations")
            
            # 删除所有每日审查统计
            cursor.execute("DELETE FROM daily_reviews")
            
            conn.commit()
            
            logger.info(f"✅ 已删除所有推荐记录: {total_recs} 条推荐, {total_reviews} 条每日统计")
            
            return {
                'deleted_recommendations': total_recs,
                'deleted_reviews': total_reviews,
                'message': f'成功删除 {total_recs} 条推荐记录和 {total_reviews} 条每日统计'
            }
    
    def get_statistics(self) -> Dict:
        """获取总体统计（亚盘版本）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 总体统计 - 亚盘五种结果
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN reviewed = 1 THEN 1 ELSE 0 END) as reviewed,
                    SUM(CASE WHEN handicap_result = 'win' THEN 1 ELSE 0 END) as win,
                    SUM(CASE WHEN handicap_result = 'half_win' THEN 1 ELSE 0 END) as half_win,
                    SUM(CASE WHEN handicap_result = 'push' THEN 1 ELSE 0 END) as push,
                    SUM(CASE WHEN handicap_result = 'half_lose' THEN 1 ELSE 0 END) as half_lose,
                    SUM(CASE WHEN handicap_result = 'lose' THEN 1 ELSE 0 END) as lose
                FROM recommendations
                WHERE direction IN ('home', 'away')
            """)
            
            row = cursor.fetchone()
            total = row['total'] or 0
            reviewed = row['reviewed'] or 0
            stats = {
                'win': row['win'] or 0,
                'half_win': row['half_win'] or 0,
                'push': row['push'] or 0,
                'half_lose': row['half_lose'] or 0,
                'lose': row['lose'] or 0
            }
            
            # 计算两种准确率
            total_decided = stats['win'] + stats['half_win'] + stats['half_lose'] + stats['lose']
            total_with_push = total_decided + stats['push']
            wins = stats['win'] + stats['half_win']
            
            accuracy_strict = wins / total_decided * 100 if total_decided > 0 else 0
            accuracy_with_push = (wins + stats['push']) / total_with_push * 100 if total_with_push > 0 else 0
            
            # 按置信度统计
            conf_stats = {}
            for level in ['high', 'mid', 'low']:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN handicap_result = 'win' THEN 1 ELSE 0 END) as win,
                        SUM(CASE WHEN handicap_result = 'half_win' THEN 1 ELSE 0 END) as half_win,
                        SUM(CASE WHEN handicap_result = 'push' THEN 1 ELSE 0 END) as push,
                        SUM(CASE WHEN handicap_result = 'half_lose' THEN 1 ELSE 0 END) as half_lose,
                        SUM(CASE WHEN handicap_result = 'lose' THEN 1 ELSE 0 END) as lose
                    FROM recommendations
                    WHERE confidence_level = ?
                    AND reviewed = 1
                    AND direction IN ('home', 'away')
                """, (level,))
                
                row = cursor.fetchone()
                level_stats = {
                    'win': row['win'] or 0,
                    'half_win': row['half_win'] or 0,
                    'push': row['push'] or 0,
                    'half_lose': row['half_lose'] or 0,
                    'lose': row['lose'] or 0
                }
                
                level_decided = level_stats['win'] + level_stats['half_win'] + level_stats['half_lose'] + level_stats['lose']
                level_with_push = level_decided + level_stats['push']
                level_wins = level_stats['win'] + level_stats['half_win']
                
                level_acc_strict = level_wins / level_decided * 100 if level_decided > 0 else 0
                level_acc_push = (level_wins + level_stats['push']) / level_with_push * 100 if level_with_push > 0 else 0
                
                conf_stats[level] = {
                    'total': row['total'] or 0,
                    **level_stats,
                    'accuracy_strict': level_acc_strict,
                    'accuracy_with_push': level_acc_push
                }
            
            return {
                'total': total,
                'reviewed': reviewed,
                **stats,
                'accuracy_strict': accuracy_strict,
                'accuracy_with_push': accuracy_with_push,
                'by_confidence': conf_stats
            }


# 全局实例
tracker = RecommendationTracker()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 审查昨天的推荐
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    result = tracker.review_date(yesterday)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
