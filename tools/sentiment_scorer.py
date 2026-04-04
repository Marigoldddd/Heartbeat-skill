#!/usr/bin/env python3
"""
sentiment_scorer.py — 好感度双向评分引擎

输入：chat_parser.py 输出的 JSON（list of message dicts）
输出：按时间窗口的评分 JSON

用法：
    python3 sentiment_scorer.py --input parsed.json --window week --output scores.json
    python3 sentiment_scorer.py --input parsed.json --window month --output scores.json
    python3 sentiment_scorer.py --input parsed.json --window day --output scores.json

输出格式：
    [
      {
        "window": "2024-W01",
        "label": "2024-01-01",
        "me":   72.5,
        "them": 63.1,
        "me_msg_count":   15,
        "them_msg_count": 12,
        "me_initiative":  0.55,   ← 我先发消息的对话数 / 总对话数
        "them_initiative": 0.45,
        "events": [],              ← 由 AI 标注，此处留空
        "raw": { ... }            ← 各维度得分（调试用）
      },
      ...
    ]
"""

import json
import sys
import math
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ─────────────────────────────────────────────
# 情感词表
# ─────────────────────────────────────────────

POSITIVE_WORDS = [
    # 强正向
    "爱你", "想你", "喜欢你", "好想你", "想见你", "最爱", "心疼",
    "幸福", "开心", "高兴", "快乐", "感动", "感谢", "谢谢你",
    "好棒", "好厉害", "真的好", "太好了", "超喜欢", "爱死了",
    "舍不得", "离不开", "在一起", "永远", "一直",
    "宝贝", "亲爱的", "baby", "honey", "dear", "love",
    # 中等正向
    "不错", "好的", "好啊", "嗯嗯", "哈哈", "嘻嘻", "哈哈哈",
    "可以", "没问题", "辛苦了", "加油", "支持你",
    "想到你", "记得你", "惦记", "牵挂",
    "么么", "❤", "♥", "💕", "😊", "😍", "🥰", "😘", "💗",
    # 英文
    "miss you", "love you", "so happy", "thank you", "wonderful",
    "amazing", "awesome", "great", "perfect", "sweet",
]

NEGATIVE_WORDS = [
    # 强负向
    "分手", "不想理", "烦死了", "讨厌你", "滚", "去死",
    "不喜欢", "冷战", "失望", "心寒", "伤心", "难过", "痛苦",
    "后悔", "委屈", "崩溃", "哭了", "绝望", "放弃",
    "不在乎", "无所谓", "随便", "算了", "不用了", "不需要",
    "冷漠", "已读不回", "不回消息",
    # 中等负向
    "生气", "烦", "好烦", "累了", "算了吧", "无语", "无聊",
    "不开心", "郁闷", "难受", "不舒服", "头疼", "烦躁",
    "迟到", "忘了", "没空", "忙", "再说", "下次",
    # 英文
    "angry", "upset", "disappointed", "hurt", "sad",
    "ignore", "whatever", "fine", "forget it", "never mind",
]

# 权重配置
WEIGHTS = {
    "initiative":   0.25,  # 主动性
    "reply_speed":  0.20,  # 回复速度
    "msg_length":   0.15,  # 消息长度
    "sentiment":    0.25,  # 情感词
    "special":      0.15,  # 特殊行为（问题/emoji/亲昵称呼）
}


# ─────────────────────────────────────────────
# 时间窗口分组
# ─────────────────────────────────────────────

def get_window_key(ts_str: str, window: str) -> str | None:
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        return None
    if window == "day":
        return dt.strftime("%Y-%m-%d")
    elif window == "week":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    elif window == "month":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-W%W")


def get_window_label(key: str, window: str) -> str:
    """从 window key 提取人类可读标签（用于 X 轴）。"""
    if window == "day":
        return key
    elif window == "week":
        # "2024-W01" → 该周一的日期
        try:
            year, wk = key.split("-W")
            d = datetime.strptime(f"{year}-W{wk}-1", "%Y-W%W-%w")
            return d.strftime("%Y-%m-%d")
        except Exception:
            return key
    elif window == "month":
        return key + "-01"
    return key


def auto_window(messages: list[dict]) -> str:
    """根据记录跨度自动选择时间粒度。"""
    ts_list = [m["ts"] for m in messages if m.get("ts")]
    if not ts_list:
        return "week"
    try:
        first = datetime.fromisoformat(min(ts_list))
        last  = datetime.fromisoformat(max(ts_list))
        days = (last - first).days
    except Exception:
        return "week"
    if days <= 30:
        return "day"
    elif days <= 365:
        return "week"
    else:
        return "month"


# ─────────────────────────────────────────────
# 维度评分函数
# ─────────────────────────────────────────────

