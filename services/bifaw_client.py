from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from parser.html_parser import parse_match_list
from parser.pdf_parser import HEADER_KEYWORD
from utils.chrome_env import resolve_chrome_binary, resolve_chromedriver
from services.baidu_ocr import get_baidu_ocr
from services.local_ocr import get_local_ocr
from services.auto_reconnect import AutoReconnectManager, get_reconnect_manager

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE_DIR / "cookies.json"
DOWNLOAD_DIR = BASE_DIR / "downloads"
CONFIG_FILE = BASE_DIR / "config.json"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = BASE_DIR / "debug_html"

BASE_HOST = "https://www.bifaw.com"
LOGIN_URL = f"{BASE_HOST}/member/login.php"

USERNAME_INPUT = (By.ID, "txtUsername")
PASSWORD_INPUT = (By.ID, "txtPassword")
CAPTCHA_INPUT = (By.ID, "vdcode")
CAPTCHA_IMAGE = (By.ID, "vdimgck")
LOGIN_BUTTON = (By.ID, "submitImage")  # 登录按钮是image类型
# 登录成功标记：多种检测方式
LOGIN_SUCCESS_MARKS = [
    (By.XPATH, "//a[contains(@href,'logout') or contains(text(),'退出')]"),
    (By.XPATH, "//a[contains(@href,'member') and not(contains(@href,'login'))]"),
    (By.XPATH, "//*[contains(text(),'欢迎') or contains(text(),'您好')]"),
    (By.ID, "_userlogin"),
]
# 登录失败标记
LOGIN_FAILURE_MARKS = [
    (By.XPATH, "//*[contains(text(),'验证码错误') or contains(text(),'密码错误')]"),
    (By.XPATH, "//*[contains(text(),'登录失败') or contains(text(),'请重新')]"),
]

SESSION_EXPIRE_SECONDS = 300
SERVEODDS_URL = f"{BASE_HOST}/bifaw/serveodds.php"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
)

DETAIL_KEYWORDS: Tuple[str, ...] = (
    HEADER_KEYWORD,
    "买家挂牌",
    "卖家挂牌",
    "最新成交",
    "成交量",
)

logger = logging.getLogger(__name__)


@dataclass
class LoginSession:
    driver: webdriver.Chrome
    created_at: float


