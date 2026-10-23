"""
增强批量回测 - 同时分析交易明细特征
目标：既要场数多，又要准确率高
"""

import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import json
from pathlib import Path

# 导入现有模块
sys.path.insert(0, str(Path(__file__).parent))
from 数据抓取与缓存管理 import get_cached_detail, load_handicap_from_cache
from 完场比赛列表 import get_finished_matches
from 回测验证器 import RecommendationValidator

# 🔥 导入X1 JSON推荐引擎（准确率84.8%，策略1：分级阈值）
from recommendation.x1_json_recommender import X1JSONRecommender
USE_X1 = True

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def analyze_trade_dynamics(trade_data):
    """分析交易动态特征"""
    if trade_data is None or len(trade_data) == 0:
        return {}
    
    features = {}
    total_rows = len(trade_data)
    features['total_rows'] = total_rows
    
    # 时间分段
    early_end = max(1, int(total_rows * 0.3))
    mid_end = max(2, int(total_rows * 0.7))
    
    early = trade_data.iloc[:early_end]
    mid = trade_data.iloc[early_end:mid_end]
    late = trade_data.iloc[mid_end:]
    
    # 成交额分析
    volume_col = None
    for col in ['成交额', '成交量', '金额']:
        if col in trade_data.columns:
            volume_col = col
            break
    
    if volume_col:
        def safe_parse(v):
            try:
                return float(str(v).replace(',', ''))
            except:
                return 0
        
        volumes = trade_data[volume_col].apply(safe_parse)
        
        early_vol = early[volume_col].apply(safe_parse).mean() if len(early) > 0 else 0
        late_vol = late[volume_col].apply(safe_parse).mean() if len(late) > 0 else 0
        
        features['early_volume'] = early_vol
        features['late_volume'] = late_vol
        features['volume_growth'] = late_vol / early_vol if early_vol > 0 else 1.0
        
        # 大额交易
        avg_vol = volumes.mean()
        if avg_vol > 0:
            big = volumes[volumes > avg_vol * 2]
            features['big_trade_ratio'] = len(big) / total_rows
            
            # 大额在晚期的比例
            if len(big) > 0:
                big_late = sum(1 for i, v in enumerate(volumes) if v > avg_vol * 2 and i >= mid_end)
                features['big_in_late_ratio'] = big_late / len(big)
    
    # 水位分析
    for prefix, pattern in [('主', '主'), ('客', '客')]:
        for col in trade_data.columns:
            if pattern in col and ('水位' in col or '赔率' in col):
                def safe_price(p):
                    try:
                        return float(p)
                    except:
                        return 0
                
                prices = trade_data[col].apply(safe_price)
                
                features[f'{prefix}_volatility'] = prices.std() if len(prices) > 1 else 0
                
                if len(early) > 0 and len(late) > 0:
                    early_p = early[col].apply(safe_price).mean()
                    late_p = late[col].apply(safe_price).mean()
                    
                    if early_p > 0:
                        features[f'{prefix}_price_change'] = (late_p - early_p) / early_p
                
                break
    
    # 交易节奏
    if total_rows >= 10:
        late_density = len(late) / (0.3 * total_rows) if total_rows > 0 else 1.0
        features['late_density'] = late_density
    
    return features


def run_enhanced_backtest():
    """运行增强回测"""
    
    logging.info("="*80)
    logging.info("增强批量回测 - 实时交易明细分析")
    logging.info("="*80)
    
    # 获取比赛列表
    matches = get_finished_matches(days=7)
    logging.info(f"共 {len(matches)} 场比赛")
    
    # 使用X1 JSON引擎
    engine = X1JSONRecommender()
    logging.info("✅ 已加载X1 JSON推荐引擎（准确率84.8%）")
    validator = RecommendationValidator()
    
    results = []
    feature_data = []
    
    for idx, match in enumerate(matches, 1):
        try:
            kickoff = match['kickoff']
            home = match['home']
            away = match['away']
            league = match['league']
            score = match.get('score', '0-0')
            
            logging.info(f"\n[{idx}/{len(matches)}] {kickoff} {league} {home} vs {away}")
            
            # 获取数据
            home_score, away_score = score.split('-')
            trade_data = get_cached_detail(kickoff, home, away, home_score, away_score, league)
            
            if trade_data is None or len(trade_data) == 0:
                logging.info("  ⚠️ 无交易数据")
                continue
            
            logging.info(f"  📊 交易数据: {len(trade_data)}行")
            
            # 获取盘口
            handicap_data = load_handicap_from_cache(kickoff, home, away, home_score, away_score, league)
            
            if not handicap_data:
                logging.info("  ⚠️ 无盘口数据")
                continue
            
            # 生成推荐
            match_data = {'handicap_data': handicap_data}
            recommendation = engine.analyze_match(match_data, trade_data=trade_data)
            
            if not recommendation.get('should_bet'):
                logging.info("  ⏸️ 不推荐")
                continue
            
            logging.info(f"  ✅ 推荐: {recommendation.get('recommendation')}")
            
            # 验证结果
            validation = validator.validate_recommendation(
                recommendation,
                int(home_score),
                int(away_score)
            )
            
            # 分析交易特征
            trade_features = analyze_trade_dynamics(trade_data)
            
            # 合并数据
            result = {
                'kickoff': kickoff,
                'league': league,
                'home': home,
                'away': away,
                'score': score,
                'recommendation': recommendation.get('recommendation'),
                'confidence': recommendation.get('confidence', 0),
                'profit': validation.get('profit', 0),
                'is_profit': validation.get('profit', 0) > 0,
                **trade_features
            }
            
            feature_data.append(result)
            logging.info(f"  💰 盈亏: {validation.get('profit', 0):+.2f}")
            
        except Exception as e:
            logging.error(f"  ❌ 错误: {e}")
            continue
    
    logging.info(f"\n{'='*80}")
    logging.info(f"完成！共分析 {len(feature_data)} 场推荐")
    logging.info(f"{'='*80}\n")
    
    # 保存数据
    if feature_data:
        df = pd.DataFrame(feature_data)
        output_file = '交易特征完整数据.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logging.info(f"💾 已保存: {output_file}")
        
        # 基础统计
        win_rate = df['is_profit'].mean()
        total_profit = df['profit'].sum()
        
        logging.info(f"\n整体表现:")
        logging.info(f"  推荐场次: {len(df)}")
        logging.info(f"  准确率: {win_rate*100:.1f}%")
        logging.info(f"  总盈亏: {total_profit:+.2f}")
        
        return df
    
    return None


