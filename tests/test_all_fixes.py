"""完整测试所有修复"""
from datetime import datetime
from services import BifawClient
from parser.html_parser import parse_bifa_html
import pandas as pd

print("="*80)
print("🧪 完场回查明细提取完整测试")
print("="*80)

client = BifawClient()

# 测试1: 获取完场比赛列表
print("\n【测试1】获取完场比赛列表")
print("-"*80)
matches = client.fetch_finished_matches(target_date=datetime(2025, 11, 5), rows=5)

if not matches:
    print("❌ 未找到比赛，测试终止")
    exit(1)

print(f"✅ 找到 {len(matches)} 场比赛")
first_match = matches[0]
print(f"\n选择第一场比赛进行测试：")
print(f"  联赛: {first_match.get('league')}")
print(f"  主队: {first_match.get('home')}")
print(f"  客队: {first_match.get('away')}")
print(f"  比分: {first_match.get('score')}")
print(f"  时间: {first_match.get('kickoff')}")
print(f"  URL: {first_match.get('detail_url')}")

# 测试2: 抓取明细HTML
print("\n【测试2】抓取明细HTML")
print("-"*80)
try:
    html = client.fetch_match_detail_selenium(
        detail_url=first_match.get('detail_url'),
        match=first_match,
        detail_params=first_match.get('detail_params')
    )
    print(f"✅ HTML抓取成功，长度: {len(html)} 字符")
except Exception as e:
    print(f"❌ HTML抓取失败: {e}")
    exit(1)

# 测试3: 解析HTML（传入match参数）
print("\n【测试3】解析HTML（使用match参数）")
print("-"*80)
try:
    result = parse_bifa_html(html, match=first_match)
    
    if isinstance(result, str):
        print(f"❌ 解析失败: {result}")
        exit(1)
    
    if not isinstance(result, pd.DataFrame):
        print(f"❌ 返回类型错误: {type(result)}")
        exit(1)
    
    print(f"✅ 解析成功，返回DataFrame")
    print(f"   数据维度: {result.shape[0]} 行 × {result.shape[1]} 列")
    
