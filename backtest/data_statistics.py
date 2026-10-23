"""
数据统计模块
统计采集数据的日期、数量、大小等信息
"""
import os
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

class DataStatistics:
    """数据统计器"""
    
    def __init__(self, data_dir: str = "data"):
        # 🔥 智能处理绝对路径和相对路径
        data_path = Path(data_dir)
        if data_path.is_absolute():
            self.data_dir = data_path
        else:
            self.data_dir = data_path.resolve()
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def scan_data_by_date(self) -> Dict:
        """
        按日期扫描数据目录
        
        Returns:
            {
                '2025': {
                    '11': {
                        '21': {
                            'files': [...],
                            'total_rows': 0,
                            'total_size': 0
                        }
                    }
                }
            }
        """
        result = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        
        # 扫描所有CSV文件
        for file_path in self.data_dir.rglob("*.csv"):
            try:
                # 从文件名提取日期
                file_name = file_path.stem
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', file_name)
                
                if not date_match:
                    continue
                
                year, month, day = date_match.groups()
                
                # 统计文件信息
                file_size = file_path.stat().st_size
                
                # 计算行数（快速估算）
                row_count = 0
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        row_count = sum(1 for line in f) - 1  # 减去表头
                except Exception:
                    row_count = 0
                
                # 提取比赛信息
                match_info = self._extract_match_info(file_name)
                
                # 初始化日期数据
                if day not in result[year][month]:
                    result[year][month][day] = {
                        'files': [],
                        'total_rows': 0,
                        'total_size': 0,
                        'file_count': 0
                    }
                
                # 添加文件信息
                result[year][month][day]['files'].append({
                    'name': file_path.name,
                    'path': str(file_path.relative_to(self.data_dir)),
                    'size': file_size,
                    'rows': row_count,
                    'match_info': match_info,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                
                # 累加统计
                result[year][month][day]['total_rows'] += row_count
                result[year][month][day]['total_size'] += file_size
                result[year][month][day]['file_count'] += 1
                
            except Exception as e:
                print(f"处理文件失败 {file_path}: {e}")
                continue
        
        return dict(result)
    
    def _extract_match_info(self, file_name: str) -> Dict:
        """
        从文件名提取比赛信息
        
        例如: 2025-11-21_利物浦_vs_曼城_1900.csv
        """
        parts = file_name.split('_')
        
        info = {
            'date': '',
            'home': '',
            'away': '',
            'time': '',
            'label': file_name
        }
        
        try:
            if len(parts) >= 4:
                info['date'] = parts[0]
                info['home'] = parts[1]
                # 找到 'vs' 的位置
                if 'vs' in parts:
                    vs_idx = parts.index('vs')
                    info['away'] = parts[vs_idx + 1] if vs_idx + 1 < len(parts) else ''
                    info['time'] = parts[vs_idx + 2].replace('.csv', '') if vs_idx + 2 < len(parts) else ''
                info['label'] = f"{info['home']} vs {info['away']} {info['time']}"
        except Exception:
            pass
        
        return info
    
    def get_daily_summary(self) -> List[Dict]:
        """
        获取每日统计摘要
        
        Returns:
            [
                {
                    'date': '2025-11-21',
                    'file_count': 3,
                    'total_rows': 122,
                    'total_size': 188416,
                    'size_mb': 0.18
                },
                ...
            ]
        """
        data = self.scan_data_by_date()
        summary = []
        
        for year in sorted(data.keys(), reverse=True):
            for month in sorted(data[year].keys(), reverse=True):
                for day in sorted(data[year][month].keys(), reverse=True):
                    day_data = data[year][month][day]
                    date_str = f"{year}-{month}-{day}"
                    
                    summary.append({
                        'date': date_str,
                        'file_count': day_data['file_count'],
                        'total_rows': day_data['total_rows'],
                        'total_size': day_data['total_size'],
                        'size_mb': round(day_data['total_size'] / 1024 / 1024, 2)
                    })
        
        return summary
    
    def get_date_details(self, date: str) -> Dict:
        """
        获取指定日期的详细信息
        
        Args:
            date: 日期字符串，如 '2025-11-21'
        
        Returns:
            {
                'date': '2025-11-21',
                'file_count': 3,
                'total_rows': 122,
                'total_size': 188416,
                'files': [...]
            }
        """
        data = self.scan_data_by_date()
        
        try:
            year, month, day = date.split('-')
            
            if year in data and month in data[year] and day in data[year][month]:
                day_data = data[year][month][day]
                return {
                    'date': date,
                    'file_count': day_data['file_count'],
                    'total_rows': day_data['total_rows'],
                    'total_size': day_data['total_size'],
                    'size_mb': round(day_data['total_size'] / 1024 / 1024, 2),
                    'files': sorted(day_data['files'], key=lambda x: x['name'])
                }
        except Exception as e:
            print(f"获取日期详情失败 {date}: {e}")
        
        return {
            'date': date,
            'file_count': 0,
            'total_rows': 0,
            'total_size': 0,
            'size_mb': 0,
            'files': []
        }
    
    def get_tree_structure(self) -> Dict:
        """
        获取树形结构
        
        Returns:
            {
                'name': 'data',
                'type': 'folder',
                'children': [
                    {
                        'name': '2025',
                        'type': 'folder',
                        'children': [...]
                    }
                ]
            }
        """
        data = self.scan_data_by_date()
        
        tree = {
            'name': 'data',
            'type': 'folder',
            'children': []
        }
        
        for year in sorted(data.keys(), reverse=True):
            year_node = {
                'name': year,
                'type': 'folder',
                'children': []
            }
            
            for month in sorted(data[year].keys(), reverse=True):
                month_node = {
                    'name': f"{month}月",
                    'type': 'folder',
                    'children': []
                }
                
                for day in sorted(data[year][month].keys(), reverse=True):
                    day_data = data[year][month][day]
                    day_node = {
                        'name': f"{day}日 ({day_data['file_count']}场)",
                        'type': 'folder',
                        'date': f"{year}-{month}-{day}",
                        'stats': {
                            'file_count': day_data['file_count'],
                            'total_rows': day_data['total_rows'],
                            'size_mb': round(day_data['total_size'] / 1024 / 1024, 2)
                        },
                        'children': [
                            {
                                'name': f['name'],
                                'type': 'file',
                                'path': f['path'],
                                'size': f['size'],
                                'rows': f['rows'],
                                'match_info': f['match_info']
                            }
                            for f in day_data['files']
                        ]
                    }
                    month_node['children'].append(day_node)
                
                year_node['children'].append(month_node)
            
            tree['children'].append(year_node)
        
        return tree
