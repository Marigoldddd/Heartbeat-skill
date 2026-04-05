#!/usr/bin/env python3
"""
chat_parser.py — 统一聊天记录解析器（双向版）

此工具同时保留双方消息，
用于主动性对比和回复速度计算。

用法：
    python3 chat_parser.py --file chat.txt --me "小明" --them "小红" --output parsed.json
    python3 chat_parser.py --file chat.db  --me "我" --them "+8613800000000" --format imessage --output parsed.json
    python3 chat_parser.py --file sms.xml  --me "我" --them "小红" --format sms --output parsed.json
    python3 chat_parser.py --file chat.html --me "小明" --them "小红" --format wechat_html --output parsed.json

输出 JSON 格式（list of dict）：
    [
      {
        "ts": "2024-01-05T10:30:00",
        "sender": "me" | "them" | "unknown",
        "raw_sender": "小明",
        "content": "hi，在吗",
        "len": 5,
        "has_question": false,
        "has_emoji": false,
        "has_affection_call": false,  ← 有没有叫对方名字/亲昵称呼
        "sentiment_raw": null          ← 留给 scorer 填入
      },
      ...
    ]
"""

import re
import sys
import csv
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser

# ─────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────

SKIP_PATTERNS = [
    "[图片]", "[文件]", "[撤回了一条消息]", "[语音]", "[视频]",
    "[表情]", "[位置]", "[名片]", "[链接]", "[红包]", "[转账]",
    "[Sticker]", "<img", "<video", "<audio",
    "[Photo]", "[Video]", "[File]", "[Recalled]",
]

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff"
    r"\U0001F300-\U0001F9FF"
    r"\u2600-\u27BF"
    r"\uD83C-\uDBFF\uDC00-\uDFFF"
    r"]+",
    re.UNICODE,
)

QUESTION_ENDINGS = ["？", "?", "吗", "呢", "啊", "嘛", "吧"]

# ─────────────────────────────────────────────
# 格式解析
# ─────────────────────────────────────────────

def parse_wechat_txt(file_path: str, me_name: str, them_name: str) -> list[dict]:
    """解析微信导出 TXT（WechatExporter 等格式）。双向保留所有消息。"""
    messages = []
    line_pattern = re.compile(
        r"^(?P<time>\d{4}[-/]\d{1,2}[-/]\d{1,2}[\s\d:]*)\s+(?P<sender>.+?)[:：]\s*(?P<content>.+)$"
    )
    block_pattern = re.compile(
        r"^(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'(?P<sender>[^']+)'$"
    )
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 兼容微信桌面/第三方工具常见的「时间+发送人单独一行，正文跟在后面」格式
    block_headers = sum(1 for line in lines if block_pattern.match(line.strip()))
    if block_headers:
        idx = 0
        while idx < len(lines):
            header = lines[idx].strip()
            match = block_pattern.match(header)
            if not match:
                idx += 1
                continue

            idx += 1
            content_lines = []
            while idx < len(lines) and not block_pattern.match(lines[idx].strip()):
                raw = lines[idx].rstrip("\n")
                if raw.strip():
                    content_lines.append(raw)
                idx += 1

            content = "\n".join(content_lines).strip()
            if not content:
                continue

            messages.append({
                "time_str": f"{match.group('date')} {match.group('time')}",
                "raw_sender": match.group("sender").strip(),
                "content": content,
            })
        return messages

    current_msg = None
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = line_pattern.match(line)
        if m:
            if current_msg:
                messages.append(current_msg)
            current_msg = {
                "time_str": m.group("time").strip(),
                "raw_sender": m.group("sender").strip(),
                "content": m.group("content").strip(),
            }
        elif current_msg:
            current_msg["content"] += "\n" + line

    if current_msg:
        messages.append(current_msg)

    return messages


def parse_wechat_csv(file_path: str, me_name: str, them_name: str) -> list[dict]:
    messages = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sender = (row.get("sender") or row.get("发送人") or
                      row.get("from") or row.get("NickName") or "")
            content = (row.get("content") or row.get("内容") or
                       row.get("message") or row.get("Message") or "")
            timestamp = (row.get("timestamp") or row.get("时间") or
                         row.get("time") or row.get("StrTime") or "")
            if not content.strip():
                continue
            messages.append({"time_str": str(timestamp), "raw_sender": str(sender), "content": str(content).strip()})
    return messages


class WechatHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.messages = []
        self._sender = ""
        self._time = ""
        self._content = []
        self._in_sender = self._in_content = self._in_time = False

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if "sender" in cls:         self._in_sender = True
        elif "content" in cls or "message-text" in cls: self._in_content = True
        elif "time" in cls or "timestamp" in cls:       self._in_time = True

    def handle_endtag(self, tag):
        if self._in_sender:   self._in_sender = False
        elif self._in_content:
            self._in_content = False
            content = "".join(self._content).strip()
            if content:
                self.messages.append({"time_str": self._time, "raw_sender": self._sender, "content": content})
            self._content = []
        elif self._in_time:   self._in_time = False

    def handle_data(self, data):
        if self._in_sender:   self._sender = data.strip()
        elif self._in_content: self._content.append(data)
        elif self._in_time:   self._time = data.strip()


def parse_wechat_html(file_path: str, me_name: str, them_name: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    p = WechatHTMLParser()
    p.feed(html)
    return p.messages


def parse_imessage(file_path: str, me_name: str, them_name: str) -> list[dict]:
    """解析 iMessage chat.db（SQLite）。"""
    messages = []
    try:
        conn = sqlite3.connect(file_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as ts,
                   m.text, m.is_from_me,
                   COALESCE(h.id, '') as handle
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            WHERE m.text IS NOT NULL AND m.text != ''
            ORDER BY m.date
        """)
        for row in cur.fetchall():
            ts, text, is_me, handle = row
            # Filter to the target contact if them_name given
            if them_name and not is_me and them_name not in str(handle):
                continue
            messages.append({
                "time_str": str(ts),
                "raw_sender": me_name if is_me else (handle or them_name),
                "content": str(text).strip(),
            })
        conn.close()
    except Exception as e:
        print(f"iMessage 解析错误: {e}", file=sys.stderr)
    return messages


def parse_sms_xml(file_path: str, me_name: str, them_name: str) -> list[dict]:
    """解析 Android SMS Backup XML。"""
    messages = []
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(file_path)
        root = tree.getroot()
        for sms in root.findall(".//sms"):
            addr = sms.get("address", "")
            if them_name and them_name not in addr:
                continue
            type_ = sms.get("type", "1")  # 1=received, 2=sent
            body = sms.get("body", "").strip()
            date_ms = int(sms.get("date", "0"))
            ts = datetime.fromtimestamp(date_ms / 1000).isoformat()
            if not body:
                continue
            messages.append({
                "time_str": ts,
                "raw_sender": me_name if type_ == "2" else (addr or them_name),
                "content": body,
            })
    except Exception as e:
        print(f"SMS 解析错误: {e}", file=sys.stderr)
    return messages


def parse_plain_text(file_path: str, me_name: str, them_name: str) -> list[dict]:
    """
    解析纯文本粘贴格式，尝试多种常见格式：
    - "发送人: 内容"
    - "[时间] 发送人: 内容"
    - "发送人 时间\\n内容"（微信桌面版复制格式）
    """
    messages = []
    pattern = re.compile(
        r"^(?:\[?(?P<time>[\d\-/: ]{8,19})\]?\s+)?(?P<sender>.+?)[:：]\s*(?P<content>.+)$"
    )
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = pattern.match(line)
        if m:
            messages.append({
                "time_str": (m.group("time") or "").strip(),
                "raw_sender": m.group("sender").strip(),
                "content": m.group("content").strip(),
            })
    return messages


# ─────────────────────────────────────────────
# 规格化 & �rich
# ─────────────────────────────────────────────

_TS_PATTERNS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
]


def parse_ts(ts_str: str) -> str | None:
    """将各种字符串时间转换为 ISO 格式，失败返回 None。"""
    ts_str = ts_str.strip()
    if not ts_str:
        return None
    for fmt in _TS_PATTERNS:
        try:
            return datetime.strptime(ts_str[:len(fmt)], fmt).isoformat()
        except ValueError:
            continue
    # 尝试解析已经是 ISO 格式的
    try:
        return datetime.fromisoformat(ts_str).isoformat()
    except ValueError:
        return None


def normalize(raw_msgs: list[dict], me_name: str, them_name: str) -> list[dict]:
    """将原始消息列表规格化为统一输出格式，并按时间排序。"""
    result = []
    for msg in raw_msgs:
        content = msg.get("content", "").strip()
        if not content:
            continue
        # 过滤系统消息
        if any(pat in content for pat in SKIP_PATTERNS):
            continue

        raw_sender = msg.get("raw_sender", "")
        if me_name and me_name in raw_sender:
            sender = "me"
        elif them_name and them_name in raw_sender:
            sender = "them"
        else:
            # 启发式：如果只有两个发送人，后续会remap
            sender = "unknown"

        ts = parse_ts(msg.get("time_str", ""))

        # 特征提取
        has_emoji = bool(EMOJI_PATTERN.search(content))
        has_question = any(content.endswith(q) or content.rstrip("~…！!") .endswith(q) for q in QUESTION_ENDINGS)
        # 亲昵称呼：叫了对方名字或常见称呼
        affection_words = [them_name, me_name, "宝", "亲", "baby", "dear", "honey",
                           "老公", "老婆", "笨蛋", "傻瓜"]
        has_affection_call = any(w and w in content for w in affection_words)

        result.append({
            "ts": ts,
            "sender": sender,
            "raw_sender": raw_sender,
            "content": content,
            "len": len(content),
            "has_question": has_question,
            "has_emoji": has_emoji,
            "has_affection_call": has_affection_call,
            "sentiment_raw": None,
        })

    # 尝试把 unknown sender 重映射为 me / them（当只有两人时）
    senders = {m["raw_sender"] for m in result if m["sender"] == "unknown"}
    if senders and not any(m["sender"] in ("me", "them") for m in result):
        senders = sorted(senders)
        mapping = {senders[0]: "me", senders[1]: "them"} if len(senders) >= 2 else {senders[0]: "me"}
        for m in result:
            if m["sender"] == "unknown" and m["raw_sender"] in mapping:
                m["sender"] = mapping[m["raw_sender"]]

    # 按时间排序
    def sort_key(m):
        return m["ts"] or ""
    result.sort(key=sort_key)

    return result


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

FORMAT_MAP = {
    "wechat_txt": parse_wechat_txt,
    "wechat_html": parse_wechat_html,
    "wechat_csv": parse_wechat_csv,
    "imessage": parse_imessage,
    "sms": parse_sms_xml,
    "plain": parse_plain_text,
}

EXT_FORMAT_MAP = {
    ".txt": "wechat_txt",
    ".html": "wechat_html",
    ".htm": "wechat_html",
    ".csv": "wechat_csv",
    ".db": "imessage",
    ".xml": "sms",
}


def main():
    parser = argparse.ArgumentParser(description="聊天记录双向解析器")
    parser.add_argument("--file", required=True, help="输入文件路径")
    parser.add_argument("--me",   required=True, help="我方的名字（昵称）")
    parser.add_argument("--them", required=True, help="对方的名字（昵称）")
    parser.add_argument("--format", default=None,
                        choices=list(FORMAT_MAP.keys()),
                        help="强制指定格式（默认按文件扩展名自动判断）")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认 stdout）")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"错误：文件不存在 {file_path}", file=sys.stderr)
        sys.exit(1)

    fmt = args.format or EXT_FORMAT_MAP.get(file_path.suffix.lower(), "plain")
    parse_fn = FORMAT_MAP[fmt]

    raw = parse_fn(str(file_path), args.me, args.them)
    messages = normalize(raw, args.me, args.them)

    if not messages:
        print("警告：未解析到任何消息，请检查 --me / --them 名字是否与文件一致。", file=sys.stderr)

    output_json = json.dumps(messages, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        me_count = sum(1 for m in messages if m["sender"] == "me")
        them_count = sum(1 for m in messages if m["sender"] == "them")
        print(f"✅ 解析完成：共 {len(messages)} 条消息（我方 {me_count} 条 / 对方 {them_count} 条）")
        print(f"   输出：{args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
