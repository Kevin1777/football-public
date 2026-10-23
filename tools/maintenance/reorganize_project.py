#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目文件重组脚本

功能：
1. 创建新的目录结构
2. 移动文件到对应目录
3. 生成移动报告
4. 支持回滚

使用：
python reorganize_project.py --mode=plan    # 预览计划（不实际移动）
python reorganize_project.py --mode=execute # 执行移动
python reorganize_project.py --mode=rollback # 回滚
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
import argparse

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 移动计划
MOVE_PLAN = {
    # 核心应用
    "core": [
        "app.py",
        "version_config.py",
        "main_automation.py",
        "auto_recommend_push.py",
        "recommendation_tracker.py",
        "schedule_manager.py",
        "daily_review_scheduler.py",
    ],
    
    # 测试文件 - 单元测试
    "tests/unit": [
        "test_logs.py",
    ],
    
    # 测试文件 - 集成测试
    "tests/integration": [
        "test_x1_integration.py",
        "test_api_v2.py",
        "integration_example.py",
        "example_x1_usage.py",
        "test_recommendation_tracking.py",
        "test_all_push.py",
    ],
    
    # 测试文件 - 准确率测试
    "tests/accuracy": [
        "test_accuracy.py",
        "quick_accuracy_test.py",
        "final_accuracy_test.py",
        "backtest_x1_accuracy.py",
        "真实准确率回测.py",
        "查看真实准确率.py",
        "快速测试真实准确率.py",
        "test_x1_json_recommender.py",
    ],
    
    # 测试文件 - 验证测试
    "tests/validation": [
        "validate_model.py",
        "verify_v2.py",
        "test_current_v2.py",
        "严格验证无未来函数.py",
        "最终验证_比分隔离.py",
        "快速验证修复.py",
        "验证统一引擎.py",
    ],
    
    # 工具 - 分析
    "tools/analysis": [
        "analyze_failures.py",
        "analyze_winners.py",
        "分析回测结果.py",
        "分析最近回测.py",
        "成交额深度分析.py",
        "实时交易明细分析.py",
        "高级特征挖掘.py",
        "score_reverse_engineer.py",
    ],
    
    # 工具 - 优化
    "tools/optimization": [
        "optimize_model.py",
        "build_new_model.py",
        "优化推荐引擎.py",
        "V5深度优化分析.py",
        "实施分级阈值.py",
        "test_optimization.py",
        "对比测试_阈值方案.py",
        "全方案对比测试.py",
    ],
    
    # 工具 - 快速脚本
    "tools/quick_scripts": [
        "quick_collect_today.py",
        "quick_batch_test.py",
        "快速测试真实准确率.py",
        "快速验证修复.py",
    ],
    
    # 工具 - 调试
    "tools/debugging": [
        "debug_v2.py",
        "debug_missing_handicap.py",
        "调试公司ID.py",
        "诊断批量回测问题.py",
    ],
    
    # 工具 - 可视化
    "tools/visualization": [
        "visualize_x1_accuracy.py",
        "generate_x1_report.py",
        "daily_review_visualizer.py",
    ],
    
    # 工具 - 数据采集
    "tools/data_collection": [
        "auto_capture_links.py",
        "测试采集盘口.py",
        "测试盘口获取.py",
        "测试标盘指数.py",
    ],
    
    # 工具 - 其他
    "tools/others": [
        "rule_based_recommender.py",
        "api_x1_json_recommendation.py",
        "interactive_monitor.py",
        "organize_files.py",
        "final_url_test.py",
        "测试完场和实时.py",
        "测试批量回测日志.py",
        "测试未来比赛盘口.py",
        "增强批量回测.py",
        "批量回测本地数据.py",
        "重新分析回测结果.py",
    ],
    
    # 配置文件
    "config": [
        ".env.example",
        "requirements.txt",
        "requirements_full.txt",
        "wecom_config.json",
        "config.json",
    ],
    
    # Shell/Bat脚本
    "scripts/deployment": [
        "deploy_server.sh",
        "服务器快速部署.sh",
        "football.service",
    ],
    
    "scripts/automation": [
        "启动服务器.bat",
        "启动自动推送.bat",
        "quick_start.bat",
    ],
    
    "scripts/utilities": [
        "quick_test.bat",
        "立即测试准确率.sh",
        "快速修复脚本.bat",
    ],
    
    # 数据文件
    "data/models": [
        "V5增强特征.csv",
    ],
    
    "data/results": [
        "X1_准确率回测结果.json",
        "X1_测试详细结果.json",
        "x1_test_results.json",
        "真实准确率回测结果.json",
        "全方案对比结果.json",
        "test_result.txt",
    ],
    
    "data/cache": [
        "pre_match_history.json",
        "cookies.json",
        "captcha.png",
    ],
    
    # 文档 - 用户指南
    "docs/user_guides": [
        "QUICK_START.md",
        "X1_快速开始.md",
        "快速开始_优化版.md",
        "X1_JSON推荐模型使用说明.md",
        "X1_集成使用文档.md",
        "推荐记录和审查系统使用文档.md",
    ],
    
    # 文档 - 开发文档
    "docs/development": [
        "VERSION_UPDATE_GUIDE.md",
        "VERSION_QUICK_GUIDE.md",
        "README_系统优化总结.md",
        "README_日志系统.md",
        "README_推荐追踪系统.md",
        "操作日志使用说明.md",
        "X1_README.md",
        "X1_项目总结.md",
    ],
    
    # 文档 - 部署文档
    "docs/deployment": [
        "DEPLOYMENT.md",
        "✅服务器部署总结.md",
        "服务器部署检查报告.md",
        "无人值守功能检查报告.md",
        "无人运行改进建议.md",
        "系统优化完成说明.md",
    ],
    
    # 文档 - 变更日志
    "docs/changelogs": [
        "V2_MODEL_INTEGRATION.md",
        "X1_集成完成总结.md",
        "✅全系统统一引擎完成.md",
        "✅统一推荐引擎替换完成.md",
        "推荐引擎替换完成.md",
        "X1_JSON引擎统一替换完成.md",
        "完整推送测试功能集成完成.md",
        "推荐记录审查系统完成总结.md",
        "自动推送系统升级完成.md",
        "登录机制优化完成.md",
        "登录并发冲突修复完成.md",
    ],
    
    # 文档 - 报告
    "docs/reports": [
        "X1_准确率分析报告.md",
        "X1_测试报告.md",
        "X1_测试结果总结.md",
        "FINAL_V2_VERIFICATION.md",
        "回测真实性验证报告.md",
        "✅真实准确率测试结论.md",
        "全盘检查报告.md",
        "系统问题检查报告.md",
        "未来函数检查报告.md",
        "OPTIMIZATION_PLAN.md",
        "准确率提升方案.md",
        "扩大覆盖范围策略.md",
        "改进方案完整指南.md",
    ],
    
    # 文档 - 归档
    "docs/archived": [
        "✅修复Web回测准确率.md",
        "✅完整修复总结.md",
        "✅准确率提升实施.md",
        "✅日志系统增强.md",
        "✅最终方案确定.md",
        "✅最终解决方案.md",
        "✅策略1已实施.md",
        "✅路由修复完成.md",
        "✅重构完成.md",
        "✅问题解决_前端未调用API.md",
        "✅集成完成.md",
        "确认问题.md",
        "凌晨比赛盘口匹配修复.md",
        "盘口识别修复说明.md",
        "推送调度说明.md",
    ],
}

