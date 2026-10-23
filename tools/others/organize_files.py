"""
文件整理脚本 - 根据类型自动分类整理项目文件

执行前会先备份，可安全使用
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 目标文件夹结构
FOLDERS = {
    'docs_backup': '文档备份（MD文件）',
    'logs_backup': '日志备份（LOG文件）',
    'tests_backup': '测试脚本备份',
    'analysis_backup': '分析脚本备份',
    'backtest_results': '回测结果备份',
    'temp_files': '临时文件备份',
    'config_backup': '配置文件备份',
    'scripts_backup': '工具脚本备份'
}

# 文件分类规则
FILE_RULES = {
    'docs_backup': {
        'extensions': ['.md'],
        'exclude': ['README.md', 'QUICK_START.md']  # 保留主要文档在根目录
    },
    'logs_backup': {
        'extensions': ['.log'],
        'patterns': []
    },
    'tests_backup': {
        'patterns': ['test_*.py', 'quick_test*.py', 'batch_*test*.py'],
        'exclude': []
    },
    'analysis_backup': {
        'patterns': ['analyze*.py', 'visualize*.py', '分析*.py', '诊断*.py', 
                    '深度分析*.py', '极致准确率*.py', '交易明细*.py'],
        'exclude': []
    },
    'backtest_results': {
        'patterns': ['backtest_result_*.log', 'backtest_result_*.json', 
                    'backtest_详细结果_*.json', '*_test_results*.json'],
        'exclude': []
    },
    'temp_files': {
        'patterns': ['temp_*.py', 'captcha*.png', 'reverse_engineer_*.log',
                    'batch_test_results_*.json'],
        'exclude': []
    },
    'config_backup': {
        'extensions': ['.json', '.ini', '.txt'],
        'exclude': ['requirements.txt', 'requirements_full.txt', '.env', 
                   '.env.example', '.gitignore', 'README.md']
    },
    'scripts_backup': {
        'patterns': ['check_*.py', 'fix_*.py', 'update_*.py', 'trigger_*.py',
                    'setup_*.py', 'manage_*.py', 'extract_*.py', 'debug_*.py',
                    '补充*.py', '应用*.py', '验证*.py', '采集*.py'],
        'exclude': []
    }
}


def should_move_file(file_path: Path, rule: dict) -> bool:
    """判断文件是否应该移动"""
    filename = file_path.name
    
    # 检查排除列表
    if filename in rule.get('exclude', []):
        return False
    
    # 检查扩展名
    if 'extensions' in rule:
        if file_path.suffix in rule['extensions']:
            return True
    
    # 检查模式匹配
    if 'patterns' in rule:
        import fnmatch
        for pattern in rule['patterns']:
            if fnmatch.fnmatch(filename, pattern):
                return True
    
    return False


def organize_files(dry_run=True):
    """
    整理文件
    
    Args:
        dry_run: 如果为True，只显示将要移动的文件，不实际移动
    """
    print("=" * 80)
    print("📂 文件整理工具")
    print("=" * 80)
    print()
    
    if dry_run:
        print("🔍 预览模式（不会实际移动文件）")
    else:
        print("⚠️  实际执行模式（将移动文件）")
        print()
        print("💡 提示：如果遇到文件占用错误，请先停止正在运行的应用")
    print()
    
    # 创建目标文件夹
    for folder, desc in FOLDERS.items():
        folder_path = ROOT_DIR / folder
        if not dry_run and not folder_path.exists():
            folder_path.mkdir(parents=True)
            print(f"✅ 创建文件夹: {folder} ({desc})")
    
    print()
    print("-" * 80)
    print()
    
    # 统计
    stats = {folder: [] for folder in FOLDERS.keys()}
    skipped_files = []  # 被占用跳过的文件
    
    # 扫描根目录下的文件
    for item in ROOT_DIR.iterdir():
        # 跳过目录
        if item.is_dir():
            continue
        
        # 跳过关键文件
        if item.name in ['app.py', 'auto_recommend_push.py', 'rule_based_recommender.py',
                         'organize_files.py', 'requirements.txt', 'requirements_full.txt',
                         '.env', '.env.example', '.gitignore', 
                         'README.md', 'QUICK_START.md', 'DEPLOYMENT.md']:
            continue
        
        # 检查每个分类规则
        moved = False
        for folder, rule in FILE_RULES.items():
            if should_move_file(item, rule):
                target_path = ROOT_DIR / folder / item.name
                
                if not dry_run:
                    # 如果目标文件已存在，添加时间戳
                    if target_path.exists():
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        stem = target_path.stem
                        suffix = target_path.suffix
                        target_path = target_path.parent / f"{stem}_{timestamp}{suffix}"
                    
                    # 尝试移动文件，如果被占用则跳过
                    try:
                        shutil.move(str(item), str(target_path))
                        stats[folder].append(item.name)  # 移动成功后添加到统计
                    except PermissionError:
                        print(f"⚠️  跳过（文件正在使用）: {item.name}")
                        skipped_files.append(item.name)
                        moved = True  # 标记已处理，避免重复匹配
                        break
                else:
                    # 预览模式直接添加到统计
                    stats[folder].append(item.name)
                
                moved = True
                break
    
    # 显示结果
    total_files = 0
    for folder, files in stats.items():
        if files:
            total_files += len(files)
            print(f"📁 {folder} ({FOLDERS[folder]})")
            print(f"   文件数: {len(files)}")
            if len(files) <= 10:
                for f in files[:10]:
                    print(f"   - {f}")
            else:
                for f in files[:5]:
                    print(f"   - {f}")
                print(f"   ... 还有 {len(files) - 5} 个文件")
            print()
    
    print("-" * 80)
    print(f"📊 总计: {total_files} 个文件")
    
    # 显示跳过的文件
    if skipped_files:
        print()
        print(f"⚠️  跳过的文件（{len(skipped_files)}个）：")
        for f in skipped_files:
            print(f"   - {f}")
    
    print()
    
    if dry_run:
        print("💡 确认无误后，请使用以下命令实际执行：")
        print(f"   python organize_files.py --execute")
    else:
        print("✅ 文件整理完成！")
        print()
        
        if skipped_files:
            print("💡 处理跳过的文件：")
            print("   1. 停止正在运行的应用")
            print("   2. 手动移动跳过的文件到对应文件夹")
            print("   3. 或者再次运行此脚本")
            print()
        
        print("📝 保留在根目录的重要文件:")
        print("   - app.py (主应用)")
        print("   - auto_recommend_push.py (自动推送)")
        print("   - rule_based_recommender.py (规则引擎)")
        print("   - requirements.txt (依赖)")
        print("   - README.md (说明文档)")
        print("   - .env (环境配置)")


if __name__ == '__main__':
    import sys
    
    # 检查是否执行模式
    if '--execute' in sys.argv or '-e' in sys.argv:
        response = input("⚠️  确认要移动文件吗？(yes/no): ")
        if response.lower() == 'yes':
            organize_files(dry_run=False)
        else:
            print("❌ 已取消")
    else:
        # 默认预览模式
        organize_files(dry_run=True)
