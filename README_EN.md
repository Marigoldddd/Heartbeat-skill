<div align="center">

# Heartbeat

> *"The rhythm of feelings, hidden in every 'typing...'."*
> *Turn thousands of chat logs back into the trajectory of your resonating heartbeats.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![Codex](https://img.shields.io/badge/Codex-Agent-10a37f)](agents/openai.yaml)

[Quick Start](#quick-start) · [How To Use](#how-to-use) · [Demo](#demo) · [How It Works](#how-it-works) · [Installation Guide](INSTALL_EN.md) · [**中文**](README.md)

</div>

Heartbeat is a bidirectional favorability curve tool for two-person chat history.

You feed it chat logs, and it produces two outputs:
- a dual-line chart showing how "Me" and "Them" change over time
- a diagnosis report summarizing relationship phases, turning points, behavior patterns, and an overall assessment

It can run as a Claude Code skill, a Codex agent, or a standalone Python CLI tool.

## When It Is Useful

- 💔 Reviewing a relationship that has already ended or cooled down
- 🌙 Tracking an ongoing interaction over time
- 🧭 Turning a vague "something feels off" into a timeline and structured report

## Inputs And Outputs

**Inputs**
- 💬 WeChat exports in `.txt`, `.html`, or `.csv`
- 🍎 iMessage exports
- 📱 Android SMS backup XML
- ✍️ plain pasted text

**Outputs**
- 📈 `heartbeat.png`: dual favorability line chart
- 📝 `report.md`: written diagnosis report
- 🗂️ `scores.json` / `parsed.json`: intermediate scoring and parsed data for follow-up analysis

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

> Claude Code / Codex setup and global installation steps are in [INSTALL_EN.md](INSTALL_EN.md).

### 2. Pick One Entry Point

#### Claude Code

```text
/heartbeat-review    Review an ended or declining relationship
/heartbeat-track     Start continuous tracking
/heartbeat-update    Append new chat logs and refresh the curve
/heartbeat-list      List saved analysis sessions
```

#### Codex

```text
Use $heartbeat to analyze my chat history and generate a favorability curve plus report
Use $heartbeat to create a continuous tracking session
Use $heartbeat to update an existing session with new messages
```

#### CLI

```bash
# 1) Parse the chat log
python3 tools/chat_parser.py --file chat.txt --me "Me" --them "Them" --output parsed.json

# 2) Calculate bidirectional scores
python3 tools/sentiment_scorer.py --input parsed.json --window week --output scores.json

# 3) Generate the chart
python3 tools/heartbeat_plotter.py --scores scores.json --me "Me" --them "Them" --output heartbeat.png

# 4) Generate the report
python3 tools/report_writer.py --scores scores.json --parsed parsed.json \
  --me "Me" --them "Them" --mode review --output report.md
```

## How To Use

This repository exposes three entry points:

- 🤖 `SKILL.md`: Claude Code skill definition
- 🧠 `agents/openai.yaml`: Codex agent description
- 🛠️ `tools/*.py`: local Python toolchain for standalone use

If you just want to run it quickly, start with Claude Code or Codex. If you want to integrate it into your own workflow, use the CLI.

## Demo

### 📈 Dual Favorability Line Chart

![Sample Curve](examples/sample_heartbeat.png)

### 📝 Diagnostic Report Sample

> **Overall Assessment**: There is a clear imbalance in emotional investment, and long-term one-sided effort is usually a relationship risk.
> **Key Time Points To Watch**: 2024-01-04, 2024-01-05, 2024-01-09

For a complete example, see [examples/sample_report.md](examples/sample_report.md).

## Features

- 📊 Bidirectional scoring: measures changes for both sides instead of only one
- 🗓️ Multiple time windows: supports day, week, and month aggregation
- 🧾 Two outputs: generates both a chart and a structured report
- 🔄 Two modes: review mode and ongoing tracking mode
- 💬 Multi-format import: WeChat, iMessage, SMS XML, and plain text
- 🔒 Local-first processing: parsing, rule scoring, plotting, and report generation all run locally

## Minimal End-To-End Flow

The standard workflow is:

1. Import the chat log
2. Parse it into a bidirectional message stream
3. Score both sides over time windows
4. Generate the chart and report
5. Save artifacts into `sessions/{slug}/`

Generated session directories look like this:

```text
sessions/{slug}/
├── heartbeat.png
├── report.md
├── scores.json
├── parsed.json
├── meta.json
└── history/
    ├── heartbeat_v1.png
    └── report_v1.md
```

## How It Works

Heartbeat combines two scoring layers:

### 1. 🧠 Semantic Inference Layer

A language model interprets the real tone and context of the conversation, for example:

- whether the same phrase sounds playful, tired, or dismissive
- which exchanges mark a real turning point in the relationship
- when to lower confidence because there is too little data

### 2. 📏 Behavioral Rule Layer

Objective scoring from chat metadata:

| Dimension | Sub-Weight | Description |
|-----------|------------|-------------|
| Initiative | 25% | Who starts conversations more often |
| Reply Speed | 20% | Average reply latency; faster often implies higher engagement |
| Message Length | 15% | Average information density per message |
| Sentiment Density | 25% | Frequency of positive/negative expressions |
| Special Behaviors | 15% | Re-asking, emoji usage, nicknames, and similar cues |

The final curve is not a simple sentiment label. It is a time series produced by combining semantic interpretation with behavioral signals.

## Toolchain

```text
Chat log files
    ↓
tools/chat_parser.py       → parsed.json
    ↓
tools/sentiment_scorer.py  → scores.json
    ↓
tools/heartbeat_plotter.py → heartbeat.png
tools/report_writer.py     → report.md
```

## Privacy Notes

- 🔐 Chat parsing, rule scoring, plotting, and report generation all run locally
- 🏠 The repository itself does not proactively upload raw chat logs anywhere
- ☁️ If you use the semantic layer through Claude Code or Codex, whether any text is sent to a model depends on your actual host and model setup

This is inherently sensitive data. Running it locally and masking personal details when needed is the safer default.

<div align="center">

*Built for use with Claude Code and Codex*

</div>
