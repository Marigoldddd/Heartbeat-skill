import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools.chat_parser import parse_wechat_txt, normalize
from tools.cc_window_preparer import prepare_windows
from tools.report_writer import generate_report
from tools.score_merger import merge_scores
from tools.sentiment_scorer import group_by_session, apply_special_day_multiplier, score_special, score_window
import tools.sentiment_scorer as scorer


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
            parsed, _ = normalize(raw, "我", "鑫月姐0205")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["sender"], "me")
        self.assertEqual(parsed[1]["sender"], "them")
        self.assertEqual(parsed[1]["ts"], "2023-05-06T22:14:21")

    def test_mask_sensitive_replaces_common_pii(self):
        raw = [{
            "time_str": "2024-01-01 10:00:00",
            "raw_sender": "我",
            "content": "我手机号13800138000，住在北京市朝阳区幸福路88号，转你￥520.00",
        }]

        parsed, masked_count = normalize(raw, "我", "TA", mask_sensitive=True)

        self.assertEqual(len(parsed), 1)
        self.assertGreater(masked_count, 0)
        self.assertIn("[手机号]", parsed[0]["content"])
        self.assertIn("[地点]", parsed[0]["content"])
        self.assertIn("[金额]", parsed[0]["content"])

    def test_multimedia_messages_are_kept_as_signals(self):
        raw = [
            {
                "time_str": "2024-01-01 10:00:00",
                "raw_sender": "我",
                "content": "[图片]",
            },
            {
                "time_str": "2024-01-01 10:03:00",
                "raw_sender": "TA",
                "content": "语音通话 12:30",
            },
        ]

        parsed, _ = normalize(raw, "我", "TA")

        self.assertEqual(len(parsed), 2)
        self.assertTrue(parsed[0]["has_image_share"])
        self.assertTrue(parsed[1]["has_call"])
        self.assertGreater(parsed[1]["call_duration_sec"], 0)

    def test_special_score_increases_with_media_and_call_signals(self):
        base = [{"has_question": False, "has_emoji": False, "has_affection_call": False}]
        rich = [{
            "has_question": True,
            "has_emoji": True,
            "has_affection_call": True,
            "has_image_share": True,
            "has_voice_msg": True,
            "has_video_share": False,
            "has_location_share": True,
            "has_call": True,
            "call_duration_sec": 900,
        }]

        self.assertGreater(score_special(rich), score_special(base))

    def test_score_window_contains_raw_media_metrics(self):
        msgs = [
            {
                "ts": "2024-01-01T10:00:00",
                "sender": "me",
                "content": "[图片]",
                "len": 4,
                "has_question": False,
                "has_emoji": False,
                "has_affection_call": False,
                "has_image_share": True,
                "has_voice_msg": False,
                "has_video_share": False,
                "has_location_share": False,
                "has_call": False,
                "call_duration_sec": 0,
            },
            {
                "ts": "2024-01-01T10:03:00",
                "sender": "them",
                "content": "语音通话 12:30",
                "len": 10,
                "has_question": False,
                "has_emoji": False,
                "has_affection_call": False,
                "has_image_share": False,
                "has_voice_msg": False,
                "has_video_share": False,
                "has_location_share": False,
                "has_call": True,
                "call_duration_sec": 750,
            },
        ]

        s = score_window(msgs, sentiment_backend="lexicon")
        self.assertIn("me_media", s["raw"])
        self.assertIn("them_media", s["raw"])

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

    def test_session_window_keeps_cross_midnight_chat_together(self):
        msgs = [
            {"ts": "2024-01-01T23:30:00", "sender": "me"},
            {"ts": "2024-01-02T00:20:00", "sender": "them"},
            {"ts": "2024-01-02T01:10:00", "sender": "me"},
        ]
        groups = group_by_session(msgs, gap_minutes=180)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups["S0001"]), 3)

    def test_session_window_splits_when_gap_exceeds_threshold(self):
        msgs = [
            {"ts": "2024-01-01T23:30:00", "sender": "me"},
            {"ts": "2024-01-02T00:20:00", "sender": "them"},
            {"ts": "2024-01-02T04:30:00", "sender": "me"},
        ]
        groups = group_by_session(msgs, gap_minutes=180)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups["S0001"]), 2)
        self.assertEqual(len(groups["S0002"]), 1)

    def test_cc_window_preparer_truncates_when_token_budget_exceeded(self):
        parsed = []
        for i in range(40):
            parsed.append({
                "ts": f"2024-01-01T10:{i:02d}:00",
                "sender": "me" if i % 2 == 0 else "them",
                "content": "我真的很在乎这段关系，我们能不能好好聊聊" * 6,
            })

        rule_scores = [{
            "window": "2024-W01",
            "label": "2024-01-01",
            "me": 60,
            "them": 58,
            "events": [],
            "raw": {},
        }]

        data = prepare_windows(parsed, rule_scores, max_window_tokens=300, headroom_tokens=100)
        w = data["windows"][0]
        self.assertTrue(w["meta"]["truncated"])
        self.assertLess(w["meta"]["selected_count"], w["meta"]["message_count"])
        self.assertLessEqual(w["meta"]["used_tokens"], w["meta"]["budget_tokens"])

    def test_sentiment_auto_falls_back_to_lexicon_when_snownlp_missing(self):
        msgs = [{"content": "我很开心"}, {"content": "今天不错"}]

        with mock.patch.object(scorer, "HAS_SNOWNLP", False):
            auto_score = scorer.score_sentiment(msgs, backend="auto")
            lex_score = scorer.score_sentiment(msgs, backend="lexicon")

        self.assertEqual(auto_score, lex_score)

    def test_sentiment_snownlp_backend_uses_model_output(self):
        msgs = [{"content": "测试文本"}]

        class DummySnow:
            def __init__(self, _text):
                self.sentiments = 0.85

        with mock.patch.object(scorer, "HAS_SNOWNLP", True), \
             mock.patch.object(scorer, "SnowNLP", DummySnow):
            score = scorer.score_sentiment(msgs, backend="snownlp")

        self.assertEqual(score, 85.0)

    def test_special_day_multiplier_amplifies_distance_from_neutral(self):
        self.assertEqual(apply_special_day_multiplier(50, 1.5), 50.0)
        self.assertGreater(apply_special_day_multiplier(70, 1.5), 70)
        self.assertLess(apply_special_day_multiplier(30, 1.5), 30)

    def test_report_contains_media_engagement_row(self):
        scores = [
            {
                "window": "2024-01",
                "label": "2024-01-01",
                "me": 62.0,
                "them": 59.0,
                "me_initiative": 0.5,
                "them_initiative": 0.5,
                "events": [],
                "raw": {
                    "me_reply": 70,
                    "them_reply": 68,
                    "me_sentiment": 60,
                    "them_sentiment": 58,
                    "me_length": 55,
                    "them_length": 50,
                    "me_media": 72,
                    "them_media": 64,
                },
            }
        ]
        parsed = [
            {"sender": "me", "len": 10, "ts": "2024-01-01T10:00:00"},
            {"sender": "them", "len": 8, "ts": "2024-01-01T10:05:00"},
        ]

        report = generate_report(scores, parsed, "我", "TA", "review")
        self.assertIn("生活分享/多媒体投入", report)


if __name__ == "__main__":
    unittest.main()
