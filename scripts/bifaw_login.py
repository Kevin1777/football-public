"""
必发指数网自动登录脚本（Selenium + 手动验证码一次）
----------------------------------------------------------
使用说明：
1. 安装依赖：
       pip install selenium pillow pytesseract
   并确保系统已安装 Chromium / Chrome 以及对应的 chromedriver。

2. 根据页面实际结构调整下方常量：
   - USERNAME_INPUT, PASSWORD_INPUT, CAPTCHA_INPUT
   - CAPTCHA_IMAGE, LOGIN_BUTTON, LOGIN_SUCCESS_MARK

3. 将账号、密码填入 ACCOUNT / PASSWORD（建议改为读取环境变量）。

4. 首次运行：
       python football/scripts/bifaw_login.py
   脚本会自动填写账号密码，提示你手动识别验证码（验证码图片默认保存到
   /root/football/captcha.png）。登录成功后脚本会保存 cookies.json，
   后续运行将优先复用 cookies，无需再输入验证码；若 cookies 过期，
   则再次按提示输入验证码刷新 cookies。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.chrome_env import resolve_chrome_binary, resolve_chromedriver

# ---------- 基础配置 ----------
LOGIN_URL = "https://www.bifaw.com/index.html"

# 文件路径
BASE_DIR = Path("/root/football")
CONFIG_FILE = BASE_DIR / "config.json"
COOKIES_PATH = BASE_DIR / "cookies.json"
REQUEST_COOKIES_PATH = BASE_DIR / "cookies_requests.json"
CAPTCHA_PATH = BASE_DIR / "captcha.png"


def _load_config() -> dict:
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


CONFIG = _load_config()
ACCOUNT = CONFIG.get("account")
PASSWORD = CONFIG.get("password")


# 页面元素定位（示例值，需根据现实页面调整）
USERNAME_INPUT = (By.ID, "txtUsername")
PASSWORD_INPUT = (By.ID, "txtPassword")
CAPTCHA_INPUT = (By.ID, "vdcode")
CAPTCHA_IMAGE = (By.ID, "vdimgck")
LOGIN_BUTTON = (By.CSS_SELECTOR, "#myform button[type='submit']")
LOGIN_SUCCESS_MARK = (By.CSS_SELECTOR, "#_userlogin a[href*='logout']")

def init_driver() -> webdriver.Chrome:
    """创建并返回 Chrome WebDriver 实例。"""
    options = Options()

    chrome_binary = resolve_chrome_binary()
    if not chrome_binary:
        raise RuntimeError(
            "未找到 Chrome/Chromium 可执行文件。请在服务器上安装浏览器，"
            "或设置环境变量 CHROME_BINARY 指向浏览器路径。"
        )
    options.binary_location = chrome_binary
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--window-size=1920,1080")

    chromedriver_path = resolve_chromedriver()
    if not chromedriver_path:
        raise RuntimeError(
            "未找到 chromedriver。请安装 chromedriver 或设置环境变量 "
            "CHROMEDRIVER_PATH 指向驱动程序。"
        )

    try:
        service = Service(chromedriver_path, log_path="/tmp/chromedriver.log")
    except TypeError:
        # 兼容旧版 selenium 对 Service 参数的位置要求
        service = Service(chromedriver_path)

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def save_captcha(driver: webdriver.Chrome) -> None:
    """截图验证码保存到指定路径。"""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    captcha_element = driver.find_element(*CAPTCHA_IMAGE)
    captcha_element.screenshot(str(CAPTCHA_PATH))
    print(f"[提示] 验证码图片已保存至：{CAPTCHA_PATH}")


def _has_login_succeeded(driver: webdriver.Chrome) -> bool:
    """根据页面状态判断是否已经登录成功。"""
    try:
        elem = driver.find_element(*LOGIN_SUCCESS_MARK)
        if elem.is_displayed():
            return True
    except Exception:
        pass

    try:
        userlogin_text = driver.find_element(By.ID, "_userlogin").text.strip()
        if userlogin_text and "登录" not in userlogin_text:
            return True
    except Exception:
        pass

    return "member" in driver.current_url.lower()


def wait_for_login_success(driver: webdriver.Chrome, timeout: int = 20) -> bool:
    """等待页面进入登录后的状态。"""
    try:
        WebDriverWait(driver, timeout).until(lambda d: _has_login_succeeded(d))
        return True
    except TimeoutException:
        return False


def driver_cookies_to_requests(driver: webdriver.Chrome) -> Dict[str, str]:
    """
    将 Selenium driver 当前持有的 cookies 转换为 requests 可直接使用的字典。
    """
    cookies = driver.get_cookies()
    return {
        cookie["name"]: cookie["value"]
        for cookie in cookies
        if cookie.get("name") and cookie.get("value") is not None
    }


def manual_login(driver: webdriver.Chrome) -> bool:
    """手动输入验证码完成一次登录，并保存 cookies。"""
    if not ACCOUNT or not PASSWORD:
        raise RuntimeError(f"请先在 {CONFIG_FILE} 中配置 account/password。")

    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 15)

    username_input = wait.until(EC.visibility_of_element_located(USERNAME_INPUT))
    password_input = wait.until(EC.visibility_of_element_located(PASSWORD_INPUT))
    captcha_input = wait.until(EC.visibility_of_element_located(CAPTCHA_INPUT))

    username_input.clear()
    username_input.send_keys(ACCOUNT)
    password_input.clear()
    password_input.send_keys(PASSWORD)

    for attempt in range(1, 8):
        captcha_input.clear()
        save_captcha(driver)
        captcha_text = input(f"[尝试 {attempt}] 请输入验证码：").strip()
        if not captcha_text:
            print("输入为空，已刷新验证码。")
            driver.find_element(*CAPTCHA_IMAGE).click()
            continue

        captcha_input.send_keys(captcha_text)
        driver.find_element(*LOGIN_BUTTON).click()

        try:
            if not wait_for_login_success(driver, timeout=20):
                raise TimeoutException("登录成功标记未出现")
            print("登录成功，正在保存 cookies……")
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            with open(COOKIES_PATH, "w", encoding="utf-8") as fh:
                json.dump(driver.get_cookies(), fh, ensure_ascii=False, indent=2)
            try:
                request_cookies = driver_cookies_to_requests(driver)
                with open(REQUEST_COOKIES_PATH, "w", encoding="utf-8") as fh:
                    json.dump(request_cookies, fh, ensure_ascii=False, indent=2)
                print(f"requests cookies 已保存到：{REQUEST_COOKIES_PATH}")
            except Exception as exc:
                print(f"转换 requests cookies 失败：{exc}")
            print(f"cookies 已保存到：{COOKIES_PATH}")
            return True
        except TimeoutException:
            print("登录失败（验证码可能错误），自动刷新后重试。")
            driver.find_element(*CAPTCHA_IMAGE).click()

    print("多次尝试仍未登录成功，请检查账号或验证方式。")
    return False


def load_cookies(driver: webdriver.Chrome) -> bool:
    """加载本地 cookies 尝试直接进入登录状态。"""
    if not COOKIES_PATH.exists():
        return False

    driver.get(LOGIN_URL)
    with open(COOKIES_PATH, "r", encoding="utf-8") as fh:
        cookies = json.load(fh)

    for cookie in cookies:
        # selenium 4 对 sameSite 有兼容问题，删除避免报错
        cookie.pop("sameSite", None)
        driver.add_cookie(cookie)

    driver.refresh()
    if wait_for_login_success(driver, timeout=15):
        print("已通过 cookies 复用登录状态。")
        return True
    else:
        print("本地 cookies 已失效，需要重新手动登录。")
        return False


def login() -> webdriver.Chrome:
    """登录入口：优先复用 cookies，失败时执行人工验证。"""
    driver = init_driver()

    if load_cookies(driver):
        return driver

    if manual_login(driver):
        return driver

    driver.quit()
    raise RuntimeError("登录流程未完成。")


if __name__ == "__main__":
    try:
        driver = login()
        print("可在此处继续编写抓取逻辑，例如访问交易明细页面。")
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(f"出现错误：{exc!r}")
        sys.exit(1)

