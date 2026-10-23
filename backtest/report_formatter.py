"""
回测报告格式化器
"""
from typing import Dict
from datetime import datetime


def format_backtest_report(backtest_result: Dict) -> str:
    """
    格式化回测报告
    
    Args:
        backtest_result: 回测结果
        
    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("```")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("【回测报告】")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 比赛信息
    match_info = backtest_result.get('match_info', {})
    lines.append("")
    lines.append("【比赛信息】")
    lines.append(f"联赛：{match_info.get('league', 'N/A')}")
    lines.append(f"对阵：{match_info.get('home', 'N/A')} vs {match_info.get('away', 'N/A')}")
    lines.append(f"开赛时间：{match_info.get('kickoff', 'N/A')}")
    
    # 实际比分
    actual_score = backtest_result.get('actual_score', (0, 0))
    lines.append(f"实际比分：{actual_score[0]} : {actual_score[1]}")
    
    # 盘口信息
    handicap_data = backtest_result.get('handicap_data', {})
    if handicap_data:
        lines.append("")
        lines.append("【让球盘口】")
        lines.append(f"初盘：{handicap_data.get('initial', 'N/A')}")
        lines.append(f"即时盘：{handicap_data.get('current', 'N/A')}")
    
    # 推荐结果
    recommendation = backtest_result.get('recommendation', {})
    final_rec = recommendation.get('最终推荐', {})
    
    lines.append("")
    lines.append("【推荐结果】")
    if final_rec.get('should_bet'):
        lines.append(f"推荐：✅ {final_rec.get('direction', 'N/A')}")
        lines.append(f"盘口：{final_rec.get('handicap_str', 'N/A')} ({final_rec.get('handicap', 'N/A')})")
        lines.append(f"置信度：{final_rec.get('confidence', 0):.1%}")
        lines.append(f"理由：{final_rec.get('reason', 'N/A')}")
    else:
        lines.append(f"推荐：❌ 不推荐下注")
        lines.append(f"原因：{final_rec.get('reason', 'N/A')}")
    
    # 评分详情
    scores = recommendation.get('评分等级', {})
    if scores:
        lines.append("")
        lines.append("【评分详情】")
        lines.append(f"FLM：{scores.get('FLM', 'N/A')}")
        lines.append(f"SPM：{scores.get('SPM', 'N/A')}")
        lines.append(f"DPI：{scores.get('DPI', 'N/A')}")
    
    # 验证结果
    validation = backtest_result.get('validation', {})
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("【验证结果】")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if validation.get('validated'):
        if validation.get('recommended'):
            result_type = validation.get('result', 'N/A')
            profit = validation.get('profit', 0)
            message = validation.get('message', 'N/A')
            
            # 结果图标
            if result_type in ['WIN', 'HALF_WIN']:
                icon = "✅"
            elif result_type in ['LOSE', 'HALF_LOSE']:
                icon = "❌"
            else:
                icon = "➖"
            
            lines.append(f"{icon} 结果：{result_type}")
            lines.append(f"盈亏：{profit:+.2f} 单位")
            lines.append(f"说明：{message}")
        else:
            lines.append("📌 未推荐下注，不参与盈亏计算")
    else:
        lines.append(f"❌ 验证失败：{validation.get('error', 'N/A')}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("```")
    
    return "\n".join(lines)


def format_batch_backtest_report(batch_result: Dict) -> str:
    """
    格式化批量回测报告
    
    Args:
        batch_result: 批量回测结果
        
    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("```")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("【批量回测报告】")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 总体统计
    stats = batch_result.get('statistics', {})
    lines.append("")
    lines.append("【总体统计】")
    lines.append(f"测试场次：{stats.get('total', 0)}")
    lines.append(f"有推荐：{stats.get('recommended', 0)}")
    lines.append(f"未推荐：{stats.get('no_bet', 0)}")
    lines.append("")
    
    # 推荐结果分布
    if stats.get('recommended', 0) > 0:
        lines.append("【推荐结果分布】")
        lines.append(f"全赢：{stats.get('win', 0)}")
        lines.append(f"半赢：{stats.get('half_win', 0)}")
        lines.append(f"走水：{stats.get('draw', 0)}")
        lines.append(f"半输：{stats.get('half_lose', 0)}")
        lines.append(f"全输：{stats.get('lose', 0)}")
        lines.append("")
        
        # 关键指标
        lines.append("【关键指标】")
        lines.append(f"胜率：{stats.get('win_rate', 0):.2f}%")
        lines.append(f"总盈亏：{stats.get('total_profit', 0):+.2f} 单位")
        lines.append(f"ROI：{stats.get('roi', 0):+.2f}%")
        lines.append("")
    
    # 详细结果列表
    results = batch_result.get('results', [])
    if results:
        lines.append("【详细结果】")
        lines.append(f"{'序号':<4} {'主队':<12} {'客队':<12} {'比分':<8} {'推荐':<10} {'结果':<10} {'盈亏':<8}")
        lines.append("-" * 80)
        
        for i, result in enumerate(results, 1):
            if not result.get('success'):
                continue
            
            match_info = result.get('match_info', {})
            validation = result.get('validation', {})
            actual_score = result.get('actual_score', (0, 0))
            
            home = match_info.get('home', 'N/A')[:12]
            away = match_info.get('away', 'N/A')[:12]
            score_str = f"{actual_score[0]}:{actual_score[1]}"
            
            if validation.get('recommended'):
                rec_dir = validation.get('recommended_direction', 'N/A')[:10]
                result_type = validation.get('result', 'N/A')
                profit = validation.get('profit', 0)
                
                lines.append(f"{i:<4} {home:<12} {away:<12} {score_str:<8} {rec_dir:<10} {result_type:<10} {profit:+.2f}")
            else:
                lines.append(f"{i:<4} {home:<12} {away:<12} {score_str:<8} {'未推荐':<10} {'N/A':<10} {0:+.2f}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("```")
    
    return "\n".join(lines)


# 模块导出
__all__ = ['format_backtest_report', 'format_batch_backtest_report']
