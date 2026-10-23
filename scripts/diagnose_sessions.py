#!/usr/bin/env python3
"""
诊断历史会话不显示问题的脚本
在服务器上运行: python scripts/diagnose_sessions.py
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check_progress_dir():
    """检查 progress 目录"""
    print_section("1. 检查 progress 目录")
    
    progress_dir = ROOT_DIR / "progress"
    print(f"   预期路径: {progress_dir}")
    print(f"   路径存在: {progress_dir.exists()}")
    
    if progress_dir.exists():
        print(f"   是目录: {progress_dir.is_dir()}")
        
        # 列出所有 session 文件
        session_files = list(progress_dir.glob("session_*.json"))
        print(f"   会话文件数量: {len(session_files)}")
        
        if session_files:
            print("\n   会话文件列表:")
            for f in sorted(session_files, reverse=True)[:10]:
                size = f.stat().st_size
                print(f"     - {f.name} ({size} bytes)")
                
                # 尝试读取文件内容
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        status = data.get('status', 'unknown')
                        start_date = data.get('start_date', 'N/A')
                        end_date = data.get('end_date', 'N/A')
                        print(f"       状态: {status}, 日期: {start_date} ~ {end_date}")
                except Exception as e:
                    print(f"       ❌ 读取失败: {e}")
        else:
            print("   ❌ 没有找到会话文件!")
    else:
        print("   ❌ progress 目录不存在!")
        print(f"   尝试创建: {progress_dir}")
        try:
            progress_dir.mkdir(parents=True, exist_ok=True)
            print("   ✅ 目录已创建")
        except Exception as e:
            print(f"   ❌ 创建失败: {e}")

def check_log_dir():
    """检查 logs 目录"""
    print_section("2. 检查 logs 目录")
    
    logs_dir = ROOT_DIR / "logs"
    print(f"   预期路径: {logs_dir}")
    print(f"   路径存在: {logs_dir.exists()}")
    
    if logs_dir.exists():
        # 列出所有 session 日志文件
        log_files = list(logs_dir.glob("session_*.log"))
        print(f"   日志文件数量: {len(log_files)}")
        
        if log_files:
            print("\n   最近的日志文件:")
            for f in sorted(log_files, reverse=True)[:5]:
                size = f.stat().st_size
                print(f"     - {f.name} ({size} bytes)")
                
                # 尝试读取最后几行
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        lines = fp.readlines()
                        print(f"       行数: {len(lines)}")
                        if lines:
                            last_line = lines[-1].strip()
                            if len(last_line) > 80:
                                last_line = last_line[:80] + "..."
                            print(f"       最后一行: {last_line}")
                except Exception as e:
                    print(f"       ❌ 读取失败: {e}")
        else:
            print("   ⚠️ 没有找到日志文件")
    else:
        print("   ❌ logs 目录不存在!")

def check_progress_manager():
    """测试 ProgressManager"""
    print_section("3. 测试 ProgressManager")
    
    try:
        from backtest.progress_manager import ProgressManager
        pm = ProgressManager()
        
        print(f"   progress_dir: {pm.progress_dir}")
        print(f"   目录存在: {pm.progress_dir.exists()}")
        
        # 测试 list_sessions
        sessions = pm.list_sessions(limit=10)
        print(f"   list_sessions 返回数量: {len(sessions)}")
        
        if sessions:
            print("\n   会话列表:")
            for s in sessions[:5]:
                print(f"     - {s['session_id']}: {s['status']} ({s['start_date']} ~ {s['end_date']})")
        else:
            print("   ❌ 没有返回任何会话!")
            
    except Exception as e:
        print(f"   ❌ ProgressManager 测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_log_manager():
    """测试 LogManager"""
    print_section("4. 测试 LogManager")
    
    try:
        from backtest.log_manager import LogManager
        lm = LogManager(log_dir=str(ROOT_DIR / "logs"), max_messages=500)
        
        print(f"   log_dir: {lm.log_dir}")
        print(f"   目录存在: {lm.log_dir.exists()}")
        
        # 测试获取最近会话ID
        latest = lm.get_latest_session_id()
        print(f"   最近会话ID: {latest}")
        
        # 测试获取消息
        messages = lm.get_recent_messages(limit=10)
        print(f"   get_recent_messages 返回数量: {len(messages)}")
        
        if messages:
            print("\n   最近消息预览:")
            for msg in messages[-3:]:
                msg_type = msg.get('type', 'unknown')
                msg_text = msg.get('message', '')[:50]
                print(f"     - [{msg_type}] {msg_text}")
                
    except Exception as e:
        print(f"   ❌ LogManager 测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_file_permissions():
    """检查文件权限"""
    print_section("5. 检查文件权限")
    
    dirs_to_check = [
        ROOT_DIR / "progress",
        ROOT_DIR / "logs",
    ]
    
    for d in dirs_to_check:
        if d.exists():
            readable = os.access(d, os.R_OK)
            writable = os.access(d, os.W_OK)
            executable = os.access(d, os.X_OK)
            print(f"   {d.name}/: R={readable}, W={writable}, X={executable}")
        else:
            print(f"   {d.name}/: 不存在")

def simulate_api_call():
    """模拟 API 调用"""
    print_section("6. 模拟 API 调用")
    
    try:
        from backtest.progress_manager import ProgressManager
        from backtest.log_manager import LogManager
        
        pm = ProgressManager()
        lm = LogManager(log_dir=str(ROOT_DIR / "logs"), max_messages=500)
        
        # 模拟 /api/collect/sessions
        print("\n   模拟 /api/collect/sessions:")
        sessions = pm.list_sessions(limit=20)
        result = {
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
            "debug": {
                "progress_dir": str(pm.progress_dir),
                "dir_exists": pm.progress_dir.exists(),
                "session_files": [f.name for f in pm.progress_dir.glob("session_*.json")] if pm.progress_dir.exists() else []
            }
        }
        print(f"   返回 count: {result['count']}")
        print(f"   debug.progress_dir: {result['debug']['progress_dir']}")
        print(f"   debug.dir_exists: {result['debug']['dir_exists']}")
        print(f"   debug.session_files: {len(result['debug']['session_files'])} 个文件")
        
        # 模拟 /api/collect/logs
        print("\n   模拟 /api/collect/logs:")
        messages = lm.get_recent_messages(limit=100)
        active_session = lm.get_active_session_id()
        if not active_session:
            active_session = lm.get_latest_session_id()
        
        result2 = {
            "success": True,
            "messages": messages,
            "count": len(messages),
            "active_session": active_session,
            "is_running": lm.get_active_session_id() is not None
        }
        print(f"   返回 count: {result2['count']}")
        print(f"   active_session: {result2['active_session']}")
        print(f"   is_running: {result2['is_running']}")
        
    except Exception as e:
        print(f"   ❌ 模拟 API 失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("\n" + "🔍 历史会话诊断工具".center(60))
    print(f"项目根目录: {ROOT_DIR}")
    print(f"当前工作目录: {os.getcwd()}")
    
    check_progress_dir()
    check_log_dir()
    check_progress_manager()
    check_log_manager()
    check_file_permissions()
    simulate_api_call()
    
    print_section("诊断完成")
    print("""
   如果看到以下问题，对应解决方案：
   
   1. progress 目录不存在或为空
      → 确认上传时包含了 progress/ 目录
      → 或者服务器上还没有运行过采集任务
   
   2. 文件权限问题
      → chmod -R 755 progress/ logs/
   
   3. ProgressManager/LogManager 路径不对
      → 检查代码中的路径配置
   
   4. 模拟 API 返回 count=0
      → 说明没有会话文件，需要同步本地数据或运行采集
""")

if __name__ == "__main__":
    main()
