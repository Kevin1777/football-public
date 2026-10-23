# parser 模块

from .html_parser import parse_bifa_html, parse_match_list
from .super_detail_parser import (
    SuperDetailParser,
    parse_handicap_trade_html,
    parse_correct_score_html,
    create_super_json,
    save_super_json,
    load_super_json,
)

__all__ = [
    "parse_bifa_html",
    "parse_match_list",
    "SuperDetailParser",
    "parse_handicap_trade_html",
    "parse_correct_score_html",
    "create_super_json",
    "save_super_json",
    "load_super_json",
]
