"""
本地明细数据缓存管理器

功能：
1. 保存采集的交易明细到本地JSON文件
2. 从本地缓存读取明细（避免重复抓取）
3. 管理缓存文件（查询、清理、统计）
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class DetailCacheManager:
    """明细数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "data"):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径（可以是绝对路径或相对于项目根目录的相对路径）
        """
        # 🔥 智能处理绝对路径和相对路径
        cache_path = Path(cache_dir)
        if cache_path.is_absolute():
            # 如果是绝对路径，直接使用
            self.cache_dir = cache_path
        else:
            # 如果是相对路径，拼接到项目根目录
            self.cache_dir = Path(__file__).parent.parent / cache_dir
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"明细缓存目录: {self.cache_dir}")
    
    def _generate_cache_key(self, match_info: Dict) -> Tuple[str, str]:
        """
        生成缓存文件的日期和文件名
        
        Args:
            match_info: 比赛信息字典
            
        Returns:
            (date_str, filename): 日期字符串和文件名
            格式：("2025-11-18", "英超_利物浦_vs_曼城_0400")
        """
        # 🔥 提取日期（使用 or 逻辑，与大小球保持一致）
        kickoff = match_info.get('kickoff', '') or match_info.get('match_time', '')
        if ' ' in str(kickoff):
            date_str = kickoff.split(' ')[0]  # YYYY-MM-DD
            time_str = kickoff.split(' ')[1].replace(':', '')[:4]  # HHMM
        else:
            # 🔥 优先使用 kickoff_date，然后是 query_date，最后才是当前日期
            date_str = match_info.get('kickoff_date', '') or match_info.get('query_date', '') or datetime.now().strftime("%Y-%m-%d")
            time_str = str(kickoff).replace(':', '')[:4] if kickoff else ""
        
        # 🔥 提取队伍名（使用 or 逻辑，与大小球保持一致）
        home = match_info.get('home', '') or match_info.get('home_team', '') or 'H'
        away = match_info.get('away', '') or match_info.get('away_team', '') or 'A'
        league = match_info.get('league', '') or match_info.get('league_name', '') or ''
        
        # 清理特殊字符
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
            home = home.replace(char, '_')
            away = away.replace(char, '_')
            league = league.replace(char, '_')
        
        # 🔥 提取比分
        score = match_info.get('score', '')
        score_str = ''
        if score:
            # 清理比分中的特殊字符
            score_clean = score.replace(' ', '').replace('-', '_')
            score_str = f"_{score_clean}"
        
        # 🔥 构造文件名：日期_时间_联赛_主队_vs_客队_比分（新格式）
        if league:
            filename = f"{date_str}_{time_str}_{league}_{home}_vs_{away}{score_str}"
        else:
            filename = f"{date_str}_{time_str}_{home}_vs_{away}{score_str}"
        
        logger.info(f"🔑 生成缓存键: {date_str} / {filename}")
        logger.info(f"  原始数据: kickoff={match_info.get('kickoff', match_info.get('match_time'))}, home={match_info.get('home', match_info.get('home_team'))}, away={match_info.get('away', match_info.get('away_team'))}, score={match_info.get('score', '')}")
        
        return date_str, filename
    
    def _get_cache_filepath(self, date_str: str, filename: str, ext: str = "json") -> Path:
        """
        获取缓存文件路径
        
        Args:
            date_str: 日期字符串 YYYY-MM-DD
            filename: 文件名（不包含扩展名）
            ext: 扩展名，默认json
        """
        # 新结构：data/YYYY/MM/DD/文件名.ext
        try:
            year, month, day = date_str.split("-")
            date_dir = self.cache_dir / year / month / day
        except ValueError:
            # 兜底：无法拆分就退回一层目录
            date_dir = self.cache_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir / f"{filename}.{ext}"
    
    def has_cache(self, match_info: Dict) -> bool:
        """
        检查比赛是否有缓存
        
        Args:
            match_info: 比赛信息字典
            
        Returns:
            True=有缓存, False=无缓存
        """
        date_str, filename = self._generate_cache_key(match_info)
        filepath = self._get_cache_filepath(date_str, filename, "json")
        
        # 检查新结构（带比分）
        if filepath.exists():
            logger.info(f"✅ 缓存命中(新-带比分): {filepath}")
            return True
        
        # 兼容旧结构：data/YYYY-MM-DD/文件名.json（带比分）
        legacy_dir = self.cache_dir / date_str
        legacy_path = legacy_dir / f"{filename}.json"
        if legacy_path.exists():
            logger.info(f"✅ 缓存命中(旧-带比分): {legacy_path}")
            return True
        
        # 🔥 如果有比分，尝试查找无比分版本
        if match_info.get('score'):
            logger.info(f"  🔍 有比分字段: {match_info.get('score')}，尝试查找无比分版本...")
            # 临时移除比分再生成文件名
            match_info_no_score = match_info.copy()
            match_info_no_score.pop('score', None)
            date_str_no_score, filename_no_score = self._generate_cache_key(match_info_no_score)
            filepath_no_score = self._get_cache_filepath(date_str_no_score, filename_no_score, "json")
            
            logger.info(f"  🔍 无比分文件名: {filename_no_score}")
            
            # 检查无比分版本
            if filepath_no_score.exists():
                logger.info(f"✅ 缓存命中(无比分版本): {filepath_no_score}")
                return True
            
            # 兼容旧结构无比分版本
            legacy_path_no_score = legacy_dir / f"{filename_no_score}.json"
            if legacy_path_no_score.exists():
                logger.info(f"✅ 缓存命中(旧-无比分版本): {legacy_path_no_score}")
                return True
        
        logger.info(f"❌ 无缓存: {filepath}")
        logger.info(f"  查找过的文件: {filepath}, {legacy_path}")
        return False
    
    def get_ou_filepath(self, match_info: Dict) -> Path:
        """
        获取大小球明细文件路径（与标盘文件配对）
        
        Args:
            match_info: 比赛信息字典
            
        Returns:
            大小球明细文件的完整路径
        """
        date_str, filename = self._generate_cache_key(match_info)
        return self._get_cache_filepath(date_str, f"{filename}_大小球明细", "json")
    
    def has_ou_cache(self, match_info: Dict) -> bool:
        """
        检查比赛是否有大小球明细缓存
        
        Args:
            match_info: 比赛信息字典
            
        Returns:
            True=有缓存, False=无缓存
        """
        # 检查新结构
        ou_filepath = self.get_ou_filepath(match_info)
        if ou_filepath.exists():
            return True
        
        # 🔥 兼容旧结构和无比分版本
        date_str, filename = self._generate_cache_key(match_info)
        
        # 旧结构：data/YYYY-MM-DD/文件名_大小球明细.json
        legacy_dir = self.cache_dir / date_str
        legacy_path = legacy_dir / f"{filename}_大小球明细.json"
        if legacy_path.exists():
            return True
        
        # 如果有比分，尝试查找无比分版本
        if match_info.get('score'):
            match_info_no_score = match_info.copy()
            match_info_no_score.pop('score', None)
            date_str_no_score, filename_no_score = self._generate_cache_key(match_info_no_score)
            
            # 新结构无比分版本
            filepath_no_score = self._get_cache_filepath(date_str_no_score, f"{filename_no_score}_大小球明细", "json")
            if filepath_no_score.exists():
                return True
            
            # 旧结构无比分版本
            legacy_path_no_score = legacy_dir / f"{filename_no_score}_大小球明细.json"
            if legacy_path_no_score.exists():
                return True
        
        return False
    
    def save_detail(
        self,
        match_info: Dict,
        trade_data: pd.DataFrame,
        handicap_data: Optional[Dict] = None,
        metadata: Optional[list] = None,
        html_content: Optional[str] = None,
        ou_trade_data: Optional[Dict] = None  # 🔥 新增：大小球交易明细
    ) -> bool:
        """
        保存明细数据到缓存（JSON + HTML）
        
        Args:
            match_info: 比赛信息
            trade_data: 交易明细DataFrame（标盘/欧赔）
            handicap_data: 让球盘口数据（可选）
            metadata: 元数据列表（可选）
            html_content: 原始HTML内容（可选）
            ou_trade_data: 大小球交易明细数据（可选）
            
        Returns:
            True=保存成功, False=保存失败
        """
        try:
            date_str, filename = self._generate_cache_key(match_info)
            json_filepath = self._get_cache_filepath(date_str, filename, "json")
            html_filepath = self._get_cache_filepath(date_str, filename, "html")
            
            # 🔥 构造缓存数据（确保包含比分）
            cache_data = {
                "date": date_str,
                "filename": filename,
                "match_info": match_info,  # 已包含score字段
                "handicap_data": handicap_data or {},
                "trade_data": {
                    "columns": trade_data.columns.tolist(),
                    "data": trade_data.to_dict(orient='records'),
                    "shape": list(trade_data.shape),
                },
                "ou_trade_data": ou_trade_data or {},  # 🔥 大小球交易明细
                "metadata": metadata or [],
                "cached_at": datetime.now().isoformat(),
            }
            
            # 保存JSON文件
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 🔥 不再保存HTML文件（已优化：只保存JSON即可）
            # if html_content:
            #     try:
            #         with open(html_filepath, 'w', encoding='utf-8') as f:
            #             f.write(html_content)
            #         logger.debug(f"✅ 已保存HTML: {html_filepath.name}")
            #     except Exception as html_err:
            #         logger.warning(f"⚠️  HTML保存失败: {html_err}")
            
            logger.info(f"✅ 已缓存明细: {date_str}/{filename} ({trade_data.shape[0]}行)")
            return True
            
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False
    
    def load_detail(
        self,
        match_info: Dict
    ) -> Optional[Tuple[pd.DataFrame, Dict, list]]:
        """
        从缓存加载明细数据
        
        Args:
            match_info: 比赛信息
            
        Returns:
            (trade_data, handicap_data, metadata) 或 None（无缓存）
        """
        try:
            date_str, filename = self._generate_cache_key(match_info)
            filepath = self._get_cache_filepath(date_str, filename, "json")
            
            if not filepath.exists():
                # 兼容旧结构：data/YYYY-MM-DD/文件名.json
                legacy_dir = self.cache_dir / date_str
                legacy_path = legacy_dir / f"{filename}.json"
                
                if not legacy_path.exists():
                    # 🔥 如果有比分，尝试查找无比分版本
                    if match_info.get('score'):
                        match_info_no_score = match_info.copy()
                        match_info_no_score.pop('score', None)
                        date_str_no_score, filename_no_score = self._generate_cache_key(match_info_no_score)
                        filepath_no_score = self._get_cache_filepath(date_str_no_score, filename_no_score, "json")
                        
                        if filepath_no_score.exists():
                            logger.info(f"✅ 使用无比分版本: {filepath_no_score}")
                            filepath = filepath_no_score
                        else:
                            # 兼容旧结构无比分版本
                            legacy_path_no_score = legacy_dir / f"{filename_no_score}.json"
                            if legacy_path_no_score.exists():
                                logger.info(f"✅ 使用无比分版本(旧): {legacy_path_no_score}")
                                filepath = legacy_path_no_score
                            else:
                                logger.info(f"❌ 无比分版本也不存在: {filepath_no_score}, {legacy_path_no_score}")
                                return None
                    else:
                        return None
                else:
                    filepath = legacy_path
            
            # 读取缓存文件
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 重建DataFrame
            trade_dict = cache_data.get('trade_data', {})
            trade_df = pd.DataFrame(trade_dict.get('data', []))
            
            # 恢复metadata
            metadata = cache_data.get('metadata', [])
            if metadata:
                trade_df.attrs['metadata'] = metadata
            
            handicap_data = cache_data.get('handicap_data', {})
            
            # 🔥 恢复大小球交易明细（如果有）
            ou_trade_data = cache_data.get('ou_trade_data', {})
            if ou_trade_data:
                trade_df.attrs['ou_trade_data'] = ou_trade_data
            
            logger.info(f"从缓存加载: {date_str}/{filename} ({len(trade_df)}行)")
            return trade_df, handicap_data, metadata
            
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            return None
    
    def get_cache_info(self, match_info: Dict) -> Optional[Dict]:
        """
        获取缓存信息（不加载完整数据）
        
        Args:
            match_info: 比赛信息
            
        Returns:
            缓存信息字典或None
        """
        try:
            date_str, filename = self._generate_cache_key(match_info)
            filepath = self._get_cache_filepath(date_str, filename, "json")
            
            if not filepath.exists():
                # 兼容旧结构：data/YYYY-MM-DD/文件名.json
                legacy_dir = self.cache_dir / date_str
                legacy_path = legacy_dir / f"{filename}.json"
                if not legacy_path.exists():
                    return None
                filepath = legacy_path
            
            # 只读取基本信息
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return {
                'cache_key': f"{date_str}/{filename}",
                'date': date_str,
                'filename': filename,
                'cached_at': cache_data.get('cached_at'),
                'rows': cache_data.get('trade_data', {}).get('shape', [0])[0],
                'file_size': filepath.stat().st_size,
            }
            
        except Exception as e:
            logger.error(f"获取缓存信息失败: {e}")
            return None
    
    def delete_cache(self, match_info: Dict) -> bool:
        """
        删除指定比赛的缓存
        
        Args:
            match_info: 比赛信息
            
        Returns:
            True=删除成功, False=删除失败或不存在
        """
        try:
            date_str, filename = self._generate_cache_key(match_info)
            json_path = self._get_cache_filepath(date_str, filename, "json")
            html_path = self._get_cache_filepath(date_str, filename, "html")
            
            # 兼容旧结构路径
            legacy_dir = self.cache_dir / date_str
            legacy_json = legacy_dir / f"{filename}.json"
            legacy_html = legacy_dir / f"{filename}.html"
            
            deleted = False
            for path in [json_path, html_path, legacy_json, legacy_html]:
                if path.exists():
                    try:
                        path.unlink()
                        deleted = True
                    except Exception:
                        continue
            
            if deleted:
                logger.info(f"已删除缓存: {date_str}/{filename}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return False
    
    def delete_by_cache_key(self, cache_key: str) -> bool:
        """根据 cache_key 删除缓存文件（支持新旧目录结构）"""
        try:
            if "/" not in cache_key:
                return False
            date_str, filename = cache_key.split("/", 1)
            json_path = self._get_cache_filepath(date_str, filename, "json")
            html_path = self._get_cache_filepath(date_str, filename, "html")
            legacy_dir = self.cache_dir / date_str
            legacy_json = legacy_dir / f"{filename}.json"
            legacy_html = legacy_dir / f"{filename}.html"
            deleted = False
            for path in [json_path, html_path, legacy_json, legacy_html]:
                if path.exists():
                    try:
                        path.unlink()
                        deleted = True
                    except Exception:
                        continue
            if deleted:
                logger.info(f"已删除缓存: {date_str}/{filename}")
            return deleted
        except Exception as e:
            logger.error(f"根据cache_key删除缓存失败: {e}")
            return False
    
    def list_all_caches(self) -> list:
        """
        列出所有缓存文件
        
        Returns:
            缓存文件列表，每项包含基本信息
        """
        caches = []
        
        # 遍历 data 目录下的所有缓存文件
        for top_dir in self.cache_dir.iterdir():
            if not top_dir.is_dir():
                continue
            name = top_dir.name
            # 跳过非缓存目录
            if name in {"handicaps", "details", "cache"}:
                continue
            
            # 新结构：data/YYYY/MM/DD
            if len(name) == 4 and name.isdigit():  # 年份目录
                for month_dir in top_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        date_label = f"{top_dir.name}-{month_dir.name}-{day_dir.name}"
                        for filepath in day_dir.glob("*.json"):
                            try:
                                if filepath.name == "盘口数据.json":
                                    continue
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    cache_data = json.load(f)
                                caches.append({
                                    'date': date_label,
                                    'filename': filepath.stem,
                                    'cache_key': f"{date_label}/{filepath.stem}",
                                    'match_label': cache_data.get('match_info', {}).get('label', ''),
                                    'cached_at': cache_data.get('cached_at'),
                                    'rows': cache_data.get('trade_data', {}).get('shape', [0])[0],
                                    'file_size': filepath.stat().st_size,
                                    'filepath': str(filepath),
                                })
                            except Exception:
                                continue
            # 旧结构：data/YYYY-MM-DD
            elif len(name) == 10 and name[4] == "-" and name[7] == "-":
                for filepath in top_dir.glob("*.json"):
                    try:
                        if filepath.name == "盘口数据.json":
                            continue
                        with open(filepath, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        caches.append({
                            'date': top_dir.name,
                            'filename': filepath.stem,
                            'cache_key': f"{top_dir.name}/{filepath.stem}",
                            'match_label': cache_data.get('match_info', {}).get('label', ''),
                            'cached_at': cache_data.get('cached_at'),
                            'rows': cache_data.get('trade_data', {}).get('shape', [0])[0],
                            'file_size': filepath.stat().st_size,
                            'filepath': str(filepath),
                        })
                    except Exception:
                        continue
        
        return caches
    
    def get_statistics(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        caches = self.list_all_caches()
        
        total_size = sum(c['file_size'] for c in caches)
        total_rows = sum(c['rows'] for c in caches)
        
        return {
            'total_files': len(caches),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'total_rows': total_rows,
            'cache_dir': str(self.cache_dir),
        }
    
    def clear_all_caches(self) -> int:
        """
        清空所有缓存
        
        Returns:
            删除的文件数量
        """
        count = 0
        
        # 遍历 data 目录下所有缓存文件
        for top_dir in self.cache_dir.iterdir():
            if not top_dir.is_dir():
                continue
            name = top_dir.name
            if name in {"handicaps", "details", "cache"}:
                continue
            
            # 新结构：data/YYYY/MM/DD
            if len(name) == 4 and name.isdigit():
                for month_dir in top_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        for filepath in day_dir.glob("*"):
                            if filepath.is_file() and filepath.name not in {"盘口数据.json", "盘口数据.html"}:
                                try:
                                    filepath.unlink()
                                    count += 1
                                except Exception:
                                    continue
            # 旧结构：data/YYYY-MM-DD
            elif len(name) == 10 and name[4] == "-" and name[7] == "-":
                for filepath in top_dir.glob("*"):
                    if filepath.is_file() and filepath.name not in {"盘口数据.json", "盘口数据.html"}:
                        try:
                            filepath.unlink()
                            count += 1
                        except Exception:
                            continue
        
        logger.info(f"已清空所有缓存: {count}个文件")
        return count


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    manager = DetailCacheManager()
    
    # 测试保存和加载
    test_match = {
        'home': '测试主队',
        'away': '测试客队',
        'kickoff': '11-19 21:00',
        'label': '11-19 21:00 测试联赛 测试主队 vs 测试客队'
    }
    
    test_df = pd.DataFrame({
        '成交时间': ['21:00', '21:05'],
        '主胜': [1.5, 1.6],
    })
    
    # 保存
    success = manager.save_detail(test_match, test_df)
    print(f"保存结果: {success}")
    
    # 检查
    has_cache = manager.has_cache(test_match)
    print(f"是否有缓存: {has_cache}")
    
    # 加载
    result = manager.load_detail(test_match)
    if result:
        df, handicap, metadata = result
        print(f"加载结果: {len(df)}行")
    
    # 统计
    stats = manager.get_statistics()
    print(f"统计信息: {stats}")
