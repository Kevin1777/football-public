"""
从本地盘口数据.html文件中提取比分

功能：
1. 扫描现有的JSON比赛文件
2. 读取同目录下的盘口数据.html
3. 从HTML中提取比分
4. 更新JSON文件并重命名

使用方法：
python scripts/extract_scores_from_html.py [--dry-run] [--limit N]
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
import argparse
from bs4 import BeautifulSoup

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.detail_cache_manager import DetailCacheManager


def extract_score_from_html(html_content: str, home_team: str, away_team: str, fid: str = None) -> Optional[str]:
    """
    从HTML中提取比分
    
    Args:
        html_content: HTML内容
        home_team: 主队名
        away_team: 客队名
        fid: 比赛ID（可选）
    
    Returns:
        比分字符串，如 "2-1"，或 None
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 方法1：如果有fid，直接查找对应行
        if fid:
            row = soup.find('tr', id=f'a{fid}')
            if row:
                # 查找比分列（通常在class="bf"的td中）
                bf_td = row.find('td', class_='bf')
                if bf_td:
                    score_text = bf_td.get_text(strip=True)
                    # 匹配 "数字-数字" 格式
                    match = re.search(r'(\d+)-(\d+)', score_text)
                    if match:
                        return match.group(0)
        
        # 方法2：通过队名查找
        # HTML结构示例：<a ... title="主队名">主队名</a> ... <span class="bf">2-1</span> ... <a ... title="客队名">客队名</a>
        
        # 清理队名（去除空格等）
        home_clean = home_team.strip().replace(' ', '')
        away_clean = away_team.strip().replace(' ', '')
        
        # 查找所有比赛行
        rows = soup.find_all('tr', id=lambda x: x and x.startswith('a'))
        
        for row in rows:
            row_text = row.get_text()
            row_html = str(row)
            
            # 检查队名是否匹配
            if home_clean in row_text and away_clean in row_text:
                # 查找比分（多种可能的class）
                for bf_class in ['bf', 'score', 'bifen']:
                    bf_elem = row.find(class_=bf_class)
                    if bf_elem:
                        score_text = bf_elem.get_text(strip=True)
                        match = re.search(r'(\d+)-(\d+)', score_text)
                        if match:
                            return match.group(0)
                
                # 如果没有找到class，尝试直接匹配比分格式
                match = re.search(r'(\d+)-(\d+)', row_text)
                if match:
                    # 验证是否真的是比分（不是日期、时间等）
                    score_candidate = match.group(0)
                    numbers = score_candidate.split('-')
                    if all(int(n) < 20 for n in numbers):  # 比分一般不会超过20
                        return score_candidate
        
        # 方法3：正则匹配整个HTML（最后尝试）
        # 查找包含队名的行，然后提取附近的比分
        pattern = rf'{re.escape(home_clean)}.*?(\d+)-(\d+).*?{re.escape(away_clean)}'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        
        return None
        
    except Exception as e:
        print(f"  ⚠️  解析HTML失败: {e}")
        return None


