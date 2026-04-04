---
name: heartbeat
description: "将千万条聊天记录，还原成你们心跳共振的轨迹。生成双向折线图与情感诊断报告"
argument-hint: "[me-name] [them-name]"
version: "1.0.0"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash
---

> **语言 / Language**: 根据用户第一条消息的语言全程使用同一语言。中文指令在前，English version follows the Chinese section.

# Heartbeat（Claude Code 版）

> *"情绪的起伏，藏在那些没有说出口的停顿里。"*
> *将千万条聊天记录，还原成你们心跳共振的轨迹。*

## 触发条件

启动 **复盘型分析**：
- `/heartbeat-review`
- "帮我分析聊天记录的好感度曲线"
- "分析我们的关系走势"
- "看看我们的好感度"

启动 **追踪型分析**（新建基线）：
- `/heartbeat-track`
- "我想追踪我们的情感变化"
- "建立好感度追踪"

**追加更新**（已有追踪会话时）：
- `/heartbeat-update`
- "更新曲线" / "我有新的聊天记录"

**管理命令**：
- `/heartbeat-list` — 列出所有已保存的分析会话
- `/heartbeat-delete {slug}` — 删除指定会话

---

## 工具使用规则

| 任务 | 使用工具 |
|------|---------|
| 读取 TXT / MD / CSV 文件 | `Read` 工具 |
| 读取图片截图 / PDF | `Read` 工具（原生支持） |
| 解析聊天记录（双向） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/chat_parser.py` |
| 规则评分（底层） | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/sentiment_scorer.py` |
| **CC 语义打分（核心）** | 读取 prompt → 直接分析消息内容 → 输出 JSON |
| 融合两层分数 | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/score_merger.py` |
| 生成折线图 | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/heartbeat_plotter.py` |
| 生成文字报告 | `Bash` → `python3 ${CLAUDE_SKILL_DIR}/tools/report_writer.py` |
| 写入会话文件 | `Write` / `Edit` 工具 |

**基础目录**：所有会话文件写入 `./sessions/{slug}/`（相对于本项目目录）。

---

## 主流程：全新分析

### Step 1：信息采集

参考 `${CLAUDE_SKILL_DIR}/prompts/intake.md` 的问题序列，询问 4 个问题：

1. 双方昵称（必填）
2. 关系背景（必填，一句话）
3. 分析模式：[A] 复盘型 / [B] 追踪型（必填）
4. 特殊时间节点补充（可选，用于在曲线上标注事件）

**slug 生成规则**：`them-name` 的拼音或英文小写 + 4位随机数字，例如 `xiaohong-2891`。

收集完成后汇总确认：
```
确认信息：
- 我方：{me_name}
- 对方：{them_name}
- 模式：复盘型 / 追踪型
- 特殊节点：{events 或"无"}

确认后开始导入聊天记录？
```

---

### Step 2：聊天记录导入

展示以下选项：

```
聊天记录怎么提供？

  [A] 微信聊天记录（TXT / HTML / CSV）
      WechatExporter 等工具导出的文件

  [B] iMessage
      macOS 的 chat.db 文件（需 Full Disk Access）
      或已导出的文本文件

  [C] SMS 短信
      Android 备份 XML 文件

  [D] 直接粘贴文本
      把聊天内容复制进来

可以混用多种方式。
```

---

#### 方式 A：微信聊天记录

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/chat_parser.py \
  --file {path} \
  --me "{me_name}" \
  --them "{them_name}" \
  --output /tmp/heartbeat_parsed.json
```

支持 `.txt` / `.html` / `.csv`，自动识别格式。

---

#### 方式 B：iMessage

```bash
# 指定导出文件
python3 ${CLAUDE_SKILL_DIR}/tools/chat_parser.py \
  --file {path_to_chat.db_or_export} \
  --format imessage \
  --me "{me_name}" \
  --them "{them_phone_or_name}" \
  --output /tmp/heartbeat_parsed.json
```

---

#### 方式 C：SMS XML

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/chat_parser.py \
  --file {path_to_sms_backup.xml} \
  --format sms \
  --me "{me_name}" \
  --them "{them_phone_or_name}" \
  --output /tmp/heartbeat_parsed.json
```

