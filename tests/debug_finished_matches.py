import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录 to path
sys.path.append(str(Path(__file__).parent.parent))

from services.bifaw_client import BifawClient

def debug_finished_matches():
    client = BifawClient()
    target_date = datetime(2025, 11, 28)
    print(f"Fetching matches for {target_date.strftime('%Y-%m-%d')}...")
    
    _, matches, _ = client.fetch_finished_matches(target_date=target_date, rows=5)
    
    print(f"Found {len(matches)} matches")
    
    for i, match in enumerate(matches):
        print(f"Match {i+1}: {match.get('home')} vs {match.get('away')}")
        print(f"  ID: {match.get('match_id')}")
        print(f"  Detail URL: {match.get('detail_url')}")
        
        if not match.get('detail_url'):
            print("  ❌ ERROR: detail_url is missing!")
        else:
            print("  ✅ detail_url found")

if __name__ == "__main__":
    debug_finished_matches()
