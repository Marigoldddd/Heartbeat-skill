#!/usr/bin/env python3
"""
cc_window_preparer.py — 为语义层准备窗口数据（含 token 估算与超限抽样）

用法：
    python3 cc_window_preparer.py \
      --parsed /tmp/heartbeat_parsed.json \
      --rule /tmp/rule_scores.json \
      --output /tmp/heartbeat_windows.json

可选参数：
    --max-window-tokens 3200     # 单窗口最大估算 token
    --headroom-tokens 400        # 预留给系统提示/输出的 token 空间
"""

import json
import math
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

EMOTION_HINT_WORDS = [
    "爱你", "想你", "喜欢", "分手", "讨厌", "失望", "难过", "开心", "生气", "委屈",
    "破防", "下头", "绝绝子", "冷战", "算了", "不用了", "抱抱", "亲亲",
]


def estimate_text_tokens(text: str) -> int:
    """
    轻量估算：
    - CJK 字符按 1 token
    - ASCII 字符按 0.25 token
    - 再加少量结构开销
    """
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ascii_chars = max(0, len(text) - cjk)
    est = cjk + ascii_chars * 0.25
    return max(1, int(math.ceil(est + 2)))


def parse_date_label(label: str):
    try:
        return datetime.strptime(label[:10], "%Y-%m-%d")
    except Exception:
        return None


def assign_messages_to_windows(parsed: list[dict], rule_scores: list[dict]) -> dict[str, list[dict]]:
    """按规则层窗口标签将消息归入最近窗口。"""
    ordered = []
    for r in rule_scores:
        dt = parse_date_label(r.get("label", ""))
        if dt is not None:
            ordered.append((dt, r["window"]))

    if not ordered:
        return {}

    ordered.sort(key=lambda x: x[0])
    groups = defaultdict(list)

    for msg in parsed:
        ts = msg.get("ts") or ""
        try:
            msg_dt = datetime.fromisoformat(ts)
        except Exception:
            continue

        best_window = ordered[0][1]
        for dt, window in ordered:
            if msg_dt >= dt:
                best_window = window
            else:
                break

        groups[best_window].append({
            "sender": msg.get("sender"),
            "content": msg.get("content", ""),
            "ts": ts,
        })

    return groups


def _message_priority(msg: dict, idx: int, total: int) -> float:
    content = msg.get("content", "")
    score = 1.0

    # 最近消息优先（保留阶段尾部语气）
    if total > 1:
        score += idx / (total - 1)

    # 长消息通常信息密度更高
    if len(content) >= 30:
        score += 0.6

    # 情绪波动线索
    if any(w in content for w in EMOTION_HINT_WORDS):
        score += 0.9
    if any(p in content for p in ["!", "！", "?", "？", "...", "…"]):
        score += 0.4

    # 深夜对话可作为关系强信号
    ts = msg.get("ts") or ""
    try:
        hour = datetime.fromisoformat(ts).hour
        if hour >= 23 or hour < 5:
            score += 0.7
    except Exception:
        pass

    return score


def shrink_window_messages(messages: list[dict], budget_tokens: int) -> tuple[list[dict], bool, int]:
    """超限窗口抽样：保留首尾锚点 + 高优先级消息，最后按时间还原。"""
    if not messages:
        return [], False, 0

    message_costs = [estimate_text_tokens(f"{m.get('sender','')}: {m.get('content','')}") for m in messages]
    total = sum(message_costs)
    if total <= budget_tokens:
        return messages, False, total

    n = len(messages)
    anchor_bonus = {0: 2.0, n - 1: 2.0}

    first_me = next((i for i, m in enumerate(messages) if m.get("sender") == "me"), None)
    first_them = next((i for i, m in enumerate(messages) if m.get("sender") == "them"), None)
    if first_me is not None:
        anchor_bonus[first_me] = anchor_bonus.get(first_me, 0.0) + 1.2
    if first_them is not None:
        anchor_bonus[first_them] = anchor_bonus.get(first_them, 0.0) + 1.2

    ranked = sorted(
        range(n),
        key=lambda i: _message_priority(messages[i], i, n) + anchor_bonus.get(i, 0.0),
        reverse=True,
    )

    chosen = set()
    used = 0
    for i in ranked:
        c = message_costs[i]
        if used + c > budget_tokens:
            continue
        chosen.add(i)
        used += c

    # 极端小预算下，至少保留一条成本最低的消息
    if not chosen:
        min_i = min(range(n), key=lambda i: message_costs[i])
        chosen.add(min_i)
        used = message_costs[min_i]

    selected = [messages[i] for i in sorted(chosen)]
    return selected, True, used


def prepare_windows(parsed: list[dict], rule_scores: list[dict], max_window_tokens: int, headroom_tokens: int) -> dict:
    groups = assign_messages_to_windows(parsed, rule_scores)
    budget = max(200, max_window_tokens - headroom_tokens)

    windows = []
    for r in rule_scores:
        window = r["window"]
        label = r.get("label", window)
        msgs = groups.get(window, [])

        selected, truncated, used_tokens = shrink_window_messages(msgs, budget_tokens=budget)
        estimated_tokens = sum(estimate_text_tokens(f"{m.get('sender','')}: {m.get('content','')}") for m in msgs)

        windows.append({
            "window": window,
            "label": label,
            "messages": selected,
            "meta": {
                "estimated_tokens": estimated_tokens,
                "used_tokens": used_tokens,
                "message_count": len(msgs),
                "selected_count": len(selected),
                "truncated": truncated,
                "budget_tokens": budget,
            },
        })

    return {"windows": windows}


def main():
    parser = argparse.ArgumentParser(description="为 CC 语义层准备窗口数据（含 token 控制）")
    parser.add_argument("--parsed", required=True, help="chat_parser.py 输出文件")
    parser.add_argument("--rule", required=True, help="sentiment_scorer.py 输出文件")
    parser.add_argument("--output", required=True, help="输出窗口文件（供 CC 语义层读取）")
    parser.add_argument("--max-window-tokens", type=int, default=3200,
                        help="每个窗口的最大估算 token（默认 3200）")
    parser.add_argument("--headroom-tokens", type=int, default=400,
                        help="预留给系统提示与输出的 token（默认 400）")
    args = parser.parse_args()

    parsed = json.loads(Path(args.parsed).read_text(encoding="utf-8"))
    rule_scores = json.loads(Path(args.rule).read_text(encoding="utf-8"))

    data = prepare_windows(
        parsed,
        rule_scores,
        max_window_tokens=args.max_window_tokens,
        headroom_tokens=args.headroom_tokens,
    )

    Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    truncated_count = sum(1 for w in data["windows"] if w["meta"]["truncated"])
    print(f"✅ 已生成 {len(data['windows'])} 个窗口 → {args.output}")
    print(f"   触发超限抽样窗口数：{truncated_count}")


if __name__ == "__main__":
    main()
