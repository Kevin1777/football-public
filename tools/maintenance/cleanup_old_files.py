#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
老旧文件清理工具

功能：
1. 识别老旧文件（超过N天未修改）
2. 识别重复文件（backup、old等）
3. 识别大文件（日志、缓存等）
4. 安全归档或删除

使用：
python cleanup_old_files.py --mode=scan      # 扫描老旧文件
python cleanup_old_files.py --mode=archive   # 归档老旧文件
python cleanup_old_files.py --mode=clean     # 清理指定文件
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import hashlib

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 配置
CONFIG = {
    # 文件老化阈值（天）
    "old_file_days": 90,  # 90天未修改视为老旧
    
    # 需要检查的目录
    "check_dirs": [
        "logs",
        "debug_html", 
        "backtest_results",
        "detail_cache",
        "data/cache",
        "data/results",
    ],
    
    # 自动归档的目录
    "auto_archive_dirs": [
        "analysis_backup",
        "config_backup",
        "docs_backup",
        "logs_backup",
        "scripts_backup",
        "tests_backup",
    ],
    
    # 需要清理的文件模式
    "cleanup_patterns": [
        "*.pyc",
        "__pycache__",
        "*.bak",
        "*.tmp",
        "*.temp",
        ".DS_Store",
        "Thumbs.db",
    ],
    
    # 大文件阈值（MB）
    "large_file_mb": 10,
    
    # 日志文件保留天数
    "log_retention_days": 30,
    
    # 归档目录
    "archive_dir": "archived/auto_cleanup",
}


