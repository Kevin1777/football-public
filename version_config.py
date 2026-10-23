#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本配置管理 - 统一管理所有版本号

使用说明：
1. 所有模块通过 from version_config import MODEL_VERSION 导入版本号
2. 更新版本时只需修改此文件的 MODEL_VERSION
3. 避免在代码中硬编码版本号
"""

# ============================================================================
# 核心模型版本配置
# ============================================================================

# 当前模型版本（修改这里会自动更新所有引用）
MODEL_VERSION = "V7.2"  # 融合盘口特征模型 - 盘口+热度双信号
MODEL_FULL_NAME = f"X1-JSON-{MODEL_VERSION}"

# 版本历史记录
VERSION_HISTORY = {
    "V1.0": {
        "name": "X1-JSON-V1.0",
        "description": "原始复杂模型（FLM+SPM+DPI+SBRE）",
        "release_date": "2025-11",
        "features": [
            "FLM热度前线评分",
            "SPM承压分析",
            "DPI风险整合",
            "SBRE反解机制",
            "动态置信度阈值"
        ],
        "performance": {
            "win_rate": "58-66%",
            "recommend_rate": "1.8-4.7%",
            "note": "胜率高但推荐率低"
        }
    },
    "V2.0": {
        "name": "X1-JSON-V2.0",
        "description": "数据驱动简化模型（基于820场历史数据）",
        "release_date": "2025-11-26",
        "features": [
            "简化规则：成交占比差≥30%",
            "必发指数差≥0",
            "最小成交量≥50,000",
            "基础置信度0.70 + 动态加成"
        ],
        "performance": {
            "win_rate": "69.5%",
            "recommend_rate": "39.0%",
            "total_matches": "959场",
            "recommended": "374场",
            "wins": "260场",
            "losses": "114场",
            "note": "胜率和推荐率均衡"
        },
        "validation": {
            "no_data_leakage": True,
            "no_future_function": True,
            "use_pre_match_data": True,
            "overfitting_risk": "Low (simple rules)"
        }
    },
    "V3.2": {
        "name": "X1-JSON-V3.2",
        "description": "加权评分优化模型（基于2025年11月深度回测分析）",
        "release_date": "2025-12-01",
        "features": [
            "Away方向惩罚（准确率65.3%低于Home的76.6%）",
            "必发指数绝对值检查（>=28%）",
            "趋势一致性检查（推荐方向趋势>=0）",
            "热度上限检查（<=20）",
            "分数差距提高到10分",
            "Away Gold阈值提高到70分"
        ],
        "performance": {
            "baseline_win_rate": "72.8%",
            "home_win_rate": "76.6%",
            "away_win_rate": "65.3%",
            "total_matches": "369场",
            "correct": "203场",
            "wrong": "76场",
            "draw": "90场",
            "note": "优化Away方向准确率"
        },
        "optimization": {
            "away_penalty": "-5分",
            "bf_low_penalty": "-10分 (BF<25)",
            "trend_penalty": "增强下降惩罚",
            "hot_penalty": "增强热度惩罚",
            "away_gold_threshold": "70分 (vs Home 65分)"
        }
    },
    "V3.5": {
        "name": "X1-JSON-V3.5",
        "description": "Silver统一策略模型（取消Gold级别，统一使用Silver/Silver+）",
        "release_date": "2025-12-01",
        "features": [
            "取消Gold级别（Gold准确率持续低于Silver）",
            "统一使用Silver和Silver+两个级别",
            "Silver+: 高分段(Home>=65, Away>=68)且热度正常",
            "联赛分级过滤（一级联赛8分差距，其他12分）",
            "Away方向惩罚-5分",
            "必发指数最低要求26%",
            "趋势一致性检查"
        ],
        "performance": {
            "total_matches": "2219场",
            "recommended": "396场",
            "correct": "221场",
            "wrong": "88场",
            "draw": "87场",
            "overall_win_rate": "71.5%",
            "silver_win_rate": "73.9%",
            "home_win_rate": "72.4%",
            "away_win_rate": "68.2%",
            "recommend_rate": "17.8%",
            "note": "推荐数量增加，准确率稳定"
        },
        "optimization": {
            "strategy": "取消Gold，统一Silver",
            "silver_plus_threshold_home": "65分",
            "silver_plus_threshold_away": "68分",
            "league_tier_filter": "一级联赛8分差距，其他12分"
        }
    },
    "V4.0": {
        "name": "X1-JSON-V4.0",
        "description": "亚盘优化模型 - 只推荐客队（基于让球盘口准确率优化）",
        "release_date": "2025-12-01",
        "features": [
            "完全禁止主队推荐（主队亚盘准确率<50%）",
            "只推荐客队方向",
            "客队受让时阈值降低（52分即可）",
            "客队让球时阈值提高（60分）",
            "保持趋势一致性检查",
            "保持必发指数最低要求"
        ],
        "performance": {
            "total_matches": "2255场",
            "recommended": "21场",
            "win": "13场",
            "half_win": "1场",
            "push": "2场",
            "lose": "5场",
            "handicap_win_rate_strict": "73.7%",
            "handicap_win_rate_with_push": "76.2%",
            "away_only": True,
            "note": "专注客队推荐，亚盘准确率大幅提升"
        },
        "optimization": {
            "strategy": "只推荐客队",
            "home_threshold": "100（禁止）",
            "away_threshold_receiving": "52分",
            "away_threshold_giving": "60分",
            "key_insight": "主队让球准确率<50%，客队受让准确率>73%"
        }
    },
    "V4.5": {
        "name": "X1-JSON-V4.5",
        "description": "亚盘优化模型 - 主队额外过滤条件（恢复主队推荐但严格过滤）",
        "release_date": "2025-12-01",
        "features": [
            "主队让球: 73分 + 盈亏>0 + 热度<12",
            "主队平手: 67分",
            "主队受让: 65分 + 防诱盘检查(盈亏>-10)",
            "客队让球: 55分",
            "客队受让: 48分",
            "深盘额外要求: 盘口>=1.5时主队+15分，客队+10分"
        ],
        "performance": {
            "total_matches": "2310场",
            "recommended": "30场",
            "win": "16场",
            "half_win": "3场",
            "push": "2场",
            "half_lose": "0场",
            "lose": "9场",
            "handicap_win_rate_strict": "67.9%",
            "handicap_win_rate_with_push": "70.0%",
            "home_win_rate": "60.0%",
            "away_win_rate": "69.6%",
            "note": "主队准确率从44%提升到60%，整体准确率从62.5%提升到67.9%"
        },
        "optimization": {
            "strategy": "恢复主队推荐但严格过滤",
            "home_giving_threshold": "73分 + 盈亏>0 + 热度<12",
            "home_even_threshold": "67分",
            "home_receiving_threshold": "65分 + 盈亏>-10",
            "away_giving_threshold": "55分",
            "away_receiving_threshold": "48分",
            "key_insight": "通过盈亏和热度检查大幅提升主队准确率"
        }
    },
    "V4.8": {
        "name": "X1-JSON-V4.8",
        "description": "亚盘优化模型 - 高准确率版本（禁止深盘，严格过滤）",
        "release_date": "2025-12-01",
        "features": [
            "禁止深盘推荐（>=1.5）",
            "主队让球: 75分",
            "主队平手: 68分",
            "主队受让: 80分（几乎禁止）",
            "客队平手: 55分",
            "客队让球: 62分",
            "客队受让: 55分",
            "较深盘(1.0-1.5): 主队+10分，客队+5分",
            "必发指数最低要求: 20",
            "分数差距: 一级联赛5分，其他8分"
        ],
        "performance": {
            "total_matches": "2428场",
            "recommended": "18场",
            "win": "11场",
            "half_win": "3场",
            "push": "0场",
            "half_lose": "0场",
            "lose": "4场",
            "handicap_win_rate_strict": "77.8%",
            "handicap_win_rate_with_push": "77.8%",
            "home_win_rate": "66.7%",
            "away_win_rate": "80.0%",
            "recommend_rate": "1.6%",
            "note": "准确率大幅提升到77.8%，客队准确率80%"
        },
        "optimization": {
            "strategy": "禁止深盘，严格过滤低分段",
            "deep_handicap_filter": ">=1.5禁止",
            "home_giving_threshold": "75分",
            "home_even_threshold": "68分",
            "home_receiving_threshold": "80分（几乎禁止）",
            "away_even_threshold": "55分",
            "away_giving_threshold": "62分",
            "away_receiving_threshold": "55分",
            "key_insight": "深盘和低分段是主要输盘来源，严格过滤后准确率大幅提升"
        }
    },
    "V7.0": {
        "name": "X1-JSON-V7.0",
        "description": "数据驱动模型 - 基于5759场深度挖掘",
        "release_date": "2025-12-10",
        "features": [
            "极热反转+高成交量 = 最强信号 (69.6%胜率)",
            "hot<-15 + vol>600K = 69.6% (ELITE)",
            "hot<-10 + vol>500K = 66.4% (STRONG)",
            "客队ELITE = 68.5%, ROI +30.2%",
            "成交量过滤: <50K不推荐",
            "三级评级: Elite/Strong/Standard"
        ],
        "performance": {
            "total_matches": "5759场",
            "elite_home_win_rate": "66.4%",
            "elite_away_win_rate": "68.5%",
            "elite_home_roi": "+26.1%",
            "elite_away_roi": "+30.2%",
            "note": "基于全量历史数据挖掘，ELITE信号ROI显著为正"
        },
        "optimization": {
            "strategy": "数据驱动，热度反转+成交量组合",
            "elite_threshold": "55分+ELITE信号",
            "strong_threshold": "45分+STRONG信号",
            "key_discovery": [
                "hot<-15 + vol>600K = 69.6%",
                "hot<-12 + vol>600K = 68.8%",
                "hot<-10 + vol>500K = 66.4%",
                "客队hot>10 + vol>500K = 68.5%"
            ]
        }
    },
    "V7.2": {
        "name": "X1-JSON-V7.2",
        "description": "逆盘策略模型 - 欧赔/让球智能切换",
        "release_date": "2025-12-10",
        "features": [
            "100%逆盘推荐（热度反转->推受让方）",
            "浅盘(≤0.5): 推欧赔 (和局退本安全)",
            "中盘(0.5-1.5): 推让球 (ROI 68%-94%)",
            "深盘(>1.5): 推欧赔 (冷门赔率高)"
        ]
    },
    "V7.3": {
        "name": "X1-JSON-V7.3",
        "description": "深度特征挖掘模型 - 1222场全量分析",
        "release_date": "2025-12-11",
        "features": [
            "必发低(<40) = +30分 (ROI+80%)",
            "超高量(>500K) = +15分 (ROI+73%)",
            "深盘+极冷门 = +40分 (ROI+180%)",
            "球半盘+极冷门 = +30分 (ROI+91%)"
        ],
        "performance": {
            "total_matches": "1222场有效推荐",
            "top_features": {
                "Elite+深盘+极冷门": "93.9%胜率, ROI+190%",
                "高赔(>=3.0)": "77.2%胜率, ROI+168%",
                "球半盘+超高量": "95.0%胜率, ROI+111%",
                "必发低(<40)": "80.6%胜率, ROI+80%"
            },
            "comparison": {
                "8月2日欧赔ROI": "V7.2:+15% -> V7.3:+25%",
                "8月17日欧赔ROI": "V7.2:+40% -> V7.3:+46%"
            }
        },
        "optimization": {
            "strategy": "深度特征交叉分析，识别高ROI组合",
            "key_discovery": [
                "深盘+极冷门=最强组合(ROI+180%)",
                "必发低是黄金信号(ROI+80%)",
                "超高量提升可靠性(ROI+73%)"
            ]
        }
    }
}

# ============================================================================
# 版本相关常量
# ============================================================================

# 引擎名称
ENGINE_NAME = "x1_json_v7.8"

# API版本
API_VERSION = "1.0"

# 数据源标识
DATA_SOURCES = {
    "ug_pdf": "✅ JSON数据",
    "handicap": "✅ 500彩票网",
    "vim": "✖ V2简化模式"
}

# ============================================================================
# 辅助函数
# ============================================================================

def get_version_info() -> dict:
    """获取当前版本的详细信息"""
    return VERSION_HISTORY.get(MODEL_VERSION, {})

def get_version_string() -> str:
    """获取完整版本字符串"""
    return MODEL_FULL_NAME

def get_all_versions() -> list:
    """获取所有可用版本列表"""
    return list(VERSION_HISTORY.keys())

def compare_versions(v1: str, v2: str) -> int:
    """
    比较版本号
    Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
    """
    v1_num = float(v1.replace('V', ''))
    v2_num = float(v2.replace('V', ''))
    
    if v1_num > v2_num:
        return 1
    elif v1_num < v2_num:
        return -1
    else:
        return 0

def print_version_info():
    """打印当前版本信息（用于调试）"""
    info = get_version_info()
    print("=" * 80)
    print(f"🎯 当前模型版本: {MODEL_FULL_NAME}")
    print("=" * 80)
    print(f"描述: {info.get('description', 'N/A')}")
    print(f"发布日期: {info.get('release_date', 'N/A')}")
    print(f"\n核心特性:")
    for feature in info.get('features', []):
        print(f"  - {feature}")
    
    perf = info.get('performance', {})
    print(f"\n性能指标:")
    print(f"  胜率: {perf.get('win_rate', 'N/A')}")
    print(f"  推荐率: {perf.get('recommend_rate', 'N/A')}")
    if 'total_matches' in perf:
        print(f"  总场次: {perf.get('total_matches', 'N/A')}")
        print(f"  推荐场次: {perf.get('recommended', 'N/A')}")
    print("=" * 80)

# ============================================================================
# 模块测试
# ============================================================================

if __name__ == "__main__":
    print_version_info()
    
    print(f"\n可用版本: {get_all_versions()}")
    print(f"版本字符串: {get_version_string()}")
    print(f"引擎名称: {ENGINE_NAME}")