def process_single_file(
    json_file: Path,
    cache_manager: DetailCacheManager,
    dry_run: bool = False
) -> bool:
    """处理单个JSON文件，从HTML提取比分"""
    try:
        print(f"\n{'='*80}")
        print(f"处理: {json_file.name}")
        print(f"{'='*80}")
        
        # 读取JSON数据
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        match_info = data.get('match_info', {})
        home = match_info.get('home', '')
        away = match_info.get('away', '')
        
        # 检查是否已有比分
        existing_score = match_info.get('score')
        if existing_score:
            print(f"  ℹ️  已有比分: {existing_score}")
            
            # 检查文件名是否包含比分
            score_in_name = existing_score.replace('-', '_')
            if score_in_name in json_file.name:
                print(f"  ✅ 文件名已包含比分，跳过")
                return True
            else:
                print(f"  🔄 文件名需要更新")
                new_score = existing_score
        else:
            # 查找同目录下的盘口数据.html
            html_file = json_file.parent / "盘口数据.html"
            
            if not html_file.exists():
                print(f"  ⚠️  未找到HTML文件: {html_file.name}")
                return False
            
            # 读取HTML
            print(f"  📂 读取HTML: {html_file.name}")
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            # 提取比分
            handicap_data = data.get('handicap_data', {})
            fid = handicap_data.get('fid')
            
            print(f"  🔍 查找比分: {home} vs {away}" + (f" (fid={fid})" if fid else ""))
            score = extract_score_from_html(html_content, home, away, fid)
            
            if not score:
                print(f"  ❌ 未找到比分")
                return False
            
            print(f"  ✅ 找到比分: {score}")
            new_score = score
            
            # 更新match_info
            match_info['score'] = new_score
        
        # 保存（会自动重命名）
        if dry_run:
            print(f"  🔥 [模拟] 将保存新文件（包含比分: {new_score}）")
            return True
        else:
            # 重新读取trade_data
            import pandas as pd
            trade_data = pd.DataFrame(data['trade_data']['data'])
            
            # 保存（会自动生成包含比分的文件名）
            success = cache_manager.save_detail(
                match_info=match_info,
                trade_data=trade_data,
                handicap_data=data.get('handicap_data'),
                metadata=data.get('metadata'),
                html_content=None
            )
            
            if success:
                print(f"  ✅ 保存成功")
                
                # 删除旧文件（如果文件名不同）
                score_str = new_score.replace('-', '_')
                if score_str not in json_file.name:
                    try:
                        json_file.unlink()
                        print(f"  🗑️  删除旧文件: {json_file.name}")
                    except Exception as e:
                        print(f"  ⚠️  删除旧文件失败: {e}")
                
                return True
            else:
                print(f"  ❌ 保存失败")
                return False
        
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='从HTML文件提取比分并更新JSON')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际修改文件')
    parser.add_argument('--limit', type=int, default=None, help='限制处理数量')
    parser.add_argument('--date', type=str, help='指定日期 YYYY-MM-DD')
    
    args = parser.parse_args()
    
    # 初始化
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return
    
    print(f"\n{'='*80}")
    print(f"从HTML文件提取比分")
    print(f"{'='*80}")
    print(f"数据目录: {data_dir}")
    print(f"模拟运行: {args.dry_run}")
    print(f"{'='*80}\n")
    
    # 扫描文件
    print("📂 扫描现有文件...")
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        # 只处理比赛文件
        if json_file.stem.startswith(('2025-', '2024-')):
            # 排除已经有比分的文件（文件名包含 _数字_数字_）
            if not re.search(r'_\d+_\d+_\d{4}\.json$', json_file.name):
                json_files.append(json_file)
    
    print(f"✅ 找到 {len(json_files)} 个需要处理的文件\n")
    
    if not json_files:
        print("❌ 没有需要处理的文件")
        return
    
    # 过滤日期
    if args.date:
        json_files = [f for f in json_files if args.date in f.name]
        print(f"🔍 筛选日期 {args.date}: {len(json_files)} 个文件\n")
    
    # 限制数量
    if args.limit:
        json_files = json_files[:args.limit]
        print(f"🔍 限制数量: {len(json_files)} 个文件\n")
    
    # 初始化缓存管理器
    cache_manager = DetailCacheManager(cache_dir=data_dir.parent)
    
    # 统计
    stats = {
        'total': len(json_files),
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    # 处理文件
    for i, json_file in enumerate(json_files, 1):
        print(f"\n[{i}/{stats['total']}] ", end='')
        
        result = process_single_file(
            json_file=json_file,
            cache_manager=cache_manager,
            dry_run=args.dry_run
        )
        
        if result:
            stats['success'] += 1
        else:
            stats['failed'] += 1
    
    # 生成报告
    print(f"\n{'='*80}")
    print(f"处理完成")
    print(f"{'='*80}")
    print(f"总计: {stats['total']}")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