def analyze_patterns(df):
    """分析黄金模式"""
    
    print("\n" + "="*80)
    print("💎 寻找黄金模式")
    print("="*80)
    
    base_win_rate = df['is_profit'].mean()
    print(f"\n基准准确率: {base_win_rate*100:.1f}%")
    
    patterns = []
    
    # 模式1: 晚期放量
    if 'volume_growth' in df.columns:
        for threshold in [1.3, 1.5, 2.0, 2.5]:
            filtered = df[df['volume_growth'] >= threshold]
            if len(filtered) >= 10:
                wr = filtered['is_profit'].mean()
                if wr > base_win_rate + 0.05:
                    patterns.append({
                        'name': f'晚期放量≥{threshold:.1f}x',
                        'count': len(filtered),
                        'win_rate': wr,
                        'avg_profit': filtered['profit'].mean(),
                    })
    
    # 模式2: 大额晚期
    if 'big_in_late_ratio' in df.columns:
        for threshold in [0.5, 0.6, 0.7]:
            filtered = df[df['big_in_late_ratio'] >= threshold]
            if len(filtered) >= 10:
                wr = filtered['is_profit'].mean()
                if wr > base_win_rate + 0.05:
                    patterns.append({
                        'name': f'大额晚期≥{threshold*100:.0f}%',
                        'count': len(filtered),
                        'win_rate': wr,
                        'avg_profit': filtered['profit'].mean(),
                    })
    
    # 模式3: 高成交量
    if 'total_rows' in df.columns:
        for threshold in [150, 200, 250, 300]:
            filtered = df[df['total_rows'] >= threshold]
            if len(filtered) >= 10:
                wr = filtered['is_profit'].mean()
                if wr > base_win_rate + 0.05:
                    patterns.append({
                        'name': f'高成交量≥{threshold}行',
                        'count': len(filtered),
                        'win_rate': wr,
                        'avg_profit': filtered['profit'].mean(),
                    })
    
    # 模式4: 主水下降
    if '主_price_change' in df.columns:
        for threshold in [-0.05, -0.03, -0.02]:
            filtered = df[df['主_price_change'] <= threshold]
            if len(filtered) >= 10:
                wr = filtered['is_profit'].mean()
                if wr > base_win_rate + 0.05:
                    patterns.append({
                        'name': f'主水下降≤{threshold*100:.0f}%',
                        'count': len(filtered),
                        'win_rate': wr,
                        'avg_profit': filtered['profit'].mean(),
                    })
    
    # 模式5: 低波动
    if '主_volatility' in df.columns:
        for threshold in [0.05, 0.03, 0.02]:
            filtered = df[df['主_volatility'] <= threshold]
            if len(filtered) >= 10:
                wr = filtered['is_profit'].mean()
                if wr > base_win_rate + 0.05:
                    patterns.append({
                        'name': f'低波动≤{threshold}',
                        'count': len(filtered),
                        'win_rate': wr,
                        'avg_profit': filtered['profit'].mean(),
                    })
    
    # 排序输出
    patterns.sort(key=lambda x: (x['win_rate'], x['count']), reverse=True)
    
    print(f"\n{'模式名称':30} {'样本数':>8} {'准确率':>10} {'平均盈利':>12}")
    print("-" * 70)
    
    for p in patterns[:15]:
        symbol = "💎" if p['win_rate'] >= 0.70 else "⭐"
        print(f"{symbol} {p['name']:28} {p['count']:>8}场 {p['win_rate']*100:>9.1f}% {p['avg_profit']:>+12.3f}")
    
    return patterns


if __name__ == "__main__":
    df = run_enhanced_backtest()
    
    if df is not None and len(df) > 0:
        patterns = analyze_patterns(df)
        
        print("\n" + "="*80)
        print("✅ 分析完成！")
        print("="*80)
