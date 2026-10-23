#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度清理脚本 - 清理根目录杂乱文件
"""

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# 深度清理计划
CLEANUP_PLAN = {
    # 备份目录 -> archived/
    "backup_dirs": [
        "analysis_backup",
        "config_backup", 
        "docs_backup",
        "logs_backup",
        "scripts_backup",
        "tests_backup",
    ],
    
    # 临时文件 -> archived/temp/
    "temp_files": [
        "auto_recommend_push.log",
        "captcha.png",
        "cookies.json",
        "cleanup_report.json",
        "reorganize_log.json",
        "X1_可视化报告.html",
    ],
    
    # 空目录（直接删除）
    "empty_dirs": [
        "downloads",
        "temp_files",
        "visualization_output",
        "analysis_charts",
        "__pycache__",
    ],
    
    # 数据库文件 -> data/databases/
    "database_files": [
        "match_data.db",
        "recommendation_tracker.db",
    ],
    
    # 重组文档 -> docs/project/
    "project_docs": [
        "PROJECT_REORGANIZATION_PLAN.md",
        "README_REORGANIZATION.md",
        "REORGANIZATION_SUMMARY.md",
        "REORGANIZATION_UPDATE.md",
    ],
    
    # 其他文件 -> 相应目录
    "other_files": {
        "reorganize_project.py": "tools/maintenance/",
        "PDF": "docs/pdf/",
    }
}

def move_backup_dirs():
    """移动备份目录到archived/"""
    print("\n📦 移动备份目录...")
    target = PROJECT_ROOT / "archived" / "old_backups"
    target.mkdir(parents=True, exist_ok=True)
    
    for dir_name in CLEANUP_PLAN["backup_dirs"]:
        source = PROJECT_ROOT / dir_name
        if source.exists():
            dest = target / dir_name
            shutil.move(str(source), str(dest))
            print(f"  ✅ {dir_name} -> archived/old_backups/")

def move_temp_files():
    """移动临时文件到archived/temp/"""
    print("\n📄 移动临时文件...")
    target = PROJECT_ROOT / "archived" / "temp_files"
    target.mkdir(parents=True, exist_ok=True)
    
    for file_name in CLEANUP_PLAN["temp_files"]:
        source = PROJECT_ROOT / file_name
        if source.exists():
            dest = target / file_name
            shutil.move(str(source), str(dest))
            print(f"  ✅ {file_name} -> archived/temp_files/")

def delete_empty_dirs():
    """删除空目录"""
    print("\n🗑️  删除空目录...")
    for dir_name in CLEANUP_PLAN["empty_dirs"]:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path, ignore_errors=True)
            print(f"  ✅ 删除 {dir_name}")

def move_database_files():
    """移动数据库文件到data/databases/"""
    print("\n💾 移动数据库文件...")
    target = PROJECT_ROOT / "data" / "databases"
    target.mkdir(parents=True, exist_ok=True)
    
    for file_name in CLEANUP_PLAN["database_files"]:
        source = PROJECT_ROOT / file_name
        if source.exists():
            dest = target / file_name
            shutil.move(str(source), str(dest))
            print(f"  ✅ {file_name} -> data/databases/")

def move_project_docs():
    """移动项目文档到docs/project/"""
    print("\n📚 移动项目文档...")
    target = PROJECT_ROOT / "docs" / "project"
    target.mkdir(parents=True, exist_ok=True)
    
    for file_name in CLEANUP_PLAN["project_docs"]:
        source = PROJECT_ROOT / file_name
        if source.exists():
            dest = target / file_name
            shutil.move(str(source), str(dest))
            print(f"  ✅ {file_name} -> docs/project/")

def move_other_files():
    """移动其他文件"""
    print("\n📦 移动其他文件...")
    for file_name, target_dir in CLEANUP_PLAN["other_files"].items():
        source = PROJECT_ROOT / file_name
        if source.exists():
            target = PROJECT_ROOT / target_dir
            target.mkdir(parents=True, exist_ok=True)
            dest = target / file_name
            shutil.move(str(source), str(dest))
            print(f"  ✅ {file_name} -> {target_dir}")

def main():
    print("=" * 80)
    print("🧹 深度清理 - 清理根目录")
    print("=" * 80)
    
    move_backup_dirs()
    move_temp_files()
    move_database_files()
    move_project_docs()
    move_other_files()
    delete_empty_dirs()
    
    print("\n" + "=" * 80)
    print("✅ 深度清理完成！")
    print("=" * 80)
    print("\n根目录现在应该只包含：")
    print("  ✅ app.py, version_config.py")
    print("  ✅ README.md, .env, .gitignore")
    print("  ✅ 核心目录（core/, tests/, tools/, docs/, etc.）")
    print("=" * 80)

if __name__ == "__main__":
    main()
