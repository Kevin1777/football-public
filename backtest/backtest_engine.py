"""
回测引擎
用于历史比赛的回测验证
"""
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, recommendation_engine, lottery500_client, bifaw_client, detail_cache_manager=None):
        """
        初始化回测引擎
        
        Args:
            recommendation_engine: 推荐引擎实例
            lottery500_client: 500彩票网客户端
            bifaw_client: 必发客户端
            detail_cache_manager: 明细缓存管理器（可选）
        """
        self.recommendation_engine = recommendation_engine
        self.lottery500_client = lottery500_client
        self.bifaw_client = bifaw_client
        self.detail_cache_manager = detail_cache_manager
        
        # 盘口数据缓存（内存缓存，避免重复请求）
        self._handicap_cache = {}
        self._last_handicap_request_time = 0
        self._handicap_request_interval = 0.5  # 500ms间隔
        
        from .result_validator import ResultValidator
        self.validator = ResultValidator()
    
    def backtest_single_match(
        self,
        match_info: Dict,
        detail_url: str,
        actual_score: Tuple[int, int],
        detail_params: Optional[Dict] = None,
        score_for_cache: Optional[str] = None
    ) -> Dict:
        """
        单场比赛回测
        
        Args:
            match_info: 比赛信息 {home, away, league, kickoff} ⚠️ 不应包含score
            detail_url: 明细页面URL
            actual_score: 实际比分 (主队, 客队) ⚠️ 仅用于事后验证
            detail_params: 明细参数（可选）
            score_for_cache: 比分字符串 🔒 仅用于缓存查找，不传给推荐引擎
            
        Returns:
            回测结果
        """
        try:
            logger.info(f"开始回测: {match_info.get('home')} vs {match_info.get('away')}")
            
            result = {
                'success': False,
                'match_info': match_info,
                'actual_score': actual_score,
                'timestamp': datetime.now().isoformat()
            }
            
            # 1. 获取交易明细（同时获取缓存的盘口数据）
            logger.info("获取交易明细...")
            trade_data, cached_handicap, metadata = self._fetch_trade_data(
                detail_url, match_info, detail_params, score_for_cache
            )
            
            if trade_data is None:
                result['error'] = '交易明细获取失败'
                return result
            
            result['trade_data_rows'] = len(trade_data)
            
            # 2. 获取让球盘口数据（优先使用缓存）
            logger.info("获取让球盘口数据...")
            if cached_handicap:
                logger.info(f"✅ 使用缓存的盘口数据")
                handicap_data = cached_handicap
            else:
                logger.info("缓存无盘口数据，尝试实时获取...")
                handicap_data = self._fetch_handicap_data(match_info)
            
            # 降级处理：即使没有盘口数据也继续回测
            if handicap_data:
                result['handicap_data'] = {
                    'initial': f"{handicap_data.get('initial_handicap_str')} ({handicap_data.get('initial_handicap')})",
                    'current': f"{handicap_data.get('current_handicap_str')} ({handicap_data.get('current_handicap')})"
                }
            else:
                logger.warning("未获取到盘口数据，将使用基础推荐")
                result['handicap_data'] = None
            
            # 3. 生成推荐
            logger.info("生成推荐...")
            # 🔒 安全验证：确保match_info中没有score
            if 'score' in match_info:
                logger.error(f"⚠️ 检测到match_info中包含score字段！这会导致偷看比分！")
                logger.error(f"   match_info keys: {list(match_info.keys())}")
                raise ValueError("match_info不应包含score字段！")
            
            recommendation = self.recommendation_engine.generate_recommendation(
                trade_data=trade_data,
                metadata=metadata,
                handicap_data=handicap_data
            )
            
            result['recommendation'] = recommendation
            
            # 4. 验证推荐结果
            logger.info("验证推荐结果...")
            validation = self.validator.validate_recommendation(
                recommendation=recommendation,
                actual_score=actual_score,
                actual_handicap=handicap_data.get('current_handicap') if handicap_data else None
            )
            
            result['validation'] = validation
            result['success'] = validation.get('validated', False)
            
            return result
            
        except Exception as e:
            logger.exception("回测失败")
            return {
                'success': False,
                'error': str(e),
                'match_info': match_info
            }
    
    def _fetch_trade_data(
        self,
        detail_url: str,
        match_info: Dict,
        detail_params: Optional[Dict],
        score_for_cache: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[Dict], List[Dict]]:
        """获取交易明细数据（优先从缓存读取，同时返回盘口数据）"""
        try:
            # 🔒 安全措施：仅用于缓存查找，不影响推荐引擎
            match_info_for_cache = match_info.copy()
            if score_for_cache:
                logger.info(f"🔍 仅用于缓存查找的比分: {score_for_cache}")
                match_info_for_cache['score'] = score_for_cache
            
            # 优先从缓存读取
            if self.detail_cache_manager:
                cache_result = self.detail_cache_manager.load_detail(match_info_for_cache)
                if cache_result:
                    trade_data, handicap_data, metadata = cache_result
                    logger.info(f"✅ 从缓存读取明细: {len(trade_data)}行")
                    if handicap_data:
                        logger.info(f"✅ 从缓存读取盘口: {handicap_data.get('current_handicap_str', 'N/A')}")
                    return trade_data, handicap_data, metadata
                else:
                    logger.info("缓存不存在，实时抓取...")
            
            # 缓存不存在，实时抓取
            logger.info("📡 使用Selenium抓取明细（支持动态加载）...")
            
            # 使用Selenium获取动态加载的HTML（和单场一样）
            detail_html = self.bifaw_client.fetch_match_detail_selenium(
                detail_url=detail_url,
                match=match_info,
                detail_params=detail_params
            )
            
            # 解析明细
            from parser.html_parser import parse_bifa_html
            
            if not detail_html or len(detail_html) < 1000:
                logger.error(f"明细HTML为空或过短: {len(detail_html) if detail_html else 0} 字符")
                return None, []
            
            # 调试：保存HTML到文件
            try:
                import os
                from pathlib import Path
                import re
                
                # 使用项目根目录的绝对路径
                project_root = Path(__file__).parent.parent
                debug_dir = project_root / "debug_html"
                debug_dir.mkdir(exist_ok=True)
                
                # 提取比赛信息
                kickoff = match_info.get('kickoff', '')  # 格式: "2025-11-07 19:00"
                league = match_info.get('league', '未知联赛')
                home = match_info.get('home', '未知主队')
                away = match_info.get('away', '未知客队')
                
                # 清理文件名中的非法字符
                def safe_filename(s):
                    # 替换非法字符为下划线
                    s = re.sub(r'[<>:"/\\|?*]', '_', s)
                    # 替换空格为下划线
                    s = s.replace(' ', '_')
                    return s[:30]  # 限制长度避免路径过长
                
                # 格式化时间: 11-07_19-00
                if kickoff:
                    try:
                        time_part = kickoff.replace(' ', '_').replace(':', '-')
                        if len(time_part) > 16:  # "2025-11-07_19-00"
                            time_part = time_part[5:]  # 去掉年份: "11-07_19-00"
                    except:
                        time_part = "未知时间"
                else:
                    time_part = "未知时间"
                
                # 构造文件名: batch_11-07_19-00_英超_曼联_vs_利物浦.html
                filename = f"batch_{time_part}_{safe_filename(league)}_{safe_filename(home)}_vs_{safe_filename(away)}.html"
                html_path = debug_dir / filename
                
                logger.info(f"准备保存HTML到: {html_path}")
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(detail_html)
                
                logger.info(f"✅ 已保存HTML: {filename}")
                logger.info(f"📂 完整路径: {html_path}")
                logger.info(f"📄 文件大小: {os.path.getsize(html_path)} 字节")
                
            except Exception as e:
                logger.error(f"❌ 保存调试HTML失败: {e}", exc_info=True)
            
            # 解析HTML
            trade_data = parse_bifa_html(detail_html, match=match_info)
            
            if not isinstance(trade_data, pd.DataFrame):
                logger.error(f"明细解析失败: {trade_data}")
                logger.error(f"HTML长度: {len(detail_html)}")
                logger.error(f"是否包含'成交量': {'成交量' in detail_html}")
                return None, None, []
            
            metadata = trade_data.attrs.get("metadata", [])
            
            # 保存到缓存（如果有缓存管理器）
            # 注意：实时抓取时不包含盘口数据，盘口需单独获取或从批量采集缓存读取
            if self.detail_cache_manager and not trade_data.empty:
                try:
                    self.detail_cache_manager.save_detail(
                        match_info=match_info,
                        trade_data=trade_data,
                        handicap_data=None,  # 实时抓取不含盘口
                        metadata=metadata
                    )
                    logger.info("已自动缓存明细")
                except Exception as e:
                    logger.warning(f"自动缓存失败: {e}")
            
            return trade_data, None, metadata  # 返回None作为盘口数据
            
        except Exception as e:
            logger.exception("获取交易明细失败")
            return None, None, []
    
    def _fetch_handicap_data(self, match_info: Dict) -> Optional[Dict]:
        """
        获取让球盘口数据（带缓存和请求间隔）
        
        Returns:
            盘口数据字典，如果获取失败返回None
        """
        try:
            # 生成缓存key
            cache_key = f"{match_info.get('home')}_{match_info.get('away')}_{match_info.get('kickoff', '')[:10]}"
            
            # 1. 先尝试从缓存读取
            if cache_key in self._handicap_cache:
                logger.info(f"从缓存读取盘口数据: {cache_key}")
                return self._handicap_cache[cache_key]
            
            # 2. 请求间隔控制（避免429限流）
            current_time = time.time()
            time_since_last_request = current_time - self._last_handicap_request_time
            
            if time_since_last_request < self._handicap_request_interval:
                wait_time = self._handicap_request_interval - time_since_last_request
                logger.info(f"等待 {wait_time:.2f}秒 避免限流...")
                time.sleep(wait_time)
            
            # 3. 发起请求
            logger.info(f"请求盘口数据: {match_info.get('home')} vs {match_info.get('away')}")
            self._last_handicap_request_time = time.time()
            
            handicap_data = self.lottery500_client.get_match_handicap(
                home_team=match_info.get("home"),
                away_team=match_info.get("away"),
                league=match_info.get("league"),
                match_date=match_info.get("kickoff", "").split()[0] if match_info.get("kickoff") else None
            )
            
            # 4. 存入缓存
            if handicap_data:
                self._handicap_cache[cache_key] = handicap_data
                logger.info(f"盘口数据已缓存: {cache_key}")
            
            return handicap_data
            
        except Exception as e:
            logger.warning(f"获取让球盘口数据失败: {e}")
            return None
    
    def batch_backtest(
        self,
        matches: List[Dict],
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        批量回测（串行处理，带请求间隔）
        
        Args:
            matches: 比赛列表，每个包含 match_info, detail_url, actual_score
            progress_callback: 进度回调函数
            
        Returns:
            批量回测结果
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"开始批量回测: {len(matches)} 场比赛")
        logger.info(f"{'='*80}\n")
        
        # 清空缓存（可选：也可以保留缓存以加速）
        # self._handicap_cache.clear()
        
        results = []
        success_count = 0
        failed_count = 0
        no_handicap_count = 0
        
        for i, match in enumerate(matches):
            logger.info(f"\n[{i+1}/{len(matches)}] 回测: {match.get('match_info', {}).get('label', '未知比赛')}")
            
            result = self.backtest_single_match(
                match_info=match.get('match_info', {}),
                detail_url=match.get('detail_url', ''),
                actual_score=match.get('actual_score', (0, 0)),
                detail_params=match.get('detail_params'),
                score_for_cache=match.get('score_for_cache')  # 🔒 仅用于缓存
            )
            
            # 统计
            if result.get('success'):
                success_count += 1
            else:
                failed_count += 1
            
            if not result.get('handicap_data'):
                no_handicap_count += 1
            
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, len(matches), result)
            
            # 每场回测后短暂延迟（避免资源占用）
            if i < len(matches) - 1:
                time.sleep(0.1)
        
        # 计算统计数据
        validations = [r.get('validation', {}) for r in results if r.get('success')]
        statistics = self.validator.calculate_statistics(validations)
        
        # 汇总日志
        logger.info(f"\n{'='*80}")
        logger.info(f"批量回测完成")
        logger.info(f"{'='*80}")
        logger.info(f"总比赛数: {len(matches)}")
        logger.info(f"成功: {success_count}, 失败: {failed_count}")
        logger.info(f"未获取盘口: {no_handicap_count}")
        logger.info(f"缓存命中: {len(self._handicap_cache)} 条盘口数据")
        logger.info(f"")
        logger.info(f"📊 推荐统计:")
        logger.info(f"   总场次: {statistics.get('total', 0)}")
        logger.info(f"   推荐场次: {statistics.get('recommended', 0)}")
        logger.info(f"   不推荐: {statistics.get('no_bet', 0)}")
        logger.info(f"")
        logger.info(f"📈 推荐结果:")
        logger.info(f"   ✅ 全赢: {statistics.get('win', 0)}")
        logger.info(f"   ❌ 全输: {statistics.get('lose', 0)}")
        logger.info(f"   ✅ 半赢: {statistics.get('half_win', 0)}")
        logger.info(f"   ❌ 半输: {statistics.get('half_lose', 0)}")
        logger.info(f"   ➖ 走水: {statistics.get('draw', 0)}")
        logger.info(f"")
        logger.info(f"🎯 核心指标:")
        logger.info(f"   引擎胜率: {statistics.get('win_rate', 0):.1f}%")
        logger.info(f"   总盈利: {statistics.get('total_profit', 0):+.2f} 单位")
        logger.info(f"   ROI: {statistics.get('roi', 0):+.1f}%")
        logger.info(f"{'='*80}\n")
        
        return {
            'total': len(matches),
            'success': success_count,
            'failed': failed_count,
            'no_handicap': no_handicap_count,
            'results': results,
            'statistics': statistics
        }


# 模块导出
__all__ = ['BacktestEngine']
