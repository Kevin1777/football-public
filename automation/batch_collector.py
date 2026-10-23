"""批量采集历史数据"""
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import BifawClient
from services.lottery500_client import Lottery500Client  # 🆕 新增
from parser.html_parser import parse_bifa_html
from recommendation.analyzer import MatchAnalyzer
from automation.database import MatchDatabase

logger = logging.getLogger(__name__)


class BatchCollector:
    """批量数据采集器"""
    
    def __init__(self):
        self.bifaw_client = BifawClient()
        self.lottery500_client = Lottery500Client()  # 🆕 初始化500彩票网客户端
        self.analyzer = MatchAnalyzer()
        self.database = MatchDatabase()
    
    def collect_date_range(self, start_date: datetime, end_date: datetime, delay: int = 3):
        """
        采集指定日期范围的历史数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            delay: 每次请求间隔秒数
        """
        try:
            logger.info("\n" + "="*60)
            logger.info(f"批量采集: {start_date.date()} 到 {end_date.date()}")
            logger.info("="*60 + "\n")
            
            current_date = start_date
            total_collected = 0
            
            while current_date <= end_date:
                logger.info(f"\n📅 采集日期: {current_date.date()}")
                
                try:
                    # 🆕 获取该日期的完场比赛（包含HTML和元数据）
                    page_html, matches, metadata = self.bifaw_client.fetch_finished_matches(
                        target_date=current_date,
                        rows=200
                    )
                    
                    logger.info(f"找到 {len(matches)} 场比赛")
                    
                    # 🆕 保存目录（使用target_date）
                    save_dir = f"data/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}"
                    
                    # 🆕 Phase 3: 保存日期级别的整页数据（4个文件）
                    logger.info(f"\n{'='*60}")
                    logger.info(f"📥 保存日期级别整页数据")
                    logger.info(f"{'='*60}")
                    
                    # 1. 保存完场回查页面（已完成）
                    self._save_result_page(save_dir, page_html, matches, metadata, current_date)
                    
                    # 2. 保存500彩票网盘口数据（整页）
                    handicap_matches = self._save_500_handicap_page(save_dir, current_date)
                    
                    # 3. 保存必发网标盘指数（整页）
                    self._save_bifaw_standard_page(save_dir, current_date)
                    
                    # 🆕 Phase 4: 匹配有让球盘口的比赛
                    logger.info(f"\n{'='*60}")
                    logger.info(f"🔗 匹配有让球盘口的比赛")
                    logger.info(f"{'='*60}")
                    
                    matched_matches = self._match_handicap_to_bifaw(
                        handicap_matches=handicap_matches,
                        bifaw_matches=matches,
                        current_date=current_date
                    )
                    
                    logger.info(f"\n匹配结果：")
                    logger.info(f"  - 盘口比赛数: {len(handicap_matches) if handicap_matches else 0}")
                    logger.info(f"  - 必发比赛数: {len(matches)}")
                    logger.info(f"  - 匹配成功数: {len(matched_matches)}")
                    logger.info(f"  - 匹配成功率: {len(matched_matches)/len(handicap_matches)*100 if handicap_matches else 0:.1f}%")
                    
                    # 使用匹配后的比赛列表进行采集
                    matches = matched_matches if matched_matches else matches
                    
                    # 采集每场比赛的明细
                    for i, match in enumerate(matches, 1):
                        try:
                            logger.info(f"  [{i}/{len(matches)}] {match.get('label')}")
                            
                            # 检查是否已采集
                            if self._is_already_collected(match.get('match_id')):
                                logger.info(f"    ⏭️  已存在，跳过")
                                continue
                            
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
                                total_collected += 1
                                logger.info(f"    ✅ 已保存")
                            else:
                                logger.warning(f"    ⚠️  解析失败")
                            
                            # 延迟避免请求过快
                            time.sleep(delay)
                            
                        except Exception as e:
                            logger.error(f"    ❌ 失败: {e}")
                            continue
                    
                except Exception as e:
                    logger.error(f"采集 {current_date.date()} 失败: {e}")
                
                # 下一天
                current_date += timedelta(days=1)
            
            logger.info("\n" + "="*60)
            logger.info(f"✅ 批量采集完成！总计: {total_collected} 场比赛")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"批量采集失败: {e}")
    
    def collect_recent_days(self, days: int = 7, delay: int = 3):
        """
        采集最近N天的数据
        
        Args:
            days: 天数
            delay: 请求间隔
        """
        end_date = datetime.now() - timedelta(days=1)  # 昨天
        start_date = end_date - timedelta(days=days - 1)
        
        self.collect_date_range(start_date, end_date, delay)
    
    def _normalize_team_name(self, team_name):
        """
        归一化队名（用于提高匹配准确度）
        
        处理：
        1. 转小写
        2. 移除空格
        3. 移除常见后缀(FC, CF, United等)
        
        Args:
            team_name: 原始队名
            
        Returns:
            归一化后的队名
        """
        if not team_name:
            return ""
        
        # 转小写
        normalized = team_name.lower().strip()
        
        # 移除常见后缀和前缀
        suffixes = ['fc', 'cf', 'united', 'city', 'town', 'athletic', 'sports', '足球俱乐部']
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # 移除所有空格
        normalized = normalized.replace(' ', '').replace('-', '')
        
        return normalized
    
    def _is_time_match(self, time1, time2, tolerance_minutes=30):
        """
        验证两个时间是否匹配（允许一定误差）
        
        Args:
            time1: 时间1 (格式: "2025-10-25 19:30" 或 "19:30")
            time2: 时间2
            tolerance_minutes: 允许的误差分钟数
            
        Returns:
            bool: 是否匹配
        """
        from datetime import datetime, timedelta
        
        if not time1 or not time2:
            return False
        
        try:
            # 提取时间部分
            def extract_time(time_str):
                time_str = str(time_str).strip()
                # 如果包含日期，提取时间部分
                if ' ' in time_str:
                    time_part = time_str.split()[1]  # "2025-10-25 19:30" -> "19:30"
                else:
                    time_part = time_str  # "19:30"
                
                # 解析时间
                hour, minute = map(int, time_part.split(':')[:2])
                return hour * 60 + minute  # 转换为分钟数
            
            minutes1 = extract_time(time1)
            minutes2 = extract_time(time2)
            
            # 计算时间差
            diff = abs(minutes1 - minutes2)
            
            # 处理跨天情况（23:50 vs 00:10）
            if diff > 12 * 60:  # 超过12小时，可能跨天
                diff = 24 * 60 - diff
            
            return diff <= tolerance_minutes
            
        except Exception as e:
            logger.debug(f"时间匹配失败: {time1} vs {time2}, 错误: {e}")
            return False
    
    def _backup_if_exists(self, file_path):
        """
        备份功能已禁用 - 直接覆盖旧文件，不创建.bak备份
        
        Args:
            file_path: 文件路径
        """
        # 🔥 禁用备份功能，避免产生大量.bak文件
        return None
    
    def _save_result_page(self, save_dir: str, page_html, matches, metadata, query_date):
        """
        保存完场回查页面（必发网result.php）
        
        Args:
            save_dir: 保存目录（基于target_date）
            page_html: 完场回查页面HTML或原始响应
            matches: 比赛列表
            metadata: 元数据（包含跨日期统计）
            query_date: 查询日期
        """
        import os
        import json
        
        try:
            os.makedirs(save_dir, exist_ok=True)
            
            # 保存原始HTML/响应
            if page_html:
                html_path = os.path.join(save_dir, "完场回查.html")
                self._backup_if_exists(html_path)  # 🆕 备份旧文件
                with open(html_path, 'w', encoding='utf-8') as f:
                    # 如果是JSON响应，包装成HTML
                    if page_html.strip().startswith('{') or page_html.strip().startswith('['):
                        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>完场回查 - {query_date.strftime('%Y-%m-%d')}</title>
