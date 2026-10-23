"""最终测试完场回查功能"""
from datetime import datetime
from services import BifawClient

def test():
    client = BifawClient()
    
    # 测试11月16日
    print("\n" + "="*60)
    print("测试完场回查功能 - 2025-11-16")
    print("="*60 + "\n")
    
    matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 16))
    
    print(f"✅ 找到 {len(matches)} 场完场比赛\n")
    
    if matches:
        print("前5场比赛详情：\n")
        for i, match in enumerate(matches[:5], 1):
            print(f"{i}. {match.get('label')}")
            print(f"   联赛: {match.get('league')}")
            print(f"   比分: {match.get('score')}")
            print(f"   主队: {match.get('home')} vs 客队: {match.get('away')}")
            print(f"   详情链接: {match.get('detail_url')[:60]}...")
            print()

if __name__ == "__main__":
    test()
