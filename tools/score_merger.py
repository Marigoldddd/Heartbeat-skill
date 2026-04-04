#!/usr/bin/env python3
"""
score_merger.py — 规则分数 + CC 语义分数融合工具

用法：
    python3 score_merger.py --rule rule_scores.json --cc cc_scores.json --output scores.json
    python3 score_merger.py --rule rule_scores.json --cc cc_scores.json --rule-weight 0.4 --output scores.json

融合策略：
    final = cc_weight * cc_score + rule_weight * rule_score
    默认：CC 权重 0.6，规则权重 0.4

当 CC 分数的 confidence="low" 时，自动提升规则权重（0.6 规则 + 0.4 CC）。
当某方 CC 分数为 null 时，直接使用规则分数。
"""

import json
import argparse
import sys
from pathlib import Path


def merge_scores(rule_scores: list[dict], cc_scores: list[dict],
                 rule_weight: float = 0.4, cc_weight: float = 0.6) -> list[dict]:
    # 以规则分数的窗口列表为主干，CC 分数作为补充
    cc_map = {s["window"]: s for s in cc_scores}

    results = []
    for r in rule_scores:
        window = r["window"]
        c = cc_map.get(window, {})

        # 根据 confidence 动态调整权重
        confidence = c.get("confidence", "medium")
        if confidence == "low":
            eff_cc_w, eff_rule_w = 0.3, 0.7
        elif confidence == "high":
            eff_cc_w, eff_rule_w = cc_weight, rule_weight
        else:
            eff_cc_w, eff_rule_w = 0.5, 0.5

        def blend(rule_val, cc_val):
            if cc_val is None:
                return rule_val
            if rule_val is None:
                return cc_val
            return round(eff_cc_w * cc_val + eff_rule_w * rule_val, 1)

        me_final   = blend(r.get("me"),   c.get("me_cc"))
        them_final = blend(r.get("them"), c.get("them_cc"))

        # 合并 events（规则层不产生 events，以 CC 层为主）
        events = c.get("events", r.get("events", []))

        result = {
            "window": window,
            "label":  r.get("label", window),
            "me":     me_final,
            "them":   them_final,
            "me_msg_count":    r.get("me_msg_count", 0),
            "them_msg_count":  r.get("them_msg_count", 0),
            "me_initiative":   r.get("me_initiative", 0.5),
            "them_initiative": r.get("them_initiative", 0.5),
            "events": events,
            # 保留各层原始分（调试用）
            "raw": {
                **r.get("raw", {}),
                "me_cc":        c.get("me_cc"),
                "them_cc":      c.get("them_cc"),
                "me_reasoning": c.get("me_reasoning", ""),
                "them_reasoning": c.get("them_reasoning", ""),
                "confidence":   confidence,
                "weights_used": f"cc={eff_cc_w}/rule={eff_rule_w}",
            }
        }
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="规则分数 + CC 语义分数融合器")
    parser.add_argument("--rule",         required=True, help="sentiment_scorer.py 输出的规则分数 JSON")
    parser.add_argument("--cc",           required=True, help="CC 语义评分 JSON")
    parser.add_argument("--rule-weight",  type=float, default=0.4, help="规则层权重（默认 0.4）")
    parser.add_argument("--output",       default=None, help="输出路径（默认 stdout）")
    args = parser.parse_args()

    rule_scores = json.loads(Path(args.rule).read_text(encoding="utf-8"))
    cc_scores   = json.loads(Path(args.cc).read_text(encoding="utf-8"))

    cc_weight = 1.0 - args.rule_weight
    merged = merge_scores(rule_scores, cc_scores, args.rule_weight, cc_weight)

    output_json = json.dumps(merged, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"✅ 融合完成：{len(merged)} 个窗口（CC 权重 {cc_weight:.0%} / 规则权重 {args.rule_weight:.0%}）")
        print(f"   输出：{args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