def score_sentiment(messages: list[dict]) -> float:
    """情感词密度评分 → 0-100。"""
    if not messages:
        return 50.0
    total = len(messages)
    pos_hits = neg_hits = 0
    for m in messages:
        content = m.get("content", "")
        pos_hits += sum(1 for w in POSITIVE_WORDS if w in content)
        neg_hits += sum(1 for w in NEGATIVE_WORDS if w in content)
    # 正负相抵，归一化到 0-100
    net = pos_hits - neg_hits * 1.5  # 负向权重更高
    per_msg = net / total
    # sigmoid-like mapping: net_per_msg ∈ [-3, 3] → [0, 100]
    score = 50 + (per_msg / (abs(per_msg) + 1)) * 40
    return max(0.0, min(100.0, score))


def score_length(messages: list[dict]) -> float:
    """平均消息长度评分 → 0-100（长消息表示投入更多）。"""
    if not messages:
        return 50.0
    avg_len = sum(m.get("len", 0) for m in messages) / len(messages)
    # 5字以下→低分，50字以上→高分，log 缩放
    score = min(100.0, math.log1p(avg_len) / math.log1p(80) * 100)
    return max(0.0, score)


def score_special(messages: list[dict]) -> float:
    """特殊行为得分 → 0-100（问题/emoji/亲昵称呼）。"""
    if not messages:
        return 50.0
    n = len(messages)
    q_rate    = sum(1 for m in messages if m.get("has_question")) / n
    emoji_rate = sum(1 for m in messages if m.get("has_emoji")) / n
    aff_rate   = sum(1 for m in messages if m.get("has_affection_call")) / n
    # 各维度权重
    raw = (q_rate * 35 + emoji_rate * 35 + aff_rate * 30)
    return max(0.0, min(100.0, raw * 100))


def score_reply_speed(me_msgs: list[dict], them_msgs: list[dict],
                       side: str) -> float:
    """
    回复速度评分：计算一方对另一方的平均回复时延。
    side = "me" 时，计算「我回复TA」的速度。
    """
    if side == "me":
        senders = (me_msgs, them_msgs)  # them 发 → me 回
        triggerside, replyside = "them", "me"
    else:
        senders = (them_msgs, me_msgs)
        triggerside, replyside = "me", "them"

    all_msgs_sorted = sorted(me_msgs + them_msgs, key=lambda m: m.get("ts") or "")
    if len(all_msgs_sorted) < 2:
        return 60.0

    delays = []
    for i in range(1, len(all_msgs_sorted)):
        prev = all_msgs_sorted[i - 1]
        cur  = all_msgs_sorted[i]
        if prev.get("sender") == triggerside and cur.get("sender") == replyside:
            if prev.get("ts") and cur.get("ts"):
                try:
                    t1 = datetime.fromisoformat(prev["ts"])
                    t2 = datetime.fromisoformat(cur["ts"])
                    delta = (t2 - t1).total_seconds() / 60  # 分钟
                    if 0 < delta < 1440:  # 只计算 24h 内的回复
                        delays.append(delta)
                except Exception:
                    pass

    if not delays:
        return 60.0

    avg_min = sum(delays) / len(delays)
    # 1 分钟内→100，60分钟→60，240分钟→30，≥480分钟→0
    if avg_min <= 1:
        return 100.0
    elif avg_min <= 60:
        return 100 - (avg_min - 1) / 59 * 40
    elif avg_min <= 240:
        return 60 - (avg_min - 60) / 180 * 30
    else:
        return max(0.0, 30 - (avg_min - 240) / 240 * 30)


# ─────────────────────────────────────────────
# 主评分逻辑
# ─────────────────────────────────────────────

def compute_initiative(window_msgs: list[dict]) -> tuple[float, float]:
    """
    计算主动性：把消息按「对话段」分组，
    对话段 = 两条消息间隔 > 30分钟视为新对话。
    统计每段对话是谁先发消息。
    """
    if not window_msgs:
        return 0.5, 0.5

    sorted_msgs = sorted(window_msgs, key=lambda m: m.get("ts") or "")
    conversations = []
    current_conv = [sorted_msgs[0]]

    for i in range(1, len(sorted_msgs)):
        prev, cur = sorted_msgs[i - 1], sorted_msgs[i]
        try:
            gap = (datetime.fromisoformat(cur["ts"]) -
                   datetime.fromisoformat(prev["ts"])).total_seconds() / 60
        except Exception:
            gap = 0
        if gap > 30:
            conversations.append(current_conv)
            current_conv = [cur]
        else:
            current_conv.append(cur)
    conversations.append(current_conv)

    me_init = them_init = 0
    for conv in conversations:
        first_sender = conv[0].get("sender")
        if first_sender == "me":
            me_init += 1
        elif first_sender == "them":
            them_init += 1

    total = me_init + them_init
    if total == 0:
        return 0.5, 0.5
    return me_init / total, them_init / total


