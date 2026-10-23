from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Optional


def _first_existing(candidates: Iterable[str]) -> Optional[str]:
    for path_str in candidates:
        if not path_str:
            continue
        path = Path(path_str).expanduser()
        if path.exists():
            return str(path)
    return None


def resolve_chrome_binary() -> Optional[str]:
    """
    返回当前环境下可用的 Chrome/Chromium 可执行文件路径。
    优先使用环境变量 CHROME_BINARY，其次根据操作系统尝试常见路径。
    """
    env_path = os.getenv("CHROME_BINARY")
    candidates = []
    if env_path:
        candidates.append(env_path)

    if sys.platform.startswith("linux"):
        candidates.extend(
            [
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/snap/bin/chromium",
            ]
        )
    elif sys.platform == "win32":
        candidates.extend(
            [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
        )
    elif sys.platform == "darwin":
        candidates.append(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )

    return _first_existing(candidates)


def resolve_chromedriver() -> Optional[str]:
    """
    返回 chromedriver 可执行文件路径。
    优先使用环境变量 CHROMEDRIVER_PATH，其次根据操作系统尝试常见路径。
    """
    env_path = os.getenv("CHROMEDRIVER_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)

    if sys.platform.startswith("linux"):
        candidates.extend(
            [
                "/usr/lib/chromium-browser/chromedriver",
                "/usr/bin/chromedriver",
            ]
        )
    elif sys.platform == "win32":
        candidates.extend(
            [
                r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            ]
        )
    elif sys.platform == "darwin":
        candidates.extend(
            [
                "/usr/local/bin/chromedriver",
                "/opt/homebrew/bin/chromedriver",
            ]
        )

    return _first_existing(candidates)


