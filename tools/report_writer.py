#!/usr/bin/env python3
"""
report_writer.py — 好感度分析文字报告生成器

用法：
    python3 report_writer.py --scores scores.json --parsed parsed.json \
        --me "小明" --them "小红" --mode review --output report.md
    python3 report_writer.py --scores scores.json --parsed parsed.json \
        --me "我" --them "TA" --mode track --output report.md
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

PHASE_LABELS = {
    "热恋期":  (70, 100),
    "稳定期":  (55,  69),
    "平淡期":  (40,  54),
    "衰退期":  (20,  39),
    "冰点期":  (0,   19),
}


def classify_phase(score: float) -> str:
    for label, (lo, hi) in PHASE_LABELS.items():
        if lo <= score <= hi:
            return label
    return "未知"


def trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "数据不足"
    first_half = sum(values[:len(values)//2]) / max(1, len(values)//2)
    second_half = sum(values[len(values)//2:]) / max(1, len(values) - len(values)//2)
    diff = second_half - first_half
    if diff > 10:
        return "📈 上升"
    elif diff < -10:
        return "📉 下滑"
    else:
        return "➡️ 平稳"


def score_summary(score: float) -> str:
    if score >= 75:
        return "高位亲近"
    if score >= 60:
        return "有好感但偏克制"
    if score >= 45:
        return "礼貌维系"
    if score >= 30:
        return "明显疏离"
    return "接近断联"


def find_peaks(scores: list[dict], key: str) -> list[dict]:
    vals = [s[key] for s in scores]
    peaks = []
    for i in range(1, len(vals) - 1):
        if vals[i] >= vals[i-1] and vals[i] >= vals[i+1] and vals[i] > 65:
            peaks.append(scores[i])
    if not peaks and vals:
        max_i = vals.index(max(vals))
        peaks = [scores[max_i]]
    return peaks[:3]


def find_valleys(scores: list[dict], key: str) -> list[dict]:
    vals = [s[key] for s in scores]
    valleys = []
    for i in range(1, len(vals) - 1):
        if vals[i] <= vals[i-1] and vals[i] <= vals[i+1] and vals[i] < 50:
            valleys.append(scores[i])
    if not valleys and vals:
        min_i = vals.index(min(vals))
        valleys = [scores[min_i]]
    return valleys[:3]


def generate_report(scores: list[dict], parsed: list[dict],
                    me_name: str, them_name: str, mode: str) -> str:
    me_vals   = [s["me"]   for s in scores]
    them_vals = [s["them"] for s in scores]
    me_avg    = round(sum(me_vals) / len(me_vals), 1) if me_vals else 50.0
    them_avg  = round(sum(them_vals) / len(them_vals), 1) if them_vals else 50.0
    me_current = round(me_vals[-1], 1) if me_vals else 50.0
    them_current = round(them_vals[-1], 1) if them_vals else 50.0

    me_msgs    = [m for m in parsed if m.get("sender") == "me"]
    them_msgs  = [m for m in parsed if m.get("sender") == "them"]
    total_msgs = len(parsed)

    # ━━━ 高阶特征计算 ━━━
    # 1. 字数信息差 (Talkativity)
    me_chars = sum(m.get("len", 0) for m in me_msgs)
    them_chars = sum(m.get("len", 0) for m in them_msgs)
    
    # 2. 深夜软肋指数 (23:00 - 05:00)
    def is_late_night(ts_str):
        try:
            hour = datetime.fromisoformat(ts_str).hour
            return hour >= 23 or hour < 5
        except Exception:
            return False
    me_night   = sum(1 for m in me_msgs if is_late_night(m.get("ts", "")))
    them_night = sum(1 for m in them_msgs if is_late_night(m.get("ts", "")))
    me_night_ratio   = round(me_night / max(1, len(me_msgs)) * 100, 1)
    them_night_ratio = round(them_night / max(1, len(them_msgs)) * 100, 1)

    # 3. 冷战/失联探测器 (Ghosting gap)
    max_gap_sec = 0
    icebreaker = "无"
    gap_desc = "无显著断联"
    sorted_msgs = sorted(parsed, key=lambda m: m.get("ts") or "")
    for i in range(1, len(sorted_msgs)):
        try:
            t1 = datetime.fromisoformat(sorted_msgs[i-1]["ts"])
            t2 = datetime.fromisoformat(sorted_msgs[i]["ts"])
            gap = (t2 - t1).total_seconds()
            if gap > max_gap_sec:
                max_gap_sec = gap
                gap_days = gap / 86400
                breaker_name = me_name if sorted_msgs[i].get("sender") == "me" else them_name
                if gap_days >= 1.5:  # 大于 1.5 天才算冷战
                    gap_desc = f"长达 {round(gap_days, 1)} 天 ({t1.strftime('%m-%d')} 至 {t2.strftime('%m-%d')})"
                    icebreaker = breaker_name
        except Exception:
            pass
    max_gap_days = round(max_gap_sec / 86400, 1)
    # ━━━━━━━━━━━━━━━━━━━━

    # 时间跨度
    ts_list = [m["ts"] for m in parsed if m.get("ts")]
    if ts_list:
        first_ts = min(ts_list)
        last_ts  = max(ts_list)
        try:
            start = datetime.fromisoformat(first_ts).strftime("%Y-%m-%d")
            end   = datetime.fromisoformat(last_ts).strftime("%Y-%m-%d")
        except Exception:
            start = first_ts[:10]
            end   = last_ts[:10]
    else:
        start = end = "未知"

    # 主动性
    me_total_initiative   = round(sum(s["me_initiative"]   for s in scores) / len(scores) * 100, 1)
    them_total_initiative = round(sum(s["them_initiative"] for s in scores) / len(scores) * 100, 1)

    # 关系阶段
    me_phase   = classify_phase(me_current)
    them_phase = classify_phase(them_current)

    # 趋势
    me_trend   = trend_direction(me_vals)
    them_trend = trend_direction(them_vals)

    # 峰值谷值
    me_peaks   = find_peaks(scores, "me")
    me_valleys = find_valleys(scores, "me")
    them_peaks = find_peaks(scores, "them")
    them_valleys = find_valleys(scores, "them")

    # 平均回复速度（从 raw 推算的已有各维度信息）
    me_avg_reply   = round(sum(s["raw"].get("me_reply", 60)   for s in scores) / len(scores), 1)
    them_avg_reply = round(sum(s["raw"].get("them_reply", 60) for s in scores) / len(scores), 1)

    # ── 报告头
    mode_label = "【复盘分析】" if mode == "review" else "【实时追踪】"
    lines = [
        f"# 好感度曲线分析报告 {mode_label}",
        f"",
        f"> 分析对象：**{me_name}**（我）↔ **{them_name}**（TA）",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"",
        f"## 一、关系概况",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 记录时间跨度 | {start} → {end} |",
        f"| 消息总量 | {total_msgs} 条（我方 {len(me_msgs)} / 对方 {len(them_msgs)}）|",
        f"| 我方平均好感度 | **{me_avg}** / 100 |",
        f"| 对方平均好感度 | **{them_avg}** / 100 |",
        f"| 我方主动发起对话占比 | {me_total_initiative}% |",
        f"| 对方主动发起对话占比 | {them_total_initiative}% |",
        f"| 我方平均回复速度评分 | {me_avg_reply} / 100 |",
        f"| 对方平均回复速度评分 | {them_avg_reply} / 100 |",
        f"",
        f"---",
        f"",
        f"## 二、好感度阶段判断",
        f"",
        f"- **我方**：当前窗口得分 {me_current} → 处于「{me_phase}」阶段，趋势 {me_trend}（历史均值 {me_avg}）",
        f"- **对方**：当前窗口得分 {them_current} → 处于「{them_phase}」阶段，趋势 {them_trend}（历史均值 {them_avg}）",
        f"",
    ]

    pair_current = round((me_current + them_current) / 2, 1)
    pair_avg = round((me_avg + them_avg) / 2, 1)
    if pair_current <= pair_avg - 8:
        phase_desc = "当前状态明显低于历史均值，这更像关系回落后的维系，而不是稳定升温。"
    elif me_trend == "📉 下滑" or them_trend == "📉 下滑":
        phase_desc = "至少一方已经出现下滑，表面还能聊，不代表关系仍在推进。"
    else:
        phase_desc = "当前窗口与历史均值接近，关系处于相对稳定的惯性区间。"
    lines.append(f"> 💡 {phase_desc}")
    lines.append("")

    # ── 关键节点
    lines += [
        "---",
        "",
        "## 三、关键节点解析",
        "",
        "### 我方好感度曲线节点",
        "",
    ]
    if me_peaks:
        lines.append("**峰值时刻（热情最高）**")
        for p in me_peaks:
            event_text = f" · {', '.join(p.get('events') or [])}" if p.get("events") else ""
            reason = p.get("raw", {}).get("me_reasoning", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- {p['label']}：得分 **{p['me']}**{event_text}{reason_text}")
        lines.append("")
    if me_valleys:
        lines.append("**谷值时刻（投入最低）**")
        for v in me_valleys:
            event_text = f" · {', '.join(v.get('events') or [])}" if v.get("events") else ""
            reason = v.get("raw", {}).get("me_reasoning", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- {v['label']}：得分 **{v['me']}**{event_text}{reason_text}")
        lines.append("")

    lines.append("### 对方好感度曲线节点")
    lines.append("")
    if them_peaks:
        lines.append("**峰值时刻（热情最高）**")
        for p in them_peaks:
            event_text = f" · {', '.join(p.get('events') or [])}" if p.get("events") else ""
            reason = p.get("raw", {}).get("them_reasoning", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- {p['label']}：得分 **{p['them']}**{event_text}{reason_text}")
        lines.append("")
    if them_valleys:
        lines.append("**谷值时刻（投入最低）**")
        for v in them_valleys:
            event_text = f" · {', '.join(v.get('events') or [])}" if v.get("events") else ""
            reason = v.get("raw", {}).get("them_reasoning", "")
            reason_text = f"（{reason}）" if reason else ""
            lines.append(f"- {v['label']}：得分 **{v['them']}**{event_text}{reason_text}")
        lines.append("")

    # ── 双方画像对比
    more_active = me_name if me_total_initiative >= them_total_initiative else them_name
    more_expressive_me   = sum(s["raw"].get("me_sentiment", 50)   for s in scores) / len(scores)
    more_expressive_them = sum(s["raw"].get("them_sentiment", 50) for s in scores) / len(scores)
    more_expressive = me_name if more_expressive_me >= more_expressive_them else them_name

    longer_msg_me   = sum(s["raw"].get("me_length", 50)   for s in scores) / len(scores)
    longer_msg_them = sum(s["raw"].get("them_length", 50) for s in scores) / len(scores)
    more_verbose = me_name if longer_msg_me >= longer_msg_them else them_name

    lines += [
        "---",
        "",
        "## 四、双方行为画像对比",
        "",
        f"| 维度 | {me_name}（我） | {them_name}（TA） |",
        f"|------|---------|---------|",
        f"| 平均好感度 | {me_avg} | {them_avg} |",
        f"| 主动性占比 | {me_total_initiative}% | {them_total_initiative}% |",
        f"| 回复速度评分 | {me_avg_reply} | {them_avg_reply} |",
        f"| 情感表达丰富度 | {round(more_expressive_me, 1)} | {round(more_expressive_them, 1)} |",
        f"| 单句消息丰富度 | {round(longer_msg_me, 1)} | {round(longer_msg_them, 1)} |",
        "",
        f"- **更主动的一方**：{more_active}（更多主动发起对话）",
        f"- **情感表达更丰富**：{more_expressive}（更多正向情感词、emoji、亲昵称呼）",
        f"- **消息内容更丰富**：{more_verbose}（平均单句消息更长、更详细）",
        "",
        "---",
        "",
        "## 五、高阶诊断特征（直击灵魂）",
        "",
        "### 1. 📝 信息差指数 (Talkativity Asymmetry)",
        f"- 我方总输出字数：**{me_chars} 字**",
        f"- 对方总输出字数：**{them_chars} 字**",
    ]
    
    char_ratio = me_chars / max(1, them_chars)
    if me_chars < 20 and them_chars < 20:
        lines.append("> 💡 数据量较少，暂无法评估输入不对等情况。")
    elif char_ratio > 3:
        lines.append("> ⚠️ **预警**：我方输出字数是对方的 3 倍以上！存在极强的单向输出（小作文）与敷衍回复倾斜。")
    elif char_ratio < 0.33:
        lines.append("> ⚠️ **预警**：对方输出字数是我方的 3 倍以上！对方极其投入，而我方回复过于简略敷衍。")
    else:
        lines.append("> 💡 双方字数投入相对均衡，沟通意愿对等。")

    lines += [
        "",
        "### 2. 🧊 冷战探测器 (Ghosting / Silence Gap)",
        f"- 记录内最长失联跨度：**{gap_desc}**",
    ]
    if max_gap_days >= 1.5:
        lines.append(f"- 最长冷战破冰者：**{icebreaker}** 先开口打破僵局")
    else:
        lines.append("- *该段关系互动高频，无明显断崖失联期。*")

    lines += [
        "",
        "### 3. 🌙 深夜软肋指数 (Late-Night Vulnerability)",
        "> *统计 23:00 - 05:00 荷尔蒙高发时段的消息占比*",
        f"- 我方深夜消息占比：**{me_night_ratio}%**（共 {me_night} 条）",
        f"- 对方深夜消息占比：**{them_night_ratio}%**（共 {them_night} 条）",
        "",
    ]

    # ── 模式相关段落
    if mode == "review":
        # 整体诊断
        gap = abs(me_avg - them_avg)
        if gap > 20:
            diagnosis = f"存在明显的「付出不对等」现象（差距 {gap} 分），长期单方投入更多往往是关系隐患。"
        elif me_current >= them_current + 12:
            diagnosis = f"当前阶段是我方更想推进、对方更偏保留的结构；历史热度并没有延续到现在。"
        elif them_current >= me_current + 12:
            diagnosis = f"当前阶段是对方仍在靠近、而我方更克制，这种错位会让互动显得忽冷忽热。"
        elif me_trend == "📉 下滑" and them_trend == "📉 下滑":
            diagnosis = "双方好感度同步下滑，关系走向疏离，可能源于共同的外部压力或关系倦怠。"
        elif me_trend == "📉 下滑" and them_trend != "📉 下滑":
            diagnosis = f"我方好感度在下滑而对方相对稳定，我方可能先产生了倦怠或失望情绪。"
        elif them_trend == "📉 下滑" and me_trend != "📉 下滑":
            diagnosis = f"对方好感度在下滑，而我方仍在投入，这种错位是关系恶化的常见前兆。"
        else:
            diagnosis = f"当前关系更接近「{score_summary(pair_current)}」，没有明显冲突，但也未见持续升温证据。"

        lines += [
            "---",
            "",
            "## 六、复盘总评",
            "",
            f"**综合评估**：{diagnosis}",
            "",
            "**建议关注的时间节点**（好感度骤降）：",
        ]
        # 找出最大单期跌幅
        drop_windows = []
        for i in range(1, len(scores)):
            me_drop   = scores[i-1]["me"]   - scores[i]["me"]
            them_drop = scores[i-1]["them"] - scores[i]["them"]
            if me_drop > 10 or them_drop > 10:
                drop_windows.append((scores[i]["label"], round(me_drop, 1), round(them_drop, 1)))
        if drop_windows:
            for lbl, md, td in drop_windows[:3]:
                lines.append(f"- {lbl}：我方 -{md} / 对方 -{td}")
        else:
            lines.append("- 未检测到显著骤降节点")
        lines.append("")

    else:  # track
        lines += [
            "---",
            "",
            "## 六、当前趋势与预测",
            "",
            f"- **我方趋势**：{me_trend}",
            f"- **对方趋势**：{them_trend}",
            "",
        ]
        if me_trend == "📈 上升" and them_trend == "📈 上升":
            lines.append("✅ 双方好感度同步上升，关系正在升温，继续保持。")
        elif me_trend == "📉 下滑" or them_trend == "📉 下滑":
            lines.append("⚠️ 检测到下滑趋势，建议追加最新聊天记录后动态评估。")
        else:
            lines.append("ℹ️ 当前关系处于稳定维系状态，建议定期追加记录观察趋势。")
        lines.append("")
        lines += [
            "**如何追加更新**：",
            "```",
            "/heartbeat-update — 追加新聊天记录，自动更新分析",
            "```",
        ]

    lines += [
        "",
        "---",
        "",
        f"*报告由 Heartbeat 自动生成 · 数据基于{total_msgs}条聊天记录*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="好感度分析文字报告生成器")
    parser.add_argument("--scores",  required=True, help="sentiment_scorer.py 输出 JSON")
    parser.add_argument("--parsed",  required=True, help="chat_parser.py 输出 JSON")
    parser.add_argument("--me",      required=True, help="我方昵称")
    parser.add_argument("--them",    required=True, help="对方昵称")
    parser.add_argument("--mode",    default="review", choices=["review", "track"])
    parser.add_argument("--output",  default=None, help="输出 MD 路径（默认 stdout）")
    args = parser.parse_args()

    scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    parsed = json.loads(Path(args.parsed).read_text(encoding="utf-8"))

    if not scores:
        print("错误：评分数据为空。"); return

    report = generate_report(scores, parsed, args.me, args.them, args.mode)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"✅ 报告已生成：{out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
