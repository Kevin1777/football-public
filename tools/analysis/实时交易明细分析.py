"""
实时交易明细分析 - 在回测过程中分析每一笔交易
目标：既要场数多，又要准确率高
"""

import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import json
from pathlib import Path

# 导入回测引擎
sys.path.insert(0, str(Path(__file__).parent))
from 数据抓取与缓存管理 import get_cached_detail, load_handicap_from_cache

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def analyze_trade_detail_features(trade_data):
    """
    深度分析交易明细的动态特征
    
    返回:
        特征字典
    """
    if trade_data is None or len(trade_data) == 0:
        return {}
    
    features = {}
    
    # 总行数
    total_rows = len(trade_data)
    features['total_rows'] = total_rows
    
    # 时间分段（早期30%、中期40%、晚期30%）
    early_end = int(total_rows * 0.3)
    mid_end = int(total_rows * 0.7)
    
    early_data = trade_data.iloc[:early_end]
    mid_data = trade_data.iloc[early_end:mid_end]
    late_data = trade_data.iloc[mid_end:]
    
    # 1. 成交额分析
    try:
        # 尝试不同的列名
        volume_col = None
        for col in ['成交额', '成交量', '金额', 'volume', 'amount']:
            if col in trade_data.columns:
                volume_col = col
                break
        
        if volume_col:
            def parse_vol(v):
                try:
                    return float(str(v).replace(',', ''))
                except:
                    return 0
            
            volumes = trade_data[volume_col].apply(parse_vol)
            
            # 各阶段平均成交额
            early_vol = early_data[volume_col].apply(parse_vol).mean() if len(early_data) > 0 else 0
            mid_vol = mid_data[volume_col].apply(parse_vol).mean() if len(mid_data) > 0 else 0
            late_vol = late_data[volume_col].apply(parse_vol).mean() if len(late_data) > 0 else 0
            
            features['early_avg_volume'] = early_vol
            features['mid_avg_volume'] = mid_vol
            features['late_avg_volume'] = late_vol
            
            # 成交额趋势
            if early_vol > 0:
                features['volume_trend'] = late_vol / early_vol
            else:
                features['volume_trend'] = 1.0
            
            # 大额交易（>平均2倍）
            avg_vol = volumes.mean()
            if avg_vol > 0:
                big_trades = volumes[volumes > avg_vol * 2]
                features['big_trade_count'] = len(big_trades)
                features['big_trade_ratio'] = len(big_trades) / total_rows
                
                # 大额交易在哪个阶段
                if len(big_trades) > 0:
                    big_in_early = sum(1 for i, v in enumerate(volumes) if v > avg_vol * 2 and i < early_end)
                    big_in_late = sum(1 for i, v in enumerate(volumes) if v > avg_vol * 2 and i >= mid_end)
                    
                    features['big_early_ratio'] = big_in_early / len(big_trades)
                    features['big_late_ratio'] = big_in_late / len(big_trades)
    except Exception as e:
        pass
    
    # 2. 水位/价格分析
    try:
        price_cols = []
        for col in ['主队赔率', '客队赔率', '主队水位', '客队水位', '主水', '客水']:
            if col in trade_data.columns:
                price_cols.append((col, '主' if '主' in col else '客'))
        
        for col, side in price_cols:
            def parse_price(p):
                try:
                    return float(p)
                except:
                    return 0
            
            prices = trade_data[col].apply(parse_price)
            
            # 价格波动
            features[f'{side}_price_volatility'] = prices.std() if len(prices) > 1 else 0
            
            # 价格趋势
            if len(early_data) > 0 and len(late_data) > 0:
                early_price = early_data[col].apply(parse_price).mean()
                late_price = late_data[col].apply(parse_price).mean()
                
                if early_price > 0:
                    features[f'{side}_price_change_pct'] = (late_price - early_price) / early_price
            
            # 价格单调性（持续上升/下降）
            price_diff = prices.diff()
            if len(price_diff) > 1:
                up_count = (price_diff > 0).sum()
                down_count = (price_diff < 0).sum()
                
                features[f'{side}_monotonic_score'] = abs(up_count - down_count) / len(price_diff)
    except Exception as e:
        pass
    
    # 3. 交易节奏分析
    try:
        # 分10个时间窗口
        if total_rows >= 10:
            window_size = total_rows // 10
            window_counts = []
            
            for i in range(10):
                start = i * window_size
                end = start + window_size if i < 9 else total_rows
                window_counts.append(end - start)
            
            # 计算变异系数（CV）
            window_counts = np.array(window_counts)
            if window_counts.mean() > 0:
                features['trade_rhythm_cv'] = window_counts.std() / window_counts.mean()
            
            # 后期加速度（最后30%的交易密度）
            late_density = len(late_data) / (0.3 * total_rows) if total_rows > 0 else 1.0
            features['late_trade_density'] = late_density
    except Exception as e:
        pass
    
    # 4. 盘口变化时机分析
    try:
        # 如果有盘口列
        handicap_cols = [col for col in trade_data.columns if '盘口' in col or 'handicap' in col.lower()]
        if handicap_cols:
            col = handicap_cols[0]
            handicaps = trade_data[col].astype(str)
            
            # 盘口变化次数
            handicap_changes = (handicaps != handicaps.shift()).sum()
            features['handicap_change_count'] = handicap_changes
            
            # 最后一次盘口变化位置
            if handicap_changes > 0:
                last_change_idx = handicaps[handicaps != handicaps.shift()].index[-1]
                features['last_handicap_change_position'] = last_change_idx / total_rows
    except Exception as e:
        pass
    
    return features