def score_window(window_msgs: list[dict]) -> dict:
    """对单个时间窗口计算双方各维度得分并加权合成。"""
    me_msgs = [m for m in window_msgs if m.get("sender") == "me"]
    them_msgs = [m for m in window_msgs if m.get("sender") == "them"]

    # 主动性
    me_init_ratio, them_init_ratio = compute_initiative(window_msgs)
    me_initiative_score   = me_init_ratio * 100
    them_initiative_score = them_init_ratio * 100

    # 回复速度
    me_reply_score   = score_reply_speed(me_msgs, them_msgs, side="me")
    them_reply_score = score_reply_speed(me_msgs, them_msgs, side="them")

    # 消息长度
    me_len_score   = score_length(me_msgs)
    them_len_score = score_length(them_msgs)

    # 情感词
    me_sent_score   = score_sentiment(me_msgs)
    them_sent_score = score_sentiment(them_msgs)

    # 特殊行为
    me_spe_score   = score_special(me_msgs)
    them_spe_score = score_special(them_msgs)

    def weighted(init, reply, length, sent, special):
        return (
            init   * WEIGHTS["initiative"] +
            reply  * WEIGHTS["reply_speed"] +
            length * WEIGHTS["msg_length"] +
            sent   * WEIGHTS["sentiment"] +
            special * WEIGHTS["special"]
        )

    me_score   = weighted(me_initiative_score,   me_reply_score,   me_len_score,   me_sent_score,   me_spe_score)
    them_score = weighted(them_initiative_score, them_reply_score, them_len_score, them_sent_score, them_spe_score)

    # 如果某方消息极少，可靠性降低，向 50 回归
    def reliability_adjust(score, count):
        if count == 0:
            return 50.0
        elif count < 3:
            return 50 + (score - 50) * (count / 3)
        return score

    me_score   = reliability_adjust(me_score,   len(me_msgs))
    them_score = reliability_adjust(them_score, len(them_msgs))

    return {
        "me":   round(me_score, 1),
        "them": round(them_score, 1),
        "me_msg_count":    len(me_msgs),
        "them_msg_count":  len(them_msgs),
        "me_initiative":   round(me_init_ratio, 3),
        "them_initiative": round(them_init_ratio, 3),
        "raw": {
            "me_initiative": round(me_initiative_score, 1),
            "me_reply":      round(me_reply_score, 1),
            "me_length":     round(me_len_score, 1),
            "me_sentiment":  round(me_sent_score, 1),
            "me_special":    round(me_spe_score, 1),
            "them_initiative": round(them_initiative_score, 1),
            "them_reply":      round(them_reply_score, 1),
            "them_length":     round(them_len_score, 1),
            "them_sentiment":  round(them_sent_score, 1),
            "them_special":    round(them_spe_score, 1),
        }
    }


# ─────────────────────────────────────────────
# EMA 平滑
# ─────────────────────────────────────────────

def ema_smooth(values: list[float], alpha: float = 0.3) -> list[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="好感度双向评分引擎")
    parser.add_argument("--input",  required=True, help="chat_parser.py 输出的 JSON 文件路径")
    parser.add_argument("--window", default="auto",
                        choices=["auto", "day", "week", "month"],
                        help="时间窗口粒度（默认 auto：按记录跨度自动选择）")
    parser.add_argument("--smooth", action="store_true", default=True,
                        help="是否对曲线做 EMA 平滑（默认开启）")
    parser.add_argument("--no-smooth", dest="smooth", action="store_false")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认 stdout）")
    args = parser.parse_args()

    messages = json.loads(Path(args.input).read_text(encoding="utf-8"))

    window = args.window if args.window != "auto" else auto_window(messages)
    print(f"[scorer] 使用时间窗口：{window}", file=sys.stderr)

    # 按窗口分组
    groups: dict[str, list[dict]] = defaultdict(list)
    for msg in messages:
        key = get_window_key(msg.get("ts") or "", window)
        if key:
            groups[key].append(msg)

    if not groups:
        print("错误：没有可分析的时间窗口，请检查消息的时间格式。", file=sys.stderr)
        sys.exit(1)

    # 计算各窗口得分
    windows_sorted = sorted(groups.keys())
    results = []
    for key in windows_sorted:
        w_msgs = groups[key]
        scores = score_window(w_msgs)
        results.append({
            "window": key,
            "label": get_window_label(key, window),
            "me":   scores["me"],
            "them": scores["them"],
            "me_msg_count":    scores["me_msg_count"],
            "them_msg_count":  scores["them_msg_count"],
            "me_initiative":   scores["me_initiative"],
            "them_initiative": scores["them_initiative"],
            "events": [],
            "raw": scores["raw"],
        })

    # EMA 平滑
    if args.smooth and len(results) >= 3:
        me_vals   = ema_smooth([r["me"]   for r in results])
        them_vals = ema_smooth([r["them"] for r in results])
        for i, r in enumerate(results):
            r["me"]   = round(me_vals[i], 1)
            r["them"] = round(them_vals[i], 1)

    output_json = json.dumps(results, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        me_avg   = round(sum(r["me"]   for r in results) / len(results), 1)
        them_avg = round(sum(r["them"] for r in results) / len(results), 1)
        print(f"✅ 评分完成：{len(results)} 个时间窗口")
        print(f"   我方平均好感度：{me_avg}  |  对方平均好感度：{them_avg}")
        print(f"   输出：{args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