</head>
<body>
    <h1>完场回查数据</h1>
    <p>查询日期: {query_date.strftime('%Y-%m-%d')}</p>
    <p>数据来源: 必发网 result.php</p>
    <pre>{page_html}</pre>
</body>
</html>"""
                        f.write(html_content)
                    else:
                        # 如果已经是HTML，直接保存
                        f.write(page_html)
            
            # 保存解析后的JSON
            json_data = {
                'query_date': query_date.strftime('%Y-%m-%d'),
                'crawl_time': datetime.now().isoformat(),
                'total_matches': metadata.get('total_matches', len(matches)),
                'date_distribution': metadata.get('date_distribution', {}),
                'cross_date_count': metadata.get('cross_date_count', 0),
                'matches': matches
            }
            
            json_path = os.path.join(save_dir, "完场回查.json")
            self._backup_if_exists(json_path)  # 🆕 备份旧文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"\n✅ 完场回查页面已保存：{save_dir}")
            logger.info(f"   - HTML: {os.path.join(save_dir, '完场回查.html')}")
            logger.info(f"   - JSON: {json_path}")
            logger.info(f"   - 总比赛数: {len(matches)}")
            
            if metadata.get('cross_date_count', 0) > 0:
                logger.info(f"   ⚠️  包含 {metadata['cross_date_count']} 场次日比赛")
                for date, count in metadata.get('date_distribution', {}).items():
                    if date != query_date.strftime('%Y-%m-%d'):
                        logger.info(f"      - {date}: {count}场")
        
        except Exception as e:
            logger.error(f"保存完场回查页面失败: {e}")
    
    def _save_500_handicap_page(self, save_dir: str, query_date: datetime):
        """
        保存500彩票网盘口数据整页，并标记有让球盘口的比赛
        
        Args:
            save_dir: 保存目录
            query_date: 查询日期
            
        Returns:
            list: 有让球盘口的比赛列表（包含标记）
        """
        import os
        import json
        
        try:
            os.makedirs(save_dir, exist_ok=True)
            
            logger.info(f"\n📥 获取500彩票网盘口数据...")
            date_str = query_date.strftime('%Y-%m-%d')
            
            # 获取盘口数据（包含HTML）
            handicaps = self.lottery500_client.batch_fetch_handicaps_by_date(
                match_date=date_str,
                use_cache=False  # 不使用缓存，确保获取最新数据
            )
            
            # 🆕 筛选有让球盘口的比赛并标记
            handicap_matches = []
            if handicaps:
                for match_key, handicap_data in handicaps.items():
                    # 检查是否有有效的让球盘口
                    has_handicap = False
                    current_handicap = handicap_data.get('current_handicap')
                    initial_handicap = handicap_data.get('initial_handicap')
                    
                    if current_handicap and current_handicap != 0:
                        has_handicap = True
                    elif initial_handicap and initial_handicap != 0:
                        has_handicap = True
                    
                    if has_handicap:
                        # 标记为有让球盘口的比赛
                        match_info = {
                            'match_key': match_key,
                            'home_team': handicap_data.get('home_team'),
                            'away_team': handicap_data.get('away_team'),
                            'kickoff': handicap_data.get('kickoff'),
                            'current_handicap': current_handicap,
                            'initial_handicap': initial_handicap,
                            'has_handicap': True,  # 🆕 标记
                            'handicap_data': handicap_data
                        }
                        handicap_matches.append(match_info)
                
                # 保存JSON（包含标记）
                json_path = os.path.join(save_dir, "盘口数据.json")
                self._backup_if_exists(json_path)  # 🆕 备份旧文件
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'query_date': date_str,
                        'crawl_time': datetime.now().isoformat(),
                        'total_matches': len(handicaps),
                        'matches_with_handicap': len(handicap_matches),  # 🆕 有盘口的比赛数
                        'handicaps': handicaps,
                        'handicap_matches': handicap_matches  # 🆕 有盘口的比赛列表
                    }, f, ensure_ascii=False, indent=2)
                
                logger.info(f"✅ 盘口数据已保存：")
                logger.info(f"   - HTML: {os.path.join(save_dir, '盘口数据.html')}")
                logger.info(f"   - JSON: {json_path}")
                logger.info(f"   - 总比赛数: {len(handicaps)}")
                logger.info(f"   - 有让球盘口: {len(handicap_matches)} 场 🎯")
                
                return handicap_matches
            else:
                logger.warning(f"⚠️  未获取到盘口数据")
                return []
        
        except Exception as e:
            logger.error(f"保存盘口数据失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _match_handicap_to_bifaw(self, handicap_matches, bifaw_matches, current_date):
        """
        多维度匹配：有让球盘口的比赛到必发网比赛
        
        匹配策略：
        1. 队名相似度（主要）
        2. 开球时间验证（辅助）
        3. 比分验证（可选）
        
        Args:
            handicap_matches: 500彩票网有让球盘口的比赛列表
            bifaw_matches: 必发网完场比赛列表
            current_date: 当前日期
            
        Returns:
            list: 匹配成功的必发网比赛列表（添加了盘口信息）
        """
        import os
        import json
        from difflib import SequenceMatcher
        from datetime import datetime, timedelta
        
        if not handicap_matches:
            logger.warning("没有找到有让球盘口的比赛")
            return bifaw_matches
        
        matched_matches = []
        unmatched_handicap = []
        duplicate_matches = []  # 🆕 记录重复匹配
        
        logger.info(f"\n🔗 开始多维度匹配...")
        logger.info(f"   匹配策略：队名相似度(70%) + 时间验证(±30分钟)")
        
        for handicap in handicap_matches:
            h_home = handicap.get('home_team', '').strip()
            h_away = handicap.get('away_team', '').strip()
            h_kickoff = handicap.get('kickoff', '')
            
            best_match = None
            best_score = 0
            match_reason = ""
            
            for bifaw in bifaw_matches:
                b_home = bifaw.get('home_team', '').strip()
                b_away = bifaw.get('away_team', '').strip()
                b_kickoff = bifaw.get('kickoff', '')
                
                # 🆕 1. 计算队名相似度（归一化处理）
                h_home_norm = self._normalize_team_name(h_home)
                h_away_norm = self._normalize_team_name(h_away)
                b_home_norm = self._normalize_team_name(b_home)
                b_away_norm = self._normalize_team_name(b_away)
                
                home_similarity = SequenceMatcher(None, h_home_norm, b_home_norm).ratio()
                away_similarity = SequenceMatcher(None, h_away_norm, b_away_norm).ratio()
                
                # 综合相似度
                total_similarity = (home_similarity + away_similarity) / 2
                
                # 🆕 2. 验证开球时间（允许±30分钟误差）
                time_match = self._is_time_match(h_kickoff, b_kickoff, tolerance_minutes=30)
                
                # 🆕 3. 综合评分
                # 队名相似度权重80%，时间匹配权重20%
                final_score = total_similarity * 0.8 + (0.2 if time_match else 0)
                
                # 相似度阈值：70%
                if final_score > 0.7:
                    if final_score > best_score:
                        best_score = final_score
                        best_match = bifaw
                        match_reason = f"队名:{total_similarity:.0%}, 时间:{'✓' if time_match else '✗'}"
            
            if best_match:
                # 🆕 检查是否已经匹配过（防止重复匹配）
                if best_match in matched_matches:
                    duplicate_matches.append({
                        'handicap': handicap,
                        'bifaw': best_match,
                        'score': best_score
                    })
                    logger.warning(f"  ⚠️  重复匹配: {h_home} vs {h_away} -> {best_match.get('home_team')} (已匹配过)")
                    continue
                
                # 匹配成功，添加盘口信息到必发网比赛
                best_match['has_handicap'] = True
                best_match['handicap_info'] = {
                    'current_handicap': handicap.get('current_handicap'),
                    'initial_handicap': handicap.get('initial_handicap'),
                    'match_key': handicap.get('match_key'),
                    'similarity': best_score,
                    'match_reason': match_reason,  # 🆕 记录匹配原因
                    'handicap_home': h_home,  # 🆕 记录500彩票网的队名
                    'handicap_away': h_away
                }
                
                matched_matches.append(best_match)
                
                logger.info(f"  ✅ 匹配成功: {h_home} vs {h_away}")
                logger.info(f"      → {best_match.get('home_team')} vs {best_match.get('away_team')}")
                logger.info(f"      评分: {best_score:.2%} ({match_reason})")
            else:
                unmatched_handicap.append(handicap)
                logger.warning(f"  ❌ 未匹配: {h_home} vs {h_away} (开球时间: {h_kickoff})")
        
        # 🆕 统计信息
        match_rate = len(matched_matches) / len(handicap_matches) * 100 if handicap_matches else 0
        
        # 🆕 按匹配质量分类
        high_quality = [m for m in matched_matches if m.get('handicap_info', {}).get('similarity', 0) >= 0.9]
        medium_quality = [m for m in matched_matches if 0.8 <= m.get('handicap_info', {}).get('similarity', 0) < 0.9]
        low_quality = [m for m in matched_matches if m.get('handicap_info', {}).get('similarity', 0) < 0.8]
        
        # 保存匹配结果
        save_dir = f"data/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}"
        match_result_path = os.path.join(save_dir, "匹配结果.json")
        try:
            self._backup_if_exists(match_result_path)  # 🆕 备份旧文件
            with open(match_result_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'match_date': current_date.strftime('%Y-%m-%d'),
                    'match_time': datetime.now().isoformat(),
                    'summary': {
                        'total_handicap_matches': len(handicap_matches),
                        'total_bifaw_matches': len(bifaw_matches),
                        'matched_count': len(matched_matches),
                        'unmatched_count': len(unmatched_handicap),
                        'duplicate_count': len(duplicate_matches),  # 🆕
                        'match_rate': f"{match_rate:.1f}%",
                        'quality': {  # 🆕 匹配质量统计
                            'high': len(high_quality),  # ≥90%
                            'medium': len(medium_quality),  # 80-90%
                            'low': len(low_quality)  # <80%
                        }
                    },
                    'matched_matches': [
                        {
                            'match_id': m.get('match_id'),
                            'bifaw_home': m.get('home_team'),
                            'bifaw_away': m.get('away_team'),
                            'handicap_home': m.get('handicap_info', {}).get('handicap_home'),  # 🆕
                            'handicap_away': m.get('handicap_info', {}).get('handicap_away'),  # 🆕
                            'current_handicap': m.get('handicap_info', {}).get('current_handicap'),
                            'initial_handicap': m.get('handicap_info', {}).get('initial_handicap'),
                            'match_score': m.get('handicap_info', {}).get('similarity'),
                            'match_reason': m.get('handicap_info', {}).get('match_reason'),  # 🆕
                            'quality': 'high' if m.get('handicap_info', {}).get('similarity', 0) >= 0.9 else 
                                      'medium' if m.get('handicap_info', {}).get('similarity', 0) >= 0.8 else 'low'  # 🆕
                        } for m in matched_matches
                    ],
                    'unmatched_handicap': [
                        {
                            'home_team': h.get('home_team'),
                            'away_team': h.get('away_team'),
                            'kickoff': h.get('kickoff'),
                            'current_handicap': h.get('current_handicap'),
                            'initial_handicap': h.get('initial_handicap')
                        } for h in unmatched_handicap
                    ],
                    'duplicate_matches': [  # 🆕 重复匹配记录
                        {
                            'handicap_home': d['handicap'].get('home_team'),
                            'handicap_away': d['handicap'].get('away_team'),
                            'bifaw_home': d['bifaw'].get('home_team'),
                            'bifaw_away': d['bifaw'].get('away_team'),
                            'score': d['score']
                        } for d in duplicate_matches
                    ]
                }, f, ensure_ascii=False, indent=2)
            
            # 🆕 详细日志
            logger.info(f"\n✅ 匹配结果已保存: {match_result_path}")
            logger.info(f"   匹配统计:")
            logger.info(f"     - 总计: {len(matched_matches)}/{len(handicap_matches)} ({match_rate:.1f}%)")
            logger.info(f"     - 高质量(≥90%): {len(high_quality)}")
            logger.info(f"     - 中等质量(80-90%): {len(medium_quality)}")
            logger.info(f"     - 低质量(<80%): {len(low_quality)}")
            if duplicate_matches:
                logger.warning(f"     - ⚠️  重复匹配: {len(duplicate_matches)}")
            if unmatched_handicap:
                logger.warning(f"     - ❌ 未匹配: {len(unmatched_handicap)}")
                
        except Exception as e:
            logger.error(f"保存匹配结果失败: {e}")
        
        return matched_matches
    
    def _save_bifaw_standard_page(self, save_dir: str, query_date: datetime):
        """
        保存必发网标盘指数整页
        
        Args:
            save_dir: 保存目录
            query_date: 查询日期
        """
        import os
        import json
        
        try:
            os.makedirs(save_dir, exist_ok=True)
            
            logger.info(f"\n📥 获取必发网标盘指数...")
            
            # 使用fetch_match_list_v2获取标盘场次
            # 注意：这个API返回的是多日数据，我们需要筛选当天的
            standard_matches = self.bifaw_client.fetch_match_list_v2(
                rows=200,
                days=1,  # 查询1天
                future_days=0,
                force_refresh=True
            )
            
            # 筛选查询日期的比赛
            date_str = query_date.strftime('%Y-%m-%d')
            filtered_matches = []
            for match in standard_matches:
                match_time = match.get('match_time', '') or match.get('kickoff', '')
                if date_str in match_time:
                    filtered_matches.append(match)
            
            # 保存JSON
            if filtered_matches or standard_matches:
                json_data = {
                    'query_date': date_str,
                    'crawl_time': datetime.now().isoformat(),
                    'total_matches': len(filtered_matches),
                    'all_matches_count': len(standard_matches),
                    'matches': filtered_matches
                }
                
                json_path = os.path.join(save_dir, "标盘指数.json")
                self._backup_if_exists(json_path)  # 🆕 备份旧文件
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                
                # 尝试保存HTML（如果有）
                # 注意：fetch_match_list_v2不返回HTML，这里我们记录一下
                html_path = os.path.join(save_dir, "标盘指数.html")
                self._backup_if_exists(html_path)  # 🆕 备份旧文件
                html_note = f"""