def run_enhanced_backtest():
    """运行增强回测"""
    
    from 完场比赛列表 import get_finished_matches
    
    logging.info("="*80)
    logging.info("开始增强回测 - 实时交易明细分析")
    logging.info("="*80)
    
    # 获取比赛列表
    matches = get_finished_matches(days=7)
    logging.info(f"共获取 {len(matches)} 场比赛")
    
    all_features = []
    processed = 0
    
    for idx, match in enumerate(matches[:100], 1):  # 先测试100场
        try:
            kickoff = match['kickoff']
            home = match['home']
            away = match['away']
            league = match['league']
            score = match.get('score', '0-0')
            
            logging.info(f"\n[{idx}/100] 分析: {kickoff} {league} {home} vs {away}")
            
            # 获取交易明细
            home_score, away_score = score.split('-')
            trade_data = get_cached_detail(kickoff, home, away, home_score, away_score, league)
            
            if trade_data is None or len(trade_data) == 0:
                logging.info("  ⚠️ 无交易数据")
                continue
            
            logging.info(f"  ✅ 交易数据: {len(trade_data)}行")
            
            # 分析交易特征
            trade_features = analyze_trade_detail_features(trade_data)
            
            # 获取盘口数据
            handicap_data = load_handicap_from_cache(kickoff, home, away, home_score, away_score, league)
            
            if handicap_data:
                initial_str = handicap_data.get('initial_handicap_text', '')
                current_str = handicap_data.get('current_handicap_text', '')
                
                try:
                    initial_val = handicap_data.get('initial_handicap_value', 0)
                    current_val = handicap_data.get('current_handicap_value', 0)
                    handicap_change = current_val - initial_val
                except:
                    handicap_change = 0
                
                # 合并特征
                combined = {
                    **trade_features,
                    'kickoff': kickoff,
                    'league': league,
                    'home': home,
                    'away': away,
                    'score': score,
                    'handicap_change': handicap_change,
                    'initial_handicap': initial_str,
                    'current_handicap': current_str,
                }
                
                all_features.append(combined)
                processed += 1
                
                logging.info(f"  ✅ 特征提取成功")
        
        except Exception as e:
            logging.error(f"  ❌ 错误: {e}")
            continue
    
    logging.info(f"\n{'='*80}")
    logging.info(f"完成！成功处理 {processed} 场比赛")
    logging.info(f"{'='*80}\n")
    
    # 保存结果
    if all_features:
        df = pd.DataFrame(all_features)
        output_file = '交易明细特征分析.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logging.info(f"💾 已保存特征数据: {output_file}")
        
        # 简单分析
        logging.info("\n特征统计:")
        for col in df.columns:
            if col not in ['kickoff', 'league', 'home', 'away', 'score', 'initial_handicap', 'current_handicap']:
                if pd.api.types.is_numeric_dtype(df[col]):
                    logging.info(f"  {col}: 平均={df[col].mean():.2f}, 中位数={df[col].median():.2f}")
        
        return df
    
    return None


if __name__ == "__main__":
    df = run_enhanced_backtest()
    
    if df is not None and len(df) > 0:
        print("\n" + "="*80)
        print(f"✅ 成功分析 {len(df)} 场比赛的交易明细")
        print("="*80)
        
        # 显示部分特征
        if 'volume_trend' in df.columns:
            print(f"\n成交额趋势分布:")
            print(f"  平均: {df['volume_trend'].mean():.2f}")
            print(f"  中位数: {df['volume_trend'].median():.2f}")
            print(f"  放量(>1.5x): {(df['volume_trend'] > 1.5).sum()} 场")
            print(f"  缩量(<0.8x): {(df['volume_trend'] < 0.8).sum()} 场")
