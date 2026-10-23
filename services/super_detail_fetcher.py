"""
超级明细数据获取器

支持获取：
1. 标盘明细 (matchDetails.php)
2. 大小球明细 (ouDetails.php)
3. 让球指数明细 (AisaDetails.php) - 亚盘
4. 比分明细 (CorrectDetails.php) - 波胆

URL构造规则：
- 所有明细页面使用base64编码的getuid参数
- getuid解码后格式: tmiid=xxx&marketid=xxx&home_sid=xxx&away_sid=xxx&opentime=xxx&hdp=xxx&fff=xxx&teammsg=xxx
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlencode, quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_HOST = "https://www.bifaw.com"

# 明细页面URL模板
DETAIL_URLS = {
    "standard": f"{BASE_HOST}/bifaw/matchDetails.php",      # 标盘明细
    "ou": f"{BASE_HOST}/bifaw/ouDetails.php",               # 大小球明细
    "handicap": f"{BASE_HOST}/bifaw/AisaDetails.php",       # 让球指数明细（亚盘）
    "correct_score": f"{BASE_HOST}/bifaw/CorrectDetails.php",  # 比分明细（波胆）
}


class SuperDetailFetcher:
    """
    超级明细数据获取器
    
    用于获取比赛的所有类型明细数据
    """
    
    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        """
        初始化获取器
        
        Args:
            cookies: 已登录的cookies字典
        """
        self.cookies = cookies or {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://www.bifaw.com/',
        })
        if cookies:
            self.session.cookies.update(cookies)
    
    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """设置cookies"""
        self.cookies = cookies
        self.session.cookies.update(cookies)
    
    def construct_getuid(
        self,
        match_id: str,
        market_id: str,
        home_sid: str,
        away_sid: str,
        opentime: str,
        team_msg: str,
        hdp: Optional[str] = None,
        fff: str = "4"
    ) -> str:
        """
        构造getuid参数（base64编码）
        
        Args:
            match_id: 比赛ID (tmiid)
            market_id: 市场ID (marketid)
            home_sid: 主队SID
            away_sid: 客队SID
            opentime: 开赛时间戳
            team_msg: 比赛信息（URL编码）
            hdp: 让球数（可选，用于让球指数）
            fff: 标识符（0=实时，4=完场回查）
        
        Returns:
            base64编码的getuid字符串
        """
        # 构造参数字符串
        params_parts = [
            f"tmiid={match_id}",
            f"marketid={market_id}",
            f"home_sid={home_sid}",
            f"away_sid={away_sid}",
            f"opentime={opentime}",
        ]
        
        # 添加让球数（如果有）
        if hdp is not None:
            params_parts.append(f"hdp={hdp}")
        
        params_parts.append(f"fff={fff}")
        params_parts.append(f"teammsg={quote(team_msg, safe='')}")
        
        params_str = "&".join(params_parts)
        
        # Base64编码
        getuid = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')
        
        return getuid
    
    def construct_handicap_url(
        self,
        match_id: str,
        market_id: str,
        home_sid: str,
        away_sid: str,
        opentime: str,
        team_msg: str,
        hdp: str,
        fff: str = "4"
    ) -> str:
        """
        构造让球指数明细URL (AisaDetails.php)
        
        Args:
            match_id: 比赛ID
            market_id: 市场ID
            home_sid: 主队SID
            away_sid: 客队SID
            opentime: 开赛时间戳
            team_msg: 比赛信息
            hdp: 让球数（如 -0.75）
            fff: 标识符
        
        Returns:
            完整的让球指数明细URL
        """
        getuid = self.construct_getuid(
            match_id=match_id,
            market_id=market_id,
            home_sid=home_sid,
            away_sid=away_sid,
            opentime=opentime,
            team_msg=team_msg,
            hdp=hdp,
            fff=fff
        )
        
        return f"{DETAIL_URLS['handicap']}?getuid={getuid}"
    
    def construct_correct_score_url(
        self,
        match_id: str,
        market_id: str,
        opentime: str,
        team_msg: str,
        fff: str = "4"
    ) -> str:
        """
        构造比分明细URL (CorrectDetails.php)
        
        注意：比分明细不需要home_sid和away_sid
        
        Args:
            match_id: 比赛ID
            market_id: 市场ID
            opentime: 开赛时间戳
            team_msg: 比赛信息（包含比分）
            fff: 标识符
        
        Returns:
            完整的比分明细URL
        """
        # 比分明细的参数格式略有不同
        params_parts = [
            f"tmiid={match_id}",
            f"marketid={market_id}",
            f"opentime={opentime}",
            f"fff={fff}",
            f"teammsg={quote(team_msg, safe='')}"
        ]
        
        params_str = "&".join(params_parts)
        getuid = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')
        
        return f"{DETAIL_URLS['correct_score']}?getuid={getuid}"
    
    def fetch_handicap_detail(
        self,
        url: str,
        timeout: int = 30
    ) -> Optional[str]:
        """
        获取让球指数明细页面HTML
        
        Args:
            url: 让球指数明细URL
            timeout: 超时时间
        
        Returns:
            页面HTML内容，失败返回None
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                logger.warning(f"让球指数请求失败: HTTP {response.status_code}")
                return None
            
            # 检查是否需要登录
            if '提交的参数有误' in response.text or '请先登录' in response.text:
                logger.warning("让球指数页面需要登录或参数错误")
                return None
            
            # 检查是否是有效页面
            if 'AisaDetails' not in response.text and '让球' not in response.text:
                logger.warning("未获取到有效的让球指数页面")
                return None
            
            return response.text
            
        except Exception as e:
            logger.error(f"获取让球指数明细失败: {e}")
            return None
    
    def fetch_correct_score_detail(
        self,
        url: str,
        timeout: int = 30
    ) -> Optional[str]:
        """
        获取比分明细页面HTML
        
        Args:
            url: 比分明细URL
            timeout: 超时时间
        
        Returns:
            页面HTML内容，失败返回None
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                logger.warning(f"比分明细请求失败: HTTP {response.status_code}")
                return None
            
            # 检查是否需要登录
            if '提交的参数有误' in response.text or '请先登录' in response.text:
                logger.warning("比分明细页面需要登录或参数错误")
                return None
            
            # 检查是否是有效页面
            if 'CorrectDetails' not in response.text and '比分' not in response.text:
                logger.warning("未获取到有效的比分明细页面")
                return None
            
            return response.text
            
        except Exception as e:
            logger.error(f"获取比分明细失败: {e}")
            return None
    
    def fetch_all_details(
        self,
        match_info: Dict,
        include_standard: bool = True,
        include_ou: bool = True,
        include_handicap: bool = True,
        include_correct_score: bool = True,
        timeout: int = 30
    ) -> Dict[str, Optional[str]]:
        """
        获取比赛的所有类型明细HTML
        
        Args:
            match_info: 比赛信息字典
            include_standard: 是否获取标盘明细
            include_ou: 是否获取大小球明细
            include_handicap: 是否获取让球指数明细
            include_correct_score: 是否获取比分明细
            timeout: 超时时间
        
        Returns:
            各类型明细HTML的字典
        """
        results = {
            "standard_html": None,
            "ou_html": None,
            "handicap_html": None,
            "correct_score_html": None,
        }
        
        # 提取必要参数
        match_id = match_info.get('match_id')
        market_id = match_info.get('market_id')
        home_sid = match_info.get('home_sid')
        away_sid = match_info.get('away_sid')
        opentime = match_info.get('opentime')
        
        league = match_info.get('league', '')
        home = match_info.get('home', '')
        away = match_info.get('away', '')
        score = match_info.get('score', '')
        
        # 构造team_msg
        team_msg = f"{league}@{home}@{away}@{score}"
        
        # 获取让球数
        hdp = match_info.get('handicap')
        if hdp is None:
            hdp_preview = match_info.get('handicap_preview', {})
            hdp = hdp_preview.get('handicap')
        
        # 获取让球指数明细
        if include_handicap and hdp is not None:
            try:
                hdp_url = self.construct_handicap_url(
                    match_id=match_id,
                    market_id=market_id,
                    home_sid=home_sid,
                    away_sid=away_sid,
                    opentime=opentime,
                    team_msg=team_msg,
                    hdp=str(hdp),
                    fff="4"
                )
                logger.info(f"获取让球指数明细: {hdp_url[:100]}...")
                results["handicap_html"] = self.fetch_handicap_detail(hdp_url, timeout)
                time.sleep(0.5)  # 避免请求过快
            except Exception as e:
                logger.error(f"获取让球指数明细失败: {e}")
        
        # 获取比分明细
        if include_correct_score:
            try:
                cs_url = self.construct_correct_score_url(
                    match_id=match_id,
                    market_id=market_id,
                    opentime=opentime,
                    team_msg=team_msg,
                    fff="4"
                )
                logger.info(f"获取比分明细: {cs_url[:100]}...")
                results["correct_score_html"] = self.fetch_correct_score_detail(cs_url, timeout)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"获取比分明细失败: {e}")
        
        return results


def parse_url_getuid(url: str) -> Dict[str, str]:
    """
    解析URL中的getuid参数
    
    Args:
        url: 包含getuid参数的URL
    
    Returns:
        解码后的参数字典
    """
    import re
    from urllib.parse import unquote
    
    # 提取getuid参数
    match = re.search(r'getuid=([^&]+)', url)
    if not match:
        return {}
    
    getuid = match.group(1)
    
    try:
        # Base64解码
        decoded = base64.b64decode(getuid).decode('utf-8')
        
        # 解析参数
        params = {}
        for part in decoded.split('&'):
            if '=' in part:
                key, value = part.split('=', 1)
                params[key] = unquote(value)
        
        return params
        
    except Exception as e:
        logger.error(f"解析getuid失败: {e}")
        return {}


def extract_handicap_from_url(url: str) -> Optional[float]:
    """
    从URL中提取让球数
    
    Args:
        url: 让球指数明细URL
    
    Returns:
        让球数，如 -0.75
    """
    params = parse_url_getuid(url)
    hdp = params.get('hdp')
    
    if hdp:
        try:
            return float(hdp)
        except:
            pass
    
    return None