<!-- 标盘指数数据 -->
<!-- 查询日期: {date_str} -->
<!-- 总比赛数: {len(filtered_matches)} -->
<!-- 数据来源: 必发网API (serveodds接口) -->
<!-- 注意: 此HTML为占位文件，实际数据在JSON中 -->
<html>
<head><meta charset="utf-8"><title>标盘指数 - {date_str}</title></head>
<body>
<h1>标盘指数数据</h1>
<p>查询日期: {date_str}</p>
<p>比赛数量: {len(filtered_matches)}</p>
<p>详细数据请查看: 标盘指数.json</p>
</body>
</html>
"""
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_note)
                
                logger.info(f"✅ 标盘指数已保存：")
                logger.info(f"   - HTML: {html_path} (占位文件)")
                logger.info(f"   - JSON: {json_path}")
                logger.info(f"   - 比赛数: {len(filtered_matches)} (筛选后)")
                logger.info(f"   - 总数: {len(standard_matches)} (API返回)")
            else:
                logger.warning(f"⚠️  未获取到标盘指数数据")
        
        except Exception as e:
            logger.error(f"保存标盘指数失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _is_already_collected(self, match_id: str) -> bool:
        """检查比赛是否已采集"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.database.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM matches WHERE match_id = ?', (match_id,))
            count = cursor.fetchone()[0]
            
            conn.close()
            
            return count > 0
            
        except:
            return False


def main():
    """主函数"""
    import argparse
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('batch_collection.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='批量采集历史数据')
    parser.add_argument('--days', type=int, default=7, help='采集最近N天的数据（默认7天）')
    parser.add_argument('--delay', type=int, default=3, help='请求间隔秒数（默认3秒）')
    
    args = parser.parse_args()
    
    # 执行采集
    collector = BatchCollector()
    collector.collect_recent_days(days=args.days, delay=args.delay)


if __name__ == "__main__":
    main()
