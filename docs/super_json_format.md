# 超级JSON格式说明

## 概述

超级JSON是一种整合了比赛所有交易明细数据的统一格式，包含：

1. **标盘明细** - 胜平负交易数据 (matchDetails.php)
2. **大小球明细** - 大小球交易数据 (ouDetails.php)
3. **让球指数明细** - 亚盘交易数据 (AisaDetails.php)
4. **比分明细** - 波胆交易数据 (CorrectDetails.php)
5. **盘口数据** - 各公司盘口变化
6. **所有让球盘口** - 所有可用的让球盘口列表（v2.1新增）
7. **所有大小球盘口** - 所有可用的大小球盘口列表（v2.1新增）

## 数据结构

```json
{
  "_数据摘要": {
    "_说明": "四合一交易明细数据摘要（最新成交数据）",
    "标盘_胜负平": {
      "记录数": 100,
      "总成交量": "612,947",
      "主胜成交量": "65,000",
      "和局成交量": "120,000",
      "客胜成交量": "427,947"
    },
    "大小球": {
      "记录数": 50,
      "主盘口": 2.5,
      "总成交量": "594,992",
      "所有盘口数": 3
    },
    "让球_亚盘": {
      "记录数": 80,
      "主盘口": "-0.75",
      "总成交量": "555,794",
      "所有盘口数": 4
    },
    "比分_波胆": {
      "记录数": 30,
      "总成交量": "xxx"
    },
    "数据完整度": "4/4"
  },
  
  "version": "2.1",
  "format": "super_detail",
  "created_at": "2025-01-08T12:00:00",
  
  "match_info": {
    "match_id": "35105507",
    "market_id": "252247102",
    "league": "英超",
    "kickoff": "2026-01-08 04:15",
    "home": "伯恩利",
    "away": "曼彻斯特联",
    "score": "2-2",
    "half_score": "1-0",
    "home_sid": "56299",
    "away_sid": "48351",
    "opentime": "1767816900",
    "handicap": -0.75,
    "handicap_str": "半球/一球"
  },
  
  "standard_trade": {
    "columns": ["成交时间", "总成交量", "主胜_欧赔", ...],
    "data": [
      {
        "成交时间": "01-08 04:14:26",
        "总成交量": "612,947",
        "主胜_欧赔": "4.30",
        "主胜_价位": "4.36",
        "主胜_已成交量": "65,000",
        ...
      }
    ],
    "total_records": 100
  },
  
  "ou_trade": {
    "ou_line": 2.5,
    "trade_records": [
      {
        "time": "01-08 04:14:31",
        "total_volume": "594,992",
        "over_sb": "1.03",
        "over_price": "2.01",
        "over_volume": "27.5",
        "under_sb": "0.85",
        "under_price": "2.01",
        "under_volume": "3.4",
        ...
      }
    ],
    "summary": {
      "total_records": 50,
      "final_volume": 594992
    }
  },
  
  "handicap_trade": {
    "handicap_line": -0.75,
    "handicap_str": "半球/一球",
    "trade_records": [
      {
        "time": "01-08 04:14:31",
        "total_volume": "555,794",
        "home_odds": "2.02",
        "home_volume": "160,817",
        "home_current": "264",
        "home_method": "买",
        "away_odds": "2.01",
        "away_volume": "29.5",
        "away_current": "1.4",
        "away_method": "",
        ...
      }
    ],
    "summary": {
      "total_records": 80,
      "final_volume": 555794
    }
  },
  
  "correct_score_trade": {
    "score_lines": ["1-0", "2-0", "2-1", "0-0", "1-1", "2-2", ...],
    "trade_records": [
      {
        "time": "01-08 04:14:31",
        "total_volume": "xxx",
        "raw_data": [...]
      }
    ],
    "summary": {
      "total_records": 30
    }
  },
  
  "handicap_data": {
    "current_handicap": -0.75,
    "current_handicap_str": "半球/一球",
    "all_companies": [
      {
        "company": "澳门",
        "curr_handicap": "半球/一球",
        "curr_handicap_value": 0.75,
        "curr_home_odds": 0.92,
        "curr_away_odds": 0.96,
        "init_handicap": "一球",
        "init_handicap_value": 1.0,
        "init_home_odds": 0.88,
        "init_away_odds": 1.00,
        "handicap_change": -0.25,
        "change_time": "01-08 03:30"
      },
      ...
    ],
    "aomen": {...},
    "huangguan": {...},
    "bet365": {...}
  },
  
  "all_handicap_lines": {
    "main_line": "-0.75",
    "total_count": 4,
    "lines": [
      {
        "hdp_home": "-0.75",
        "hdp_away": "0.75",
        "sb": "0.92",
        "volume": 555794,
        "is_main": true
      },
      {
        "hdp_home": "-0.5",
        "hdp_away": "0.5",
        "sb": null,
        "volume": 120000,
        "is_main": false
      },
      {
        "hdp_home": "-1",
        "hdp_away": "1",
        "sb": null,
        "volume": 80000,
        "is_main": false
      }
    ]
  },
  
  "all_ou_lines": {
    "main_line": "2.5",
    "total_count": 3,
    "lines": [
      {
        "line": "2.5",
        "sb": "1.03",
        "volume": 594992,
        "is_main": true
      },
      {
        "line": "2.25",
        "sb": null,
        "volume": 150000,
        "is_main": false
      },
      {
        "line": "2.75",
        "sb": null,
        "volume": 100000,
        "is_main": false
      }
    ]
  },
  
  "summary": {
    "has_standard_trade": true,
    "has_ou_trade": true,
    "has_handicap_trade": true,
    "has_correct_score_trade": true,
    "has_handicap_companies": true,
    "has_all_handicap_lines": true,
    "has_all_ou_lines": true,
    "standard_count": 100,
    "ou_count": 50,
    "handicap_count": 80,
    "correct_score_count": 30,
    "handicap_lines_count": 4,
    "ou_lines_count": 3,
    "completeness_score": 1.0,
    "completeness_level": "完整"
  }
}
```

