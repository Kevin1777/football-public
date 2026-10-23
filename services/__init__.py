"""
服务模块导出。
"""

from .bifaw_client import BifawClient
from .trade_report import generate_trade_report
from .lottery500_client import Lottery500Client
from .super_detail_fetcher import (
    SuperDetailFetcher,
    parse_url_getuid,
    extract_handicap_from_url,
)

__all__ = [
    "BifawClient",
    "generate_trade_report",
    "Lottery500Client",
    "SuperDetailFetcher",
    "parse_url_getuid",
    "extract_handicap_from_url",
]
