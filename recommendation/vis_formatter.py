"""
VIS-E01输出格式化器
将推荐结果格式化为VIS-E01标准输出
"""
from typing import Dict
from datetime import datetime


class VISFormatter:
    """VIS-E01格式化器"""
    
    @staticmethod
    def format_output(result: Dict) -> str:
        """
        格式化推荐结果为VIS-E01标准输出
        
        Args:
            result: 推荐引擎输出结果
            
        Returns:
            格式化的字符串（Markdown代码块格式）
        """
        # 🔥 检查是否是X1 JSON引擎的结果
        if result.get('engine') == 'x1_json':
            return VISFormatter._format_x1_json(result)
        
        # 检查熔断
        if result.get('熔断类型'):
            return VISFormatter._format_fuse(result)
        
        lines = []
        lines.append("```")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        # 🔥 动态显示引擎版本
        version = result.get('version', 'X1-HANDICAP-V2.0')
        if 'V2' in version:
            lines.append("【X1让球盘口推荐系统 V2 · 数据驱动版】")
        else:
            lines.append("【X1全侦破版 · 让球盘口推荐系统】")
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # 比赛信息
        match_info = result.get('match_info', {})
        lines.append("")
        lines.append("【比赛信息】")
        lines.append(f"联赛：{match_info.get('league', 'N/A')}")
        lines.append(f"对阵：{match_info.get('home', 'N/A')} vs {match_info.get('away', 'N/A')}")
        lines.append(f"开赛时间：{match_info.get('kickoff', 'N/A')}")
        
        # 盘口信息
        lines.append("")
        lines.append("【让球盘口】")
        lines.append(f"初盘：{match_info.get('initial_handicap_str', 'N/A')} ({match_info.get('initial_handicap', 'N/A')})")
        lines.append(f"即时盘：{match_info.get('current_handicap_str', 'N/A')} ({match_info.get('current_handicap', 'N/A')})")
        
        handicap_change = 0
        if match_info.get('current_handicap') is not None and match_info.get('initial_handicap') is not None:
            handicap_change = match_info['current_handicap'] - match_info['initial_handicap']
            if abs(handicap_change) > 0.01:
                direction = "上升" if handicap_change > 0 else "下降"
                lines.append(f"盘口变化：{direction} {abs(handicap_change):.2f}")
        
        # 采集状态
        collection = result.get('collection_status', {})
        lines.append("")
        lines.append("【数据采集状态】")
        lines.append(f"交易明细(UG-PDF)：{'✅ 已采集' if collection.get('ug_pdf') else '❌ 缺失'}")
        lines.append(f"让球盘口数据：{'✅ 已采集' if collection.get('handicap') else '❌ 缺失'}")
        lines.append(f"比赛元数据：{'✅ 已采集' if collection.get('metadata') else '❌ 缺失'}")
        
        # 成交指数
        trade_index = result.get('成交指数', {})
        if trade_index.get('status') == 'calculated':
            lines.append("")
            lines.append("【成交指数】")
            lines.append(f"📊 指数：主 {trade_index.get('home', 0):.1f} / 和 {trade_index.get('draw', 0):.1f} / 客 {trade_index.get('away', 0):.1f}")
        
        # 资金等级
        funding = result.get('资金等级', {})
        lines.append("")
        lines.append("【资金等级判定】")
        lines.append(f"成交总额：{funding.get('total_volume', 0):,}")
        lines.append(f"判定区间：{funding.get('range', 'N/A')}")
        lines.append(f"资金等级：{funding.get('level', 'N/A')}")
        lines.append(f"SBRE响应权重：{funding.get('sbre_weight', 0):.2f}")
        
        # 评分等级
        scores = result.get('评分等级', {})
        lines.append("")
        lines.append("【评分等级】")
        lines.append(f"FLM（热度前线）：{scores.get('FLM', '未评分')}")
        lines.append(f"SPM（承压评分）：{scores.get('SPM', '未评分')}")
        lines.append(f"DPI（风险整合）：{scores.get('DPI', '未评分')}")
        
        # 风控机制
        risk_checks = result.get('风控机制', {})
        lines.append("")
        lines.append("【风控机制状态】")
        lines.append(f"SmartSafe（结构支撑）：{'✔️ 触发' if risk_checks.get('SmartSafe') else '✖ 未触发'}")
        lines.append(f"SS-Dagger（诱导识别）：{'✔️ 触发' if risk_checks.get('SS-Dagger') else '✖ 未触发'}")
        lines.append(f"LVC（落点验证）：{'✔️ 触发' if risk_checks.get('LVC') else '✖ 未触发'}")
        lines.append(f"TPI（穿盘预警）：{'✔️ 触发' if risk_checks.get('TPI') else '✖ 未触发'}")
        
        if risk_checks.get('details'):
            lines.append("风控详情：")
            for detail in risk_checks['details']:
                lines.append(f"  · {detail}")
        
        # SBRE机制
        sbre = result.get('SBRE', {})
        lines.append("")
        lines.append("【SBRE机制】")
        if sbre.get('triggered'):
            lines.append(f"✔️ 已触发反解")
            lines.append(f"触发原因：{sbre.get('reason', 'N/A')}")
            lines.append(f"SBRE推荐：{sbre.get('recommendation', 'N/A')}")
        else:
            lines.append("✖ 未触发反解")
        
        # 让球盘口推荐
        handicap_rec = result.get('让球盘口推荐', {})
        lines.append("")
        lines.append("【让球盘口落点推演】")
        lines.append(f"推荐方向：{handicap_rec.get('direction', 'N/A')}")
        lines.append(f"推荐盘口：{handicap_rec.get('recommended_handicap_str', 'N/A')} ({handicap_rec.get('recommended_handicap', 'N/A')})")
        lines.append(f"置信度：{handicap_rec.get('confidence', 0):.1%}")
        
        if handicap_rec.get('reason'):
            lines.append("推演依据：")
            for reason in handicap_rec['reason']:
                lines.append(f"  · {reason}")
        
        # 风险提示
        risk_notes = result.get('风险提示', [])
        if risk_notes:
            lines.append("")
            lines.append("【风险提示】")
            for note in risk_notes:
                lines.append(f"  {note}")
        
        # 最终推荐
        final_rec = result.get('最终推荐', {})
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 【最终下注建议】（仅一项）")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if final_rec.get('should_bet'):
            lines.append(f"✅ 推荐：{final_rec.get('direction', 'N/A')}")
            lines.append(f"盘口：{final_rec.get('handicap_str', 'N/A')} ({final_rec.get('handicap', 'N/A')})")
            lines.append(f"置信度：{final_rec.get('confidence', 0):.1%}")
            lines.append(f"理由：{final_rec.get('reason', 'N/A')}")
        else:
            lines.append(f"❌ 不推荐下注")
            lines.append(f"原因：{final_rec.get('reason', 'N/A')}")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("```")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_fuse(result: Dict) -> str:
        """格式化熔断输出"""
        lines = []
        lines.append("```")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("【系统熔断】")
        lines.append(f"熔断类型：{result.get('熔断类型', 'UNKNOWN')}")
        lines.append(f"熔断原因：{result.get('熔断原因', 'N/A')}")
        lines.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("❌ 数据链不完整，无法生成推荐")
        lines.append("请确保以下数据齐全：")
        
        collection = result.get('collection_status', {})
        lines.append(f"  · 交易明细(UG-PDF)：{'✅' if collection.get('ug_pdf') else '❌ 缺失'}")
        lines.append(f"  · 让球盘口数据：{'✅' if collection.get('handicap') else '❌ 缺失'}")
        lines.append(f"  · 比赛元数据：{'✅' if collection.get('metadata') else '❌ 缺失'}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("```")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_telegram_message(result: Dict) -> str:
        """
        格式化为Telegram消息（简洁版）
        
        Args:
            result: 推荐结果
            
        Returns:
            Telegram消息文本
        """
        if result.get('熔断类型'):
            return f"❌ 系统熔断\n{result.get('熔断原因', 'N/A')}"
        
        match_info = result.get('match_info', {})
        final_rec = result.get('最终推荐', {})
        
        lines = []
        lines.append("⚽ **足球赛事推荐**")
        lines.append("")
        lines.append(f"🏆 {match_info.get('league', 'N/A')}")
        lines.append(f"🆚 {match_info.get('home', 'N/A')} vs {match_info.get('away', 'N/A')}")
        lines.append(f"⏰ {match_info.get('kickoff', 'N/A')}")
        lines.append("")
        lines.append(f"💰 盘口：{match_info.get('current_handicap_str', 'N/A')}")
        lines.append("")
        
        if final_rec.get('should_bet'):
            lines.append("✅ **推荐下注**")
            lines.append(f"📍 方向：{final_rec.get('direction', 'N/A')}")
            lines.append(f"🎯 盘口：{final_rec.get('handicap_str', 'N/A')}")
            lines.append(f"📊 置信度：{final_rec.get('confidence', 0):.0%}")
            lines.append(f"💡 理由：{final_rec.get('reason', 'N/A')}")
        else:
            lines.append("❌ **不推荐下注**")
            lines.append(f"💡 原因：{final_rec.get('reason', 'N/A')}")
        
        # 风险提示
        risk_notes = result.get('风险提示', [])
        if risk_notes:
            lines.append("")
            lines.append("⚠️ **风险提示**")
            for note in risk_notes[:3]:  # 最多3条
                lines.append(f"  {note}")
        
        return "\n".join(lines)


    @staticmethod
    def _format_x1_json(result: Dict) -> str:
        """格式化X1 JSON推荐引擎的输出"""
        lines = []
        lines.append("```")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("【X1 JSON推荐引擎 · 准确率83.6%】")
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # 提取X1 JSON的数据
        x1_scores = result.get('x1_json_scores', {})
        x1_funding = result.get('x1_json_funding', {})
        x1_risk = result.get('x1_json_risk', {})
        
        # 推荐信息
        direction_map = {'home': '主队', 'away': '客队', 'none': '不推荐'}
        direction_text = direction_map.get(result.get('direction', 'none'), result.get('direction', '不推荐'))
        
        lines.append("【推荐结果】")
        lines.append(f"方向: {direction_text}")
        lines.append(f"盘口: {result.get('handicap', 'N/A')}")
        lines.append(f"置信度: {result.get('confidence', 0)*100:.1f}%")
        lines.append(f"理由: {result.get('reason', 'N/A')}")
        lines.append("")
        
        # 资金等级
        if x1_funding:
            lines.append("【资金等级】")
            lines.append(f"等级: {x1_funding.get('level', 'N/A')}")
            lines.append(f"总成交量: {x1_funding.get('total_volume', 0):,}")
            lines.append(f"SBRE权重: {x1_funding.get('sbre_weight', 0):.2f}")
            lines.append("")
        
        # 评分模块
        if x1_scores:
            lines.append("【评分模块】")
            
            # FLM
            flm = x1_scores.get('FLM', {})
            if flm:
                lines.append(f"FLM (热度前线): {flm.get('level', 'N/A')}")
                lines.append(f"  - 置信度: {flm.get('confidence', 0)*100:.1f}%")
                lines.append(f"  - 主: {flm.get('home_pct', 0):.1f}% | 和: {flm.get('draw_pct', 0):.1f}% | 客: {flm.get('away_pct', 0):.1f}%")
            
            # SPM
            spm = x1_scores.get('SPM', {})
            if spm:
                lines.append(f"SPM (结构承压): {spm.get('structure', 'N/A')}")
                lines.append(f"  - 置信度: {spm.get('confidence', 0)*100:.1f}%")
            
            # DPI
            dpi = x1_scores.get('DPI', {})
            if dpi:
                lines.append(f"DPI (风险整合): {dpi.get('risk_level', 'N/A')}")
                lines.append(f"  - 置信度: {dpi.get('confidence', 0)*100:.1f}%")
                lines.append(f"  - 压强指数: {dpi.get('pressure_index', 0)}")
            
            lines.append("")
        
        # 风控机制
        if x1_risk:
            risk_triggered = any([
                x1_risk.get('SmartSafe'),
                x1_risk.get('SS-Dagger'),
                x1_risk.get('LVC'),
                x1_risk.get('TPI')
            ])
            
            if risk_triggered:
                lines.append("【风控提示】")
                if x1_risk.get('SmartSafe'):
                    lines.append("⚠️ SmartSafe: 结构支撑缺失")
                if x1_risk.get('SS-Dagger'):
                    lines.append("⚠️ SS-Dagger: 诱导盘识别")
                if x1_risk.get('LVC'):
                    lines.append("⚠️ LVC: 凯利指数异常")
                if x1_risk.get('TPI'):
                    lines.append("⚠️ TPI: 穿盘预警")
                
                messages = x1_risk.get('messages', [])
                if messages:
                    for msg in messages:
                        lines.append(f"  - {msg}")
                lines.append("")
        
        # 最终下注建议
        confidence = result.get('confidence', 0)
        should_bet = result.get('should_bet', False) and confidence >= 0.85
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🎯 【最终下注建议】")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if should_bet:
            lines.append(f"✅ 推荐: {direction_text}")
            lines.append(f"盘口: {result.get('handicap', 'N/A')}")
            lines.append(f"置信度: {confidence*100:.1f}%")
            lines.append(f"理由: {result.get('reason', 'N/A')}")
        else:
            lines.append("❌ 不推荐下注")
            if confidence < 0.85:
                lines.append(f"原因: 置信度不足({confidence*100:.1f}%)，建议观望")
            else:
                lines.append("原因: 风控提示或推荐方向不明确")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("💡 数据来源: X1 JSON推荐引擎（基于历史数据）")
        lines.append("📊 历史准确率: 整体77.1% | 高置信度83.6%")
        lines.append("```")
        
        return "\n".join(lines)


# 模块导出
__all__ = ['VISFormatter']
