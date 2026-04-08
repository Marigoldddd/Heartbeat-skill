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

try:
    from snownlp import SnowNLP
    HAS_SNOWNLP = True
except Exception:
    SnowNLP = None
    HAS_SNOWNLP = False

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


def group_by_session(messages: list[dict], gap_minutes: int) -> dict[str, list[dict]]:
    """按会话切分：相邻两条消息间隔超过阈值即开启新 session。"""
    valid_msgs = [m for m in messages if m.get("ts")]
    if not valid_msgs:
        return {}

    valid_msgs = sorted(valid_msgs, key=lambda m: m.get("ts") or "")
    sessions: dict[str, list[dict]] = {}

    session_index = 1
    current_key = f"S{session_index:04d}"
    sessions[current_key] = [valid_msgs[0]]
    prev_dt = datetime.fromisoformat(valid_msgs[0]["ts"])

    for msg in valid_msgs[1:]:
        cur_dt = datetime.fromisoformat(msg["ts"])
        gap = (cur_dt - prev_dt).total_seconds() / 60
        if gap > gap_minutes:
            session_index += 1
            current_key = f"S{session_index:04d}"
            sessions[current_key] = []
        sessions[current_key].append(msg)
        prev_dt = cur_dt

    return sessions


def get_session_label(session_msgs: list[dict], session_key: str) -> str:
    """session 标签使用该会话首条消息日期，便于与绘图脚本兼容。"""
    if not session_msgs:
        return session_key
    first_ts = session_msgs[0].get("ts") or ""
    if not first_ts:
        return session_key
    try:
        return datetime.fromisoformat(first_ts).strftime("%Y-%m-%d")
    except Exception:
        return session_key


# ─────────────────────────────────────────────
# 维度评分函数
# ─────────────────────────────────────────────

def score_sentiment_lexicon(messages: list[dict]) -> float:
    """情感词密度评分（词典法）→ 0-100。"""
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


def score_sentiment_snownlp(messages: list[dict]) -> float:
    """SnowNLP 情感评分（0~1）映射到 0~100。"""
    if not messages:
        return 50.0
    if not HAS_SNOWNLP:
        return score_sentiment_lexicon(messages)

    vals = []
    for m in messages:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        try:
            polarity = float(SnowNLP(content).sentiments)
            vals.append(max(0.0, min(1.0, polarity)))
        except Exception:
            continue

    if not vals:
        return 50.0

    return round(sum(vals) / len(vals) * 100, 2)


def score_sentiment(messages: list[dict], backend: str = "auto") -> float:
    """可插拔情感评分入口。"""
    if backend == "lexicon":
        return score_sentiment_lexicon(messages)
    if backend == "snownlp":
        return score_sentiment_snownlp(messages)
    # auto: 优先 SnowNLP，不可用时回退词典法
    if HAS_SNOWNLP:
        return score_sentiment_snownlp(messages)
    return score_sentiment_lexicon(messages)


def score_length(messages: list[dict]) -> float:
    """平均消息长度评分 → 0-100（长消息表示投入更多）。"""
    if not messages:
        return 50.0
    avg_len = sum(m.get("len", 0) for m in messages) / len(messages)
    # 5字以下→低分，50字以上→高分，log 缩放
    score = min(100.0, math.log1p(avg_len) / math.log1p(80) * 100)
    return max(0.0, score)


def score_special(messages: list[dict]) -> float:
    """特殊行为得分 → 0-100（文本互动 + 多媒体分享 + 通话投入）。"""
    if not messages:
        return 50.0
    n = len(messages)
    q_rate    = sum(1 for m in messages if m.get("has_question")) / n
    emoji_rate = sum(1 for m in messages if m.get("has_emoji")) / n
    aff_rate   = sum(1 for m in messages if m.get("has_affection_call")) / n
    image_rate = sum(1 for m in messages if m.get("has_image_share")) / n
    voice_rate = sum(1 for m in messages if m.get("has_voice_msg")) / n
    video_rate = sum(1 for m in messages if m.get("has_video_share")) / n
    location_rate = sum(1 for m in messages if m.get("has_location_share")) / n
    call_rate = sum(1 for m in messages if m.get("has_call")) / n
    avg_call_min = sum((m.get("call_duration_sec") or 0) for m in messages) / 60 / n
    call_duration_norm = min(1.0, avg_call_min / 10)  # 平均 10 分钟视作高投入

    weighted_sum = (
        q_rate * 20 +
        emoji_rate * 20 +
        aff_rate * 20 +
        image_rate * 12 +
        voice_rate * 10 +
        video_rate * 8 +
        location_rate * 5 +
        call_rate * 10 +
        call_duration_norm * 15
    )
    # 上式满分 120，线性映射到 0-100
    return max(0.0, min(100.0, weighted_sum / 120 * 100))


def score_media_engagement(messages: list[dict]) -> float:
    """多媒体互动投入得分（图片/语音/视频/位置/通话时长）。"""
    if not messages:
        return 50.0
    n = len(messages)
    image_rate = sum(1 for m in messages if m.get("has_image_share")) / n
    voice_rate = sum(1 for m in messages if m.get("has_voice_msg")) / n
    video_rate = sum(1 for m in messages if m.get("has_video_share")) / n
    location_rate = sum(1 for m in messages if m.get("has_location_share")) / n
    call_rate = sum(1 for m in messages if m.get("has_call")) / n
    avg_call_min = sum((m.get("call_duration_sec") or 0) for m in messages) / 60 / n
    call_duration_norm = min(1.0, avg_call_min / 10)

    weighted_sum = (
        image_rate * 28 +
        voice_rate * 20 +
        video_rate * 15 +
        location_rate * 10 +
        call_rate * 12 +
        call_duration_norm * 15
    )
    return max(0.0, min(100.0, weighted_sum))