# 日志文件
MOVE_LOG_FILE = PROJECT_ROOT / "reorganize_log.json"


def create_directories():
    """创建所有目标目录"""
    print("=" * 80)
    print("📂 创建目录结构...")
    print("=" * 80)
    
    created = []
    for target_dir in MOVE_PLAN.keys():
        dir_path = PROJECT_ROOT / target_dir
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(target_dir)
            print(f"✅ 创建: {target_dir}")
    
    if not created:
        print("ℹ️  所有目录已存在")
    
    return created


def move_files(mode="plan"):
    """移动文件
    
    Args:
        mode: plan=预览, execute=执行
    """
    print("\n" + "=" * 80)
    print(f"📦 {'预览' if mode == 'plan' else '执行'}文件移动计划...")
    print("=" * 80)
    
    move_log = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "moves": []
    }
    
    total_files = sum(len(files) for files in MOVE_PLAN.values())
    current = 0
    
    for target_dir, files in MOVE_PLAN.items():
        print(f"\n📁 目标: {target_dir}")
        print("-" * 80)
        
        for filename in files:
            current += 1
            source = PROJECT_ROOT / filename
            dest = PROJECT_ROOT / target_dir / filename
            
            # 检查源文件是否存在
            if not source.exists():
                print(f"[{current}/{total_files}] ⏭️  跳过（不存在）: {filename}")
                continue
            
            # 检查目标是否已存在
            if dest.exists():
                print(f"[{current}/{total_files}] ⚠️  已存在: {filename}")
                continue
            
            # 记录移动
            move_info = {
                "source": str(source),
                "dest": str(dest),
                "timestamp": datetime.now().isoformat()
            }
            
            if mode == "execute":
                try:
                    # 确保目标目录存在
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # 移动文件
                    shutil.move(str(source), str(dest))
                    print(f"[{current}/{total_files}] ✅ 移动: {filename}")
                    move_info["status"] = "success"
                except Exception as e:
                    print(f"[{current}/{total_files}] ❌ 失败: {filename} - {e}")
                    move_info["status"] = "failed"
                    move_info["error"] = str(e)
            else:
                print(f"[{current}/{total_files}] 📋 计划: {filename} → {target_dir}")
                move_info["status"] = "planned"
            
            move_log["moves"].append(move_info)
    
    # 保存日志
    with open(MOVE_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(move_log, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 80)
    print(f"📊 统计:")
    print(f"  总文件数: {total_files}")
    print(f"  已处理: {current}")
    print(f"  日志文件: {MOVE_LOG_FILE}")
    print("=" * 80)
    
    return move_log


def rollback():
    """回滚移动操作"""
    print("=" * 80)
    print("🔙 执行回滚...")
    print("=" * 80)
    
    if not MOVE_LOG_FILE.exists():
        print("❌ 未找到移动日志文件")
        return
    
    with open(MOVE_LOG_FILE, 'r', encoding='utf-8') as f:
        log = json.load(f)
    
    success_count = 0
    fail_count = 0
    
    for move in log["moves"]:
        if move["status"] != "success":
            continue
        
        source = Path(move["dest"])
        dest = Path(move["source"])
        
        if source.exists():
            try:
                shutil.move(str(source), str(dest))
                print(f"✅ 恢复: {dest.name}")
                success_count += 1
            except Exception as e:
                print(f"❌ 失败: {dest.name} - {e}")
                fail_count += 1
    
    print("\n" + "=" * 80)
    print(f"📊 回滚统计:")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="项目文件重组工具")
    parser.add_argument(
        "--mode",
        choices=["plan", "execute", "rollback"],
        default="plan",
        help="运行模式：plan=预览, execute=执行, rollback=回滚"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🗂️  项目文件重组工具")
    print("=" * 80)
    print(f"模式: {args.mode}")
    print(f"根目录: {PROJECT_ROOT}")
    print()
    
    if args.mode == "rollback":
        rollback()
    else:
        create_directories()
        move_files(args.mode)
        
        if args.mode == "plan":
            print("\n💡 提示:")
            print("  这是预览模式，未实际移动文件")
            print("  使用 --mode=execute 执行实际移动")
        else:
            print("\n✅ 移动完成！")
            print("\n⚠️  重要提示:")
            print("  1. 检查应用是否正常运行")
            print("  2. 更新可能需要修改的import路径")
            print("  3. 如有问题，运行 --mode=rollback 回滚")


if __name__ == "__main__":
    main()