---

#### 方式 D：粘贴文本

将用户粘贴的内容写入 `/tmp/heartbeat_pasted.txt`：
```bash
cat > /tmp/heartbeat_pasted.txt << 'CHATEOF'
{粘贴内容}
CHATEOF
```

然后：
```bash
python3 ${CLAUDE_SKILL_DIR}/tools/chat_parser.py \
  --file /tmp/heartbeat_pasted.txt \
  --format plain \
  --me "{me_name}" \
  --them "{them_name}" \
  --output /tmp/heartbeat_parsed.json
```

---

解析完成后汇报结果：
```
✅ 解析完成：共 {N} 条消息（我方 {me_count} 条 / 对方 {them_count} 条）
时间跨度：{start_date} → {end_date}
```

如果解析结果中某方消息为 0，提示用户检查名字是否匹配。

---

### Step 3：双层评分（规则 + Claude 语义）

#### 3a. 规则层评分

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/sentiment_scorer.py \
  --input /tmp/heartbeat_parsed.json \
  --window auto \
  --output /tmp/rule_scores.json
```

---

#### 3b. 按时间窗口分组，准备 CC 分析数据

```bash
python3 - << 'EOF'
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

parsed = json.loads(Path("/tmp/heartbeat_parsed.json").read_text())
rule   = json.loads(Path("/tmp/rule_scores.json").read_text())

# 按规则层的窗口划分，将消息分组
windows = {r["window"]: r["label"] for r in rule}

# 对每条消息确定所属窗口
def get_window(ts, w_labels):
    for wk, lbl in w_labels.items():
        if ts and ts[:10] >= lbl[:10]:
            last = wk
    return last if 'last' in dir() else list(w_labels.keys())[0]

groups = defaultdict(list)
for msg in parsed:
    ts = msg.get("ts") or ""
    # 找最近窗口（简单：按 label date 比较）
    best = None
    for r in rule:
        if ts[:10] >= r["label"][:10]:
            best = r["window"]
    if best:
        groups[best].append({
            "sender": msg["sender"],
            "content": msg["content"],
            "ts": ts,
        })

