"""测试元数据修复"""
from parser.html_parser import parse_bifa_html

# 模拟一个包含多个表格的HTML
test_html = """
<html>
<head><title>巴西甲,圣保罗,弗拉门戈,标盘明细</title></head>
<body>
<table>
    <tr><td>成交时间</td><td>赔率</td></tr>
    <tr><td>10:00</td><td>1.5</td></tr>
</table>
<table>
    <tr><td>成交时间</td><td>赔率</td></tr>
    <tr><td>10:05</td><td>1.6</td></tr>
</table>
</body>
</html>
"""

# 测试：传入match参数
match_info = {
    "league": "巴西甲",
    "kickoff": "2025-11-06 08:30",
    "home": "圣保罗",
    "away": "弗拉门戈",
    "score": "2-2"
}

print("="*70)
print("测试元数据修复")
print("="*70)

result = parse_bifa_html(test_html, match=match_info)

if hasattr(result, 'attrs') and 'metadata' in result.attrs:
    metadata = result.attrs['metadata']
    print(f"\n✅ 解析成功！")
    print(f"📊 数据行数: {len(result)}")
    print(f"📋 元数据数量: {len(metadata)}")
    
    if len(metadata) == 1:
        print(f"✅ 元数据数量正确（只有1个）")
    else:
        print(f"❌ 元数据数量错误（有{len(metadata)}个，应该只有1个）")
    
    print(f"\n元数据内容:")
    for i, meta in enumerate(metadata, 1):
        title_meta = meta.get('title_meta', {})
        print(f"  {i}. 联赛: {title_meta.get('league')}")
        print(f"     时间: {title_meta.get('datetime')}")
        print(f"     主队: {title_meta.get('home')}")
        print(f"     客队: {title_meta.get('away')}")
else:
    print("❌ 解析失败或没有metadata")

print("\n" + "="*70)
print("测试完成！")
print("="*70)
print("\n修复说明:")
print("- 修复前：每个表格section都会添加一个metadata，导致重复")
print("- 修复后：只添加一次metadata，避免重复显示")
print("\n现在刷新网页重新测试完场回查的抓取明细功能")