class FileCleanupTool:
    """文件清理工具"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.archive_dir = self.project_root / CONFIG["archive_dir"]
        self.scan_results = {
            "old_files": [],
            "duplicate_dirs": [],
            "large_files": [],
            "cleanup_candidates": [],
            "total_size": 0,
        }
    
    def scan_old_files(self):
        """扫描老旧文件"""
        print("=" * 80)
        print("🔍 扫描老旧文件...")
        print("=" * 80)
        
        threshold_date = datetime.now() - timedelta(days=CONFIG["old_file_days"])
        
        for dir_name in CONFIG["check_dirs"]:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            print(f"\n📁 检查: {dir_name}")
            count = 0
            size = 0
            
            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue
                
                # 检查修改时间
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < threshold_date:
                    file_size = file_path.stat().st_size
                    self.scan_results["old_files"].append({
                        "path": str(file_path.relative_to(self.project_root)),
                        "size": file_size,
                        "mtime": mtime.isoformat(),
                        "days_old": (datetime.now() - mtime).days
                    })
                    count += 1
                    size += file_size
            
            if count > 0:
                print(f"  发现 {count} 个老旧文件，总大小 {size / 1024 / 1024:.2f} MB")
    
    def scan_backup_dirs(self):
        """扫描备份目录"""
        print("\n" + "=" * 80)
        print("🔍 扫描备份目录...")
        print("=" * 80)
        
        for dir_name in CONFIG["auto_archive_dirs"]:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            # 计算目录大小
            total_size = sum(
                f.stat().st_size 
                for f in dir_path.rglob("*") 
                if f.is_file()
            )
            
            file_count = sum(1 for _ in dir_path.rglob("*") if _.is_file())
            
            self.scan_results["duplicate_dirs"].append({
                "path": str(dir_path.relative_to(self.project_root)),
                "size": total_size,
                "files": file_count
            })
            
            print(f"📦 {dir_name}: {file_count} 个文件, {total_size / 1024 / 1024:.2f} MB")
    
    def scan_large_files(self):
        """扫描大文件"""
        print("\n" + "=" * 80)
        print("🔍 扫描大文件...")
        print("=" * 80)
        
        threshold_size = CONFIG["large_file_mb"] * 1024 * 1024
        
        for file_path in self.project_root.rglob("*"):
            if not file_path.is_file():
                continue
            
            # 跳过某些目录
            if any(p in str(file_path) for p in ['.git', '__pycache__', '.venv', 'node_modules']):
                continue
            
            file_size = file_path.stat().st_size
            if file_size > threshold_size:
                self.scan_results["large_files"].append({
                    "path": str(file_path.relative_to(self.project_root)),
                    "size": file_size,
                    "size_mb": file_size / 1024 / 1024
                })
        
        # 排序并显示
        self.scan_results["large_files"].sort(key=lambda x: x["size"], reverse=True)
        
        print(f"\n发现 {len(self.scan_results['large_files'])} 个大文件（>{CONFIG['large_file_mb']}MB）:")
        for item in self.scan_results["large_files"][:10]:  # 只显示前10个
            print(f"  📄 {item['path']}: {item['size_mb']:.2f} MB")
    
    def scan_cleanup_candidates(self):
        """扫描可清理文件"""
        print("\n" + "=" * 80)
        print("🔍 扫描可清理文件...")
        print("=" * 80)
        
        for pattern in CONFIG["cleanup_patterns"]:
            if pattern == "__pycache__":
                # 查找__pycache__目录
                for cache_dir in self.project_root.rglob("__pycache__"):
                    if cache_dir.is_dir():
                        size = sum(
                            f.stat().st_size 
                            for f in cache_dir.rglob("*") 
                            if f.is_file()
                        )
                        self.scan_results["cleanup_candidates"].append({
                            "path": str(cache_dir.relative_to(self.project_root)),
                            "type": "cache",
                            "size": size
                        })
            else:
                # 查找匹配模式的文件
                for file_path in self.project_root.rglob(pattern):
                    if file_path.is_file():
                        self.scan_results["cleanup_candidates"].append({
                            "path": str(file_path.relative_to(self.project_root)),
                            "type": "pattern",
                            "size": file_path.stat().st_size
                        })
        
        total_size = sum(item["size"] for item in self.scan_results["cleanup_candidates"])
        print(f"\n发现 {len(self.scan_results['cleanup_candidates'])} 个可清理文件")
        print(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    
    def generate_report(self):
        """生成扫描报告"""
        print("\n" + "=" * 80)
        print("📊 扫描报告")
        print("=" * 80)
        
        # 计算总大小
        total_size = 0
        total_size += sum(f["size"] for f in self.scan_results["old_files"])
        total_size += sum(d["size"] for d in self.scan_results["duplicate_dirs"])
        total_size += sum(f["size"] for f in self.scan_results["cleanup_candidates"])
        
        print(f"\n老旧文件: {len(self.scan_results['old_files'])} 个")
        print(f"备份目录: {len(self.scan_results['duplicate_dirs'])} 个")
        print(f"大文件: {len(self.scan_results['large_files'])} 个")
        print(f"可清理: {len(self.scan_results['cleanup_candidates'])} 个")
        print(f"\n可释放空间: {total_size / 1024 / 1024:.2f} MB")
        
        # 保存报告
        report_file = self.project_root / "cleanup_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                "scan_time": datetime.now().isoformat(),
                "results": self.scan_results,
                "total_size_mb": total_size / 1024 / 1024
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n报告已保存: {report_file}")
        
        return self.scan_results
    
    def archive_old_files(self, dry_run=True):
        """归档老旧文件"""
        print("\n" + "=" * 80)
        print(f"📦 {'预览' if dry_run else '执行'}归档操作...")
        print("=" * 80)
        
        if not self.scan_results["old_files"]:
            print("ℹ️  没有需要归档的文件")
            return
        
        # 创建归档目录
        archive_date = datetime.now().strftime("%Y%m%d")
        target_archive = self.archive_dir / f"old_files_{archive_date}"
        
        if not dry_run:
            target_archive.mkdir(parents=True, exist_ok=True)
        
        archived_count = 0
        archived_size = 0
        
        for item in self.scan_results["old_files"]:
            source = self.project_root / item["path"]
            if not source.exists():
                continue
            
            # 保持目录结构
            rel_path = Path(item["path"])
            dest = target_archive / rel_path
            
            if dry_run:
                print(f"  📋 将归档: {item['path']} ({item['size'] / 1024:.1f} KB)")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(dest))
                print(f"  ✅ 已归档: {item['path']}")
            
            archived_count += 1
            archived_size += item["size"]
        
        print(f"\n{'预计' if dry_run else '已'}归档 {archived_count} 个文件")
        print(f"{'预计' if dry_run else '已'}释放空间: {archived_size / 1024 / 1024:.2f} MB")
        
        if dry_run:
            print("\n💡 这是预览模式，使用 --execute 执行实际归档")
    
    def clean_backup_dirs(self, dry_run=True):
        """清理备份目录"""
        print("\n" + "=" * 80)
        print(f"🗑️  {'预览' if dry_run else '执行'}备份目录清理...")
        print("=" * 80)
        
        for item in self.scan_results["duplicate_dirs"]:
            dir_path = self.project_root / item["path"]
            if not dir_path.exists():
                continue
            
            if dry_run:
                print(f"  📋 将删除: {item['path']} ({item['size'] / 1024 / 1024:.2f} MB)")
            else:
                shutil.rmtree(dir_path)
                print(f"  ✅ 已删除: {item['path']}")
        
        if dry_run:
            print("\n💡 这是预览模式，使用 --execute 执行实际删除")
    
    def clean_temp_files(self, dry_run=True):
        """清理临时文件"""
        print("\n" + "=" * 80)
        print(f"🗑️  {'预览' if dry_run else '执行'}临时文件清理...")
        print("=" * 80)
        
        cleaned_count = 0
        cleaned_size = 0
        
        for item in self.scan_results["cleanup_candidates"]:
            file_path = self.project_root / item["path"]
            if not file_path.exists():
                continue
            
            if dry_run:
                print(f"  📋 将删除: {item['path']}")
            else:
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                print(f"  ✅ 已删除: {item['path']}")
            
            cleaned_count += 1
            cleaned_size += item["size"]
        
        print(f"\n{'预计' if dry_run else '已'}清理 {cleaned_count} 个文件/目录")
        print(f"{'预计' if dry_run else '已'}释放空间: {cleaned_size / 1024 / 1024:.2f} MB")
        
        if dry_run:
            print("\n💡 这是预览模式，使用 --execute 执行实际清理")


def main():
    parser = argparse.ArgumentParser(description="老旧文件清理工具")
    parser.add_argument(
        "--mode",
        choices=["scan", "archive", "clean", "full"],
        default="scan",
        help="运行模式：scan=扫描, archive=归档, clean=清理, full=完整清理"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行实际操作（默认为预览模式）"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="老旧文件阈值（天）"
    )
    
    args = parser.parse_args()
    
    # 更新配置
    CONFIG["old_file_days"] = args.days
    
    print("=" * 80)
    print("🧹 老旧文件清理工具")
    print("=" * 80)
    print(f"模式: {args.mode}")
    print(f"执行: {'是' if args.execute else '否（预览）'}")
    print(f"老化阈值: {args.days} 天")
    print()
    
    tool = FileCleanupTool()
    
    if args.mode in ["scan", "full"]:
        # 扫描所有类型
        tool.scan_old_files()
        tool.scan_backup_dirs()
        tool.scan_large_files()
        tool.scan_cleanup_candidates()
        tool.generate_report()
    
    if args.mode == "archive":
        # 先扫描，再归档
        tool.scan_old_files()
        tool.archive_old_files(dry_run=not args.execute)
    
    if args.mode == "clean":
        # 清理临时文件和备份目录
        tool.scan_cleanup_candidates()
        tool.scan_backup_dirs()
        tool.clean_temp_files(dry_run=not args.execute)
        tool.clean_backup_dirs(dry_run=not args.execute)
    
    if args.mode == "full" and args.execute:
        # 完整清理
        print("\n⚠️  即将执行完整清理，请确认！")
        confirm = input("输入 'YES' 确认: ")
        if confirm == "YES":
            tool.archive_old_files(dry_run=False)
            tool.clean_temp_files(dry_run=False)
            tool.clean_backup_dirs(dry_run=False)
            print("\n✅ 清理完成！")
        else:
            print("\n❌ 取消清理")


if __name__ == "__main__":
    main()