except Exception as e:
    print(f"❌ 解析异常: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 测试4: 验证元数据
print("\n【测试4】验证元数据")
print("-"*80)
if hasattr(result, 'attrs') and 'metadata' in result.attrs:
    metadata = result.attrs['metadata']
    print(f"✅ 找到metadata，数量: {len(metadata)}")
    
    if len(metadata) != 1:
        print(f"⚠️  元数据数量异常（应该只有1个）: {len(metadata)}")
    
    for i, meta in enumerate(metadata, 1):
        title_meta = meta.get('title_meta', {})
        league = title_meta.get('league')
        datetime_str = title_meta.get('datetime')
        home = title_meta.get('home')
        away = title_meta.get('away')
        
        print(f"\n  元数据 {i}:")
        print(f"    联赛: {league}")
        print(f"    时间: {datetime_str}")
        print(f"    主队: {home}")
        print(f"    客队: {away}")
        
        # 验证元数据是否正确
        issues = []
        if not league or league == '未知联赛':
            issues.append("联赛信息缺失")
        if not datetime_str or datetime_str == '未知时间':
            issues.append("时间信息缺失")
        if not home or '?' in str(home):
            issues.append("主队信息缺失")
        if not away or '?' in str(away):
            issues.append("客队信息缺失")
        
        if issues:
            print(f"    ⚠️  问题: {', '.join(issues)}")
        else:
            print(f"    ✅ 元数据完整")
else:
    print("❌ 没有找到metadata")

# 测试5: 验证列名
print("\n【测试5】验证列名（检查是否包含数据值）")
print("-"*80)
columns = result.columns.tolist()
print(f"列名数量: {len(columns)}")
print(f"前10个列名: {columns[:10]}")

# 检查列名中是否包含数字（说明数据被当作列名）
import re
numeric_columns = [col for col in columns if re.search(r'^\d+[,\d]*$', str(col))]
if numeric_columns:
    print(f"❌ 发现数字列名（数据被当作表头）: {numeric_columns[:5]}")
else:
    print(f"✅ 列名正确，没有数字列名")

# 检查是否有标准列名
standard_columns = ['成交时间', '价位', '买家挂牌', '成交量', '赔率']
found_standard = [col for col in standard_columns if col in columns or any(col in str(c) for c in columns)]
if found_standard:
    print(f"✅ 找到标准列名: {found_standard}")
else:
    print(f"⚠️  未找到标准列名")

# 测试6: 验证数据完整性
print("\n【测试6】验证数据完整性")
print("-"*80)
print(f"总行数: {len(result)}")

# 检查NaN比例
nan_count = result.isna().sum().sum()
total_cells = result.shape[0] * result.shape[1]
nan_ratio = nan_count / total_cells if total_cells > 0 else 0

print(f"NaN单元格数: {nan_count} / {total_cells} ({nan_ratio*100:.1f}%)")

if nan_ratio > 0.5:
    print(f"⚠️  NaN比例过高，可能解析有问题")
else:
    print(f"✅ NaN比例正常")

# 检查是否有完全空的行
empty_rows = result.isna().all(axis=1).sum()
if empty_rows > 0:
    print(f"⚠️  发现 {empty_rows} 行完全为空")
else:
    print(f"✅ 没有完全空的行")

# 测试7: 查看前几行数据
print("\n【测试7】查看前5行数据样本")
print("-"*80)
print(result.head(5).to_string())

# 测试8: 检查成交时间列
print("\n【测试8】检查成交时间列")
print("-"*80)
time_cols = [col for col in columns if '时间' in str(col) or 'time' in str(col).lower()]
if time_cols:
    print(f"找到时间列: {time_cols}")
    time_col = time_cols[0]
    time_values = result[time_col].dropna()
    if len(time_values) > 0:
        print(f"时间数据样本:")
        for i, val in enumerate(time_values.head(5), 1):
            print(f"  {i}. {val}")
        
        # 检查时间格式
        time_pattern = re.compile(r'\d{2}-\d{2}\s+\d{2}:\d{2}')
        valid_times = time_values.apply(lambda x: bool(time_pattern.search(str(x)))).sum()
        print(f"✅ 有效时间格式: {valid_times} / {len(time_values)}")
    else:
        print(f"⚠️  时间列为空")
else:
    print(f"⚠️  未找到时间列")

# 最终总结
print("\n" + "="*80)
print("📋 测试总结")
print("="*80)

passed = []
failed = []

# 检查各项测试结果
if len(matches) > 0:
    passed.append("✅ 比赛列表获取")
else:
    failed.append("❌ 比赛列表获取")

if len(html) > 0:
    passed.append("✅ HTML抓取")
else:
    failed.append("❌ HTML抓取")

if isinstance(result, pd.DataFrame):
    passed.append("✅ DataFrame解析")
else:
    failed.append("❌ DataFrame解析")

if hasattr(result, 'attrs') and 'metadata' in result.attrs and len(result.attrs['metadata']) == 1:
    passed.append("✅ 元数据正确（1个）")
else:
    failed.append("❌ 元数据异常")

if not numeric_columns:
    passed.append("✅ 列名不包含数据")
else:
    failed.append("❌ 列名包含数据值")

if nan_ratio < 0.5:
    passed.append("✅ NaN比例正常")
else:
    failed.append("❌ NaN比例过高")

if empty_rows == 0:
    passed.append("✅ 无空行")
else:
    failed.append("❌ 有空行")

print("\n通过的测试:")
for item in passed:
    print(f"  {item}")

if failed:
    print("\n失败的测试:")
    for item in failed:
        print(f"  {item}")
    print(f"\n❌ 测试未完全通过（{len(passed)}/{len(passed)+len(failed)}）")
else:
    print(f"\n🎉 所有测试通过！（{len(passed)}/{len(passed)}）")

print("\n" + "="*80)
print("测试完成！")
print("="*80)
