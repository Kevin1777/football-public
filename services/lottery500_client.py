"""
500彩票网数据获取服务 - 获取让球盘口数据
"""
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    计算两个字符串的编辑距离（Levenshtein Distance）
    
    Args:
        s1: 字符串1
        s2: 字符串2
    
    Returns:
        编辑距离（需要多少次插入、删除、替换操作才能将s1转换为s2）
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # 插入、删除、替换的代价都是1
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    计算两个字符串的相似度（0-1之间，1表示完全相同）
    
    Args:
        s1: 字符串1
        s2: 字符串2
    
    Returns:
        相似度得分
    """
    if not s1 or not s2:
        return 0.0
    
    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    
    if max_len == 0:
        return 1.0
    
    return 1.0 - (distance / max_len)


class Lottery500Client:
    """500彩票网数据客户端"""
    
    def __init__(self, data_dir: str = "data"):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://odds.500.com/',
        })
        
        # 🔥 存储目录配置（智能处理绝对路径和相对路径）
        data_path = Path(data_dir)
        if data_path.is_absolute():
            # 如果是绝对路径，直接使用
            self.data_dir = data_path
        else:
            # 如果是相对路径，转换为绝对路径（相对于当前工作目录）
            self.data_dir = data_path.resolve()
        
        self.handicaps_dir = self.data_dir / "handicaps"
        self.details_dir = self.data_dir / "details"
        self.cache_dir = self.data_dir / "cache"
        
        # 确保目录存在
        self.handicaps_dir.mkdir(parents=True, exist_ok=True)
        self.details_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 盘口映射表 - 将中文盘口转换为数值
        self.handicap_map = {
            # 平手盘
            '平手': 0.0,
            '平': 0.0,
            '0': 0.0,
            
            # 平/半
            '平/半': 0.25,
            '平半': 0.25,
            '平手/半球': 0.25,  # 🔥 修复：补充完整格式
            '0/0.5': 0.25,
            
            # 半球
            '半球': 0.5,
            '半': 0.5,
            '0.5': 0.5,
            
            # 半/一
            '半/一': 0.75,
            '半一': 0.75,
            '半球/一球': 0.75,  # 🔥 补充完整格式
            '0.5/1': 0.75,
            
            # 一球
            '一球': 1.0,
            '一': 1.0,
            '1': 1.0,
            
            # 一/球半
            '一/球半': 1.25,
            '一球/球半': 1.25,  # 🔥 补充
            '一球半': 1.25,
            '一球/一球半': 1.25,  # 🔥 补充完整格式
            '1/1.5': 1.25,
            
            # 球半
            '球半': 1.5,
            '1.5': 1.5,
            
            # 球半/两
            '球半/两': 1.75,
            '球半/两球': 1.75,  # 🔥 补充
            '球半两': 1.75,
            '一球半/两球': 1.75,  # 🔥 补充完整格式
            '1.5/2': 1.75,
            
            # 两球
            '两球': 2.0,
            '两': 2.0,
            '2': 2.0,
            
            # 两/两球半
            '两/两球半': 2.25,
            '两球/两球半': 2.25,  # 🔥 补充（用户发现的bug）
            '两两球半': 2.25,
            '2/2.5': 2.25,
            
            # 两球半
            '两球半': 2.5,
            '2.5': 2.5,
            
            # 两球半/三
            '两球半/三': 2.75,
            '两球半/三球': 2.75,  # 🔥 补充
            '两球半三': 2.75,
            '2.5/3': 2.75,
            
            # 三球
            '三球': 3.0,
            '三': 3.0,
            '3': 3.0,
            
            # 三/三球半
            '三/三球半': 3.25,
            '三球/三球半': 3.25,  # 🔥 补充
            '三三球半': 3.25,
            '3/3.5': 3.25,
            
            # 三球半
            '三球半': 3.5,
            '3.5': 3.5,
            
            # 四球
            '四球': 4.0,
            '四': 4.0,
            '4': 4.0,
        }
    
    def fetch_daily_handicaps(self, match_date: str, use_cache: bool = True) -> Dict[str, Dict]:
        """
        批量获取某一天所有比赛的盘口数据（优化：一次请求获取全天数据）
        
        Args:
            match_date: 比赛日期，格式：YYYY-MM-DD
            use_cache: 是否使用本地缓存（默认True）
            
        Returns:
            字典：{match_key: handicap_data}
            match_key格式："{home}_{away}_{time}"
        """
        try:
            date_obj = datetime.strptime(match_date, "%Y-%m-%d")
            date_str = date_obj.strftime("%Y%m%d")
            formatted_date = date_obj.strftime("%Y-%m-%d")
            
            # 🔥 优先从本地缓存读取
            if use_cache:
                cached_data = self.load_daily_handicap_json(match_date)
                if cached_data:
                    print(f"✅ 使用本地缓存: {match_date} ({len(cached_data)}场)")
                    logger.info(f"✅ 使用本地缓存: {match_date} ({len(cached_data)}场)")
                    return cached_data
            
            # 🔥 使用完整版页面获取盘口数据
            # wanchang.php: 完场页面（按日期查询）
            # 2h1.php: 完整版页面（今天+未来2-3天所有比赛）
            today = datetime.now().strftime("%Y-%m-%d")
            
            if match_date < today:
                # 过去的日期：使用完场页面（有日期参数）
                url = f"https://live.500.com/wanchang.php?e={formatted_date}"
                print(f"📥 从500.com批量获取 {match_date} 的盘口数据（完场页面）...")
            else:
                # 今天或未来：使用完整版页面（包含所有比赛）
                url = "https://live.500.com/2h1.php"
                print(f"📥 从500.com批量获取 {match_date} 的盘口数据（完整版）...")
            
            print(f"  URL: {url}")
            logger.info(f"📥 批量获取 {match_date} 的盘口数据...")
            logger.info(f"  URL: {url}")
            
            # 🔥 添加重试机制（最多3次）
            max_retries = 3
            retry_delay = 2
            html = None
            
            for attempt in range(max_retries):
                try:
                    response = self.session.get(url, timeout=15)  # 增加超时到15秒
                    # 🔥 修复编码问题：强制使用GB2312（500.com是GB2312编码）
                    # apparent_encoding有时会错误识别为ISO-8859-5
                    response.encoding = 'gb2312'
                    html = response.text
                    break  # 成功获取，跳出重试循环
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  ⚠️ 请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)[:100]}")
                        print(f"  ⏳ 等待 {retry_delay} 秒后重试...")
                        logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        print(f"  ❌ 请求失败，已达最大重试次数: {str(e)[:100]}")
                        logger.error(f"请求失败，已达最大重试次数: {e}")
                        return {}  # 返回空字典而不是抛出异常
            
            if not html:
                logger.warning(f"  ⚠️ 无法获取页面内容")
                return {}
            
            # 🔥 调试：打印编码信息
            print(f"  📝 响应编码: {response.encoding}")
            
            if not html or response.status_code != 200:
                logger.warning(f"  ⚠️  页面获取失败: {response.status_code}")
                return {}
            
            print(f"  ✅ 页面获取成功（{len(html)}字符），开始解析...")
            logger.info(f"  ✅ 页面获取成功，开始解析...")
            
            # 🔥 保存HTML到本地
            self.save_daily_handicap_html(match_date, html)
            
            # 解析所有比赛的盘口数据
            handicaps = {}
            # 🔥 增加context长度到3000字符，确保盘口div不被截断
            pattern = r'<tr[^>]*id="a(\d+)"[^>]*>(.{0,3000}?)</tr>'
            
            matches_found = 0
            handicaps_with_value = 0
            for match in re.finditer(pattern, html, re.DOTALL):
                matches_found += 1
                fid = match.group(1)
                context = match.group(2)
                
                # 每处理50场打印一次进度
                if matches_found % 50 == 0:
                    print(f"  解析进度: {matches_found} 场...")
                    import sys
                    sys.stdout.flush()
                
                # 提取比赛日期和时间
                date_str, time_info = self._extract_datetime_from_context(context)
                
                # 🔥 如果使用完整版页面，需要过滤日期
                if match_date >= today and date_str:
                    # 将 "11-22" 格式转换为 "2025-11-22" 进行比较
                    year = datetime.now().year
                    try:
                        match_full_date = f"{year}-{date_str}"
                        # 如果不是目标日期，跳过这场比赛
                        if match_full_date != match_date:
                            continue
                    except:
                        pass  # 日期解析失败，继续处理
                
                # 提取队名
                home_team, away_team = self._extract_teams_from_context(context)
                
                # 提取盘口（从pk div中）
                handicap_str = self._extract_handicap_from_context(context)
                
                # 🔥 调试：打印前几个盘口样例和队名提取情况
                if matches_found <= 3:
                    print(f"  样例{matches_found}: fid={fid}")
                    print(f"    盘口: '{handicap_str}'")
                    print(f"    队名: {home_team} vs {away_team}")
                    # 查找队名相关的HTML片段
                    if 'mainName' in context:
                        name_pos = context.find('mainName')
                        name_snippet = context[name_pos-50:name_pos+150]
                        print(f"    队名片段: {name_snippet}")
                    elif 'gy=' in context:
                        gy_pos = context.find('gy=')
                        gy_snippet = context[gy_pos:gy_pos+100]
                        print(f"    gy片段: {gy_snippet}")
                    else:
                        # 显示整个context的前300字符
                        print(f"    context前300字符: {context[:300]}")
                    print()  # 空行分隔
                
                # 只保存真正有让球盘口的比赛（排除盘口为"-"或空的）
                if handicap_str and handicap_str.strip() and handicap_str.strip() != '-':
                    handicaps_with_value += 1
                    match_key = f"{fid}_{time_info}"
                    
                    handicaps[match_key] = {
                        'fid': fid,
                        'home_team': home_team,
                        'away_team': away_team,
                        'time': time_info,
                        'current_handicap_str': handicap_str,
                        'current_handicap': self.parse_handicap(handicap_str)
                    }
                    
                    # 每找到10场有盘口的比赛打印一次
                    if handicaps_with_value % 10 == 0:
                        print(f"  找到有盘口的比赛: {handicaps_with_value} 场...")
                        import sys
                        sys.stdout.flush()
            
            print(f"  📊 页面总比赛数: {matches_found} 场")
            print(f"  ✅ 解析完成：找到 {len(handicaps)} 场有让球盘口的比赛")
            logger.info(f"  ✅ 解析完成：找到 {len(handicaps)} 场比赛的盘口数据")
            
            # 保存JSON到本地
            # 🔥 保存JSON到本地
            self.save_daily_handicap_json(match_date, handicaps)
            
            return handicaps
            
        except Exception as e:
            import traceback
            error_msg = f"批量获取盘口失败: {type(e).__name__} - {str(e)}"
            print(f"❌ {error_msg}")
            print(f"完整堆栈跟踪:")
            print(traceback.format_exc())
            logger.error(error_msg)
            return {}
    
    def _extract_handicap_from_context(self, context: str) -> Optional[str]:
        """从上下文中提取盘口字符串
        
        支持多种HTML格式，以应对500彩票网结构变化：
        1. 完场页面格式: class="fhuise"
        2. 系统彩页面格式: class="fgreen"  
        3. 新格式: class="fred"
        4. data-ao属性格式
        5. 直接文本内容
        """
        # 匹配 <div class="pk">...</div> 中的盘口
        
        # 🔥 模式1: 完场页面格式 class="fhuise"
        pk_match = re.search(r'<div class="pk">.*?class="fhuise"[^>]*>([^<]+)</a>', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-':
                return result
        
        # 🔥 模式2: 系统彩页面格式 class="fgreen"
        pk_match = re.search(r'<div class="pk">.*?class="fgreen"[^>]*>([^<]+)</a>', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-':
                return result
        
        # 🔥 模式3: 新增 class="fred"（红色盘口）
        pk_match = re.search(r'<div class="pk">.*?class="fred"[^>]*>([^<]+)</a>', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-':
                return result
        
        # 🔥 模式4: 任意颜色class（通用匹配）
        pk_match = re.search(r'<div class="pk">.*?<a[^>]*class="f(?:huise|green|red|blue|orange)"[^>]*>([^<]+)</a>', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-':
                return result
        
        # 🔥 模式5: data-ao属性（备用）
        pk_match = re.search(r'<div class="pk">.*?data-ao="([^"]+)"', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-':
                return result
        
        # 🔥 模式6: 直接提取pk div中的任意链接文本
        pk_match = re.search(r'<div class="pk"[^>]*>(.*?)</div>', context, re.DOTALL)
        if pk_match:
            pk_content = pk_match.group(1)
            # 提取所有<a>标签中的文本
            link_matches = re.findall(r'<a[^>]*>([^<]+)</a>', pk_content)
            for text in link_matches:
                text = text.strip()
                # 过滤掉明显不是盘口的文本
                if text and text != '-' and not text.isdigit():
                    # 检查是否包含盘口关键字
                    if any(kw in text for kw in ['球', '平', '受', '/', '+', '-', '.']):
                        return text
        
        # 🔥 模式7: 最宽松匹配 - pk div中的纯文本
        pk_match = re.search(r'<div class="pk"[^>]*>([^<]+)</div>', context, re.DOTALL)
        if pk_match:
            result = pk_match.group(1).strip()
            if result and result != '-' and len(result) < 20:  # 避免匹配到太长的文本
                return result
        
        return None
    
    def find_handicap_from_daily_data(
        self, 
        daily_handicaps: Dict[str, Dict],
        home_team: str,
        away_team: str,
        match_time: str
    ) -> Optional[Dict]:
        """
        从批量获取的每日盘口数据中查找匹配的比赛
        
        Args:
            daily_handicaps: 从fetch_daily_handicaps获取的数据
            home_team: 主队名称
            away_team: 客队名称
            match_time: 比赛时间，格式："HH:MM" 或 "YYYY-MM-DD HH:MM"
            
        Returns:
            盘口数据字典，如果未找到返回None
        """
        # 🔥 修复：检查输入参数
        if not daily_handicaps:
            logger.warning(f"  ⚠️  盘口数据为空，无法匹配")
            return None
        
        if not home_team or not away_team:
            logger.warning(f"  ⚠️  队名为空，无法匹配")
            return None
        
        # 清理队名
        home_clean = self._clean_team_name(home_team)
        away_clean = self._clean_team_name(away_team)
        
        # 提取时间（HH:MM）
        if ' ' in match_time:
            time_str = match_time.split(' ')[1][:5]  # HH:MM
        else:
            time_str = match_time[:5]
        
        logger.info(f"  🔍 查找盘口: {home_clean} vs {away_clean} @ {time_str}")
        logger.info(f"     共有 {len(daily_handicaps)} 场盘口数据可供匹配")
        
        # 🔥 收紧匹配策略，避免错误匹配
        best_match = None
        best_score = 0
        
        # 🔥 输出所有候选比赛，便于调试
        logger.info(f"  📋 候选比赛列表:")
        for idx, (match_key, handicap_data) in enumerate(daily_handicaps.items(), 1):
            logger.info(f"     [{idx}] {handicap_data['home_team']} vs {handicap_data['away_team']} @ {handicap_data['time'][:5]} (盘口: {handicap_data.get('current_handicap_str', 'N/A')})")
        
        for match_key, handicap_data in daily_handicaps.items():
            score = 0
            
            # 1. 时间匹配（权重提高到40分）
            if handicap_data['time'][:5] == time_str:
                score += 40
            else:
                # 收紧时间误差范围
                try:
                    h1, m1 = map(int, handicap_data['time'][:5].split(':'))
                    h2, m2 = map(int, time_str.split(':'))
                    time_diff = abs((h1 * 60 + m1) - (h2 * 60 + m2))
                    if time_diff <= 5:  # ±5分钟
                        score += 35
                    elif time_diff <= 15:  # ±15分钟
                        score += 25
                    elif time_diff <= 30:  # ±30分钟
                        score += 10
                    elif time_diff <= 90:  # ±90分钟，作为兜底交给队名相似度过滤
                        score += 5
                    else:
                        continue  # 时间差太大，直接跳过
                except:
                    continue
            
            # 2. 队名相似度（权重提高，要求更严格）
            home_500 = self._clean_team_name(handicap_data['home_team'])
            away_500 = self._clean_team_name(handicap_data['away_team'])
            
            home_similarity = similarity_ratio(home_clean, home_500)
            away_similarity = similarity_ratio(away_clean, away_500)
            
            # 🔥 收紧队名相似度阈值，增加权重
            if home_similarity >= 0.7:  # 提高到0.7
                score += int(home_similarity * 40)  # 提高权重到40
            elif home_similarity >= 0.5:
                score += int(home_similarity * 20)  # 中等相似度给少量分
            else:
                # 相似度太低，严重扣分（避免错误匹配）
                score -= 30
            
            if away_similarity >= 0.7:  # 提高到0.7
                score += int(away_similarity * 40)  # 提高权重到40
            elif away_similarity >= 0.5:
                score += int(away_similarity * 20)
            else:
                score -= 30
            
            # 额外检查：关键词匹配（处理"FC首尔"vs"首尔FC"这种情况）
            if home_clean in home_500 or home_500 in home_clean:
                score += 5
            if away_clean in away_500 or away_500 in away_clean:
                score += 5
            
            # 🔥 强制输出所有候选的详细信息（便于调试）
            logger.info(f"    候选: {home_500} vs {away_500} @ {handicap_data['time'][:5]}")
            logger.info(f"           相似度: 主={home_similarity:.2f}, 客={away_similarity:.2f}, 得分={score}")
            
            if score > best_score:
                best_score = score
                best_match = handicap_data
        
        # 🔥 降低最低通过分数到50分（更宽松的匹配）
        min_score = 50  # 时间匹配40分 + 队名部分匹配10分
        
        if best_match and best_score >= min_score:
            logger.info(f"  ✅ 找到匹配: {best_match['home_team']} vs {best_match['away_team']}, 盘口={best_match['current_handicap_str']}, 得分={best_score}")
            return best_match
        
        # 🔥 如果标准匹配失败，尝试更宽松的核心词匹配
        if not best_match or best_score < min_score:
            for match_key, handicap_data in daily_handicaps.items():
                # 检查时间是否接近（±60分钟）
                try:
                    h1, m1 = map(int, handicap_data['time'][:5].split(':'))
                    h2, m2 = map(int, time_str.split(':'))
                    time_diff = abs((h1 * 60 + m1) - (h2 * 60 + m2))
                    if time_diff > 60:
                        continue
                except:
                    continue
                
                home_500 = handicap_data['home_team']
                away_500 = handicap_data['away_team']
                
                # 核心词匹配：取队名的后2-3个字进行匹配
                home_core = home_clean[-3:] if len(home_clean) >= 3 else home_clean
                away_core = away_clean[-3:] if len(away_clean) >= 3 else away_clean
                home_500_core = home_500[-3:] if len(home_500) >= 3 else home_500
                away_500_core = away_500[-3:] if len(away_500) >= 3 else away_500
                
                # 如果核心词匹配，认为是同一场比赛
                home_match = (home_core in home_500 or home_500_core in home_clean or 
                             home_clean in home_500 or home_500 in home_clean)
                away_match = (away_core in away_500 or away_500_core in away_clean or
                             away_clean in away_500 or away_500 in away_clean)
                
                if home_match and away_match:
                    logger.info(f"  ✅ 核心词匹配成功: {home_500} vs {away_500}, 盘口={handicap_data['current_handicap_str']}")
                    return handicap_data
        
        if best_match:
            logger.warning(f"  ⚠️  最佳候选得分不足（{best_score}/{min_score}）: {best_match['home_team']} vs {best_match['away_team']}")
            logger.warning(f"           查找: {home_clean} vs {away_clean} @ {time_str}")
        else:
            logger.warning(f"  ⚠️  未找到任何候选")
            logger.warning(f"           查找: {home_clean} vs {away_clean} @ {time_str}")
            logger.warning(f"           共有 {len(daily_handicaps)} 场盘口数据")
        return None
    
    def parse_handicap(self, handicap_str: str, is_home: bool = True) -> float:
        """
        解析盘口字符串，转换为数值
        
        Args:
            handicap_str: 盘口字符串，如 "球半"、"受平/半"、"-1.5"、"+0.5" 等
            is_home: 是否是主队的盘口
            
        Returns:
            盘口数值，正数表示受让，负数表示让球
        """
        if not handicap_str:
            return 0.0
        
        handicap_str = str(handicap_str).strip()
        original_str = handicap_str  # 保存原始字符串用于调试
        
        # 🔥 关键逻辑：判断是否是受让方
        is_receiving = False
        if '受' in handicap_str:
            is_receiving = True
            handicap_str = handicap_str.replace('受', '')
        
        # 去除空格和其他符号（但保留正负号）
        handicap_str = handicap_str.replace(' ', '').replace('让', '')
        
        # 🔥 检测是否有明确的+/-号
        has_explicit_sign = handicap_str.startswith('-') or handicap_str.startswith('+')
        sign = 1
        
        if has_explicit_sign:
            # 有明确的+/-号，提取符号
            if handicap_str.startswith('-'):
                sign = -1
            handicap_str = handicap_str[1:]  # 去掉符号
        
        # 解析数值部分（总是正数）
        value = self._parse_handicap_value(handicap_str)
        
        # 🔥 核心逻辑：決定最终符号
        if has_explicit_sign:
            # 情况1：有明确的+/-号，直接使用
            result = value * sign
        else:
            # 情况2：没有明确的+/-号，根据"受"字判断
            if is_receiving:
                # 有"受"字 = 受让 = 正数（+）
                result = value
            else:
                # 无"受"字 = 让球 = 负数（-）
                result = -value
        
        # 🔥 调试日志：打印解析过程
        logger.info(f"🎯 盘口解析: '{original_str}' -> 数值={value}, 有明确符号={has_explicit_sign}, 符号={sign if has_explicit_sign else 'N/A'}, 受让={is_receiving}, 结果={result}")
        
        return result
    
    def _parse_handicap_value(self, handicap_str: str) -> float:
        """解析盘口字符串的数值部分"""
        # 尝试直接解析数字
        try:
            return float(handicap_str)
        except ValueError:
            pass
        
        # 先尝试精确匹配
        if handicap_str in self.handicap_map:
            return self.handicap_map[handicap_str]
        
        # 按长度从长到短排序，优先匹配较长的key（避免"球半"被"半"匹配）
        sorted_keys = sorted(self.handicap_map.keys(), key=len, reverse=True)
        
        for key in sorted_keys:
            if key in handicap_str or handicap_str in key:
                return self.handicap_map[key]
        
        logger.warning(f"无法解析盘口: {handicap_str}，默认返回0")
        return 0.0
    
    def search_match_by_teams(
        self, 
        home_team: str, 
        away_team: str,
        league: Optional[str] = None,
        match_date: Optional[str] = None,
        match_time: Optional[str] = None
    ) -> Optional[str]:
        """
        根据球队名称搜索比赛ID（时间优先策略）
        
        策略：时间最可靠 > 球队模糊匹配 > 联赛辅助
        
        Args:
            home_team: 主队名称
            away_team: 客队名称
            league: 联赛名称（可选，辅助验证，翻译可能不同）
            match_date: 比赛日期，格式：YYYY-MM-DD（用于访问页面）
            match_time: 完整时间，格式：YYYY-MM-DD HH:MM（用于精确匹配）
            
        Returns:
            比赛ID (fid)，如果未找到返回None
        """
        try:
            # 500彩票网的比赛列表页面
            # 根据日期访问不同的页面
            possible_urls = None  # 初始化
            
            if match_date:
                date_obj = datetime.strptime(match_date, "%Y-%m-%d")
                date_str = date_obj.strftime("%Y%m%d")
                today_obj = datetime.now()
                today = today_obj.strftime("%Y%m%d")
                
                # 判断是否为完场比赛（日期早于今天）
                if date_str < today:
                    # 完场比赛：尝试多种可能的URL格式
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                    
                    # 可能的URL格式（按优先级）
                    possible_urls = [
                        f"https://live.500.com/wanchang.php?e={formatted_date}",  # 格式1：完场比分页面
                        f"https://odds.500.com/fenxi/shuju-{date_str}.shtml",  # 格式2：数据榜（备用）
                    ]
                    
                    url = possible_urls[0]  # 先尝试第一个
                    logger.info(f"  检测到完场比赛（{date_str} < {today}）")
                    logger.info(f"  使用完场比分页面")
                    logger.info(f"  备用URL: {len(possible_urls)} 个")
                else:
                    # 未来或当天比赛使用"完赛比分"页面（通用）
                    # 注意：live.500.com/2h1.php 不需要日期参数，显示当天+未来比赛
                    possible_urls = [
                        "https://live.500.com/2h1.php",  # 格式1：完赛比分（通用页面）
                        f"https://odds.500.com/fenxi/shuju-{date_str}.shtml",  # 格式2：数据榜（备用）
                    ]
                    url = possible_urls[0]
                    logger.info(f"  当天或未来比赛")
                    logger.info(f"  备用URL: {len(possible_urls)} 个")
            else:
                # 没有指定日期，使用今天的未来比赛页面
                date_str = datetime.now().strftime("%Y%m%d")
                today = datetime.now().strftime("%Y%m%d")
                possible_urls = [
                    "https://live.500.com/2h1.php",  # 格式1：完赛比分（通用页面）
                    f"https://odds.500.com/fenxi/shuju-{date_str}.shtml",  # 格式2：数据榜（备用）
                ]
                url = possible_urls[0]
                logger.info(f"  未指定日期，使用今天")
            
            # 尝试访问赛事页面（如果有备用URL，失败时自动重试）
            
            logger.info(f"搜索比赛: {home_team} vs {away_team}")
            logger.info(f"  联赛: {league}, 日期: {match_date}, 时间: {match_time}")
            
            # 如果有备用URL，逐个尝试
            urls_to_try = [url] if not possible_urls else possible_urls
            html = None
            response = None
            
            for idx, try_url in enumerate(urls_to_try, 1):
                logger.info(f"  尝试URL {idx}/{len(urls_to_try)}: {try_url}")
                
                try:
                    response = self.session.get(try_url, timeout=15)
                    response.encoding = 'gb2312'  # 500彩票网使用GB2312编码
                    
                    logger.info(f"    响应状态码: {response.status_code}")
                    
                    if response.status_code == 200:
                        temp_html = response.text
                        
                        # 检查是否返回"暂无数据"
                        if "暂无该场比赛的数据" in temp_html and len(urls_to_try) > 1 and idx < len(urls_to_try):
                            logger.warning(f"    ⚠️  此URL暂无数据，尝试下一个...")
                            continue
                        
                        html = temp_html
                        logger.info(f"  ✅ 成功访问（格式{idx}）")
                        break
                    else:
                        logger.warning(f"    ⚠️  状态码 {response.status_code}，尝试下一个...")
                        
                except Exception as e:
                    logger.warning(f"    ⚠️  请求失败: {e}，尝试下一个...")
                    continue
            
            # 如果所有URL都失败
            if not html or not response or response.status_code != 200:
                logger.warning(f"⚠️  所有URL尝试均失败")
                if response:
                    logger.warning(f"  最后状态码: {response.status_code}")
                    
                    # 保存错误响应
                    try:
                        from pathlib import Path
                        debug_dir = Path(__file__).parent.parent / "debug_html"
                        debug_dir.mkdir(exist_ok=True)
                        debug_file = debug_dir / f"500_error_{response.status_code}_{date_str}.html"
                        debug_file.write_text(response.text, encoding='gb2312', errors='ignore')
                        logger.info(f"  已保存错误响应: {debug_file.name}")
                    except:
                        pass
                else:
                    logger.warning(f"  所有请求均失败，无响应")
                
                return None
            
            # 检查页面是否有效
            if len(html) < 100:
                logger.warning(f"⚠️  500彩票网返回空页面（长度: {len(html)}）")
                
                # 保存空页面用于调试
                try:
                    from pathlib import Path
                    debug_dir = Path(__file__).parent.parent / "debug_html"
                    debug_dir.mkdir(exist_ok=True)
                    debug_file = debug_dir / f"500_empty_{date_str}_{home_team}_vs_{away_team}.html"
                    debug_file.write_text(html, encoding='gb2312', errors='ignore')
                    logger.info(f"  已保存空页面: {debug_file.name}")
                except:
                    pass
                
                return None
            
            # 检查是否返回"暂无数据"（仅用于非完场页面）
            if "暂无该场比赛的数据" in html or ("暂无数据" in html and date_str >= today):
                logger.warning(f"⚠️  500彩票网暂无此比赛数据")
                
                # 保存HTML用于确认
                try:
                    from pathlib import Path
                    debug_dir = Path(__file__).parent.parent / "debug_html"
                    debug_dir.mkdir(exist_ok=True)
                    debug_file = debug_dir / f"500_no_data_{date_str}_{home_team}_vs_{away_team}.html"
                    debug_file.write_text(html, encoding='gb2312', errors='ignore')
                    logger.info(f"  已保存响应HTML: {debug_file.name}")
                except:
                    pass
                
                return None
            
            # 保存HTML用于调试（完场比赛或调试模式）
            if match_date:
                try:
                    from pathlib import Path
                    debug_dir = Path(__file__).parent.parent / "debug_html"
                    debug_dir.mkdir(exist_ok=True)
                    page_type = "finished" if date_str < today else "live"
                    debug_file = debug_dir / f"500_{page_type}_{date_str}_{home_team}_vs_{away_team}.html"
                    debug_file.write_text(html, encoding='gb2312', errors='ignore')
                    logger.info(f"  已保存{page_type}页面HTML: {debug_file.name}")
                    logger.info(f"  HTML长度: {len(html)} 字符")
                except Exception as e:
                    logger.warning(f"保存调试HTML失败: {e}")
            
            # 清理球队名称
            home_clean = self._clean_team_name(home_team)
            away_clean = self._clean_team_name(away_team)
            league_clean = self._clean_league_name(league) if league else None
            
            logger.info(f"清理后的名称 - 主队: {home_clean}, 客队: {away_clean}, 联赛: {league_clean}")
            
            # 查找所有可能的比赛ID及其上下文（按时间筛选）
            candidates = self._find_match_candidates(html, home_clean, away_clean, league_clean, match_time or match_date)
            
            if not candidates:
                logger.warning(f"未找到任何匹配: {home_team} vs {away_team}")
                logger.warning(f"  清理后: {home_clean} vs {away_clean}")
                
                # 尝试在HTML中搜索球队名称
                if home_clean in html:
                    logger.info(f"  ✓ HTML中找到主队: {home_clean}")
                else:
                    logger.warning(f"  ✗ HTML中未找到主队: {home_clean}")
                    # 尝试搜索部分名称
                    if len(home_clean) >= 2:
                        partial = home_clean[-2:]
                        if partial in html:
                            logger.info(f"    但找到部分匹配: {partial}")
                
                if away_clean in html:
                    logger.info(f"  ✓ HTML中找到客队: {away_clean}")
                else:
                    logger.warning(f"  ✗ HTML中未找到客队: {away_clean}")
                    if len(away_clean) >= 2:
                        partial = away_clean[-2:]
                        if partial in html:
                            logger.info(f"    但找到部分匹配: {partial}")
                
                # 保存HTML用于调试
                try:
                    from pathlib import Path
                    debug_dir = Path(__file__).parent.parent / "debug_html"
                    debug_dir.mkdir(exist_ok=True)
                    debug_file = debug_dir / f"500_no_match_{date_str}_{home_team}_vs_{away_team}.html"
                    debug_file.write_text(html, encoding='gb2312', errors='ignore')
                    logger.info(f"  已保存调试HTML: {debug_file.name}")
                except:
                    pass
                
                return None
            
            # 如果有多个候选，选择最佳匹配
            best_match = self._select_best_match(candidates, home_clean, away_clean, league_clean)
            
            if best_match:
                logger.info(f"✅ 找到最佳匹配: fid={best_match['fid']}, 得分={best_match['score']}")
                logger.info(f"   匹配信息: {best_match.get('context', 'N/A')}")
                return best_match['fid']
            
            logger.warning(f"候选比赛均不符合条件: {home_team} vs {away_team}")
            return None
            
        except Exception as e:
            logger.exception(f"搜索比赛失败: {e}")
            return None
    
    def _find_match_candidates(
        self, 
        html: str, 
        home_clean: str, 
        away_clean: str,
        league_clean: Optional[str],
        match_date: Optional[str] = None
    ) -> List[Dict]:
        """
        查找所有可能的比赛候选（优先使用时间+联赛匹配）
        
        策略：
        1. 首先按时间+联赛筛选
        2. 球队名称作为辅助验证（允许翻译差异）
        
        Returns:
            候选列表，每个包含 fid 和上下文信息
        """
        candidates = []
        
        # 从match_date中提取时间（HH:MM格式）
        target_time = None
        target_hour = None
        if match_date:
            # 尝试从"YYYY-MM-DD HH:MM"格式提取时间
            if ' ' in match_date:
                try:
                    time_part = match_date.split(' ')[1]
                    if ':' in time_part:
                        target_time = time_part[:5]  # HH:MM
                        target_hour = int(time_part.split(':')[0])
                        logger.info(f"  目标时间: {target_time} (小时: {target_hour})")
                except:
                    pass
        
        # 正则：提取比赛ID和周边文本（包含时间和联赛）
        # 匹配 shuju-数字.shtml，捕获足够多的上下文（包括整个<tr>标签）
        # 为了获取完整的比赛信息，需要捕获更大的范围
        pattern = r'<tr[^>]*id="a(\d+)"[^>]*>(.{0,2000}?)</tr>'  # 使用<tr>标签，包含完整比赛信息
        
        for match in re.finditer(pattern, html, re.DOTALL):
            fid = match.group(1)  # fid从<tr id="a{fid}">中提取
            context = match.group(2)  # 整个<tr>标签内的内容
            
            # 提取时间信息（格式：MM-DD HH:MM 或 HH:MM）
            time_info = self._extract_time_from_context(context)
            
            # 提取联赛信息
            league_info = self._extract_league_from_context(context)
            
            # 提取队名信息（用于编辑距离匹配）
            home_team_info, away_team_info = self._extract_teams_from_context(context)
            
            # 构建候选
            candidate = {
                'fid': fid,
                'context': context,
                'time_info': time_info,
                'league_info': league_info,
                'home_team': home_team_info,
                'away_team': away_team_info,
                'score': 0,  # 待计算匹配分数
            }
            
            # 策略：优先时间+联赛匹配
            if target_time and time_info:
                # 检查时间是否匹配
                time_match = self._check_time_match(time_info, target_time, target_hour)
                if time_match:
                    candidate['score'] += 50  # 时间匹配，加50分
                    logger.debug(f"  时间匹配: {time_info} ≈ {target_time}, fid={fid}")
                    
                    # 如果联赛也匹配，再加分
                    if league_clean and league_info:
                        if self._fuzzy_match(league_clean, league_info):
                            candidate['score'] += 30  # 联赛匹配，加30分
                            logger.debug(f"    联赛匹配: {league_info} ≈ {league_clean}")
                    
                    # 使用编辑距离计算队名相似度
                    if home_team_info and away_team_info:
                        home_similarity = similarity_ratio(home_clean, home_team_info)
                        away_similarity = similarity_ratio(away_clean, away_team_info)
                        
                        # 相似度 > 0.6 就加分（0.6表示60%相似）
                        if home_similarity > 0.6:
                            score_bonus = int(home_similarity * 20)  # 最多20分
                            candidate['score'] += score_bonus
                            logger.debug(f"    主队相似度: {home_clean} ≈ {home_team_info} ({home_similarity:.2f}), +{score_bonus}分")
                        
                        if away_similarity > 0.6:
                            score_bonus = int(away_similarity * 20)  # 最多20分
                            candidate['score'] += score_bonus
                            logger.debug(f"    客队相似度: {away_clean} ≈ {away_team_info} ({away_similarity:.2f}), +{score_bonus}分")
                    
                    # 即使联赛不匹配，时间匹配也是强信号
                    candidates.append(candidate)
                    continue
            
            # 如果没有时间信息，使用联赛+球队名称匹配
            if league_clean and league_info and self._fuzzy_match(league_clean, league_info):
                candidate['score'] += 30  # 联赛匹配
                
                has_home = self._fuzzy_match(home_clean, context) or home_clean in context
                has_away = self._fuzzy_match(away_clean, context) or away_clean in context
                
                if has_home and has_away:
                    candidate['score'] += 25  # 双方球队都匹配
                    candidates.append(candidate)
                elif has_home or has_away:
                    candidate['score'] += 15  # 单方匹配
                    candidates.append(candidate)
            else:
                # 没有联赛信息，只能用球队名称
                has_home = self._fuzzy_match(home_clean, context) or home_clean in context
                has_away = self._fuzzy_match(away_clean, context) or away_clean in context
                
                if has_home and has_away:
                    candidate['score'] += 20  # 双方球队都匹配
                    candidates.append(candidate)
        
        logger.info(f"找到 {len(candidates)} 个候选比赛")
        
        # 按分数排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 输出前3个候选的详细信息
        for i, c in enumerate(candidates[:3], 1):
            logger.debug(f"  候选{i}: fid={c['fid']}, 得分={c['score']}, 时间={c['time_info']}, 联赛={c['league_info']}")
        
        return candidates
    
    def _extract_datetime_from_context(self, context: str) -> tuple:
        """从上下文中提取比赛日期和时间（用于新的采集逻辑）
        
        Returns:
            tuple: (date_str, time_str)
            例如: ("11-22", "09:00")
        """
        # 匹配日期和时间格式: MM-DD HH:MM 或 MM-DD&nbsp;HH:MM
        datetime_match = re.search(r'(\d{1,2}-\d{1,2})(?:&nbsp;|\s+)(\d{2}:\d{2})', context)
        if datetime_match:
            date_str = datetime_match.group(1)
            time_str = datetime_match.group(2)
            # 统一日期格式为 MM-DD（补零）
            if '-' in date_str:
                parts = date_str.split('-')
                date_str = f"{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            return (date_str, time_str)
        
        # 如果没有日期，只匹配时间
        time_match = re.search(r'(\d{2}:\d{2})', context)
        if time_match:
            return (None, time_match.group(1))
        
        return (None, "00:00")
    
    def _extract_time_from_context(self, context: str) -> Optional[str]:
        """从上下文中提取时间信息（格式：HH:MM）"""
        # 匹配格式：MM-DD HH:MM 或 HH:MM
        time_patterns = [
            r'(\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2})',  # 11-17 10:00
            r'(\d{1,2}:\d{2})',  # 10:00
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, context)
            if match:
                time_str = match.group(1)
                # 提取HH:MM部分
                if ':' in time_str:
                    parts = time_str.split()
                    if len(parts) >= 2:
                        return parts[-1]  # 返回时间部分
                    return time_str
        return None
    
    def _extract_league_from_context(self, context: str) -> Optional[str]:
        """从上下文中提取联赛信息"""
        # 匹配HTML标签中的联赛名称
        # 例如：<a ...>墨西乙</a> 或 gy="墨西乙,..."
        league_patterns = [
            r'gy="([^",]+)',  # gy属性中的第一个值
            r'ssbox_01.*?>([^<]+)</a>',  # ssbox_01样式的链接文本
        ]
        
        for pattern in league_patterns:
            match = re.search(pattern, context)
            if match:
                league = match.group(1).strip()
                if league:
                    return league
        return None
    
    def _extract_teams_from_context(self, context: str) -> Tuple[str, str]:
        """
        从上下文中提取主客队名称
        """
        # 1. 尝试从 gy 属性提取 (适用于大部分页面)
        gy_match = re.search(r'gy="([^"]+)"', context)
        if gy_match:
            parts = gy_match.group(1).split(',')
            if len(parts) >= 3:
                home = parts[1].strip()
                away = parts[2].strip()
                # 只有当提取到的名字不为空时才返回
                if home and away:
                    return home, away
        
        # 2. 尝试从 mainName/clientName 提取 (适用于完场页面 wanchang.php)
        home_match = re.search(r'class="mainName">([^<]+)</span>', context)
        away_match = re.search(r'class="clientName">([^<]+)</span>', context)
        
        if home_match and away_match:
            return home_match.group(1).strip(), away_match.group(1).strip()

        # 3. 尝试从 p_lr01 提取 (适用于系统彩页面 index.php)
        # 主队: align="right" class="p_lr01" -> a tag
        # 客队: align="left" class="p_lr01" -> a tag
        
        # 注意：re.DOTALL 让 . 匹配换行符
        home_index_match = re.search(r'<td[^>]*align="right"[^>]*class="p_lr01"[^>]*>.*?<a[^>]*>([^<]+)</a>', context, re.DOTALL)
        away_index_match = re.search(r'<td[^>]*align="left"[^>]*class="p_lr01"[^>]*>.*?<a[^>]*>([^<]+)</a>', context, re.DOTALL)
        
        if home_index_match and away_index_match:
            return home_index_match.group(1).strip(), away_index_match.group(1).strip()
        
        return "", ""
    
    def _check_time_match(self, time_info: str, target_time: str, target_hour: int) -> bool:
        """检查时间是否匹配（允许一定误差）"""
        try:
            # 提取小时和分钟
            if ':' in time_info:
                parts = time_info.split(':')
                hour = int(parts[0])
                minute = int(parts[1][:2])  # 只取前两位
                
                target_parts = target_time.split(':')
                target_h = int(target_parts[0])
                target_m = int(target_parts[1])
                
                # 允许时间误差：±2小时
                hour_diff = abs(hour - target_h)
                if hour_diff <= 2 or hour_diff >= 22:  # 跨天的情况
                    # 如果小时接近，再检查分钟（允许±15分钟）
                    if hour_diff == 0:
                        minute_diff = abs(minute - target_m)
                        return minute_diff <= 15
                    else:
                        # 小时不同但在范围内，直接返回True
                        return True
        except:
            pass
        
        return False
    
    def _select_best_match(
        self,
        candidates: List[Dict],
        home_clean: str,
        away_clean: str,
        league_clean: Optional[str]
    ) -> Optional[Dict]:
        """
        从候选中选择最佳匹配（候选已按分数排序）
        
        策略：
        - 如果第一名得分 >= 50（时间+联赛匹配），直接返回
        - 否则，再检查球队名称
        """
        if not candidates:
            return None
        
        best = candidates[0]  # 已排序，第一个就是最佳
        best_score = best.get('score', 0)
        
        logger.info(f"最佳候选: fid={best['fid']}, 得分={best_score}, 时间={best.get('time_info')}, 联赛={best.get('league_info')}")
        
        # 如果通过时间+联赛匹配（得分>=50），直接返回
        if best_score >= 50:
            logger.info(f"  → 时间+联赛匹配成功")
            return best
        
        # 否则，验证球队名称（至少一方匹配）
        context = best['context'].lower()
        home_match = self._fuzzy_match(home_clean, context) or home_clean in context
        away_match = self._fuzzy_match(away_clean, context) or away_clean in context
        
        if home_match or away_match:
            logger.info(f"  → 球队名称匹配（主:{home_match}, 客:{away_match}）")
            return best
        
        logger.warning(f"  → 最佳候选未通过验证（时间:{best.get('time_info')}, 联赛:{best.get('league_info')}）")
        return None
    
    def _fuzzy_match(self, target: str, text: str) -> bool:
        """
        模糊匹配：检查target的主要部分是否在text中
        
        例如：
        - "墨西哥美洲" 可以匹配 "美洲"
        - "莱昂" 可以匹配 "莱昂"
        - "托卢卡" 可以匹配 "托卢卡"
        """
        target_lower = target.lower()
        text_lower = text.lower()
        
        # 1. 完全匹配
        if target in text or target_lower in text_lower:
            return True
        
        # 反向：text在target中（处理简称）
        if text in target or text_lower in target_lower:
            return True
        
        # 2. 去掉国家/地区/城市前缀后匹配
        # 如 "墨西哥美洲" -> "美洲"
        prefixes = [
            '墨西哥', '阿根廷', '巴西', '中国', '日本', '韩国', 
            '西班牙', '英格兰', '意大利', '德国', '法国',
            '新墨西哥', '洛杉矶', '纽约', '旧金山', 
            '圣保罗', '里约热内卢', '布宜诺斯艾利斯'
        ]
        for prefix in prefixes:
            if target.startswith(prefix):
                short_name = target.replace(prefix, '').strip()
                if short_name and (short_name in text or short_name.lower() in text_lower):
                    return True
            if text.startswith(prefix):
                short_name = text.replace(prefix, '').strip()
                if short_name and (short_name in target or short_name.lower() in target_lower):
                    return True
        
        # 3. 取核心队名匹配（后2-4个字）
        if len(target) >= 3:
            # 取后2-4个字作为核心队名
            for length in [4, 3, 2]:
                if len(target) >= length:
                    core_name = target[-length:]
                    if core_name in text or core_name.lower() in text_lower:
                        return True
                if len(text) >= length:
                    core_name = text[-length:]
                    if core_name in target or core_name.lower() in target_lower:
                        return True
        
        # 4. 任意连续2个字匹配（最宽松）
        if len(target) >= 2:
            for i in range(len(target) - 1):
                bi_gram = target[i:i+2]
                if bi_gram in text:
                    return True
        
        return False
    
    def _clean_league_name(self, league: str) -> str:
        """清理联赛名称"""
        if not league:
            return ""
        
        # 去除常见的后缀和括号内容
        league = re.sub(r'\[.*?\]', '', league)
        league = re.sub(r'\(.*?\)', '', league)
        league = re.sub(r'（.*?）', '', league)
        
        # 去除空格
        league = re.sub(r'\s+', '', league)
        
        # 联赛名称简化映射
        league_map = {
            '墨西超': '墨超',
            '墨西哥超级联赛': '墨超',
            '墨西联': '墨超',
            '英格兰超级联赛': '英超',
            '英格兰冠军联赛': '英冠',
            '西班牙甲级联赛': '西甲',
            '意大利甲级联赛': '意甲',
            '德国甲级联赛': '德甲',
            '法国甲级联赛': '法甲',
            '中国超级联赛': '中超',
            '国际友谊': '友谊赛',
            '国际友谊赛': '友谊赛',
            '友谊': '友谊赛',
            '世预赛': '世界杯外围赛',
            '世界杯预选赛': '世界杯外围赛',
            '欧国联': '欧洲国家联赛',
            '欧洲国家杯': '欧洲杯',
        }
        
        # 先尝试精确映射
        if league in league_map:
            return league_map[league]
        
        # 模糊匹配：如果包含关键词，也做映射
        for key, value in league_map.items():
            if key in league or league in key:
                return value
        
        return league
    
    def _clean_team_name(self, team_name: str) -> str:
        """清理球队名称，去除可能的干扰字符，并进行队名映射"""
        if not team_name:
            return ''
        
        original_name = team_name
        
        # 队名映射表（必发网 → 500.com常见译名）
        team_mapping = {
            # ============ 英超 Premier League ============
            '曼联': '曼彻斯特联',
            '曼彻斯特联': '曼联',
            '曼城': '曼彻斯特城',
            '曼彻斯特城': '曼城',
            '热刺': '托特纳姆热刺',
            '托特纳姆热刺': '热刺',
            '纽卡斯尔': '纽卡斯尔联',
            '纽卡斯尔联': '纽卡斯尔',
            '莱切斯特城': '莱斯特城',
            '莱斯特城': '莱切斯特城',
            '布莱顿': '布莱顿',
            '狼队': '狼队',
            '西汉姆联': '西汉姆',
            '西汉姆': '西汉姆联',
            
            # ============ 西甲 La Liga ============
            '马德里竞技': '马德里体育会',
            '马德里体育会': '马德里竞技',
            '马竞': '马德里竞技',
            '皇家马德里': '皇马',
            '皇马': '皇家马德里',
            '巴塞罗那': '巴萨',
            '巴萨': '巴塞罗那',
            '塞维利亚': '塞维利亚',
            '比利亚雷亚尔': '维拉利尔',
            '维拉利尔': '比利亚雷亚尔',
            '皇家社会': '皇家社会',
            '毕尔巴鄂竞技': '毕尔巴鄂',
            '毕尔巴鄂': '毕尔巴鄂竞技',
            '贝蒂斯': '皇家贝蒂斯',
            '皇家贝蒂斯': '贝蒂斯',
            '瓦伦西亚': '瓦伦西亚',
            '赫塔费': '赫塔费',
            '西班牙人': '西班牙人',
            '阿拉维斯': '阿拉维斯',
            '巴列卡诺': '巴列卡诺',
            
            # ============ 西乙 Segunda División ============
            '莱万特': '莱万特',
            '萨拉戈萨': '萨拉戈萨',
            '希洪竞技': '希洪竞技',
            '埃瓦尔': '埃瓦尔',
            '马拉加': '马拉加',
            '拉科鲁尼亚': '拉科鲁尼亚',
            '奥维多': '奥维多',
            '特内里费': '特内里费',
            '埃尔切': '埃尔切',
            '巴利亚多利德': '巴利亚多利德',
            
            # ============ 意甲 Serie A ============
            '国际米兰': '国米',
            '国米': '国际米兰',
            '尤文图斯': '尤文',
            '尤文': '尤文图斯',
            '那不勒斯': '拿玻里',
            '拿玻里': '那不勒斯',
            'AC米兰': '米兰',
            '米兰': 'AC米兰',
            '罗马': '罗马',
            '拉齐奥': '拉齐奥',
            '佛罗伦萨': '佛罗伦斯',
            '佛罗伦斯': '佛罗伦萨',
            '亚特兰大': '亚特兰大',
            '博洛尼亚': '博洛尼亚',
            '都灵': '都灵',
            '乌迪内斯': '乌迪内斯',
            '萨索洛': '萨索洛',
            '恩波利': '恩波利',
            '热那亚': '热那亚',
            '莱切': '莱切',
            
            # ============ 意乙 Serie B ============
            '克雷莫纳': '克雷莫纳',
            '帕尔马': '帕尔马',
            '威尼斯': '威尼斯',
            '科莫': '科莫',
            '布雷西亚': '布雷西亚',
            '雷吉纳': '雷吉纳',
            '巴里': '巴里',
            '摩德纳': '摩德纳',
            
            # ============ 德甲 Bundesliga ============
            '拜仁慕尼黑': '拜仁',
            '拜仁': '拜仁慕尼黑',
            '多特蒙德': '多特',
            '多特': '多特蒙德',
            '勒沃库森': '勒沃库森',
            '莱比锡': '莱比锡红牛',
            '莱比锡红牛': '莱比锡',
            '法兰克福': '法兰克福',
            '柏林联': '柏林联合',
            '柏林联合': '柏林联',
            '门兴格拉德巴赫': '门兴',
            '门兴': '门兴格拉德巴赫',
            '沃尔夫斯堡': '狼堡',
            '狼堡': '沃尔夫斯堡',
            '弗赖堡': '弗赖堡',
            '霍芬海姆': '霍芬海姆',
            '斯图加特': '斯图加特',
            '美因茨': '美因茨',
            '奥格斯堡': '奥格斯堡',
            '科隆': '科隆',
            '柏林赫塔': '柏林赫塔',
            
            # ============ 德乙 2. Bundesliga ============
            '汉堡': '汉堡',
            '汉诺威96': '汉诺威',
            '汉诺威': '汉诺威96',
            '纽伦堡': '纽伦堡',
            '帕德博恩': '帕德博恩',
            '达姆施塔特': '达姆施塔特',
            '圣保利': '圣保利',
            '卡尔斯鲁厄': '卡尔斯鲁厄',
            '汉诺威96': '汉诺威',
            '杜塞尔多夫': '杜塞尔多夫',
            '基尔': '基尔',
            '波鸿': '波鸿',
            '布伦瑞克': '布伦瑞克',
            '马格德堡': '马格德堡',
            '雷根斯堡': '雷根斯堡',
            '海登海姆': '海登海姆',
            
            # ============ 法甲 Ligue 1 ============
            '巴黎圣日耳曼': '巴黎圣日门',
            '巴黎圣日门': '巴黎圣日耳曼',
            'PSG': '巴黎圣日耳曼',
            '马赛': '马赛',
            '摩纳哥': '摩纳哥',
            '里昂': '里昂',
            '里尔': '里尔',
            '雷恩': '雷恩',
            '尼斯': '尼斯',
            '朗斯': '朗斯',
            '斯特拉斯堡': '斯特拉斯堡',
            '南特': '南特',
            '图卢兹': '图卢兹',
            '兰斯': '朗斯',
            '布雷斯特': '布雷斯特',
            
            # ============ 法乙 Ligue 2 ============
            '欧塞尔': '欧塞尔',
            '阿雅克肖': '阿雅克肖',
            '昂热': '昂热',
            '巴斯蒂亚': '巴斯蒂亚',
            '第戎': '第戎',
            '甘冈': '甘冈',
            '格勒诺布尔': '格勒诺布尔',
            '勒阿弗尔': '勒阿弗尔',
            '梅斯': '梅斯',
            
            # ============ 荷甲 Eredivisie ============
            'PSV埃因霍温': '埃因霍温',
            '埃因霍温': 'PSV埃因霍温',
            'PSV': 'PSV埃因霍温',
            '阿贾克斯': '阿贾克斯',
            '费耶诺德': '费耶诺德',
            'AZ阿尔克马尔': '阿尔克马尔',
            '阿尔克马尔': 'AZ阿尔克马尔',
            '特温特': '特温特',
            '乌德勒支': '乌德勒支',
            '海伦芬': '海伦芬',
            '维特斯': '维特斯',
            '格罗宁根': '格罗宁根',
            
            # ============ 荷乙 Eerste Divisie ============
            '埃因霍温青年队': '埃因霍温青年',
            '阿贾克斯青年队': '阿贾克斯青年',
            '鹿特丹斯巴达': '鹿特丹斯巴达',
            '阿尔梅勒城': '阿尔梅勒城',
            '多德勒支': '多德勒支',
            
            # ============ 葡超 Primeira Liga ============
            '葡萄牙体育': '里斯本竞技',
            '里斯本竞技': '葡萄牙体育',
            '本菲卡': '本菲卡',
            '波尔图': '波尔图',
            '布拉加': '布拉加',
            
            # ============ 英冠 Championship ============
            '布里斯托尔城': '布里斯托城',
            '布里斯托城': '布里斯托尔城',
            '考文垂': '考文垂',
            '德比郡': '德比郡',
            '伊普斯维奇': '伊普斯维奇',
            '莱切斯特': '莱斯特城',
            '谢菲尔德联': '谢菲尔德联队',
            '谢菲尔德联队': '谢菲尔德联',
            '谢周三': '谢菲尔德星期三',
            '谢菲尔德星期三': '谢周三',
            '西布罗姆维奇': '西布罗姆',
            '西布罗姆': '西布罗姆维奇',
            '米德尔斯堡': '米德尔斯堡',
            '赫尔城': '赫尔城',
            '斯托克城': '斯托克城',
            '布莱克本': '布莱克本',
            '米尔沃尔': '米尔沃尔',
            '牛津联队': '牛津联',
            '牛津联': '牛津联队',
            '沃特福德': '沃特福德',
            '伯明翰': '伯明翰',
            '查尔顿': '查尔顿',
            '女王公园巡游者': 'QPR',
            'QPR': '女王公园巡游者',
            
            # ============ 英甲 League One ============
            '罗瑟汉姆': '罗瑟汉姆',
            '伯顿': '伯顿',
            '博尔顿': '博尔顿',
            '林肯城': '林肯城',
            '彼得堡联': '彼得堡',
            '彼得堡': '彼得堡联',
            '吉林汉姆': '吉林汉姆',
            '普利茅斯': '普利茅斯',
            '巴恩斯利': '巴恩斯利',
            '牛津联': '牛津联队',
            
            # ============ 英乙 League Two ============
            '曼斯菲尔德': '曼斯菲尔德',
            '克劳利': '克劳利',
            '唐卡斯特': '唐卡斯特',
            '格林斯比': '格林斯比',
            '哈特利浦': '哈特利浦',
            '莫雷坎比': '莫雷坎比',
            '诺茨郡': '诺茨郡',
            '罗奇代尔': '罗奇代尔',
            
            # ============ 欧冠其他球队 ============
            '圣吉罗斯': '圣吉罗斯联',
            '圣吉罗斯联': '圣吉罗斯',
            '布拉格斯拉维亚': '布拉格斯拉维亚',
            '萨尔茨堡': '萨尔茨堡红牛',
            '萨尔茨堡红牛': '萨尔茨堡',
            '哥本哈根': '哥本哈根',
            '凯尔特人': '凯尔特人',
            '流浪者': '格拉斯哥流浪者',
            '格拉斯哥流浪者': '流浪者',
            '博德闪耀': '博多格林特',
            '博多格林特': '博德闪耀',
            '奥林匹亚科斯': '奥林匹亚科斯',
            
            # ============ 亚冠 AFC Champions League ============
            'FC首尔': '首尔FC',
            '首尔FC': 'FC首尔',
            '武里南': '武里南联',
            '武里南联': '武里南',
            '上海海港': '海港',
            '海港': '上海海港',
            '广岛三箭': '广岛',
            '广岛': '广岛三箭',
            '浦和红钻': '浦和',
            '浦和': '浦和红钻',
            '川崎前锋': '川崎',
            '川崎': '川崎前锋',
            '墨尔本城': '墨尔本城',
            '江原FC': '江原',
            '江原': '江原FC',
            '成都蓉城': '成都',
            '成都': '成都蓉城',
            '吉达联合': '吉达联合',
            '吉达国民': '吉达国民',
            '萨德': '萨德',
            '沙迦': '沙迦',
            '町田泽维亚': '町田',
            '町田': '町田泽维亚',
            '塞帕汉': '塞帕汉',
            '阿哈尔': '阿哈尔',
            
            # ============ 中超 Chinese Super League ============
            '上海海港': '海港',
            '上海申花': '申花',
            '申花': '上海申花',
            '山东泰山': '泰山',
            '泰山': '山东泰山',
            '北京国安': '国安',
            '国安': '北京国安',
            '广州队': '广州',
            '广州': '广州队',
            '武汉三镇': '三镇',
            '三镇': '武汉三镇',
            '成都蓉城': '蓉城',
            '蓉城': '成都蓉城',
            '河南嵩山龙门': '河南',
            '河南': '河南嵩山龙门',
            '浙江队': '浙江',
            '浙江': '浙江队',
            
            # ============ 日职联 J-League ============
            '横滨水手': '横滨',
            '横滨': '横滨水手',
            '鹿岛鹿角': '鹿岛',
            '鹿岛': '鹿岛鹿角',
            '大阪钢巴': '大阪',
            '大阪': '大阪钢巴',
            '名古屋鲸八': '名古屋',
            '名古屋': '名古屋鲸八',
            '神户胜利船': '神户',
            '神户': '神户胜利船',
            'FC东京': '东京FC',
            '东京FC': 'FC东京',
            
            # ============ K联赛 K-League ============
            '全北现代': '全北',
            '全北': '全北现代',
            '蔚山现代': '蔚山',
            '蔚山': '蔚山现代',
            '济州联': '济州',
            '济州': '济州联',
            '水原三星': '水原',
            '水原': '水原三星',
            
            # ============ 美职联 MLS ============
            '西雅图海湾人': '西雅图海湾',
            '西雅图海湾': '西雅图海湾人',
            '明尼苏达联': '明尼苏达',
            '明尼苏达': '明尼苏达联',
            '洛杉矶银河': '洛杉矶',
            '洛杉矶': '洛杉矶银河',
            '波特兰伐木者': '波特兰',
            '波特兰': '波特兰伐木者',
            '圣地亚哥': '圣地亚哥',
            '亚特兰大联': '亚特兰大',
            
            # ============ 南美球队 ============
            '墨西哥美洲': '美洲',
            '美洲': '墨西哥美洲',
            '河床': '河床',
            '博卡青年': '博卡',
            '博卡': '博卡青年',
            '弗拉门戈': '弗拉门戈',
            '帕尔梅拉斯': '帕尔梅拉斯',
            
            # ============ 非洲球队 ============
            '恺撒酋长': '凯撒酋长',
            '凯撒酋长': '恺撒酋长',
            '轨道学院': '轨道学院',
            '茨普帕': '茨普帕',
            '玛盖斯': '玛格斯',
            '玛格斯': '玛盖斯',
            '阿玛祖鲁': '阿玛祖鲁',
            '贝联': '波洛克瓦尼',
            '波洛克瓦尼': '贝联',
            '瑟库库内联': '瑟库库内',
            '瑟库库内': '瑟库库内联',
            '理查兹湾FC': '理查兹湾',
            '理查兹湾': '理查兹湾FC',
            
            # ============ U19/U21 青年队 ============
            '马德里竞技U19': '马德里体育会U19',
            '马德里体育会U19': '马德里竞技U19',
            '巴黎圣日耳曼U19': '巴黎圣日门U19',
            '巴黎圣日门U19': '巴黎圣日耳曼U19',
            '埃因霍温U19': 'PSV埃因霍温U19',
            'PSV埃因霍温U19': '埃因霍温U19',
            '那不勒斯U19': '拿玻里U19',
            '拿玻里U19': '那不勒斯U19',
            '葡萄牙体育U19': '里斯本竞技U19',
            '里斯本竞技U19': '葡萄牙体育U19',
            '奥林匹亚科斯U19': '奥林比亚高斯U19',
            '奥林比亚高斯U19': '奥林匹亚科斯U19',
            '博德闪耀U19': '博多格林特U19',
            '博多格林特U19': '博德闪耀U19',
            '圣吉罗斯U19': '圣吉罗斯联U19',
            '圣吉罗斯联U19': '圣吉罗斯U19',
            '林肯红魔U19': '林肯U19',
            '林肯U19': '林肯红魔U19',
            '曼彻斯特联U21': '曼联U21',
            '曼联U21': '曼彻斯特联U21',
            '埃弗顿U21': '埃弗顿U21',
            '水晶宫U21': '水晶宫(U21)',
            '水晶宫(U21)': '水晶宫U21',
            '富勒姆U21': '富勒姆U21',
            '莱斯特城U21': '莱切斯特U21',
            '莱切斯特U21': '莱斯特城U21',
            
            # ============ 越南联赛 ============
            '河静鸿岭': '河静',
            '河静': '河静鸿岭',
            '黄安嘉莱': '黄安',
            '黄安': '黄安嘉莱',
            'TT河内': '河内',
            '河内': 'TT河内',
            'PVF人民公安': '人民公安',
            '人民公安': 'PVF人民公安',
            
            # ============ 其他联赛 ============
            '基多体育大学': '基多大学',
            '基多大学': '基多体育大学',
            '奥伦斯CS': '奥伦斯',
            '奥伦斯': '奥伦斯CS',
            '哈德斯菲尔德': '哈德斯菲尔德',
            
            # ============ 保加利亚联赛 ============
            'FC蒙塔纳': '蒙塔那',
            '蒙塔那': 'FC蒙塔纳',
            '普罗夫迪夫火车头': '普罗夫迪夫火车头',
            
            # ============ 智利联赛 ============
            '帕莱斯蒂诺': '巴勒斯坦人',
            '巴勒斯坦人': '帕莱斯蒂诺',
            '塞雷那': '塞雷那',
            
            # ============ 荷乙补充 ============
            '邓伯什': '邓博施',
            '邓博施': '邓伯什',
            '威廉二世': '威廉二世',
            
            # ============ 印尼联赛 ============
            '巴杨卡拉泗水联': '巴杨卡拉',
            '巴杨卡拉': '巴杨卡拉泗水联',
            '帕尔斯巴亚': '帕尔斯巴亚',
            
            # ============ 泰国联赛 ============
            '巴蜀府': '巴蜀基利',
            '巴蜀基利': '巴蜀府',
            '狮子港': '泰国港口局',
            '泰国港口局': '狮子港',
            
            # ============ 亚美尼亚联赛 ============
            'BKMA': 'BKMA',
            '卡潘宝山': '卡潘',
            '卡潘': '卡潘宝山',
            
            # ============ 丹麦联赛 ============
            'B93哥本哈根': 'B93',
            'B93': 'B93哥本哈根',
            '霍布罗': '霍布罗',
            '希勒罗德': '希勒罗德',
            '利恩比': '林比',
            '林比': '利恩比',
            
            # ============ 克罗地亚联赛 ============
            '乌克瓦': '乌克瓦',
            '奥斯杰克': '奥西耶克',
            '奥西耶克': '奥斯杰克',
            
            # ============ 北爱尔兰联赛 ============
            'FC宾高': '宾高',
            '宾高': 'FC宾高',
            '格伦托兰': '格伦杜兰',
            '格伦杜兰': '格伦托兰',
            
            # ============ 奥地利联赛 ============
            'WSC赫塔威尔斯': '赫塔威尔斯',
            '赫塔威尔斯': 'WSC赫塔威尔斯',
            '圣珀尔滕': '圣珀尔滕',
            '列弗宁': '列弗宁',
            '奥地利克拉根福': '克拉根福',
            '克拉根福': '奥地利克拉根福',
            '卡芬堡': '卡芬堡',
            '奥地利维也纳青年队': '奥地利维也纳青年',
            '奥地利维也纳青年': '奥地利维也纳青年队',
            '弗洛里茨多夫': '弗洛里茨多夫',
            '阿德米拉': '阿德米拉',
            '阿姆斯特顿': '阿姆斯特顿',
            '奥地利卢斯特瑙': '卢斯特瑙',
            '卢斯特瑙': '奥地利卢斯特瑙',
            
            # ============ 威尔士联赛 ============
            '巴里镇联': '巴里镇',
            '巴里镇': '巴里镇联',
            '西哈弗福德': '哈弗福德韦斯特',
            '哈弗福德韦斯特': '西哈弗福德',
            '新圣徒': '新圣人',
            '新圣人': '新圣徒',
            '卡那封': '卡那封',
            
            # ============ 德国地区联赛 ============
            '韦恩': '韦恩',
            '奥厄': '奥厄',
            
            # ============ 比利时联赛 ============
            '欧本': '欧本',
            '洛默尔': '洛默尔',
            '比斯查': '比斯查',
            'RFC列日': '列日',
            '列日': 'RFC列日',
            
            # ============ 法国低级别联赛 ============
            '萨勒格米斯': '萨勒格米斯',
            '南锡': '南锡',
            
            # ============ 波兰联赛 ============
            '比托姆': '比托姆',
            '莱茨纳': '莱茨纳',
            '马特斯': '马特斯',
            '台基': '台基',
            '拉多麦科': '拉多姆',
            '拉多姆': '拉多麦科',
            '扎布热矿工': '扎布热',
            '扎布热': '扎布热矿工',
            '罗切霍茹夫': '罗切霍茹夫',
            '涅波沃米采': '涅波沃米采',
            'GKS卡托威斯': '卡托威斯',
            '卡托威斯': 'GKS卡托威斯',
            '什切青': '什切青',
            
            # ============ 瑞士联赛 ============
            '尼奈斯': '尼奈斯',
            '瓦杜兹': '瓦杜兹',
            '瑞普斯威尔': '拉珀斯维尔',
            '拉珀斯维尔': '瑞普斯威尔',
            '贝林佐纳': '贝林佐纳',
            '纳沙泰尔': '纳沙泰尔',
            '阿劳': '阿劳',
            '卢塞恩': '卢塞恩',
            '温特图尔': '温特图尔',
            
            # ============ 罗马尼亚联赛 ============
            '布加勒斯特快速': '布加勒斯特快速',
            'FK米耶尔库雷亚丘克': '米耶尔库雷亚',
            '米耶尔库雷亚': 'FK米耶尔库雷亚丘克',
            '布加勒斯特迪纳摩': '布加勒斯特迪纳摩',
            '加拉茨钢铁': '加拉茨',
            '加拉茨': '加拉茨钢铁',
            
            # ============ 苏格兰联赛 ============
            '连利弗哥玫瑰': '利文斯顿',
            '利文斯顿': '连利弗哥玫瑰',
            '女王公园': '女王公园',
            
            # ============ 非洲冠军联赛 ============
            'MC阿尔及尔': '阿尔及尔',
            '阿尔及尔': 'MC阿尔及尔',
            '马梅洛迪日落': '马梅洛迪',
            '马梅洛迪': '马梅洛迪日落',
            '卡比利亚': '卡比利亚',
            '非洲年轻人': '非洲青年',
            '非洲青年': '非洲年轻人',
            '拉巴特皇家武装': '拉巴特',
            '拉巴特': '拉巴特皇家武装',
            '开罗国民': '开罗国民',
            '流浪联': '流浪者',
            '贝尔卡勒': '贝尔卡勒',
        }
        
        # 先尝试直接映射
        if team_name in team_mapping:
            team_name = team_mapping[team_name]
            logger.debug(f"  队名映射: {original_name} → {team_name}")
        
        # 去除括号及其内容（如"墨西哥(中)" -> "墨西哥"）
        team_name = re.sub(r'[(\（\[].*?[)\）\]]', '', team_name)
        
        # 去除空格
        team_name = re.sub(r'\s+', '', team_name)
        team_name = team_name.strip()
        
        # 去除国家/地区前缀（500彩票网通常不包含这些前缀）
        prefixes = [
            '墨西哥', '阿根廷', '巴西', '中国', '日本', '韩国',
            '西班牙', '英格兰', '意大利', '德国', '法国',
            '新墨西哥', '洛杉矶', '纽约', '旧金山',
            '圣保罗', '里约热内卢', '布宜诺斯艾利斯',
            '葡萄牙', '荷兰', '比利时', '土耳其'
        ]
        
        for prefix in prefixes:
            if team_name.startswith(prefix) and len(team_name) > len(prefix):
                # 去掉前缀后还有剩余内容，才去除
                short_name = team_name[len(prefix):]
                if short_name:  # 确保不是空字符串
                    team_name = short_name
                    logger.debug(f"  去除前缀'{prefix}': {team_name}")
                    break
        
        return team_name
    
    def fetch_handicap_data(self, fid: str, company_id: str = "澳门") -> Optional[Dict]:
        """
        获取指定比赛的让球盘口数据（从HTML页面解析）
        
        Args:
            fid: 比赛ID
            company_id: 博彩公司ID或名称，默认"澳门"
                       - 可以是具体ID: "5", "3", "4"等
                       - 可以是名称: "澳门", "Bet365", "立博"等（推荐）
                       常用: 澳门, Bet365, 立博, 皇冠
            
        Returns:
            盘口数据字典，包含：
            - handicap_text: 盘口描述（如"一球/球半"）
            - initial_handicap: 初盘让球数
            - current_handicap: 即时盘让球数
            - initial_home_odds: 初盘主队水位
            - initial_away_odds: 初盘客队水位
            - current_home_odds: 即时盘主队水位
            - current_away_odds: 即时盘客队水位
            - trend: 盘口变化趋势（"升"/"降"/"平"）
        """
        try:
            # 直接访问HTML页面
            url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"
            
            logger.info(f"获取盘口数据: fid={fid}, company_id={company_id}")
            logger.info(f"  访问URL: {url}")
            
            # 添加浏览器headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://odds.500.com/',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.encoding = 'gb2312'
            
            if response.status_code != 200:
                logger.warning(f"盘口页面获取失败: {response.status_code}")
                return None
            
            logger.info(f"  HTML长度: {len(response.text)} 字符")
            
            # 解析HTML提取盘口数据
            data = self._parse_handicap_html(response.text, company_id, fid)
            
            if data:
                logger.info(f"  ✅ 盘口解析成功")
                logger.info(f"     博彩公司: {data.get('company_name', company_id)} (ID={data.get('company_id')})")
                logger.info(f"     即时盘: {data.get('current_handicap_text')} ({data.get('current_home_odds')}/{data.get('current_away_odds')})")
                logger.info(f"     初盘: {data.get('initial_handicap_text')} ({data.get('initial_home_odds')}/{data.get('initial_away_odds')})")
            else:
                logger.warning(f"  ⚠️  未找到company_id={company_id}的盘口数据")
            
            return data
            
        except Exception as e:
            logger.exception(f"获取盘口数据失败: {e}")
            return None
    
    def _parse_handicap_html(self, html: str, company_id: str, fid: str) -> Optional[Dict]:
        """
        从HTML页面解析盘口数据
        
        支持两种方式查找博彩公司：
        1. 通过ID查找: company_id="5"
        2. 通过名称查找: company_id="澳门" (推荐，因为ID可能变化)
        
        HTML结构：
        <tr id="{row_id}">
            <td>公司名称</td>
            第一个table: 即时盘
            第二个table: 初盘
        </tr>
        """
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            
            target_row = None
            found_company_id = None
            found_company_name = None
            
            # 如果是纯数字，先尝试按ID查找
            if company_id.isdigit():
                target_row = soup.find('tr', id=company_id)
                if target_row:
                    found_company_id = company_id
                    # 尝试提取公司名称
                    tds = target_row.find_all('td', recursive=False)
                    for td in tds[:3]:
                        text = td.get_text(strip=True)
                        if text and len(text) < 20 and not text.replace('.', '').replace('↑', '').replace('↓', '').isdigit():
                            found_company_name = text
                            break
            
            # 如果没找到，或者是名称，则按名称模糊搜索
            if not target_row:
                all_rows = soup.find_all('tr', id=True)
                
                for row in all_rows:
                    # 提取公司名称
                    tds = row.find_all('td', recursive=False)
                    company_name = None
                    
                    for td in tds[:3]:
                        text = td.get_text(strip=True)
                        if text and len(text) < 20 and not text.replace('.', '').replace('↑', '').replace('↓', '').isdigit():
                            if text not in ['水', '盘', '值', '初', '即']:
                                company_name = text
                                break
                    
                    if not company_name:
                        continue
                    
                    # 模糊匹配（支持"澳门"、"*门"、"Bet365"等）
                    if (company_id in company_name or 
                        company_name in company_id or
                        (company_id == "澳门" and "门" in company_name) or
                        (company_id.lower() in company_name.lower())):
                        target_row = row
                        found_company_id = row.get('id')
                        found_company_name = company_name
                        logger.info(f"  找到博彩公司: {company_name} (ID={found_company_id})")
                        break
            
            if not target_row:
                logger.warning(f"未找到company_id={company_id}的数据行")
                return None
            
            # 找到该行中的所有table
            tables = target_row.find_all('table', class_='pl_table_data')
            
            if len(tables) < 2:
                logger.warning(f"盘口数据table数量不足: {len(tables)}")
                return None
            
            # 第一个table是即时盘，第二个是初盘
            current_table = tables[0]
            initial_table = tables[1]
            
            # 解析即时盘
            current_data = self._parse_handicap_table(current_table)
            # 解析初盘
            initial_data = self._parse_handicap_table(initial_table)
            
            if not current_data or not initial_data:
                logger.warning("盘口数据解析失败")
                return None
            
            # 组合数据
            result = {
                'source': '500.com',
                'fid': fid,
                'company_id': found_company_id or company_id,
                'company_name': found_company_name or company_id,
                # 即时盘
                'current_handicap': current_data['handicap_value'],
                'current_handicap_text': current_data['handicap_text'],
                'current_home_odds': current_data['home_odds'],
                'current_away_odds': current_data['away_odds'],
                'current_trend': current_data.get('trend', ''),
                # 初盘
                'initial_handicap': initial_data['handicap_value'],
                'initial_handicap_text': initial_data['handicap_text'],
                'initial_home_odds': initial_data['home_odds'],
                'initial_away_odds': initial_data['away_odds'],
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"解析盘口HTML失败: {e}")
            return None
    
    def _parse_handicap_table(self, table) -> Optional[Dict]:
        """
        解析单个盘口table（即时盘或初盘）
        
        table结构：
        <td>主队水位（如1.020↑）</td>
        <td ref="-1.250">盘口文本（如一球/球半）</td>
        <td>客队水位（如0.770↓）</td>
        """
        try:
            tds = table.find_all('td')
            
            if len(tds) < 3:
                return None
            
            # 主队水位
            home_odds_text = tds[0].get_text().strip()
            home_odds = float(re.sub(r'[↑↓]', '', home_odds_text))
            
            # 盘口
            handicap_td = tds[1]
            handicap_value = float(handicap_td.get('ref', '0'))
            handicap_text = handicap_td.get_text().strip()
            # 去除HTML标签（如<font>）
            handicap_text = re.sub(r'<[^>]+>', '', handicap_text)
            handicap_text = re.sub(r'\s*(升|降)\s*', '', handicap_text).strip()
            
            # 趋势
            trend = ''
            if '升' in handicap_td.get_text():
                trend = '升'
            elif '降' in handicap_td.get_text():
                trend = '降'
            
            # 客队水位
            away_odds_text = tds[2].get_text().strip()
            away_odds = float(re.sub(r'[↑↓]', '', away_odds_text))
            
            return {
                'home_odds': home_odds,
                'handicap_value': handicap_value,
                'handicap_text': handicap_text,
                'away_odds': away_odds,
                'trend': trend,
            }
            
        except Exception as e:
            logger.debug(f"解析盘口table失败: {e}")
            return None
    
    def _parse_handicap_response(self, response_text: str) -> Optional[Dict]:
        """
        解析盘口数据响应
        
        500彩票网的亚洲盘返回格式通常是：
        [[时间戳, 主队水位, 盘口, 客队水位, 盘口类型], ...]
        """
        try:
            # 移除可能的JavaScript变量声明
            text = response_text.strip()
            if text.startswith('var'):
                text = text.split('=', 1)[1].strip()
            if text.endswith(';'):
                text = text[:-1]
            
            # 解析JSON数组
            import json
            data_array = json.loads(text)
            
            if not data_array or len(data_array) == 0:
                logger.warning("盘口数据为空")
                return None
            
            # 第一条是初盘，最后一条是即时盘
            initial_data = data_array[0]
            current_data = data_array[-1]
            
            result = {
                'initial_home_odds': float(initial_data[1]) if len(initial_data) > 1 else None,
                'initial_handicap_str': str(initial_data[2]) if len(initial_data) > 2 else None,
                'initial_away_odds': float(initial_data[3]) if len(initial_data) > 3 else None,
                'current_home_odds': float(current_data[1]) if len(current_data) > 1 else None,
                'current_handicap_str': str(current_data[2]) if len(current_data) > 2 else None,
                'current_away_odds': float(current_data[3]) if len(current_data) > 3 else None,
                'initial_time': initial_data[0] if len(initial_data) > 0 else None,
                'current_time': current_data[0] if len(current_data) > 0 else None,
            }
            
            # 解析盘口数值
            if result['initial_handicap_str']:
                result['initial_handicap'] = self.parse_handicap(result['initial_handicap_str'])
            if result['current_handicap_str']:
                result['current_handicap'] = self.parse_handicap(result['current_handicap_str'])
            
            # 添加完整历史数据
            result['history'] = []
            for item in data_array:
                if len(item) >= 4:
                    handicap_str = str(item[2])
                    result['history'].append({
                        'time': item[0],
                        'home_odds': float(item[1]),
                        'handicap_str': handicap_str,
                        'handicap': self.parse_handicap(handicap_str),
                        'away_odds': float(item[3]),
                    })
            
            return result
            
        except Exception as e:
            logger.exception(f"解析盘口数据失败: {e}")
            return None
    
    def get_match_handicap(
        self,
        home_team: str,
        away_team: str,
        league: Optional[str] = None,
        match_date: Optional[str] = None,
        match_time: Optional[str] = None,
        company_id: str = "3"
    ) -> Optional[Dict]:
        """
        获取比赛的让球盘口数据（一站式方法）
        
        Args:
            home_team: 主队名称
            away_team: 客队名称
            league: 联赛名称（可选，用于辅助验证）
            match_date: 比赛日期，格式：YYYY-MM-DD（用于访问页面）
            match_time: 完整比赛时间，格式：YYYY-MM-DD HH:MM（用于精确匹配）
            company_id: 博彩公司ID（默认澳门盘）
            
        Returns:
            盘口数据字典
        """
        # 1. 搜索比赛ID（时间优先匹配）
        fid = self.search_match_by_teams(home_team, away_team, league, match_date, match_time)
        
        if not fid:
            logger.warning(f"未找到比赛: {home_team} vs {away_team}")
            return None
        
        # 2. 获取盘口数据
        handicap_data = self.fetch_handicap_data(fid, company_id)
        
        if not handicap_data:
            logger.warning(f"未获取到盘口数据: fid={fid}")
            return None
        
        # 3. 添加球队信息
        handicap_data['home_team'] = home_team
        handicap_data['away_team'] = away_team
        handicap_data['league'] = league
        handicap_data['match_date'] = match_date
        handicap_data['fid'] = fid
        
        return handicap_data
    
    def get_handicap(
        self,
        home_team: str,
        away_team: str,
        match_time: str,
        league: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取让球盘口（简化接口，兼容原有调用）
        
        Args:
            home_team: 主队名称
            away_team: 客队名称  
            match_time: 比赛时间，格式："MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM"
            league: 联赛名称（可选）
            
        Returns:
            盘口数据字典
        """
        # 解析时间格式
        match_date = None
        match_datetime = None
        
        try:
            # 处理 "MM-DD HH:MM" 格式
            if '-' in match_time and len(match_time.split()[0].split('-')) == 2:
                current_year = datetime.now().year
                date_part, time_part = match_time.split()
                month, day = date_part.split('-')
                match_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                match_datetime = f"{match_date} {time_part}"
            # 处理 "YYYY-MM-DD HH:MM" 格式
            elif '-' in match_time and len(match_time.split()[0].split('-')) == 3:
                match_date = match_time.split()[0]
                match_datetime = match_time
        except:
            logger.warning(f"无法解析时间格式: {match_time}")
        
        return self.get_match_handicap(
            home_team=home_team,
            away_team=away_team,
            league=league,
            match_date=match_date,
            match_time=match_datetime
        )
    
    def get_match_result(
        self,
        home_team: str,
        away_team: str,
        match_time: str,
        league: Optional[str] = None
    ) -> Optional[Dict]:
        """
        查询比赛结果（比分）
        
        Args:
            home_team: 主队名称
            away_team: 客队名称
            match_time: 比赛时间，格式："MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM"
            league: 联赛名称（可选）
            
        Returns:
            结果字典，包含 score 字段（格式："2-1"）
        """
        # 解析时间格式
        match_date = None
        match_datetime = None
        
        try:
            # 处理 "MM-DD HH:MM" 格式
            if '-' in match_time and len(match_time.split()[0].split('-')) == 2:
                current_year = datetime.now().year
                date_part, time_part = match_time.split()
                month, day = date_part.split('-')
                match_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"
                match_datetime = f"{match_date} {time_part}"
            # 处理 "YYYY-MM-DD HH:MM" 格式
            elif '-' in match_time and len(match_time.split()[0].split('-')) == 3:
                match_date = match_time.split()[0]
                match_datetime = match_time
        except:
            logger.warning(f"无法解析时间格式: {match_time}")
            return None
        
        # 1. 搜索比赛ID
        fid = self.search_match_by_teams(home_team, away_team, league, match_date, match_datetime)
        
        if not fid:
            logger.warning(f"未找到比赛: {home_team} vs {away_team}")
            return None
        
        # 2. 访问比赛详情页获取比分
        try:
            detail_url = f"https://odds.500.com/fenxi/shuju-{fid}.shtml"
            response = self.session.get(detail_url, timeout=15)
            response.encoding = 'gb2312'
            html = response.text
            
            # 从HTML中提取比分
            # 查找 <span class="score">2-1</span> 或类似结构
            import re
            score_pattern = r'<span[^>]*class="score"[^>]*>(\d+)-(\d+)</span>'
            match = re.search(score_pattern, html)
            
            if match:
                home_score = match.group(1)
                away_score = match.group(2)
                score_str = f"{home_score}-{away_score}"
                
                return {
                    'score': score_str,
                    'home_score': int(home_score),
                    'away_score': int(away_score),
                    'fid': fid
                }
            
            # 备用方案：查找其他可能的比分标记
            score_pattern2 = r'比分[：:]\s*<[^>]+>(\d+)-(\d+)<'
            match2 = re.search(score_pattern2, html)
            
            if match2:
                home_score = match2.group(1)
                away_score = match2.group(2)
                score_str = f"{home_score}-{away_score}"
                
                return {
                    'score': score_str,
                    'home_score': int(home_score),
                    'away_score': int(away_score),
                    'fid': fid
                }
            
            logger.warning(f"未能从详情页提取比分: fid={fid}")
            return None
            
        except Exception as e:
            logger.exception(f"获取比分失败: {e}")
            return None
    
    # ========== 🔥 新增：数据存储和加载方法 ==========
    
    def save_daily_handicap_html(self, date_str: str, html: str) -> bool:
        """
        保存指定日期的500.com完场页面HTML
        
        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD
            html: HTML内容（已经是unicode字符串）
            
        Returns:
            是否保存成功
        """
        try:
            # 按日期创建子文件夹（data/YYYY/MM/DD）
            try:
                year, month, day = date_str.split("-")
                date_dir = self.data_dir / year / month / day
            except ValueError:
                # 兜底：无法拆分就退回一层目录
                date_dir = self.data_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)
            
            # 🔥 临时启用HTML保存（调试500彩票网结构变化）
            file_path = date_dir / "盘口数据.html"
            
            # 🔥 已禁用备份功能，直接覆盖旧文件
            
            print(f"  💾 正在保存盘口HTML: {file_path}")
            
            # 🔥 使用utf-8编码保存（避免编码问题）
            try:
                with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(html)
                print(f"  ✅ 盘口HTML保存成功: {file_path}")
                logger.info(f"✅ 保存盘口HTML成功: {file_path}")
            except Exception as e:
                # 如果utf-8失败，尝试gb2312
                try:
                    with open(file_path, 'w', encoding='gb2312', errors='ignore') as f:
                        f.write(html)
                    print(f"  ✅ 盘口HTML保存成功(gb2312): {file_path}")
                except:
                    print(f"  ❌ HTML保存失败: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.exception(f"保存盘口HTML失败: {e}")
            return False
    
    def save_daily_handicap_json(self, date_str: str, handicaps: Dict) -> bool:
        """
        保存指定日期的解析后盘口数据（JSON格式）
        
        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD
            handicaps: 盘口数据字典
            
        Returns:
            是否保存成功
        """
        try:
            # 按日期创建子文件夹（data/YYYY/MM/DD）
            try:
                year, month, day = date_str.split("-")
                date_dir = self.data_dir / year / month / day
            except ValueError:
                date_dir = self.data_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = date_dir / "盘口数据.json"
            
            # 🔥 始终保存（覆盖旧文件）
            print(f"  💾 正在保存盘口JSON: {file_path}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(handicaps, f, ensure_ascii=False, indent=2)
            
            print(f"  ✅ 盘口JSON保存成功: {file_path} ({len(handicaps)}场)")
            logger.info(f"✅ 保存盘口JSON成功: {file_path} ({len(handicaps)}场)")
            return True
            
        except Exception as e:
            logger.exception(f"保存盘口JSON失败: {e}")
            return False
    
    def load_daily_handicap_html(self, date_str: str) -> Optional[str]:
        """
        从本地加载指定日期的盘口HTML
        
        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD
            
        Returns:
            HTML内容，如果不存在返回None
        """
        try:
            # 优先从新的分级目录 data/YYYY/MM/DD 读取
            try:
                year, month, day = date_str.split("-")
                date_dir = self.data_dir / year / month / day
            except ValueError:
                # 兜底：无法拆分就退回一层目录
                date_dir = self.data_dir / date_str
            
            # 🔥 不再读取HTML文件（已优化：只使用JSON数据）
            # file_path = date_dir / "盘口数据.html"
            # 
            # # 兼容旧目录：data/YYYY-MM-DD/盘口数据.html
            # if not file_path.exists():
            #     legacy_dir = self.data_dir / date_str
            #     legacy_path = legacy_dir / "盘口数据.html"
            #     if not legacy_path.exists():
            #         return None
            #     file_path = legacy_path
            # 
            # logger.info(f"正在读取盘口HTML: {file_path}")
            
            # 直接返回None，让调用者使用JSON数据
            logger.info(f"已跳过HTML读取，请使用load_daily_handicap_json方法读取JSON数据")
            return None
            
        except Exception as e:
            logger.exception(f"加载盘口HTML失败: {e}")
            return None
    
    def load_daily_handicap_json(self, date_str: str) -> Optional[Dict]:
        """
        从本地加载指定日期的盘口JSON数据
        
        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD
            
        Returns:
            盘口数据字典，如果不存在返回None
        """
        try:
            # 优先从新的分级目录 data/YYYY/MM/DD 读取
            try:
                year, month, day = date_str.split("-")
                date_dir = self.data_dir / year / month / day
            except ValueError:
                date_dir = self.data_dir / date_str
            file_path = date_dir / "盘口数据.json"
            
            # 兼容旧目录：data/YYYY-MM-DD/盘口数据.json
            if not file_path.exists():
                legacy_dir = self.data_dir / date_str
                legacy_path = legacy_dir / "盘口数据.json"
                if not legacy_path.exists():
                    return None
                file_path = legacy_path
            
            with open(file_path, 'r', encoding='utf-8') as f:
                handicaps = json.load(f)
            
            logger.info(f"📂 从本地加载盘口JSON: {file_path} ({len(handicaps)}场)")
            return handicaps
            
        except Exception as e:
            logger.exception(f"加载盘口JSON失败: {e}")
            return None

    # ============================================================
    # 🔥 新增方法：盘口数据获取（完场回查 + 赛前推荐）
    # ============================================================
    
    def match_handicap(
        self,
        home: str,
        away: str,
        kickoff: str,
        daily_handicaps: Dict[str, Dict]
    ) -> Optional[Dict]:
        """
        从每日盘口数据中匹配单场比赛的盘口
        
        Args:
            home: 主队名称
            away: 客队名称
            kickoff: 开赛时间，格式：YYYY-MM-DD HH:MM
            daily_handicaps: 从fetch_daily_handicaps获取的每日盘口数据
            
        Returns:
            匹配到的盘口数据，如果未找到返回None
        """
        if not daily_handicaps:
            return None
        
        # 提取时间
        if ' ' in kickoff:
            time_str = kickoff.split(' ')[1][:5]
        else:
            time_str = kickoff[:5] if kickoff else ''
        
        # 调用已有的匹配方法
        return self.find_handicap_from_daily_data(
            daily_handicaps=daily_handicaps,
            home_team=home,
            away_team=away,
            match_time=time_str
        )
    
    def fetch_handicap_data(
        self,
        fid: str,
        company_id: str = "澳门"
    ) -> Optional[Dict]:
        """
        获取单场比赛的详细盘口数据（初盘 + 即时盘）
        
        从500.com的亚盘详情页面获取指定公司的盘口数据
        
        Args:
            fid: 比赛ID（500.com的fid）
            company_id: 公司名称或ID，默认"澳门"
            
        Returns:
            盘口详细数据，包含初盘和即时盘
        """
        try:
            # 构建亚盘详情页URL
            url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"
            logger.info(f"📊 获取详细盘口: {url}")
            
            response = self.session.get(url, timeout=15)
            response.encoding = 'gb2312'
            
            if response.status_code != 200:
                logger.warning(f"获取盘口详情失败: HTTP {response.status_code}")
                return None
            
            html = response.text
            
            if len(html) < 100:
                logger.warning(f"盘口详情页面为空")
                return None
            
            # 解析盘口数据
            return self._parse_handicap_detail_page(html, company_id)
            
        except Exception as e:
            logger.exception(f"获取盘口详情失败: {e}")
            return None
    
    def _parse_all_handicaps(self, html: str) -> Dict:
        """
        解析所有机构的亚盘数据
        
        Returns:
            {
                'primary': {...},  # 主要机构(澳门)数据
                'all_companies': [...],  # 所有机构数据列表
                'market_consensus': {...}  # 市场共识分析
            }
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', {'id': 'datatb'})
            if not table:
                return {}
            
            rows = table.find_all('tr')
            all_companies = []
            
            # 主要机构关键字映射（支持500.com的*号隐藏）
            # 尽量完整覆盖所有常见博彩公司
            company_keywords = {
                # 亚洲主流
                '澳门': ['门', '澳门', '*门'],
                '皇冠': ['皇冠', '*冠', 'Crown'],
                '金宝博': ['金*博', '金宝', '188'],
                '利记': ['利*', '利记', 'sbo'],
                '沙巴': ['沙巴', 'IBCBET'],
                
                # 欧洲主流
                'Bet365': ['365', 't3*5', 'bet365', 'Bet365'],
                '威廉希尔': ['威廉', '希尔', 'William', '伟*'],
                '立博': ['立博', 'Ladbrokes', 'lad'],
                'Pinnacle': ['Pinnacle', '平*', 'Pi****le', '平博'],
                'Interwetten': ['Inter', 'wetten', 'rw**t'],
                'bwin': ['bwin', 'b*in'],
                'Unibet': ['Unibet', 'uni'],
                'Betfair': ['Betfair', 'fair', '必发'],
                
                # 亚洲其他
                '易胜博': ['易*博', '易胜', 'Easybets'],
                '12bet': ['12**t', '12bet', '壹*博'],
                '18bet': ['18**t', '18bet'],
                '明升': ['M****on', '明*', 'Mansion', 'M88'],
                '盈禾': ['W****t', '盈*', 'Webet'],
                '乐天堂': ['乐天', 'fun', 'F**88'],
                '10bet': ['10bet', '10**t'],
                'SNAI': ['SNAI', 'sn*i'],
                
                # 欧洲其他  
                'Coral': ['Coral', 'cor*l'],
                'Paddy': ['Paddy', 'pad*y', 'Power'],
                'Skybet': ['Skybet', 'sky'],
                'Betsson': ['Betsson', 'tss*n'],
                'Nordicbet': ['Nordic', 'nord'],
                'Expekt': ['Expekt', 'xp**t'],
                'Titanbet': ['Titan', 'tit*n'],
                'Sportingbet': ['Sporting', 'port*ng'],
                
                # 其他
                'bet-at-home': ['home', 'h*me'],
                '香港马会': ['香港', '马会', 'HKJC'],
                'Singbet': ['Sing', 'sing'],
                'SBObet': ['SBO', 'sbo'],
            }
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 12:
                    continue
                
                company_name = cells[1].get_text(strip=True)
                if not company_name or company_name == '公司':
                    continue
                
                try:
                    # 解析该公司数据
                    current_home = self._extract_odds(cells[3])
                    current_handicap_text = cells[4].get_text(strip=True)
                    current_away = self._extract_odds(cells[5])
                    initial_home = self._extract_odds(cells[9])
                    initial_handicap_text = cells[10].get_text(strip=True)
                    initial_away = self._extract_odds(cells[11])
                    
                    if current_home == 0 and current_away == 0:
                        continue
                    
                    # 识别机构类型
                    company_type = None
                    for key, keywords in company_keywords.items():
                        if any(kw in company_name for kw in keywords):
                            company_type = key
                            break
                    
                    # 如果没匹配到，清理原始名字作为类型（去除重复和*号）
                    if not company_type:
                        # 500.com显示格式是"名字名字"（重复两遍），取一半
                        clean_name = company_name.replace('*', '')
                        if len(clean_name) >= 4 and clean_name[:len(clean_name)//2] == clean_name[len(clean_name)//2:]:
                            clean_name = clean_name[:len(clean_name)//2]
                        company_type = clean_name if clean_name else company_name
                    
                    company_data = {
                        'company_name': company_name,
                        'company_type': company_type,
                        'current_handicap': self.parse_handicap(current_handicap_text),
                        'current_handicap_text': current_handicap_text,
                        'current_home_odds': current_home,
                        'current_away_odds': current_away,
                        'initial_handicap': self.parse_handicap(initial_handicap_text),
                        'initial_handicap_text': initial_handicap_text,
                        'initial_home_odds': initial_home,
                        'initial_away_odds': initial_away,
                    }
                    all_companies.append(company_data)
                    
                except Exception as e:
                    continue
            
            if not all_companies:
                return {}
            
            # 找主要机构(澳门)
            primary = None
            for c in all_companies:
                if c['company_type'] == '澳门':
                    primary = c
                    break
            if not primary:
                primary = all_companies[0]
            
            # 计算市场共识
            handicaps = [c['current_handicap'] for c in all_companies if c['current_handicap'] != 0]
            if handicaps:
                avg_handicap = sum(handicaps) / len(handicaps)
                handicap_std = (sum((h - avg_handicap)**2 for h in handicaps) / len(handicaps)) ** 0.5
                
                # 统计各盘口数量
                handicap_counts = {}
                for h in handicaps:
                    handicap_counts[h] = handicap_counts.get(h, 0) + 1
                most_common = max(handicap_counts, key=handicap_counts.get)
                
                market_consensus = {
                    'avg_handicap': round(avg_handicap, 3),
                    'handicap_std': round(handicap_std, 3),
                    'most_common_handicap': most_common,
                    'consensus_count': handicap_counts[most_common],
                    'total_companies': len(all_companies),
                    'consensus_ratio': round(handicap_counts[most_common] / len(all_companies), 2),
                }
            else:
                market_consensus = {}
            
            logger.info(f"✅ 解析{len(all_companies)}家机构盘口, 共识盘口:{market_consensus.get('most_common_handicap')}")
            
            return {
                'primary': primary,
                'all_companies': all_companies,
                'market_consensus': market_consensus
            }
            
        except Exception as e:
            logger.exception(f"解析多机构盘口失败: {e}")
            return {}
    
    def _parse_handicap_detail_page(
        self,
        html: str,
        company_id: str = "澳门"
    ) -> Optional[Dict]:
        """
        解析亚盘详情页面，提取指定公司的盘口数据
        
        500.com表格结构（14列）：
        [0]: 序号
        [1]: 公司名称（部分隐藏，如"*门"代表"澳门"）
        [2]: 即时盘合并显示
        [3]: 即时主水
        [4]: 即时盘口
        [5]: 即时客水
        [6]: 变化标记
        [7]: 即时盘时间
        [8]: 初盘合并显示
        [9]: 初盘主水
        [10]: 初盘盘口
        [11]: 初盘客水
        [12]: 初盘时间
        [13]: 走势
        
        Args:
            html: 页面HTML内容
            company_id: 公司名称或ID（支持"澳门"、"门"等）
            
        Returns:
            盘口数据字典
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 🔥 新增：同时获取所有机构数据
            all_handicaps = self._parse_all_handicaps(html)
            
            # 查找盘口表格
            table = soup.find('table', {'id': 'datatb'})
            if not table:
                logger.warning("未找到盘口表格 (id=datatb)")
                return None
            
            # 查找目标公司的行
            rows = table.find_all('tr')
            target_row = None
            
            # 匹配关键字（支持部分隐藏的公司名）
            match_keywords = ['门', '澳门', '*门']
            if company_id not in match_keywords:
                match_keywords.insert(0, company_id)
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) > 1:
                    company_name = cells[1].get_text(strip=True)
                    # 检查是否匹配目标公司
                    for keyword in match_keywords:
                        if keyword in company_name:
                            target_row = row
                            logger.debug(f"找到目标公司: {company_name}")
                            break
                    if target_row:
                        break
            
            if not target_row:
                # 如果没找到澳门，使用第一个有效行（通常是88bet）
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 12:
                        target_row = row
                        logger.info(f"未找到{company_id}，使用第一个有效行")
                        break
            
            if not target_row:
                logger.warning(f"未找到{company_id}的盘口数据")
                return None
            
            # 解析盘口数据
            cells = target_row.find_all(['td', 'th'])
            
            if len(cells) < 12:
                logger.warning(f"盘口数据列数不足: {len(cells)}")
                return None
            
            try:
                result = {
                    'source': '500.com',
                    'company_id': company_id,
                    'company_name': cells[1].get_text(strip=True),
                }
                
                # 解析即时盘数据（列3-5）
                current_home_odds = self._extract_odds(cells[3])
                current_handicap_text = cells[4].get_text(strip=True)
                current_away_odds = self._extract_odds(cells[5])
                
                result['current_handicap_text'] = current_handicap_text
                result['current_handicap'] = self.parse_handicap(current_handicap_text)
                result['current_home_odds'] = current_home_odds
                result['current_away_odds'] = current_away_odds
                
                # 解析变化趋势（列6）
                if len(cells) > 6:
                    trend_text = cells[6].get_text(strip=True)
                    if '↑' in cells[3].get_text() or '升' in trend_text:
                        result['current_trend'] = '升'
                    elif '↓' in cells[3].get_text() or '降' in trend_text:
                        result['current_trend'] = '降'
                    else:
                        result['current_trend'] = ''
                
                # 解析初盘数据（列9-11）
                initial_home_odds = self._extract_odds(cells[9])
                initial_handicap_text = cells[10].get_text(strip=True)
                initial_away_odds = self._extract_odds(cells[11])
                
                result['initial_handicap_text'] = initial_handicap_text
                result['initial_handicap'] = self.parse_handicap(initial_handicap_text)
                result['initial_home_odds'] = initial_home_odds
                result['initial_away_odds'] = initial_away_odds
                
                # 🔥 新增：添加多机构数据
                if all_handicaps:
                    result['all_companies'] = all_handicaps.get('all_companies', [])
                    result['market_consensus'] = all_handicaps.get('market_consensus', {})
                
                logger.info(f"✅ 解析盘口成功: {result.get('company_name')} "
                           f"即时={current_handicap_text}({current_home_odds}/{current_away_odds}) "
                           f"初盘={initial_handicap_text}({initial_home_odds}/{initial_away_odds}) "
                           f"共{len(result.get('all_companies', []))}家机构")
                return result
                
            except Exception as e:
                logger.warning(f"解析盘口数据失败: {e}")
                return None
            
        except Exception as e:
            logger.exception(f"解析盘口详情页失败: {e}")
            return None
    
    def _extract_odds(self, cell) -> float:
        """从单元格中提取赔率数值"""
        try:
            text = cell.get_text(strip=True)
            # 移除非数字字符（保留小数点）
            text = re.sub(r'[^\d.]', '', text)
            return float(text) if text else 0.0
        except:
            return 0.0
    
    def get_handicap(
        self,
        home: str,
        away: str,
        kickoff: str,
        league: str = None
    ) -> Optional[Dict]:
        """
        获取比赛的完整盘口数据（用于赛前推荐）
        
        流程：
        1. 先从每日盘口数据中查找基础盘口
        2. 如果找到fid，再获取详细的初盘和即时盘数据
        
        Args:
            home: 主队名称
            away: 客队名称
            kickoff: 开赛时间
            league: 联赛名称（可选）
            
        Returns:
            完整的盘口数据
        """
        try:
            # 提取日期
            if ' ' in kickoff:
                match_date = kickoff.split(' ')[0]
            else:
                match_date = kickoff
            
            # 1. 获取每日盘口数据
            daily_handicaps = self.fetch_daily_handicaps(match_date, use_cache=True)
            
            if not daily_handicaps:
                logger.warning(f"未获取到 {match_date} 的盘口数据")
                return None
            
            # 2. 匹配比赛
            handicap_data = self.match_handicap(
                home=home,
                away=away,
                kickoff=kickoff,
                daily_handicaps=daily_handicaps
            )
            
            if not handicap_data:
                logger.warning(f"未匹配到盘口: {home} vs {away}")
                return None
            
            # 3. 获取详细盘口数据（初盘 + 即时盘）
            fid = handicap_data.get('fid')
            if fid:
                detailed_data = self.fetch_handicap_data(fid, company_id="澳门")
                if detailed_data:
                    # 合并数据
                    handicap_data.update(detailed_data)
            
            return handicap_data
            
        except Exception as e:
            logger.exception(f"获取盘口失败: {e}")
            return None
    
    def get_match_handicap(
        self,
        home_team: str,
        away_team: str,
        match_date: str = None,
        match_time: str = None,
        league: str = None,
        company_id: str = "澳门"
    ) -> Optional[Dict]:
        """
        获取比赛盘口数据（兼容旧接口）
        
        Args:
            home_team: 主队名称
            away_team: 客队名称
            match_date: 比赛日期
            match_time: 比赛时间
            league: 联赛名称
            company_id: 公司名称，默认"澳门"
            
        Returns:
            盘口数据
        """
        # 构建kickoff时间
        if match_date and match_time:
            kickoff = f"{match_date} {match_time}"
        elif match_date:
            kickoff = match_date
        else:
            kickoff = datetime.now().strftime("%Y-%m-%d")
        
        return self.get_handicap(
            home=home_team,
            away=away_team,
            kickoff=kickoff,
            league=league
        )


    # ============================================================
    # 🔥 新增方法：完整盘口数据获取
    # ============================================================
    
    def is_handicap_complete(self, handicap_data: Dict) -> bool:
        """
        检查盘口数据是否完整（包含初始盘口）
        
        Args:
            handicap_data: 盘口数据字典
            
        Returns:
            True if contains initial_handicap, False otherwise
        """
        if not handicap_data:
            return False
        
        # 检查是否有初始盘口字段且不为None
        initial_handicap = handicap_data.get('initial_handicap')
        return initial_handicap is not None
    
    def fetch_complete_handicaps(
        self, 
        match_date: str, 
        use_cache: bool = True,
        rate_limit_delay: float = 0.5,
        max_matches: int = None
    ) -> Dict[str, Dict]:
        """
        批量获取完整盘口数据（包含初始盘口和即时盘口）
        
        Args:
            match_date: 比赛日期，格式：YYYY-MM-DD
            use_cache: 是否使用本地缓存
            rate_limit_delay: 请求间隔（秒），避免过载
            max_matches: 最大处理比赛数（用于测试）
            
        Returns:
            字典：{match_key: complete_handicap_data}
        """
        import time
        
        logger.info(f"📊 开始获取完整盘口数据: {match_date}")
        
        # 1. 先获取基础盘口数据（即时盘口）
        daily_handicaps = self.fetch_daily_handicaps(match_date, use_cache=use_cache)
        
        if not daily_handicaps:
            logger.warning(f"未获取到 {match_date} 的基础盘口数据")
            return {}
        
        logger.info(f"  基础盘口数据: {len(daily_handicaps)} 场")
        
        # 2. 对每个有fid的比赛获取详细盘口
        complete_count = 0
        skip_count = 0
        fetch_count = 0
        error_count = 0
        
        matches_to_process = list(daily_handicaps.items())
        if max_matches:
            matches_to_process = matches_to_process[:max_matches]
        
        for i, (match_key, handicap_data) in enumerate(matches_to_process):
            # 检查是否已有完整数据
            if self.is_handicap_complete(handicap_data):
                skip_count += 1
                continue
            
            fid = handicap_data.get('fid')
            if not fid:
                logger.debug(f"  跳过无fid的比赛: {match_key}")
                continue
            
            # 获取详细盘口数据
            try:
                detailed_data = self.fetch_handicap_data(fid, company_id="澳门")
                
                if detailed_data:
                    # 合并数据
                    handicap_data.update(detailed_data)
                    complete_count += 1
                    fetch_count += 1
                    
                    if fetch_count % 10 == 0:
                        logger.info(f"  进度: {fetch_count}/{len(matches_to_process) - skip_count}")
                else:
                    error_count += 1
                    logger.debug(f"  未获取到详细盘口: {match_key}")
                
                # 速率限制
                if rate_limit_delay > 0:
                    time.sleep(rate_limit_delay)
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"  获取详细盘口失败 {match_key}: {e}")
        
        logger.info(f"✅ 完整盘口获取完成: 成功={complete_count}, 跳过={skip_count}, 失败={error_count}")
        
        # 3. 保存更新后的数据
        self.save_daily_handicap_json(match_date, daily_handicaps)
        
        return daily_handicaps

    def fetch_asian_data(self, fid: str) -> Optional[Dict]:
        """
        获取500.com亚盘/让球指数数据（所有机构）
        
        URL: https://odds.500.com/fenxi/yazhi-{fid}.shtml
        
        Args:
            fid: 比赛ID
            
        Returns:
            让球盘口数据字典，包含所有机构数据
        """
        url = f"https://odds.500.com/fenxi/yazhi-{fid}.shtml"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Referer': 'https://odds.500.com/',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.encoding = 'gb2312'
            
            if response.status_code != 200:
                logger.warning(f"获取亚盘数据失败: HTTP {response.status_code}")
                return None
            
            return self._parse_asian_page(response.text)
            
        except Exception as e:
            logger.warning(f"获取亚盘数据失败: {e}")
            return None
    
    def _parse_asian_page(self, html: str) -> Optional[Dict]:
        """解析亚盘/让球指数页面，获取所有机构数据"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', {'id': 'datatb'})
            
            if not table:
                return None
            
            rows = table.find_all('tr')
            all_companies = []
            
            # 公司关键字映射
            company_keywords = {
                '澳门': ['门', '澳门'],
                '皇冠': ['皇冠', '*冠'],
                '大巨': ['大巨'],
                'Bet365': ['365', 't3*5'],
                '威廉希尔': ['威廉', '伟*'],
                '立博': ['立*'],
                '易胜博': ['易*博'],
                '利记': ['利*'],
                'Pinnacle': ['Pi****le', '平*'],
                'SNAI': ['S**I'],
                '金宝博': ['金*博'],
                '香港马会': ['香**会'],
                'bwin': ['B**n'],
                '10bet': ['10**t'],
                '12bet': ['12**t'],
                '18bet': ['18**t'],
                '明升': ['M****on', '明*'],
                '必发': ['必*'],
                'Interwetten': ['rw**t', 'Inter'],
                'Coral': ['C***l'],
            }
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 12:
                    continue
                
                company_name = cells[1].get_text(strip=True)
                if not company_name or '公司' in company_name or '筛选' in company_name:
                    continue
                
                # 亚盘列索引: [3]即时主水 [4]即时盘口 [5]即时客水 [9]初始主水 [10]初始盘口 [11]初始客水
                curr_home = self._extract_odds(cells[3])
                curr_handicap = cells[4].get_text(strip=True).replace('↑', '').replace('↓', '')
                curr_away = self._extract_odds(cells[5])
                
                init_home = self._extract_odds(cells[9])
                init_handicap = cells[10].get_text(strip=True).replace('↑', '').replace('↓', '')
                init_away = self._extract_odds(cells[11])
                
                change_time = cells[7].get_text(strip=True) if len(cells) > 7 else ''
                
                if curr_home == 0 and curr_away == 0:
                    continue
                
                # 识别公司
                company_type = None
                for key, keywords in company_keywords.items():
                    if any(kw in company_name for kw in keywords):
                        company_type = key
                        break
                if not company_type:
                    clean = company_name.replace('*', '')
                    if len(clean) >= 4 and clean[:len(clean)//2] == clean[len(clean)//2:]:
                        clean = clean[:len(clean)//2]
                    company_type = clean if clean else company_name
                
                # 解析盘口值
                curr_hdp = self._parse_handicap_value(curr_handicap)
                init_hdp = self._parse_handicap_value(init_handicap)
                
                company_data = {
                    'company': company_type,
                    'company_name': company_name,
                    'curr_handicap': curr_handicap,
                    'curr_handicap_value': curr_hdp,
                    'curr_home_odds': curr_home,
                    'curr_away_odds': curr_away,
                    'init_handicap': init_handicap,
                    'init_handicap_value': init_hdp,
                    'init_home_odds': init_home,
                    'init_away_odds': init_away,
                    'handicap_change': round(curr_hdp - init_hdp, 2) if curr_hdp and init_hdp else 0,
                    'change_time': change_time
                }
                
                all_companies.append(company_data)
            
            if not all_companies:
                return None
            
            # 提取特定公司
            aomen = next((c for c in all_companies if c['company'] == '澳门'), {})
            huangguan = next((c for c in all_companies if c['company'] == '皇冠'), {})
            bet365 = next((c for c in all_companies if c['company'] == 'Bet365'), {})
            
            # 统计盘口变化
            hdp_up = sum(1 for c in all_companies if c.get('handicap_change', 0) > 0)
            hdp_down = sum(1 for c in all_companies if c.get('handicap_change', 0) < 0)
            
            return {
                'all_companies': all_companies,
                'aomen': aomen,
                'huangguan': huangguan,
                'bet365': bet365,
                'avg_handicap': round(sum(c.get('curr_handicap_value', 0) for c in all_companies if c.get('curr_handicap_value')) / max(1, len([c for c in all_companies if c.get('curr_handicap_value')])), 2),
                'handicap_up_count': hdp_up,
                'handicap_down_count': hdp_down,
            }
            
        except Exception as e:
            logger.warning(f"解析亚盘页面失败: {e}")
            return None

    def fetch_ou_data(self, fid: str) -> Optional[Dict]:
        """
        获取500.com大小球指数数据
        
        URL: https://odds.500.com/fenxi/daxiao-{fid}.shtml
        
        Args:
            fid: 比赛ID
            
        Returns:
            大小球数据字典
        """
        url = f"https://odds.500.com/fenxi/daxiao-{fid}.shtml"
        
        try:
            response = self.session.get(url, timeout=15)
            response.encoding = 'gb2312'
            
            if response.status_code != 200:
                logger.warning(f"获取大小球数据失败: HTTP {response.status_code}")
                return None
            
            return self._parse_ou_page(response.text)
            
        except Exception as e:
            logger.warning(f"获取大小球数据失败: {e}")
            return None
    
    def _parse_ou_page(self, html: str) -> Optional[Dict]:
        """解析大小球指数页面"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', {'id': 'datatb'})
            
            if not table:
                return None
            
            rows = table.find_all('tr')
            all_companies = []
            
            # 公司关键字映射
            company_keywords = {
                '澳门': ['门', '澳门'],
                '皇冠': ['皇冠', '*冠'],
                '大巨': ['大巨'],
                'Bet365': ['365', 't3*5'],
                '威廉希尔': ['威廉', '伟*'],
                '立博': ['立*'],
                '易胜博': ['易*博'],
                '利记': ['利*'],
                'Pinnacle': ['Pi****le', '平*'],
                'SNAI': ['S**I'],
                '金宝博': ['金*博'],
                '香港马会': ['香**会'],
                'bwin': ['B**n'],
                '10bet': ['10**t'],
                '12bet': ['12**t'],
                '18bet': ['18**t'],
                '明升': ['M****on', '明*'],
                '必发': ['必*'],
                'Interwetten': ['rw**t', 'Inter'],
                'Coral': ['C***l'],
            }
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 12:
                    continue
                
                company_name = cells[1].get_text(strip=True)
                if not company_name or '公司' in company_name or '筛选' in company_name:
                    continue
                
                # 索引: [3]即时大 [4]即时盘 [5]即时小 [9]初始大 [10]初始盘 [11]初始小
                curr_over = self._extract_odds(cells[3])
                curr_line = cells[4].get_text(strip=True).replace('↑', '').replace('↓', '')
                curr_under = self._extract_odds(cells[5])
                
                init_over = self._extract_odds(cells[9])
                init_line = cells[10].get_text(strip=True).replace('↑', '').replace('↓', '')
                init_under = self._extract_odds(cells[11])
                
                change_time = cells[7].get_text(strip=True) if len(cells) > 7 else ''
                
                if curr_over == 0 and curr_under == 0:
                    continue
                
                # 识别公司
                company_type = None
                for key, keywords in company_keywords.items():
                    if any(kw in company_name for kw in keywords):
                        company_type = key
                        break
                if not company_type:
                    clean = company_name.replace('*', '')
                    if len(clean) >= 4 and clean[:len(clean)//2] == clean[len(clean)//2:]:
                        clean = clean[:len(clean)//2]
                    company_type = clean if clean else company_name
                
                # 解析盘口值
                curr_val = self._parse_ou_line(curr_line)
                init_val = self._parse_ou_line(init_line)
                
                company_data = {
                    'company': company_type,
                    'company_name': company_name,
                    'curr_line': curr_line,
                    'curr_line_value': curr_val,
                    'curr_over': curr_over,
                    'curr_under': curr_under,
                    'init_line': init_line,
                    'init_line_value': init_val,
                    'init_over': init_over,
                    'init_under': init_under,
                    'line_change': round(curr_val - init_val, 2),
                    'change_time': change_time,
                }
                all_companies.append(company_data)
            
            if not all_companies:
                return None
            
            # 统计
            lines = [c['curr_line_value'] for c in all_companies]
            from collections import Counter
            line_counts = Counter(lines)
            most_common = line_counts.most_common(1)[0][0] if line_counts else 2.5
            avg_line = sum(lines) / len(lines) if lines else 2.5
            
            # 盘口变化统计
            down_count = sum(1 for c in all_companies if c['line_change'] < 0)
            up_count = sum(1 for c in all_companies if c['line_change'] > 0)
            
            # 找澳门
            aomen = next((c for c in all_companies if c['company'] == '澳门'), None)
            
            return {
                'all_companies': all_companies,
                'total_companies': len(all_companies),
                'avg_line': round(avg_line, 2),
                'most_common_line': most_common,
                'line_down_count': down_count,
                'line_up_count': up_count,
                'aomen': aomen,
            }
            
        except Exception as e:
            logger.warning(f"解析大小球页面失败: {e}")
            return None
    
    def _parse_ou_line(self, line_str: str) -> float:
        """解析大小球盘口字符串为数值"""
        try:
            line_str = line_str.strip()
            if '/' in line_str:
                parts = line_str.split('/')
                return (float(parts[0]) + float(parts[1])) / 2
            return float(line_str)
        except:
            return 2.5


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    client = Lottery500Client()
    
    # 测试盘口解析
    print("=== 测试盘口解析 ===")
    test_cases = [
        ("球半", True),
        ("受平/半", True),
        ("平手", True),
        ("-1.5", True),
        ("+0.25", True),
        ("一球", True),
        ("受让一球", True),
    ]
    
    for handicap_str, is_home in test_cases:
        value = client.parse_handicap(handicap_str, is_home)
        print(f"{handicap_str} -> {value}")
    
    # 测试搜索比赛（需要实际的球队名称）
    print("\n=== 测试搜索比赛 ===")
    # fid = client.search_match_by_teams("曼联", "利物浦")
    # print(f"比赛ID: {fid}")
