"""
重新获取完场比赛数据并保存（包含比分）

功能：
1. 扫描现有的比赛数据文件
2. 从必发网重新获取比赛信息（包含比分）
3. 重新保存数据，文件名包含比分
4. 生成详细报告

使用方法：
python scripts/rebuild_data_with_scores.py [--date YYYY-MM-DD] [--all]
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient
from backtest.detail_cache_manager import DetailCacheManager


def scan_existing_files(data_dir: Path) -> List[Path]:
    """扫描现有的比赛数据文件"""
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        # 只处理比赛文件，排除盘口数据文件
        if json_file.name.match(r'^\d{4}-\d{2}-\d{2}_'):
            json_files.append(json_file)
    return json_files


def extract_match_info(json_file: Path) -> Optional[Dict]:
    """从JSON文件提取比赛信息"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('match_info', {})
    except Exception as e:
        print(f"⚠️  读取文件失败 {json_file.name}: {e}")
        return None


def find_match_with_score(
    bifaw_client: BifawClient,
    match_info: Dict,
    target_date: datetime
) -> Optional[Dict]:
    """从必发网查找比赛并获取比分"""
    try:
        print(f"  🔍 查询比赛: {match_info.get('home')} vs {match_info.get('away')}")
        
        # 获取当天的完场比赛列表
        matches = bifaw_client.fetch_finished_matches(target_date=target_date)
        
        # 匹配比赛
        home = match_info.get('home', '')
        away = match_info.get('away', '')
        
        for match in matches:
            if (match.get('home') == home and match.get('away') == away):
                score = match.get('score')
                if score:
                    print(f"  ✅ 找到比分: {score}")
                    return match
                else:
                    print(f"  ⚠️  找到比赛但无比分")
                    return match
        
        print(f"  ❌ 未找到匹配的比赛")
        return None
        
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return None


def rebuild_single_file(
    json_file: Path,
    bifaw_client: BifawClient,
    cache_manager: DetailCacheManager,
    dry_run: bool = False
) -> bool:
    """重建单个文件（添加比分并重命名）"""
    try:
        print(f"\n{'='*80}")
        print(f"处理文件: {json_file.name}")
        print(f"{'='*80}")
        
        # 读取现有数据
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        match_info = data.get('match_info', {})
        kickoff = match_info.get('kickoff', '')
        
        if not kickoff:
            print(f"⚠️  跳过：无开球时间")
            return False
        
        # 解析日期
        try:
            target_date = datetime.strptime(kickoff.split()[0], "%Y-%m-%d")
        except Exception as e:
            print(f"⚠️  日期解析失败: {e}")
            return False
        
        # 检查是否已有比分
        existing_score = match_info.get('score')
        if existing_score:
            print(f"  ℹ️  已有比分: {existing_score}")
            
            # 检查文件名是否包含比分
            if existing_score.replace('-', '_') in json_file.name:
                print(f"  ✅ 文件名已包含比分，跳过")
                return True
            else:
                print(f"  🔄 文件名需要更新")
                # 直接更新文件名（数据中已有比分）
                new_info = match_info.copy()
        else:
            # 从必发网查询比分
            matched = find_match_with_score(bifaw_client, match_info, target_date)
            
            if not matched:
                print(f"  ⚠️  跳过：未找到比赛")
                return False
            
            # 更新比赛信息（添加比分）
            new_info = match_info.copy()
            new_info['score'] = matched.get('score', '')
            
            if not new_info['score']:
                print(f"  ⚠️  跳过：比赛无比分")
                return False
        
        # 重新保存（文件名会包含比分）
        if dry_run:
            print(f"  🔥 [模拟] 将保存新文件（包含比分）")
            print(f"     比分: {new_info['score']}")
            return True
        else:
            # 重新读取trade_data和其他字段
            import pandas as pd
            trade_data = pd.DataFrame(data['trade_data']['data'])
            
            # 设置attrs（用于保持元数据）
            if data.get('metadata'):
                trade_data.attrs['metadata'] = data['metadata']
            
            # 保存（会自动生成包含比分的文件名）
            success = cache_manager.save_detail(
                match_info=new_info,
                trade_data=trade_data,
                handicap_data=data.get('handicap_data'),
                metadata=data.get('metadata'),
                html_content=None  # HTML文件不需要重新保存
            )
            
            if success:
                print(f"  ✅ 保存成功")
                
                # 删除旧文件（如果文件名不同）
                date_str = target_date.strftime("%Y-%m-%d")
                score_str = new_info['score'].replace(' ', '').replace('-', '_')
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
    parser = argparse.ArgumentParser(description='重新获取比赛数据并添加比分')
    parser.add_argument('--date', type=str, help='指定日期 YYYY-MM-DD（默认处理所有）')
    parser.add_argument('--all', action='store_true', help='处理所有文件')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际修改文件')
    parser.add_argument('--limit', type=int, default=None, help='限制处理数量')
    
    args = parser.parse_args()
    
    # 初始化
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "2025"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return
    
    print(f"\n{'='*80}")
    print(f"重新获取比赛数据并添加比分")
    print(f"{'='*80}")
    print(f"数据目录: {data_dir}")
    print(f"模拟运行: {args.dry_run}")
    print(f"{'='*80}\n")
    
    # 扫描文件
    print("📂 扫描现有文件...")
    json_files = []
    for json_file in data_dir.rglob("*.json"):
        # 只处理比赛文件，排除盘口数据文件
        if json_file.stem.startswith(('2025-', '2024-')):
            json_files.append(json_file)
    
    print(f"✅ 找到 {len(json_files)} 个比赛文件\n")
    
    if not json_files:
        print("❌ 没有找到比赛文件")
        return
    
    # 过滤日期
    if args.date:
        json_files = [f for f in json_files if args.date in f.name]
        print(f"🔍 筛选日期 {args.date}: {len(json_files)} 个文件\n")
    
    # 限制数量
    if args.limit:
        json_files = json_files[:args.limit]
        print(f"🔍 限制数量: {len(json_files)} 个文件\n")
    
    # 初始化客户端
    bifaw_client = BifawClient()
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
        
        result = rebuild_single_file(
            json_file=json_file,
            bifaw_client=bifaw_client,
            cache_manager=cache_manager,
            dry_run=args.dry_run
        )
        
        if result:
            stats['success'] += 1
        elif result is False:
            stats['failed'] += 1
        else:
            stats['skipped'] += 1
    
    # 生成报告
    print(f"\n{'='*80}")
    print(f"处理完成")
    print(f"{'='*80}")
    print(f"总计: {stats['total']}")
    print(f"成功: {stats['success']}")
    print(f"失败: {stats['failed']}")
    print(f"跳过: {stats['skipped']}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
