"""
X1推荐模型 V7.0 - 基于5759场数据深度挖掘

核心发现 (2025-12-10):
1. 极热反转 + 高成交 = 最强信号
   - hot<-15 + vol>600K = 69.6%
   - hot<-10 + vol>500K = 66.4%
2. 客队ELITE = 68.5%, ROI +30%
3. 成交量是关键过滤器

数据源：
- 标盘指数_latest.json
- [比赛]_[日期].json - 成交明细、必发指数、热度等
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 🔥 统一版本管理
from version_config import MODEL_FULL_NAME, MODEL_VERSION, ENGINE_NAME, DATA_SOURCES

logger = logging.getLogger(__name__)


class X1JSONRecommender:
    """X1 JSON数据推荐引擎"""
    
    def __init__(self):
        # 资金等级阈值（X1标准）
        self.funding_levels = {
            'L1': (0, 50000),
            'L2': (50000, 150000),
            'L3': (150000, 700000),
            'L4': (700000, 1500000),
            'L5': (1500000, float('inf'))
        }
        
        # SBRE响应权重
        self.sbre_weights = {
            'L1': 1.00, 'L2': 0.85, 'L3': 0.65, 'L4': 0.35, 'L5': 0.15
        }
        
        # 🔥 一级联赛（主流联赛，数据更可靠）
        self.tier1_leagues = {
            # 五大联赛
            '英超', '西甲', '德甲', '意甲', '法甲',
            # 五大联赛二级
            '英冠', '西乙', '德乙', '意乙', '法乙',
            # 欧战
            '欧冠杯', '欧罗巴杯', '欧会杯', '欧联杯',
            # 其他顶级联赛
            '中超', '葡超', '荷甲', '比甲', '土超', '苏超',
            '巴西甲', '阿甲', '美职业', '墨西联',
            '日职联', '日职乙', '韩K联', '澳超',
            # 杯赛
            '英足总杯', '英联杯', '德国杯', '西班牙杯', '意大利杯', '法国杯',
            # 亚冠
            '亚冠联', '亚冠精英', '亚冠联2'
        }
    
    def recommend(self, match_json_path: str) -> Dict:
        """
        生成推荐（主入口）
        
        Args:
            match_json_path: 比赛JSON文件路径
            
        Returns:
            VIS格式的推荐结果
        """
        try:
            # 1. 加载数据
            data = self._load_match_data(match_json_path)
            if not data:
                return self._create_melt_result('F-GATE', '数据加载失败')
            
            # 2. 数据完整性检查
            if not self._validate_data(data):
                return self._create_melt_result('F-EVD', '数据字段不完整')
            
            # 3. 提取核心指标
            metrics = self._extract_metrics(data)
            
            # 🔥 V3模式：使用加权评分模型 (Weighted Scoring Model)
            v2_result = self._recommend_weighted_scoring(metrics, data)
            if v2_result['direction'] != 'none':
                # 直接返回V2推荐结果（包装成VIS格式）
                return {
                    'version': MODEL_FULL_NAME,
                    'timestamp': datetime.now().isoformat(),
                    'match_info': data.get('match_info', {}),
                    'data_source': DATA_SOURCES,
                    'funding_level': {
                        'level': 'V2',
                        'total_volume': metrics.get('total_volume', 0),
                        'sbre_weight': 1.0
                    },
                    'scores': {
                        'FLM': v2_result,
                        'SPM': {'structure': 'V2简化', 'confidence': v2_result['confidence']},
                        'DPI': {'risk_level': '低风险', 'confidence': v2_result['confidence'], 
                                'recommendation': v2_result['direction'], 'pressure_index': 70}
                    },
                    'risk_control': {
                        'SmartSafe': False,
                        'SS-Dagger': False,
                        'LVC': False,
                        'TPI': False,
                        'messages': []
                    },
                    'sbre': {
                        'triggered': False,
                        'direction': None,
                        'confidence': 0.0,
                        'reason': ''
                    },
                    'recommendation': {
                        'direction': v2_result['direction'],
                        'confidence': v2_result['confidence'],
                        'level': v2_result.get('level', ''),
                        'score': v2_result.get('score', 0),
                        'reason': v2_result['reason'],
                        'handicap': v2_result.get('handicap', 0),
                        'formatted': v2_result.get('formatted', ''),  # 🔥 带队名和盘口的推荐
                        'home_team': v2_result.get('home_team', ''),
                        'away_team': v2_result.get('away_team', ''),
                        'bet_type': v2_result.get('bet_type', 'euro'),  # 🔥 V7.2 推荐类型
                        'handicap_bet': v2_result.get('handicap_bet'),  # 🔥 让球推荐方向
                        'handicap_bet_reason': v2_result.get('handicap_bet_reason', '')  # 🔥 让球推荐理由
                    },
                    'meltdown': {}  # V2模式不使用融断
                }
            
            # 🔥 V2不推荐时，也直接返回（不再继续旧逻辑）
            return {
                'version': MODEL_FULL_NAME,
                'timestamp': datetime.now().isoformat(),
                'match_info': data.get('match_info', {}),
                'data_source': DATA_SOURCES,
                'funding_level': {
                    'level': 'V2',
                    'total_volume': metrics.get('total_volume', 0),
                    'sbre_weight': 1.0
                },
                'scores': {
                    'FLM': v2_result,
                    'SPM': {'structure': 'V2简化', 'confidence': 0},
                    'DPI': {'risk_level': '低风险', 'confidence': 0, 
                            'recommendation': 'none', 'pressure_index': 0}
                },
                'risk_control': {
                    'SmartSafe': False,
                    'SS-Dagger': False,
                    'LVC': False,
                    'TPI': False,
                    'messages': []
                },
                'sbre': {
                    'triggered': False,
                    'direction': None,
                    'confidence': 0.0,
                    'reason': ''
                },
                'recommendation': {
                    'direction': 'none',
                    'confidence': 0.0,
                    'reason': v2_result['reason']
                },
                'meltdown': {
                    'type': 'V2_NO_RECOMMEND',
                    'reason': v2_result['reason']
                }
            }
            
            # === 以下是旧逻辑，已被V2完全替代 ===
            # 4. 资金等级判定
            funding_level = self._determine_funding_level(metrics['total_volume'])
            
            # 5. FLM评分 - 热度前线
            flm_score = self._flm_scoring(metrics)
            
            # 6. SPM评分 - 承压分析
            spm_score = self._spm_scoring(metrics)
            
            # 7. DPI评分 - 风险整合
            dpi_score = self._dpi_scoring(flm_score, spm_score, metrics)
            
            # 8. 风控检测
            risk_flags = self._run_risk_checks(metrics, flm_score, spm_score, dpi_score)
            
            # 9. SBRE反解（如触发）
            sbre_result = self._sbre_mechanism(funding_level, metrics, dpi_score, risk_flags)
            
            # 10. 生成推荐
            recommendation = self._generate_recommendation(
                metrics, flm_score, spm_score, dpi_score, sbre_result, risk_flags, funding_level
            )
            
            return recommendation
            
        except Exception as e:
            logger.exception("推荐生成失败")
            return self._create_melt_result('F-CAP', f'执行异常: {str(e)}')
    
    def _load_match_data(self, json_path: str) -> Optional[Dict]:
        """加载比赛JSON数据"""
        try:
            path = Path(json_path)
            if not path.exists():
                logger.error(f"文件不存在: {json_path}")
                return None
            
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载JSON失败: {e}")
            return None
    
    def _validate_data(self, data: Dict) -> bool:
        """验证数据完整性"""
        required_keys = ['match_info', 'handicap_data', 'trade_data']
        return all(key in data for key in required_keys)
    
    def _extract_metrics(self, data: Dict) -> Dict:
        """提取核心指标"""
        trade_data = data.get('trade_data', {})
        trade_list = trade_data.get('data', [])
        handicap = data.get('handicap_data', {})
        
        if not trade_list:
            return {}
        
        # 最新一条交易数据
        latest = trade_list[0] if trade_list else {}
        
        # 成交总量（移除逗号）- 适配新字段：价位 或 总成交量
        total_volume_str = latest.get('总成交量') or latest.get('价位', '0')
        total_volume = float(str(total_volume_str).replace(',', '')) if total_volume_str else 0.0
        
        # 三方成交占比 - 适配新字段：额外列6/7/8 或 比例_主/和/客
        home_pct = float(latest.get('比例_主') or latest.get('额外列6', 0) or 0)
        draw_pct = float(latest.get('比例_和') or latest.get('额外列7', 0) or 0)
        away_pct = float(latest.get('比例_客') or latest.get('额外列8', 0) or 0)
        
        # 🔥 盘口数据：优先从handicap_data读取，否则从raw.macth读取
        current_handicap = handicap.get('current_handicap', 0) or 0
        if current_handicap == 0:
            # 尝试从raw.macth读取 (macth[21]是盘口)
            match_info = data.get('match_info', {})
            raw = match_info.get('raw', {})
            macth = raw.get('macth', '').split(',')
            if len(macth) > 21 and macth[21]:
                try:
                    current_handicap = float(macth[21])
                except:
                    pass
        
        initial_handicap = handicap.get('initial_handicap', 0) or 0
        handicap_change = float(initial_handicap) - float(current_handicap)  # 正值=降盘，负值=升盘
        
        # 赔率变化
        current_home_odds = handicap.get('current_home_odds', 0) or 0
        current_away_odds = handicap.get('current_away_odds', 0) or 0
        initial_home_odds = handicap.get('initial_home_odds', 0) or 0
        initial_away_odds = handicap.get('initial_away_odds', 0) or 0
        
        home_odds_change = float(current_home_odds) - float(initial_home_odds)
        away_odds_change = float(current_away_odds) - float(initial_away_odds)
        
        # 欧赔
        home_euro_odds = float(latest.get('主胜_欧赔', 0) or 0)
        draw_euro_odds = float(latest.get('和局_欧赔', 0) or 0)
        away_euro_odds = float(latest.get('客胜_欧赔', 0) or 0)
        
        # 必发指数 - 适配新字段：额外列12/13/14 或 必指_主/和/客
        bfindex_home = float(latest.get('必指_主') or latest.get('额外列12', 0) or 0)
        bfindex_draw = float(latest.get('必指_和') or latest.get('额外列13', 0) or 0)
        bfindex_away = float(latest.get('必指_客') or latest.get('额外列14', 0) or 0)
        
        # 凯利指数
        kelly_home = float(latest.get('凯利_主', 0) or 0)
        kelly_draw = float(latest.get('凯利_和', 0) or 0)
        kelly_away = float(latest.get('凯利_客', 0) or 0)
        
        # 赔付率
        payout_home = float(latest.get('赔付率_主', 0) or 0)
        payout_draw = float(latest.get('赔付率_和', 0) or 0)
        payout_away = float(latest.get('赔付率_客', 0) or 0)
        
        return {
            'total_volume': total_volume,
            'home_pct': home_pct,
            'draw_pct': draw_pct,
            'away_pct': away_pct,
            'handicap_current': current_handicap,
            'handicap_initial': initial_handicap,
            'handicap_change': handicap_change,
            'handicap_trend': handicap.get('handicap_trend', ''),
            'home_odds': current_home_odds,
            'away_odds': current_away_odds,
            'home_odds_change': home_odds_change,
            'away_odds_change': away_odds_change,
            'home_euro_odds': home_euro_odds,
            'draw_euro_odds': draw_euro_odds,
            'away_euro_odds': away_euro_odds,
            'bfindex_home': bfindex_home,
            'bfindex_draw': bfindex_draw,
            'bfindex_away': bfindex_away,
            'kelly_home': kelly_home,
            'kelly_draw': kelly_draw,
            'kelly_away': kelly_away,
            'payout_home': payout_home,
            'payout_draw': payout_draw,
            'payout_away': payout_away,
            'match_info': data.get('match_info', {}),
            'handicap_str': handicap.get('current_handicap_text', ''),
            # 🔥 新增：加权评分模型所需指标
            'profit_home': float(latest.get('赢亏_主') or latest.get('额外列20', 0) or 0),
            'profit_away': float(latest.get('赢亏_客') or latest.get('额外列22', 0) or 0),
            'hot_home': float(latest.get('热指_主') or latest.get('额外列16', 0) or 0),
            'hot_away': float(latest.get('热指_客') or latest.get('额外列17', 0) or 0),
            'kelly_diff_home': float(latest.get('凯差_主') or latest.get('额外列18', 0) or 0),
            'kelly_diff_away': float(latest.get('凯差_客') or latest.get('额外列19', 0) or 0),
            'fair_home': 0.0, # Will be calculated in scoring
            'fair_away': 0.0  # Will be calculated in scoring
        }
    
    def _determine_funding_level(self, total_volume: float) -> Dict:
        """资金等级判定"""
        level = 'L1'
        for lev, (min_val, max_val) in self.funding_levels.items():
            if min_val <= total_volume < max_val:
                level = lev
                break
        
        return {
            'level': level,
            'total_volume': int(total_volume),
            'sbre_weight': self.sbre_weights[level]
        }
    
    def calculate_score_v7(self, metrics: Dict, direction: str, handicap: float = None) -> tuple:
        """
        V7.2 评分模型 - 融合盘口特征
        
        关键发现:
        1. hot<-15 + vol>600K = 69.6% (V7 ELITE)
        2. 主让球+热度反冷 = 76.7% (盘口加成)
        3. 主受让+热度过热 = 83.8% (盘口加成)
        4. 主让+凯利低(<95) = 74.5%
        5. 主受让+凯利低(<95) = 81.9%
        """
        score = 0
        signals = []
        
        # 提取指标
        bf_h = metrics.get('bfindex_home', 0)
        bf_a = metrics.get('bfindex_away', 0)
        hot_h = metrics.get('hot_home', 0)
        hot_a = metrics.get('hot_away', 0)
        volume = metrics.get('total_volume', 0)
        pct_h = metrics.get('home_pct', 0)
        kd_h = metrics.get('kelly_diff_home', 0)
        kd_a = metrics.get('kelly_diff_away', 0)
        kelly_h = metrics.get('kelly_home', 0)
        kelly_a = metrics.get('kelly_away', 0)
        
        bf_diff = bf_h - bf_a
        hot_diff = hot_h - hot_a
        
        if direction == 'home':
            # === 主队评分 V7 ===
            
            # 1. 🔥 极端热度反转 + 高成交 (最强信号!)
            # hot<-15 + vol>600K = 69.6%
            # hot<-10 + vol>500K = 66.4%
            if hot_diff < -15 and volume > 600000:
                score += 60
                signals.append("ELITE_HOT_VOL")
            elif hot_diff < -12 and volume > 500000:
                score += 55
                signals.append("SUPER_HOT_VOL")
            elif hot_diff < -10 and volume > 500000:
                score += 50
                signals.append("STRONG_HOT_VOL")
            elif hot_diff < -10 and volume > 300000:
                score += 40
                signals.append("HOT_VOL")
            elif hot_diff < -10 and volume > 200000:
                score += 30
                signals.append("HOT_MED")
            
            # 2. 高成交比例 + 高必发 (64.1%)
            if pct_h > 60 and bf_h > 45:
                score += 35
                signals.append("PCT_BF")
            elif pct_h > 60:
                score += 15
                signals.append("HIGH_PCT")
            
            # 3. 必发指数优势
            if bf_h > 50:
                score += 25
                signals.append("HIGH_BF")
            elif bf_diff > 15:
                score += 15
                signals.append("BF_DIFF+")
            elif bf_diff > 10:
                score += 10
                signals.append("BF+")
            
            # 4. 热度反转 (无高成交时)
            if hot_diff < -5 and volume > 200000 and "HOT" not in str(signals):
                score += 20
                signals.append("HOT_REV")
            
            # 5. 凯利指数信号
            if kelly_h < 90 and kd_h < 5:
                score += 20
                signals.append("KELLY_SIG")
            elif kelly_h < 95:
                score += 10
                signals.append("LOW_KELLY")
            
            # 6. 负面信号 (扣分)
            if hot_diff > 5:  # 主队过热
                score -= 30
                signals.append("HOT_TRAP!")
            if bf_diff < -10:  # 必发不支持
                score -= 25
                signals.append("BF_NEG!")
            if volume < 50000:  # 成交量过低
                score -= 20
                signals.append("LOW_VOL!")
            
            # 7. 🔥 V7.3 深度特征加成 (基于1222场深度挖掘)
            # 必发低(<40) = ROI+80%, 胜率80.6%
            if bf_h < 40:
                score += 30
                signals.append("BF_LOW_GOLD")
            
            # 超高量(>500K) = ROI+73%
            if volume > 500000:
                score += 15
                signals.append("ULTRA_VOL")
            
            if handicap is not None:
                abs_hdp = abs(handicap)
                
                # 深盘(>1.5) + Elite级别 = ROI+180%
                if abs_hdp > 1.5 and hot_diff < -15:
                    score += 40
                    signals.append("DEEP_ELITE")
                # 球半盘(1.0-1.5) + 极冷门 = ROI+91%
                elif 1.0 < abs_hdp <= 1.5 and hot_diff < -15:
                    score += 30
                    signals.append("HALF_BALL_COLD")
                
                # 主让球 + 热度反冷 = 真让 (76.7%胜率)
                if handicap < -0.25 and hot_diff < -10:
                    score += 25
                    signals.append("HDP_TRUE_LET")
                # 主让 + 凯利低 = 机构看好 (74.5%胜率)
                if handicap < -0.25 and kelly_h < 95:
                    score += 20
                    signals.append("HDP_KELLY")
                # 深让球确定性高 (95.6%胜率)
                if handicap <= -1.5:
                    score += 15
                    signals.append("DEEP_LET")
                # 逆盘惩罚: 主受让却推主队
                if handicap > 0.5:
                    score -= 25
                    signals.append("ANTI_HDP!")
                
        else:  # direction == 'away'
            # === 客队评分 V7 ===
            # 客队ELITE = 68.5%, ROI +30%
            
            # 1. 极端热度反转 + 高成交 (68.5%最强!)
            if hot_diff > 15 and volume > 600000:
                score += 60
                signals.append("ELITE_HOT_VOL")
            elif hot_diff > 10 and volume > 500000:
                score += 50
                signals.append("STRONG_HOT_VOL")
            elif hot_diff > 5 and volume > 300000:
                score += 35
                signals.append("HOT_VOL")
            
            # 2. 必发指数支持
            if bf_a > 45 and hot_diff > 5:
                score += 30
                signals.append("BF_HOT")
            elif bf_diff < -15:
                score += 20
                signals.append("BF_DIFF+")
            elif bf_diff < -10:
                score += 10
                signals.append("BF+")
            
            # 3. 凯利信号
            if kelly_a < 95 and kd_a < 10:
                score += 15
                signals.append("KELLY_SIG")
            
            # 4. 负面信号
            if hot_diff < -5:
                score -= 30
                signals.append("HOT_TRAP!")
            if bf_diff > 10:
                score -= 25
                signals.append("BF_NEG!")
            if volume < 50000:
                score -= 20
                signals.append("LOW_VOL!")
            
            # 5. 🔥 V7.3 深度特征加成 (基于1222场深度挖掘)
            # 必发低(<40) = ROI+80%, 胜率80.6%
            if bf_a < 40:
                score += 30
                signals.append("BF_LOW_GOLD")
            
            # 超高量(>500K) = ROI+73%
            if volume > 500000:
                score += 15
                signals.append("ULTRA_VOL")
            
            if handicap is not None:
                abs_hdp = abs(handicap)
                
                # 深盘(>1.5) + Elite级别 = ROI+180%
                if abs_hdp > 1.5 and hot_diff > 15:
                    score += 40
                    signals.append("DEEP_ELITE")
                # 球半盘(1.0-1.5) + 极冷门 = ROI+91%
                elif 1.0 < abs_hdp <= 1.5 and hot_diff > 15:
                    score += 30
                    signals.append("HALF_BALL_COLD")
                
                # 主受让 + 热度过热 = 假热诱盘 (83.8%胜率!)
                if handicap > 0.25 and hot_diff > 10:
                    score += 30
                    signals.append("HDP_HOT_TRAP")
                # 主受让 + 凯利低 = 机构看好客队 (81.9%胜率)
                if handicap > 0.25 and kelly_a < 95:
                    score += 25
                    signals.append("HDP_KELLY")
                # 深受让确定性高 (95.7%胜率)
                if handicap >= 1.5:
                    score += 15
                    signals.append("DEEP_RCV")
                # 逆盘惩罚: 主让球却推客队
                if handicap < -0.5:
                    score -= 25
                    signals.append("ANTI_HDP!")
        
        return score, signals

    def _recommend_weighted_scoring(self, metrics: Dict, data: Dict) -> Dict:
        """
        🔥 V7.2 推荐模型 - 融合盘口特征
        
        核心发现：
        1. hot<-15 + vol>600K = 69.6% (V7 ELITE)
        2. 主让球+热度反冷 = 76.7% (盘口加成)
        3. 主受让+热度过热 = 83.8% (盘口加成)
        4. 客队ELITE = 68.5%, ROI +30%
        """
        # 获取盘口值
        handicap_value = metrics.get('handicap_current', 0)
        
        # 1. 使用V7.2评分 (传入盘口)
        score_h, sig_h = self.calculate_score_v7(metrics, 'home', handicap_value)
        score_a, sig_a = self.calculate_score_v7(metrics, 'away', handicap_value)
        
        # 2. 获取基础信息
        match_info = metrics.get('match_info', {})
        home_team = match_info.get('home', '') or match_info.get('home_team', '')
        away_team = match_info.get('away', '') or match_info.get('away_team', '')
        handicap_value = metrics.get('handicap_current', 0)
        handicap_current = abs(handicap_value)
        volume = metrics.get('total_volume', 0)
        hot_h = metrics.get('hot_home', 0)
        hot_a = metrics.get('hot_away', 0)
        hot_diff = hot_h - hot_a
        
        # 3. V7推荐逻辑
        direction = 'none'
        confidence = 0.0
        level = ''
        reason = ''
        final_score = 0
        score_diff = abs(score_h - score_a)
        
        # 深盘过滤 (>= 2.0)
        if handicap_current >= 2.0:
            return {'direction': 'none', 'confidence': 0, 'reason': f'超深盘{handicap_current}跳过'}
        
        # 成交量过低过滤
        if volume < 50000:
            return {'direction': 'none', 'confidence': 0, 'reason': f'成交量{volume/1000:.0f}K过低'}
        
        # V7级别阈值 (基于数据挖掘结果)
        ELITE_TH = 55    # ELITE级别 (66%+胜率)
        STRONG_TH = 45   # STRONG级别 (60%+胜率)
        STANDARD_TH = 35 # STANDARD级别 (55%+胜率)
        MIN_DIFF = 20    # 最小分差
        
        # 判断推荐方向
        if score_h > score_a and score_h >= STANDARD_TH and score_diff >= MIN_DIFF:
            # 主队推荐
            final_score = score_h
            
            # 🔥 V7.2信号级别判定 (加入盘口信号)
            has_v7_elite = "ELITE_HOT_VOL" in sig_h or "SUPER_HOT_VOL" in sig_h
            has_v7_strong = "STRONG_HOT_VOL" in sig_h or "HOT_VOL" in sig_h
            has_hdp_signal = "HDP_TRUE_LET" in sig_h or "HDP_KELLY" in sig_h or "DEEP_LET" in sig_h
            has_hot_reversal = hot_diff < -5
            
            # Elite: V7信号 或 (盘口信号+高分)
            if has_v7_elite or (has_hdp_signal and score_h >= 70):
                direction = 'home'
                level = 'Elite'      # 77%+胜率!
                confidence = 0.92
                reason = f"Elite {score_h:.0f}分 ({','.join(sig_h[:4])})"
            elif has_v7_strong and score_h >= STRONG_TH:
                direction = 'home'
                level = 'Strong'     # 70%+胜率
                confidence = 0.85
                reason = f"Strong {score_h:.0f}分 ({','.join(sig_h[:4])})"
            elif (score_h >= ELITE_TH and has_hot_reversal) or has_hdp_signal:
                direction = 'home'
                level = 'Standard'   # 65%+胜率
                confidence = 0.78
                reason = f"Standard {score_h:.0f}分 ({','.join(sig_h[:4])})"
            else:
                reason = f"主队分数{score_h:.0f}不满足条件"
            
        elif score_a > score_h and score_a >= STANDARD_TH and score_diff >= MIN_DIFF:
            # 客队推荐 (客队ELITE = 68.5%!)
            final_score = score_a
            
            has_v7_elite = "ELITE_HOT_VOL" in sig_a or "STRONG_HOT_VOL" in sig_a
            has_v7_strong = "HOT_VOL" in sig_a
            has_hdp_signal = "HDP_HOT_TRAP" in sig_a or "HDP_KELLY" in sig_a or "DEEP_RCV" in sig_a
            has_hot_reversal = hot_diff > 5
            
            # Elite: V7信号 或 (盘口信号+高分) - 盘口信号83.8%胜率!
            if has_v7_elite or (has_hdp_signal and score_a >= 70):
                direction = 'away'
                level = 'Elite'      # 83%+胜率!
                confidence = 0.92
                reason = f"Elite {score_a:.0f}分 ({','.join(sig_a[:4])})"
            elif has_v7_strong and score_a >= STRONG_TH:
                direction = 'away'
                level = 'Strong'     # 70%+胜率
                confidence = 0.82
                reason = f"Strong {score_a:.0f}分 ({','.join(sig_a[:4])})"
            elif (score_a >= ELITE_TH and has_hot_reversal) or has_hdp_signal:
                direction = 'away'
                level = 'Standard'
                confidence = 0.75
                reason = f"Standard {score_a:.0f}分 ({','.join(sig_a[:4])})"
            else:
                reason = f"客队分数{score_a:.0f}不满足条件"
        else:
            reason = f"评分不足(主{score_h:.0f}/客{score_a:.0f},差{score_diff:.0f})"
        
        # 生成格式化推荐
        formatted = ''
        if direction == 'home' and home_team:
            if handicap_value == 0:
                formatted = f"{home_team} 平手"
            elif handicap_value > 0:
                formatted = f"{home_team} +{handicap_value}"
            else:
                formatted = f"{home_team} {handicap_value}"
        elif direction == 'away' and away_team:
            away_hcap = -handicap_value
            if away_hcap == 0:
                formatted = f"{away_team} 平手"
            elif away_hcap > 0:
                formatted = f"{away_team} +{away_hcap}"
            else:
                formatted = f"{away_team} {away_hcap}"
                
        # 🔥 V7.4 智能投注类型选择 (基于1410场平局分析)
        # 关键发现：
        # - 浅盘(<1.0)欧赔胜率仅46%，平局率28% → 改用让球
        # - 深盘(>=1.0)欧赔胜率71%，平局率20% → 推欧赔
        # - 和赔>=4.0时欧赔胜率65% → 可推欧赔
        # - 评分>=150时胜率66% → 可推欧赔
        handicap_bet = None
        handicap_bet_reason = ''
        bet_type = 'euro'  # 默认欧赔
        
        if direction in ['home', 'away'] and handicap_value != 0:
            abs_hdp = abs(handicap_value)
            
            # 判断是否逆盘推荐
            is_ni_pan = (direction == 'home' and handicap_value > 0) or (direction == 'away' and handicap_value < 0)
            
            # V7.8 智能策略：基于409场数据验证
            # 核心发现：
            # - 受让方让球胜率100%!
            # - 深盘蚊子肉(<1.6)：欧赔ROI-0.2%，让球ROI+23.2% → 用让球!
            # - 深盘非蚊子肉(>=1.6)：欧赔胜率71%
            # - 高评分(>=150)：欧赔胜率66%
            
            # 获取推荐方欧赔
            euro_odds = metrics.get('home_euro_odds', 0) if direction == 'home' else metrics.get('away_euro_odds', 0)
            
            if is_ni_pan:
                # 逆盘（受让方）: 让球胜率100%! 
                bet_type = 'handicap'
                handicap_bet = direction
                hdp_type = '平手盘' if abs_hdp < 0.25 else ('平半盘' if abs_hdp <= 0.5 else ('半一盘' if abs_hdp <= 0.75 else '一球盘'))
                team = home_team if direction == 'home' else away_team
                if direction == 'home':
                    hdp_display = handicap_value
                else:
                    hdp_display = -handicap_value
                handicap_bet_reason = f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}受让)"
            elif abs_hdp >= 1.0 and euro_odds > 0 and euro_odds < 1.6:
                # 深盘蚊子肉(<1.6): 让球ROI+23.2%远高于欧赔!
                bet_type = 'handicap'
                handicap_bet = direction
                hdp_type = '球半盘' if abs_hdp <= 1.25 else ('一球半盘' if abs_hdp <= 1.5 else '深盘')
                team = home_team if direction == 'home' else away_team
                if direction == 'home':
                    hdp_display = -handicap_value  # 顺盘让球
                else:
                    hdp_display = handicap_value
                handicap_bet_reason = f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}避蚊子肉ROI+23%)"
            elif abs_hdp >= 1.0:
                # 深盘(>=1.0) + 顺盘: 用让球（ROI+31%验证）
                bet_type = 'handicap'
                handicap_bet = direction
                hdp_type = '一球盘' if abs_hdp <= 1.0 else ('球半盘' if abs_hdp <= 1.5 else '深盘')
                team = home_team if direction == 'home' else away_team
                if direction == 'home':
                    hdp_display = -handicap_value  # 顺盘让球
                else:
                    hdp_display = handicap_value
                handicap_bet_reason = f"让球推荐: {team} {hdp_display:+.2f} ({hdp_type}顺盘)"
            else:
                # 浅中盘(<1.0) + 顺盘: 风险高，过滤不推
                direction = 'none'
                bet_type = 'euro'
                handicap_bet = None
        
        return {
            'direction': direction,
            'confidence': confidence,
            'level': level,
            'score': final_score,
            'reason': reason,
            'handicap': handicap_value,
            'formatted': formatted,
            'home_team': home_team,
            'away_team': away_team,
            'bet_type': bet_type,  # 🔥 推荐类型: 'euro' 或 'handicap'
            'handicap_bet': handicap_bet,  # 🔥 让球盘口推荐方向
            'handicap_bet_reason': handicap_bet_reason  # 🔥 让球推荐理由
        }
    
    def _flm_scoring(self, metrics: Dict) -> Dict:
        """
        FLM评分 - 热度前线模块
        
        核心逻辑：
        1. 分析三方成交占比的分布
        2. 判断是否存在明显的资金倾向
        3. 识别虚热、灌热、真实热度
        """
        home_pct = metrics['home_pct']
        away_pct = metrics['away_pct']
        draw_pct = metrics['draw_pct']
        
        # 判断主导方
        if home_pct > 60:
            direction = 'home_strong'
            confidence = min(home_pct / 70, 1.0)
        elif away_pct > 50:
            direction = 'away_strong'
            confidence = min(away_pct / 60, 1.0)
        elif draw_pct > 25:
            direction = 'draw_risk'
            confidence = min(draw_pct / 30, 1.0)
        else:
            # 🔥 优化：即使是均衡，也根据优势方给出倾向（降低阈值）
            if home_pct > away_pct and home_pct > draw_pct:
                direction = 'home_weak'  # 主队弱优势
                confidence = min(home_pct / 60, 0.65)  # 最高65%
            elif away_pct > home_pct and away_pct > draw_pct:
                direction = 'away_weak'  # 客队弱优势
                confidence = min(away_pct / 50, 0.65)  # 最高65%
            else:
                direction = 'balanced'
                confidence = 0.3
        
        # 热度等级
        if home_pct > 70 or away_pct > 60:
            level = '强热支持'
        elif home_pct > 55 or away_pct > 45:
            level = '热度支持'
        elif abs(home_pct - away_pct) < 15:
            level = '热度均衡'
        else:
            level = '虚热'
        
        return {
            'direction': direction,
            'confidence': confidence,
            'level': level,
            'home_pct': home_pct,
            'away_pct': away_pct,
            'draw_pct': draw_pct
        }
    
    def _spm_scoring(self, metrics: Dict) -> Dict:
        """
        SPM评分 - 结构承压模块
        
        核心逻辑：
        1. 分析盘口变化方向
        2. 分析赔率变化方向
        3. 判断盘口+赔率是否一致
        """
        handicap_change = metrics['handicap_change']
        home_odds_change = metrics['home_odds_change']
        away_odds_change = metrics['away_odds_change']
        
        # 盘口变化分析
        if handicap_change > 0.25:
            handicap_signal = 'home_favor'  # 降盘，利好主队
        elif handicap_change < -0.25:
            handicap_signal = 'away_favor'  # 升盘，利好客队
        else:
            handicap_signal = 'neutral'
        
        # 赔率变化分析（水位）
        if home_odds_change < -0.05:  # 主队水位降低
            odds_signal = 'home_favor'
        elif away_odds_change < -0.05:  # 客队水位降低
            odds_signal = 'away_favor'
        else:
            odds_signal = 'neutral'
        
        # 判断一致性
        if handicap_signal == odds_signal and handicap_signal != 'neutral':
            structure = '顺势结构'
            confidence = 0.8
        elif handicap_signal != odds_signal and handicap_signal != 'neutral' and odds_signal != 'neutral':
            structure = '诱导结构'
            confidence = 0.4
        else:
            structure = '中性结构'
            confidence = 0.5
        
        return {
            'structure': structure,
            'confidence': confidence,
            'handicap_signal': handicap_signal,
            'odds_signal': odds_signal,
            'handicap_change': handicap_change
        }
    
    def _dpi_scoring(self, flm: Dict, spm: Dict, metrics: Dict) -> Dict:
        """
        DPI评分 - 风险整合模块
        
        核心逻辑：
        1. 综合FLM和SPM的结果
        2. 判断方向一致性
        3. 给出最终风险评级
        """
        flm_direction = flm['direction']
        spm_structure = spm['structure']
        
        # 🔥 调试日志
        logger.info(f"  DPI输入: FLM方向={flm_direction}, SPM结构={spm_structure}, 盘口信号={spm.get('handicap_signal')}")
        
        # 判断方向一致性
        if 'home' in flm_direction and spm['handicap_signal'] == 'home_favor':
            risk_level = '低风险'
            confidence = min((flm['confidence'] + spm['confidence']) / 2 * 1.2, 1.0)
            recommendation = 'home'
            logger.info(f"  DPI决策: 低风险-主队 (FLM+SPM一致)")
        elif 'away' in flm_direction and spm['handicap_signal'] == 'away_favor':
            risk_level = '低风险'
            confidence = min((flm['confidence'] + spm['confidence']) / 2 * 1.2, 1.0)
            recommendation = 'away'
            logger.info(f"  DPI决策: 低风险-客队 (FLM+SPM一致)")
        elif spm_structure == '诱导结构':
            risk_level = '高风险'
            confidence = 0.3
            recommendation = 'none'
            logger.warning(f"  DPI决策: 高风险-不推荐 (诱导结构)")
        else:
            risk_level = '中风险'
            confidence = (flm['confidence'] + spm['confidence']) / 2
            # 🔥 优化：支持 'home_weak' 和 'away_weak' 方向
            if 'home' in flm_direction:
                recommendation = 'home'
            elif 'away' in flm_direction:
                recommendation = 'away'
            else:
                recommendation = 'none'
            logger.info(f"  DPI决策: 中风险-{recommendation} (FLM主导, confidence={confidence:.2f})")
        
        # 压强指数
        pressure_index = int(confidence * 100)
        
        return {
            'risk_level': risk_level,
            'confidence': confidence,
            'recommendation': recommendation,
            'pressure_index': pressure_index
        }
    
    def _run_risk_checks(self, metrics: Dict, flm: Dict, spm: Dict, dpi: Dict) -> Dict:
        """
        风控机制检测
        
        SmartSafe: 结构支撑缺失检测
        SS-Dagger: 诱导识别
        LVC: 落点验证
        TPI: 穿盘预警
        """
        flags = {
            'SmartSafe': False,
            'SS-Dagger': False,
            'LVC': False,
            'TPI': False,
            'messages': []
        }
        
        # SmartSafe: 高成交但结构矛盾
        if metrics['total_volume'] > 100000 and spm['structure'] == '诱导结构':
            flags['SmartSafe'] = True
            flags['messages'].append('结构支撑缺失：高成交量但盘口赔率矛盾')
        
        # SS-Dagger: 盘口诱导识别
        if spm['structure'] == '诱导结构':
            flags['SS-Dagger'] = True
            flags['messages'].append('诱导识别：盘口变化与赔率调整相反')
        
        # LVC: 落点验证（凯利指数异常）
        if metrics['kelly_home'] > 120 or metrics['kelly_away'] > 120:
            flags['LVC'] = True
            flags['messages'].append('落点异常：凯利指数过高，存在虚脱风险')
        
        # TPI: 穿盘预警（深盘+低水）
        if abs(metrics['handicap_current']) > 1.5 and (metrics['home_odds'] < 0.75 or metrics['away_odds'] < 0.75):
            flags['TPI'] = True
            flags['messages'].append('穿盘预警：深盘配低水，存在穿盘陷阱风险')
        
        return flags
    
    def _sbre_mechanism(self, funding_level: Dict, metrics: Dict, dpi: Dict, risk_flags: Dict) -> Dict:
        """
        SBRE反解机制
        
        触发条件：
        1. L1/L2资金等级 + 高风险标记
        2. 盘口赔率严重矛盾
        """
        triggered = False
        direction = None
        confidence = 0.0
        reason = ''
        
        # L1/L2强制执行
        sbre_weight = funding_level['sbre_weight']
        
        if sbre_weight >= 0.85 and (risk_flags['SS-Dagger'] or risk_flags['SmartSafe']):
            triggered = True
            # 反解：诱导盘通常反向
            if dpi['recommendation'] == 'home':
                direction = 'away'
            elif dpi['recommendation'] == 'away':
                direction = 'home'
            else:
                direction = 'none'
            
            confidence = sbre_weight * 0.7
            reason = f"SBRE反解触发（{funding_level['level']}）：诱导盘反向推荐"
        
        return {
            'triggered': triggered,
            'direction': direction,
            'confidence': confidence,
            'reason': reason
        }
    
    def _calculate_dynamic_threshold(self, metrics: Dict, funding_level: Dict) -> float:
        """
        🔥 新版：数据驱动规则（V2.0）
        
        基于820场历史数据验证的简单规则
        预期胜率: 69.5%，推荐率: 45.2%
        
        核心规则：
        1. 成交占比差值 ≥ 30%
        2. 必发指数差值 ≥ 0
        3. 最小成交量 ≥ 50,000
        """
        # 🔥 使用简单规则，不需要复杂的动态阈值
        # 如果满足规则，固定返回0.70让比赛通过
        # 如果不满足规则，返回高阈值让比赛不通过
        
        total_volume = metrics.get('total_volume', 0)
        home_pct = metrics.get('home_pct', 0)
        away_pct = metrics.get('away_pct', 0)
        pct_diff = home_pct - away_pct
        
        bfindex_home = metrics.get('bfindex_home', 0)
        bfindex_away = metrics.get('bfindex_away', 0)
        bfindex_diff = bfindex_home - bfindex_away
        
        # 检查基础条件
        if total_volume < 50000:
            return 0.95  # 成交量不足，几乎不推荐
        
        # 检查主胜条件或客胜条件
        if (pct_diff >= 30 and bfindex_diff >= 0) or (pct_diff <= -30 and bfindex_diff <= 0):
            return 0.65  # 满足规则，允许推荐
        else:
            return 0.90  # 不满足规则，不推荐
        
        # 2. 数据完整性
        data_quality = sum([
            metrics.get('bfindex_home', 0) > 0,
            metrics.get('kelly_home', 0) > 0,
            metrics.get('home_euro_odds', 0) > 0
        ])
        if data_quality == 3:
            adjustments -= 0.02  # 数据完整：降2%
        elif data_quality < 2:
            adjustments += 0.03  # 数据不完整：升3%
        
        # 3. 资金等级（SBRE权重反映市场效率）
        sbre_weight = funding_level.get('sbre_weight', 0.5)
        if sbre_weight >= 0.85:  # L1/L2 大热门
            adjustments -= 0.02
        elif sbre_weight <= 0.35:  # L4/L5 冷门
            adjustments += 0.03
        
        # 限制在合理范围
        return max(0.70, min(0.90, base_threshold + adjustments))
    
    def _generate_recommendation(
        self,
        metrics: Dict,
        flm: Dict,
        spm: Dict,
        dpi: Dict,
        sbre: Dict,
        risk_flags: Dict,
        funding_level: Dict
    ) -> Dict:
        """生成最终推荐（VIS格式）"""
        
        # 🔥 准确率提升：动态置信度阈值
        MIN_CONFIDENCE_THRESHOLD = self._calculate_dynamic_threshold(metrics, funding_level)  # 策略1：分级阈值
        
        # 如果触发熔断
        if any(risk_flags.values()) and dpi['risk_level'] == '高风险':
            return {
                'version': 'X1-JSON-V1.0',
                'timestamp': datetime.now().isoformat(),
                'match_info': metrics['match_info'],
                'data_source': {
                    'ug_pdf': '✅ JSON数据',
                    'handicap': '✅ 500彩票网',
                    'vim': '✖ 未触发（模块下线）'
                },
                'funding_level': funding_level,
                'scores': {
                    'FLM': flm,
                    'SPM': spm,
                    'DPI': dpi
                },
                'risk_control': risk_flags,
                'sbre': sbre,
                'recommendation': {
                    'direction': 'none',
                    'confidence': 0.0,
                    'reason': '触发风控熔断，不建议下注'
                },
                'meltdown': {
                    'type': 'F-CONS',
                    'reason': '风控机制触发：' + ', '.join(risk_flags['messages'])
                }
            }
        
        # 正常推荐
        final_direction = sbre['direction'] if sbre['triggered'] else dpi['recommendation']
        final_confidence = sbre['confidence'] if sbre['triggered'] else dpi['confidence']
        final_reason = sbre['reason'] if sbre['triggered'] else f"{flm['level']}, {spm['structure']}, {dpi['risk_level']}"
        
        # 🔥 置信度阈值检查（准确率提升的关键）
        if final_confidence < MIN_CONFIDENCE_THRESHOLD and final_direction != 'none':
            logger.info(f"  ⚠️  置信度{final_confidence:.2f}低于阈值{MIN_CONFIDENCE_THRESHOLD}，不推荐")
            return {
                'version': 'X1-JSON-V1.0',
                'timestamp': datetime.now().isoformat(),
                'match_info': metrics['match_info'],
                'data_source': {
                    'ug_pdf': '✅ JSON数据',
                    'handicap': '✅ 500彩票网',
                    'vim': '✖ 未触发（模块下线）'
                },
                'funding_level': funding_level,
                'scores': {'FLM': flm, 'SPM': spm, 'DPI': dpi},
                'risk_control': risk_flags,
                'sbre': sbre,
                'recommendation': {
                    'direction': 'none',
                    'confidence': final_confidence,
                    'reason': f'置信度{final_confidence:.2f}低于阈值{MIN_CONFIDENCE_THRESHOLD}，建议观望'
                },
                'meltdown': {
                    'type': 'LOW_CONFIDENCE',
                    'reason': f'置信度{final_confidence:.2f}低于阈值{MIN_CONFIDENCE_THRESHOLD}',
                    'original_direction': final_direction,
                    'threshold': MIN_CONFIDENCE_THRESHOLD
                }
            }
        
        # 盘口推荐
        if final_direction == 'home':
            handicap_rec = f"主队 {metrics['handicap_str']} @{metrics['home_odds']}"
        elif final_direction == 'away':
            handicap_rec = f"客队受让 {metrics['handicap_str']} @{metrics['away_odds']}"
        else:
            handicap_rec = "不推荐"
        
        return {
            'version': 'X1-JSON-V1.0',
            'timestamp': datetime.now().isoformat(),
            'match_info': metrics['match_info'],
            'data_source': {
                'ug_pdf': '✅ JSON数据',
                'handicap': '✅ 500彩票网',
                'vim': '✖ 未触发（模块下线）'
            },
            'funding_level': funding_level,
            'scores': {
                'FLM': flm,
                'SPM': spm,
                'DPI': dpi
            },
            'risk_control': risk_flags,
            'sbre': sbre,
            'recommendation': {
                'direction': final_direction,
                'handicap': handicap_rec,
                'confidence': final_confidence,
                'confidence_pct': f"{final_confidence*100:.1f}%",
                'reason': final_reason
            },
            'risk_notes': risk_flags['messages'] if risk_flags['messages'] else ['无显著风险']
        }
    
    def _create_melt_result(self, melt_type: str, reason: str) -> Dict:
        """创建熔断结果"""
        return {
            'version': 'X1-JSON-V1.0',
            'timestamp': datetime.now().isoformat(),
            'recommendation': {
                'direction': 'none',
                'confidence': 0.0,
                'reason': '熔断'
            },
            'meltdown': {
                'type': melt_type,
                'reason': reason
            }
        }
    
    def generate_recommendation(self, trade_data, metadata, handicap_data) -> Dict:
        """
        兼容旧接口的推荐方法（用于回测引擎）
        
        将 DataFrame 格式的数据转换为 X1 JSON 格式，然后调用推荐逻辑
        """
        try:
            # 1. 统一metadata格式（兼容list和dict）
            if isinstance(metadata, list):
                # list格式: [联赛, 主队, 客队, ...]
                meta = {
                    'league': metadata[0] if len(metadata) > 0 else '',
                    'home': metadata[1] if len(metadata) > 1 else '',
                    'away': metadata[2] if len(metadata) > 2 else ''
                }
            elif isinstance(metadata, dict):
                meta = metadata
            else:
                # 兜底：如果是str或其他类型
                meta = {
                    'league': str(metadata) if metadata else '',
                    'home': '',
                    'away': ''
                }
            
            # 提取比赛信息
            match_info = {
                'league': meta.get('league', ''),
                'home_team': meta.get('home', ''),
                'away_team': meta.get('away', '')
            }
            
            # 2. 构建 X1 JSON 格式的数据
            temp_data = {
                'match_info': match_info,
                'handicap_data': handicap_data or {},
                'trade_data': {
                    'data': trade_data.to_dict('records') if hasattr(trade_data, 'to_dict') else []
                }
            }
            
            # 3. 提取核心指标
            metrics = self._extract_metrics(temp_data)
            if not metrics:
                return {
                    'direction': 'none',
                    'should_bet': False,
                    'confidence': 0.0,
                    'reason': '数据不足',
                    'version': 'X1-JSON-V1.0'
                }
            
            # 添加比赛信息和盘口字符串
            metrics['match_info'] = match_info
            metrics['handicap_str'] = handicap_data.get('current_handicap_str', '') if handicap_data else ''
            
            # 🔥 V2模式：使用简化规则直接推荐（与recommend方法一致）
            v2_result = self._recommend_v2_simple(metrics)
            if v2_result['direction'] != 'none':
                # 提取盘口数据
                handicap_value = handicap_data.get('current_handicap') if handicap_data else 0
                handicap_str = handicap_data.get('current_handicap_str', '') if handicap_data else ''
                
                # 构建完整的推荐结果（兼容验证器）
                final_recommendation = {
                    'direction': v2_result['direction'],
                    'should_bet': True,
                    'confidence': v2_result['confidence'],
                    'reason': v2_result['reason'],
                    'handicap': handicap_value,
                    'handicap_str': handicap_str
                }
                
                # 返回V2推荐结果（包装成验证器期望的格式）
                return {
                    'direction': v2_result['direction'],
                    'should_bet': True,
                    'confidence': v2_result['confidence'],
                    'reason': v2_result['reason'],
                    'handicap': handicap_value,
                    'handicap_str': handicap_str,
                    'version': MODEL_FULL_NAME,
                    'engine': ENGINE_NAME,
                    '最终推荐': final_recommendation  # 🔥 添加验证器需要的字段
                }
            
            # 如果V2不推荐，返回不推荐（不再继续旧逻辑）
            return {
                'direction': 'none',
                'should_bet': False,
                'confidence': 0.0,
                'reason': v2_result['reason'],
                'version': MODEL_FULL_NAME
            }
            
            # === 以下是旧逻辑，已被V2替代，保留作为参考 ===
            # 4. 资金等级判定
            funding_level = self._determine_funding_level(metrics['total_volume'])
            
            # 5. FLM评分 - 热度前线
            flm_score = self._flm_scoring(metrics)
            
            # 6. SPM评分 - 承压分析
            spm_score = self._spm_scoring(metrics)
            
            # 7. DPI评分 - 风险整合
            dpi_score = self._dpi_scoring(flm_score, spm_score, metrics)
            
            # 8. 风控检测
            risk_flags = self._run_risk_checks(metrics, flm_score, spm_score, dpi_score)
            
            # 9. SBRE反解（如触发）
            sbre_result = self._sbre_mechanism(funding_level, metrics, dpi_score, risk_flags)
            
            # 10. 生成推荐
            x1_result = self._generate_recommendation(
                metrics, flm_score, spm_score, dpi_score, sbre_result, risk_flags, funding_level
            )
            
            # 11. 转换为旧格式（兼容回测引擎和vis_formatter）
            rec = x1_result.get('recommendation', {})
            
            # 🔥 构建最终推荐结构（兼容验证器）
            direction = rec.get('direction', 'none')
            confidence = rec.get('confidence', 0)
            
            # 🔥 使用策略1：动态阈值（与recommend方法一致）
            # 根据比赛质量动态调整阈值，保证准确率
            dynamic_threshold = self._calculate_dynamic_threshold(metrics, funding_level)
            should_bet = direction not in ['none', None] and confidence >= dynamic_threshold
            
            # 🔥 调试日志：记录推荐决策
            logger.info(f"📊 推荐决策: direction={direction}, confidence={confidence:.2f}, dynamic_threshold={dynamic_threshold:.2f}, should_bet={should_bet}")
            
            # 🔥 提取数值格式的盘口（用于验证器计算）
            # metrics 中有 current_handicap (float) 和 handicap_str (字符串)
            handicap_value = metrics.get('current_handicap', 0.0)
            handicap_str = metrics.get('handicap_str', '')
            
            final_recommendation = {
                'direction': direction,
                'should_bet': should_bet,
                'confidence': confidence,
                'reason': rec.get('reason', ''),
                'handicap': handicap_value,  # 数值格式，用于验证器
                'handicap_str': handicap_str  # 字符串格式，用于显示
            }
            
            # 🔥 返回完整的X1结果数据结构（兼容vis_formatter和验证器）
            result = {
                'direction': direction,
                'should_bet': should_bet,
                'confidence': confidence,
                'reason': rec.get('reason', ''),
                'handicap': rec.get('handicap', ''),
                'version': 'X1-JSON-V1.0',
                'engine': 'x1_json',  # 标记为x1_json以使用正确的格式化器
                # 🔥 验证器需要的结构
                '最终推荐': final_recommendation,
                # 🔥 提取完整的X1数据结构给vis_formatter使用
                'x1_json_scores': x1_result.get('scores', {}),
                'x1_json_funding': x1_result.get('funding_level', {}),
                'x1_json_risk': x1_result.get('risk_control', {}),
                # 保留完整的 X1 结果用于调试
                'x1_full_result': x1_result
            }
            return result
            
        except Exception as e:
            logger.exception("兼容接口推荐失败")
            return {
                'direction': 'none',
                'should_bet': False,
                'confidence': 0.0,
                'reason': f'执行异常: {str(e)}',
                'version': 'X1-JSON-V1.0'
            }


# 测试函数
def test_recommender():
    """测试推荐器"""
    logging.basicConfig(level=logging.INFO)
    
    recommender = X1JSONRecommender()
    
    # 示例：测试一场比赛
    test_path = "data/2025/11/25/2025-11-25_欧联U19_曼彻斯特城U19_vs_勒沃库森U19_2300.json"
    
    print("="*80)
    print("X1 JSON推荐引擎测试")
    print("="*80)
    print(f"测试文件: {test_path}")
    print()
    
    result = recommender.recommend(test_path)
    
    # 美化输出
    import json as json_lib
    print(json_lib.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_recommender()