## URL构造规则

### 让球指数明细 (AisaDetails.php)

```
https://bifaw.com/bifaw/AisaDetails.php?getuid={base64编码}
```

getuid解码后格式：
```
tmiid={比赛ID}&marketid={市场ID}&home_sid={主队SID}&away_sid={客队SID}&opentime={开赛时间戳}&hdp={让球数}&fff={标识}&teammsg={比赛信息}
```

示例：
- `hdp=-0.75` 表示主队让0.75球
- `fff=4` 表示完场回查
- `fff=0` 表示实时比赛

### 比分明细 (CorrectDetails.php)

```
https://bifaw.com/bifaw/CorrectDetails.php?getuid={base64编码}
```

getuid解码后格式：
```
tmiid={比赛ID}&marketid={市场ID}&opentime={开赛时间戳}&fff={标识}&teammsg={比赛信息含比分}
```

teammsg格式：`联赛@主队@客队@全:2-2半:1-0`

## 使用示例

### Python采集

```python
from services.bifaw_client import BifawClient
from services.super_detail_fetcher import SuperDetailFetcher
from parser.super_detail_parser import create_super_json, save_super_json

# 初始化
client = BifawClient()
fetcher = SuperDetailFetcher(cookies=client.get_requests_cookies())

# 获取比赛信息
match_info = {...}

# 构造让球指数URL
hdp_url = fetcher.construct_handicap_url(
    match_id=match_info['match_id'],
    market_id=match_info['market_id'],
    home_sid=match_info['home_sid'],
    away_sid=match_info['away_sid'],
    opentime=match_info['opentime'],
    team_msg=f"{match_info['league']}@{match_info['home']}@{match_info['away']}@{match_info['score']}",
    hdp=str(match_info['handicap']),
    fff="4"
)

# 获取HTML
html = fetcher.fetch_handicap_detail(hdp_url)

# 解析数据
from parser.super_detail_parser import parse_handicap_trade_html
handicap_data = parse_handicap_trade_html(html)

# 创建超级JSON
super_json = create_super_json(
    match_info=match_info,
    handicap_data=handicap_data,
    ...
)

# 保存
save_super_json(super_json, "output/match_super.json")
```

## 完整度评级

| 等级 | 分数 | 说明 |
|------|------|------|
| 无数据 | 0% | 没有任何明细数据 |
| 基础 | 25% | 只有1种明细数据 |
| 中等 | 50% | 有2种明细数据 |
| 良好 | 75% | 有3种明细数据 |
| 完整 | 100% | 有全部4种明细数据 |

## 注意事项

1. **登录要求**：所有明细页面都需要登录后才能访问
2. **请求频率**：建议每次请求间隔0.5-1秒，避免被封IP
3. **数据时效**：实时比赛数据会持续更新，完场比赛数据固定
4. **编码问题**：teammsg参数需要URL编码
5. **盘口变化**：让球数可能在比赛期间变化，需要记录采集时的盘口