data = {"windows": [
    {"window": r["window"], "label": r["label"], "messages": groups.get(r["window"], [])}
    for r in rule
]}
Path("/tmp/heartbeat_windows.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(f"已生成 {len(rule)} 个时间窗口分组 → /tmp/heartbeat_windows.json")
EOF
```

---

#### 3c. **[CC 核心步骤] Claude 语义打分**

读取评分 prompt：
```
Read ${CLAUDE_SKILL_DIR}/prompts/cc_scorer_prompt.md
```

然后读取分组数据：
```
Read /tmp/heartbeat_windows.json
```

**按照 `cc_scorer_prompt.md` 的指令，对每个时间窗口进行语义分析：**

- 真正阅读每条消息的内容、语气、潜台词
- 结合上下文判断情感状态（不是统计关键词）
- 对「我方」和「对方」分别打分（0–100整数）
- 标注该窗口的关键事件（如有）
- 对消息极少的窗口（<3条）标注 `"confidence": "low"`

将分析结果以**严格 JSON 格式**写入 `/tmp/cc_scores.json`：
```bash
# 将上面 CC 分析得到的 JSON 写入文件
python3 -c "
import json, pathlib
cc_result = {CC_OUTPUT_JSON}  # 替换为实际的 CC 分析结果
pathlib.Path('/tmp/cc_scores.json').write_text(json.dumps(cc_result, ensure_ascii=False, indent=2))
print('CC 评分已写入 /tmp/cc_scores.json')
"
```

> 💡 **注意**：cc_scores.json 中每个窗口的 `events` 字段也必须在此步骤填写，
> 用户在 Step 1 提供的时间节点要匹配到对应窗口，并加入 events 数组。

---

#### 3d. 融合两层分数

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/score_merger.py \
  --rule /tmp/rule_scores.json \
  --cc   /tmp/cc_scores.json \
  --rule-weight 0.2 \
  --output /tmp/heartbeat_scores.json
```

融合策略：**CC 语义分数权重 80%，规则分数权重 20%**。
当某窗口 CC confidence 为 `"low"` 时，自动切换为规则优先（规则 60% / CC 40%）。

---

### Step 4：生成图表和报告

**生成折线图**：
```bash
python3 ${CLAUDE_SKILL_DIR}/tools/heartbeat_plotter.py \
  --scores /tmp/heartbeat_scores.json \
  --me "{me_name}" \
  --them "{them_name}" \
  --output /tmp/heartbeat_preview.png
```

**生成文字报告**：
```bash
python3 ${CLAUDE_SKILL_DIR}/tools/report_writer.py \
  --scores /tmp/heartbeat_scores.json \
  --parsed /tmp/heartbeat_parsed.json \
  --me "{me_name}" \
  --them "{them_name}" \
  --mode {review|track} \
  --output /tmp/heartbeat_report_preview.md
```

---

#### Step 4b：最终 AI 深度心理剖析 (Final AI Diagnosis)

报告的基础框架生成后，你需要基于你在前面步骤中**阅读过的全部原生聊天文本的记忆**，再加上这篇 `_report_preview.md` 里的精准量化数据，亲自撰写最后的深度剖析。

```
Read ${CLAUDE_SKILL_DIR}/prompts/cc_final_diagnosis_prompt.md
Read /tmp/heartbeat_report_preview.md
```

按照 `cc_final_diagnosis_prompt.md` 的专家指令，生成一份 500 字以上的深度情感心理测写长文。
**直接将你生成的这段 Markdown 文本（以 `## 七、AI 深度心理剖析与侧写` 开头），通过 Bash/Edit 工具原生追加（Append）到 `/tmp/heartbeat_report_preview.md` 文件的最末尾！**

---

### 向用户展示

读取追加完你心血剖析的完整报告内容后，向用户展示摘要预览（关系概况表 + 阶段判断 + 前 2 个关键节点 + 你刚写的一句核心判词），询问确认：

```
📊 分析完成，预览摘要：

  时间跨度：{start} → {end}
  消息总量：{N} 条
  我方平均好感度：{me_avg} → {me_phase}
  对方平均好感度：{them_avg} → {them_phase}

  💡 核心判定：{你的判词内容}

确认保存完整报告和图表？
```

---

### Step 5：保存到 sessions/

用户确认后：

**1. 创建目录结构**：
```bash
mkdir -p sessions/{slug}/history
```

**2. 复制最终文件**：
```bash
cp /tmp/heartbeat_scores.json   sessions/{slug}/scores.json
cp /tmp/heartbeat_parsed.json   sessions/{slug}/parsed.json
cp /tmp/heartbeat_preview.png   sessions/{slug}/heartbeat.png
cp /tmp/heartbeat_report_preview.md sessions/{slug}/report.md
```

**3. 写入 meta.json**（用 Write 工具）：
路径：`sessions/{slug}/meta.json`
```json
{
  "slug": "{slug}",
  "me": "{me_name}",
  "them": "{them_name}",
  "mode": "review | track",
  "created_at": "{ISO时间}",
  "updated_at": "{ISO时间}",
  "version": 1,
  "background": "{用户提供的关系背景}",
  "window": "day | week | month",
  "msg_count": {N},
  "time_range": ["{start}", "{end}"],
  "user_events": [...用户提供的时间节点]
}
```

告知用户：
```
✅ 分析完成，已保存！

📁 文件位置
   sessions/{slug}/
     ├── heartbeat.png     ← 好感度折线图
     ├── report.md     ← 完整分析报告
     ├── scores.json   ← 评分数据
     └── meta.json     ← 会话信息

如需追加新记录，输入 /heartbeat-update 即可。
```

---

## 追加更新模式（/heartbeat-update）

当用户提供新聊天记录时：

1. 询问用户选择哪个 slug（或自动匹配最近的一个）
2. 读取 `sessions/{slug}/meta.json` 获取配置
3. 按 Step 2 方式解析新记录到 `/tmp/heartbeat_new.json`
4. 合并新旧记录：
   ```bash
   python3 - << 'EOF'
   import json
   from pathlib import Path

   old = json.loads(Path("sessions/{slug}/parsed.json").read_text())
   new = json.loads(Path("/tmp/heartbeat_new.json").read_text())
   merged = old + new
   # 去重（按 ts + content）
   seen = set()
   deduped = []
   for m in merged:
       key = (m.get("ts",""), m.get("content",""))
       if key not in seen:
           seen.add(key)
           deduped.append(m)
   deduped.sort(key=lambda m: m.get("ts") or "")
   Path("/tmp/heartbeat_merged.json").write_text(json.dumps(deduped, ensure_ascii=False, indent=2))
   print(f"合并完成：{len(old)} + {len(new)} → {len(deduped)} 条（去重后）")
   EOF
   ```
5. 对合并后的数据重新评分和绘图
6. 备份旧版本：
   ```bash
   cp sessions/{slug}/heartbeat.png   sessions/{slug}/history/heartbeat_v{old_version}.png
   cp sessions/{slug}/report.md   sessions/{slug}/history/report_v{old_version}.md
   cp sessions/{slug}/scores.json sessions/{slug}/history/scores_v{old_version}.json
   ```
7. 用新文件覆盖 `sessions/{slug}/`，更新 meta.json 的 version 和 updated_at

---

## 管理命令

### /heartbeat-list

```bash
python3 - << 'EOF'
import json, os
from pathlib import Path

sessions_dir = Path("sessions")
if not sessions_dir.exists():
    print("暂无任何分析会话。")
else:
    sessions = sorted(sessions_dir.iterdir())
    if not sessions:
        print("暂无任何分析会话。")
    else:
        print(f"{'Slug':<20} {'对方':<12} {'模式':<8} {'版本':<6} {'更新时间'}")
        print("-" * 60)
        for s in sessions:
            meta_path = s / "meta.json"
            if meta_path.exists():
                m = json.loads(meta_path.read_text())
                print(f"{m['slug']:<20} {m['them']:<12} {m['mode']:<8} v{m['version']:<5} {m['updated_at'][:10]}")
EOF
```

### /heartbeat-delete {slug}

确认后：
```bash
rm -rf sessions/{slug}
```

---

---

# English Version

# Heartbeat (Claude Code Edition)

> *"The rhythm of feelings, hidden in every 'typing...'."*
> *Turn thousands of chat logs back into the trajectory of your resonating heartbeats.*

## Trigger Conditions

Start **Review Mode** (finished relationship):
- `/heartbeat-review`
- "Analyze my chat history for favorability curve"
- "Show me our relationship trend"

Start **Tracking Mode** (ongoing relationship):
- `/heartbeat-track`
- "Track our emotional dynamics"

**Append Update** (when a session exists):
- `/heartbeat-update` / "I have new chat logs"

**Management**:
- `/heartbeat-list` — list all saved analysis sessions
- `/heartbeat-delete {slug}` — delete a session

---

## Tool Usage

| Task | Tool |
|------|------|
| Read TXT / MD / CSV | `Read` tool |
| Read images / PDF | `Read` tool (native support) |
| Parse chat logs (both parties) | `Bash` → `chat_parser.py` |
| Score favorability | `Bash` → `sentiment_scorer.py` |
| Generate chart | `Bash` → `heartbeat_plotter.py` |
| Generate text report | `Bash` → `report_writer.py` |
| Write session files | `Write` / `Edit` tool |

**Base directory**: `./sessions/{slug}/`

---

## Main Flow: New Analysis

### Step 1: Info Collection

Refer to `${CLAUDE_SKILL_DIR}/prompts/intake.md`. Ask 4 questions:

1. Both parties' names (required)
2. Relationship background — one sentence (required)
3. Mode: [A] Review / [B] Track (required)
4. Special time events to mark on chart (optional)

**Slug format**: lowercase `them-name` + 4 random digits, e.g. `amy-4821`

---

### Step 2: Chat Log Import

Show options:

```
How would you like to provide chat logs?

  [A] WeChat (TXT / HTML / CSV)
  [B] iMessage (chat.db or export)
  [C] SMS (Android XML backup)
  [D] Paste text directly

You can mix multiple sources.
```

For each option, run chat_parser.py with the appropriate `--format` flag.
Output to `/tmp/heartbeat_parsed.json`.

---

### Step 3: Dual-Layer Scoring (Rule + CC Semantic)

#### 3a. Rule-based scoring
```bash
python3 ${CLAUDE_SKILL_DIR}/tools/sentiment_scorer.py \
  --input /tmp/heartbeat_parsed.json \
  --window auto \
  --output /tmp/rule_scores.json
```

#### 3b. Group messages by time window → `/tmp/heartbeat_windows.json`
(Run the grouping Python snippet from the Chinese section above)

#### 3c. **[CC Core Step] Claude Semantic Scoring**

```
Read ${CLAUDE_SKILL_DIR}/prompts/cc_scorer_prompt.md
Read /tmp/heartbeat_windows.json
```

Actually read and understand the content of each message in each time window.
Score both parties 0–100 based on genuine language understanding (not keyword counting).
Output a strict JSON array and write it to `/tmp/cc_scores.json`.

Also fill in `events` for key turning points and user-provided time markers.

#### 3d. Merge scores
```bash
python3 ${CLAUDE_SKILL_DIR}/tools/score_merger.py \
  --rule /tmp/rule_scores.json \
  --cc   /tmp/cc_scores.json \
  --rule-weight 0.2 \
  --output /tmp/heartbeat_scores.json
```
Final score = 80% CC semantic + 20% rule-based.

---

### Step 4: Generate Chart & Report

```bash
python3 ${CLAUDE_SKILL_DIR}/tools/heartbeat_plotter.py \
  --scores /tmp/heartbeat_scores.json \
  --me "{me_name}" --them "{them_name}" \
  --output /tmp/heartbeat_preview.png

python3 ${CLAUDE_SKILL_DIR}/tools/report_writer.py \
  --scores /tmp/heartbeat_scores.json \
  --parsed /tmp/heartbeat_parsed.json \
  --me "{me_name}" --them "{them_name}" \
  --mode {review|track} \
  --output /tmp/heartbeat_report_preview.md
```

#### Step 4b: Final AI Semantic Diagnosis
```
Read ${CLAUDE_SKILL_DIR}/prompts/cc_final_diagnosis_prompt.md
Read /tmp/heartbeat_report_preview.md
```
Combine the objective stats from `_report_preview.md` with your memory of the actual chat content from `_windows.json`. Generate a deep, piercing 500-word psychoanalysis markdown following the prompt's persona.
**Append this newly generated Markdown strictly to the end of `/tmp/heartbeat_report_preview.md`.**

Show the user a summary preview including your core judgment quote, ask for confirmation before saving.

---

### Step 5: Save to sessions/

After confirmation:

```bash
mkdir -p sessions/{slug}/history
cp /tmp/heartbeat_scores.json   sessions/{slug}/scores.json
cp /tmp/heartbeat_parsed.json   sessions/{slug}/parsed.json
cp /tmp/heartbeat_preview.png   sessions/{slug}/heartbeat.png
cp /tmp/heartbeat_report_preview.md sessions/{slug}/report.md
```

Write `sessions/{slug}/meta.json` via the `Write` tool.

Notify user:
```
✅ Analysis complete and saved!

📁 Location: sessions/{slug}/
  ├── heartbeat.png    ← Favorability chart
  ├── report.md    ← Full analysis report
  └── scores.json  ← Scoring data

To append new logs later, use /heartbeat-update
```

---

## Update Mode (/heartbeat-update)

1. Load `sessions/{slug}/meta.json`
2. Parse new logs → `/tmp/heartbeat_new.json`
3. Merge with existing parsed.json, deduplicate, re-sort by timestamp
4. Re-run scorer + plotter + report_writer
5. Backup old files to `sessions/{slug}/history/`
6. Overwrite session files with new results, increment version in meta.json

---

## Management

`/heartbeat-list`: List all sessions with slug, name, mode, version, update time.

`/heartbeat-delete {slug}`: Confirm then `rm -rf sessions/{slug}`.