def parse_special_days_arg(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {d.strip() for d in raw.split(",") if d.strip()}


def parse_special_days_file(path: str | None) -> set[str]:
    if not path:
        return set()
    p = Path(path)
    if not p.exists():
        print(f"[scorer] 警告：special days 文件不存在：{p}", file=sys.stderr)
        return set()

    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return set()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {str(x).strip() for x in data if str(x).strip()}
    except Exception:
        pass

    days = set()
    for line in text.splitlines():
        s = line.strip()
        if s:
            days.add(s)
    return days


def apply_special_day_multiplier(score: float, multiplier: float) -> float:
    """强化特殊日期上的情绪偏移：以 50 为中轴放大波动。"""
    adjusted = 50 + (score - 50) * multiplier
    return max(0.0, min(100.0, adjusted))


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


def score_window(window_msgs: list[dict], sentiment_backend: str = "auto") -> dict:
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
    me_sent_score   = score_sentiment(me_msgs, backend=sentiment_backend)
    them_sent_score = score_sentiment(them_msgs, backend=sentiment_backend)

    # 特殊行为
    me_spe_score   = score_special(me_msgs)
    them_spe_score = score_special(them_msgs)
    me_media_score = score_media_engagement(me_msgs)
    them_media_score = score_media_engagement(them_msgs)

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
            "me_media":      round(me_media_score, 1),
            "them_initiative": round(them_initiative_score, 1),
            "them_reply":      round(them_reply_score, 1),
            "them_length":     round(them_len_score, 1),
            "them_sentiment":  round(them_sent_score, 1),
            "them_special":    round(them_spe_score, 1),
            "them_media":      round(them_media_score, 1),
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
                        choices=["auto", "day", "week", "month", "session"],
                        help="时间窗口粒度（默认 auto：按记录跨度自动选择）")
    parser.add_argument("--session-gap-minutes", type=int, default=180,
                        help="仅在 window=session 时生效：超过该静默分钟数切分为新会话（默认 180）")
    parser.add_argument("--sentiment-backend", default="auto",
                        choices=["auto", "lexicon", "snownlp"],
                        help="情感评分后端：auto(默认)/lexicon/snownlp")
    parser.add_argument("--special-days", default="",
                        help="特殊日期列表（逗号分隔，YYYY-MM-DD），如 2026-02-14,2026-12-31")
    parser.add_argument("--special-days-file", default=None,
                        help="特殊日期文件路径（JSON 数组或每行一个日期）")
    parser.add_argument("--special-day-multiplier", type=float, default=1.2,
                        help="特殊日期情绪波动放大倍数（默认 1.2）")
    parser.add_argument("--smooth", action="store_true", default=True,
                        help="是否对曲线做 EMA 平滑（默认开启）")
    parser.add_argument("--no-smooth", dest="smooth", action="store_false")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认 stdout）")
    args = parser.parse_args()

    messages = json.loads(Path(args.input).read_text(encoding="utf-8"))

    window = args.window if args.window != "auto" else auto_window(messages)
    print(f"[scorer] 使用时间窗口：{window}", file=sys.stderr)
    if args.sentiment_backend == "snownlp" and not HAS_SNOWNLP:
        print("[scorer] 未检测到 SnowNLP，自动回退 lexicon 后端", file=sys.stderr)
    elif args.sentiment_backend == "auto":
        backend_used = "snownlp" if HAS_SNOWNLP else "lexicon"
        print(f"[scorer] 情感后端：{backend_used}", file=sys.stderr)
    else:
        print(f"[scorer] 情感后端：{args.sentiment_backend}", file=sys.stderr)

    special_days = parse_special_days_arg(args.special_days)
    special_days |= parse_special_days_file(args.special_days_file)
    if special_days:
        print(f"[scorer] 特殊日期加权：{len(special_days)} 天，倍率 {args.special_day_multiplier}", file=sys.stderr)

    # 按窗口分组
    if window == "session":
        groups = group_by_session(messages, args.session_gap_minutes)
    else:
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
        scores = score_window(w_msgs, sentiment_backend=args.sentiment_backend)
        label = get_session_label(w_msgs, key) if window == "session" else get_window_label(key, window)

        window_days = set()
        for m in w_msgs:
            ts = m.get("ts") or ""
            if len(ts) >= 10:
                window_days.add(ts[:10])
        has_special_day = bool(window_days & special_days)

        me_value = scores["me"]
        them_value = scores["them"]
        if has_special_day and args.special_day_multiplier > 0:
            me_value = round(apply_special_day_multiplier(me_value, args.special_day_multiplier), 1)
            them_value = round(apply_special_day_multiplier(them_value, args.special_day_multiplier), 1)

        results.append({
            "window": key,
            "label": label,
            "me":   me_value,
            "them": them_value,
            "me_msg_count":    scores["me_msg_count"],
            "them_msg_count":  scores["them_msg_count"],
            "me_initiative":   scores["me_initiative"],
            "them_initiative": scores["them_initiative"],
            "events": [],
            "raw": {
                **scores["raw"],
                "has_special_day": has_special_day,
                "special_day_multiplier": args.special_day_multiplier if has_special_day else 1.0,
            },
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
