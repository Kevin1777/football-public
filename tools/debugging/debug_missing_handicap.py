
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.lottery500_client import Lottery500Client

# Configure logging
logging.basicConfig(level=logging.INFO)

def debug_specific_match():
    client = Lottery500Client(data_dir="data")
    
    # Target match from screenshot
    home = "江原FC"
    away = "町田泽维亚"
    match_time = "18:00"
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🔍 正在调试特定比赛匹配...")
    print(f"   目标: {home} vs {away} @ {match_time}")
    
    # 1. Fetch daily data
    print(f"\n📥 1. 获取今日 ({date_str}) 所有盘口数据...")
    # Force fetch to ensure we have latest data
    daily_data = client.fetch_daily_handicaps(date_str, use_cache=False)
    
    if not daily_data:
        print("❌ 获取今日数据失败或为空")
        return

    print(f"✅ 获取成功，共 {len(daily_data)} 场比赛")
    
    # 2. Try standard matching
    print(f"\n🔄 2. 尝试标准匹配逻辑...")
    result = client.find_handicap_from_daily_data(
        daily_handicaps=daily_data,
        home_team=home,
        away_team=away,
        match_time=match_time
    )
    
    if result:
        print("\n✅ 匹配成功！")
        print(f"   500.com队名: {result['home_team']} vs {result['away_team']}")
        print(f"   盘口: {result['current_handicap_str']}")
    else:
        print("\n❌ 匹配失败！")
        print("   开始深入诊断...")
        
        # 3. Deep diagnosis - print close matches
        print(f"\n🔎 3. 寻找潜在候选比赛（时间相近或队名相似）...")
        
        candidates = []
        for key, data in daily_data.items():
            h = data['home_team']
            a = data['away_team']
            t = data['time']
            
            # Check time (allow +/- 1 hour)
            try:
                h_match, m_match = map(int, match_time.split(':'))
                h_data, m_data = map(int, t.split(':'))
                
                if abs(h_match - h_data) <= 1:
                    candidates.append(data)
                    continue
            except:
                pass
            
            # Check name similarity
            if home[0] in h or away[0] in a:
                 candidates.append(data)

        print(f"   找到 {len(candidates)} 个潜在候选：")
        for i, c in enumerate(candidates[:10], 1): # Show top 10
            print(f"   {i}. [{c['time']}] {c['home_team']} vs {c['away_team']} (盘口: {c.get('current_handicap_str')})")

if __name__ == "__main__":
    debug_specific_match()
