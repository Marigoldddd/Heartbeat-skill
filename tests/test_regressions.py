import json
import tempfile
import unittest
from pathlib import Path

from tools.chat_parser import parse_wechat_txt, normalize
from tools.report_writer import generate_report
from tools.score_merger import merge_scores


class HeartbeatRegressionTests(unittest.TestCase):
    def test_wechat_txt_block_format_parses_both_sides(self):
        sample = """2023-05-06 22:13:59 '我'
姐

2023-05-06 22:14:21 '鑫月姐0205'
哦对

2023-05-06 22:14:27 '我'
嗯嗯
"""
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(sample)
            tmp_path = handle.name

        try:
            raw = parse_wechat_txt(tmp_path, "我", "鑫月姐0205")
            parsed = normalize(raw, "我", "鑫月姐0205")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["sender"], "me")
        self.assertEqual(parsed[1]["sender"], "them")
        self.assertEqual(parsed[1]["ts"], "2023-05-06T22:14:21")

    def test_score_merger_keeps_semantic_default_above_eighty_percent(self):
        rule_scores = [{
            "window": "2024-01",
            "label": "2024-01-01",
            "me": 40,
            "them": 40,
            "me_msg_count": 10,
            "them_msg_count": 10,
            "me_initiative": 0.5,
            "them_initiative": 0.5,
            "events": [],
            "raw": {},
        }]
        cc_scores = [{
            "window": "2024-01",
            "me_cc": 90,
            "them_cc": 80,
            "me_reasoning": "主动明显",
            "them_reasoning": "回应积极",
            "events": ["升温"],
            "confidence": "medium",
        }]

        merged = merge_scores(rule_scores, cc_scores, rule_weight=0.2, cc_weight=0.8)

        self.assertEqual(merged[0]["me"], 80.0)
        self.assertEqual(merged[0]["them"], 72.0)
        self.assertEqual(merged[0]["raw"]["weights_used"], "cc=0.8/rule=0.2")

    def test_report_uses_current_window_for_phase_not_historical_average(self):
        scores = [
            {
                "window": "2024-02",
                "label": "2024-02-01",
                "me": 82.0,
                "them": 76.0,
                "me_initiative": 0.6,
                "them_initiative": 0.4,
                "events": ["热络峰值"],
                "raw": {"me_reply": 95, "them_reply": 95, "me_sentiment": 60, "them_sentiment": 62, "me_length": 55, "them_length": 50, "me_reasoning": "高密度投入", "them_reasoning": "亲昵称呼明显"},
            },
            {
                "window": "2025-10",
                "label": "2025-10-01",
                "me": 63.0,
                "them": 46.0,
                "me_initiative": 1.0,
                "them_initiative": 0.0,
                "events": ["边界浮现"],
                "raw": {"me_reply": 95, "them_reply": 90, "me_sentiment": 50, "them_sentiment": 45, "me_length": 50, "them_length": 42, "me_reasoning": "求助靠近明显", "them_reasoning": "愿帮忙但划边界"},
            },
        ]
        parsed = [
            {"sender": "me", "len": 4, "ts": "2024-02-03T13:53:20"},
            {"sender": "them", "len": 4, "ts": "2024-02-03T14:05:04"},
            {"sender": "me", "len": 4, "ts": "2025-10-14T15:43:23"},
            {"sender": "them", "len": 4, "ts": "2025-10-14T15:45:30"},
        ]

        report = generate_report(scores, parsed, "我", "TA", "review")

        self.assertIn("当前窗口得分 63.0 → 处于「稳定期」阶段", report)
        self.assertIn("历史均值 72.5", report)
        self.assertIn("边界浮现", report)


if __name__ == "__main__":
    unittest.main()