class BifawClient:
    """封装必发指数网登录与文件下载逻辑。"""

    def __init__(self, account: Optional[str] = None, password: Optional[str] = None) -> None:
        config = self._load_config()
        self.account = account or config.get("account")
        self.password = password or config.get("password")

        self._sessions: Dict[str, LoginSession] = {}
        self._lock = threading.Lock()
        self._last_captcha_path: Optional[Path] = None
        self._match_cache: Dict[str, object] = {"timestamp": 0.0, "data": []}
        self._match_cache_v2: Dict[str, object] = {"timestamp": 0.0, "data": []}
        self._requests_cookie_cache: Optional[Dict[str, str]] = None
        self._finished_matches_cache: Dict[str, tuple] = {}  # 缓存完场回查结果 {date_str: (matches, timestamp)}
        
        # 🔥 记录最后一次成功登录的时间（手动或自动）
        self._last_successful_login_time: float = 0.0  # 时间戳（秒）
        self._is_manual_login: bool = False  # 标记是否为手动登录
        
        # 🔥 登录互斥锁：防止手动登录和OCR登录冲突
        self._login_in_progress = False  # 标记是否有登录正在进行
        self._login_type = None  # 登录类型：'manual' 或 'auto'
        self._login_start_time = 0.0  # 登录开始时间（用于超时检测）
        self._login_lock = threading.Lock()  # 登录锁
        self._manual_login_requested = False  # 手动登录请求标记
        
        # 初始化OCR（只使用本地OCR，不再依赖百度OCR）
        self._baidu_ocr = None  # 已弃用
        self._local_ocr = get_local_ocr()
        
        # 🔥 初始化自动重连管理器
        self._reconnect_manager = AutoReconnectManager(self)

    # ------------------------------------------------------------------ #
    # 内部工具方法
    # ------------------------------------------------------------------ #
    def _load_config(self) -> Dict[str, str]:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        cfg = {"account": "", "password": ""}
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        return cfg

    def _require_credentials(self) -> None:
        if not self.account or not self.password:
            cfg = self._load_config()
            self.account = cfg.get("account")
            self.password = cfg.get("password")
            if not self.account or not self.password:
                raise RuntimeError(
                    f"未找到账号或密码，请检查 {CONFIG_FILE} 是否包含 account/password 字段。"
                )

    def _record_login_success(self, is_manual: bool = False):
        """
        记录登录成功的时间
        用于冷却期判断，避免频繁自动登录覆盖用户手动登录
        
        Args:
            is_manual: 是否为手动登录
        """
        self._last_successful_login_time = time.time()
        self._is_manual_login = is_manual
        login_type = "手动登录" if is_manual else "自动登录"
        logger.info(f"✅ 已记录{login_type}时间: {datetime.fromtimestamp(self._last_successful_login_time).strftime('%Y-%m-%d %H:%M:%S')}")

    def is_login_recently(self, minutes: int = None) -> bool:
        """
        检查是否最近刚登录过
        
        Args:
            minutes: 多少分钟内算"最近"（默认：手动登录60分钟，自动登录15分钟）
        
        Returns:
            True表示最近刚登录，False表示已经过了一段时间
        """
        if self._last_successful_login_time == 0:
            return False
        
        # 🔥 智能冷却期：手动登录60分钟，自动登录15分钟
        if minutes is None:
            minutes = 60 if self._is_manual_login else 15
        
        elapsed = time.time() - self._last_successful_login_time
        elapsed_minutes = int(elapsed / 60)
        
        if elapsed < (minutes * 60):
            login_type = "手动登录" if self._is_manual_login else "自动登录"
            logger.debug(f"📍 距离上次{login_type}已过 {elapsed_minutes} 分钟（冷却期 {minutes} 分钟）")
            return True
        
        return False
    
    def should_auto_login(self) -> bool:
        """
        判断是否允许触发OCR自动登录
        
        考虑因素：
        1. OCR是否启用
        2. 是否在登录冷却期内（手动登录后60分钟，自动登录后15分钟）
        3. 🔥 是否有其他登录正在进行（手动或自动）
        
        Returns:
            True表示可以自动登录，False表示不应该自动登录
        """
        # 1. OCR未启用（只检查本地OCR）
        local_ok = self._local_ocr and self._local_ocr.is_enabled()
        if not local_ok:
            return False
        
        # 2. 🔥 有登录正在进行（手动或自动），不要干扰
        if self._login_in_progress:
            logger.info("⏭️ 检测到登录正在进行中，跳过OCR自动登录（避免冲突）")
            return False
        
        # 3. 最近刚登录过，不要覆盖
        if self.is_login_recently():
            login_type = "手动登录" if self._is_manual_login else "自动登录"
            cooldown = 60 if self._is_manual_login else 15
            logger.info(f"⏭️ 距离上次{login_type}不到{cooldown}分钟，跳过OCR自动登录（保护登录状态）")
            return False
        
        return True

    def _kill_zombie_chrome_processes(self):
        """杀掉僵尸Chrome进程"""
        try:
            import psutil
            for proc in psutil.process_iter(['name', 'pid']):
                if 'chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower():
                    try:
                        proc.kill()
                        print(f"[清理] 已杀掉进程: {proc.info['name']} (PID: {proc.info['pid']})")
                    except:
                        pass
        except ImportError:
            # psutil未安装，使用系统命令
            import subprocess
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'], capture_output=True)
                subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'], capture_output=True)
                print("[清理] 已尝试清理Chrome进程")
            except:
                pass

    def _init_driver(self, *, headless: bool = True, retry: bool = True) -> webdriver.Chrome:
        try:
            return self._create_driver_instance(headless=headless)
        except Exception as e:
            if retry and "session not created" in str(e).lower():
                print(f"[警告] 首次创建driver失败: {e}")
                print("[重试] 清理僵尸进程后重试...")
                self._kill_zombie_chrome_processes()
                time.sleep(2)
                return self._create_driver_instance(headless=headless)
            raise
    
    def _create_driver_instance(self, *, headless: bool = True) -> webdriver.Chrome:
        options = Options()

        chrome_binary = resolve_chrome_binary()
        if not chrome_binary:
            raise RuntimeError(
                "未找到 Chrome/Chromium 浏览器。请安装浏览器或设置环境变量 "
                "CHROME_BINARY 指向可执行文件。"
            )
        options.binary_location = chrome_binary
        
        # 基础配置
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # 反检测配置
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # 模拟真实浏览器
        options.add_argument(f"user-agent={DEFAULT_USER_AGENT}")
        
        # 其他优化
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-popup-blocking")

        # 尝试使用 webdriver-manager 自动管理 chromedriver
        chromedriver_path = resolve_chromedriver()
        
        if not chromedriver_path:
            # 尝试使用 webdriver-manager（带缓存）
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                import os
                
                # 设置缓存目录，避免重复下载
                os.environ['WDM_LOCAL'] = '1'  # 使用本地缓存
                os.environ['WDM_LOG'] = '0'    # 减少日志
                
                # 自动下载/使用缓存的 chromedriver
                driver_path = ChromeDriverManager().install()
                logger.info(f"chromedriver 路径: {driver_path}")
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(30)
                self._apply_stealth_scripts(driver)
                return driver
            except ImportError:
                raise RuntimeError(
                    "未找到 chromedriver。请选择以下方案之一：\n"
                    "1. 运行: pip install webdriver-manager (推荐)\n"
                    "2. 手动下载 chromedriver 并设置环境变量 CHROMEDRIVER_PATH\n"
                    "3. 将 chromedriver.exe 放到 Chrome 安装目录"
                )

        try:
            service = Service(chromedriver_path, log_path="NUL")
        except TypeError:
            service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        self._apply_stealth_scripts(driver)
        return driver
    
    def _apply_stealth_scripts(self, driver: webdriver.Chrome) -> None:
        """应用反检测脚本"""
        # 隐藏webdriver特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // 覆盖chrome对象
                window.navigator.chrome = {
                    runtime: {}
                };
                
                // 覆盖permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // 覆盖plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // 覆盖languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            """
        })

    def _capture_captcha_base64(self, driver: webdriver.Chrome) -> str:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(CAPTCHA_IMAGE)
                )
                src = element.get_attribute("src") or ""
                if not src:
                    raise RuntimeError("验证码地址为空。")

                if src.startswith("data:image"):
                    try:
                        _, b64_data = src.split(",", 1)
                    except ValueError as exc_split:
                        raise RuntimeError("验证码数据格式异常。") from exc_split
                    if not b64_data:
                        raise RuntimeError("验证码数据为空。")
                    return b64_data

                captcha_url = urljoin(LOGIN_URL, src)
                session = requests.Session()
                session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
                for cookie in driver.get_cookies():
                    name = cookie.get("name")
                    value = cookie.get("value")
                    if not name:
                        continue
                    session.cookies.set(
                        name,
                        value,
                        domain=cookie.get("domain"),
                        path=cookie.get("path", "/"),
                    )

                response = session.get(captcha_url, timeout=10)
                response.raise_for_status()
                png_bytes = response.content
                if not png_bytes:
                    raise RuntimeError("验证码响应为空。")

                file_path = BASE_DIR / "captcha.png"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "wb") as fh:
                    fh.write(png_bytes)
                self._last_captcha_path = file_path

                return base64.b64encode(png_bytes).decode("ascii")
            except (StaleElementReferenceException, WebDriverException, requests.RequestException) as exc:
                last_error = exc
                if "target frame detached" in str(exc):
                    try:
                        driver.refresh()
                    except Exception:
                        raise
                    continue
                raise
        if last_error:
            raise RuntimeError(f"验证码截图失败：{last_error}") from last_error
        raise RuntimeError("验证码截图失败，未知原因。")

    @staticmethod
    def _cookies_to_requests_map(cookies: Sequence[Mapping[str, object]]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for cookie in cookies:
            if not isinstance(cookie, Mapping):
                cookie = dict(cookie)  # type: ignore[assignment]
            name = str(cookie.get("name") or "").strip()
            value = cookie.get("value")
            if not name or value is None:
                continue
            result[name] = str(value)
        return result

    def _extract_requests_cookies(self, driver: webdriver.Chrome) -> Dict[str, str]:
        return self._cookies_to_requests_map(driver.get_cookies())

    def _load_cookie_file(self) -> List[Dict[str, object]]:
        if not COOKIES_PATH.exists():
            raise RuntimeError("尚未登录或 cookies 已丢失，请先在采集控制台完成登录。")
        with open(COOKIES_PATH, "r", encoding="utf-8") as fh:
            cookies = json.load(fh)
        if not isinstance(cookies, list):
            raise RuntimeError("cookies 文件内容异常，期望列表结构。")
        return cookies  # type: ignore[return-value]

    def _load_requests_cookies(self) -> Dict[str, str]:
        if self._requests_cookie_cache:
            return dict(self._requests_cookie_cache)
        cookies = self._load_cookie_file()
        cookie_map = self._cookies_to_requests_map(cookies)
        self._requests_cookie_cache = dict(cookie_map)
        return cookie_map

    def get_requests_cookies(self) -> Dict[str, str]:
        """返回适用于 requests 的 cookies 映射。"""
        return self._load_requests_cookies()

    def _save_cookies(self, driver: webdriver.Chrome) -> None:
        cookies = driver.get_cookies()
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIES_PATH, "w", encoding="utf-8") as fh:
            json.dump(cookies, fh, ensure_ascii=False, indent=2)
        self._requests_cookie_cache = self._cookies_to_requests_map(cookies)

    def _inject_cookies(self, driver: webdriver.Chrome) -> None:
        if not COOKIES_PATH.exists():
            raise RuntimeError("尚未登录或 cookies 已丢失，请先在采集控制台完成登录。")
        driver.get(LOGIN_URL)
        with open(COOKIES_PATH, "r", encoding="utf-8") as fh:
            cookies = json.load(fh)
        driver.delete_all_cookies()
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            cookie = dict(cookie)
            cookie.pop("sameSite", None)
            expiry = cookie.get("expiry")
            if isinstance(expiry, float):
                cookie["expiry"] = int(expiry)
            domain = cookie.get("domain")
            if isinstance(domain, str) and domain.startswith("."):
                cookie["domain"] = domain.lstrip(".")
            try:
                driver.add_cookie(cookie)
            except Exception as exc:
                logger.debug("注入单个 cookie 失败：%s，原因：%s", cookie.get("name"), exc)
        driver.refresh()

    def _cleanup_sessions(self) -> None:
        with self._lock:
            now = time.time()
            expired = [sid for sid, sess in self._sessions.items() if now - sess.created_at > SESSION_EXPIRE_SECONDS]
            for sid in expired:
                try:
                    self._sessions[sid].driver.quit()
                finally:
                    self._sessions.pop(sid, None)

    def _build_requests_session(self) -> requests.Session:
        cookies = self._load_cookie_file()

        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not name:
                continue
            session.cookies.set(
                name,
                value,
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

        self._requests_cookie_cache = self._cookies_to_requests_map(cookies)
        return session

    @staticmethod
    def _normalize_response_encoding(response: requests.Response) -> None:
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            try:
                response.encoding = response.apparent_encoding or "utf-8"
            except Exception:
                response.encoding = "utf-8"

    def _fetch_detail_recursive(
        self,
        session: requests.Session,
        url: str,
        *,
        timeout: int,
        referer: Optional[str],
        visited: Optional[Set[str]] = None,
        depth: int = 0,
        max_depth: int = 3,
    ) -> requests.Response:
        if visited is None:
            visited = set()
        visited.add(url)

        headers: Dict[str, str] = {}
        if referer:
            headers["Referer"] = referer

        print(f"\n[请求URL] {url}")
        print(f"[Referer] {referer or '无'}")
        response = session.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        response.raise_for_status()

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "pdf" in content_type:
            return response

        if not any(token in content_type for token in ("html", "text")):
            return response

        self._normalize_response_encoding(response)
        html_text = response.text
        response._bifaw_detail_html = html_text  # type: ignore[attr-defined]

        if "你还没有登陆" in html_text or "尚未登录" in html_text:
            debug_path = self._save_debug_html(html_text, prefix="detail_requires_login")
            logger.warning("⚠️  检测到登录状态失效")
            
            # 🔥 检查是否允许自动登录（考虑登录冷却期）
            if self.should_auto_login():
                logger.info("🤖 尝试自动OCR登录...")
                ocr_success, ocr_message = self._auto_login_with_ocr()
                if ocr_success:
                    logger.info("✅ 自动登录成功，请重试请求")
                    # 清空cookies缓存
                    self._requests_cookie_cache = None
                    raise RuntimeError(
                        f"登录状态已恢复，请重试请求。调试文件：{debug_path.name}"
                    )
                else:
                    logger.error(f"❌ 自动登录失败: {ocr_message}")
                    raise RuntimeError(
                        f"标盘明细请求返回未登录页面，自动登录失败({ocr_message})，请手动登录后再试。调试文件：{debug_path.name}"
                    )
            else:
                # 🔥 在冷却期内，不自动登录，提示用户手动登录
                raise RuntimeError(
                    f"检测到登录失效，但距离上次登录不到15分钟（保护手动登录），请手动登录后再试。调试文件：{debug_path.name}"
                )

        if any(keyword in html_text for keyword in DETAIL_KEYWORDS):
            return response

        if depth >= max_depth:
            return response

        soup = BeautifulSoup(html_text, "html.parser")

        # 处理 meta refresh
        meta = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
        if meta:
            content = meta.get("content") or ""
            lower_content = content.lower()
            if "url=" in lower_content:
                _, _, target = lower_content.partition("url=")
                redirect_url = urljoin(response.url, target.strip())
                if redirect_url and redirect_url not in visited:
                    return self._fetch_detail_recursive(
                        session,
                        redirect_url,
                        timeout=timeout,
                        referer=response.url,
                        visited=visited,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )

        frame_tags = soup.find_all(["iframe", "frame"])
        for frame in frame_tags:
            src = (frame.get("src") or "").strip()
            if not src or src.lower().startswith("javascript"):
                continue
            nested_url = urljoin(response.url, src)
            if not nested_url or nested_url in visited:
                continue
            try:
                nested_resp = self._fetch_detail_recursive(
                    session,
                    nested_url,
                    timeout=timeout,
                    referer=response.url,
                    visited=visited,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            except Exception as exc:
                logger.debug("抓取嵌套明细失败：%s，原因：%s", nested_url, exc)
                continue

            nested_type = (nested_resp.headers.get("Content-Type") or "").lower()
            if "pdf" in nested_type:
                return nested_resp

            nested_html = getattr(nested_resp, "_bifaw_detail_html", None)  # type: ignore[attr-defined]
            if isinstance(nested_html, str) and any(keyword in nested_html for keyword in DETAIL_KEYWORDS):
                return nested_resp

        return response

    def _save_debug_html(self, html: str, *, prefix: str) -> Path:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        file_path = DEBUG_DIR / f"{prefix}_{timestamp}.html"
        try:
            file_path.write_text(html, encoding="utf-8", errors="ignore")
        except Exception:
            logger.exception("写入调试 HTML 失败：%s", file_path)
        return file_path

    def _save_debug_screenshot(self, driver: webdriver.Chrome, *, prefix: str) -> Path:
        """
        保存调试截图到 debug 目录
        
        注意：截图失败不影响主流程，只记录警告日志
        """
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        file_path = DEBUG_DIR / f"{prefix}_{timestamp}.png"
        
        try:
            driver.save_screenshot(str(file_path))
            logger.info("已保存调试截图：%s", file_path)
        except TimeoutException:
            # Chrome渲染器超时，跳过截图
            logger.warning(f"⚠️  截图超时（跳过）: {file_path.name}")
        except Exception as e:
            # 其他错误也只记录警告
            logger.warning(f"⚠️  截图失败（跳过）: {file_path.name} - {type(e).__name__}")
            
        return file_path

    # ------------------------------------------------------------------ #
    # 对外接口
    # ------------------------------------------------------------------ #
    def fetch_captcha(self, _record_time: bool = True) -> Tuple[str, str]:
        """
        初始化浏览器会话并返回验证码图像（base64），同时返回 session_id。
        
        Args:
            _record_time: 保留参数（兼容性），不再使用
        """
        self._require_credentials()
        self._cleanup_sessions()

        last_error: Optional[Exception] = None

        for attempt in range(3):
            driver = self._init_driver()
            wait = WebDriverWait(driver, 15)
            try:
                driver.get(LOGIN_URL)

                username_input = wait.until(EC.visibility_of_element_located(USERNAME_INPUT))
                password_input = wait.until(EC.visibility_of_element_located(PASSWORD_INPUT))

                username_input.clear()
                username_input.send_keys(self.account)
                password_input.clear()
                password_input.send_keys(self.password)

                captcha_b64 = self._capture_captcha_base64(driver)

                session_id = uuid.uuid4().hex
                with self._lock:
                    self._sessions[session_id] = LoginSession(driver=driver, created_at=time.time())

                return session_id, captcha_b64
            except Exception as exc:
                last_error = exc
                try:
                    driver.quit()
                except Exception:
                    pass
        if last_error:
            raise RuntimeError(f"获取验证码失败：{last_error}") from last_error
        raise RuntimeError("获取验证码失败，未知原因。")

    def _has_login_succeeded(self, driver: webdriver.Chrome, log_result: bool = False) -> bool:
        """
        判断登录是否成功，按优先级检测：
        1. URL已离开登录页进入会员区
        2. 找到登录成功标记元素
        3. 检查是否仍在登录页/有失败标记
        
        Args:
            log_result: 是否记录结果日志（避免循环等待时刻印大量日志）
        """
        current_url = driver.current_url.lower()
        
        # ★ 快速判断1: URL已进入会员区且离开登录页
        if "member" in current_url and "login" not in current_url:
            if log_result:
                logger.info(f"✅ 登录成功：已跳转到会员区域 {driver.current_url}")
            return True
        
        # ★ 快速判断2: 仍在登录页且验证码输入框可见 → 未成功
        if "login" in current_url:
            try:
                captcha_input = driver.find_element(*CAPTCHA_INPUT)
                if captcha_input.is_displayed():
                    return False  # 仍在登录页，不记录日志避免刷屏
            except Exception:
                pass
        
        # ★ 检查登录失败标记（验证码错误等提示）
        for locator in LOGIN_FAILURE_MARKS:
            try:
                elem = driver.find_element(*locator)
                if elem.is_displayed():
                    if log_result:
                        logger.warning(f"❌ 登录失败：发现错误提示 - {elem.text[:50]}")
                    return False
            except Exception:
                pass
        
        # ★ 检查登录成功标记（退出链接、欢迎词等）
        for locator in LOGIN_SUCCESS_MARKS:
            try:
                elem = driver.find_element(*locator)
                if elem.is_displayed():
                    # 对于_userlogin元素，需额外检查文本内容
                    if locator[1] == "_userlogin":
                        text = elem.text.strip()
                        if text and "登录" not in text and "注册" not in text:
                            if log_result:
                                logger.info(f"✅ 登录成功：用户名={text}")
                            return True
                    else:
                        if log_result:
                            logger.info("✅ 登录成功：找到登录成功标记")
                        return True
            except Exception:
                pass
        
        # ★ 无法确定，返回False继续等待
        return False

    def _wait_for_login_success(self, driver: webdriver.Chrome, timeout: int = 20) -> bool:
        """等待登录成功，超时返回False"""
        try:
            # 使用不记录日志的版本避免刷屏
            WebDriverWait(driver, timeout, poll_frequency=0.5).until(
                lambda d: self._has_login_succeeded(d, log_result=False)
            )
            # 成功后记录一次日志
            self._has_login_succeeded(driver, log_result=True)
            return True
        except TimeoutException:
            # 超时时记录最终状态
            logger.warning(f"⚠️ 登录超时，当前URL: {driver.current_url}")
            return False

    def _auto_login_with_ocr(self, max_retries: int = 20, force: bool = False) -> Tuple[bool, str]:
        """
        使用百度OCR自动识别验证码并登录
        
        Args:
            max_retries: 最大重试次数（默认5次）
            force: 是否强制登录（忽略冷却期和进行中状态）
            
        Returns:
            (success, message)
        """
        # 检查本地OCR是否可用
        local_ok = self._local_ocr and self._local_ocr.is_enabled()
        if not local_ok:
            return False, "本地OCR未启用（请确保ddddocr已安装）"
        
        # 🔥 获取登录锁，防止与手动登录冲突
        with self._login_lock:
            # 如果有手动登录请求，立即放弃OCR登录
            if self._manual_login_requested:
                logger.info("⏭️ 检测到手动登录请求，跳过OCR自动登录")
                return False, "用户请求手动登录"
            
            # 如果有其他登录正在进行
            if self._login_in_progress:
                # 如果是强制登录，且超时超过10秒，强制接管
                if force and time.time() - self._login_start_time > 10:
                    logger.warning("⚠️ 强制登录模式：检测到旧登录超时，强制接管")
                    self._login_in_progress = False
                # 检查是否超时（60秒）
                elif time.time() - self._login_start_time > 60:
                    logger.warning("⚠️ 检测到登录超时，强制释放锁")
                    self._login_in_progress = False
                    self._login_type = None
                else:
                    logger.info(f"⏭️ 检测到{self._login_type}登录正在进行，跳过OCR自动登录")
                    return False, "其他登录正在进行"
            
            self._login_in_progress = True
            self._login_type = 'auto'
            self._login_start_time = time.time()
            logger.info("🔐 开始OCR自动登录流程（强制模式）" if force else "🔐 开始OCR自动登录流程")
        
        try:
            logger.info(f"🤖 开始自动OCR登录（最多{max_retries}次重试）...")
            
            for attempt in range(1, max_retries + 1):
                # 🔥 每次循环都检查是否有手动登录请求
                with self._login_lock:
                    if self._manual_login_requested:
                        logger.info("⏭️ 检测到手动登录请求，中止OCR自动登录")
                        return False, "用户请求手动登录，OCR已中止"
                
                try:
                    logger.info(f"🔄 第 {attempt}/{max_retries} 次尝试...")
                    # 🔥 OCR自动登录时不记录首次访问时间（因为已经过了宽限期）
                    session_id, captcha_b64 = self.fetch_captcha(_record_time=False)
                    
                    # 2. OCR识别（本地OCR优先，失败后尝试百度OCR）
                    logger.info("🔍 正在OCR识别验证码...")
                    success, captcha_text, message = False, None, "未尝试"
                    
                    # 🔥 只使用本地OCR（ddddocr，无API限制，不再使用百度OCR）
                    if self._local_ocr and self._local_ocr.is_enabled():
                        success, captcha_text, message = self._local_ocr.recognize_captcha_from_base64(captcha_b64)
                    else:
                        success, captcha_text, message = False, None, "本地OCR未启用"
                    
                    if not success or not captcha_text:
                        logger.warning(f"⚠️ OCR识别失败: {message}")
                        # 清理session
                        with self._lock:
                            session = self._sessions.pop(session_id, None)
                            if session:
                                try:
                                    session.driver.quit()
                                except:
                                    pass
                        continue
                    
                    # 🔥 验证码格式检查：必须是4位数字
                    if not captcha_text.isdigit() or len(captcha_text) != 4:
                        logger.warning(f"⚠️  OCR识别结果格式错误: '{captcha_text}' (期望4位数字)")
                        # 保存验证码图片供调试
                        try:
                            import base64
                            captcha_data = base64.b64decode(captcha_b64)
                            debug_path = self._save_debug_image(captcha_data, prefix="invalid_captcha")
                            logger.info(f"   验证码图片已保存: {debug_path.name}")
                        except:
                            pass
                        # 清理session
                        with self._lock:
                            session = self._sessions.pop(session_id, None)
                            if session:
                                try:
                                    session.driver.quit()
                                except:
                                    pass
                        continue
                    
                    logger.info(f"✅ OCR识别成功: '{captcha_text}'")
                    
                    # 3. 提交登录
                    logger.info("📝 正在提交登录...")
                    # 🔥 使用内部调用标记，跳过锁检查
                    login_success, login_payload = self.submit_captcha(session_id, captcha_text, _internal_call=True)
                    
                    if login_success:
                        logger.info("✅ 自动登录成功！")
                        self._record_login_success(is_manual=False)  # 🔥 记录登录时间（自动登录）
                        return True, "自动OCR登录成功"
                    else:
                        logger.warning(f"⚠️  登录失败: {login_payload.get('message')}")
                        
                except Exception as e:
                    logger.error(f"❌ 自动登录异常: {e}")
            
            return False, f"自动OCR登录失败，已重试{max_retries}次"
        finally:
            # 🔥 释放登录锁
            with self._login_lock:
                if self._login_type == 'auto':  # 只释放自己的锁
                    self._login_in_progress = False
                    self._login_type = None
                    logger.info("🔓 OCR自动登录流程结束")
    
    def submit_captcha(self, session_id: str, captcha_text: str, _internal_call: bool = False) -> Tuple[bool, Dict[str, str]]:
        """提交验证码，若成功则保存 cookies 并关闭浏览器。
        
        Args:
            session_id: 登录会话ID
            captcha_text: 验证码文本
            _internal_call: 内部调用标记（OCR流程使用，跳过锁检查）
        """
        # 🔥 如果不是内部调用，获取登录锁，防止与OCR登录冲突
        if not _internal_call:
            # 设置手动登录请求标记
            with self._login_lock:
                self._manual_login_requested = True
            
            # 等待OCR登录结束（最多等待10秒）
            wait_start = time.time()
            while True:
                with self._login_lock:
                    if not self._login_in_progress:
                        break
                    elif self._login_type == 'auto':
                        # OCR正在进行，等待它结束
                        elapsed = time.time() - wait_start
                        if elapsed > 10:
                            logger.warning("⚠️ 等待OCR登录超时（10秒），强制开始手动登录")
                            self._login_in_progress = False
                            self._login_type = None
                            break
                        logger.info(f"⏳ 等待OCR登录结束...（已等待{elapsed:.1f}秒）")
                    elif self._login_type == 'manual':
                        logger.warning("⚠️ 检测到其他手动登录正在进行，请稍后重试")
                        self._manual_login_requested = False
                        return False, {"message": "其他手动登录正在进行，请稍后重试"}
                time.sleep(0.5)  # 等待0.5秒后重试
            
            # 获取锁
            with self._login_lock:
                self._login_in_progress = True
                self._login_type = 'manual'
                self._login_start_time = time.time()
                self._manual_login_requested = False  # 清除请求标记
                logger.info("🔐 开始手动登录流程")
        
        try:
            with self._lock:
                session = self._sessions.get(session_id)

            if not session:
                return False, {"message": "登录会话已过期，请重新获取验证码。"}

            driver = session.driver
            wait = WebDriverWait(driver, 15)
            captcha_input = wait.until(EC.visibility_of_element_located(CAPTCHA_INPUT))
            captcha_input.clear()
            captcha_input.send_keys(captcha_text.strip())
            driver.find_element(*LOGIN_BUTTON).click()

            try:
                if not self._wait_for_login_success(driver, timeout=20):
                    raise TimeoutException("登录成功标记未出现")
                self._save_cookies(driver)
                driver.quit()
                with self._lock:
                    self._sessions.pop(session_id, None)
                self._record_login_success(is_manual=True)  # 🔥 记录登录时间（手动登录）
                logger.info("✅ 手动登录成功")
                return True, {"message": "登录成功，cookies 已保存。"}
            except TimeoutException:
                # 登录失败，需要返回登录页获取新验证码
                try:
                    # 先检查当前是否在登录页
                    if "login" not in driver.current_url.lower():
                        logger.info("⚠️ 登录超时，导航回登录页...")
                        driver.get(LOGIN_URL)
                        time.sleep(1)
                    # 刷新验证码
                    try:
                        driver.find_element(*CAPTCHA_IMAGE).click()
                    except Exception:
                        pass
                    new_img = self._capture_captcha_base64(driver)
                    session.created_at = time.time()
                    return False, {"message": "登录失败，验证码可能错误，请重试。", "captcha": new_img}
                except Exception as e:
                    logger.error(f"获取新验证码失败: {e}")
                    driver.quit()
                    with self._lock:
                        self._sessions.pop(session_id, None)
                    return False, {"message": f"登录失败且无法获取新验证码: {e}"}
            except Exception as exc:
                driver.quit()
                with self._lock:
                    self._sessions.pop(session_id, None)
                return False, {"message": f"登录过程中发生错误：{exc}"}
        finally:
            # 🔥 释放登录锁（仅限非内部调用）
            if not _internal_call:
                with self._login_lock:
                    if self._login_type == 'manual':  # 只释放自己的锁
                        self._login_in_progress = False
                        self._login_type = None
                        self._manual_login_requested = False
                        logger.info("🔓 手动登录流程结束")

    def _check_login_status_quick(self) -> bool:
        """
        快速检查登录状态（不发送网络请求）
        
        检查条件：
        1. cookies文件存在
        2. 最近15分钟内有成功登录记录
        
        Returns:
            True: 可能已登录（不需要重新登录）
            False: 需要登录
        """
        # 1. 检查是否最近刚登录过
        if self.is_login_recently(minutes=15):
            return True
        
        # 2. 检查cookies文件是否存在且不太旧
        if not COOKIES_PATH.exists():
            return False
        
        # 3. 检查cookies文件年龄（超过2小时认为可能失效）
        stat = COOKIES_PATH.stat()
        age_minutes = (time.time() - stat.st_mtime) / 60
        
        if age_minutes > 120:  # 2小时
            return False
        
        return True

    def get_cookie_status(self, verify: bool = False) -> Dict[str, object]:
        """返回 cookies 状态用于前端展示。
        
        Args:
            verify: 是否实际验证 cookie 有效性（会发送请求）
        """
        if not COOKIES_PATH.exists():
            return {"exists": False, "message": "当前未登录，请完成验证码验证。", "valid": False}

        stat = COOKIES_PATH.stat()
        updated_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # 检查 cookie 文件年龄
        age_seconds = time.time() - stat.st_mtime
        age_minutes = age_seconds / 60
        age_hours = age_seconds / 3600
        
        # 格式化时间显示
        def format_age(mins):
            if mins < 1:
                return "刚刚"
            elif mins < 60:
                return f"{int(mins)}分钟前"
            elif mins < 1440:  # 24小时
                return f"{mins/60:.1f}小时前"
            else:
                return f"{mins/1440:.1f}天前"
        
        age_str = format_age(age_minutes)
        
        result = {
            "exists": True,
            "updated_at": updated_at,
            "path": str(COOKIES_PATH),
            "age_hours": round(age_hours, 1),
        }
        
        # 🔥 严格验证：如果需要验证或 cookie 超过30分钟，进行实际验证
        # 之前的12小时太长了，导致系统误判
        if verify or age_minutes > 30:
            try:
                session = self._build_requests_session()
                # 访问会员中心来验证（如果未登录通常会重定向或返回登录页）
                # 使用 verify=False 避免 SSL 错误（如果目标站点证书有问题）
                resp = session.get("https://www.bifaw.com/member/", timeout=20, verify=False)
                
                # 检查是否包含登录后的特征
                # 如果页面包含 "login.php" 或 "用户登录" 等字样，说明失效
                is_invalid = (
                    'login.php' in resp.url or 
                    '用户登录' in resp.text or 
                    '请输入验证码' in resp.text
                )
                
                if is_invalid:
                    result["valid"] = False
                    result["message"] = f"Cookie 已失效（{age_str}更新），系统将自动重新登录"
                    # 🔥 既然失效了，主动删除它，触发后续的自动登录逻辑
                    try:
                        os.remove(COOKIES_PATH)
                    except:
                        pass
                else:
                    result["valid"] = True
                    result["message"] = f"已登录（{age_str}更新，已验证有效）"
            except Exception as e:
                # 网络错误时，保守起见认为是有效的，避免误删，但标记为未验证
                result["valid"] = True 
                result["message"] = f"已登录（{age_str}，网络验证超时）"
        else:
            result["valid"] = True
            result["message"] = f"已登录（{age_str}更新）"
        
        return result

    def download_file(self, url: str, filename: Optional[str] = None) -> Path:
        """使用已保存的 cookies 下载指定 URL 内容。"""
        session = self._build_requests_session()
        response = session.get(url, stream=True, timeout=30)
        response.raise_for_status()

        if not filename:
            filename = Path(urlparse(url).path).name or f"bifaw_{int(time.time())}.dat"

        destination = DOWNLOAD_DIR / filename
        destination.parent.mkdir(parents=True, exist_ok=True)

        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)

        return destination

    def fetch_page_html(self, url: str, timeout: int = 20) -> str:
        """在已登录状态下获取网页 HTML。"""
        session = self._build_requests_session()
        target = urljoin(LOGIN_URL, url)
        print(f"\n[访问页面] {target}")
        response = session.get(target, timeout=timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def fetch_match_detail_selenium(
        self,
        *,
        detail_url: Optional[str] = None,
        match: Optional[Dict[str, object]] = None,
        detail_params: Optional[Dict[str, object]] = None,
        wait_text: Union[str, Sequence[str]] = (HEADER_KEYWORD, "买家挂牌", "卖家挂牌"),
        timeout: int = 40,
    ) -> str:
        """
        使用 Selenium 浏览器抓取标盘明细页面，支持处理新窗口打开的情况。
        
        Args:
            detail_url: 已知的明细链接。
            match: `fetch_match_list` / `fetch_match_list_v2` 返回的比赛字典。
            detail_params: 备用参数，可从 openMatchDetails 解析得到。
            wait_text: 等待出现的关键字。
            timeout: 请求超时时间（秒）。
            
        Returns:
            明细页面的 HTML 源码。
        """
        target = self._resolve_detail_url(
            detail_url=detail_url,
            match=match,
            detail_params=detail_params,
        )
        
        driver = self._init_driver()
        original_window = None
        
        try:
            # 注入 cookies 并验证登录状态
            logger.info("开始注入 cookies 并验证登录状态")
            try:
                self._inject_cookies(driver)
            except RuntimeError as e:
                # 如果是 cookies 丢失导致的错误，尝试自动登录
                if "尚未登录" in str(e) or "cookies" in str(e).lower():
                    logger.warning(f"⚠️ {e}，尝试自动登录...")
                    if self._local_ocr and self._local_ocr.is_enabled():
                        success, msg = self._auto_login_with_ocr(max_retries=20)
                        if success:
                            logger.info("✅ 自动登录成功，重试注入 cookies")
                            self._inject_cookies(driver)
                        else:
                            logger.error(f"❌ 自动登录失败: {msg}")
                            raise
                    else:
                        raise
                else:
                    raise
            
            driver.get(urljoin(LOGIN_URL, "/bifaw/index.php"))
            
            # 等待页面加载
            time.sleep(2)
            
            # 登录状态检查（不保存调试文件）
            
            def _login_ready(d: webdriver.Chrome) -> bool:
                page_source = d.page_source
                page_title = d.title or ""
                
                # 如果页面包含登录表单，说明未登录
                if "登录" in page_title and "验证码" in page_source:
                    logger.warning("检测到登录页面")
                    return False
                
                # 检查是否有登录成功的标志
                if self._has_login_succeeded(d):
                    logger.info("登录状态验证成功")
                    return True
                
                # 如果页面包含"标盘"或"必发"等关键字，也认为登录成功
                if "标盘" in page_source or "必发指数" in page_source:
                    logger.info("检测到站内内容，登录有效")
                    return True
                    
                return False
            
            try:
                WebDriverWait(driver, 10).until(_login_ready)
                logger.info("登录状态验证通过")
            except TimeoutException as exc_login:
                logger.error("登录状态验证超时")
                self._save_debug_screenshot(driver, prefix="detail_login_timeout")
                self._save_debug_html(driver.page_source, prefix="detail_login_timeout")
                raise RuntimeError(
                    "明细页面登录状态验证失败，请在采集控制台重新登录后再试。检查 debug_html 目录中的 detail_login_timeout 文件。"
                ) from exc_login
            
            # 保存初始窗口句柄
            original_window = driver.current_window_handle
            initial_windows = set(driver.window_handles)
            
            # 在新窗口中打开明细链接（模拟点击按钮打开新窗口的行为）
            logger.info("正在访问明细页面：%s", target)
            print(f"\n" + "="*80)
            print(f"[Selenium明细页面] {target}")
            print(f"你可以手动访问此URL来检查是否能正常打开")
            print("="*80 + "\n")
            driver.execute_script(f"window.open('{target}', '_blank');")
            
            # 等待新窗口出现
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(set(d.window_handles)) > len(initial_windows)
                )
            except TimeoutException:
                # 如果没有新窗口，可能是在当前窗口打开
                logger.warning("未检测到新窗口，尝试在当前窗口处理")
            
            # 查找新窗口
            new_windows = set(driver.window_handles) - initial_windows
            if new_windows:
                new_window = new_windows.pop()
                logger.info("切换到新窗口：%s", new_window)
                driver.switch_to.window(new_window)
            else:
                logger.warning("没有检测到新窗口，在当前窗口继续")
            
            # 等待页面初始化（优化：减少到1秒）
            time.sleep(1.0)
            
            # 页面已打开（不保存调试快照）
            
            # 🔥 快速滚动加载（优化版：减少等待时间）
            logger.info("开始滚动加载数据...")
            try:
                prev_row_count = 0
                stable_attempts = 0
                max_scroll_attempts = 4  # 减少到4次
                
                for scroll_attempt in range(max_scroll_attempts):
                    # 滚动到底部
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)  # 优化：减少到0.5秒
                    
                    # 检查当前行数
                    try:
                        tables = driver.find_elements(By.TAG_NAME, "table")
                        current_row_count = 0
                        for table in tables:
                            rows = table.find_elements(By.TAG_NAME, "tr")
                            current_row_count = max(current_row_count, len(rows))
                        
                        # 如果行数不再增加，说明已经加载完成
                        if current_row_count == prev_row_count and current_row_count > 5:
                            stable_attempts += 1
                            if stable_attempts >= 1:  # 只需1次稳定
                                break
                        else:
                            stable_attempts = 0
                        
                        prev_row_count = current_row_count
                    except Exception as e:
                        logger.debug(f"滚动加载检查失败: {e}")
                
                # 滚动回顶部
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.3)  # 优化：减少到0.3秒
            except Exception as e:
                logger.warning(f"滚动加载出错: {e}")
            
            # 优化：减少额外等待时间到0.5秒
            time.sleep(0.5)
            
            # 页面加载完成（不保存调试快照）
            
            # 等待页面加载完成
            try:
                WebDriverWait(driver, min(timeout, 15)).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                logger.debug("document.readyState 超时，继续处理")
            
            # 专门等待数据表格加载（优化版：减少等待时间）
            try:
                logger.info("等待数据表格加载...")
                WebDriverWait(driver, 8).until(
                    lambda d: len(d.find_elements(By.TAG_NAME, "table")) > 0
                )
                table_count = len(driver.find_elements(By.TAG_NAME, "table"))
                logger.info(f"✅ 检测到 {table_count} 个表格元素")
                
                # 快速等待表格数据填充
                stable_count = 0
                prev_max_rows = 0
                
                for attempt in range(6):  # 减少到6次（约6秒）
                    time.sleep(1)
                    
                    # 检查表格行数
                    tables = driver.find_elements(By.TAG_NAME, "table")
                    max_rows = 0
                    for table in tables:
                        try:
                            rows = table.find_elements(By.TAG_NAME, "tr")
                            if len(rows) > max_rows:
                                max_rows = len(rows)
                        except:
                            pass
                    
                    # 如果行数稳定（连续1次相同且>5行），说明数据已加载完成
                    if max_rows == prev_max_rows and max_rows > 5:
                        stable_count += 1
                        if stable_count >= 1:
                            break
                    else:
                        stable_count = 0
                    
                    prev_max_rows = max_rows
                    
                    # 如果有表格包含大量数据行（>15行），直接继续
                    if max_rows > 15:
                        break
                
            except TimeoutException:
                logger.warning("⚠️  未检测到表格元素，但继续尝试解析")
            
            # 处理关键字等待
            keywords: Tuple[str, ...]
            if isinstance(wait_text, str):
                keywords = (wait_text,)
            else:
                keywords = tuple(str(item) for item in wait_text if item)
            
            frame_html: Optional[str] = None
            
            def _extract_html_with_keyword(d: webdriver.Chrome) -> Optional[str]:
                try:
                    d.switch_to.default_content()
                except Exception:
                    pass
                
                def _dfs() -> Optional[str]:
                    html_content = d.page_source
                    if not keywords or any(keyword in html_content for keyword in keywords):
                        return html_content
                    
                    frames = d.find_elements(By.TAG_NAME, "iframe") + d.find_elements(By.TAG_NAME, "frame")
                    for frame in frames:
                        try:
                            d.switch_to.frame(frame)
                            nested_html = _dfs()
                            if nested_html:
                                return nested_html
                        except Exception:
                            continue
                        finally:
                            try:
                                d.switch_to.parent_frame()
                            except Exception:
                                try:
                                    d.switch_to.default_content()
                                except Exception:
                                    pass
                    return None
                
                result = _dfs()
                try:
                    d.switch_to.default_content()
                except Exception:
                    pass
                return result
            
            def _wait_for_keyword(d: webdriver.Chrome) -> bool:
                nonlocal frame_html
                result = _extract_html_with_keyword(d)
                if result:
                    frame_html = result
                    return True
                frame_html = d.page_source
                return False
            
            if keywords:
                try:
                    WebDriverWait(driver, timeout).until(_wait_for_keyword)
                    # 关键字检测成功（不保存调试快照）
                except TimeoutException as exc:
                    html = frame_html or driver.page_source
                    # 截图：超时时
                    self._save_debug_screenshot(driver, prefix="detail_timeout")
                    
                    if not any(keyword in html for keyword in keywords):
                        current_url = driver.current_url
                        page_title = driver.title or "未知标题"
                        debug_path = self._save_debug_html(html, prefix="detail_timeout_no_keyword")
                        keywords_str = '、'.join(keywords)
                        
                        if "登录" in html or "验证码" in html:
                            logger.warning("⚠️  明细页面登录状态失效")
                            
                            # 关闭driver
                            try:
                                driver.quit()
                            except:
                                pass
                            
                            # 🔥 检查是否允许自动登录（考虑登录冷却期）
                            if self.should_auto_login():
                                logger.info("🤖 尝试自动OCR登录...")
                                ocr_success, ocr_message = self._auto_login_with_ocr()
                                if ocr_success:
                                    logger.info("✅ 自动登录成功，请重试请求")
                                    raise RuntimeError(
                                        f"登录状态已恢复，请重试请求。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                    ) from exc
                                else:
                                    logger.error(f"❌ 自动登录失败: {ocr_message}")
                                    raise RuntimeError(
                                        f"明细页面加载超时，疑似登录状态失效，自动登录失败({ocr_message})。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                    ) from exc
                            else:
                                # 🔥 在冷却期内，不自动登录，提示用户手动登录
                                raise RuntimeError(
                                    f"明细页面登录状态失效，但距离上次登录不到15分钟（保护手动登录），请手动登录后再试。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                ) from exc
                        raise RuntimeError(
                            f"明细页面加载超时，未找到关键字「{keywords_str}」。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                        ) from exc
            
            html = frame_html or driver.page_source
            
            # 数据获取成功（不保存调试快照）
            
            # 优化：减少JavaScript渲染等待时间
            time.sleep(1.0)  # 优化：减少到1秒
            
            # 获取渲染后的HTML（从DOM而不是page_source）
            # page_source只返回原始HTML，不包含JS动态插入的内容
            print("[最终检查] 从DOM获取渲染后的HTML...")
            
            try:
                # 获取整个文档的outerHTML（包含所有JS渲染的内容）
                final_html = driver.execute_script("return document.documentElement.outerHTML;")
                print(f"[最终检查] 通过execute_script获取HTML，长度: {len(final_html):,}")
            except Exception as e:
                print(f"[警告] execute_script失败: {e}，使用page_source")
                final_html = driver.page_source
            
            # 检查数据行数量
            final_tables = driver.find_elements(By.TAG_NAME, "table")
            max_rows = 0
            data_table = None
            for table in final_tables:
                try:
                    trs = table.find_elements(By.TAG_NAME, "tr")
                    tds = table.find_elements(By.TAG_NAME, "td")
                    if len(tds) > 0 and len(trs) > max_rows:
                        max_rows = len(trs)
                        data_table = table
                        print(f"[最终检查] 找到数据表格：{len(trs)}行，{len(tds)}个数据单元格")
                except:
                    pass
            
            # 如果找到数据表格，直接获取该表格的HTML
            if data_table:
                try:
                    table_html = data_table.get_attribute('outerHTML')
                    print(f"[最终检查] 数据表格HTML长度: {len(table_html):,}")
                    
                    # 验证表格HTML中是否有<td>标签
                    td_count = table_html.count('<td')
                    tr_count = table_html.count('<tr')
                    print(f"[验证] 表格HTML中：{tr_count}个<tr>标签，{td_count}个<td>标签")
                    
                    if td_count > 0:
                        # 用表格HTML替换final_html中的对应部分
                        # 或者直接使用包含该表格的完整HTML
                        print("✅ 表格HTML包含数据单元格")
                except Exception as e:
                    print(f"[警告] 获取表格HTML失败: {e}")
            
            # 🔥🔥🔥 检测并处理分页 🔥🔥🔥
            print("\n" + "="*80)
            print("[分页检测] 检查是否有多页数据...")
            all_pages_html = [final_html]  # 保存所有页面的HTML
            current_page = 1
            max_pages = 10  # 最多翻10页，防止无限循环
            
            try:
                # 检查是否有分页链接（查找"下一页"、">"、数字链接等）
                page_source = driver.page_source
                has_pagination = False
                
                # 🔥 详细检测分页元素
                print("[分页检测] 正在搜索分页容器...")
                pagination_containers = driver.find_elements(By.XPATH, "//span[contains(@id, 'af_pagehtmlLab1') or contains(@class, 'pagehtmlLab')]")
                if pagination_containers:
                    print(f"[分页检测] ✅ 找到 {len(pagination_containers)} 个分页容器")
                    for i, container in enumerate(pagination_containers):
                        try:
                            container_text = container.text
                            print(f"[分页检测] 容器 {i+1} 文本: {container_text[:100]}")
                        except:
                            pass
                
                # 检测所有可能的分页链接
                all_links = driver.find_elements(By.TAG_NAME, "a")
                pagination_links = []
                for link in all_links:
                    try:
                        link_text = link.text.strip()
                        if link_text in ['>', '<', '下一页', '上一页', 'next', 'prev'] or link_text.isdigit():
                            pagination_links.append(link_text)
                    except:
                        pass
                
                if pagination_links:
                    print(f"[分页检测] ✅ 找到分页相关链接: {set(pagination_links)}")
                    has_pagination = True
                else:
                    print(f"[分页检测] ℹ️  未找到明显的分页链接")
                
                # 检测分页的多种模式
                pagination_indicators = [
                    "下一页", "next", "Next", ">", "尾页",
                    "Page 2", "page=2", "&p=2"
                ]
                
                for indicator in pagination_indicators:
                    if indicator in page_source:
                        has_pagination = True
                        print(f"[分页检测] ✅ 检测到页面源码中的分页标识: {indicator}")
                        break
                
                if has_pagination:
                    print(f"[分页检测] 页面有分页，开始自动翻页...")
                    
                    while current_page < max_pages:
                        try:
                            # 尝试查找"下一页"或数字链接
                            next_page_found = False
                            
                            # 方法1：使用ID查找分页容器中的链接（基于af_pagehtmlLab1）
                            try:
                                # 查找分页容器
                                pagination_containers = driver.find_elements(By.XPATH, "//span[contains(@id, 'af_pagehtmlLab1') or contains(@class, 'pagehtmlLab')]")
                                if pagination_containers:
                                    print(f"[翻页] 找到 {len(pagination_containers)} 个分页容器")
                                    for container in pagination_containers:
                                        # 在容器内查找下一页链接
                                        next_links = container.find_elements(By.XPATH, ".//a[contains(text(), '>') or contains(text(), '下一页')]")
                                        if next_links:
                                            for link in next_links:
                                                if link.is_displayed() and link.is_enabled():
                                                    print(f"[翻页] 方法1成功，点击容器内的链接: {link.text}")
                                                    link.click()
                                                    next_page_found = True
                                                    break
                                        if next_page_found:
                                            break
                            except Exception as e:
                                print(f"[翻页] 方法1失败: {e}")
                            
                            # 方法2：直接查找包含">"的链接（全局搜索）
                            if not next_page_found:
                                try:
                                    next_links = driver.find_elements(By.XPATH, "//a[text()='>' or text()='下一页' or text()='next']")
                                    if next_links:
                                        print(f"[翻页] 方法2找到 {len(next_links)} 个下一页链接")
                                        for link in next_links:
                                            if link.is_displayed() and link.is_enabled():
                                                # 检查链接是否在页面底部（Y坐标较大）
                                                try:
                                                    location = link.location
                                                    if location['y'] > 200:  # 在页面下方
                                                        print(f"[翻页] 方法2成功，点击链接: {link.text} (位置: {location})")
                                                        link.click()
                                                        next_page_found = True
                                                        break
                                                except:
                                                    pass
                                except Exception as e:
                                    print(f"[翻页] 方法2失败: {e}")
                            
                            # 方法3：查找页码数字链接（如"2", "3"等）
                            if not next_page_found:
                                try:
                                    next_page_num = current_page + 1
                                    page_links = driver.find_elements(By.XPATH, f"//a[text()='{next_page_num}']")
                                    if page_links:
                                        print(f"[翻页] 方法3找到页码 {next_page_num} 的链接")
                                        for link in page_links:
                                            if link.is_displayed():
                                                print(f"[翻页] 方法3成功，点击页码: {next_page_num}")
                                                link.click()
                                                next_page_found = True
                                                break
                                except Exception as e:
                                    print(f"[翻页] 方法3失败: {e}")
                            
                            if not next_page_found:
                                print(f"[翻页] 所有方法都未找到下一页链接，停止翻页")
                                break
                            
                            # 等待新页面加载
                            time.sleep(3)
                            
                            # 滚动加载新页面的数据
                            try:
                                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                time.sleep(2)
                                driver.execute_script("window.scrollTo(0, 0);")
                                time.sleep(1)
                            except:
                                pass
                            
                            # 获取当前页的HTML
                            current_page_html = driver.page_source
                            
                            # 🔥 检查内容是否真的改变了（对比表格数据）
                            # 简单方法：检查HTML长度和部分内容
                            previous_html = all_pages_html[-1]
                            
                            # 提取表格数据特征（避免整页比较）
                            def extract_table_signature(html):
                                """提取表格的特征签名"""
                                import re
                                # 提取所有的时间戳（交易明细的时间）
                                times = re.findall(r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', html)
                                return set(times[:50])  # 只取前50条，避免内存问题
                            
                            prev_sig = extract_table_signature(previous_html)
                            curr_sig = extract_table_signature(current_page_html)
                            
                            # 计算重复度
                            if prev_sig and curr_sig:
                                overlap = len(prev_sig & curr_sig) / len(prev_sig) if len(prev_sig) > 0 else 0
                                print(f"[翻页] 内容重复度: {overlap:.1%}")
                                
                                if overlap > 0.8:  # 如果超过80%相同
                                    print(f"[翻页] ⚠️  内容几乎相同，可能未真正翻页，停止翻页")
                                    break
                            
                            current_page += 1
                            all_pages_html.append(current_page_html)
                            print(f"[翻页] ✅ 已翻到第 {current_page} 页，HTML长度: {len(current_page_html):,}")
                            
                        except Exception as e:
                            print(f"[翻页] 翻页过程出错: {e}")
                            break
                    
                    print(f"[分页检测] ✅ 翻页完成，共获取 {len(all_pages_html)} 页数据")
                else:
                    print(f"[分页检测] ℹ️  无分页，只有1页数据")
                    
            except Exception as e:
                print(f"[分页检测] 分页处理出错: {e}")
                # 出错也继续，至少有第一页的数据
            
            print("="*80 + "\n")
            
            # 使用最终HTML（第一页）
            html = final_html
            
            # 🔥 如果有多页，将所有页的表格数据合并
            if len(all_pages_html) > 1:
                print(f"[数据合并] 正在合并 {len(all_pages_html)} 页的数据...")
                # 简单方案：将所有HTML拼接（解析器会处理）
                # 或者：提取每页的<tr>标签合并到第一页的<table>中
                # 这里使用简单方案，让解析器去重处理
                html = "\n<!-- 第1页 -->\n" + all_pages_html[0]
                for i, page_html in enumerate(all_pages_html[1:], start=2):
                    html += f"\n<!-- 第{i}页 -->\n{page_html}"
                print(f"[数据合并] 合并后HTML长度: {len(html):,}")
            
            # 🔥 不再保存成功的 HTML 快照，只保留失败的用于调试
            return html
            
        except Exception as e:
            # 捕获所有异常，保存当前状态截图
            logger.error("明细抓取失败: %s", e)
            try:
                self._save_debug_screenshot(driver, prefix="detail_error")
            except:
                pass
            raise
        finally:
            # 确保driver被关闭
            if driver:
                try:
                    print("[清理] 关闭浏览器")
                    driver.quit()
                except Exception as ex:
                    print(f"[警告] 关闭浏览器失败: {ex}")

    def fetch_dynamic_page_html(
        self,
        url: str,
        wait_text: Union[str, Sequence[str]] = HEADER_KEYWORD,
        timeout: int = 35,
    ) -> str:
        """使用浏览器加载执行 JS 后的页面源码。"""
        driver = self._init_driver()
        try:
            self._inject_cookies(driver)
            target = urljoin(LOGIN_URL, url)
            driver.get(urljoin(LOGIN_URL, "/bifaw/index.php"))

            def _login_ready(d: webdriver.Chrome) -> bool:
                if "登录" in (d.title or "") and "验证码" in d.page_source:
                    return False
                return self._has_login_succeeded(d)

            try:
                WebDriverWait(driver, 6).until(_login_ready)
            except TimeoutException as exc_login:
                driver.save_screenshot(str(DEBUG_DIR / "login_failed.png"))
                raise RuntimeError(
                    "Selenium 注入 cookies 失败或登录状态已过期，请在采集控制台重新登录后再试。"
                ) from exc_login

            WebDriverWait(driver, 10).until(
                lambda d: "标盘明细" in d.page_source or "必发指数" in d.page_source
            )

            driver.execute_script(
                "window.location.href = arguments[0];", target
            )

            try:
                WebDriverWait(driver, min(timeout, 15)).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                # `document.readyState` 可能在部分 iframe 页面上恒为 "loading"，忽略此类异常
                pass

            keywords: Tuple[str, ...]
            if isinstance(wait_text, str):
                keywords = (wait_text,)
            else:
                keywords = tuple(str(item) for item in wait_text if item)

            frame_html: Optional[str] = None

            def _extract_html_with_keyword(d: webdriver.Chrome) -> Optional[str]:
                try:
                    d.switch_to.default_content()
                except Exception:
                    pass

                def _dfs() -> Optional[str]:
                    html_content = d.page_source
                    if not keywords or any(keyword in html_content for keyword in keywords):
                        return html_content

                    frames = d.find_elements(By.TAG_NAME, "iframe") + d.find_elements(By.TAG_NAME, "frame")
                    for frame in frames:
                        try:
                            d.switch_to.frame(frame)
                            nested_html = _dfs()
                            if nested_html:
                                return nested_html
                        except Exception:
                            continue
                        finally:
                            try:
                                d.switch_to.parent_frame()
                            except Exception:
                                try:
                                    d.switch_to.default_content()
                                except Exception:
                                    pass
                    return None

                result = _dfs()
                try:
                    d.switch_to.default_content()
                except Exception:
                    pass
                return result

            def _wait_for_keyword(d: webdriver.Chrome) -> bool:
                nonlocal frame_html
                result = _extract_html_with_keyword(d)
                if result:
                    frame_html = result
                    return True
                frame_html = d.page_source
                return False

            if keywords:
                try:
                    WebDriverWait(driver, timeout).until(_wait_for_keyword)
                except TimeoutException as exc:
                    html = frame_html or driver.page_source
                    if not any(keyword in html for keyword in keywords):
                        current_url = driver.current_url
                        page_title = driver.title or "未知标题"
                        debug_path = self._save_debug_html(html, prefix="timeout_without_keyword")
                        if "登录" in html or "验证码" in html:
                            logger.warning("⚠️  页面加载登录状态失效")
                            
                            # 关闭driver
                            try:
                                driver.quit()
                            except:
                                pass
                            
                            # 🔥 检查是否允许自动登录（考虑登录冷却期）
                            if self.should_auto_login():
                                logger.info("🤖 尝试自动OCR登录...")
                                ocr_success, ocr_message = self._auto_login_with_ocr()
                                if ocr_success:
                                    logger.info("✅ 自动登录成功，请重试请求")
                                    raise RuntimeError(
                                        f"登录状态已恢复，请重试请求。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                    ) from exc
                                else:
                                    logger.error(f"❌ 自动登录失败: {ocr_message}")
                                    raise RuntimeError(
                                        f"加载页面超时，疑似登录状态失效，自动登录失败({ocr_message})。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                    ) from exc
                            else:
                                # 🔥 在冷却期内，不自动登录，提示用户手动登录
                                raise RuntimeError(
                                    f"加载页面登录状态失效，但距离上次登录不到15分钟（保护手动登录），请手动登录后再试。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                                ) from exc
                        raise RuntimeError(
                            f"加载页面超时，未在页面中找到关键字“{'、'.join(keywords)}”。当前地址：{current_url}，标题：{page_title}，调试文件：{debug_path.name}"
                        ) from exc
            html = frame_html or driver.page_source
            return html
        finally:
            driver.quit()

    def _resolve_detail_url(
        self,
        *,
        detail_url: Optional[str] = None,
        match: Optional[Dict[str, object]] = None,
        detail_params: Optional[Dict[str, object]] = None,
    ) -> str:
        """
        根据比赛信息拼装标盘明细页面 URL。

        站内“标盘明细”按钮通常会通过 JS `openMatchDetails` 打开新窗口，
        该方法复用解析阶段存储的参数，构造可直接访问的链接。
        """
        if match is None:
            match = {}
        if detail_params is None:
            detail_params = {}

        if not detail_params and isinstance(match.get("detail_params"), dict):
            detail_params = match.get("detail_params") or {}

        if not detail_url:
            detail_url = (
                str(match.get("detail_url"))
                if match and match.get("detail_url")
                else None
            )

        if detail_url:
            return urljoin(LOGIN_URL, detail_url)

        # openMatchDetails(matchid, mid, opentime, homesid, awaysid, extra, flag)
        # 其中 extra 通常指 subtype，flag 为 type/flag。
        def _pick(*keys: str) -> Optional[str]:
            for key in keys:
                value = match.get(key) if match and key in match else detail_params.get(key)
                if value not in (None, "", "None"):
                    return str(value)
            return None

        # 🔥 方案1：优先尝试使用matchDetails.php方式构造（更可靠）
        match_id = _pick("match_id", "matchid")
        market_id = _pick("market_id", "marketid")
        home_sid = _pick("home_sid", "homesid")
        away_sid = _pick("away_sid", "awaysid")
        opentime = _pick("opentime", "matchtime", "open_time")
        
        if match_id and market_id:
            # 构造team_msg
            league = match.get("league") if match else None
            home = match.get("home") if match else None
            away = match.get("away") if match else None
            team_msg = f"{league or ''}@{home or ''}@{away or ''}@"
            
            constructed_url = self._construct_match_detail_url(
                match_id=match_id,
                market_id=market_id,
                home_sid=home_sid,
                away_sid=away_sid,
                opentime=opentime,
                team_msg=team_msg,
                fff="0"  # 标盘明细使用 fff=0
            )
            if constructed_url:
                print(f"[_resolve_detail_url] 使用matchDetails.php构造链接")
                return constructed_url

        # 🔥 方案2：备用方案，使用传统的sporttery.php
        query_params: Dict[str, Optional[str]] = {
            "matchid": match_id,
            "type": _pick("type", "flag") or "1",
            "oddstype": _pick("oddstype", "oddstypeid") or "1",
            "subtype": _pick("subtype", "extra", "subtypeid"),
            "mid": _pick("mid", "match_mid"),
            "matchtime": opentime,
            "homesid": home_sid,
            "awaysid": away_sid,
        }

        encoded = urlencode({k: v for k, v in query_params.items() if v})
        if not encoded:
            raise RuntimeError("缺少构造标盘明细链接所需的 match_id 参数。")

        print(f"[_resolve_detail_url] 使用sporttery.php构造链接（备用方案）")
        return urljoin(LOGIN_URL, f"/bifaw/sporttery.php?{encoded}")

    def fetch_match_detail_response(
        self,
        *,
        detail_url: Optional[str] = None,
        match: Optional[Dict[str, object]] = None,
        detail_params: Optional[Dict[str, object]] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """
        使用 requests 携带已登录 cookies 请求标盘明细页面。

        Args:
            detail_url: 已知的明细链接。
            match: `fetch_match_list` / `fetch_match_list_v2` 返回的比赛字典。
            detail_params: 备用参数，可从 openMatchDetails 解析得到。
            timeout: 请求超时时间（秒）。
        """
        target = self._resolve_detail_url(
            detail_url=detail_url,
            match=match,
            detail_params=detail_params,
        )
        session = self._build_requests_session()
        session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Referer": f"{BASE_HOST}/bifaw/index.php",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        visited: Set[str] = set()
        response = self._fetch_detail_recursive(
            session,
            target,
            timeout=timeout,
            referer=f"{BASE_HOST}/bifaw/index.php",
            visited=visited,
        )
        return response

    def fetch_match_detail_html(
        self,
        *,
        detail_url: Optional[str] = None,
        match: Optional[Dict[str, object]] = None,
        detail_params: Optional[Dict[str, object]] = None,
        wait_text: Union[str, Sequence[str]] = (HEADER_KEYWORD, "买家挂牌", "卖家挂牌"),
        timeout: int = 30,
    ) -> str:
        """
        为向后兼容保留的封装：返回标盘明细页面 HTML 文本。
        对于 PDF 类型明细将抛出异常，需改用 `fetch_match_detail_response`。
        """
        response = self.fetch_match_detail_response(
            detail_url=detail_url,
            match=match,
            detail_params=detail_params,
            timeout=timeout,
        )
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "pdf" in content_type or (detail_url or "").lower().endswith(".pdf"):
            raise RuntimeError(
                "标盘明细返回 PDF 文件，请改用 fetch_match_detail_response 获取二进制内容。"
            )
        html_text = getattr(response, "_bifaw_detail_html", None)  # type: ignore[attr-defined]
        if isinstance(html_text, str):
            return html_text
        self._normalize_response_encoding(response)
        return response.text

    def fetch_match_list(self, url: str = "/bifaw/index.php", force_refresh: bool = False, capture_real_urls: bool = True) -> List[Dict[str, Optional[str]]]:
        """
        返回标盘列表页中的比赛集合（使用Selenium获取动态链接）。
        
        Args:
            url: 标盘列表页URL
            force_refresh: 强制刷新缓存
            capture_real_urls: 是否捕获真实的matchDetails.php链接（推荐）
        """
        cache_timestamp = self._match_cache.get("timestamp", 0.0)
        if not force_refresh and cache_timestamp and time.time() - float(cache_timestamp) < 60:
            print("使用缓存数据")
            return self._match_cache.get("data", [])

        target = urljoin(BASE_HOST, url)
        driver = self._init_driver()
        try:
            self._inject_cookies(driver)
            driver.get(target)
            time.sleep(3)
            
            # 等待页面加载
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: "标盘" in d.page_source
                )
            except Exception:
                pass
            
            # 捕获真实的matchDetails.php链接
            real_url_map: Dict[str, str] = {}
            if capture_real_urls:
                try:
                    print("\n" + "="*80)
                    print("🔗 捕获标盘明细真实链接（matchDetails.php）...")
                    print("="*80)
                    from services.selenium_helper import capture_detail_urls_from_buttons
                    real_url_map = capture_detail_urls_from_buttons(driver, max_buttons=30)
                    print(f"✅ 成功捕获 {len(real_url_map)} 个真实明细链接\n")
                except Exception as e:
                    print(f"捕获真实链接失败: {e}，将使用备用sporttery.php链接\n")
            
            html = driver.page_source
            
            # 🔥 不再保存比赛列表 HTML 快照
            matches = parse_match_list(html, target)
            
            # 用真实链接替换sporttery.php链接
            if real_url_map:
                for match in matches:
                    match_key = f"{match.get('home')}_{match.get('away')}"
                    if match_key in real_url_map:
                        old_url = match.get('detail_url', '')
                        match['detail_url'] = real_url_map[match_key]
                        if 'sporttery.php' in old_url and 'matchDetails.php' in match['detail_url']:
                            print(f"已替换: {match.get('home')} vs {match.get('away')}")
            
            self._match_cache = {"timestamp": time.time(), "data": matches}
            return matches
        finally:
            driver.quit()

    def fetch_match_list_v2(self, *, rows: int = 9999, days: int = 2, future_days: int = 0, force_refresh: bool = False) -> List[Dict[str, Optional[str]]]:
        """
        通过 serveodds 接口返回更完整的比赛列表。
        
        Args:
            rows: 每天查询的比赛数量
            days: 查询过去多少天（0=只查今天，1=今天+昨天，2=今天+昨天+前天）
            future_days: 查询未来多少天（0=不查未来，1=今天+明天，2=今天+明天+后天）
            force_refresh: 强制刷新缓存
        """
        cache_timestamp = self._match_cache_v2.get("timestamp", 0.0)
        
        # 🔥 智能登录策略：只在需要时才登录（避免频繁OCR导致混乱）
        # 检查是否已登录，如果未登录才执行OCR登录
        if not self._check_login_status_quick():
            logger.info("🤖 检测到未登录，执行OCR自动登录...")
            self._auto_login_with_ocr(force=False)
        else:
            logger.debug("✅ 已登录，跳过OCR登录")
        
        session = self._build_requests_session()
        today = datetime.utcnow() + timedelta(hours=8)

        collected: Dict[str, Dict[str, Optional[str]]] = {}

        sample_path = BASE_DIR / "serveodds_sample.json"

        def _first(item: Dict[str, object], keys: List[str]) -> Optional[str]:
            for key in keys:
                if key in item and item[key]:
                    return str(item[key])
            return None

        html_detail_map: Dict[str, Dict[str, Optional[str]]] = {}
        
        # 不再预先批量获取URL，改为每场采集时单独获取
        # 这样可以避免大量并发请求的日志干扰，实现真正的串行处理
        print("\n" + "="*80)
        print("开始获取场次列表...")
        print("="*80)

        # 🔥 查询日期范围：过去 + 今天 + 未来
        date_list = []
        
        # 添加过去的日期
        for delta in range(days):
            date_list.append(today - timedelta(days=delta))
        
        # 添加未来的日期
        for delta in range(1, future_days + 1):
            date_list.append(today + timedelta(days=delta))
        
        for target_date in date_list:
            payload = {
                "year": str(target_date.year),
                "month": str(target_date.month),
                "day": str(target_date.day),
                "page": "1",
                "fff": "1" if target_date.weekday() in (5, 6) else "0",
                "rows": str(rows),
            }
            headers = {
                "Referer": f"{BASE_HOST}/bifaw/",
                "Origin": BASE_HOST,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            }

            date_str = f"{payload['year']}-{payload['month']:0>2}-{payload['day']:0>2}"
            print(f"\n[POST请求] {SERVEODDS_URL}")
            print(f"[日期参数] {date_str} (星期{'六' if target_date.weekday() == 5 else '日' if target_date.weekday() == 6 else target_date.weekday()+1})")
            response = session.post(SERVEODDS_URL, data=payload, headers=headers, timeout=20)
            response.raise_for_status()

            try:
                data_text = response.text.lstrip("\ufeff")
                data = json.loads(data_text)
                
                # 🔥 检查会话失效错误（账号在其他地方登录或未登录）
                if isinstance(data, dict) and "ErrMsg" in data:
                    err_msg = data["ErrMsg"]
                    if "别出登" in err_msg or "重新" in err_msg or "过期" in err_msg or "失效" in err_msg or "没有登" in err_msg or "登陆" in err_msg:
                        logger.warning(f"⚠️ 会话已失效: {err_msg}")
                        print(f"\n⚠️ [会话失效] {err_msg}")
                        print("🔄 尝试自动重新登录...")
                        
                        self._requests_cookie_cache = None
                        if self._local_ocr and self._local_ocr.is_enabled():
                            login_ok, login_msg = self._auto_login_with_ocr(max_retries=20)
                            if login_ok:
                                logger.info("✅ 自动重新登录成功，正在重试请求...")
                                print("✅ 登录成功，重试请求...\n")
                                session = self._build_requests_session()
                                response = session.post(SERVEODDS_URL, data=payload, headers=headers, timeout=20)
                                response.raise_for_status()
                                data_text = response.text.lstrip("\ufeff")
                                data = json.loads(data_text)
                                if isinstance(data, dict) and "ErrMsg" in data:
                                    logger.error(f"❌ 重新登录后仍然失败: {data['ErrMsg']}")
                                    continue
                            else:
                                logger.error(f"❌ 自动重新登录失败: {login_msg}")
                                print(f"❌ 自动登录失败，请手动登录后重试")
                                continue
                        else:
                            logger.warning("⚠️ OCR未启用，无法自动重新登录")
                            print("❌ OCR未启用，请手动登录后重试")
                            continue
                
                # 🔥 调试：打印响应数据类型和大小
                print(f"[{date_str}] 📦 响应数据类型: {type(data)}")
                if isinstance(data, dict):
                    print(f"[{date_str}] 📦 字典键: {list(data.keys())[:10]}")
                
            except ValueError:
                if not sample_path.exists():
                    sample_path.write_text(response.text, encoding="utf-8", errors="ignore")
                print(f"[{date_str}] ❌ JSON解析失败: {response.text[:200]}")
                raise RuntimeError(f"serveodds 返回异常：{response.text[:200]}")

            if isinstance(data, list):
                rows_data = data
            elif isinstance(data, dict):
                if any(k.startswith("a") for k in data.keys()):
                    rows_data = list(data.values())
                else:
                    rows_data = (
                        data.get("rows")
                        or data.get("data")
                        or data.get("list")
                        or data.get("matchs")
                        or []
                    )
            else:
                rows_data = []

            if isinstance(rows_data, dict):
                rows_data = (
                    rows_data.get("rows")
                    or rows_data.get("data")
                    or rows_data.get("list")
                    or list(rows_data.values())
                    or []
                )

            if not isinstance(rows_data, list):
                if not sample_path.exists():
                    sample_path.write_text(data_text, encoding="utf-8", errors="ignore")
                print(f"[{date_str}] ⚠️ 数据格式异常，跳过")
                continue

            # 🔥 添加日志：显示该日期的比赛数
            print(f"[{date_str}] 📥 获取到 {len(rows_data)} 场比赛")
            
            for item in rows_data:
                if not isinstance(item, dict):
                    continue

                info_str = item.get("info")
                info_parts: List[str] = []
                if isinstance(info_str, str):
                    info_parts = [part.strip() for part in info_str.split(",")]

                match_id = _first(item, [
                    "matchid",
                    "MatchID",
                    "matchId",
                    "mid",
                ])
                if not match_id and len(info_parts) >= 7:
                    match_id = info_parts[6]
                if not match_id:
                    continue

                league = _first(item, [
                    "league",
                    "League",
                    "leaguecn",
                    "LeagueCN",
                    "league_cn",
                    "LeagueName",
                    "leagueName",
                ]) or (info_parts[1] if len(info_parts) > 1 else None)
                home = _first(item, [
                    "hometeam",
                    "Home",
                    "home",
                    "hname",
                    "HomeTeam",
                    "HomeName",
                ]) or (info_parts[4] if len(info_parts) > 4 else None)
                away = _first(item, [
                    "awayteam",
                    "Away",
                    "away",
                    "aname",
                    "AwayTeam",
                    "AwayName",
                ]) or (info_parts[5] if len(info_parts) > 5 else None)

                kickoff: Optional[str] = None
                kickoff_value = _first(item, [
                    "matchtime",
                    "MatchTime",
                    "match_time",
                    "startTime",
                    "StartTime",
                ]) or (info_parts[3] if len(info_parts) > 3 else None)
                if kickoff_value:
                    try:
                        kickoff_dt = datetime.fromtimestamp(int(kickoff_value), tz=timezone.utc) + timedelta(hours=8)
                        kickoff = kickoff_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        kickoff = kickoff_value

                detail_url = _first(item, [
                    "detailurl",
                    "DetailUrl",
                    "url",
                    "Url",
                ])

                oddstype = _first(item, ["oddstype", "OddsType", "OddsTypeID", "oddstypeid"]) or (info_parts[12] if len(info_parts) > 12 else None)
                match_type = _first(item, ["type", "Type"]) or (info_parts[11] if len(info_parts) > 11 else None)
                subtype = _first(item, ["subtype", "SubType", "subOddstype", "OddstypeSub"]) or (info_parts[13] if len(info_parts) > 13 else None)

                if not match_type:
                    match_type = "1"
                if not oddstype:
                    oddstype = "1"

                html_params = html_detail_map.get(str(match_id), {}).get("detail_params")

                flag_type = (
                    (html_params or {}).get("flag")
                    or match_type
                    or (html_detail_map.get(str(match_id), {}) or {}).get("type")
                )
                if not flag_type:
                    flag_type = "1"

                oddstype_value = oddstype or "1"
                subtype_value = subtype or ((html_params or {}).get("extra") or None)

                query_params: Dict[str, Optional[str]] = {
                    "matchid": match_id,
                    "type": flag_type,
                    "oddstype": oddstype_value,
                }
                if subtype_value:
                    query_params["subtype"] = subtype_value

                if html_params:
                    param_mapping = {
                        "match_mid": "mid",
                        "open_time": "matchtime",
                        "home_sid": "homesid",
                        "away_sid": "awaysid",
                    }
                    for source_key, target_key in param_mapping.items():
                        value = html_params.get(source_key)
                        if value:
                            query_params[target_key] = value

                # 🔥 提取用于构造matchDetails.php的参数
                # info字段格式分析（索引从0开始）：
                # [0]=?, [1]=联赛, [2]=?, [3]=时间戳, [4]=主队, [5]=客队, [6]=match_id,
                # [7]=?, [8-18]=?, [19]=market_id, [20]=home_sid, [21]=away_sid
                match_mid = None
                home_sid = None
                away_sid = None
                market_id = None
                
                # 从info_parts提取参数（正确的索引位置）
                if len(info_parts) > 19:
                    market_id = info_parts[19].strip() if info_parts[19] else None
                if len(info_parts) > 20:
                    home_sid = info_parts[20].strip() if info_parts[20] else None
                if len(info_parts) > 21:
                    away_sid = info_parts[21].strip() if info_parts[21] else None
                
                # 从macth字段提取market_id（backup，如果info中没有）
                if not market_id:
                    macth_data = item.get("macth") or item.get("Macth")
                    if isinstance(macth_data, str):
                        macth_parts = macth_data.split(",")
                        if len(macth_parts) > 0 and macth_parts[0].strip():
                            match_mid = macth_parts[0].strip()
                            market_id = match_mid

                # 构造明细URL（优先使用matchDetails.php方式）
                if detail_url:
                    detail_url = urljoin(LOGIN_URL, detail_url)
                elif market_id:
                    # 🔥 方案1：构造matchDetails.php URL（推荐）
                    # 添加排名信息到队名（如果有的话）
                    home_rank = info_parts[13] if len(info_parts) > 13 and info_parts[13] else None
                    away_rank = info_parts[14] if len(info_parts) > 14 and info_parts[14] else None
                    
                    home_with_rank = f"{home}[{home_rank}]" if home_rank else home
                    away_with_rank = f"{away}[{away_rank}]" if away_rank else away
                    
                    team_msg = f"{league}@{home_with_rank}@{away_with_rank}@"
                    constructed_url = self._construct_match_detail_url(
                        match_id=match_id,
                        market_id=market_id,
                        home_sid=home_sid,
                        away_sid=away_sid,
                        opentime=kickoff_value,
                        team_msg=team_msg,
                        fff="0"  # 标盘明细使用 fff=0
                    )
                    if constructed_url:
                        detail_url = constructed_url
                    else:
                        # 备用方案：使用sporttery.php
                        detail_url = (
                            f"{BASE_HOST}/bifaw/sporttery.php?"
                            + urlencode({k: v for k, v in query_params.items() if v})
                        )
                else:
                    # 🔥 方案2：备用方案，使用sporttery.php
                    detail_url = (
                        f"{BASE_HOST}/bifaw/sporttery.php?"
                        + urlencode({k: v for k, v in query_params.items() if v})
                    )

                label_parts = [kickoff, league, home, "vs", away]
                label = " ".join(part for part in label_parts if part)

                collected[match_id] = {
                    "match_id": match_id,
                    "league": league,
                    "kickoff": kickoff,
                    "home": home,
                    "away": away,
                    "label": label or (f"{home} vs {away}" if home or away else match_id),
                    "detail_url": detail_url,
                    "type": flag_type,
                    "oddstype": oddstype_value,
                    "subtype": subtype_value,
                    "detail_params": html_params or {},
                    "market_id": market_id,  # 保存market_id
                    "home_sid": home_sid,     # 保存home_sid
                    "away_sid": away_sid,     # 保存away_sid
                    "opentime": kickoff_value,  # 保存opentime
                    "raw": item,
                }

        matches = list(collected.values())
        matches.sort(key=lambda x: x.get("kickoff") or "")
        
        # 统计URL构造方式
        matchdetails_count = sum(1 for m in matches if m.get("detail_url") and "matchDetails.php" in m["detail_url"])
        sporttery_count = sum(1 for m in matches if m.get("detail_url") and "sporttery.php" in m["detail_url"])
        print(f"\n[标盘明细] 找到 {len(matches)} 场比赛")
        print(f"[URL构造] matchDetails.php: {matchdetails_count} 场")
        print(f"[URL构造] sporttery.php: {sporttery_count} 场")

        for match in matches:
            match_id_key = str(match.get("match_id"))
            html_info = html_detail_map.get(match_id_key)
            if not html_info:
                continue

            if not match.get("detail_url") and html_info.get("detail_url"):
                match["detail_url"] = html_info["detail_url"]

            if html_info.get("detail_params"):
                match["detail_params"] = html_info["detail_params"]

            if html_info.get("label") and not match.get("label"):
                match["label"] = html_info["label"]

        # 🔥 添加日志：显示查询摘要
        print(f"\n{'='*80}")
        print(f"📊 查询摘要:")
        print(f"  查询范围: 过去{days}天 + 未来{future_days}天")
        print(f"  总共获取: {len(matches)} 场比赛")
        print(f"  每天限制: {rows} 场")
        print(f"{'='*80}\n")
        
        self._match_cache_v2 = {"timestamp": time.time(), "data": matches}
        return matches

    def _construct_match_detail_url(
        self,
        match_id: str,
        market_id: Optional[str],
        home_sid: Optional[str],
        away_sid: Optional[str],
        opentime: Optional[str],
        team_msg: Optional[str],
        fff: str = "0"
    ) -> Optional[str]:
        """
        构造matchDetails.php URL（通用方法）
        
        Args:
            match_id: 比赛ID
            market_id: 市场ID（从macth字段提取）
            home_sid: 主队sid
            away_sid: 客队sid  
            opentime: 开赛时间（时间戳）
            team_msg: 比赛信息
            fff: 标识符（0=标盘明细，4=完场回查）
            
        Returns:
            完整的matchDetails.php URL，如果参数不足则返回None
        """
        import base64
        from urllib.parse import quote
        
        # 检查必要参数
        if not match_id or not market_id:
            return None
        
        # 构造getuid参数内容
        # 格式: tmiid=XXX&marketid=XXX&home_sid=XXX&away_sid=XXX&opentime=XXX&fff=X&teammsg=XXX&
        params_parts = [
            f"tmiid={match_id}",
            f"marketid={market_id}",
        ]
        
        if home_sid:
            params_parts.append(f"home_sid={home_sid}")
        if away_sid:
            params_parts.append(f"away_sid={away_sid}")
        if opentime:
            params_parts.append(f"opentime={opentime}")
        
        # fff参数：0=标盘明细，4=完场回查
        params_parts.append(f"fff={fff}")
        
        if team_msg:
            # 对team_msg进行URL编码（保留@符号不编码）
            encoded_msg = quote(team_msg, safe='@')
            params_parts.append(f"teammsg={encoded_msg}")
        
        # 拼接参数并添加结尾的&
        params_str = "&".join(params_parts) + "&"
        
        # Base64编码
        getuid = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')
        
        # 构造完整URL
        detail_url = f"{BASE_HOST}/bifaw/matchDetails.php?getuid={getuid}"
        
        return detail_url
    
    def _construct_ou_detail_url(
        self,
        match_id: str,
        market_id: Optional[str],
        home_sid: Optional[str],
        away_sid: Optional[str],
        opentime: Optional[str],
        team_msg: Optional[str],
        hdp: Optional[str] = None,  # 大小球盘口值
        ou_market_id: Optional[str] = None,  # 大小球市场ID
        fff: str = "0",  # 🔥 默认fff=0（实时比赛），fff=4是完场回查
    ) -> Optional[str]:
        """
        构造大小球明细页面URL (ouDetails.php)
        
        Args:
            match_id: 比赛ID
            market_id: 市场ID
            home_sid: 主队sid
            away_sid: 客队sid  
            opentime: 开赛时间（时间戳）
            team_msg: 比赛信息
            hdp: 大小球盘口值（如2.5）
            ou_market_id: 大小球市场ID
            fff: 标识符（0=实时比赛，4=完场回查）
            
        Returns:
            完整的ouDetails.php URL
        """
        import base64
        from urllib.parse import quote
        
        if not match_id:
            return None
        
        # 使用大小球市场ID（如果有）
        # 🔥 如果没有market_id，使用match_id作为备选（有些比赛可以工作）
        actual_market_id = ou_market_id or market_id or match_id
        
        # 构造getuid参数
        params_parts = [
            f"tmiid={match_id}",
            f"opentime={opentime}" if opentime else None,
            f"marketid={actual_market_id}",
        ]
        
        # 过滤None值
        params_parts = [p for p in params_parts if p]
        
        if home_sid:
            params_parts.append(f"home_sid={home_sid}")
        if away_sid:
            params_parts.append(f"away_sid={away_sid}")
        
        # hdp参数是必须的（大小球盘口值）
        if hdp:
            params_parts.append(f"hdp={hdp}")
        
        # 🔥 fff=0 表示实时比赛，fff=4 表示完场回查
        params_parts.append(f"fff={fff}")
        
        if team_msg:
            encoded_msg = quote(team_msg, safe='@')
            params_parts.append(f"teammsg={encoded_msg}")
        
        params_str = "&".join(params_parts) + "&"
        getuid = base64.b64encode(params_str.encode('utf-8')).decode('utf-8')
        
        return f"{BASE_HOST}/bifaw/ouDetails.php?getuid={getuid}"
    
    def fetch_ou_trade_details(
        self,
        match: Dict,
        timeout: int = 30
    ) -> Optional[Dict]:
        """
        获取大小球交易明细数据
        
        Args:
            match: 比赛数据字典（包含match_info）
            timeout: 超时时间
            
        Returns:
            大小球交易明细数据
        """
        match_info = match.get('match_info', {})
        
        match_id = match_info.get('match_id')
        market_id = match_info.get('market_id')
        home_sid = match_info.get('home_sid')
        away_sid = match_info.get('away_sid')
        opentime = match_info.get('opentime')
        
        # 从raw.ou提取大小球信息
        # ou格式: marketid,vol1,vol2,odds1,...,hdp,ou_market_id,...
        raw_ou = match_info.get('raw', {}).get('ou', [])
        hdp = None
        ou_market_id = None
        
        if raw_ou and len(raw_ou) > 0:
            ou_parts = raw_ou[0].split(',')
            if len(ou_parts) > 16:
                # 索引15是盘口值，索引0可能是market_id
                hdp = ou_parts[15] if ou_parts[15] else None
                ou_market_id = ou_parts[0] if ou_parts[0] else None
        
        league = match_info.get('league', '')
        home = match_info.get('home', '')
        away = match_info.get('away', '')
        score = match_info.get('score', '')
        # 🔥 修正team_msg格式（不带结尾的&）
        team_msg = f"{league}@{home}@{away}@{score}"
        
        ou_url = self._construct_ou_detail_url(
            match_id=match_id,
            market_id=market_id,
            home_sid=home_sid,
            away_sid=away_sid,
            opentime=opentime,
            team_msg=team_msg,
            hdp=hdp,
            ou_market_id=ou_market_id,
            fff="0"  # 🔥 实时比赛使用fff=0
        )
        
        if not ou_url:
            return None
        
        try:
            import requests
            
            # 获取cookies（使用已登录的cookies）
            try:
                cookies = self._load_requests_cookies()
            except:
                cookies = {}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': 'https://www.bifaw.com/',
            }
            
            response = requests.get(ou_url, headers=headers, cookies=cookies, timeout=timeout)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                return None
            
            # 检查是否需要登录（检查是否是错误页面）
            if '提交的参数有误' in response.text or '请先在采集控制台完成登录' in response.text:
                print("⚠️ bifaw需要登录或参数错误")
                return None
            
            # 检查是否是有效的大小球明细页面
            if '大小明细' not in response.text and 'ouDetails' not in response.text:
                print("⚠️ 未获取到有效的大小球明细页面")
                return None
            
            return self._parse_ou_trade_details(response.text)
            
        except Exception as e:
            print(f"获取大小球明细失败: {e}")
            return None

    def fetch_ou_trade_details_selenium(
        self,
        match: Dict,
        timeout: int = 40,
        is_finished: bool = True  # 🔥 默认为完场比赛
    ) -> Optional[Dict]:
        """
        使用Selenium获取大小球交易明细数据（动态加载页面）
        
        🔥 重写版本：参照 fetch_match_detail_selenium 的健壮实现
        
        Args:
            match: 比赛数据字典（包含match_info）
            timeout: 超时时间
            is_finished: 是否为完场比赛（True=fff=4, False=fff=0）
            
        Returns:
            大小球交易明细数据
        """
        match_info = match.get('match_info', {})
        
        # 🔥🔥🔥 优先使用预先捕获的ou_detail_url
        ou_url = match_info.get('ou_detail_url')
        hdp = match_info.get('ou_hdp')  # 预先存储的盘口值
        
        if ou_url:
            logger.info(f"使用预先捕获的大小球明细URL")
        else:
            # 没有预先捕获的URL，尝试自己构造（可能不准确）
            logger.warning("⚠️ 没有预先捕获的URL，尝试自己构造（可能参数不正确）")
            
            match_id = match_info.get('match_id')
            market_id = match_info.get('market_id')
            home_sid = match_info.get('home_sid')
            away_sid = match_info.get('away_sid')
            opentime = match_info.get('opentime')
            
            # 🔥 初始化变量
            ou_market_id = None
            
            # 从raw.ou提取大小球信息
            raw_ou = match_info.get('raw', {}).get('ou', [])
            
            if raw_ou and len(raw_ou) > 0:
                ou_parts = raw_ou[0].split(',')
                if len(ou_parts) > 16:
                    hdp = ou_parts[15] if ou_parts[15] else None
                    ou_market_id = ou_parts[16] if ou_parts[16] else None
            
            league = match_info.get('league', '')
            home = match_info.get('home', '')
            away = match_info.get('away', '')
            score = match_info.get('score', '')
            team_msg = f"{league}@{home}@{away}@{score}"
            
            fff_value = "4" if is_finished else "0"
            
            # 🔥🔥🔥 大小球URL不使用标盘的home_sid/away_sid
            # 因为大小球使用不同的sid体系，传错的参数会导致页面报错
            ou_url = self._construct_ou_detail_url(
                match_id=match_id,
                market_id=None,  # 不使用标盘market_id
                home_sid=None,   # 🔥 不传，避免参数错误
                away_sid=None,   # 🔥 不传，避免参数错误
                opentime=opentime,
                team_msg=team_msg,
                hdp=hdp,
                ou_market_id=ou_market_id,  # 使用大小球专用的market_id
                fff=fff_value
            )
        
        if not ou_url:
            logger.warning("无法构造大小球明细URL")
            return None
        
        logger.info(f"🎯 大小球明细URL: {ou_url}")
        print(f"\n" + "="*80)
        print(f"[大小球明细页面] {ou_url}")
        print(f"你可以手动访问此URL来检查是否能正常打开")
        print("="*80 + "\n")
        
        driver = None
        try:
            driver = self._init_driver()
            
            # 🔥 注入cookies并验证登录状态（参照标盘明细的做法）
            logger.info("开始注入cookies并验证登录状态")
            try:
                self._inject_cookies(driver)
            except RuntimeError as e:
                if "尚未登录" in str(e) or "cookies" in str(e).lower():
                    logger.warning(f"⚠️ {e}，尝试自动登录...")
                    if self._local_ocr and self._local_ocr.is_enabled():
                        success, msg = self._auto_login_with_ocr(max_retries=20)
                        if success:
                            logger.info("✅ 自动登录成功，重试注入cookies")
                            self._inject_cookies(driver)
                        else:
                            logger.error(f"❌ 自动登录失败: {msg}")
                            raise
                    else:
                        raise
                else:
                    raise
            
            # 先访问主页验证登录
            driver.get(urljoin(LOGIN_URL, "/bifaw/index.php"))
            time.sleep(2)
            
            # 保存初始窗口句柄
            original_window = driver.current_window_handle
            initial_windows = set(driver.window_handles)
            
            # 🔥 在新窗口中打开大小球明细（模拟点击按钮打开新窗口）
            logger.info("正在访问大小球明细页面...")
            driver.execute_script(f"window.open('{ou_url}', '_blank');")
            
            # 等待新窗口出现
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(set(d.window_handles)) > len(initial_windows)
                )
            except TimeoutException:
                logger.warning("未检测到新窗口，尝试在当前窗口处理")
            
            # 切换到新窗口
            new_windows = set(driver.window_handles) - initial_windows
            if new_windows:
                new_window = new_windows.pop()
                logger.info(f"切换到新窗口: {new_window}")
                driver.switch_to.window(new_window)
            
            # 🔥 等待页面初始加载（优化：减少等待）
            time.sleep(1.5)
            
            # 🔥🔥🔥 等待AJAX数据加载（优化版）
            logger.info("等待数据加载...")
            max_wait = 10  # 从20秒减少到10秒
            check_interval = 1  # 从2秒减少到1秒
            waited = 0
            
            while waited < max_wait:
                try:
                    # 检查table_1
                    table = driver.find_element(By.ID, "table_1")
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    data_rows = [r for r in rows if r.find_elements(By.TAG_NAME, "td")]
                    
                    if len(data_rows) > 0:
                        logger.info(f"✅ table_1数据加载完成，{len(data_rows)}行数据")
                        break
                    
                    # 🔥 尝试点击"大球"或"小球"标签触发加载
                    tabs = driver.find_elements(By.CSS_SELECTOR, ".tabs li, .tab-item, li[onclick]")
                    for tab in tabs:
                        try:
                            tab_text = tab.text.strip()
                            if '大球' in tab_text or '小球' in tab_text:
                                print(f"[大小球] 点击标签: {tab_text}")
                                tab.click()
                                time.sleep(1)
                                break
                        except:
                            pass
                except Exception as e:
                    print(f"[大小球] 检查失败: {e}")
                
                # 滚动（优化：减少等待）
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.8)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.2)
                waited += 1
            
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # 🔥 等待table_1中有实际数据行（优化：减少超时）
            try:
                logger.info("等待数据表格加载...")
                
                def check_data_rows(d):
                    try:
                        table = d.find_element(By.ID, "table_1")
                        rows = table.find_elements(By.TAG_NAME, "tr")
                        # 至少要有2行（1行表头+1行数据）
                        return len(rows) > 1
                    except:
                        return False
                
                WebDriverWait(driver, 10).until(check_data_rows)  # 从30秒减少到10秒
                
                # 检查实际行数
                table = driver.find_element(By.ID, "table_1")
                rows = table.find_elements(By.TAG_NAME, "tr")
                logger.info(f"✅ table_1 有 {len(rows)} 行数据")
            except TimeoutException:
                logger.warning("⚠️ 等待数据超时，table_1可能为空")
            except Exception as e:
                logger.warning(f"⚠️ 检查表格失败: {e}")
            
            # 额外等待确保数据完全加载（优化：减少等待）
            time.sleep(1)
            
            # 🔥🔥🔥 获取数据表格HTML（参照标盘明细的做法）
            print("[大小球] 从DOM获取渲染后的HTML...")
            try:
                final_html = driver.execute_script("return document.documentElement.outerHTML;")
                print(f"[大小球] HTML长度: {len(final_html):,}")
            except Exception as e:
                logger.warning(f"execute_script失败: {e}")
                final_html = driver.page_source
            
            # 🔥 检查数据表格是否有数据
            final_tables = driver.find_elements(By.TAG_NAME, "table")
            max_rows = 0
            data_table = None
            for table in final_tables:
                try:
                    trs = table.find_elements(By.TAG_NAME, "tr")
                    tds = table.find_elements(By.TAG_NAME, "td")
                    if len(tds) > 0 and len(trs) > max_rows:
                        max_rows = len(trs)
                        data_table = table
                        print(f"[大小球] 找到数据表格：{len(trs)}行，{len(tds)}个数据单元格")
                except:
                    pass
            
            # 🔥🔥🔥 分页检测和翻页
            all_pages_html = [final_html]
            current_page = 1
            max_pages = 10
            
            try:
                # 检测分页链接
                all_links = driver.find_elements(By.TAG_NAME, "a")
                has_next = any(link.text.strip() == '下一页' for link in all_links if link.text.strip())
                
                if has_next:
                    print(f"[大小球] 检测到分页，开始翻页...")
                    
                    while current_page < max_pages:
                        # 查找下一页链接
                        next_links = [link for link in driver.find_elements(By.TAG_NAME, "a") 
                                     if link.text.strip() == '下一页']
                        if not next_links:
                            break
                        
                        try:
                            # 记录当前内容
                            prev_html = driver.page_source
                            
                            # 点击下一页（优化：减少等待）
                            next_links[0].click()
                            time.sleep(1)
                            
                            # 获取新页面内容
                            new_html = driver.execute_script("return document.documentElement.outerHTML;")
                            
                            # 检查内容是否变化
                            if new_html[:5000] == prev_html[:5000]:
                                print(f"[大小球] 翻页后内容未变化，停止")
                                break
                            
                            all_pages_html.append(new_html)
                            current_page += 1
                            print(f"[大小球] 已获取第 {current_page} 页")
                        except Exception as e:
                            print(f"[大小球] 翻页失败: {e}")
                            break
                    
                    print(f"[大小球] 翻页完成，共 {len(all_pages_html)} 页")
            except Exception as e:
                print(f"[大小球] 分页检测失败: {e}")
            
            # 🔥 合并所有页面的HTML
            if len(all_pages_html) > 1:
                final_html = '\n'.join(all_pages_html)
                print(f"[大小球] 合并后HTML长度: {len(final_html):,}")
            
            # 🔥 检查是否有"没有数据"的提示（只在table_1确实为空时才判断为无数据）
            page_text = driver.page_source
            # 先检查table_1是否真的有数据
            try:
                table_rows = driver.find_elements(By.CSS_SELECTOR, "#table_1 tr")
                has_data_rows = len(table_rows) > 1  # 超过1行（包含表头）说明有数据
            except:
                has_data_rows = False
            
            # 只有在table没有数据行且出现无数据提示时，才判断为无数据
            if not has_data_rows and ('没有更多' in page_text or '暂无数据' in page_text or '离线交易数据' in page_text):
                logger.warning("⚠️ 该比赛没有大小球交易数据")
                return {
                    'trade_records': [],
                    'total_records': 0,
                    'summary': {},
                    'hdp': hdp,
                    'no_data_reason': '该比赛没有大小球交易历史数据'
                }
            
            # 检查是否需要登录
            if '你还没有登陆' in final_html or '尚未登录' in final_html:
                logger.warning("⚠️ 大小球明细页面需要登录")
                self._save_debug_html(final_html, prefix="ou_detail_need_login")
                return None
            
            # 保存调试HTML
            debug_path = self._save_debug_html(final_html, prefix="ou_detail")
            logger.info(f"已保存大小球明细调试HTML: {debug_path.name}")
            
            # 解析数据
            result = self._parse_ou_trade_details_selenium(final_html, hdp=hdp)
            
            if result:
                logger.info(f"✅ 大小球明细获取成功: {result.get('total_records', 0)} 条记录")
            else:
                logger.warning("⚠️ 大小球明细解析失败")
            
            return result
            
        except Exception as e:
            logger.error(f"Selenium获取大小球明细失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def _parse_ou_trade_details_selenium(self, html: str, hdp: Optional[str] = None) -> Optional[Dict]:
        """
        解析Selenium获取的大小球交易明细页面
        
        🔥 重写版本：根据实际页面结构解析
        
        表格结构（参照截图）:
        成交时间 | 已成交量 | 大球 | 成交量 | 大成交比例 | 赔率 | 卖均 | STDp | 小球 | 成交量 | 小成交比例 | 赔率 | ...
        """
        from bs4 import BeautifulSoup
        import re
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            trade_records = []
            
            # 🔥 查找数据表格 - 尝试多种方式
            # 1. 优先查找table_1（实际数据在这里）
            main_table = soup.find('table', {'id': 'table_1'})
            
            # 2. 如果没找到，查找包含class="item"的tr的表格
            if not main_table:
                for table in soup.find_all('table'):
                    item_rows = table.find_all('tr', class_='item')
                    if item_rows:
                        main_table = table
                        break
            
            # 3. 查找Daohang_table_1（备用）
            if not main_table:
                main_table = soup.find('table', {'id': 'Daohang_table_1'})
            
            # 4. 查找包含日期格式的表格（12-xx格式）
            if not main_table:
                for table in soup.find_all('table'):
                    table_html = str(table)
                    if re.search(r'12-\d{2}\s+\d{2}:\d{2}', table_html):
                        main_table = table
                        break
            
            # 5. 查找行数最多的表格
            if not main_table:
                max_rows = 0
                for table in soup.find_all('table'):
                    rows = table.find_all('tr')
                    if len(rows) > max_rows:
                        max_rows = len(rows)
                        main_table = table
            
            if main_table:
                rows = main_table.find_all('tr')
                logger.info(f"找到数据表格，共 {len(rows)} 行")
                
                # 解析表头确定列位置
                header_row = None
                data_start_idx = 0
                
                for i, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join([c.get_text(strip=True) for c in cells])
                    if '成交时间' in row_text:
                        header_row = row
                        data_start_idx = i + 1
                        break
                
                # 解析数据行
                for row in rows[data_start_idx:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 7:
                        continue
                    
                    # 提取数据
                    time_text = cells[0].get_text(strip=True)
                    if not time_text or time_text == '成交时间' or not re.match(r'\d{2}-\d{2}', time_text):
                        continue
                    
                    try:
                        # 🔥 修正字段映射，对应实际HTML列顺序：
                        # 成交时间|总成交量|SB大|价位|已成交量|现成交量|方式|赔付率|比例|必指|赔指|赢亏|赔付|
                        # SB小|价位|已成交量|现成交量|方式|赔付率|比例|必指|赔指|赢亏|赔付|SB大小
                        record = {
                            'time': time_text,                                                      # 0: 成交时间
                            'total_volume': cells[1].get_text(strip=True) if len(cells) > 1 else '',# 1: 总成交量
                            # 大球数据
                            'over_sb': cells[2].get_text(strip=True) if len(cells) > 2 else '',     # 2: SB大
                            'over_price': cells[3].get_text(strip=True) if len(cells) > 3 else '',  # 3: 价位
                            'over_volume': cells[4].get_text(strip=True) if len(cells) > 4 else '', # 4: 已成交量
                            'over_current': cells[5].get_text(strip=True) if len(cells) > 5 else '',# 5: 现成交量
                            'over_method': cells[6].get_text(strip=True) if len(cells) > 6 else '', # 6: 方式(买/卖)
                            'over_payout_rate': cells[7].get_text(strip=True) if len(cells) > 7 else '', # 7: 赔付率
                            'over_ratio': cells[8].get_text(strip=True) if len(cells) > 8 else '',  # 8: 比例
                            'over_bifa': cells[9].get_text(strip=True) if len(cells) > 9 else '',   # 9: 必指
                            'over_odds_idx': cells[10].get_text(strip=True) if len(cells) > 10 else '', # 10: 赔指
                            'over_win_loss': cells[11].get_text(strip=True) if len(cells) > 11 else '', # 11: 赢亏
                            'over_payout': cells[12].get_text(strip=True) if len(cells) > 12 else '',   # 12: 赔付
                            # 小球数据
                            'under_sb': cells[13].get_text(strip=True) if len(cells) > 13 else '',  # 13: SB小
                            'under_price': cells[14].get_text(strip=True) if len(cells) > 14 else '',# 14: 价位
                            'under_volume': cells[15].get_text(strip=True) if len(cells) > 15 else '',# 15: 已成交量
                            'under_current': cells[16].get_text(strip=True) if len(cells) > 16 else '',# 16: 现成交量
                            'under_method': cells[17].get_text(strip=True) if len(cells) > 17 else '',# 17: 方式
                            'under_payout_rate': cells[18].get_text(strip=True) if len(cells) > 18 else '', # 18: 赔付率
                            'under_ratio': cells[19].get_text(strip=True) if len(cells) > 19 else '',# 19: 比例
                            'under_bifa': cells[20].get_text(strip=True) if len(cells) > 20 else '', # 20: 必指
                            'under_odds_idx': cells[21].get_text(strip=True) if len(cells) > 21 else '', # 21: 赔指
                            'under_win_loss': cells[22].get_text(strip=True) if len(cells) > 22 else '', # 22: 赢亏
                            'under_payout': cells[23].get_text(strip=True) if len(cells) > 23 else '',   # 23: 赔付
                            # SB大小差
                            'sb_diff': cells[24].get_text(strip=True) if len(cells) > 24 else '',   # 24: SB大小
                        }
                        trade_records.append(record)
                    except Exception as e:
                        logger.debug(f"解析行失败: {e}")
                        continue
            else:
                logger.warning("未找到数据表格")
            
            # 获取统计信息
            summary = {}
            summary_text = soup.get_text()
            
            # 大小总成交量
            vol_match = re.search(r'总成交[量]*[：:\s]*([\d,]+)', summary_text)
            if vol_match:
                summary['total_volume'] = vol_match.group(1).replace(',', '')
            
            # 尝试提取大小球各自的成交量
            over_vol_match = re.search(r'大[球]*[成交量：:\s]*([\d,]+)', summary_text)
            if over_vol_match:
                summary['over_volume'] = over_vol_match.group(1).replace(',', '')
            
            under_vol_match = re.search(r'小[球]*[成交量：:\s]*([\d,]+)', summary_text)
            if under_vol_match:
                summary['under_volume'] = under_vol_match.group(1).replace(',', '')
            
            logger.info(f"解析完成: {len(trade_records)} 条记录")
            
            return {
                'trade_records': trade_records,
                'total_records': len(trade_records),
                'summary': summary,
                'hdp': hdp,
            }
            
        except Exception as e:
            logger.error(f"解析大小球明细失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_ou_trade_details(self, html: str) -> Optional[Dict]:
        """解析大小球交易明细页面"""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 找交易明细表格
            table = soup.find('table', {'class': 'gd'}) or soup.find('table', {'id': 'table'})
            if not table:
                tables = soup.find_all('table')
                for t in tables:
                    rows = t.find_all('tr')
                    if len(rows) > 5:
                        table = t
                        break
            
            if not table:
                return None
            
            rows = table.find_all('tr')
            trade_records = []
            
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all(['td', 'th'])
                if len(cells) < 8:
                    continue
                
                try:
                    record = {
                        'time': cells[0].get_text(strip=True),
                        'volume': cells[1].get_text(strip=True),
                        'total_volume': cells[2].get_text(strip=True),
                        'over_odds': cells[3].get_text(strip=True),
                        'line': cells[4].get_text(strip=True),
                        'under_odds': cells[5].get_text(strip=True),
                        'direction': cells[6].get_text(strip=True) if len(cells) > 6 else '',
                    }
                    trade_records.append(record)
                except:
                    continue
            
            # 获取总成交量等统计
            summary = {}
            for text in soup.stripped_strings:
                if '大小总成交量' in text or '总成交' in text:
                    import re
                    match = re.search(r'[\d,]+', text)
                    if match:
                        summary['total_volume'] = match.group().replace(',', '')
            
            return {
                'trade_records': trade_records,
                'total_records': len(trade_records),
                'summary': summary,
            }
            
        except Exception as e:
            print(f"解析大小球明细失败: {e}")
            return None

    def _construct_finished_match_detail_url(
        self,
        match_id: str,
        market_id: Optional[str],
        home_sid: Optional[str],
        away_sid: Optional[str],
        opentime: Optional[str],
        team_msg: Optional[str]
    ) -> Optional[str]:
        """
        构造完场比赛的matchDetails.php URL（备用方案）
        
        Args:
            match_id: 比赛ID
            market_id: 市场ID（从macth字段提取）
            home_sid: 主队sid
            away_sid: 客队sid  
            opentime: 开赛时间（时间戳）
            team_msg: 比赛信息
            
        Returns:
            完整的matchDetails.php URL，如果参数不足则返回None
        """
        # fff=4 表示完场回查
        return self._construct_match_detail_url(
            match_id=match_id,
            market_id=market_id,
            home_sid=home_sid,
            away_sid=away_sid,
            opentime=opentime,
            team_msg=team_msg,
            fff="4"
        )
    
    def _capture_finished_match_urls(
        self, 
        driver,
        target_date: datetime,
        max_buttons: int = 100
    ) -> Dict[str, str]:
        """
        访问完场回查页面，点击'标盘明细'按钮获取真实的明细链接
        
        Args:
            driver: Selenium WebDriver实例
            target_date: 目标日期
            max_buttons: 最多点击的按钮数量
            
        Returns:
            Dict[match_id, detail_url]: match_id到真实明细URL的映射
        """
        from .selenium_helper import capture_detail_urls_from_buttons
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        url_map = {}
        
        try:
            # 方法1：先访问首页建立session
            index_url = urljoin(LOGIN_URL, "/bifaw/index.php")
            print(f"\n[Selenium] 先访问首页建立session: {index_url}")
            driver.get(index_url)
            time.sleep(2)
            
            # 方法2：尝试点击导航菜单进入完场回查
            try:
                # 等待链接可点击
                result_link = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'result.php')]"))
                )
                print("[完场回查] 找到完场回查链接，点击进入...")
                result_link.click()
                time.sleep(3)
            except Exception as e:
                # 如果找不到链接或点击失败，直接访问URL（带日期参数）
                date_str = f"{target_date.year}-{target_date.month}-{target_date.day}"
                print(f"[完场回查] 直接访问result.php（带日期参数: {date_str}）")
                result_url = urljoin(LOGIN_URL, f"/bifaw/result.php?rq={date_str}")
                driver.get(result_url)
                time.sleep(2)
            
            # 等待页面加载，确保出现"标盘明细"按钮
            print("[完场回查] 等待页面加载...")
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: "标盘明细" in d.page_source or "完场回查" in d.page_source
                )
                print("[完场回查] 页面加载完成")
            except Exception as e:
                print(f"⚠️  页面加载等待超时: {e}")
            
            # 额外等待JavaScript渲染
            time.sleep(2)
            
            # 显示当前页面信息
            print(f"[调试] 当前URL: {driver.current_url}")
            print(f"[调试] 页面标题: {driver.title}")
            
            # 🔥 设置查询日期并提交
            try:
                # 构建日期字符串（格式：YYYY-M-D，不要前导零）
                date_str = f"{target_date.year}-{target_date.month}-{target_date.day}"
                print(f"[完场回查] 设置查询日期: {date_str}")
                
                # 🔥 方法1: 直接用JavaScript修改日期变量并刷新数据
                try:
                    # 设置页面的全局日期变量
                    js_code = f"""
                    if (typeof rq !== 'undefined') {{
                        document.getElementById('rq').value = '{date_str}';
                    }}
                    // 尝试设置laydate控件的值
                    var inputs = document.querySelectorAll('input[id*="date"], input[name*="date"], input[id="rq"]');
                    inputs.forEach(function(input) {{
                        input.value = '{date_str}';
                    }});
                    """
                    driver.execute_script(js_code)
                    print(f"[完场回查] JavaScript设置日期: {date_str}")
                except Exception as e:
                    print(f"[完场回查] JavaScript设置日期失败: {e}")
                
                # 方法2: 查找日期输入框
                date_input = None
                for selector in ["#rq", "input[name='rq']", "input[name='date']", "input[name='sdate']", "input.laydate-icon"]:
                    try:
                        date_input = driver.find_element(By.CSS_SELECTOR, selector)
                        if date_input:
                            break
                    except:
                        continue
                
                if date_input:
                    # 清空并输入日期
                    date_input.clear()
                    date_input.send_keys(date_str)
                    print(f"[完场回查] 日期输入成功: {date_str}")
                    
                    # 查找并点击"查询"按钮
                    query_button = None
                    # 尝试多种选择器
                    selectors = [
                        (By.XPATH, "//button[contains(text(), '查询')]"),
                        (By.XPATH, "//input[@type='button' and @value='查询']"),
                        (By.CSS_SELECTOR, "input[value='查询']"),
                        (By.ID, "query_btn"),
                        (By.CSS_SELECTOR, "button[type='submit']"),
                    ]
                    for by, selector in selectors:
                        try:
                            query_button = driver.find_element(by, selector)
                            if query_button:
                                break
                        except:
                            continue
                    
                    if query_button:
                        query_button.click()
                        print("[完场回查] 已点击查询按钮，等待结果...")
                        time.sleep(3)  # 等待AJAX加载
                    else:
                        print("⚠️  未找到查询按钮，尝试回车提交")
                        from selenium.webdriver.common.keys import Keys
                        date_input.send_keys(Keys.RETURN)
                        time.sleep(3)
                else:
                    print("⚠️  未找到日期输入框，使用默认日期")
                    
            except Exception as e:
                print(f"⚠️  设置查询日期失败: {e}")
            
            # 页面加载成功（不保存调试快照）
            
            # 检查页面是否包含"标盘明细"按钮
            page_source = driver.page_source
            
            # 检查是否在正确的页面
            if "标盘指数" in driver.title or "index.php" in driver.current_url:
                print("❌ 错误：仍在标盘指数页面，未成功进入完场回查页面")
                print("[提示] 可能需要手动点击导航菜单'标盘指数 -> 完场回查'")
                return url_map
            
            if "标盘明细" not in page_source:
                print("⚠️  警告：页面中未找到'标盘明细'按钮")
                print(f"[调试] 页面可能是: {driver.current_url}")
                # 检查是否有完场比赛数据
                if "完场" not in page_source and "result" not in page_source.lower():
                    print("❌ 页面内容不包含完场相关信息")
                    return url_map
            
            # 使用通用的按钮点击函数捕获标盘明细链接
            url_map = capture_detail_urls_from_buttons(driver, max_buttons=max_buttons)
            print(f"✅ 从完场回查页面捕获 {len(url_map)} 个标盘明细链接")
            
            # 🔥🔥🔥 同时捕获大小球明细链接
            from .selenium_helper import capture_ou_detail_urls_from_buttons
            try:
                ou_url_map = capture_ou_detail_urls_from_buttons(driver, max_buttons=max_buttons)
                if ou_url_map:
                    print(f"✅ 从完场回查页面捕获 {len(ou_url_map)} 个大小球明细链接")
                    # 将大小球URL合并到url_map中
                    for key, ou_info in ou_url_map.items():
                        if key in url_map:
                            # 如果是字符串，转为字典
                            if isinstance(url_map[key], str):
                                url_map[key] = {'detail_url': url_map[key]}
                            url_map[key]['ou_detail_url'] = ou_info.get('url')
                            url_map[key]['ou_hdp'] = ou_info.get('hdp')
                        else:
                            url_map[key] = {
                                'ou_detail_url': ou_info.get('url'),
                                'ou_hdp': ou_info.get('hdp')
                            }
            except Exception as e:
                print(f"⚠️ 捕获大小球明细链接失败: {e}")
            
        except Exception as e:
            print(f"❌ 捕获完场比赛链接时出错: {e}")
            import traceback
            traceback.print_exc()
        
        return url_map
    
    def fetch_finished_matches_selenium(
        self,
        *,
        target_date: Optional[datetime] = None,
    ) -> List[Dict[str, Optional[str]]]:
        """
        使用 Selenium 抓取完场回查页面的比赛列表。
        
        Args:
            target_date: 目标日期，默认为昨天
            
        Returns:
            比赛列表
        """
        if target_date is None:
            target_date = (datetime.utcnow() + timedelta(hours=8)) - timedelta(days=1)
        
        driver = self._init_driver()
        
        try:
            # 注入cookies并登录
            self._inject_cookies(driver)
            
            # 访问首页
            driver.get(urljoin(LOGIN_URL, "/bifaw/index.php"))
            time.sleep(2)
            
            # 访问完场回查页面
            # 根据网站结构，完场回查的URL可能是 /bifaw/result.php 或类似
            # 让我们先访问主页，然后查找完场回查链接
            print(f"\n[完场回查Selenium] 访问完场回查页面")
            
            # 尝试找到完场回查链接或直接构造URL
            finished_url = urljoin(LOGIN_URL, "/bifaw/result.php")
            driver.get(finished_url)
            time.sleep(3)
            
            # 🔥 不再保存完场回查 HTML 快照
            html = driver.page_source
            
            # 解析页面中的比赛列表
            # 这里需要根据实际页面结构来解析
            from parser.html_parser import parse_match_list
            
            matches = parse_match_list(html, finished_url)
            print(f"[完场回查Selenium] 找到 {len(matches)} 场比赛")
            
            return matches
            
        finally:
            driver.quit()
    
    def fetch_asian_handicap(
        self,
        match_id: str,
        market_id: str,
        home_sid: str,
        away_sid: str,
        opentime: str,
    ) -> Optional[Dict]:
        """
        从必发指数网获取让球盘口数据
        
        Args:
            match_id: 比赛ID (matchid/tmid)
            market_id: 市场ID (marketid)
            home_sid: 主队ID
            away_sid: 客队ID
            opentime: 开赛时间戳
            
        Returns:
            盘口数据字典，包含让球数、赔率等信息
        """
        try:
            logger.info(f"从必发获取让球盘口: match_id={match_id}")
            
            # 必发让球API（与serveodds同样的endpoint，但参数不同）
            url = f"{BASE_HOST}/bifaw/serveodds.php"
            params = {
                "matchid": match_id,
                "marketid": market_id,
                "home_sid": home_sid,
                "away_sid": away_sid,
                "opentime": opentime,
                "oddstype": "5",  # 5=让球盘（asian handicap）
                "action": "result",  # 完场数据
                "rows": "50",
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"必发让球API返回错误: {response.status_code}")
                return None
            
            # 尝试解析JSON
            try:
                data = response.json()
            except ValueError:
                logger.warning("必发让球API返回非JSON数据")
                return None
            
            # 解析盘口数据
            # 数据格式待研究，先返回原始数据
            if data:
                logger.info(f"✅ 必发让球盘口获取成功")
                return {
                    "source": "bifaw",
                    "raw_data": data,
                    # TODO: 解析具体的让球数和赔率
                }
            else:
                logger.warning("必发让球API返回空数据")
                return None
                
        except Exception as e:
            logger.exception(f"获取必发让球盘口失败: {e}")
            return None
    
    def fetch_finished_matches(
        self, 
        *, 
        target_date: Optional[datetime] = None,
        rows: int = 9999,
        auto_retry: bool = True,
        save_page: bool = False,  # 🆕 是否保存页面
        save_dir: Optional[str] = None  # 🆕 保存目录
    ) -> Tuple[Optional[str], List[Dict[str, Optional[str]]], Dict]:
        """
        获取指定日期的已完场比赛列表（支持自动重连）
        
        Args:
            target_date: 目标日期（默认为昨天）
            rows: 每页返回的比赛数量
            auto_retry: 是否启用自动重试（默认True）
            save_page: 是否保存页面（默认False）
            save_dir: 保存目录路径
            
        Returns:
            Tuple[page_html, matches, metadata]:
            - page_html: 页面HTML或原始响应（可能为None）
            - matches: 已完场比赛列表
            - metadata: 元数据（包含日期分布、跨日期统计等）
        """
        # 🔥 如果启用自动重试，使用重连管理器
        if auto_retry:
            return self._reconnect_manager.execute_with_retry(
                self._fetch_finished_matches_impl,
                target_date=target_date,
                rows=rows,
                save_page=save_page,
                save_dir=save_dir
            )
        else:
            return self._fetch_finished_matches_impl(
                target_date=target_date, 
                rows=rows,
                save_page=save_page,
                save_dir=save_dir
            )
    
    def _fetch_finished_matches_impl(
        self,
        target_date: Optional[datetime] = None,
        rows: int = 200,
        save_page: bool = False,
        save_dir: Optional[str] = None
    ) -> Tuple[Optional[str], List[Dict[str, Optional[str]]], Dict]:
        """
        获取指定日期的已完场比赛列表（实际实现）
        
        Args:
            target_date: 目标日期（默认为昨天）
            rows: 每页返回的比赛数量
            save_page: 是否保存页面
            save_dir: 保存目录
            
        Returns:
            Tuple[page_html, matches, metadata]
        """
        if target_date is None:
            # 默认查询昨天的完场比赛
            target_date = (datetime.utcnow() + timedelta(hours=8)) - timedelta(days=1)
        
        # 检查缓存（5分钟有效期）
        date_key = target_date.strftime("%Y-%m-%d")
        if date_key in self._finished_matches_cache:
            cached_data = self._finished_matches_cache[date_key]
            cached_time = cached_data.get('time', 0)
            cache_age = time.time() - cached_time
            if cache_age < 300:  # 5分钟内
                print(f"✅ 使用缓存数据（{cache_age:.0f}秒前）: {len(cached_data.get('matches', []))} 场比赛\n")
                return cached_data.get('html'), cached_data.get('matches', []), cached_data.get('metadata', {})
            else:
                # 缓存过期，删除
                del self._finished_matches_cache[date_key]
        
        # 🔥 临时禁用Selenium捕获（加速查询，避免卡住）
        # 原因：Selenium启动浏览器+页面加载+点击按钮需要60秒，导致查询卡住
        # 解决方案：直接使用备用方案（API返回的URL），速度快且稳定
        real_url_map: Dict[str, str] = {}
        print("\n⚠️  跳过Selenium捕获（使用快速备用方案）")
        print("提示：如需启用Selenium捕获真实URL，请修改 bifaw_client.py 第3697行\n")
        
        # 以下代码已禁用（如需启用，取消注释）
        # try:
        #     print("\n" + "="*80)
        #     print("开始获取完场比赛真实明细链接（使用Selenium，优化版）...")
        #     print("="*80)
        #     
        #     # 使用线程执行Selenium，设置超时避免长时间等待
        #     import concurrent.futures
        #     
        #     def capture_urls():
        #         driver = self._init_driver()
        #         try:
        #             self._inject_cookies(driver)
        #             # 只捕获前30个，大多数用户只需要看最近的几场
        #             return self._capture_finished_match_urls(driver, target_date, max_buttons=30)
        #         finally:
        #             driver.quit()
        #     
        #     # 🔥 设置60秒超时（需要等待页面加载和点击多个按钮）
        #     with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        #         future = executor.submit(capture_urls)
        #         try:
        #             real_url_map = future.result(timeout=60)
        #             if real_url_map:
        #                 print(f"✅ 成功捕获 {len(real_url_map)} 个完场比赛真实明细链接\n")
        #         except concurrent.futures.TimeoutError:
        #             print("⚠️ Selenium捕获超时（60秒），将使用备用方案\n")
        #             real_url_map = {}
        # except Exception as e:
        #     logger.warning(f"Selenium捕获完场比赛链接失败: {e}，将使用备用方案")
        
        session = self._build_requests_session()
        
        # 🔥 构造请求参数
        # fff参数说明：
        # - "0" 或 "1": 未完场比赛（根据星期几）
        # - "4": 完场回查
        
        # 🔥 使用与标盘场次相同的格式
        payload = {
            "year": str(target_date.year),
            "month": str(target_date.month).zfill(2),  # 🔥 补零
            "day": str(target_date.day).zfill(2),      # 🔥 补零
            "page": "1",
            "rows": str(rows),
            "fff": "4",
        }
        
        headers = {
            "Referer": f"{BASE_HOST}/bifaw/",  # 🔥 修复：使用与标盘场次相同的Referer
            "Origin": BASE_HOST,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        
        print(f"\n[完场回查] 查询日期: {payload['year']}-{payload['month']}-{payload['day']}")
        print(f"[完场回查] 请求参数: {payload}")
        print(f"[完场回查] 请求URL: {SERVEODDS_URL}")
        
        # 🔥 添加重试机制（最多3次）
        max_retries = 3
        retry_delay = 2
        response = None
        
        for attempt in range(max_retries):
            try:
                response = session.post(SERVEODDS_URL, data=payload, headers=headers, timeout=20)
                response.raise_for_status()
                break  # 成功，跳出重试循环
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠️ 请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)[:100]}")
                    print(f"  ⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    print(f"  ❌ 请求失败，已达最大重试次数: {str(e)[:100]}")
                    logger.error(f"完场回查请求失败: {e}")
                    return None, [], {}  # 🆕 返回3个值
        
        if not response:
            logger.warning("无法获取完场比赛数据")
            return None, [], {}
        
        print(f"[完场回查] HTTP状态码: {response.status_code}")
        print(f"[完场回查] 响应长度: {len(response.text)} 字符")
        
        # 🔥 调试：打印完整的响应内容
        print(f"[完场回查] 完整响应内容: {response.text[:1000]}")
        
        # 🆕 保存原始响应（JSON格式）
        page_html = response.text
        
        try:
            data_text = response.text.lstrip("\ufeff")
            data = json.loads(data_text)
            print(f"[完场回查] JSON解析成功，数据类型: {type(data)}")
            
            # 🔥 检查会话失效错误（账号在其他地方登录或未登录）
            if isinstance(data, dict) and "ErrMsg" in data:
                err_msg = data["ErrMsg"]
                # 检测各种登录失效的情况
                if "别出登" in err_msg or "重新" in err_msg or "过期" in err_msg or "失效" in err_msg or "没有登" in err_msg or "登陆" in err_msg:
                    logger.warning(f"⚠️ 会话已失效: {err_msg}")
                    print(f"\n⚠️ [会话失效] {err_msg}")
                    print("🔄 尝试自动重新登录...")
                    
                    # 清空cookie缓存，触发重新登录
                    self._requests_cookie_cache = None
                    if self._local_ocr and self._local_ocr.is_enabled():
                        login_ok, login_msg = self._auto_login_with_ocr(max_retries=20)
                        if login_ok:
                            logger.info("✅ 自动重新登录成功，正在重试请求...")
                            print("✅ 登录成功，重试请求...\n")
                            # 重建会话并重试
                            session = self._build_requests_session()
                            response = session.post(SERVEODDS_URL, data=payload, headers=headers, timeout=20)
                            response.raise_for_status()
                            data_text = response.text.lstrip("\ufeff")
                            data = json.loads(data_text)
                            # 再次检查是否仍然失败
                            if isinstance(data, dict) and "ErrMsg" in data:
                                logger.error(f"❌ 重新登录后仍然失败: {data['ErrMsg']}")
                                return None, [], {}
                        else:
                            logger.error(f"❌ 自动重新登录失败: {login_msg}")
                            print(f"❌ 自动登录失败: {login_msg}")
                            print("请在采集控制台手动登录后重试")
                            return None, [], {}
                    else:
                        logger.warning("⚠️ OCR未启用，无法自动重新登录，请手动登录")
                        print("❌ OCR未启用，请在采集控制台手动登录后重试")
                        return None, [], {}
            
            # 🔥 打印解析后的数据结构
            if isinstance(data, dict):
                print(f"[完场回查] 数据字典的键: {list(data.keys())}")
            elif isinstance(data, list):
                print(f"[完场回查] 数据列表长度: {len(data)}")
        except ValueError as e:
            print(f"[完场回查] JSON解析失败: {e}")
            print(f"[完场回查] 响应内容（前500字符）: {response.text[:500]}")
            raise RuntimeError(f"serveodds 返回异常：{response.text[:200]}")
        
        # 解析响应数据
        if isinstance(data, list):
            rows_data = data
        elif isinstance(data, dict):
            if any(k.startswith("a") for k in data.keys()):
                rows_data = list(data.values())
            else:
                rows_data = (
                    data.get("rows")
                    or data.get("data")
                    or data.get("list")
                    or data.get("matchs")
                    or []
                )
        else:
            rows_data = []
        
        if isinstance(rows_data, dict):
            rows_data = (
                rows_data.get("rows")
                or rows_data.get("data")
                or rows_data.get("list")
                or list(rows_data.values())
                or []
            )
        
        if not isinstance(rows_data, list):
            print(f"[完场回查] 警告：rows_data 不是列表类型: {type(rows_data)}")
            return []
        
        print(f"[完场回查] 原始数据包含 {len(rows_data)} 条记录")
        
        # 调试：打印第一条记录的所有字段
        if rows_data and isinstance(rows_data[0], dict):
            print(f"\n[调试] 第一条记录的字段：")
            for key, value in rows_data[0].items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
            print()
        
        def _first(item: Dict[str, object], keys: List[str]) -> Optional[str]:
            for key in keys:
                if key in item and item[key]:
                    return str(item[key])
            return None
        
        collected: List[Dict[str, Optional[str]]] = []
        
        for item in rows_data:
            if not isinstance(item, dict):
                continue
            
            info_str = item.get("info")
            info_parts: List[str] = []
            if isinstance(info_str, str):
                info_parts = [part.strip() for part in info_str.split(",")]
            
            match_id = _first(item, [
                "matchid",
                "MatchID",
                "matchId",
                "mid",
            ])
            if not match_id and len(info_parts) >= 7:
                match_id = info_parts[6]
            if not match_id:
                continue
            
            league = _first(item, [
                "league",
                "League",
                "leaguecn",
                "LeagueCN",
                "league_cn",
                "LeagueName",
                "leagueName",
            ]) or (info_parts[1] if len(info_parts) > 1 else None)
            
            # 提取主队名
            home = _first(item, [
                "hometeam",
                "Home",
                "home",
                "hname",
                "HomeTeam",
                "HomeName",
            ])
            if not home and len(info_parts) > 4:
                home = info_parts[4]
            
            # 提取客队名
            away = _first(item, [
                "awayteam",
                "Away",
                "away",
                "aname",
                "AwayTeam",
                "AwayName",
            ])
            if not away and len(info_parts) > 5:
                away = info_parts[5]
            
            # 调试：打印队名提取结果（仅前3条）
            if len(collected) < 3:
                print(f"[调试] 比赛#{len(collected)+1}:")
                print(f"  info_parts长度: {len(info_parts)}")
                if len(info_parts) > 5:
                    print(f"  info_parts[4]: {info_parts[4]}")
                    print(f"  info_parts[5]: {info_parts[5]}")
                print(f"  提取的home: {home}")
                print(f"  提取的away: {away}")
            
            kickoff: Optional[str] = None
            kickoff_value = _first(item, [
                "matchtime",
                "MatchTime",
                "match_time",
                "startTime",
                "StartTime",
            ]) or (info_parts[3] if len(info_parts) > 3 else None)
            if kickoff_value:
                try:
                    kickoff_dt = datetime.fromtimestamp(int(kickoff_value), tz=timezone.utc) + timedelta(hours=8)
                    kickoff = kickoff_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    kickoff = kickoff_value
            
            # 获取比分信息 - info_parts[9]是主队进球，info_parts[10]是客队进球
            # info_parts[8]是比赛状态(6=已完场)
            score = None
            if len(info_parts) > 10:
                home_goals = info_parts[9].strip()
                away_goals = info_parts[10].strip()
                if home_goals and away_goals and home_goals.isdigit() and away_goals.isdigit():
                    score = f"{home_goals}-{away_goals}"
            
            detail_url = _first(item, [
                "detailurl",
                "DetailUrl",
                "url",
                "Url",
            ])
            
            oddstype = _first(item, ["oddstype", "OddsType", "OddsTypeID", "oddstypeid"]) or (info_parts[12] if len(info_parts) > 12 else None)
            match_type = _first(item, ["type", "Type"]) or (info_parts[11] if len(info_parts) > 11 else None)
            subtype = _first(item, ["subtype", "SubType", "subOddstype", "OddstypeSub"]) or (info_parts[13] if len(info_parts) > 13 else None)
            
            # 完场回查API返回的type和oddstype可能是"0"，需要替换为有效值
            if not match_type or match_type == "0":
                match_type = "1"
            if not oddstype or oddstype == "0":
                oddstype = "1"
            
            # 从info_parts或macth字段提取额外参数
            # info格式: [0]=status, [1]=league, [2]=color, [3]=matchtime, [4]=home, [5]=away, [6]=matchid, [7]=marketid, [8]=status, ...
            # 更详细的info字段: [19]=home_sid?, [20]=away_sid?, ...
            match_mid = None
            home_sid = None
            away_sid = None
            market_id = None
            
            # 从info_parts提取market_id (通常在索引7或19)
            if len(info_parts) > 7:
                market_id = info_parts[7].strip() if info_parts[7] else None
            
            # 从info_parts提取home_sid和away_sid（索引可能在19-20之间）
            if len(info_parts) > 19:
                home_sid = info_parts[19].strip() if info_parts[19] else None
            if len(info_parts) > 20:
                away_sid = info_parts[20].strip() if info_parts[20] else None
            
            # 从macth字段提取market_id和总成交量
            macth_data = item.get("macth") or item.get("Macth")
            total_volume = None
            
            if isinstance(macth_data, str):
                macth_parts = macth_data.split(",")
                if len(macth_parts) > 0 and macth_parts[0].strip():
                    match_mid = macth_parts[0].strip()
                    if not market_id:
                        market_id = match_mid
                
                # 🆕 提取总成交量（macth字段的第2个值，索引1）
                # 格式：mid,total_volume,odds1,vol1,vol2,...
                if len(macth_parts) > 1:
                    try:
                        total_volume = float(macth_parts[1].strip())
                    except (ValueError, AttributeError):
                        pass
            
            # 构造detail_params字典（用于_resolve_detail_url）
            detail_params = {
                "match_id": match_id,
                "mid": match_mid,
                "matchtime": kickoff_value,
                "homesid": home_sid or "",
                "awaysid": away_sid or "",
                "flag": match_type,
                "extra": subtype,
            }
            
            # URL构造策略（按优先级）：
            # 1. 尝试直接构造matchDetails.php URL（如果有足够参数）
            # 2. 使用Selenium捕获的真实URL
            # 3. 备用方案：构造sporttery.php URL
            
            detail_url = None
            
            # 方案1：尝试构造matchDetails.php URL
            if market_id:
                # 构造team_msg
                team_msg = f"{league}@{home}@{away}@{score or ''}"
                constructed_url = self._construct_finished_match_detail_url(
                    match_id=match_id,
                    market_id=market_id,
                    home_sid=home_sid,
                    away_sid=away_sid,
                    opentime=kickoff_value,
                    team_msg=team_msg
                )
                if constructed_url:
                    detail_url = constructed_url
            
            # 方案2：使用Selenium捕获的URL
            if not detail_url and match_id in real_url_map:
                url_info = real_url_map[match_id]
                # 可能是字符串（旧格式）或字典（新格式）
                if isinstance(url_info, str):
                    detail_url = url_info
                elif isinstance(url_info, dict):
                    detail_url = url_info.get('detail_url')
            
            # 方案3：构造sporttery.php URL（最后备用）
            if not detail_url:
                from urllib.parse import urlencode
                query_params: Dict[str, str] = {
                    "matchid": match_id,
                    "type": match_type,
                    "oddstype": oddstype,
                }
                if subtype:
                    query_params["subtype"] = subtype
                if match_mid:
                    query_params["mid"] = match_mid
                if kickoff_value:
                    query_params["matchtime"] = kickoff_value
                if home_sid:
                    query_params["homesid"] = home_sid
                if away_sid:
                    query_params["awaysid"] = away_sid
                
                detail_url = (
                    f"{BASE_HOST}/bifaw/sporttery.php?"
                    + urlencode({k: v for k, v in query_params.items() if v})
                )
            
            label_parts = [kickoff, league, home, score or "vs", away]
            label = " ".join(part for part in label_parts if part)
            
            # 🆕 解析实际开球日期
            kickoff_date_str = None
            kickoff_time_str = None
            is_cross_date = False
            
            if kickoff:  # kickoff格式："2025-10-25 10:00"
                try:
                    parts = kickoff.split()
                    if len(parts) >= 2:
                        kickoff_date_str = parts[0]  # "2025-10-25"
                        kickoff_time_str = parts[1]  # "10:00"
                        
                        # 判断是否跨日期
                        kickoff_dt = datetime.strptime(kickoff_date_str, '%Y-%m-%d')
                        is_cross_date = (kickoff_dt.date() != target_date.date())
                except:
                    pass
            
            if not kickoff_date_str:
                kickoff_date_str = target_date.strftime('%Y-%m-%d')
            
            # 🔥🔥🔥 从real_url_map获取大小球明细URL（用match_id作为key）
            ou_detail_url = None
            ou_hdp = None
            if match_id in real_url_map:
                url_info = real_url_map[match_id]
                if isinstance(url_info, dict):
                    ou_detail_url = url_info.get('ou_detail_url')
                    ou_hdp = url_info.get('ou_hdp')
            
            # 构建比赛数据
            match_data = {
                "match_id": match_id,
                "market_id": market_id,  # 添加market_id
                "home_sid": home_sid,     # 添加home_sid
                "away_sid": away_sid,     # 添加away_sid
                "opentime": kickoff_value,  # 添加opentime
                "league": league,
                "match_time": kickoff,  # 🔥 修复：添加match_time键
                "kickoff": kickoff,
                "kickoff_date": kickoff_date_str,  # 🆕 实际开球日期
                "kickoff_time": kickoff_time_str,  # 🆕 开球时间
                "query_date": target_date.strftime('%Y-%m-%d'),  # 🆕 查询日期
                "is_cross_date": is_cross_date,  # 🆕 是否跨日期
                "home": home,
                "away": away,
                "home_team": home,  # 🔥 修复：添加home_team键以保持一致性
                "away_team": away,  # 🔥 修复：添加away_team键以保持一致性
                "score": score,
                "label": label or (f"{home} {score or 'vs'} {away}" if home or away else match_id),
                "detail_url": detail_url,
                "ou_detail_url": ou_detail_url,  # 🔥 大小球明细URL
                "ou_hdp": ou_hdp,  # 🔥 大小球盘口值
                "type": match_type,
                "oddstype": oddstype,
                "subtype": subtype,
                "detail_params": detail_params,
                "raw": item,
            }
            
            # 🆕 添加总成交量（如果存在）
            if total_volume is not None:
                match_data["total_volume"] = total_volume
            
            collected.append(match_data)
        
        # 按开球时间倒序排序（最新的在前）
        collected.sort(key=lambda x: x.get("kickoff") or "", reverse=True)
        
        # 统计URL来源
        matchdetails_count = sum(1 for match in collected if "matchDetails.php" in match.get("detail_url", ""))
        sporttery_count = sum(1 for match in collected if "sporttery.php" in match.get("detail_url", ""))
        selenium_count = len(real_url_map)
        constructed_count = matchdetails_count - selenium_count if matchdetails_count > selenium_count else 0
        
        # 🆕 统计日期分布
        date_distribution = {}
        for match in collected:
            date = match.get('kickoff_date', target_date.strftime('%Y-%m-%d'))
            date_distribution[date] = date_distribution.get(date, 0) + 1
        
        # 🆕 统计跨日期比赛
        cross_date_count = sum(1 for m in collected if m.get('is_cross_date'))
        
        # 🆕 生成元数据
        metadata = {
            'query_date': target_date.strftime('%Y-%m-%d'),
            'date_distribution': date_distribution,
            'cross_date_count': cross_date_count,
            'total_matches': len(collected),
        }
        
        print(f"\n[完场回查] 找到 {len(collected)} 场已完场比赛")
        print(f"[URL来源] matchDetails.php: {matchdetails_count} 场（Selenium捕获: {selenium_count}, 直接构造: {constructed_count}）")
        print(f"[URL来源] sporttery.php备用方案: {sporttery_count} 场")
        
        # 🆕 显示跨日期提示
        if cross_date_count > 0:
            print(f"\n⚠️  检测到 {cross_date_count} 场跨日期比赛：")
            for date, count in sorted(date_distribution.items()):
                if date != target_date.strftime('%Y-%m-%d'):
                    print(f"   - {date}: {count}场")
        
        # 🆕 如果需要保存页面
        if save_page and save_dir:
            self._save_result_page_internal(save_dir, page_html, collected, metadata, target_date)
        
        # 保存到缓存
        self._finished_matches_cache[date_key] = {
            'html': page_html,
            'matches': collected,
            'metadata': metadata,
            'time': time.time()
        }
        print(f"✅ 已缓存结果（5分钟有效期）\n")
        
        return page_html, collected, metadata  # 🆕 返回3个值

    def _save_result_page_internal(self, save_dir: str, page_html: Optional[str], matches: List[Dict], metadata: Dict, query_date: datetime):
        """
        内部方法：保存完场回查页面
        
        Args:
            save_dir: 保存目录
            page_html: 页面HTML或原始响应
            matches: 比赛列表
            metadata: 元数据
            query_date: 查询日期
        """
        import os
        import json
        
        try:
            os.makedirs(save_dir, exist_ok=True)
            
            # 保存原始响应（JSON格式）
            if page_html:
                json_raw_path = os.path.join(save_dir, "完场回查_原始响应.json")
                with open(json_raw_path, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                print(f"✅ 已保存原始响应: {json_raw_path}")
            
            # 保存解析后的JSON
            json_data = {
                'query_date': query_date.strftime('%Y-%m-%d'),
                'crawl_time': datetime.now().isoformat(),
                'total_matches': metadata['total_matches'],
                'date_distribution': metadata['date_distribution'],
                'cross_date_count': metadata['cross_date_count'],
                'matches': matches
            }
            
            json_path = os.path.join(save_dir, "完场回查.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 完场回查数据已保存：{save_dir}")
            print(f"   - 解析数据: {json_path}")
            print(f"   - 总比赛数: {len(matches)}")
            
            if metadata['cross_date_count'] > 0:
                print(f"   ⚠️  包含 {metadata['cross_date_count']} 场次日比赛")
                for date, count in metadata['date_distribution'].items():
                    if date != query_date.strftime('%Y-%m-%d'):
                        print(f"      - {date}: {count}场")
        
        except Exception as e:
            logger.error(f"保存完场回查页面失败: {e}")
    
    def cleanup(self) -> None:
        """关闭所有遗留浏览器会话。"""
        with self._lock:
            for session in self._sessions.values():
                try:
                    session.driver.quit()
                except Exception:
                    pass
            self._sessions.clear()
    
    # ================================================================== #
    # 🔥 四合一数据采集功能
    # ================================================================== #
    
    def fetch_all_markets_detail(
        self,
        match: Dict,
        collect_handicap: bool = True,
        collect_ou: bool = True,
        collect_correct_score: bool = False,
        top_n_handicap_lines: int = 5
    ) -> Dict[str, any]:
        """
        采集比赛的所有市场数据（四合一）
        
        Args:
            match: 比赛信息字典
            collect_handicap: 是否采集让球盘数据
            collect_ou: 是否采集大小球数据
            collect_correct_score: 是否采集比分数据
            top_n_handicap_lines: 采集前N个让球盘口（按交易量排序）
            
        Returns:
            {
                'standard': {
                    'html': '标盘HTML',
                    'data': DataFrame或dict
                },
                'handicap': {
                    'main_line': '-0.5',
                    'lines': [
                        {
                            'hdp': '-0.5',
                            'volume': 1000000,
                            'is_main': True,
                            'html': 'HTML',
                            'data': DataFrame或dict
                        },
                        ... (共top_n个)
                    ]
                },
                'ou': {
                    'html': '大小球HTML',
                    'data': DataFrame或dict
                },
                'correct_score': {
                    'html': '比分HTML',
                    'data': DataFrame或dict
                }
            }
        """
        from parser.html_parser import parse_bifa_html
        
        logger.info("=" * 80)
        logger.info(f"🔥 开始四合一数据采集: {match.get('home')} vs {match.get('away')}")
        logger.info(f"   采集让球盘: {collect_handicap} (前{top_n_handicap_lines}个盘口)")
        logger.info(f"   采集大小球: {collect_ou}")
        logger.info(f"   采集比分: {collect_correct_score}")
        logger.info("=" * 80)
        
        result = {
            'standard': None,
            'handicap': None,
            'ou': None,
            'correct_score': None
        }
        
        # ========== 1. 采集标盘数据 ==========
        logger.info("\n📊 步骤1/4: 采集标盘数据...")
        try:
            detail_url = match.get('detail_url')
            if detail_url:
                standard_html = self.fetch_match_detail_selenium(
                    detail_url=detail_url,
                    match=match
                )
                
                if standard_html:
                    standard_data = parse_bifa_html(standard_html)
                    result['standard'] = {
                        'html': standard_html,
                        'data': standard_data
                    }
                    logger.info(f"✅ 标盘数据采集成功: {len(standard_data) if hasattr(standard_data, '__len__') else 'N/A'} 行")
                else:
                    logger.warning("⚠️  标盘HTML为空")
            else:
                logger.warning("⚠️  缺少标盘URL")
        except Exception as e:
            logger.error(f"❌ 标盘数据采集失败: {e}")
        
        # ========== 2. 采集让球盘数据（前N个盘口）==========
        if collect_handicap:
            logger.info(f"\n📊 步骤2/4: 采集让球盘数据（前{top_n_handicap_lines}个盘口）...")
            try:
                handicap_result = self._fetch_top_handicap_lines(
                    match=match,
                    top_n=top_n_handicap_lines
                )
                result['handicap'] = handicap_result
                
                if handicap_result and handicap_result.get('lines'):
                    logger.info(f"✅ 让球盘数据采集成功: {len(handicap_result['lines'])} 个盘口")
                    for i, line in enumerate(handicap_result['lines'], 1):
                        logger.info(f"   {i}. {line['hdp']} (交易量: {line.get('volume', 'N/A')}, 主盘口: {line.get('is_main', False)})")
                else:
                    logger.warning("⚠️  让球盘数据为空")
            except Exception as e:
                logger.error(f"❌ 让球盘数据采集失败: {e}")
        
        # ========== 3. 采集大小球数据 ==========
        if collect_ou:
            logger.info("\n📊 步骤3/4: 采集大小球数据...")
            try:
                ou_result = self._fetch_ou_detail(match=match)
                result['ou'] = ou_result
                
                if ou_result and ou_result.get('data'):
                    logger.info(f"✅ 大小球数据采集成功")
                else:
                    logger.warning("⚠️  大小球数据为空")
            except Exception as e:
                logger.error(f"❌ 大小球数据采集失败: {e}")
        
        # ========== 4. 采集比分数据 ==========
        if collect_correct_score:
            logger.info("\n📊 步骤4/4: 采集比分数据...")
            try:
                correct_result = self._fetch_correct_score_detail(match=match)
                result['correct_score'] = correct_result
                
                if correct_result and correct_result.get('data'):
                    logger.info(f"✅ 比分数据采集成功")
                else:
                    logger.warning("⚠️  比分数据为空")
            except Exception as e:
                logger.error(f"❌ 比分数据采集失败: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 四合一数据采集完成")
        logger.info("=" * 80 + "\n")
        
        return result
    
    def _fetch_top_handicap_lines(
        self,
        match: Dict,
        top_n: int = 5
    ) -> Optional[Dict]:
        """
        采集交易量前N的让球盘口数据
        
        Returns:
            {
                'main_line': '-0.5',
                'lines': [
                    {
                        'hdp': '-0.5',
                        'volume': 1000000,
                        'is_main': True,
                        'html': 'HTML',
                        'data': DataFrame或dict
                    },
                    ...
                ]
            }
        """
        from parser.html_parser import parse_bifa_html
        from parser.super_detail_parser import parse_handicap_trade_html
        
        try:
            # 从match中获取让球盘口信息（由app.py采集时已经获取）
            handicap_all_lines = match.get('handicap_all_lines', [])
            main_line_home = match.get('handicap_main_line')  # 主队视角
            
            if not handicap_all_lines:
                logger.warning("⚠️  没有让球盘口信息")
                return None
            
            logger.info(f"📊 找到 {len(handicap_all_lines)} 个让球盘口")
            
            # 按交易量排序（降序）
            sorted_lines = sorted(
                handicap_all_lines,
                key=lambda x: x.get('volume', 0) if x.get('volume') else 0,
                reverse=True
            )
            
            # 确保主盘口在前N个中
            main_line_info = None
            for line in sorted_lines:
                if line.get('is_main'):
                    main_line_info = line
                    break
            
            # 选择前N个盘口
            selected_lines = sorted_lines[:top_n]
            
            # 如果主盘口不在前N个中，替换最后一个
            if main_line_info and main_line_info not in selected_lines:
                logger.info(f"⚠️  主盘口不在前{top_n}个中，替换最后一个")
                selected_lines[-1] = main_line_info
            
            logger.info(f"📊 选择了 {len(selected_lines)} 个盘口进行采集")
            
            # 依次采集每个盘口的交易明细数据
            result_lines = []
            for i, line_info in enumerate(selected_lines, 1):
                hdp_home = line_info.get('hdp_home')
                hdp_away = line_info.get('hdp_away')
                volume = line_info.get('volume', 0)
                is_main = line_info.get('is_main', False)
                
                logger.info(f"   {i}/{len(selected_lines)}: 采集盘口 {hdp_home} (交易量: {volume}, 主盘口: {is_main})")
                
                try:
                    # 构造让球URL并采集数据
                    # 使用客队视角的hdp_away来构造URL（必发网的URL参数使用客队视角）
                    handicap_url = match.get('handicap_url_base', '') or match.get('handicap_url', '')
                    if handicap_url and hdp_away:
                        # 替换URL中的hdp参数
                        import re
                        import base64
                        from urllib.parse import parse_qs, urlparse
                        
                        # 解析URL
                        parsed_url = urlparse(handicap_url)
                        query_params = parse_qs(parsed_url.query)
                        
                        if 'getuid' in query_params:
                            # 解码getuid
                            getuid_encoded = query_params['getuid'][0]
                            try:
                                getuid_decoded = base64.b64decode(getuid_encoded).decode('utf-8')
                                
                                # 替换hdp参数
                                getuid_decoded = re.sub(r'hdp=[^&]+', f'hdp={hdp_away}', getuid_decoded)
                                
                                # 重新编码
                                getuid_new = base64.b64encode(getuid_decoded.encode('utf-8')).decode('utf-8')
                                
                                # 构造新URL
                                handicap_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?getuid={getuid_new}"
                                
                            except Exception as e:
                                logger.warning(f"      ⚠️  URL解码失败，使用简单替换: {e}")
                                # 如果解码失败，尝试简单替换
                                handicap_url = re.sub(r'hdp=[^&]+', f'hdp={hdp_away}', handicap_url)
                        else:
                            # 如果没有getuid参数，尝试简单替换
                            handicap_url = re.sub(r'hdp=[^&]+', f'hdp={hdp_away}', handicap_url)
                        
                        # 使用Selenium获取HTML
                        html = self.fetch_match_detail_selenium(
                            detail_url=handicap_url,
                            match=match
                        )
                        
                        if html:
                            # 解析HTML
                            data = parse_handicap_trade_html(html)
                            
                            result_lines.append({
                                'hdp': hdp_home,  # 使用主队视角
                                'hdp_away': hdp_away,  # 保存客队视角
                                'volume': volume,
                                'is_main': is_main,
                                'html': html,
                                'data': data
                            })
                            logger.info(f"      ✅ 采集成功")
                        else:
                            logger.warning(f"      ⚠️  HTML为空")
                    else:
                        logger.warning(f"      ⚠️  缺少URL或hdp参数")
                        
                except Exception as e:
                    logger.error(f"      ❌ 采集失败: {e}")
                    continue
            
            if not result_lines:
                logger.warning("⚠️  没有成功采集任何让球盘口数据")
                return None
            
            return {
                'main_line': main_line_home,
                'lines': result_lines
            }
            
        except Exception as e:
            logger.error(f"❌ 让球盘口采集失败: {e}")
            return None
    
    def _fetch_ou_detail(self, match: Dict) -> Optional[Dict]:
        """
        采集大小球数据
        
        Returns:
            {
                'html': 'HTML',
                'data': DataFrame或dict
            }
        """
        from parser.html_parser import parse_bifa_html
        from parser.super_detail_parser import parse_ou_trade_html
        
        try:
            ou_url = match.get('ou_url')
            if not ou_url:
                logger.warning("⚠️  缺少大小球URL")
                return None
            
            logger.info(f"📊 采集大小球数据: {ou_url}")
            
            # 使用Selenium获取HTML
            html = self.fetch_match_detail_selenium(
                detail_url=ou_url,
                match=match
            )
            
            if not html:
                logger.warning("⚠️  大小球HTML为空")
                return None
            
            # 解析HTML
            data = parse_ou_trade_html(html)
            
            return {
                'html': html,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"❌ 大小球采集失败: {e}")
            return None
    
    def _fetch_correct_score_detail(self, match: Dict) -> Optional[Dict]:
        """
        采集比分数据
        
        Returns:
            {
                'html': 'HTML',
                'data': DataFrame或dict
            }
        """
        from parser.html_parser import parse_bifa_html
        from parser.super_detail_parser import parse_correct_score_html
        
        try:
            correct_score_url = match.get('correct_score_url')
            if not correct_score_url:
                logger.warning("⚠️  缺少比分URL")
                return None
            
            logger.info(f"📊 采集比分数据: {correct_score_url}")
            
            # 使用Selenium获取HTML
            html = self.fetch_match_detail_selenium(
                detail_url=correct_score_url,
                match=match
            )
            
            if not html:
                logger.warning("⚠️  比分HTML为空")
                return None
            
            # 解析HTML
            data = parse_correct_score_html(html)
            
            return {
                'html': html,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"❌ 比分采集失败: {e}")
            return None

